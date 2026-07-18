"""A7 state machine — IDLE -> SWEPT -> WAIT_RETRACE -> IN_TRADE.

Consumes a features frame (``prepare_features``) and yields one ``Trade`` record
per completed trade, with R, MAE and MFE. Long and short are handled by a single
sign-parameterised path.

Fills/exits here use a **conservative 5m-bar model**: a limit fills only if price
trades THROUGH the CE by >= 1 tick; management starts on the bar AFTER the fill so
there is never a same-bar entry+exit; and when SL and a target are both touched in
one bar, the STOP is assumed first. Phase 5 replaces this bar model with 1-minute
intrabar resolution — the state-machine logic is unchanged, only the fill model.

Costs are NOT applied here (gross R); the Phase 5 harness wraps entries/exits with
the mandatory cost model. Prices needed for that are recorded on every Trade.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..data.nytime import to_ny
from ..detectors.dol import dol_exists
from ..detectors.filters import news_clear, spread_ok
from ..detectors.mss import mss_confirmed
from ..detectors.sweep import detect_sweep_at
from .fills import BarFillModel
from .params import EngineParams

IDLE, SWEPT, WAIT_RETRACE, IN_TRADE = "IDLE", "SWEPT", "WAIT_RETRACE", "IN_TRADE"
LONG, SHORT = "long", "short"


@dataclass
class Trade:
    direction: str
    trading_day: pd.Timestamp
    entry_time: pd.Timestamp
    entry: float
    sl: float          # initial stop
    tp1: float
    tp2: float
    exit_time: pd.Timestamp
    exit_reason: str
    r_total: float
    tp1_hit: bool
    mae_r: float
    mfe_r: float
    swept_pool: float
    risk_distance: float


@dataclass
class _DirSpec:
    name: str
    sign: int              # +1 long, -1 short
    sweep_dir: str         # sweep of PDL(bull) / PDH(bear)
    dol_dir: str           # target above(bull) / below(bear)
    sweep_pool: str        # which pool is swept: 'pdl' | 'pdh'
    dol_pool: str          # which pool is the draw target: 'pdh' | 'pdl'


_LONG = _DirSpec(LONG, +1, "bull", "bull", "pdl", "pdh")
_SHORT = _DirSpec(SHORT, -1, "bear", "bear", "pdh", "pdl")


def run(features: pd.DataFrame, params: EngineParams, news=None,
        fill_model=None) -> pd.DataFrame:
    """Run the state machine over ``features``; return a DataFrame of trades.

    ``fill_model`` resolves intrabar fills/exits (default: conservative
    :class:`BarFillModel`; pass an ``IntrabarFillModel`` for 1-minute resolution).
    """
    news = list(news or [])
    fill_model = fill_model or BarFillModel()
    idx = features.index
    n = len(features)

    op = features["open"].to_numpy(float)
    hi = features["high"].to_numpy(float)
    lo = features["low"].to_numpy(float)
    cl = features["close"].to_numpy(float)
    atr5 = features["atr"].to_numpy(float)
    atr1h = features["atr1h"].to_numpy(float)
    conf_sh = features["conf_sh"].to_numpy(float)
    conf_sl = features["conf_sl"].to_numpy(float)
    pdh = features["pdh"].to_numpy(float)
    pdl = features["pdl"].to_numpy(float)
    # DEF-LIQ-02 (v2.0): overnight running extremes; absent on older frames
    if "day_run_low" in features.columns:
        run_lo = features["day_run_low"].to_numpy(float)
        run_hi = features["day_run_high"].to_numpy(float)
    else:
        run_lo = np.full(n, np.nan)
        run_hi = np.full(n, np.nan)
    in_kz = features["in_kz"].to_numpy(bool)
    bias = features["bias"].to_numpy(object)
    spread = features["spread"].to_numpy(float)
    tday = features["trading_day"].to_numpy()

    # pierce flags for "swept already today" checks (wick counts)
    pierced_pdl = lo <= (pdl - params.tick)
    pierced_pdh = hi >= (pdh + params.tick)

    # first bar index and killzone-open price per trading day
    day_first: dict = {}
    day_kz_open: dict = {}
    day_kz_open_idx: dict = {}
    for i in range(n):
        dy = tday[i]
        if dy not in day_first:
            day_first[dy] = i
        if in_kz[i] and dy not in day_kz_open:
            day_kz_open[dy] = op[i]
            day_kz_open_idx[dy] = i

    def swept_incl(pool: str, day, upto_incl: int) -> bool:
        arr = pierced_pdl if pool == "pdl" else pierced_pdh
        start = day_first[day]
        return bool(np.any(arr[start:upto_incl + 1]))

    trades: list[Trade] = []
    state = IDLE
    d: _DirSpec | None = None

    # per-day guards
    cur_day = None
    trades_today = 0
    day_r = 0.0
    locked = False
    attempted: set = set()   # (day, dirname, level) — one attempt per pool per day
    # A2 narrative cache: day -> None (no trade today) | (DirSpec, swp_lvl, dol_lvl).
    # Bias + DOL + shallow-floor are the "at 08:30 NY" narrative gate (spec A2) and
    # are evaluated ONCE, at the day's first killzone bar — not re-derived every
    # bar. DOL's reach is a distance from CURRENT price to the opposite pool; at
    # the moment a sweep actually fires, price sits at one extreme of the day's
    # range, i.e. structurally farthest from that opposite pool, so re-checking
    # DOL bar-by-bar would reject genuine setups almost by construction. Freezing
    # it to the killzone-open snapshot is what "all three must be TRUE at 08:30
    # NY" in the spec actually asks for. The LTF mechanical trigger (A3: sweep ->
    # MSS -> FVG) still runs reactively, bar by bar, from there.
    narrative: dict = {}

    # setup carry
    sweep_extreme = np.nan
    swept_pool = np.nan
    dol_lvl = np.nan
    sweep_pen_idx = -1
    swept_bars = 0
    zone = None
    entry = sl0 = sl = tp1 = tp2 = risk_dist = np.nan
    wait_bars = 0
    entry_bar = -1
    bars_in_trade = 0
    remaining = 1.0
    tp1_hit = False
    r_accum = 0.0
    mae = mfe = 0.0
    entry_time = None

    def reset_setup():
        nonlocal state, d, sweep_extreme, swept_pool, swept_bars, zone
        state = IDLE
        d = None
        sweep_extreme = swept_pool = np.nan
        swept_bars = 0
        zone = None

    for i in range(n):
        day = tday[i]
        if day != cur_day:                       # 17:00-NY boundary reset
            cur_day = day
            trades_today = 0
            day_r = 0.0
            locked = False
        ny_t = to_ny(idx[i]).time()

        # ---------------- IN_TRADE management ----------------
        if state == IN_TRADE:
            if i <= entry_bar:                    # no same-bar entry+exit
                continue
            bars_in_trade += 1
            sgn = d.sign
            # excursions vs entry (in R)
            fav = max(sgn * (hi[i] - entry), sgn * (lo[i] - entry)) / risk_dist
            adv = min(sgn * (hi[i] - entry), sgn * (lo[i] - entry)) / risk_dist
            mfe = max(mfe, fav)
            mae = min(mae, adv)

            closed = False
            if not tp1_hit:
                ev = fill_model.pre_tp1(idx[i], hi[i], lo[i], entry, sl, tp1, d.name)
                if ev == "SL":                    # stop assumed first if both
                    r_accum += sgn * (sl0 - entry) / risk_dist * remaining
                    _close(trades, d, day, entry_time, entry, sl0, tp1, tp2,
                           idx[i], "SL", r_accum, tp1_hit, mae, mfe, swept_pool, risk_dist)
                    closed = True
                elif ev == "TP1":
                    frac = params.partial_close_pct / 100.0
                    r_accum += sgn * (tp1 - entry) / risk_dist * frac
                    remaining -= frac
                    tp1_hit = True
                    sl = entry                    # break-even
            else:
                ev = fill_model.post_tp1(idx[i], hi[i], lo[i], entry, sl, tp2, d.name)
                if ev == "SL":
                    r_accum += sgn * (sl - entry) / risk_dist * remaining  # ~0 at BE
                    _close(trades, d, day, entry_time, entry, sl0, tp1, tp2,
                           idx[i], "BE_STOP", r_accum, tp1_hit, mae, mfe, swept_pool, risk_dist)
                    closed = True
                elif ev == "TP2":
                    r_accum += sgn * (tp2 - entry) / risk_dist * remaining
                    _close(trades, d, day, entry_time, entry, sl0, tp1, tp2,
                           idx[i], "TP2", r_accum, tp1_hit, mae, mfe, swept_pool, risk_dist)
                    closed = True

            if not closed:                        # time-based exits at bar close
                if ny_t >= params.flat_time or bars_in_trade >= params.max_bars:
                    reason = "FLAT" if ny_t >= params.flat_time else "MAX_BARS"
                    r_accum += sgn * (cl[i] - entry) / risk_dist * remaining
                    _close(trades, d, day, entry_time, entry, sl0, tp1, tp2,
                           idx[i], reason, r_accum, tp1_hit, mae, mfe, swept_pool, risk_dist)
                    closed = True

            if closed:
                t = trades[-1]
                trades_today += 1
                day_r += t.r_total
                if t.exit_reason == "SL":
                    attempted.add((day, d.name, swept_pool))
                if day_r <= -params.daily_stop_r:
                    locked = True
                reset_setup()
            continue

        # ---------------- entry-path guards ----------------
        entry_ok = (not locked and trades_today < params.max_trades
                    and day_r > -params.daily_stop_r and in_kz[i])

        # ---------------- IDLE ----------------
        if state == IDLE:
            if not entry_ok:
                continue

            if day not in narrative:                # A2: evaluate once, at 08:30 NY
                kz_idx = day_kz_open_idx.get(day)
                kz_open = day_kz_open.get(day)
                nb = bias[kz_idx] if kz_idx is not None else None
                nd = (_LONG if nb == "BULLISH" else _SHORT if nb == "BEARISH" else None)
                entry_narrative = None
                if nd is not None and kz_idx is not None:
                    # DEF-LIQ-02: sweep pool = overnight session extreme, frozen
                    # at kz open; PDL/PDH fallback when no overnight bars exist.
                    if nd.name == LONG:
                        n_swp_lvl = run_lo[kz_idx] if np.isfinite(run_lo[kz_idx]) else pdl[kz_idx]
                        n_dol_lvl = pdh[kz_idx]
                    else:
                        n_swp_lvl = run_hi[kz_idx] if np.isfinite(run_hi[kz_idx]) else pdh[kz_idx]
                        n_dol_lvl = pdl[kz_idx]
                    if np.isfinite(n_swp_lvl) and np.isfinite(n_dol_lvl):
                        shallow = ((kz_open - n_swp_lvl) < params.shallow_floor_price
                                   if nd.name == LONG
                                   else (n_swp_lvl - kz_open) < params.shallow_floor_price)
                        dol_swept = swept_incl(nd.dol_pool, day, kz_idx)
                        if not shallow and dol_exists(kz_open, n_dol_lvl, atr1h[kz_idx],
                                                      nd.dol_dir, dol_swept, params.dol_reach):
                            entry_narrative = (nd, n_swp_lvl, n_dol_lvl)
                narrative[day] = entry_narrative

            cached = narrative[day]
            if cached is None:
                continue
            d, swp_lvl, dol_lvl = cached
            if (day, d.name, swp_lvl) in attempted:
                continue

            sweep = detect_sweep_at(features, i, swp_lvl, d.sweep_dir,
                                    params.tick, params.sweep_close_n)
            if sweep is None:
                continue
            # N3 fuel unspent: no same-day penetration of the pool before this
            # sweep's own penetration (level-based — the pool is per-day now)
            fs = day_first[day]
            if d.name == LONG:
                fuel_spent = bool(np.any(lo[fs:sweep.penetration_idx] <= swp_lvl - params.tick))
            else:
                fuel_spent = bool(np.any(hi[fs:sweep.penetration_idx] >= swp_lvl + params.tick))
            if fuel_spent:
                continue
            sweep_extreme = sweep.extreme
            swept_pool = swp_lvl
            sweep_pen_idx = sweep.penetration_idx
            swept_bars = 0
            state = SWEPT
            continue

        # ---------------- SWEPT ----------------
        if state == SWEPT:
            if not in_kz[i]:                      # setup must form in killzone
                reset_setup(); continue
            swept_bars += 1
            if swept_bars > params.mss_window:    # sweep stale
                reset_setup(); continue
            swing = conf_sh[i] if d.name == LONG else conf_sl[i]
            zone = mss_confirmed(features, features["atr"], i, d.sweep_dir, swing,
                                 params.disp_mult, params.fvg_min, params.fvg_max,
                                 params.disp_max)
            if zone is None:
                continue
            # build order levels
            entry = zone.ce
            # v2.0 TP1 = displacement-leg extreme (sweep penetration bar -> MSS
            # bar): the internal liquidity this manipulation->displacement leg
            # actually created — strictly beyond a CE entry, known at placement.
            if d.name == LONG:
                sl0 = sweep_extreme - params.sl_buffer_price
                tp1 = float(np.max(hi[sweep_pen_idx:i + 1]))
                tp2 = dol_lvl                    # TP2 = frozen DOL target (kz open)
            else:
                sl0 = sweep_extreme + params.sl_buffer_price
                tp1 = float(np.min(lo[sweep_pen_idx:i + 1]))
                tp2 = dol_lvl
            risk_dist = abs(entry - sl0)
            if risk_dist <= 0:
                reset_setup(); continue
            rr1 = d.sign * (tp1 - entry) / risk_dist   # RR to TP1
            if rr1 < 1.0:                          # skip low-RR setups
                reset_setup(); continue
            sl = sl0
            wait_bars = 0
            state = WAIT_RETRACE
            continue

        # ---------------- WAIT_RETRACE ----------------
        if state == WAIT_RETRACE:
            wait_bars += 1
            if wait_bars > params.expiry_bars or ny_t >= params.kz_end:
                reset_setup(); continue
            ev = fill_model.wait(idx[i], hi[i], lo[i], entry, tp1, params.tick, d.name)
            if ev == "FILL":
                if not (spread_ok(spread[i], params.max_spread_pips, params.pip)
                        and news_clear(idx[i], news, params.news_window_min)):
                    reset_setup(); continue        # blocked at fill time
                entry_bar = i
                entry_time = idx[i]
                bars_in_trade = 0
                remaining = 1.0
                tp1_hit = False
                r_accum = 0.0
                mae = mfe = 0.0
                state = IN_TRADE
                continue
            if ev == "TP1_FIRST":                  # ran to target without filling
                reset_setup(); continue
            continue

    cols = [f.name for f in Trade.__dataclass_fields__.values()]
    return pd.DataFrame([{c: getattr(t, c) for c in cols} for t in trades], columns=cols)


def _close(trades, d, day, entry_time, entry, sl0, tp1, tp2, exit_time, reason,
           r_total, tp1_hit, mae, mfe, swept_pool, risk_dist):
    trades.append(Trade(
        direction=d.name, trading_day=day, entry_time=entry_time, entry=entry,
        sl=sl0, tp1=tp1, tp2=tp2, exit_time=exit_time, exit_reason=reason,
        r_total=r_total, tp1_hit=tp1_hit, mae_r=mae, mfe_r=mfe,
        swept_pool=swept_pool, risk_distance=risk_dist,
    ))

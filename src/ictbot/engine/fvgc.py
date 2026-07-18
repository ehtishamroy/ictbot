"""EURUSD-FVGC v1.0 — Fair Value Gap Continuation engine.

Pre-registered (docs/spec/PREREG_EURUSD-FVGC_v1.0.md). A deliberately small,
single-mechanism state machine, separate from the archived sweep engine but
reusing the shared primitives (ATR, FVG detection, intrabar 1m fills, cost model,
metrics, gates, reporting).

Flow per 5m bar inside the 07:00-16:00 UTC session:
  IDLE      -> a fresh, displacement-born FVG aligned with the EMA trend appears;
               place a limit at its PROXIMAL (near) edge          -> WAIT_FILL
  WAIT_FILL -> price trades THROUGH the proximal edge by >=1 tick -> IN_TRADE
               (expires after expiry_bars or at session end)
  IN_TRADE  -> fixed target at rr_target x initial risk; stop beyond the FVG's
               distal edge; hard flat at session end; max_hold_bars guard.

No partials, no break-even, one target — fewer knobs, cleaner test.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..config import Config
from ..detectors.fvg import BEAR, BULL, detect_fvg
from ..indicators.atr import atr
from .params import INT_FREE, POINT_EURUSD, PIP_EURUSD

LONG, SHORT = "long", "short"
IDLE, WAIT_FILL, IN_TRADE = "IDLE", "WAIT_FILL", "IN_TRADE"

_FVGC_FREE = {
    "ema_len": "ema_len", "fvg_min": "fvg_min_atr", "disp_mult": "disp_mult",
    "rr_target": "rr_target", "sl_buffer_points": "sl_buffer_points",
    "expiry_bars": "expiry_bars",
}
_FVGC_INT = {"ema_len", "expiry_bars"}


@dataclass(frozen=True)
class FvgcParams:
    ema_len: int
    fvg_min: float
    disp_mult: float
    rr_target: float
    sl_buffer_points: float
    expiry_bars: int
    atr_len: int
    fvg_max: float
    disp_max: float
    risk_pct: float
    max_trades_per_day: int
    daily_stop_r: float
    max_hold_bars: int
    max_spread_pips: float
    session_start_h: int
    session_end_h: int
    point: float
    pip: float
    ranges: dict = field(default_factory=dict)

    @property
    def tick(self) -> float:
        return self.point

    @property
    def sl_buffer_price(self) -> float:
        return self.sl_buffer_points * self.point

    def replace(self, **kw) -> "FvgcParams":
        return dataclasses.replace(self, **kw)

    def clamp_free(self, name: str, value: float) -> float:
        lo, hi = self.ranges.get(name, (value, value))
        value = min(max(value, lo), hi)
        return int(round(value)) if name in _FVGC_INT else value

    @classmethod
    def from_config(cls, cfg: Config, point: float = POINT_EURUSD,
                    pip: float = PIP_EURUSD) -> "FvgcParams":
        f, s = cfg.fixed, cfg.session
        return cls(
            ema_len=int(cfg.p("ema_len")), fvg_min=float(cfg.p("fvg_min_atr")),
            disp_mult=float(cfg.p("disp_mult")), rr_target=float(cfg.p("rr_target")),
            sl_buffer_points=float(cfg.p("sl_buffer_points")),
            expiry_bars=int(cfg.p("expiry_bars")),
            atr_len=int(f["atr_len"]), fvg_max=float(f["fvg_max_atr"]),
            disp_max=float(f["disp_max_atr"]), risk_pct=float(f["risk_pct"]),
            max_trades_per_day=int(f["max_trades_per_day"]),
            daily_stop_r=float(f["daily_stop_r"]), max_hold_bars=int(f["max_hold_bars"]),
            max_spread_pips=float(f["max_spread_pips"]),
            session_start_h=int(s["start_utc_h"]), session_end_h=int(s["end_utc_h"]),
            point=point, pip=pip,
            ranges={fld: tuple(cfg.free[k].__dict__[x] for x in ("lo", "hi"))
                    for fld, k in _FVGC_FREE.items() if k in cfg.free},
        )


@dataclass
class FvgcTrade:
    direction: str
    trading_day: pd.Timestamp
    entry_time: pd.Timestamp
    entry: float
    sl: float
    tp: float
    exit_time: pd.Timestamp
    exit_reason: str
    r_total: float
    tp1_hit: bool          # always False (single target) — for cost-model API
    mae_r: float
    mfe_r: float
    risk_distance: float


def prepare_fvgc_features(df5: pd.DataFrame, params: FvgcParams,
                          default_spread_price: float | None = None) -> pd.DataFrame:
    out = df5.copy()
    out["atr"] = atr(df5, params.atr_len)
    out["ema"] = df5["close"].ewm(span=params.ema_len, adjust=False).mean()
    h = out.index.hour
    out["in_sess"] = (h >= params.session_start_h) & (h < params.session_end_h)
    out["utc_day"] = out.index.normalize()
    if "spread" not in out.columns:
        out["spread"] = (default_spread_price if default_spread_price is not None
                         else params.max_spread_pips * params.pip)
    return out


def run_fvgc(features: pd.DataFrame, params: FvgcParams, fill_model=None) -> pd.DataFrame:
    """Run the FVGC state machine; return a DataFrame of trades.

    ``fill_model`` (IntrabarFillModel) is used for which-first SL/TP resolution;
    without it, a conservative stop-first bar model is used.
    """
    idx = features.index
    n = len(features)
    op = features["open"].to_numpy(float)
    hi = features["high"].to_numpy(float)
    lo = features["low"].to_numpy(float)
    cl = features["close"].to_numpy(float)
    a = features["atr"].to_numpy(float)
    ema = features["ema"].to_numpy(float)
    in_sess = features["in_sess"].to_numpy(bool)
    spread = features["spread"].to_numpy(float)
    uday = features["utc_day"].to_numpy()
    tick = params.tick

    trades: list[FvgcTrade] = []
    state = IDLE
    cur_day = None
    trades_today = 0
    day_r = 0.0

    # setup / trade carry
    sgn = 0
    entry = sl0 = tp = risk = np.nan
    wait_bars = 0
    entry_bar = -1
    bars_held = 0
    mae = mfe = 0.0
    entry_time = None
    setup_day = None

    def resolve(ts, hi_b, lo_b, sl_lvl, tp_lvl, direction):
        """Return 'SL' | 'TP' | None for this bar (intrabar if available)."""
        if fill_model is not None:
            sub = fill_model.sub_bars(ts)
            if sub is not None:
                mh, ml = sub
                for k in range(len(mh)):
                    if direction == LONG:
                        if ml[k] <= sl_lvl:
                            return "SL"
                        if mh[k] >= tp_lvl:
                            return "TP"
                    else:
                        if mh[k] >= sl_lvl:
                            return "SL"
                        if ml[k] <= tp_lvl:
                            return "TP"
                return None
        # conservative bar model (stop-first)
        if direction == LONG:
            if lo_b <= sl_lvl:
                return "SL"
            if hi_b >= tp_lvl:
                return "TP"
        else:
            if hi_b >= sl_lvl:
                return "SL"
            if lo_b <= tp_lvl:
                return "TP"
        return None

    def filled(ts, hi_b, lo_b, edge, direction):
        """Trade-through the proximal edge by >=1 tick (intrabar if available)."""
        if fill_model is not None:
            sub = fill_model.sub_bars(ts)
            if sub is not None:
                mh, ml = sub
                for k in range(len(mh)):
                    if direction == LONG and ml[k] <= edge - tick:
                        return True
                    if direction == SHORT and mh[k] >= edge + tick:
                        return True
                return False
        return (lo_b <= edge - tick) if direction == LONG else (hi_b >= edge + tick)

    for i in range(n):
        day = uday[i]
        if day != cur_day:
            cur_day = day
            trades_today = 0
            day_r = 0.0

        if state == IN_TRADE:
            if i <= entry_bar:
                continue
            bars_held += 1
            fav = max(sgn * (hi[i] - entry), sgn * (lo[i] - entry)) / risk
            adv = min(sgn * (hi[i] - entry), sgn * (lo[i] - entry)) / risk
            mfe = max(mfe, fav); mae = min(mae, adv)
            direction = LONG if sgn > 0 else SHORT
            ev = resolve(idx[i], hi[i], lo[i], sl0, tp, direction)
            closed = False
            if ev == "SL":
                r = -1.0; reason = "SL"; closed = True
            elif ev == "TP":
                r = params.rr_target; reason = "TP"; closed = True
            elif not in_sess[i] or bars_held >= params.max_hold_bars:
                r = sgn * (cl[i] - entry) / risk
                reason = "FLAT" if not in_sess[i] else "MAX_BARS"; closed = True
            if closed:
                trades.append(FvgcTrade(
                    direction, setup_day, entry_time, entry, sl0, tp, idx[i], reason,
                    r, False, mae, mfe, risk))
                trades_today += 1; day_r += r
                state = IDLE
            continue

        # entry-path guards
        if not in_sess[i] or trades_today >= params.max_trades_per_day \
                or day_r <= -params.daily_stop_r:
            state = IDLE
            continue

        if state == IDLE:
            if i < 2 or not np.isfinite(a[i]) or a[i] <= 0:
                continue
            up = cl[i] > ema[i]
            dn = cl[i] < ema[i]
            g = detect_fvg(hi, lo, i, a[i], params.fvg_min, params.fvg_max)
            if g is None:
                continue
            if g.direction == BULL and up:
                sgn = 1
            elif g.direction == BEAR and dn:
                sgn = -1
            else:
                continue
            # displacement candle = middle candle (i-1) that opened the gap
            if abs(cl[i - 1] - op[i - 1]) < params.disp_mult * a[i]:
                continue
            if abs(cl[i - 1] - op[i - 1]) > params.disp_max * a[i]:
                continue
            if sgn > 0:                       # bull: proximal = top, distal = bottom
                entry = g.top
                sl0 = g.bottom - params.sl_buffer_price
            else:                             # bear: proximal = bottom, distal = top
                entry = g.bottom
                sl0 = g.top + params.sl_buffer_price
            risk = abs(entry - sl0)
            if risk <= 0:
                continue
            tp = entry + sgn * params.rr_target * risk
            wait_bars = 0
            setup_day = day
            state = WAIT_FILL
            continue

        if state == WAIT_FILL:
            wait_bars += 1
            if wait_bars > params.expiry_bars or not in_sess[i]:
                state = IDLE
                continue
            direction = LONG if sgn > 0 else SHORT
            if filled(idx[i], hi[i], lo[i], entry, direction):
                if spread[i] > params.max_spread_pips * params.pip:
                    state = IDLE
                    continue
                entry_bar = i
                entry_time = idx[i]
                bars_held = 0
                mae = mfe = 0.0
                state = IN_TRADE
            continue

    cols = [f.name for f in FvgcTrade.__dataclass_fields__.values()]
    return pd.DataFrame([{c: getattr(t, c) for c in cols} for t in trades], columns=cols)

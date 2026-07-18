"""Diagnostic v2: trace narrative -> sweep -> SWEPT -> MSS -> FVG -> RR funnel,
using the real engine's detector functions (not a rewrite of their logic)."""
import sys
from collections import Counter

sys.path.insert(0, "src")

import numpy as np
import pandas as pd

from ictbot.config import load_config
from ictbot.detectors.dol import dol_exists
from ictbot.detectors.mss import mss_confirmed
from ictbot.detectors.sweep import detect_sweep_at
from ictbot.engine.features import prepare_features
from ictbot.engine.params import EngineParams
from ictbot.engine.state_machine import LONG, _LONG, _SHORT

df5 = pd.read_pickle("/tmp/df5.pkl")
df1h = pd.read_pickle("/tmp/df1h.pkl")
cfg = load_config("config/nyam_sweep_fvg_v1.0.yaml")
params = EngineParams.from_config(cfg)
feats = prepare_features(df5, df1h, params)

op = feats["open"].to_numpy(float); hi = feats["high"].to_numpy(float)
lo = feats["low"].to_numpy(float); cl = feats["close"].to_numpy(float)
atr1h = feats["atr1h"].to_numpy(float)
conf_sh = feats["conf_sh"].to_numpy(float); conf_sl = feats["conf_sl"].to_numpy(float)
pdh = feats["pdh"].to_numpy(float); pdl = feats["pdl"].to_numpy(float)
in_kz = feats["in_kz"].to_numpy(bool); bias = feats["bias"].to_numpy(object)
tday = feats["trading_day"].to_numpy()
pierced_pdl = lo <= (pdl - params.tick); pierced_pdh = hi >= (pdh + params.tick)

day_first, day_kz_open, day_kz_open_idx = {}, {}, {}
for i in range(len(feats)):
    d = tday[i]
    if d not in day_first: day_first[d] = i
    if in_kz[i] and d not in day_kz_open:
        day_kz_open[d] = op[i]; day_kz_open_idx[d] = i

def swept_incl(pool, day, upto_incl):
    arr = pierced_pdl if pool == "pdl" else pierced_pdh
    return bool(np.any(arr[day_first[day]:upto_incl+1]))

def swept_before(pool, day, upto_excl):
    arr = pierced_pdl if pool == "pdl" else pierced_pdh
    return bool(np.any(arr[day_first[day]:upto_excl]))

# 1. build narrative cache exactly as engine does
narrative = {}
for day, kz_idx in day_kz_open_idx.items():
    nb = bias[kz_idx]
    nd = _LONG if nb == "BULLISH" else _SHORT if nb == "BEARISH" else None
    entry_narrative = None
    if nd is not None:
        n_swp_lvl = pdl[kz_idx] if nd.name == LONG else pdh[kz_idx]
        n_dol_lvl = pdh[kz_idx] if nd.name == LONG else pdl[kz_idx]
        if np.isfinite(n_swp_lvl) and np.isfinite(n_dol_lvl):
            kz_open = day_kz_open[day]
            shallow = ((kz_open - n_swp_lvl) < params.shallow_floor_price if nd.name == LONG
                       else (n_swp_lvl - kz_open) < params.shallow_floor_price)
            dol_swept = swept_incl(nd.dol_pool, day, kz_idx)
            if not shallow and dol_exists(kz_open, n_dol_lvl, atr1h[kz_idx],
                                          nd.dol_dir, dol_swept, params.dol_reach):
                entry_narrative = (nd, n_swp_lvl, n_dol_lvl)
    narrative[day] = entry_narrative

eligible_days = {d: v for d, v in narrative.items() if v is not None}
print("narrative-eligible days:", len(eligible_days), "/", len(narrative))

# 2. for each eligible day, walk killzone bars looking for sweep -> SWEPT -> MSS -> RR
funnel = Counter()
sample_mss_reject = []
for day, (d, swp_lvl, dol_lvl) in eligible_days.items():
    bars = [i for i in range(day_first[day], len(feats))
             if tday[i] == day and in_kz[i]]
    if not bars:
        continue
    found_sweep = False
    entered_swept = False
    mss_ok = False
    rr_ok = False
    swept_bars_count = 0
    sweep_i = None
    for i in bars:
        if (day, d.name, swp_lvl) in set():  # placeholder, attempted tracked globally elsewhere
            pass
        if not found_sweep:
            sw = detect_sweep_at(feats, i, swp_lvl, d.sweep_dir, params.tick, params.sweep_close_n)
            if sw is not None and not swept_before(d.sweep_pool, day, sw.penetration_idx):
                found_sweep = True
                entered_swept = True
                sweep_i = i
                swept_bars_count = 0
                continue
        else:
            swept_bars_count += 1
            if swept_bars_count > params.mss_window:
                break
            swing = conf_sh[i] if d.name == LONG else conf_sl[i]
            zone = mss_confirmed(feats, feats["atr"], i, d.sweep_dir, swing,
                                 params.disp_mult, params.fvg_min, params.fvg_max,
                                 params.disp_max)
            if zone is not None:
                mss_ok = True
                entry = zone.ce
                sweep_extreme = sw.extreme if sweep_i == i - swept_bars_count else None
                # recompute sweep extreme properly: re-run detect at sweep_i
                sw2 = detect_sweep_at(feats, sweep_i, swp_lvl, d.sweep_dir, params.tick, params.sweep_close_n)
                ext = sw2.extreme
                if d.name == LONG:
                    sl0 = ext - params.sl_buffer_price
                    tp1 = swing
                else:
                    sl0 = ext + params.sl_buffer_price
                    tp1 = swing
                risk = abs(entry - sl0)
                if risk > 0:
                    rr1 = d.sign * (tp1 - entry) / risk
                    if rr1 >= 1.0:
                        rr_ok = True
                break
    funnel["days_eligible"] += 1
    if found_sweep: funnel["sweep_found"] += 1
    if mss_ok: funnel["mss_confirmed"] += 1
    if rr_ok: funnel["rr_ok"] += 1

print(funnel)

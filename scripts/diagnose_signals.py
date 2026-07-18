"""Diagnostic: tally why candidate setups die, bar by bar through the IDLE path."""
import sys
import time
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

df1m = pd.read_pickle("/tmp/df1m.pkl")
df5 = pd.read_pickle("/tmp/df5.pkl")
df1h = pd.read_pickle("/tmp/df1h.pkl")

cfg = load_config("config/nyam_sweep_fvg_v1.0.yaml")
params = EngineParams.from_config(cfg)

t0 = time.time()
feats = prepare_features(df5, df1h, params)
print(f"features built in {time.time()-t0:.1f}s")

print("\nbias distribution:", Counter(feats["bias"]))
print("in_kz bars:", int(feats["in_kz"].sum()), "/", len(feats))
print("pdh/pdl non-null:", feats["pdh"].notna().sum(), feats["pdl"].notna().sum())
print("atr non-null:", feats["atr"].notna().sum())
print("atr1h non-null:", feats["atr1h"].notna().sum())
print("atr describe:\n", feats["atr"].describe())
print("atr1h describe:\n", feats["atr1h"].describe())

hi = feats["high"].to_numpy(float)
lo = feats["low"].to_numpy(float)
cl = feats["close"].to_numpy(float)
pdh = feats["pdh"].to_numpy(float)
pdl = feats["pdl"].to_numpy(float)
atr1h = feats["atr1h"].to_numpy(float)
in_kz = feats["in_kz"].to_numpy(bool)
bias = feats["bias"].to_numpy(object)
tday = feats["trading_day"].to_numpy()
conf_sh = feats["conf_sh"].to_numpy(float)
conf_sl = feats["conf_sl"].to_numpy(float)

pierced_pdl = lo <= (pdl - params.tick)
pierced_pdh = hi >= (pdh + params.tick)

day_first = {}
day_kz_open = {}
for i in range(len(feats)):
    d = tday[i]
    if d not in day_first:
        day_first[d] = i
    if in_kz[i] and d not in day_kz_open:
        day_kz_open[d] = feats["open"].to_numpy(float)[i]

reasons = Counter()
n = len(feats)
sweeps_found = 0
mss_found = 0
for i in range(n):
    if not in_kz[i]:
        continue
    d = tday[i]
    b = bias[i]
    if b == "NEUTRAL":
        reasons["neutral_bias"] += 1
        continue
    dirn = 1 if b == "BULLISH" else -1
    swp_lvl = pdl[i] if dirn == 1 else pdh[i]
    dol_lvl = pdh[i] if dirn == 1 else pdl[i]
    if not np.isfinite(swp_lvl) or not np.isfinite(dol_lvl):
        reasons["no_pdh_pdl"] += 1
        continue
    kz_open = day_kz_open.get(d)
    if kz_open is None:
        reasons["no_kz_open"] += 1
        continue
    shallow = ((kz_open - swp_lvl) < params.shallow_floor_price if dirn == 1
               else (swp_lvl - kz_open) < params.shallow_floor_price)
    if shallow:
        reasons["shallow_sweep_floor"] += 1
        continue
    dol_pool_arr = pierced_pdl if (dirn == 1) else pierced_pdh  # dol pool side = swp side of OTHER direction... fix below
    # dol pool is opposite of sweep pool:
    dol_arr = pierced_pdh if dirn == 1 else pierced_pdl
    start = day_first[d]
    dol_swept = bool(np.any(dol_arr[start:i+1]))
    if not dol_exists(cl[i], dol_lvl, atr1h[i], "bull" if dirn==1 else "bear", dol_swept, params.dol_reach):
        reasons["no_dol"] += 1
        continue
    sweep_dir = "bull" if dirn == 1 else "bear"
    sw = detect_sweep_at(feats, i, swp_lvl, sweep_dir, params.tick, params.sweep_close_n)
    if sw is None:
        reasons["no_sweep_this_bar"] += 1
        continue
    sweeps_found += 1
    swp_arr = pierced_pdl if dirn == 1 else pierced_pdh
    if bool(np.any(swp_arr[start:sw.penetration_idx])):
        reasons["fuel_already_spent"] += 1
        continue
    reasons["sweep_ok_would_enter_SWEPT"] += 1

print("\nrejection funnel (killzone bars only):")
for k, v in reasons.most_common():
    print(f"  {k}: {v}")
print("\nsweeps_found (raw sweep_detected hits):", sweeps_found)

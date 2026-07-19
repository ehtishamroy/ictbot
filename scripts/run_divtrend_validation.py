"""DIVTREND v1.0 — full validation per the PRE-REGISTERED protocol.

docs/spec/PREREG_DIVTREND_v1.0.md. Reads the ETF panel from data/raw/etf/,
chronological IS/OOS split, <=20-config IS grid (2 passes), single OOS look.
Gates: cost-robustness PRIMARY (net Sharpe>0 AND net return>0 at 1.5x AND 2x),
OOS Sharpe>=0.40, stability, maxDD<=35%, breadth (leave-one-sleeve-out OOS
Sharpe>0), and Deflated Sharpe (vs cumulative trial count). Reports to reports/.

Run once the ETF CSVs are in data/raw/etf/:
    python3 scripts/run_divtrend_validation.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")

import numpy as np
import pandas as pd

from ictbot.config import load_config
from ictbot.portfolio.backtest import run_divtrend
from ictbot.portfolio.data import load_etf_dir, prices_to_returns, sleeves_for
from ictbot.portfolio.metrics import compute_metrics, deflated_sharpe
from ictbot.portfolio.params import DivtrendParams

T0 = time.time()
def log(m): print(f"[{time.time()-T0:6.1f}s] {m}", flush=True)

CUMULATIVE_PRIOR_TRIALS = 128        # from reports/TRIAL_LEDGER.md
ETF_DIR = sys.argv[1] if len(sys.argv) > 1 else "data/raw/etf"

cfg = load_config("config/divtrend_v1.0.yaml")
base = DivtrendParams.from_config(cfg)
gates_cfg = cfg.backtest["gates"]

prices = load_etf_dir(ETF_DIR)
# Pre-reg B1: every instrument must span the full window. Trim to the common
# window where all instruments have data (ffill already applied by the loader).
prices = prices.dropna()
sleeves = sleeves_for(prices.columns)
log(f"panel: {prices.shape[1]} instruments, common window "
    f"{prices.index[0].date()}..{prices.index[-1].date()} ({prices.shape[0]} rows)")
log(f"sleeves: {pd.Series(sleeves).value_counts().to_dict()}")

split = prices.index[int(len(prices) * base.is_frac)]
p_is = prices[prices.index < split]
log(f"IS < {split.date()} ({len(p_is)} rows) | OOS >= {split.date()} ({len(prices)-len(p_is)} rows)")


def sharpe_is(p):
    res = run_divtrend(p_is, p, sleeves)
    return compute_metrics(res["daily_ret"]).sharpe, res


# --- C2 baseline ------------------------------------------------------------
s0, _ = sharpe_is(base)
log(f"C2 baseline IS Sharpe = {s0:.2f}")

# --- C3 grid: <=2 passes, <=2 params each (<=20 configs) --------------------
trial_sharpes = []
best = (base, s0)
log("C3 pass 1: lookback_months x vol_lookback_days")
for lb in (6, 9, 12):
    for vl in (30, 60, 120):
        p = base.replace(lookback_months=lb, vol_lookback_days=vl)
        s, _ = sharpe_is(p)
        trial_sharpes.append(s)
        log(f"  lb={lb} vol_lb={vl}: IS Sharpe={s:.2f}")
        if s > best[1]:
            best = (p, s)
p1 = best[0]
log(f"pass1 best: lb={p1.lookback_months} vol_lb={p1.vol_lookback_days} (Sharpe={best[1]:.2f})")

log("C3 pass 2: skip_recent_month x rebal_band")
best = (p1, best[1])
for sk in (0, 1):
    for band in (0.0, 0.1, 0.3):
        p = p1.replace(skip_recent_month=sk, rebal_band=band)
        s, _ = sharpe_is(p)
        trial_sharpes.append(s)
        log(f"  skip={sk} band={band}: IS Sharpe={s:.2f}")
        if s > best[1]:
            best = (p, s)
p_lock = best[0]
n_trials = len(trial_sharpes)
trial_sr_std = float(np.std(trial_sharpes)) or 0.3
log(f"LOCKED: lb={p_lock.lookback_months} skip={p_lock.skip_recent_month} "
    f"vol_lb={p_lock.vol_lookback_days} band={p_lock.rebal_band} "
    f"| {n_trials} configs, trial-SR std={trial_sr_std:.2f}")

# --- single OOS look --------------------------------------------------------
p_oos = prices[prices.index >= split]
oos = run_divtrend(p_oos, p_lock, sleeves)
is_final = run_divtrend(p_is, p_lock, sleeves)
m_oos = compute_metrics(oos["daily_ret"], turnover_ann=oos["turnover_ann"])
m_is = compute_metrics(is_final["daily_ret"], turnover_ann=is_final["turnover_ann"])
log(f"OOS: Sharpe={m_oos.sharpe:.2f} CAGR={m_oos.cagr*100:.1f}% vol={m_oos.ann_vol*100:.1f}% "
    f"maxDD={m_oos.max_dd_pct:.1f}% Calmar={m_oos.calmar:.2f} turnover={m_oos.turnover_ann:.1f}x")

# --- PRIMARY gate: cost robustness 1.5x AND 2x -----------------------------
def oos_at(mult):
    r = run_divtrend(p_oos, p_lock, sleeves, cost_mult=mult)
    mm = compute_metrics(r["daily_ret"])
    return mm.sharpe, (1 + r["daily_ret"]).prod() - 1
s15, ret15 = oos_at(1.5)
s20, ret20 = oos_at(2.0)
primary = bool(s15 > 0 and ret15 > 0 and s20 > 0 and ret20 > 0)
log(f"PRIMARY cost gate: 1.5x(Sharpe={s15:.2f},ret={ret15*100:.1f}%) "
    f"2.0x(Sharpe={s20:.2f},ret={ret20*100:.1f}%) -> {'PASS' if primary else 'FAIL'}")

# --- breadth gate: leave-one-sleeve-out ------------------------------------
breadth_ok = True; loo = {}
for sl in sorted(set(sleeves.values())):
    keep = [t for t in prices.columns if sleeves[t] != sl]
    r = run_divtrend(p_oos[keep], p_lock, {t: sleeves[t] for t in keep})
    ss = compute_metrics(r["daily_ret"]).sharpe
    loo[sl] = ss
    if not (ss > 0):
        breadth_ok = False
log(f"breadth (leave-one-sleeve-out) OOS Sharpe: "
    + " ".join(f"-{k}={v:.2f}" for k, v in loo.items()) + f" -> {'PASS' if breadth_ok else 'FAIL'}")

# --- other gates + DSR ------------------------------------------------------
g_sharpe = m_oos.sharpe >= gates_cfg["oos_sharpe_min"]
g_stab = m_oos.sharpe >= gates_cfg["stability_ratio"] * m_is.sharpe if m_is.sharpe > 0 else False
g_dd = m_oos.max_dd_pct <= gates_cfg["max_dd_pct_max"]
dsr = deflated_sharpe(oos["daily_ret"], CUMULATIVE_PRIOR_TRIALS + n_trials, trial_sr_std)
g_dsr = np.isfinite(dsr) and dsr > 0.95
flags = [primary, g_sharpe, g_stab, g_dd, breadth_ok, g_dsr]
passed = all(flags)
log(f"GATES: cost={primary} sharpe={g_sharpe} stability={g_stab} maxDD={g_dd} "
    f"breadth={breadth_ok} DSR={g_dsr} (DSR={dsr:.3f}) -> {'PASS' if passed else 'FAIL'}")

status = "TESTED-PASS" if passed else "TESTED-FAIL"
lines = [
    f"Strategy: DIVTREND v1.0   Universe: {prices.shape[1]} ETFs   Vehicle: ETF",
    f"Window: {prices.index[0].date()}..{prices.index[-1].date()}  IS<{split.date()}  single OOS look",
    f"Costs: {base.default_cost_bps}bps/side (1.0x/1.5x/2.0x)  Turnover(ann)={m_oos.turnover_ann:.1f}x",
    "",
    f"IS : Sharpe={m_is.sharpe:.2f} CAGR={m_is.cagr*100:.1f}% vol={m_is.ann_vol*100:.1f}% "
    f"maxDD={m_is.max_dd_pct:.1f}% Calmar={m_is.calmar:.2f}",
    f"OOS: Sharpe={m_oos.sharpe:.2f} CAGR={m_oos.cagr*100:.1f}% vol={m_oos.ann_vol*100:.1f}% "
    f"maxDD={m_oos.max_dd_pct:.1f}% Calmar={m_oos.calmar:.2f} worstMo={m_oos.worst_month*100:.1f}%",
    f"Leave-one-sleeve-out OOS Sharpe: " + " ".join(f"-{k}={v:.2f}" for k, v in loo.items()),
    "",
    f"Gates: 1cost[{'x' if primary else ' '}] 2sharpe[{'x' if g_sharpe else ' '}] "
    f"3stability[{'x' if g_stab else ' '}] 4maxDD[{'x' if g_dd else ' '}] "
    f"5breadth[{'x' if breadth_ok else ' '}] 6DSR[{'x' if g_dsr else ' '}]  -> {'PASS' if passed else 'FAIL'}",
    f"DSR (vs {CUMULATIVE_PRIOR_TRIALS}+{n_trials} trials) = {dsr:.3f}   Trial budget used = {n_trials}/20",
    f"Status: {status}",
]
report = "\n".join(lines)
print("\n== PART F ==\n" + report)
Path("reports/DIVTREND_v1.0_run.txt").write_text(report + "\n")
log(f"status={status}; report saved. TOTAL {time.time()-T0:.0f}s")

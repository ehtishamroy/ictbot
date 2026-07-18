"""EURUSD-FVGC v1.0 — full validation per the PRE-REGISTERED protocol.

docs/spec/PREREG_EURUSD-FVGC_v1.0.md. IS 2015-2021, OOS 2022-2024 (single look).
Trial budget: 2 coarse grids of 9 cells = 18 configs (<= 24), sl_buffer from MAE.
COST ROBUSTNESS LEADS: OOS expectancy must be > 0 at BOTH 1.5x and 2.0x costs,
else reject as a cost artifact. Then six B5 gates (OOS trades floor = 100), then
perturbation robustness. Grid selection uses conservative bar fills; the locked
IS+OOS verdict uses 1-minute intrabar fills.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")

import numpy as np
import pandas as pd

from ictbot.backtest.costs import CostModel, apply_costs
from ictbot.config import load_config
from ictbot.engine.fills import IntrabarFillModel
from ictbot.engine.fvgc import FvgcParams, prepare_fvgc_features, run_fvgc
from ictbot.reporting.metrics import compute_metrics, evaluate_gates
from ictbot.reporting.report import part_f_report
from ictbot.validation.optimize import suggest_sl_buffer_points

T0 = time.time()
def log(m): print(f"[{time.time()-T0:7.1f}s] {m}", flush=True)

df1m = pd.read_pickle("/tmp/df1m.pkl")
df5 = pd.read_pickle("/tmp/df5.pkl")
df1h = pd.read_pickle("/tmp/df1h.pkl")  # unused but keeps cache warm/consistent
cfg = load_config("config/eurusd_fvgc_v1.0.yaml")
base = FvgcParams.from_config(cfg)
cm = CostModel(0.8, 7.0, 0.3)
OOS_MIN = 100

feats = prepare_fvgc_features(df5, base, default_spread_price=cm.spread_pips * base.pip)
IS_END = pd.Timestamp("2022-01-01", tz="UTC")
fis = feats[feats.index < IS_END]
foos = feats[feats.index >= IS_END]
IS_DAYS = (IS_END - feats.index[0]).days
log(f"features {len(feats):,} | IS {len(fis):,} | OOS {len(foos):,}")


def set_p(p, name, val):
    return p.replace(**{name: p.clamp_free(name, val)})


def is_metrics(p):
    tr = apply_costs(run_fvgc(fis, p), cm)      # bar fills, conservative
    return compute_metrics(tr, r_col="r_net", risk_pct=0.5, window_days=IS_DAYS), tr


m0, _ = is_metrics(base)
log(f"C2 baseline IS: n={m0.n} exp={m0.expectancy:.3f}R PF={m0.profit_factor:.2f} "
    f"maxDD={m0.max_dd_r:.1f}R t/mo={m0.trades_per_month:.1f}")

# --- C3 pass 1: ema_len x rr_target ----------------------------------------
rows = []
for el in (20, 50, 100):
    for rr in (1.5, 2.0, 3.0):
        p = set_p(set_p(base, "ema_len", el), "rr_target", rr)
        m, _ = is_metrics(p)
        rows.append(dict(ema_len=el, rr_target=rr, n=m.n, exp=m.expectancy,
                         pf=m.profit_factor, dd=m.max_dd_r, tpm=m.trades_per_month))
        log(f"  p1 ema={el} rr={rr}: n={m.n} exp={m.expectancy:.3f} pf={m.profit_factor:.2f} "
            f"dd={m.max_dd_r:.1f} t/mo={m.trades_per_month:.1f}")
g1 = pd.DataFrame(rows); g1.to_csv("reports/FVGC_is_grid_pass1.csv", index=False)
e1 = g1[g1.n >= OOS_MIN].sort_values(["exp", "dd"], ascending=[False, True])
c1 = (e1.iloc[0] if not e1.empty else g1.sort_values("exp", ascending=False).iloc[0])
p1 = set_p(set_p(base, "ema_len", int(c1.ema_len)), "rr_target", float(c1.rr_target))
log(f"pass1 -> ema_len={int(c1.ema_len)} rr_target={c1.rr_target} (exp={c1.exp:.3f} n={int(c1.n)})")

# --- C3 pass 2: fvg_min x disp_mult ----------------------------------------
rows = []
for fv in (0.2, 0.3, 0.5):
    for dm in (0.8, 1.0, 1.5):
        p = set_p(set_p(p1, "fvg_min", fv), "disp_mult", dm)
        m, _ = is_metrics(p)
        rows.append(dict(fvg_min=fv, disp_mult=dm, n=m.n, exp=m.expectancy,
                         pf=m.profit_factor, dd=m.max_dd_r, tpm=m.trades_per_month))
        log(f"  p2 fvg={fv} disp={dm}: n={m.n} exp={m.expectancy:.3f} pf={m.profit_factor:.2f} "
            f"dd={m.max_dd_r:.1f} t/mo={m.trades_per_month:.1f}")
g2 = pd.DataFrame(rows); g2.to_csv("reports/FVGC_is_grid_pass2.csv", index=False)
e2 = g2[g2.n >= OOS_MIN].sort_values(["exp", "dd"], ascending=[False, True])
c2 = (e2.iloc[0] if not e2.empty else g2.sort_values("exp", ascending=False).iloc[0])
p2 = set_p(set_p(p1, "fvg_min", float(c2.fvg_min)), "disp_mult", float(c2.disp_mult))
log(f"pass2 -> fvg_min={c2.fvg_min} disp_mult={c2.disp_mult} (exp={c2.exp:.3f} n={int(c2.n)})")

# --- sl_buffer from IS MAE p90 ---------------------------------------------
_, tr_p2 = is_metrics(p2)
slb = suggest_sl_buffer_points(tr_p2, p2, r_col="r_net")
p_lock = set_p(p2, "sl_buffer_points", slb)
mL, _ = is_metrics(p_lock)
log(f"sl_buffer<-MAE p90={slb}; IS lock (bar): n={mL.n} exp={mL.expectancy:.3f} "
    f"pf={mL.profit_factor:.2f} dd={mL.max_dd_r:.1f}")
log(f"LOCKED: ema={p_lock.ema_len} rr={p_lock.rr_target} fvg={p_lock.fvg_min} "
    f"disp={p_lock.disp_mult} slb={p_lock.sl_buffer_points} exp_b={p_lock.expiry_bars}")

# --- final INTRABAR run + single OOS look ----------------------------------
log("building 1-minute intrabar model...")
fm = IntrabarFillModel(df1m)
trades = apply_costs(run_fvgc(feats, p_lock, fill_model=fm), cm)
trades.to_pickle("/tmp/trades_fvgc.pkl")
et = pd.to_datetime(trades["entry_time"])
is_t = trades[et < IS_END]; oos_t = trades[et >= IS_END]
log(f"FINAL intrabar: total={len(trades)} IS={len(is_t)} OOS={len(oos_t)}")

# --- PRIMARY gate: cost robustness (1.5x AND 2.0x) -------------------------
oos_15 = apply_costs(run_fvgc(foos, p_lock, fill_model=fm), cm.scaled(1.5))
oos_20 = apply_costs(run_fvgc(foos, p_lock, fill_model=fm), cm.scaled(2.0))
e15 = compute_metrics(oos_15, r_col="r_net").expectancy
e20 = compute_metrics(oos_20, r_col="r_net").expectancy
oos_e = compute_metrics(oos_t, r_col="r_net").expectancy
primary = bool(np.isfinite(e15) and np.isfinite(e20) and e15 > 0 and e20 > 0)
log(f"PRIMARY cost-robustness gate: OOS exp 1.0x={oos_e:.3f} 1.5x={e15:.3f} "
    f"2.0x={e20:.3f} -> {'PASS' if primary else 'FAIL (cost artifact)'}")

gates = evaluate_gates(is_t, oos_t, risk_pct=0.5, r_col="r_net", oos_trades_min=OOS_MIN)
log(f"Six B5 gates (OOS floor {OOS_MIN}): {gates.as_flags()} -> "
    f"{'PASS' if gates.passed else 'FAIL'}")
log(f"  OOS exp={gates.oos.expectancy:.3f} PF={gates.oos.profit_factor:.2f} "
    f"maxDD={gates.oos.max_dd_r:.1f} n={gates.oos.n} conc={gates.concentration:.2f} "
    f"| IS PF={gates.is_.profit_factor:.2f}")

# --- perturbation robustness (bar fills, OOS) ------------------------------
perturb_ok = True; pert = {}
if primary and gates.passed:
    for fld in p_lock.ranges:
        for pct in (-0.2, 0.2):
            pp = set_p(p_lock, fld, getattr(p_lock, fld) * (1 + pct))
            e = compute_metrics(apply_costs(run_fvgc(foos, pp), cm), r_col="r_net").expectancy
            pert[(fld, pct)] = e
            if not (np.isfinite(e) and e >= 0):
                perturb_ok = False
    log(f"perturbation ±20% OOS: {'PASS' if perturb_ok else 'FAIL'}  "
        + " ".join(f"{k[0]}{k[1]:+.0%}={v:.2f}" for k, v in pert.items()))

status = ("TESTED-FAIL" if not (primary and gates.passed)
          else "TESTED-PASS" if perturb_ok else "GATES-PASS / ROBUSTNESS-FAIL")

report = part_f_report(
    version="v1.0", window="IS 2015-2021 / OOS 2022-2024 (EURUSD, 07-16 UTC)",
    data_desc="1m HistData (fixed GMT-5->UTC); news filter DISABLED (no calendar)",
    mt5_mode="n/a (Python, 1-minute intrabar fills)",
    costs_desc=f"spread=0.8pip commission=$7/lot slippage=0.3pip "
               f"(1.0x; PRIMARY GATE 1.5x exp={e15:.3f}, 2.0x exp={e20:.3f})",
    is_trades=is_t, oos_trades=oos_t, gates=gates, r_col="r_net", risk_pct=0.5,
    robustness={"perturb": perturb_ok, "cost_stress": primary,
                "session_shift": None, "monthly": True},
    status=status, strategy_name="EURUSD-FVGC")
print("\n== PART F ==\n" + report)
Path("reports/EURUSD-FVGC_v1.0_10y_run.txt").write_text(
    report + f"\n\nLOCKED (IS 2015-2021 only): ema_len={p_lock.ema_len} "
    f"rr_target={p_lock.rr_target} fvg_min={p_lock.fvg_min} disp_mult={p_lock.disp_mult} "
    f"sl_buffer_points={p_lock.sl_buffer_points} expiry_bars={p_lock.expiry_bars}\n"
    f"PRIMARY cost gate: 1.5x exp={e15:.3f}, 2.0x exp={e20:.3f} -> "
    f"{'PASS' if primary else 'FAIL'}\n")
log(f"status={status}; report saved. TOTAL {time.time()-T0:.0f}s")

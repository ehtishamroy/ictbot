"""NYAM-ILS-FVG v1.0 — full 10-year validation (EURUSD 2015-2024, HistData 1m).

Protocol (spec Part C, scrupulous about what is clean):
  * IS = 2015-01-01 .. 2021-12-31 (7 y) — genuinely fresh, never seen before now.
  * OOS = 2022-01-01 .. 2024-12-31 (3 y) — single look, evaluated ONCE at locked
    params. HONEST CAVEAT: this window informed the ILS *design* (v1 failure
    diagnosis) and a prior param search, so it is structurally contaminated as an
    OOS. It is still the best available held-out test for parameters selected on
    2015-2021, and mutual cross-window generalization is reported plainly.

  A. features built once on the full 10 y.
  B. C2 baseline on IS at v1.0 defaults.
  C. C3 pass 1 (frequency levers mss_window x fvg_min x expiry_bars) then pass 2
     (disp_mult x sweep_close_n), IS ONLY, coarse grids, select by expectancy
     tie-broken by maxDD, n>=40 guard (7 y). Selection uses the CONSERVATIVE
     bar-fill model (a pessimistic lower bound — decisions made under it are
     conservative).
  D. sl_buffer from p90 MAE of winning IS trades (C3 step 7), re-verify IS.
  E. LOCK. Final IS + single OOS look use the ACCURATE 1-minute intrabar model.
     Six B5 gates on OOS; B6 robustness (bar-fill, conservative). Part F report.

Costs: full B2 (0.8 pip spread, $7/lot, 0.3 pip slippage), 1.0x and 1.5x.
News filter: no calendar source -> empty event list (documented per D5).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")

import numpy as np
import pandas as pd

from ictbot.backtest.costs import CostModel, apply_costs
from ictbot.config import load_config
from ictbot.engine.features import prepare_features
from ictbot.engine.fills import IntrabarFillModel
from ictbot.engine.params import EngineParams
from ictbot.engine.state_machine import run
from ictbot.reporting.metrics import compute_metrics, evaluate_gates
from ictbot.reporting.report import part_f_report
from ictbot.validation.optimize import suggest_sl_buffer_points
from ictbot.validation.perturb import set_param
from ictbot.validation.preflight import preflight
from ictbot.validation.robustness import run_robustness

T0 = time.time()
def log(m): print(f"[{time.time()-T0:7.1f}s] {m}", flush=True)

df1m = pd.read_pickle("/tmp/df1m.pkl")
df5 = pd.read_pickle("/tmp/df5.pkl")
df1h = pd.read_pickle("/tmp/df1h.pkl")
cfg = load_config("config/nyam_ils_fvg_v1.0.yaml")
base = EngineParams.from_config(cfg)
cm = CostModel(0.8, 7.0, 0.3)

pf = preflight(df5, df1h, base)
log(f"C1 pre-flight: {'PASS' if pf.passed else 'FAIL'} {pf.checks}")
if not pf.passed:
    sys.exit(1)

feats = prepare_features(df5, df1h, base, default_spread_price=cm.spread_pips * base.pip)
log(f"features built: {len(feats):,} 5m bars")
IS_END = pd.Timestamp("2022-01-01", tz="UTC")
fis = feats[feats.index < IS_END]
foos = feats[feats.index >= IS_END]
IS_DAYS = (IS_END - feats.index[0]).days
log(f"IS 2015-2021: {len(fis):,} bars | OOS 2022-2024: {len(foos):,} bars")


def is_metrics(p):
    tr = apply_costs(run(fis, p, news=[]), cm)          # bar fills (conservative)
    return compute_metrics(tr, r_col="r_net", risk_pct=0.5, window_days=IS_DAYS), tr


# --- B. baseline ------------------------------------------------------------
m0, _ = is_metrics(base)
log(f"C2 baseline IS: n={m0.n} exp={m0.expectancy:.3f}R PF={m0.profit_factor:.2f} "
    f"maxDD={m0.max_dd_r:.1f}R t/mo={m0.trades_per_month:.2f}")

MIN_N = 40

# --- C. pass 1: frequency levers -------------------------------------------
rows = []
for mw in (8, 14, 20):
    for fv in (0.3, 0.5, 0.8):
        for ex in (8, 15, 24):
            p = set_param(set_param(set_param(base, "mss_window", mw), "fvg_min", fv),
                          "expiry_bars", ex)
            m, _ = is_metrics(p)
            rows.append(dict(mss_window=mw, fvg_min=fv, expiry_bars=ex, n=m.n,
                             exp=m.expectancy, pf=m.profit_factor, dd=m.max_dd_r,
                             tpm=m.trades_per_month))
            log(f"  p1 mss={mw} fvg={fv} exp_b={ex}: n={m.n} exp={m.expectancy:.3f} "
                f"pf={m.profit_factor:.2f} dd={m.max_dd_r:.1f} t/mo={m.trades_per_month:.2f}")
g1 = pd.DataFrame(rows)
g1.to_csv("reports/ILS_10y_is_grid_pass1.csv", index=False)
e1 = g1[g1.n >= MIN_N].sort_values(["exp", "dd"], ascending=[False, True])
c1 = (e1.iloc[0] if not e1.empty else
      g1.sort_values("exp", ascending=False).iloc[0])
log(f"pass1 select: mss={int(c1.mss_window)} fvg={c1.fvg_min} exp_b={int(c1.expiry_bars)} "
    f"(exp={c1.exp:.3f} n={int(c1.n)})")
p1 = set_param(set_param(set_param(base, "mss_window", int(c1.mss_window)),
                         "fvg_min", float(c1.fvg_min)), "expiry_bars", int(c1.expiry_bars))

# --- C. pass 2: displacement x sweep window --------------------------------
rows = []
for dm in (1.0, 1.25, 1.5):
    for sc in (1, 3, 5):
        p = set_param(set_param(p1, "disp_mult", dm), "sweep_close_n", sc)
        m, _ = is_metrics(p)
        rows.append(dict(disp_mult=dm, sweep_close_n=sc, n=m.n, exp=m.expectancy,
                         pf=m.profit_factor, dd=m.max_dd_r, tpm=m.trades_per_month))
        log(f"  p2 disp={dm} scn={sc}: n={m.n} exp={m.expectancy:.3f} "
            f"pf={m.profit_factor:.2f} dd={m.max_dd_r:.1f} t/mo={m.trades_per_month:.2f}")
g2 = pd.DataFrame(rows)
g2.to_csv("reports/ILS_10y_is_grid_pass2.csv", index=False)
e2 = g2[g2.n >= MIN_N].sort_values(["exp", "dd"], ascending=[False, True])
c2 = (e2.iloc[0] if not e2.empty else g2.sort_values("exp", ascending=False).iloc[0])
log(f"pass2 select: disp={c2.disp_mult} scn={int(c2.sweep_close_n)} "
    f"(exp={c2.exp:.3f} n={int(c2.n)})")
p2 = set_param(set_param(p1, "disp_mult", float(c2.disp_mult)),
               "sweep_close_n", int(c2.sweep_close_n))

# --- D. sl_buffer from MAE p90 (never gridded) -----------------------------
_, tr_p2 = is_metrics(p2)
slb = suggest_sl_buffer_points(tr_p2, p2, r_col="r_net")
p_lock = set_param(p2, "sl_buffer_points", slb)
mL, _ = is_metrics(p_lock)
log(f"sl_buffer<-MAE p90 = {slb} pts; IS re-verify (bar fills): n={mL.n} "
    f"exp={mL.expectancy:.3f} pf={mL.profit_factor:.2f} dd={mL.max_dd_r:.1f}")
log(f"LOCKED: mss={p_lock.mss_window} fvg={p_lock.fvg_min} exp_b={p_lock.expiry_bars} "
    f"disp={p_lock.disp_mult} scn={p_lock.sweep_close_n} slb={p_lock.sl_buffer_points}")

# --- E. final run with INTRABAR fills; single OOS look ----------------------
log("building 1-minute intrabar fill model (full 10y)...")
fm = IntrabarFillModel(df1m)
trades = apply_costs(run(feats, p_lock, news=[], fill_model=fm), cm)
trades.to_pickle("/tmp/trades_ils_10y.pkl")
et = pd.to_datetime(trades["entry_time"])
is_t = trades[et < IS_END]
oos_t = trades[et >= IS_END]
log(f"FINAL intrabar run: total={len(trades)} IS={len(is_t)} OOS={len(oos_t)}")

gates = evaluate_gates(is_t, oos_t, risk_pct=0.5, r_col="r_net")
log(f"OOS GATES (single look): {gates.as_flags()} -> {'PASS' if gates.passed else 'FAIL'}")
log(f"  OOS exp={gates.oos.expectancy:.3f} PF={gates.oos.profit_factor:.2f} "
    f"maxDD={gates.oos.max_dd_r:.1f} n={gates.oos.n} conc={gates.concentration:.2f} "
    f"| IS PF={gates.is_.profit_factor:.2f}")

# --- cost stress at 1.5x on OOS --------------------------------------------
oos_15 = apply_costs(run(foos, p_lock, news=[], fill_model=fm), cm.scaled(1.5))
m15 = compute_metrics(oos_15, r_col="r_net", risk_pct=0.5)
log(f"OOS @1.5x costs: exp={m15.expectancy:.3f} PF={m15.profit_factor:.2f} n={m15.n}")

# --- B6 robustness (conservative bar fills on OOS) --------------------------
robustness = None
if gates.passed:
    def rob_fn(p, cost):
        if (p.kz_start, p.kz_end) != (base.kz_start, base.kz_end):
            f = prepare_features(df5, df1h, p, default_spread_price=cost.spread_pips*p.pip)
            fo = f[f.index >= IS_END]
        else:
            fo = foos
        tr = apply_costs(run(fo, p, news=[]), cost)
        return tr
    robustness = run_robustness(p_lock, cm, rob_fn, r_col="r_net")
    log(f"B6 robustness (bar-fill, OOS): perturb={robustness.perturb_ok} "
        f"cost={robustness.cost_ok} session={robustness.session_ok} -> "
        f"{'PASS' if robustness.passed else 'FAIL'}")

status = ("TESTED-FAIL" if not gates.passed
          else "TESTED-PASS" if (robustness and robustness.passed)
          else "GATES-PASS / ROBUSTNESS-FAIL")

report = part_f_report(
    version="v1.0", window="IS 2015-2021 / OOS 2022-2024 (EURUSD)",
    data_desc="1m HistData (fixed GMT-5->UTC); news filter DISABLED (no calendar)",
    mt5_mode="n/a (Python, 1-minute intrabar fills)",
    costs_desc=f"spread=0.8pip commission=$7/lot slippage=0.3pip (1.0x; 1.5x OOS exp={m15.expectancy:.3f})",
    is_trades=is_t, oos_trades=oos_t, gates=gates, r_col="r_net", risk_pct=0.5,
    robustness=(robustness.marks() if robustness else None), status=status,
    strategy_name="NYAM-ILS-FVG")
print("\n== PART F ==\n" + report)
Path("reports/NYAM-ILS-FVG_v1.0_10y_run.txt").write_text(
    report + f"\n\nLOCKED PARAMS (selected on IS 2015-2021 only): "
    f"mss_window={p_lock.mss_window} fvg_min={p_lock.fvg_min} "
    f"expiry_bars={p_lock.expiry_bars} disp_mult={p_lock.disp_mult} "
    f"sweep_close_n={p_lock.sweep_close_n} sl_buffer_points={p_lock.sl_buffer_points}\n"
    f"IS (intrabar): n={gates.is_.n} exp={compute_metrics(is_t,r_col='r_net').expectancy:.3f} "
    f"PF={gates.is_.profit_factor:.2f}\nOOS @1.5x costs: exp={m15.expectancy:.3f} PF={m15.profit_factor:.2f}\n")
log(f"status={status}; report saved.")
log(f"TOTAL {time.time()-T0:.0f}s")

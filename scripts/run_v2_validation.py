"""v2.0 IS-ONLY tuning pass on EURUSD (HistData 1m), per Part C.

IMPORTANT: by default this script NEVER touches the OOS tail (last 30%) — the
single OOS look (C4) is reserved until the full 2015-2024 sample is available,
so the tail stays uncontaminated. Pass --oos explicitly to consume the look.

Stages, all bounded by the spec's anti-overfit rules:
  A. features built once; chronological 70/30 IS/OOS boundary by date
  B. C2 baseline: IS run at v2.0 defaults
  C. C3 one bounded IS grid on the FREQUENCY levers (C2 step 5 rule: when
     trade frequency is below target, the only levers are mss_window, fvg_min,
     expiry_bars) — 3 coarse values each, selected by expectancy tie-broken by
     maxDD, min-n guard
  D. C3 step 7: sl_buffer from p90 MAE of winning IS trades, re-verify IS once
  E. (--oos only) LOCK -> full run -> single OOS look -> six gates ->
     robustness if passed -> Part F report saved to reports/

News filter: no calendar source available in this environment -> runs with an
empty event list (documented in the report per D5).
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
from ictbot.reporting.metrics import compute_metrics, evaluate_gates, monthly_net_r
from ictbot.reporting.report import part_f_report
from ictbot.validation.optimize import suggest_sl_buffer_points
from ictbot.validation.perturb import set_param
from ictbot.validation.preflight import preflight
from ictbot.validation.robustness import run_robustness

T0 = time.time()
def log(msg):
    print(f"[{time.time()-T0:7.1f}s] {msg}", flush=True)

CONFIG = "config/nyam_sweep_fvg_v2.0.yaml"
for a_i, a in enumerate(sys.argv):
    if a == "--config" and a_i + 1 < len(sys.argv):
        CONFIG = sys.argv[a_i + 1]

df1m = pd.read_pickle("/tmp/df1m.pkl")
df5 = pd.read_pickle("/tmp/df5.pkl")
df1h = pd.read_pickle("/tmp/df1h.pkl")
cfg = load_config(CONFIG)
params = EngineParams.from_config(cfg)
TAG = f"{cfg.name}_v{cfg.version}"
log_prefix = TAG
cm = CostModel(spread_pips=0.8, commission_per_lot_roundturn=7.0, slippage_pips=0.3)

pf = preflight(df5, df1h, params)
log(f"C1 pre-flight: {'PASS' if pf.passed else 'FAIL'} {pf.checks}")
if not pf.passed:
    sys.exit(1)

feats_full = prepare_features(df5, df1h, params,
                              default_spread_price=cm.spread_pips * params.pip)
fm = IntrabarFillModel(df1m)
log("features + intrabar model built")

start, end = df5.index[0], df5.index[-1]
boundary = start + (end - start) * 0.70
feats_is = feats_full[feats_full.index < boundary]
log(f"window {start.date()}..{end.date()}, IS/OOS boundary {boundary.date()}")


def run_is(p: EngineParams) -> pd.DataFrame:
    tr = run(feats_is, p, news=[], fill_model=fm)
    return apply_costs(tr, cm)


# --- B. C2 baseline ---------------------------------------------------------
base_is = run_is(params)
m = compute_metrics(base_is, r_col="r_net", risk_pct=params.risk_pct)
log(f"C2 baseline IS: n={m.n} exp={m.expectancy:.3f}R PF={m.profit_factor:.2f} "
    f"maxDD={m.max_dd_r:.1f}R trades/mo={m.trades_per_month:.1f}")

# --- C. C3 bounded grid: FREQUENCY levers (C2 step 5) -----------------------
GRID = {"mss_window": [8, 14, 20],
        "fvg_min": [0.3, 0.5, 0.8],
        "expiry_bars": [8, 15, 24]}
MIN_N = 20     # IS is ~25 months; below this a cell's stats are noise
rows = []
for mw in GRID["mss_window"]:
    for fv in GRID["fvg_min"]:
        for ex in GRID["expiry_bars"]:
            p = set_param(set_param(set_param(params, "mss_window", mw),
                                    "fvg_min", fv), "expiry_bars", ex)
            mm = compute_metrics(run_is(p), r_col="r_net", risk_pct=params.risk_pct)
            rows.append(dict(mss_window=mw, fvg_min=fv, expiry_bars=ex, n=mm.n,
                             exp=mm.expectancy, pf=mm.profit_factor, dd=mm.max_dd_r,
                             tpm=mm.trades_per_month))
            log(f"  grid mss={mw} fvg={fv} exp_b={ex}: n={mm.n} "
                f"exp={mm.expectancy:.3f} pf={mm.profit_factor:.2f} "
                f"dd={mm.max_dd_r:.1f} t/mo={mm.trades_per_month:.2f}")
grid_df = pd.DataFrame(rows)
grid_df.to_csv(f"reports/{TAG}_is_grid.csv", index=False)
eligible = grid_df[grid_df["n"] >= MIN_N].sort_values(["exp", "dd"],
                                                      ascending=[False, True])
if eligible.empty:
    log(f"NO grid cell reached n>={MIN_N} on IS — selection falls back to defaults")
    chosen = dict(mss_window=params.mss_window, fvg_min=params.fvg_min,
                  expiry_bars=params.expiry_bars)
else:
    chosen = eligible.iloc[0][["mss_window", "fvg_min", "expiry_bars"]].to_dict()
log(f"C3 selected: {chosen}")
p_sel = set_param(set_param(set_param(params, "mss_window", int(chosen["mss_window"])),
                            "fvg_min", chosen["fvg_min"]),
                  "expiry_bars", int(chosen["expiry_bars"]))

# --- D. sl_buffer from MAE p90 of IS winners (never gridded) ----------------
is_sel = run_is(p_sel)
slb = suggest_sl_buffer_points(is_sel, p_sel, r_col="r_net")
p_lock = set_param(p_sel, "sl_buffer_points", slb)
is_final = run_is(p_lock)
mf = compute_metrics(is_final, r_col="r_net", risk_pct=params.risk_pct)
log(f"sl_buffer set from MAE p90 -> {slb} pts; IS re-verify: n={mf.n} "
    f"exp={mf.expectancy:.3f} pf={mf.profit_factor:.2f} dd={mf.max_dd_r:.1f}")
log(f"LOCKED params: disp_mult={p_lock.disp_mult} fvg_min={p_lock.fvg_min} "
    f"expiry_bars={p_lock.expiry_bars} sl_buffer={p_lock.sl_buffer_points} "
    f"dol_reach={p_lock.dol_reach} (defaults elsewhere)")

# --- E. LOCK -> full run -> single OOS look -> gates -> robustness ----------
if "--oos" not in sys.argv:
    log("OOS look NOT consumed (pass --oos to run it). IS tuning pass complete.")
    sys.exit(0)

def run_full(p: EngineParams, cost: CostModel) -> pd.DataFrame:
    if (p.kz_start, p.kz_end) != (params.kz_start, params.kz_end):
        f = prepare_features(df5, df1h, p,
                             default_spread_price=cost.spread_pips * p.pip)
    else:
        f = feats_full
    tr = run(f, p, news=[], fill_model=fm)
    return apply_costs(tr, cost)

trades_full = run_full(p_lock, cm)
trades_full.to_pickle("/tmp/trades_v2.pkl")
et = pd.to_datetime(trades_full["entry_time"])
is_t = trades_full[et < boundary]
oos_t = trades_full[et >= boundary]
log(f"FULL run: total={len(trades_full)}  IS n={len(is_t)}  OOS n={len(oos_t)}")

gates = evaluate_gates(is_t, oos_t, risk_pct=params.risk_pct, r_col="r_net")
log(f"OOS gates (single look): {gates.as_flags()} -> "
    f"{'PASS' if gates.passed else 'FAIL'}")
log(f"  OOS: exp={gates.oos.expectancy:.3f} PF={gates.oos.profit_factor:.2f} "
    f"maxDD={gates.oos.max_dd_r:.1f} n={gates.oos.n} conc={gates.concentration:.2f}")

robustness = None
if gates.passed:
    def rob_fn(p, cost):
        tr = run_full(p, cost)
        e = pd.to_datetime(tr["entry_time"])
        return tr[e >= boundary]
    robustness = run_robustness(p_lock, cm, rob_fn, r_col="r_net")
    log(f"B6 robustness: perturb={robustness.perturb_ok} "
        f"cost1.5x={robustness.cost_ok} session={robustness.session_ok} "
        f"-> {'PASS' if robustness.passed else 'FAIL'}")

status = ("TESTED-FAIL" if not gates.passed
          else "TESTED-PASS" if (robustness and robustness.passed)
          else "GATES-PASS / ROBUSTNESS-FAIL")

report = part_f_report(
    version=f"v{cfg.version}",
    window=f"{start.date()}..{end.date()}",
    data_desc=("1m, HistData.com (fixed GMT-5 source -> true UTC); "
               "news filter DISABLED (no calendar source)"),
    mt5_mode="n/a (Python harness, 1-minute intrabar fills)",
    costs_desc=(f"spread={cm.spread_pips}pip commission=${cm.commission_per_lot_roundturn}"
                f"/lot slippage={cm.slippage_pips}pip (1.0x)"),
    is_trades=is_t, oos_trades=oos_t, gates=gates, r_col="r_net",
    risk_pct=params.risk_pct,
    robustness=(robustness.marks() if robustness else None), status=status,
)
print("\n== PART F ==\n" + report)
Path(f"reports/{TAG}_run1.txt").write_text(
    report + f"\n\nLocked params: disp_mult={p_lock.disp_mult} "
    f"fvg_min={p_lock.fvg_min} expiry_bars={p_lock.expiry_bars} "
    f"sl_buffer={p_lock.sl_buffer_points} dol_reach={p_lock.dol_reach}\n")
log(f"report saved: reports/{TAG}_run1.txt")

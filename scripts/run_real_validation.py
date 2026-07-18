"""One-off runner for the real EURUSD 2022-2024 validation (HistData 1m).

Not part of the CLI's normal path (that reads CSVs fresh each time); this reuses
the already-loaded/cached frames for speed during the initial real run and writes
the Part F report to reports/.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")

import pandas as pd

from ictbot.backtest.costs import CostModel
from ictbot.backtest.harness import backtest, split_is_oos
from ictbot.config import load_config
from ictbot.engine.params import EngineParams
from ictbot.reporting.metrics import evaluate_gates
from ictbot.reporting.report import part_f_report
from ictbot.validation.preflight import preflight
from ictbot.validation.robustness import run_robustness

t0 = time.time()
df1m = pd.read_pickle("/tmp/df1m.pkl")
df5 = pd.read_pickle("/tmp/df5.pkl")
df1h = pd.read_pickle("/tmp/df1h.pkl")
print(f"loaded cached frames in {time.time()-t0:.1f}s", flush=True)

cfg = load_config("config/nyam_sweep_fvg_v1.0.yaml")
params = EngineParams.from_config(cfg)

t1 = time.time()
pf = preflight(df5, df1h, params)
print(f"\n== C1 PRE-FLIGHT ({time.time()-t1:.1f}s) ==", flush=True)
for name, ok in pf.checks.items():
    print(f"  [{'x' if ok else ' '}] {name}: {pf.notes.get(name, '')}")
if not pf.passed:
    print("PRE-FLIGHT FAILED — stopping.")
    sys.exit(1)

cm = CostModel(spread_pips=0.8, commission_per_lot_roundturn=7.0, slippage_pips=0.3)

t2 = time.time()
trades = backtest(df5, df1h, params, news=[], cost_model=cm, df1m=df1m)
print(f"\nbacktest done in {time.time()-t2:.1f}s, trades={len(trades)}", flush=True)
trades.to_pickle("/tmp/trades_v1.pkl")

is_t, oos_t, boundary = split_is_oos(trades, df5.index[0], df5.index[-1])
print(f"IS/OOS boundary: {boundary}  IS n={len(is_t)}  OOS n={len(oos_t)}", flush=True)

gates = evaluate_gates(is_t, oos_t, risk_pct=params.risk_pct, r_col="r_net")
print(f"\nGates: {gates.as_flags()}  passed={gates.passed}", flush=True)

robustness = None
if gates.passed:
    t3 = time.time()
    def run_fn(p, c):
        tr = backtest(df5, df1h, p, news=[], cost_model=c, df1m=df1m)
        _, o, _ = split_is_oos(tr, df5.index[0], df5.index[-1])
        return o
    robustness = run_robustness(params, cm, run_fn, r_col="r_net")
    print(f"robustness done in {time.time()-t3:.1f}s, passed={robustness.passed}", flush=True)

status = ("TESTED-FAIL" if not gates.passed
          else "TESTED-PASS" if (robustness and robustness.passed)
          else "GATES-PASS / ROBUSTNESS-FAIL")

report = part_f_report(
    version="v1.0",
    window=f"{df5.index[0].date()}..{df5.index[-1].date()}",
    data_desc="1m, HistData.com (EURUSD, fixed GMT-5 source, converted to true UTC)",
    mt5_mode="n/a (Python harness, 1-minute intrabar fills)",
    costs_desc=(f"spread={cm.spread_pips}pip commission=${cm.commission_per_lot_roundturn}/lot "
               f"slippage={cm.slippage_pips}pip (1.0x)"),
    is_trades=is_t, oos_trades=oos_t, gates=gates, r_col="r_net",
    risk_pct=params.risk_pct,
    robustness=(robustness.marks() if robustness else None),
    status=status,
)
print("\n== PART F ==")
print(report)

Path("reports").mkdir(exist_ok=True)
out = Path("reports/v1.0_2022-2024_run1.txt")
out.write_text(report)
print(f"\nsaved: {out}")
print(f"\ntotal wall time: {time.time()-t0:.1f}s")

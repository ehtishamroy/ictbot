# ictbot — NYAM-SWEEP-FVG

Mechanical ICT trading system (NY AM liquidity sweep → MSS → FVG tap entry) on EURUSD.
Python research harness first, MQL5 EA for forward/live.

> **Status: UNTESTED.** No win rate, return, or edge is claimed. Performance numbers
> may only come from our own backtests run exactly per the validation protocol.

## What this is
An implementation of the [NYAM-SWEEP-FVG v1.0 spec](docs/spec/NYAM-SWEEP-FVG_v1.0_spec.md),
built under the spec's own anti-self-deception discipline (real-tick data, mandatory
cost model, single OOS look, bounded tuning, archive-on-fail).

## Roadmap & progress
See **[PROJECT_PLAN.md](PROJECT_PLAN.md)** — the project is split into phases 0–10 with
checklists so no validation step gets skipped. That file is the source of truth for status.

## Layout
```
config/     parameter sets (A6 table + fixed constants)
data/       raw / processed price data, news calendars  (gitignored, not committed)
docs/spec/  the frozen strategy specification
src/ictbot/ data · indicators · detectors · engine · backtest · reporting
tests/      unit tests (detectors, time layer, fills)
mql5/       MetaTrader 5 EA (Phase 8)
pine/       TradingView visual-validation script (Phase 9)
reports/    Part F run reports
```

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Non-negotiables (from the spec)
- Backtests use tick / 1-minute data only ("Every tick based on real ticks" in MT5).
- Every result includes the cost model; re-run finals at 1.5× costs.
- OOS window looked at once per version; all tuning on in-sample only.
- No look-ahead: swings confirm k bars late; limit fills need trade-through by ≥1 tick.

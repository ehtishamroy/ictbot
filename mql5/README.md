# NYAM-SWEEP-FVG — MetaTrader 5 EA

`NYAM_SWEEP_FVG.mq5` is the MQL5 port of the tested Python engine — the forward/live
vehicle. Function names match the D1 DEF-ID map so behaviour lines up with the
research harness. **Status: UNTESTED.** No edge is claimed.

> ⚠️ This file has **not been compiled** in this environment (no MetaEditor here).
> Treat it as a faithful transcription of the Python logic that must be compiled,
> pre-flighted, and cross-checked before any use.

## Install & compile
1. Copy `NYAM_SWEEP_FVG.mq5` into `MQL5/Experts/` under your MT5 data folder
   (MetaTrader → File → Open Data Folder).
2. Open it in MetaEditor and press **Compile** (F7). Fix any broker-specific
   symbol assumptions flagged below.
3. Attach to a **EURUSD M5** chart. The EA is new-M5-bar driven.

## Pre-flight (do this first — spec C1 / D6)
1. **Verify `ServerToNYOffsetH`.** On init the EA prints the NY time it computes for
   the current server time. Confirm a known session open (e.g. that 13:30 UTC in
   winter shows as 08:30 NY). Most brokers that anchor to US DST need `7`, but this
   MUST be checked per broker — a wrong offset makes every killzone and every
   PDH/PDL wrong. **Never optimise this value.**
2. **Backtest ONLY in "Every tick based on real ticks" mode.** Reject any result
   from "Open prices only" or "1 minute OHLC" — the sweep/FVG/SL-vs-TP logic lives
   inside M5 candles and needs real ticks.
3. Confirm on the first runs: swings act only after `k` confirmed bars (no
   repainting), PDH/PDL use the 17:00→17:00 NY day, daily counters reset at 17:00 NY.

## Cross-check against Python (the point of Phase 8)
Run the same window in both:
- Python: `python -m ictbot.validation.cli --csv <same_data>.csv`
- MT5: Strategy Tester, real ticks, same dates, same inputs.

Trade count, entries, and expectancy should agree within the cost model. Material
divergence means a port bug — fix before trusting the EA.

## Known differences vs the Python engine (reconcile during cross-check)
- **DST handling.** Python uses true `America/New_York` (`zoneinfo`); the EA uses the
  fixed `ServerToNYOffsetH` per the spec's MT5 approach (D2/DEF-TIME-01). These agree
  only if the broker server tracks US DST. On DST-transition weeks expect small
  timing differences — those weeks are tradeable but journal-tagged.
- **Intrabar fills.** Python's `IntrabarFillModel` resolves SL-vs-TP with 1-minute
  bars; the EA resolves them live on the real tick stream in the tester. Same intent,
  different mechanism — real-tick mode is required for them to match.
- **R accounting.** The EA tracks day-R from closed-deal `DEAL_PROFIT` for the −2R
  daily lock; authoritative R metrics come from the Python harness / Part F report.
- **News filter.** Live/tester uses `CalendarValueHistory` (USD/EUR high-impact,
  ±`NewsBlockMin`). Python backtests join a ForexFactory CSV — state the source in
  every report.

## Inputs
All A6 free parameters and fixed constants are exposed as inputs, grouped to match
the spec. Keep free parameters inside their A6 test ranges; keep the fixed constants
fixed. Go-live risk ladder is in Part E of the spec (start 0.25%, scale to 0.5%).

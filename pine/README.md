# NYAM-SWEEP-FVG — Pine Script (visual validation only)

`NYAM_SWEEP_FVG_visual.pine` is a TradingView **indicator** for eyeballing where the
mechanical signals land on a EURUSD M5 chart. Per spec D4 it is deliberately **not a
strategy**: Pine's lower-timeframe fill assumptions are optimistic, so **all
performance numbers come from the Python harness / MT5 real-ticks tester — never from
Pine.**

## Use
1. TradingView → Pine Editor → paste the file → **Add to chart** (EURUSD, 5m).
2. It plots:
   - **Killzone** shading — NY AM 08:30–11:00 in `America/New_York` (DST-correct via the session string).
   - **PDH / PDL** — previous **17:00→17:00 NY** trading-day high/low (not the exchange day).
   - **Confirmed swings** — `ta.pivothigh/low(k, k)`, drawn `k` bars back so they confirm late (matches DEF-SWING-01, no repaint).
   - **Sweeps** — a close back across PDL/PDH within `sweep_close_n` bars of a wick beyond it.
   - **Displacement / MSS** — a displaced close beyond the last confirmed swing.
   - **FVG zones** — 3-candle gaps inside the ATR size band, with the CE (entry) dotted line.

## What to check
- Killzone shading aligns with 08:30–11:00 NY across DST changes.
- PDH/PDL roll at 17:00 NY, not midnight.
- Swing markers appear `k` bars after the pivot (never on the live bar).
- Sweep/MSS/FVG marks land where the Python engine would fire — if they don't, that's
  a discrepancy to investigate in the port, not a reason to trust Pine's version.

## Caveats
- Sweep and MSS here are simplified for on-chart clarity (single-candle displacement,
  last-confirmed-swing break). The authoritative logic is the Python engine.
- No orders, no fills, no P&L — by design.

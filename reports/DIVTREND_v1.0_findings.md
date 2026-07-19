# DIVTREND v1.0 — findings (EURUSD project's first TESTED-PASS)

**Status: TESTED-PASS.** Diversified time-series momentum across 19 liquid ETFs,
2007-2026, passed all six pre-registered gates on a single OOS look AND survived a
hard post-pass robustness deep-dive. This is the first strategy in the entire
project to clear the bar — and it is the one direction with real independent
academic backing (TSMOM). Reported honestly, with every caveat.

## Setup (pre-registered, not tuned after the fact)
- 19 ETFs (equity 6, rates 4, commodity 6, fx 3), daily, HistData/Stooq adjusted.
- Common window 2007-10-05 .. 2026-07-17 (all 19 present throughout, per B1).
- IS < 2020-11-20 (70%), OOS >= 2020-11-20 (30%), single OOS look.
- 15 IS configs (≤20 budget). Locked: lookback=9mo, skip=0, vol_lookback=30d, band=0.3.
- Costs 3 bps/side; vol target 10%.

## Result
| Window | Sharpe | CAGR | vol | maxDD | Calmar |
|---|---|---|---|---|---|
| IS 2007-2020 | 0.51 | 5.2% | 11.4% | 15.0% | 0.35 |
| OOS 2020-2026 (single look) | 0.97 | 10.5% | 10.9% | 19.2% | 0.54 |
| **FULL 2007-2026 (honest headline)** | **0.67** | **7.2%** | ~11% | 19.2% | — |

**Six gates: ALL PASS.**
`1 cost[x] 2 sharpe[x] 3 stability[x] 4 maxDD[x] 5 breadth[x] 6 DSR[x]`
- Cost robustness (PRIMARY): OOS Sharpe 0.95 at 1.5×, 0.93 at 2.0× — edge is not a
  cost artifact.
- Breadth (leave-one-sleeve-out OOS Sharpe): −commodity 0.78, −equity 0.82,
  −fx 0.94, −rates 0.86 — no single asset class carries it.
- Deflated Sharpe Ratio = **0.958** (> 0.95), computed against ~143 cumulative
  trials (128 prior price-action + 15 here) — significant after deflation.

## Post-pass robustness deep-dive (the skeptic's checks)
- **Per-year, all 19 years:** profitable in ~14 of 19; losing years 2009, 2011,
  2016, 2018, 2023 — the documented, survivable regime dependence of trend, not a
  hidden coin flip. Best years 2013/15/17/19/22/24; worst 2023 (−11%).
- **Drop the best year (2022):** OOS Sharpe 1.04 → 0.84. It does NOT collapse —
  2022 did not carry the result.
- **Parameter perturbation ±20%** (each free param): full-period Sharpe stays
  positive everywhere, 0.45–0.86. No knife-edge fit.

## Honest interpretation — what this IS and ISN'T
**IS:** a real, cost-surviving, breadth-robust, regime-broad edge on diversified
trend-following — exactly what the independent evidence predicted (a modest,
decayed-but-present premium). The full-period **Sharpe ~0.67** is the number to
anchor on; the OOS 0.97 is flattered by the strong 2020-2025 trend regime and
should not be extrapolated.

**ISN'T:** a money printer, and NOT yet proven live.
- Sharpe 0.67 ≈ ~7%/yr at ~11% vol with ~19% drawdowns and multiple losing years.
  On small capital that is modest money and requires patience through ugly stretches.
- A backtest pass is the FIRST gate, not the finish line. The spec ladder still
  applies: forward/paper test (≥ 6-12 months) → small live (0.25% risk) → scale.
- Premia decay (McLean-Pontiff: ~74% persists near-term, but it fades) — treat
  validation as ongoing, not a one-time stamp.
- Cost assumption 3 bps is fine for liquid ETFs; less-liquid ones (UNG, DBB, BWX)
  run higher, but the 2× cost stress (6 bps) still passed.
- Retail frictions not fully modeled: fractional shares, rebalancing discipline,
  taxes, tracking. Turnover ~14×/yr two-way is manageable but real.

## Decision
TESTED-PASS → proceed to **forward test** per the go-live ladder (paper-trade the
locked rules monthly, confirm live behavior matches backtest for 6-12 months)
before any real capital, and only then scale in slowly. Log every forward month;
if forward expectancy turns negative or drawdown exceeds ~1.5× the backtest maxDD
(~29%), suspend and re-examine.

**Bottom line:** after correctly falsifying the ICT/price-action family, the same
disciplined pipeline found a genuine, modest, robust edge in diversified trend-
following. That is the honest, hard-won win — a *real* edge, not an imaginary one.

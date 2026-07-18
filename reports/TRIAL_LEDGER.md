# Trial ledger — EURUSD intraday price-action research

Kept per Bailey & López de Prado (Deflated Sharpe Ratio / PBO): the number of
configurations tried is the single biggest driver of out-of-sample failure, so
it must be counted, not forgotten. Every future EURUSD price-action hypothesis
inherits this cumulative trial budget when computing a deflated significance bar.

## Stage 0 — ratified negative (2026-07-18)

**sweep→MSS→FVG on EURUSD / NY-AM has NO detectable cost-adjusted OOS edge across
3 out-of-sample tests. ARCHIVED.** Corroborated independently by the engineering-
evidence report `docs/spec/` review (base rates, ICT falsification literature,
Minimum Backtest Length). The negative is a first-class result: it saved capital
and it is being logged rather than patched away.

## Configurations tried on the archived family (~110)

| Variant | Grid cells | Notes |
|---|---|---|
| NYAM-SWEEP-FVG v1.0 | ~0 formal grid | 0 trades; diagnostic funnel runs only |
| NYAM-SWEEP-FVG v2.0 | 27 | frequency grid (mss×fvg×expiry), `reports/v2.0_is_grid.csv` |
| NYAM-ILS-FVG v1.0 (3y) | 27 + ~9 | pass1 CSV + inline disp×scn pass2 |
| NYAM-ILS-FVG v1.0 (10y) | 27 + 9 | pass1 + pass2 CSVs |
| Baselines / cross-checks | ~10 | defaults, London cross-check, prior-winner, 2015-2021 baseline |
| **Cumulative (distinct configs)** | **≈ 110** | |

**Implication (Minimum Backtest Length):** at ~0.65 trades/month the family could
never accumulate a valid sample; at ~110 trials even a 10-year IS is overfit-prone.
Both facts point the same way — the constraint was structural, not tuning effort.

## Raised bar for the next hypothesis

Anything new on EURUSD intraday price action must clear a *deflated* bar:
- lead with COST ROBUSTNESS as a primary gate (survive 1.5× **and** 2× costs),
- pre-register a hard trial budget (≤ 20–30 configs) and honor it,
- target ≥ 100 OOS trades (frequency, not session, is the lever),
- one single OOS look, computed with the actual cumulative trial count in mind.

New trials for a fresh hypothesis are logged in that hypothesis's own pre-reg doc.

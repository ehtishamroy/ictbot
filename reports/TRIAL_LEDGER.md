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

## EURUSD-FVGC v1.0 (Direction 2) — +18 configs, TESTED-FAIL

Pre-reg `docs/spec/PREREG_EURUSD-FVGC_v1.0.md`; 18 IS grid configs (2×9) within
the ≤24 budget; single OOS look. **Result: robust OOS-confirmed NEGATIVE**
(IS −0.35R / OOS −0.32R, PF 0.61/0.63). A direct signal probe (5,174 IS signals)
found fresh-FVG forward returns ~50/50 — the signal is directionless.
`reports/EURUSD-FVGC_v1.0_findings.md`.

**Cumulative distinct configs across all EURUSD price-action work: ≈ 128.**

## New program: DIVTREND v1.0 (different signal family) — 2026-07-19

Owner redirected to diversified time-series momentum (TSMOM), vol-scaled, across
a 20–40 instrument basket — the evidence-preferred fresh direction
(`docs/spec/PREREG_DIVTREND_v1.0.md`, `docs/spec/Redeploy_Direction_Evidence_Report.md`).
Different signal family (documented information content + high breadth), so it
addresses the root causes; but the deflated-significance accounting CONTINUES —
DIVTREND's ≤20-config budget is counted on top of the ~128 already spent, via
its own Deflated Sharpe Ratio gate (B5 #6). Universe fixed at pre-registration
(no in-sample universe cherry-picking). Abandonment rule pre-committed.

## DIVTREND v1.0 — TESTED-PASS (2026-07-19)

15 IS configs (<=20 budget). Locked lookback=9mo/skip=0/vol_lb=30d/band=0.3.
Single OOS look: all 6 gates PASS. OOS Sharpe 0.97, full-period 0.67, survives
2x costs, breadth-robust (leave-one-sleeve 0.78-0.94), DSR 0.958 vs ~143 trials.
Post-pass robustness held (drop-2022 -> 0.84; perturbation +/-20% all positive).
reports/DIVTREND_v1.0_findings.md. Next: forward/paper test per go-live ladder.

## Stage-2 escalation reached (2026-07-19)

Two distinct concept families (sweep→MSS→FVG; FVG-continuation) have failed OOS,
and the core signal is measured directionless. Per the pre-reg Stage-2 rule and
the evidence report: **bank the negative on EURUSD intraday price-action.** Any
further work should be genuinely new territory (different instrument/timeframe or
non-price-action signal), started as a new research program with its own budget —
not another patch here.

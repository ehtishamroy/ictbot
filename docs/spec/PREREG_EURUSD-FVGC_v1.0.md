# PRE-REGISTRATION — EURUSD-FVGC v1.0 (Fair Value Gap Continuation)

**Locked BEFORE any tuning.** This is a *fresh* hypothesis (not a 4th patch of the
archived sweep→MSS→FVG family), chosen on the evidence in the engineering report:
Direction 2 (higher-frequency, single mechanism) is the only path that removes the
binding sample-size constraint. Pre-registering the rules, gates, and trial budget
now is what keeps the eventual result honest.

## Hypothesis (one sentence)
In an established intraday EURUSD trend, price retracing into a fresh, displacement-
born fair value gap continues in the trend direction often enough to yield a
cost-adjusted positive expectancy that survives out-of-sample and 2× costs.

## Why this is tractable where the family was not
Frequency probe (existing FVG detector, OOS 2022-2024, 07-16 UTC, EMA50 filter,
fvg_min 0.3×ATR): **8,197 trend-aligned signals (~228/mo); 780 candidate days
(~22/mo).** Even after RR/fill/one-per-day attrition this clears **≥100 OOS
trades** — the floor the archived family (≈0.65/mo) could never reach.

## Single mechanism (NO concept stacking)
- **Trigger (the only trigger concept):** DEF-FVG-01 fresh fair value gap, born of
  a DEF-DISP-01 displacement, aligned with the trend.
- **Trend filter (CONTEXT, not a second trigger):** execution-TF (5m) EMA(`ema_len`);
  long only when close > EMA, short only when close < EMA.
- No sweep, no MSS, no order block, no killzone-liquidity, no DOL. Deliberately.

## Objective rules (mechanical, reproducible)
- **Instrument/TF:** EURUSD, 5m execution, 1-minute intrabar fills.
- **Session:** 07:00–16:00 UTC (London open → NY overlap). Fixed.
- **Long setup:** close > EMA(`ema_len`); a bullish FVG forms at bar i
  (`low[i] > high[i-2]`) whose displacement body ≥ `disp_mult`×ATR(14) and whose
  height ∈ [`fvg_min`, 3.0]×ATR. Short = mirror.
- **Entry:** limit at the FVG **proximal (near) edge** — filled only on a
  trade-through by ≥1 tick (directly addresses the archived model's 74% no-fill).
  Expires after `expiry_bars` or at 16:00 UTC.
- **Stop:** distal edge of the FVG ∓ `sl_buffer_points`.
- **Target:** fixed `rr_target` × initial risk (single target, no partials — fewer
  knobs, cleaner test). Hard flat at 16:00 UTC; `max_hold_bars` guard.
- **Guards:** spread cap (A5), one open position, ≤ `max_trades_per_day`, −2R daily
  stop, one entry per FVG.

## Free parameters — CAP 6 (kept deliberately small; every knob inflates PBO)
| # | param | default | test range |
|---|---|---|---|
| 1 | `ema_len` | 50 | 20–100 |
| 2 | `fvg_min` (×ATR) | 0.3 | 0.2–0.6 |
| 3 | `disp_mult` | 1.0 | 0.8–1.5 |
| 4 | `rr_target` | 2.0 | 1.5–3.0 |
| 5 | `sl_buffer_points` | 2 | 0–10 (set from MAE, not gridded) |
| 6 | `expiry_bars` | 6 | 3–12 |

## Validation protocol (cost-robustness LEADS)
- **Data:** EURUSD HistData 1m. **IS = 2015-2021, OOS = 2022-2024, single OOS look.**
- **Costs:** B2 model (0.8 pip spread, $7/lot, 0.3 pip slippage).
- **PRIMARY gate (must pass first):** OOS expectancy > 0 at **1.5× AND 2.0× costs**.
  If positive at 1× but negative at 1.5×/2× → **reject as a cost artifact.**
- **Then the six B5 gates on OOS at 1× costs**, with the trade-count floor raised
  to **OOS trades ≥ 100** (not 30).
- **Then B6 robustness** (±20% perturbation, session ±15 min, monthly regime).
- **Frequency downgrade rule:** if the built model cannot produce ≥100 OOS trades,
  downgrade/abandon (same disease as the archived family).

## Trial budget (hard, pre-committed)
- **≤ 24 configurations total**, IS only, ≤3 params per coarse grid pass, ≤2 passes.
- `sl_buffer` set from IS winners' MAE p90 (never gridded).
- **One** OOS look at locked params. These 24 trials are logged in `TRIAL_LEDGER.md`
  and the significance bar is deflated against the cumulative count (≈110 already
  spent on the archived family + these).
- **Escalation:** if EURUSD-FVGC also fails OOS under this protocol, and one more
  distinct fresh mechanism fails, bank the negative on EURUSD intraday price-action
  generally (report's Stage-2 rule) — do not keep spinning.

## Status: PRE-REGISTERED, NOT YET BUILT.
Awaiting owner ratification of (a) this mechanism vs. order-block-retest, (b) these
gates, (c) this trial budget — before a single line of tuning is run.

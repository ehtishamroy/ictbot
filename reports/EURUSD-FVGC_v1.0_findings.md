# EURUSD-FVGC v1.0 — findings (Direction-2 fresh hypothesis)

**Status: TESTED-FAIL — and this one is decisive.** Unlike the archived family
(which failed on rarity/overfit), FVGC failed with a large, robust,
out-of-sample-CONFIRMED *negative* edge, and a direct signal probe shows why:
the FVG signal carries no exploitable directional information on EURUSD 5m.

## Result (pre-registered protocol, IS 2015-2021 / OOS 2022-2024, 1m intrabar)
| Window | n | win% | avgRR | expectancy | PF | maxDD(R) |
|---|---|---|---|---|---|---|
| IS 2015-2021 | 2746 | 33.1 | 1.22 | **−0.35R** | 0.61 | 950 |
| OOS 2022-2024 | 1095 | 34.1 | 1.22 | **−0.32R** | 0.63 | 357 |
| OOS @1.5x costs | 1095 | — | — | −0.48R | — | — |
| OOS @2.0x costs | 1095 | — | — | −0.64R | — | — |

- **Frequency solved:** 30.5 trades/month, 3,841 lifetime — far above the 100-OOS
  floor. The sample-size disease of the archived family is gone.
- **Not overfit:** IS ≈ OOS (−0.35 vs −0.32R, PF 0.61 vs 0.63). This is a *stable,
  reproducible negative*, not a fluke — the strategy reliably loses.
- **PRIMARY cost gate: FAIL** (negative at 1x, worse at 1.5x/2x). Six B5 gates
  FAIL (only trade-count and stability pass — a stable loser is still "stable").
- Nearly every one of the 36 OOS months is negative.

## Root cause — the FVG signal is directionless (IS probe, 5,174 signals)
Forward return in the *continuation* direction after a fresh, displacement-born,
trend-aligned FVG (normalized by ATR):

| Horizon | mean | median | % positive |
|---|---|---|---|
| 6 bars (30m) | −0.031 | −0.071 | 48.1% |
| 12 bars (1h) | −0.029 | −0.099 | 48.5% |
| 24 bars (2h) | +0.022 | −0.077 | 49.1% |

**~50/50, indistinguishable from a random walk.** So:
- Momentum-continuation has no edge (confirmed: FVGC loses).
- Mean-reversion is NOT a hidden winner either — the reversion drift is tiny
  (medians ~−0.08 ATR) and nowhere near enough to overcome ~1 pip round-trip
  cost. Fading these signals would fight a near-zero signal against real costs.
- FVGC's −0.35R is explained fully: a coin-flip signal traded at a fixed 2:1 RR
  wins ~33% of the time (the break-even rate), and costs turn break-even into a
  loss. No bug — the design faithfully monetizes a non-signal into the cost drag.

## Archive entry (spec C5)
```
2026-07-19 | EURUSD-FVGC v1.0 | EURUSD / London+NY (07-16 UTC) | IS 2015-21/OOS 22-24
Gates failed: PRIMARY cost gate + 1,2,3,6   Key: OOS exp=-0.32 PF=0.63 n=1095
  (IS exp=-0.35 PF=0.61; stable IS=OOS => robust negative, not overfit)
Diagnosis: direct probe shows fresh-FVG forward returns are ~50/50 (48-49% pos);
  the signal has no directional edge, so any fixed-RR mechanical strategy on it
  bleeds the cost drag. Neither momentum nor reversion is exploitable here.
Decision: ARCHIVE. Escalate to Stage-2 (bank the negative) per the pre-reg rule:
  the sweep family AND a distinct fresh mechanism have now both failed OOS, and
  the underlying signal is measured directionless.
```

## Recommendation: BANK THE NEGATIVE (evidence-based)
The pre-registered escalation rule has triggered: two distinct concept families
(sweep→MSS→FVG; FVG-continuation) have failed OOS, and a direct probe now shows
the core price-action signal is directionless on EURUSD intraday. The disciplined
conclusion the evidence supports:

> **On EURUSD intraday (5m, London+NY), FVG/sweep price-action patterns do not
> carry an exploitable, cost-adjusted edge. Validated across 3+ mechanisms and
> 10 years, under correct IS/OOS discipline. Archived.**

Continuing to spin new price-action variants on this instrument/timescale is the
sunk-cost error the evidence report explicitly warns against (each new variant
also burns multiple-testing budget, raising the bar further). Genuinely new
*territory* — a different instrument class, a higher/lower timeframe, or
non-price-action signals (e.g. carry, calendar/session seasonality, volatility
regime) — would be a fresh research program, not a 5th patch here.

**This negative is the project's real deliverable: a rigorously validated "no edge
here," obtained by a pipeline that repeatedly refused to ship an overfit.**

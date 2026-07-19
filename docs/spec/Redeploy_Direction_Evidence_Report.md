# Redeploying a Rigorous Backtest Pipeline After a Validated Negative: Which Fresh Direction, on the Evidence

*Engineering documentation for hypothesis selection. Not financial advice. No win rate, return, or live edge is asserted for any strategy below — only the direction and quality of the independent evidence.*

## The situation in one line
Two structurally different mechanical price-action families are now archived on EURUSD intraday (sweep→MSS→FVG, then FVG-continuation), the second with a direct probe proving the signal is directionless (~50/50 forward returns). The question is no longer "which pattern" — it's **which fresh direction has a real, independent, cost-survivable, and *testable* evidence base** to point the existing discipline at.

## TL;DR — Ranked recommendation

| Rank | Direction | Evidence base | Testable by a solo dev? | Cost-fragile? | Verdict |
|---|---|---|---|---|---|
| **1** | **Diversified time-series momentum / trend-following across many liquid futures markets** (higher-TF trend done with *breadth*, not one pair) | **Strongest** — documented across 58 instruments, every asset class, ~a century | **Yes** — naturally high-breadth | **No** — low turnover, large moves | **Best next hypothesis** |
| 2 | Cross-sectional carry across a currency / multi-asset basket | Strong premium, but currency carry carries genuine crash/tail risk | Yes, high-breadth, but tail risk is hard to backtest | Medium (swap/rollover) | Good diversifier, dangerous as a concentrated solo bet |
| 3 | Volatility scaling / vol-targeting | Contested as a standalone edge; accepted as a *sizing overlay* | As an overlay, yes | Depends on turnover | Use as position-sizing, **not** as the edge |
| 4 | Calendar / seasonality | Weakest; the textbook data-snooping trap | Yes but likely spurious | Very (thin effects) | Avoid as a primary edge |
| — | **Single-pair H4/daily swing on EURUSD alone** | N/A | **No — recreates your sample-size wall** | No | **Explicitly avoid** |

**The single most important structural insight:** your project failed on *one instrument, at high frequency, on a directionless signal*. The fix is not a different pattern — it is **(a) a signal with documented information content** (trend and carry are the only retail-accessible ones with real academic support) **and (b) breadth** — trading many instruments so the math works in your favour even with a small per-bet edge. This is the Fundamental Law of Active Management, and it is the through-line of this whole report.

---

## The connective tissue: breadth is why your architecture was fragile

Grinold & Kahn's Fundamental Law states the information ratio equals the information coefficient times the square root of breadth (IR = IC × √Breadth), where breadth is the number of independent bets per year. The worked example is the whole story: a great-skill manager (IC = 0.10) making one bet a year has an IR of ~0.10, while a modest-skill model (IC = 0.05) ranking 3,000 names has an IR of ~2.74. And crucially, the square-root term means going from 1 to 100 independent predictions is a 10× improvement, while lifting per-bet skill from 0.05 to 0.10 is only 2×.

Translated to your project: a single EURUSD intraday model is a **low-breadth** bet — you were trying to win by raising per-trade skill (IC) on one instrument, the hardest possible lever, on a signal that turned out to have IC ≈ 0. Every direction that ranks well below does so because it is **naturally high-breadth**: it spreads a *modest* documented edge across dozens of instruments, which is both more robust and — directly relevant to your last two months — **more statistically testable**, because many instruments generate many independent observations. The honest caveat baked into the law: it assumes predictions are truly independent and implementation is frictionless, so real-world IR is always lower than the formula implies — but the directional lesson (diversified, systematic, high-breadth beats single-bet skill-chasing) holds.

This reframes your "higher timeframe" instinct. Higher TF is right about costs but wrong if done on **one pair** — an H4/daily EURUSD-only model produces a handful of independent trades per year and lands you straight back in the unverifiable-sample problem you just escaped. Higher TF only works as an upgrade if it is **also** multi-market.

---

## Direction-by-direction evidence

### A — Time-series momentum / trend-following *(strongest evidence; recommended, if done with breadth)*

The foundational result (Moskowitz, Ooi & Pedersen 2012): across 58 diverse futures and forwards spanning equity indices, currencies, commodities and bonds over 25+ years, an instrument's past 12-month excess return positively predicts its future return — a "trend" effect that persists ~12 months then partially reverses, and 12-month time-series momentum profits are positive not just on average but for every one of the contracts examined. It is theoretically notable because the existence of time-series momentum rejects the random-walk hypothesis, and the follow-up literature extended it across developed and emerging markets, individual stocks, and back through roughly a century of data (Hurst, Ooi & Pedersen, "A Century of Evidence on Trend-Following Investing").

**But the regime-dependence is real and must be planned for.** Trend-following had a "lost decade" of roughly flat performance from about 2009 to 2019, then a record ~27.3% for the SG Trend Index in 2022 — its best year since inception in 2000 — when bonds and stocks fell together (AQR's trend strategies returned as much as 70% in 2022), and then struggled again in the low-volatility equity bull that followed. The mechanism is not a hidden flaw — it is the known trade-off: choppy, range-bound markets punish trend-followers with whipsaw losses, and a decade of sub-2% annualized returns with a ~21.8% drawdown happened within recent memory. That is the decisive contrast with your dead concept: **trend's failure mode is documented, survivable, and diversifiable-across-markets — not a directionless coin flip.**

*Why it fits you:* strongest independent evidence of the five; naturally high-breadth (trade 20–40 markets, not one pair); and **low cost-sensitivity** — monthly-ish rebalancing on multi-week moves means costs are trivial relative to range, which directly fixes what killed your intraday model.

### B — Carry *(real premium, real tail risk; good diversifier, hazardous solo)*

Carry is one of the most robust documented premia (Koijen, Moskowitz, Pedersen & Vrugt, "Carry"): a carry return premium is present in all nine asset classes studied, is not explained by known predictors, and rejects uncovered interest parity in favour of time-varying risk premia; in FX specifically the currency risk premium is as large as the equity risk premium. The catch is the shape of the risk: currency carry exhibits negative skewness and crash risk (Brunnermeier, Nagel & Pedersen), a feature that is *not* shared by carry in most other asset classes, and carry trades are exposed to global FX volatility and liquidity risk — when liquidity dries up, high-carry currencies crash. Practitioners also note carry can be difficult to implement due to high transaction costs (Burnside et al.), and the tail events are a classic "peso problem" — rare, severe, and under-sampled in any backtest window, so a clean-looking historical test can badly understate the true downside.

*Why it ranks second:* real and high-breadth, but the "picking up pennies in front of a steamroller" tail is genuinely hard to model, and for FX you must model swap/rollover accurately. Best as a *diversifier alongside trend* (the two are complementary and both appear in the Koijen et al. framework), not as a concentrated standalone program.

### C — Volatility timing / vol-managed portfolios *(contested edge; use only as a sizing overlay)*

This is an active, unresolved academic dispute — which by itself makes it a poor primary bet for a solo researcher. The original claim (Moreira & Muir 2017): volatility-managed portfolios earn significantly positive alphas and survive realistic transaction costs for the market portfolio. The rebuttals are serious and published in the same top journal: Cederburg, O'Doherty, Wang & Yan (2020) find volatility-managed portfolios do not systematically outperform their unmanaged counterparts out-of-sample, with the failure stemming from structural instability in the underlying regressions; and Barroso & Detzel (2020) show the gains do not survive transaction costs for every factor except the market. When the top people in the field can't agree whether an effect survives OOS and costs, a solo dev betting a research program on it is taking the wrong side of the multiple-testing problem.

*Verdict:* volatility **scaling as position sizing** (target constant risk, lever down when vol is high) is broadly accepted and is in fact how trend portfolios are built — adopt it there. Volatility *timing as a standalone alpha* is too contested to be your edge.

### D — Calendar / seasonality *(weakest; the data-snooping poster child)*

Calendar effects are the canonical example of what happens when you test enough rules on one dataset (Sullivan, Timmermann & White specifically re-examined calendar rules under data-snooping correction). They are also where the decay literature bites hardest (see below). Some overnight/turn-of-month effects have shown persistence, but they are small, cost-fragile, and the prior probability that any given calendar pattern is spurious is high. *Verdict:* avoid as a primary edge; at most a minor overlay filter, never the thesis.

### E — Different instrument class *(not a signal — the vehicle that supplies breadth)*

"Different instrument class" isn't a separate edge; it's the **delivery mechanism** for A and B. A diversified basket of liquid futures (equity indices, rates, commodities, FX) is the natural home for both trend and carry and is what supplies the breadth term. It is retail-accessible via futures or managed-futures ETFs, though the latter's live record shows the same regime dependence — e.g. one such ETF has struggled to generate meaningful returns in the low-volatility equity bull market since its 2022 launch, because managed futures thrive on volatility and sustained trends, not relentless bull markets. Crypto is an alternative universe (young, volatile, less crowded, but data-poor and regime-unstable) — plausible as a *satellite*, not a foundation.

---

## The meta-caveat that applies to *every* direction: premia decay

Whatever you pick, treat it as decaying, not permanent. The benchmark result (McLean & Pontiff 2016): across 97 published cross-sectional predictors, portfolio returns are 26% lower out-of-sample and 58% lower post-publication, with the ~32-point gap attributed to investors trading on the published signal, and post-publication declines are largest exactly for the predictors with the highest in-sample returns — a direct warning against chasing the flashiest backtest. The saving grace, and the reason these directions still beat inventing a third private pattern: the decay is **partial, not total** — predictability persists out-of-sample; in the first three years after the original sample ends, roughly 74% of the in-sample return remains. Trend and carry are published, crowded, and decayed — but they are *real and still there*, which is more than can be said for a directionless intraday pattern.

---

## Infrastructure transfer: your engine mostly doesn't move — your *discipline* does

Be clear-eyed about this, because it affects the build estimate:

- **Does not transfer:** your event-driven, single-pair, tick/intrabar engine. Trend and carry are **daily-bar, portfolio-level, cross-sectional**. You need many-market daily data, a portfolio backtester (ranking + weighting across instruments), and volatility-scaled/risk-parity position sizing — a different architecture, not a parameter swap.
- **Transfers perfectly (and is the real asset):** the *methodology* you already built and proved — pre-registration, strict single-look OOS, realistic cost modelling, cost-robustness-first gates, data hygiene/DST correctness, the multiple-testing budget, and the willingness to archive. That rigor is exactly what most retail systematic efforts lack, and it ports directly onto a diversified-futures program.

**Net:** you are not throwing away the pipeline; you are pointing its *discipline* at an architecture that has both a documented edge and enough breadth to be testable.

---

## Cost sensitivity: this is the direct antidote to what killed you

Your model died from transaction costs eroding a weak signal (−0.13R → −0.34R at 1.5× costs). The ranking above is, not coincidentally, also a **turnover ranking**: trend (low turnover, large multi-week moves) and carry (held for the yield) pay costs rarely relative to the size of the moves they harvest, whereas your intraday model paid the spread on every one of thousands of trades. Moving to higher-TF, multi-market trend/carry attacks the exact failure mode you just diagnosed — provided you still model swap/rollover (carry) and keep rebalancing infrequent.

---

## Recommended next hypothesis (pre-registration skeleton)

If you continue rather than banking permanently, pre-register **before any tuning**:

1. **Concept:** diversified time-series (absolute) momentum — long instruments with positive trailing ~12-month return, short those negative — across a basket of **20–40 liquid, low-correlation futures** (equity indices, rates, commodities, FX). Optionally add a cross-sectional carry sleeve as a second, independent signal.
2. **Sizing:** volatility-scaled to a constant target risk per instrument (this is where vol-targeting belongs — as sizing, not alpha).
3. **Data/architecture:** daily bars, portfolio backtester, realistic per-market costs incl. roll and (for carry) swap.
4. **Gates (unchanged philosophy):** cost-robustness first (survive 1.5×–2× costs), single OOS look, and — because breadth is the entire thesis — require the edge to hold across **market subsets** (drop any one asset class and it should degrade gracefully, not collapse).
5. **Trial budget:** you have spent ~128 configs on price-action; keep the new program's budget explicit and small, and compute the deflated significance against it. Different *signal family*, but the same disciplined accounting.
6. **Pre-commit the abandonment rule:** if a diversified, high-breadth, low-cost trend/carry program *also* fails this protocol OOS, that is strong evidence to bank systematic trading research entirely for now — because you will have falsified not just a pattern but the best-documented edges available to a retail systematic trader, done correctly.

## Bottom line
- The evidence points to **diversified, multi-market time-series momentum (with an optional carry sleeve), sized by volatility** as the single best fresh direction: strongest independent support, naturally high-breadth (which fixes the sample-size wall), and low cost-sensitivity (which fixes your specific burn).
- **Do not** run higher-timeframe EURUSD-only swing — it recreates the exact unverifiability problem you just escaped.
- Treat every premium as decayed-but-real, keep your pre-registration and multiple-testing discipline, and pre-commit the rule that a rigorous failure *here* means banking systematic research is the rational end state — not a fifth mutation.

## Caveats
- No performance, edge, or win rate is promised for any direction; all figures are documentation of prior/independent research, and every effect cited has documented decay and regime dependence.
- The strongest evidence (TSMOM, carry) is for **diversified, multi-instrument portfolios**, not single-pair retail implementations; a solo trader's realized results will differ and are subject to costs, capacity, and execution the source studies do not fully capture.
- Volatility-timing and calendar effects are included mainly to argue *against* using them as a primary edge; that recommendation is itself a judgment, not settled fact.
- Retail-accessible futures/ETF implementations carry their own frictions (contract rolls, margin, ETF fees, tracking) not fully modeled here — verify against your own broker and data before committing.
- Breadth math (IR = IC × √Breadth) assumes independent bets and no frictions; real breadth is lower than the raw instrument count because markets are correlated, so do not over-credit a large universe.

---

### Key sources
- Moskowitz, Ooi & Pedersen (2012), "Time Series Momentum," *Journal of Financial Economics* 104.
- Hurst, Ooi & Pedersen, "A Century of Evidence on Trend-Following Investing" (AQR).
- Koijen, Moskowitz, Pedersen & Vrugt (2018), "Carry," *Journal of Financial Economics*.
- Lustig, Roussanov & Verdelhan; Menkhoff, Sarno, Schmeling & Schrimpf — carry, FX volatility and crash risk.
- Brunnermeier, Nagel & Pedersen (2009) — carry crashes and liquidity.
- Moreira & Muir (2017), "Volatility-Managed Portfolios," *Journal of Finance*.
- Cederburg, O'Doherty, Wang & Yan (2020), "On the performance of volatility-managed portfolios," *JFE*; Barroso & Detzel (2020) — costs.
- McLean & Pontiff (2016), "Does Academic Research Destroy Stock Return Predictability?", *Journal of Finance*.
- Grinold & Kahn, *Active Portfolio Management* — the Fundamental Law (IR = IC × √Breadth).
- Sullivan, Timmermann & White (1999); White (2000) — data-snooping and calendar effects.
- SG Trend / SG CTA Index performance (2009–2019 flat, 2022 record year) — Société Générale / industry reporting.

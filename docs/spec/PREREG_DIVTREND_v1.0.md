# DIVTREND v1.0 — Diversified Time-Series Momentum, Vol-Scaled
## Pre-registration & Complete System Spec

**Engineering documentation for an untested hypothesis. Not financial advice.**
**Status: UNTESTED. Pre-registered BEFORE any tuning.** No Sharpe, return, or edge
is asserted; performance may only come from a backtest run under Part B and
reported via Part F.

---

## READ THIS FIRST — why this direction, and what "working" means

This is a **fresh research program**, chosen on independent evidence
(`docs/spec/Redeploy_Direction_Evidence_Report.md`) after two structurally
different EURUSD intraday price-action families were archived (the second with a
direct probe proving the signal was directionless). It deliberately fixes the
three things that killed the prior work — all with one move, **breadth**:

| What killed the old work | How DIVTREND fixes it |
|---|---|
| Directionless signal (IC≈0) | Time-series momentum: the best-documented retail edge — positive 12-mo predictability across 58 futures, every asset class, ~a century (Moskowitz-Ooi-Pedersen 2012; Hurst-Ooi-Pedersen). Real information content. |
| Sample-size wall (~0.65 trades/mo) | Trade 20–40 markets → naturally high-breadth → many independent observations → actually testable (Fundamental Law: IR = IC × √Breadth). |
| Cost erosion (−0.13R→−0.34R at 1.5×) | Monthly rebalance on multi-week moves → costs trivial vs range. Low turnover is the direct antidote. |

**Definition of done:** all Part-B gates hold on a single OOS look AND the edge
survives 1.5×–2× costs AND degrades *gracefully* (not collapse) when any one
asset class is dropped (the breadth thesis must be real, not one lucky sleeve).
**Pre-committed abandonment:** if a diversified, high-breadth, low-cost trend
program *also* fails this protocol, that is the signal to **bank systematic
research** — we will have falsified the best documented retail edges, done
correctly. Not defeat; a definitive answer.

**What transfers from the old project:** the *discipline only* — pre-registration,
single-look OOS, cost-robustness-first gates, data hygiene/DST, the trial-budget
ledger, willingness to archive. The event-driven intraday engine does **not**
transfer; Part D specifies the new portfolio architecture that must be built.

---

# PART A — STRATEGY SPECIFICATION

## A0. Strategy ID Card
| Field | Value |
|---|---|
| Name | DIVTREND |
| Version | v1.0 |
| Concept | Time-series (absolute) momentum, vol-scaled, cross-market |
| Universe | 20–40 liquid, low-correlation instruments across ≥4 asset classes |
| Signal concepts (cap 2) | TSMOM (primary); optional independent CARRY sleeve (v1.x, not v1.0) |
| Rebalance | Monthly (last trading day), positions held to next rebalance |
| Sizing | Volatility-scaled to constant risk per instrument; portfolio vol target |
| Data | Daily bars, roll-adjusted continuous futures (or liquid ETF proxies) |
| Status | UNTESTED |
| Date | 2026-07-19 |

## A1. Universe (breadth is the thesis — specify it up front)
Target **≥ 24 instruments**, ~equal across 4 sleeves so no single asset class
dominates. Canonical futures, with a retail **ETF-proxy** column (freely
available daily history, what v1.0 will actually be built/tested on first):

| Sleeve | Futures (canonical) | ETF proxy (v1.0 build) |
|---|---|---|
| Equity indices | ES, NQ, FDAX, FTSE, NKD, … | SPY, QQQ, EFA, EEM, EWJ, IWM |
| Rates / bonds | ZN, ZB, ZF, Bund, … | IEF, TLT, SHY, BWX |
| Commodities | CL, GC, SI, HG, NG, ZC, ZS, … | USO, GLD, SLV, DBB, DBA, UNG |
| FX | 6E, 6J, 6B, 6A, … | UUP, FXE, FXY, FXB |

Selection is FIXED at pre-registration (no in-sample cherry-picking of the
universe — that would be the worst multiple-testing sin). Instruments must have
history covering the full IS+OOS window; any that don't are excluded up front and
listed. The ETF proxy is the v1.0 vehicle (data accessibility); a futures
re-implementation is a documented v2.0 upgrade, not a tuning step.

## A2. Signal — DEF-TSMOM-01 (the only trigger concept)
At each monthly rebalance date `t`, for each instrument `i`:
- Compute trailing **`lookback_months`** total return, optionally skipping the
  most recent `skip_recent_month` (momentum's short-term-reversal guard):
  `mom_i = P[t − skip] / P[t − skip − lookback] − 1`.
- **Direction:** `sign(mom_i)` → +1 long if positive, −1 short if negative, 0 if
  exactly flat or history insufficient. This is *absolute/time-series* momentum
  (each instrument vs its own past), NOT cross-sectional ranking.

## A3. Sizing — DEF-VOLSCALE-01 (vol as sizing, never as alpha)
- Estimate each instrument's ex-ante annualized volatility `σ_i` from daily
  returns over `vol_lookback_days` (exponentially weighted).
- Raw weight: `w_i = sign(mom_i) × (target_vol_inst / σ_i)`, so every instrument
  targets equal risk `target_vol_inst` (fixed, e.g. 10% annualized).
- **Portfolio vol target:** scale the whole book by `k = target_vol_port / σ_port`
  where `σ_port` is the ex-ante portfolio vol of the raw-weighted book (using the
  same vol estimates and a rolling correlation), capping `k ≤ k_max` to avoid
  leverage spikes. `target_vol_port` fixed (e.g. 10% annualized).
- Per-instrument gross weight cap (fixed) to prevent any single name dominating.

## A4. Portfolio construction & turnover control
- Rebalance monthly to the target weights above. No intramonth trading (v1.0).
- **No-trade band:** only trade an instrument if its target weight moved by
  > `rebal_band` (fixed, e.g. 0.1× its target) since last rebalance — kills
  churn from tiny vol wiggles, protects the low-cost thesis.
- Positions are continuous weights, not discrete entries; there is no per-trade
  stop-loss (risk is controlled by vol-scaling + the portfolio vol target).

## A5. Risk management (portfolio-level)
- Constant portfolio vol target (A3) is the primary risk control.
- Per-instrument gross cap; per-sleeve gross cap (no sleeve > ~40% of gross risk).
- Max gross leverage cap `k_max` (fixed).
- Drawdown is expected and planned for (trend has documented ~20%+ DDs); there is
  NO discretionary de-risking rule in v1.0 — that would be a hidden parameter.

## A6. Parameter Table — 4 free parameters (cap 6; kept minimal on purpose)
| # | Parameter | Default | Test range | Note |
|---|---|---|---|---|
| 1 | `lookback_months` | 12 | 6–12 | canonical TSMOM horizon; don't over-explore |
| 2 | `skip_recent_month` | 1 | 0–1 | short-reversal guard |
| 3 | `vol_lookback_days` | 60 | 20–120 | ex-ante vol estimate window |
| 4 | `rebal_band` | 0.1 | 0.0–0.3 | turnover / cost control |

**Fixed (not optimized):** `target_vol_inst` = 10%, `target_vol_port` = 10%,
per-instrument gross cap, per-sleeve cap, `k_max`, monthly rebalance frequency,
universe membership, EW vol/correlation estimator. **`target_vol_*` are risk
preferences, not edge levers — never gridded.**

## A7. Pseudocode
```
for each month-end date t:
    for each instrument i with sufficient history:
        mom  = P[i, t-skip] / P[i, t-skip-lookback*21] - 1
        sig  = sign(mom)
        sig_i = 0 if |mom| == 0 else sig
        vol_i = ewvol(daily_ret[i], vol_lookback_days) * sqrt(252)
        w_i   = sig_i * (target_vol_inst / vol_i)
    apply per-instrument & per-sleeve gross caps to {w_i}
    sig_port = ex_ante_portfolio_vol({w_i}, cov_ew)      # rolling covariance
    k = min(target_vol_port / sig_port, k_max)
    w_i *= k
    # no-trade band vs current weights
    for each i: if |w_i - w_held_i| < rebal_band * |w_i|: w_i = w_held_i
    trade to {w_i}; accrue costs on the traded delta; hold to t+1 month
record daily portfolio returns net of costs
```
(Short side is symmetric by construction — `sign` handles both.)

---

# PART B — VALIDATION PROTOCOL

## B1. Data requirements
- **Daily** bars, dividend/roll-adjusted total-return series (ETF adjusted-close,
  or roll-adjusted continuous futures). Document the source and adjustment method
  in every report.
- **History ≥ 15 years** (ideally 20+) covering multiple regimes: the 2009–2019
  trend "lost decade", the 2022 trend surge, and the weak post-2022 period must
  ALL be inside the window (otherwise the regime story is untested).
- Every universe member must span the full window or be excluded up front.

## B2. Cost model (mandatory; zero-cost is rejected)
- Per-instrument round-trip cost on the **traded weight delta** each rebalance:
  ETF spread + commission (bps of notional), or futures spread + commission + roll
  cost. Use realistic retail figures per instrument, documented.
- **Turnover is reported explicitly** (annualized two-way) — the low-cost thesis
  must be shown, not assumed.
- **Re-run every final result at 1.5× and 2.0× costs** (leading gate, B5).

## B3. Split
- **Chronological IS/OOS.** IS = earliest ~70% of the window; OOS = latest ~30%,
  looked at **once**. All tuning on IS only.
- Prefer **walk-forward** (expanding-window) as the primary evidence, with the
  single hold-out OOS as the confirmatory look.

## B4. Metrics (portfolio-level — Sharpe, not per-trade R)
Annualized return, annualized vol, **Sharpe** (primary), Sortino, max drawdown
(%), Calmar, worst month, monthly win rate, skew/kurtosis, annualized turnover,
per-sleeve return contribution, and the **Deflated Sharpe Ratio** computed against
the cumulative trial count (≈128 already spent + this program's budget).

## B5. Pass gates (cost-robustness LEADS; breadth is a first-class gate)
A version PASSES only if ALL hold on the OOS window:
| # | Gate | Threshold |
|---|---|---|
| 1 | **Cost robustness (PRIMARY)** | net Sharpe > 0 AND net return > 0 at **both 1.5× and 2.0×** costs |
| 2 | OOS net Sharpe | ≥ **0.40** (modest — premia are decayed-but-real) |
| 3 | Stability | OOS Sharpe ≥ **0.5 × IS Sharpe** |
| 4 | Max drawdown | ≤ **35%** at the 10% vol target |
| 5 | **Breadth robustness** | drop ANY one asset-class sleeve → OOS Sharpe stays **> 0** (degrade gracefully, not collapse) |
| 6 | **Deflated Sharpe Ratio** | DSR > 0 (significant after deflating by the trial count) |

Fail any gate → status TESTED-FAIL for that version. Two failed versions of this
concept → archive DIVTREND and invoke the Part-C abandonment rule.

## B6. Robustness (after gates pass, before any live consideration)
1. Parameter perturbation ±20% each free param → Sharpe stays positive.
2. Cost stress already in gate 1; also test at 2.5×.
3. **Leave-one-sleeve-out AND leave-one-instrument-out** — no single market carries
   the result.
4. Sub-period table (per-year Sharpe) — confirm the known regime dependence is
   present and survivable, and that no single year dominates.

---

# PART C — TRIAL BUDGET & ABANDONMENT

- **Cumulative configs across all prior EURUSD price-action work: ≈ 128** (logged
  in `reports/TRIAL_LEDGER.md`). DIVTREND is a different signal family but the
  deflated-significance accounting continues.
- **DIVTREND trial budget: ≤ 20 configurations**, IS/walk-forward only, ≤ 2 free
  params per coarse grid pass, ≤ 2 passes. `target_vol_*` never gridded. Universe
  fixed at pre-registration. One single OOS look at locked params.
- Every config counts toward the DSR (gate 6).
- **Abandonment (pre-committed):** if DIVTREND fails Part B, and one further
  distinct high-breadth edge (e.g. the carry sleeve) also fails, **bank systematic
  research** — the best documented retail edges will have been falsified under
  correct protocol. That is the rational end state, not a further mutation.

---

# PART D — ARCHITECTURE (what must be built; what transfers)

**Does NOT transfer:** the event-driven, single-pair, 5m/intrabar engine.
**Must be built (new):**
1. **Multi-market daily data layer** — load N adjusted daily series, align on a
   common calendar, handle missing days, compute daily returns.
2. **Portfolio backtester** — monthly rebalance loop, ex-ante vol & rolling
   covariance estimators, vol-scaling + portfolio-vol-target sizing, gross caps,
   no-trade band, cost accrual on traded deltas, daily NAV.
3. **Portfolio metrics + DSR** (extends the existing `reporting/` — Sharpe/Sortino/
   Calmar/turnover/DSR/per-sleeve, alongside the R-based metrics already built).
4. **Walk-forward + single-OOS harness** (the split/gate discipline ports; the
   unit of analysis changes from trades to a daily return stream).

**Transfers directly:** `config.py` loader + range validation, the pre-reg/gate/
trial-ledger discipline, `data/load.py` CSV ingestion patterns, cost-model
philosophy, `reporting/report.py` templating, the whole test-first workflow.

Estimate: this is a **new module (`src/ictbot/portfolio/`)**, not a parameter
swap — but ~40% of the plumbing (config, loading, reporting, tests) is reusable.

---

# PART E — DATA ACQUISITION (the immediate blocker → next action)

v1.0 needs **≥ 24 liquid ETFs, daily adjusted-close, ≥ 15 years**. Options, in
order of preference for a solo dev:
1. **User provides** daily adjusted-close CSVs (Yahoo Finance "Download" per
   ticker, or a bulk export) for the A1 ETF list → drop in `data/raw/etf/`.
   Same upload flow as the HistData files. This is the fastest path.
2. **Stooq daily CSVs** (`stooq.com`, free daily history per ticker) — if egress
   is permitted from the session; will be attempted and reported.
3. Roll-adjusted futures (Nasdaq Data Link / broker) → the v2.0 canonical build.

Until data lands, the build proceeds on the **architecture** (Part D modules +
tests on synthetic multi-market data), exactly as the intraday engine was built
and unit-tested before real data arrived.

---

# PART F — REPORTING TEMPLATE (paste back after every run)
```
Strategy: DIVTREND vX.Y   Universe: <N instruments, sleeves>   Vehicle: <ETF|futures>
Window: <dates>   Data: <source, adjustment>   Rebalance: monthly
Costs: <per-instrument model>   (1.0x / 1.5x / 2.0x)   Turnover(ann, 2-way)=

IS  : CAGR=  vol=  Sharpe=  Sortino=  maxDD%=  Calmar=  worstMo=  win%=
OOS : CAGR=  vol=  Sharpe=  Sortino=  maxDD%=  Calmar=  worstMo=  win%=
Per-year Sharpe table: <rows>      Per-sleeve contribution: <rows>
Leave-one-sleeve-out OOS Sharpe: <4 rows>

Gates: 1[cost1.5/2x] 2[Sharpe≥.4] 3[stability] 4[maxDD≤35] 5[breadth] 6[DSR]
   ->  PASS / FAIL
DSR (vs ~128+budget trials) =        Trial budget used = __/20
Status restated: UNTESTED / TESTED-FAIL / TESTED-PASS
```

---

# APPENDIX 1 — QUANTIFIED DEFINITIONS
- **DEF-TSMOM-01:** direction = `sign(P[t−skip]/P[t−skip−lookback] − 1)`; absolute
  (own-history) momentum, monthly, `lookback` in months (×21 trading days).
- **DEF-VOLSCALE-01:** `w = sign × target_vol_inst / σ_ewma`, then portfolio scaled
  by `min(target_vol_port/σ_port, k_max)`; vol is sizing, never signal.
- **Sharpe (annualized):** `mean(daily_net_ret)/std(daily_net_ret) × √252`.
- **Deflated Sharpe Ratio (Bailey–López de Prado):** SR adjusted for the number of
  trials, non-normality (skew/kurtosis), and sample length; the significance bar,
  not the raw SR.
- **Breadth (Fundamental Law):** effective number of independent bets/year;
  `IR ≈ IC × √Breadth`. Correlated instruments reduce effective breadth below the
  raw count — do not over-credit the universe size.

*End of pre-registration. Status UNTESTED. Next action: source Part-E data and
build the Part-D portfolio module (tested on synthetic data first), THEN tune on
IS within the ≤20-config budget, THEN one OOS look.*

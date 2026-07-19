# NYAM-SWEEP-FVG — Master Project Plan & Progress Tracker

**Strategy status: UNTESTED.** No edge is claimed. Numbers come only from our own
backtests, run exactly per Part B of the spec. This file is the single source of
truth for *what is done, what is next, and what must never be skipped.*

Spec: [`docs/spec/NYAM-SWEEP-FVG_v1.0_spec.md`](docs/spec/NYAM-SWEEP-FVG_v1.0_spec.md)

**Legend:** `[ ]` todo · `[~]` in progress · `[x]` done & verified · `[!]` blocked

---

## Guiding rules (never violate — from the spec)

- Status ladder: `UNTESTED → TESTED-FAIL (archive)` or `TESTED-PASS → forward → LIVE-SMALL`. Nothing skips a stage.
- Numbers only from "Every tick / real tick" (MT5) or tick/1m event-driven (Python) backtests **with the B2 cost model**. Zero-cost runs are rejected.
- OOS window is looked at **once per version**. All tuning on IS only.
- ≤ 8 free parameters; optimize ≤ 3 at a time on coarse grids.
- No look-ahead: swings confirm `k` bars late; FVG on bar *i* uses bars *i−2…i*; limit fills require trade-through by ≥ 1 tick.
- Two failed versions of this concept pair on this instrument/session → **archive**, do not torture.

---

## PHASE 0 — Project setup & scaffolding
Goal: a runnable, testable, reproducible skeleton.
- [x] Directory structure (`src/`, `data/`, `tests/`, `reports/`, `config/`, `docs/`, `mql5/`, `pine/`)
- [x] Spec committed under `docs/spec/`
- [x] This roadmap committed
- [ ] `requirements.txt` / Python env pinned
- [ ] Package installable (`pip install -e .`) with `pyproject.toml`
- [ ] Config file encoding the **A6 parameter table + fixed constants** (`config/nyam_sweep_fvg_v1.0.yaml`)
- [ ] Typed config loader (`src/ictbot/config.py`) that validates ranges/caps
- [ ] Test runner wired (`pytest`) + CI-friendly `make test`

## PHASE 1 — Data & time layer (highest-risk foundation)
Goal: correct data and correct time. If time is wrong, every downstream number is garbage (D6 bug #2).
- [x] Data source decided: **Dukascopy** (free tick data)
- [x] Dukascopy downloader written (`data/dukascopy.py`) — [!] **blocked: egress policy 403 on datafeed.dukascopy.com**
- [x] Resampler → ticks→1m/5m and 5m→1H HTF, left-labelled/right-open, no look-ahead (`data/resample.py`)
- [x] **Timezone core**: `to_ny()`, DST-correct via `zoneinfo` (DEF-TIME-01)
- [x] `in_killzone()` NY AM 08:30–11:00, scalar + vectorized (DEF-KZ-01)
- [x] **17:00-NY trading-day boundary** + PDH/PDL computation (`nytime.previous_day_levels`)
- [x] Unit tests: winter/summer killzone + boundary + PDH/PDL (12 tests green)
- [ ] Data validation: ≥ 2 years, ≥ both a high- and low-vol ATR regime present (needs real data)
- [ ] News calendar loader (ForexFactory CSV) joined on timestamp, USD+EUR high-impact (D5)

## PHASE 2 — Core primitives / indicators  ✅
- [x] `ATR(14)` — Wilder RMA, matches MT5 iATR / Pine ta.atr (`indicators/atr.py`)
- [x] `compute_swings(k)` — fractal swings, **confirmed k bars late, never repaint**; per-bar look-ahead-safe `conf_sh/conf_sl` (`indicators/swings.py`, DEF-SWING-01)
- [x] BOS / CHoCH structure state machine (`indicators/structure.py`, DEF-STRUCT-01/02)
- [x] Unit tests against hand-built fixtures (15 tests green total)

## PHASE 3 — Detectors (one function per DEF-ID, D1 map)  ✅
Each: uses only data up to bar *i*, returns bool/zone, has its own unit test.
- [x] `detect_sweep_at(level)` → `Sweep` with `sweep_extreme` (`detectors/sweep.py`, DEF-SWEEP-01)
- [x] `is_displacement(i)` incl. 4.0×ATR news-print reject (`detectors/displacement.py`, DEF-DISP-01)
- [x] `mss_confirmed(dir)` — sweep-window + close-beyond-swing + displacement-leaves-FVG (`detectors/mss.py`, DEF-MSS-01)
- [x] `detect_fvg` + `is_alive` + CE + nested lowest-bull/highest-bear (`detectors/fvg.py`, DEF-FVG-01)
- [x] `htf_bias_series` + `bias_at` (no look-ahead HTF alignment) (`detectors/bias.py`, DEF-BIAS-01)
- [x] `dol_exists(level)` unswept PDH/PDL within 3.0×ATR(1H) (`detectors/dol.py`, DEF-DOL-01)
- [x] `spread_ok()`, `news_clear()` filters (`detectors/filters.py`, A5) — news loader (CSV→event list) still pending
- [x] 11 new unit tests (26 total green)

## PHASE 4 — Strategy engine (A7 state machine)  ✅
- [x] `EngineParams` (points/pips → price distances) + `prepare_features` (all look-ahead-safe inputs)
- [x] Guards block (trades/day, dayR, killzone; reset at 17:00-NY boundary)
- [x] State machine IDLE → SWEPT → WAIT_RETRACE → IN_TRADE, per A7 (`engine/state_machine.py`)
- [x] Entry: limit at CE, trade-through-by-1-tick fill, expiry/killzone-end cancel, **skip if RR-to-TP1 < 1.0**, spread+news gate at fill
- [x] Exits: TP1 (close 50% + SL→BE), TP2 @ PDH/PDL, flat @ 12:00 NY, `max_bars`; conservative stop-first on same-bar ambiguity; mgmt starts next bar (no same-bar entry+exit)
- [x] Account guards: 2 trades/day, −2R daily lock, one-attempt-per-pool/day
- [x] Full short-side mirror (sign-parameterised; verified 1.536R vs long 1.686R)
- [x] Trade record: entry, exit, R, MAE, MFE, reason (5 engine tests; 31 total green)
- [ ] `calc_lots(sl_points, risk_pct)` currency sizing — deferred to Phase 5/8 (R accounting is size-independent)
- Note: costs NOT applied here (gross R); Phase 5 harness wraps with the mandatory cost model.

## PHASE 5 — Backtest harness (B1/B2 + no look-ahead)  ✅
- [x] Event-driven per-5m-bar loop (the engine `run()`, D3)
- [x] **Intrabar fill model** using 1m data — walks sub-bars in time order to resolve SL-vs-TP "which first" (`engine/fills.py IntrabarFillModel`); `BarFillModel` default unchanged
- [x] Fill decisions refactored behind a `FillModel` seam (31 prior tests still green)
- [x] Trade-through-by-1-tick rule for limit fills (in both fill models)
- [x] Cost model in R: spread + $7/lot commission + 0.3 pip slippage (market exits only); `multiplier` for **1.0× and 1.5×** (`backtest/costs.py`)
- [x] IS/OOS chronological split by date (70/30) (`backtest/harness.py split_is_oos`)
- [x] `backtest()` orchestration (features → engine → costs)
- [x] Synthetic 1m smoke: full pipeline runs clean, 0 spurious trades on noise (10 new tests, 41 total)
- [ ] 3-month smoke on REAL data (C1 step 3) — needs data (blocked on egress)

## PHASE 6 — Metrics, gates & Part F reporting  ✅
- [x] All B4 metrics (expectancy, PF, maxDD R & %, win%, avgRR, streak, trades/mo, MAE p90 / MFE median) (`reporting/metrics.py`)
- [x] Six B5 pass gates evaluated automatically (incl. gate 5 stability vs IS PF, gate 6 concentration)
- [x] Monthly net-R table + concentration fraction (gate 6)
- [x] Part F report generator — renders exactly to the spec template (`reporting/report.py`)
- [x] 9 new tests (48 total green); sample report verified visually

## PHASE 7 — Validation & fine-tuning loop (Part C)  — REAL RUN COMPLETE, TESTED-FAIL
- [x] C1 pre-flight (`validation/preflight.py`): time conversion, 17:00 boundary, killzone/PDH-PDL present, no same-bar exit
- [x] C3 bounded IS optimiser (`validation/optimize.py`): ≤3 params + coarse-grid + no-sl_buffer guards enforced in code; select by expectancy, tie-break maxDD; `suggest_sl_buffer_points` from winners' MAE p90
- [x] C4 single OOS look → 6 gates (via `evaluate_gates`, Phase 6)
- [x] B6 robustness (`validation/robustness.py`): ±20% perturb, 1.5× cost, ±15 min session shift, monthly regime table
- [x] `full_validation` driver + `cli.py` (`python -m ictbot.validation.cli`) + CSV/tick loader (`data/load.py`)
- [x] Param mutation helpers on `EngineParams` (`replace`, `clamp_free`, ranges) + `perturb`/`set`/`shift_session`
- [x] 10 new tests (58 total green); driver smoke → TESTED-FAIL on noise as expected
- [x] **C2 baseline + C4 OOS run on REAL data** — ran on EURUSD 2022-2024 (HistData 1m, 3 full years). Found and fixed a real bug: the narrative gate (bias+DOL+shallow-floor) was being re-evaluated every 5m bar with a moving price instead of once at 08:30 NY per spec A2; fixed in `state_machine.py` (all 60 tests still pass, unchanged). After the fix: **0 trades over 3 years** — traced to a structural tension between the fixed `dol_reach_atr_1h=3.0` constant (~44-46 pip reach) and the actual EURUSD PDH-PDL day range (median 66.7 pips), which none of the 7 free parameters can address. Full writeup: `reports/v1.0_2022-2024_run1_findings.md`; machine report: `reports/v1.0_2022-2024_run1.txt`.
- [x] Archive log entry written (C5, in the findings doc) — **decision on next step left to the user** (archive & pick a new instrument/session/concept, deliberately revise the fixed `dol_reach_atr_1h` constant as a new spec version, or reconsider DOL as a hard gate). Not unilaterally resolved — the spec reserves fixed-constant changes for a human decision, not an implementation "fix."

## PHASE 8 — MQL5 EA (forward/live vehicle)  — written ✅ / needs MetaEditor compile + cross-check
- [x] Full A7 state machine ported (`mql5/NYAM_SWEEP_FVG.mq5`), function names match D1
- [x] All detectors: sweep, displacement, FVG(+nested), MSS, confirmed swings, HTF bias/BOS-CHoCH, DOL
- [x] Time layer: `ToNY`, killzone, 17:00-NY boundary, PDH/PDL scan; `ServerToNYOffsetH` verify print on init
- [x] Guards (2/day, −2R lock via deal history, one-attempt-per-pool), `CalcLots` 0.5% sizing
- [x] Limit-at-CE pending order + expiry, TP1 50%+SL→BE, TP2, flat@12:00, max_bars
- [x] `CalendarValueHistory` news filter (USD/EUR high-impact, ±15min)
- [x] README: compile steps, offset verification, real-ticks-only, Python cross-check, known differences
- [x] Structural sanity: braces/parens balanced, all lifecycle + DEF-ID functions present
- [ ] **Compile in MetaEditor** (not possible in this env) + fix any broker-specific issues
- [ ] Cross-check MT5 real-ticks run vs Python numbers (must agree within costs) — needs data + MT5

## PHASE 9 — Pine Script (visual validation only)  ✅
- [x] `pine/NYAM_SWEEP_FVG_visual.pine` — killzone shading, 17:00-NY PDH/PDL, confirmed swings (`ta.pivothigh/low(k,k)`, k bars late), sweeps, displacement/MSS, FVG zones + CE
- [x] Session `"0830-1100"` with `America/New_York` (DST-correct); indicator (not strategy) by design
- [x] `VISUAL ONLY` watermark + README — explicitly not a source of numbers (D4)

## PHASE 10 — Go-live ladder (Part E) — only after TESTED-PASS
- [ ] Forward/demo ≥ 40 trades or 8 weeks (later of the two), expectancy > 0
- [ ] Live 0.25% risk for first 30 trades
- [ ] Scale to 0.5% only if real costs within 25% of model
- [ ] Kill-switch: suspend if live DD > 1.5× backtest maxDD

---

## Current position (NEW PROGRAM: DIVTREND v1.0)
- **Direction chosen by owner (evidence-backed): diversified time-series momentum, vol-scaled, across a 20–40 instrument basket.** Not a patch on the archived price-action work — a fresh signal family (TSMOM: documented edge + high breadth) that fixes all three root causes (directionless signal → real IC; sample-size wall → breadth; cost erosion → monthly low turnover). Evidence: `docs/spec/Redeploy_Direction_Evidence_Report.md`.
- **Pre-registration DONE (before any tuning):** `docs/spec/PREREG_DIVTREND_v1.0.md` — universe, DEF-TSMOM-01 signal, DEF-VOLSCALE-01 sizing, 4 free params, cost-robustness-first gates + a breadth gate + Deflated-Sharpe gate, ≤20-config budget, pre-committed abandonment rule.
- **Honest scope:** the intraday engine does NOT transfer (daily-bar, portfolio-level, cross-sectional = new `src/ictbot/portfolio/` module per Part D); the *discipline* + ~40% of plumbing (config/loading/reporting/tests) does.
- **Two immediate needs:**
  1. **DATA** — ≥24 liquid ETFs, daily adjusted-close, ≥15 years. Egress blocked (Stooq/Yahoo 403), so **user provides CSVs** (Yahoo download per ticker → `data/raw/etf/`), same flow as HistData.
  2. **BUILD** — the Part-D portfolio module, testable on synthetic multi-market data first (as the intraday engine was), no trial budget spent until IS tuning.
- **Next action:** build `src/ictbot/portfolio/` on synthetic data while the ETF CSVs are gathered.

## Prior position (after FVGC — banked the price-action negative)
- **EURUSD-FVGC v1.0 (Direction 2, FVG-continuation): TESTED-FAIL, decisively.** Full 10-year pre-registered run: IS −0.35R / OOS −0.32R, PF 0.61/0.63 — a *robust, out-of-sample-confirmed negative* (IS≈OOS, so not overfit), 3,841 trades so frequency is solved. Fails the PRIMARY cost-robustness gate and 4 of 6 B5 gates. `reports/EURUSD-FVGC_v1.0_findings.md`.
- **Root cause measured, not guessed:** a direct probe (5,174 IS signals) shows fresh-FVG forward returns are **~50/50** (48–49% positive) — the signal is directionless on EURUSD 5m. Momentum doesn't work; reversion is far too weak to beat costs. A ~coin-flip signal at fixed 2:1 RR wins ~33% (break-even) and costs make it a loss.
- **Stage-2 escalation reached → recommendation: BANK THE NEGATIVE.** Two distinct concept families have now failed OOS and the core signal is directionless; ~128 cumulative configs spent. Per the pre-reg rule and the evidence report, continuing to spin EURUSD price-action variants is the sunk-cost error. **The rigorously validated "no edge here" IS the deliverable** — produced by a pipeline that repeatedly refused to ship an overfit. Any further work = genuinely new territory (different instrument/timeframe or non-price-action signal), a fresh research program. **Decision is the user's.**
- 73 tests green. All pushed.

## Earlier position (after full 10-year sweep-family validation)
- **NYAM-ILS-FVG v1.0: TESTED-FAIL out-of-sample** on the full 10-year sample (IS 2015-2021 / OOS 2022-2024, 3.67M 1m bars). Tuned on the fresh 2015-2021 IS only (best cell +0.49R IS), locked, single OOS look on 2022-2024: **OOS expectancy −0.13R, PF 0.79, −0.34R at 1.5× costs; gates 1/2/4/6 fail.** The in-sample edge did not survive out-of-sample (overfit, correctly caught). Full writeup: `reports/NYAM-ILS-FVG_v1.0_findings.md`; machine report: `reports/NYAM-ILS-FVG_v1.0_10y_run.txt`.
- **ARCHIVED — this is the 3rd failed variant of the sweep→MSS→FVG family on EURUSD/NY-AM** (NYAM-SWEEP-FVG v1.0, v2.0; NYAM-ILS-FVG v1.0). Per the spec's own rule ("archived, not tortured until it confesses"), the concept family is done on this instrument/session. A structural frequency floor (~0.65 trades/mo → ~78 lifetime < 100-trade minimum) means it is effectively unvalidatable in this form regardless.
- **Honest overall conclusion:** across 3 designs and 10 years of real data under correct IS/OOS discipline and realistic costs, no durable edge was demonstrated. The system worked — it found and *rejected* an overfit rather than shipping one. That is the correct, valuable outcome. **Decision on any genuinely new direction (different session/concept, still EURUSD) is the user's** — I will not keep patching an archived concept.
- 67 tests green; report label bug fixed (`strategy_name` param). All pushed.

## Earlier position (after v2.0 + ILS pivot)
- **NYAM-SWEEP-FVG is ARCHIVED on EURUSD/NY-AM** after two failed versions (spec C5 entries: `reports/NYAM-SWEEP-FVG_archive.md`):
  - v1.0: 0 trades / 3 years (bias+PDL contradiction; DOL reach vs real ranges).
  - v2.0 (user-authorized spec revision — overnight pool DEF-LIQ-02, free `dol_reach`, leg-extreme TP1; `docs/spec/NYAM-SWEEP-FVG_v2.0_changes.md`): mechanically correct and trading, but IS grid showed n≤2 in every cell — confluence starvation, session-independent (London cross-check n=3).
- **Successor: NYAM-ILS-FVG v1.0** (`docs/spec/NYAM-ILS-FVG_v1.0.md`, `config/nyam_ils_fvg_v1.0.yaml`) — intraday confirmed-swing pools (DEF-LIQ-03), no DOL gate, TP2 = max/min(PDH/PDL, session extreme); engine `pool_mode: swing`. **C2/C3 complete on IS: verdict IS-FAIL** — funnel healthy (558 sweeps → 78 MSS → 42 RR-ok → 11 fills), but best tuned cell is n=22 / expectancy −0.026R / PF 0.96, and *every* cell in two bounded grids is negative after costs. The single OOS look was deliberately **NOT consumed** (running it on a negative-IS version would be theater); the 2024 tail stays sealed.
- **The honest overall finding after three designs on 3 years of real data:** the sweep→MSS→FVG family on EURUSD trades ~0.9/month at realistic definitions and shows no positive expectancy in-sample at honest costs. The machinery is correct (67 tests, hand-verified R, staged funnel instrumentation); the data has simply not shown an edge yet.
- **User action needed:** 2015–2021 HistData yearly files (same download procedure). That gives a fresh 7-year IS untouched by any of this iteration, with 2022–2024 as a clean OOS for a frozen design — the only statistically honest next step. If long-IS is also flat → archive the family on EURUSD.
- All work pushed to `claude/ready-to-start-work-m5uwbq`.

## Previous position (v1.0 first real run)
- **The real validation run happened.** User supplied EURUSD 2022-2024 1-minute data (HistData.com). Ran C1 pre-flight (green) → found and fixed a genuine engine bug (DOL narrative gate was re-evaluated every bar instead of once at 08:30 NY per spec A2) → re-ran → **0 trades over 3 years**, traced to a structural tension between the fixed `dol_reach_atr_1h=3.0` constant and real EURUSD range statistics, not addressable by any of the 7 free parameters. **Status: TESTED-FAIL (insufficient sample).** Full findings: `reports/v1.0_2022-2024_run1_findings.md`. Data lives in `data/raw/EURUSD_M1_histdata/` (source documented in `SOURCE.md`); loader `ictbot.data.load.load_histdata_ascii_m1` handles HistData's fixed-GMT-5 (no-DST) timestamp convention. **60 tests green.**
- **Decision needed from the user** (deliberately not made unilaterally — the spec reserves fixed-constant changes for a human): archive this concept pair and start a new v1.0 hypothesis on a different instrument/session/concept (per spec C4 step 12), or consciously revise the fixed `dol_reach_atr_1h` constant as a new documented spec version, or reconsider DOL as a hard gate. See the findings doc's "Options" section.
- Phase 8 (MQL5 EA) still needs a MetaEditor compile + cross-check against Python. Phase 10 (go-live) stays gated on an eventual TESTED-PASS.
- Dukascopy egress is still blocked, but is now moot — HistData supplied the real dataset.
- **Next action:** wait on the user's decision above before writing any v1.1 or new hypothesis.

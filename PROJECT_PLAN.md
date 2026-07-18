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

## PHASE 6 — Metrics, gates & Part F reporting
- [ ] All B4 metrics (R, win%, avgRR, expectancy, PF, maxDD in R & %, streak, trades/mo, MAE/MFE)
- [ ] Six B5 pass gates evaluated automatically
- [ ] Monthly net-R concentration table (gate 6)
- [ ] Part F report generator (paste-ready)

## PHASE 7 — Validation & fine-tuning loop (Part C)
- [ ] C1 pre-flight (time, day-boundary, smoke) all green
- [ ] C2 baseline IS run at defaults + MAE/MFE distribution
- [ ] C3 bounded IS optimization (≤3 params, coarse grid; `sl_buffer` from MAE p90, not grid)
- [ ] C4 single OOS look → evaluate 6 gates
- [ ] B6 robustness: ±20% perturb, 1.5× cost, ±15 min session shift, monthly regime table
- [ ] Archive log entry if FAIL (C5); iterate to v1.1 with **one** change if warranted

## PHASE 8 — MQL5 EA (forward/live vehicle)
- [ ] Port A7 state machine to the D2 skeleton, function names matching D1
- [ ] `CalendarValueHistory` news filter (D5)
- [ ] `ServerToNYOffsetH` verification harness (never hardcode)
- [ ] Cross-check MT5 "real ticks" run vs Python numbers (must agree within costs)

## PHASE 9 — Pine Script (visual validation only)
- [ ] `ta.pivothigh/low(k,k)`, session `"0830-1100"` NY — eyeball signal placement (D4)
- [ ] Explicitly not a source of numbers

## PHASE 10 — Go-live ladder (Part E) — only after TESTED-PASS
- [ ] Forward/demo ≥ 40 trades or 8 weeks (later of the two), expectancy > 0
- [ ] Live 0.25% risk for first 30 trades
- [ ] Scale to 0.5% only if real costs within 25% of model
- [ ] Kill-switch: suspend if live DD > 1.5× backtest maxDD

---

## Current position
- **Active phase:** Phases 0–5 done (scaffold, time/data, indicators, detectors, engine, harness). The full backtest pipeline runs end-to-end on synthetic 1m data. Moving to Phase 6 (metrics, gates, Part F report).
- **Open blocker (environment/policy):**
  - **Dukascopy egress → 403** — session network policy blocks `datafeed.dukascopy.com`. Everything is built and unit-tested on synthetic data; producing the *actual reportable numbers* (Phases 6–7) needs real tick/1m data: open the network policy, run the downloader elsewhere, or drop CSVs into `data/raw`.
- **Next action:** Phase 6 — all B4 metrics + the six B5 pass-gates + monthly concentration table + the paste-ready Part F report generator (buildable now; validated against synthetic/fixture trades, then run for real once data lands).

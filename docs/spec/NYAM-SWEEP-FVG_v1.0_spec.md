# NYAM-SWEEP-FVG v1.0 — Complete ICT Trading Bot System

**Engineering documentation for an untested hypothesis. Not financial advice.**

---

## READ THIS FIRST — What "Working" Means in This System

1. **No win rate, return, or edge is stated or implied anywhere in this document.** Performance numbers may only come from your own backtest results, produced under Part B and reported via Part F.
2. **Status ladder:** `UNTESTED → TESTED-FAIL (archive)` or `TESTED-PASS → forward test → LIVE-SMALL`. Nothing skips a stage. Current status: **UNTESTED**.
3. **"Fine-tune until it works" is bounded.** Tuning happens only inside the Parameter Table (Section A6), within the stated test ranges, one version at a time (v1.0 → v1.1 → v1.2). Two failed versions of this concept pair on this instrument/session → the pair is **archived**, and the next hypothesis starts fresh at v1.0. A strategy that fails its gates gets archived, not tortured until it confesses.
4. **Definition of done ("working"):** all six pass gates hold on out-of-sample data (B5) AND all four robustness checks pass (B6) AND the forward test stays positive (Part E). Nothing else counts.

**How to use this document:**
- Hand **Part A + Part D** to implementation (EA / backtester).
- Run the tests exactly per **Part B**.
- Iterate exactly per **Part C**.
- Graduate to live exactly per **Part E**.
- Report every run in the **Part F** template.
- **Appendix 1** contains every quantified definition (DEF-ID) referenced, so this file is self-contained.

---

# PART A — STRATEGY SPECIFICATION

## A0. Strategy ID Card

| Field | Value |
|---|---|
| Name | NYAM-SWEEP-FVG |
| Version | v1.0 |
| Instrument | EURUSD |
| Direction | Both (long rules shown; short fully mirrored) |
| Trigger concepts (2/2 cap) | DEF-SWEEP-01 (liquidity sweep) + DEF-FVG-01 (fair value gap entry) |
| Context filters (do not count toward cap) | DEF-KZ-01 (NY AM killzone), DEF-BIAS-01 (HTF order flow), DEF-DOL-01 (draw on liquidity), DEF-MSS-01 (sequence gate inside the sweep→shift structure), news filter, spread filter |
| Target platform | MQL5 (MetaTrader 5) · Python harness for research backtests |
| Status | UNTESTED |
| Date | 2026-07-17 |

## A1. Time & Price Matrix

- **Killzone:** NY AM, **08:30–11:00 New York time** = 13:30–16:00 UTC (winter, NY=UTC−5) / 12:30–15:00 UTC (summer, NY=UTC−4). Setups may only FORM and FILL inside this window.
- **HTF = 1H** (narrative) · **LTF = 5m** (execution).
- **Trading-day boundary = 17:00 NY** (PDH/PDL are computed on this boundary, NOT calendar-UTC days).
- **Server time:** expose input `ServerToNYOffsetH` {default 7}. Most MT5 brokers run UTC+2/UTC+3 synchronized to US DST so that 17:00 NY = 00:00 server, making the offset 7h year-round — but this MUST be verified against one known session open before the first run (DEF-TIME-01). Never hardcode.

## A2. The Narrative (HTF Setup) — all three must be TRUE at 08:30 NY

- **N1 — Bias:** DEF-BIAS-01 on 1H ≠ NEUTRAL. Longs require BULLISH; shorts require BEARISH.
- **N2 — Target exists:** DEF-DOL-01 — an **unswept PDH** (for longs) within **3.0 × ATR(1H, 14)** of current price. No draw on liquidity within reach → no trade today.
- **N3 — Fuel exists:** the opposing pool **PDL** (for longs) has **NOT** been swept since 17:00 NY. Already swept overnight → stand down (the manipulation leg already happened).

Short side: mirror (target = unswept PDL within reach; fuel = PDH unswept).

## A3. The Trigger (LTF 5m Entry Rules) — strict sequence A → B → C

- **Condition A (Sweep):** DEF-SWEEP-01 of PDL — wick trades ≥ 1 tick below PDL, then a 5m candle **closes back above PDL** within `sweep_close_n` {3} candles of first penetration. Record `sweep_extreme` = lowest price reached. No close-back within the window → classify as breakout, setup VOID.
- **Condition B (Shift):** within `mss_window` {12} candles of A, DEF-MSS-01 bullish — a 5m candle **closes above** the most recent confirmed swing high (swing_k = 1 on LTF), where the breaking move satisfies DEF-DISP-01 (summed body of ≤ 3 consecutive same-direction candles ≥ `disp_mult` {1.5} × ATR(14, 5m)) and leaves ≥ 1 valid DEF-FVG-01 (gap height ≥ `fvg_min` {0.5} × ATR and ≤ 3.0 × ATR). If the displacement leaves multiple valid FVGs: take the **LOWEST** bullish gap (nested-FVG rule).
- **Condition C (Return):** place a **limit order at the FVG's CE** (50% midpoint of the gap) per DEF-ENTRY-01. The order expires after `expiry_bars` {15} five-minute candles, at 11:00 NY, or if price reaches the TP1 level before filling — whichever comes first.
- **Action:** limit fill = position open. **Skip the trade at order-placement time if RR to TP1 < 1.0**, computed with the exact SL from A4.

Short side: sweep of PDH → MSS bearish (close below most recent confirmed swing low) → HIGHEST bearish FVG → limit at CE.

## A4. Risk Management (Invalidation & Targets)

- **SL:** `sweep_extreme` − `sl_buffer` {2 points} for longs (mirrored above for shorts). Never widened, never moved except by the break-even rule below.
- **Position size:** `lots = (equity × 0.5%) / (SL_distance_in_points × point_value)`. Risk fixed at **0.5% of equity per trade**. Trade-level risk without account-level sizing is not risk management — the formula is mandatory in code.
- **TP1 (internal liquidity):** the swing high whose break confirmed Condition B. On TP1 fill: **close 50%** of the position (fixed), **move SL to entry** (break-even rule — mechanical, no discretion).
- **TP2 (external liquidity):** PDH — the DEF-DOL-01 target. Close the remainder.
- **Time exits:** hard **flat at 12:00 NY** (fixed); maximum holding time `max_bars` = 42 five-minute candles (3.5 h) — redundant guard, fixed.
- **Account guards (all fixed):**
  - Max **2 trades/day**.
  - **Daily loss stop at −2R** — no new entries after it is hit; counter resets on the 17:00-NY boundary, not server midnight.
  - **One open position** per instrument at a time.
  - **Re-entry policy:** NO re-entry after a stop-out on the same swept pool that day. One attempt per pool per day.

## A5. Edge Cases & Filtering — do NOT enter when any is TRUE

1. **News:** high-impact event for USD or EUR within **±15 min** of entry time. Calendar source: MQL5 economic calendar (live) / ForexFactory historical CSV (backtests). Open positions are NOT auto-flattened for news ({news_flat = false}).
2. **Spread:** spread at order placement > **1.2 pips** (fixed).
3. **Oversized displacement:** displacement candle body > **4.0 × ATR(14, 5m)** → reject the setup (news-print behavior, DEF-DISP-01 upper bound, fixed).
4. **FVG size band:** gap outside **[fvg_min, 3.0] × ATR** → not a valid entry array (min is a parameter, max fixed).
5. **Shallow sweep floor:** PDL sits < **5 points** below the 08:30 NY open → skip (fixed floor; the sweep would be too shallow to anchor an SL).
6. **Friday cutoff:** no new entries after 11:00 NY Friday (killzone end already enforces this; stated for clarity).
7. **DST-transition weeks** (2 per year): tradeable ({dst_week_trade = true}, fixed), but tag every trade in those weeks in the journal for review.

## A6. Parameter Table — 7 free parameters (cap = 8)

| # | Parameter | Default | Test range | DEF-ID |
|---|---|---|---|---|
| 1 | `sweep_close_n` | 3 | 1–5 | DEF-SWEEP-01 |
| 2 | `mss_window` | 12 | 6–20 | DEF-MSS-01 |
| 3 | `disp_mult` | 1.5 | 1.0–2.5 | DEF-DISP-01 |
| 4 | `fvg_min` (×ATR) | 0.5 | 0.3–1.0 | DEF-FVG-01 |
| 5 | `expiry_bars` | 15 | 8–24 | DEF-ENTRY-01 |
| 6 | `sl_buffer` (points) | 2 | 0–10 | SL anchor |
| 7 | `ServerToNYOffsetH` | 7 | broker-verified, **never optimized** | DEF-TIME-01 |

**Fixed constants (not optimized, not free):** `swing_k` = 1 (LTF) / 2 (HTF) · `atr_len` = 14 · `fvg_max` = 3.0 × ATR · `sweep_penetration` = 1 tick · `entry_level` = CE · partial close = 50% · risk = 0.5% · `max_trades` = 2/day · `daily_stop` = 2R · flat time = 12:00 NY · `max_bars` = 42 · news window = ±15 min · `news_flat` = false · `max_spread` = 1.2 pips · shallow-sweep floor = 5 points · `dol_reach` = 3.0 × ATR(1H) · `dst_week_trade` = true.

## A7. Pseudocode (canonical state machine — function names per Part D map)

```
every new 5m bar:
  guards (before any state logic):
    trades_today < 2  AND  dayR > -2.0  AND  no_open_position
    AND in_killzone(t) AND spread_ok() AND news_clear()
    (daily counters reset at 17:00 NY boundary)

  IDLE:
    if htf_bias() == BULL and dol_exists(PDH) and !swept_today(PDL)
       and sweep_detected(PDL):
         save sweep_extreme; bars = 0  -> SWEPT

  SWEPT:
    bars++
    if bars > mss_window                          -> IDLE   // sweep stale
    if mss_confirmed(BULL):
         zone = lowest_fvg()                                // nested-FVG rule
         if fvg_ok(zone)                          -> WAIT_RETRACE

  WAIT_RETRACE:
    bars2++
    if bars2 > expiry_bars or t >= 11:00 NY: cancel order -> IDLE
    ensure limit order at CE(zone)   // skip if RR_to_TP1 < 1.0
    if price reaches TP1 level before fill: cancel        -> IDLE
    on fill                                        -> IN_TRADE

  IN_TRADE:
    TP1 @ broken_swing_high: close 50%, SL -> entry
    exit on: TP2 @ PDH | SL | flat @ 12:00 NY | max_bars
    on close: log entry, exit, R, MAE, MFE; trades_today++;
              update dayR; check daily_stop        -> IDLE (or LOCKED for day)

(short side: mirror every comparison — sweep PDH, MSS bearish,
 HIGHEST bearish FVG, SL above sweep_extreme + sl_buffer,
 TP1 = broken swing low, TP2 = PDL)
```

## A8. Validation Gates (binding — restated from Part B)

- **Data:** tick or 1-minute data, ≥ 2 full years, ≥ 100 total trades, MT5 mode = "Every tick based on real ticks" only.
- **Costs:** 75th-percentile session spread (EURUSD NY AM ≈ 0.6–1.0 pip), $7/lot round-turn commission, 0.3 pip slippage on market-side executions; limit fills require price to trade THROUGH the level by ≥ 1 tick. Re-run the final result at **1.5× costs**.
- **Split:** 70% in-sample / 30% out-of-sample, chronological. All tuning on IS only. OOS is looked at ONCE per version.
- **PASS requires — all six, on the OOS window:**
  1. Expectancy ≥ **0.15 R** per trade
  2. Profit factor ≥ **1.3**
  3. Max drawdown ≤ **12 R**
  4. OOS trade count ≥ **30**
  5. OOS PF ≥ **0.6 × IS PF** (large IS→OOS decay = overfit)
  6. No single month > **40%** of total net R
- Then robustness: parameter perturbation ±20%, session shift ±15 min, cost-stress at 1.5×, month-by-month regime table (Part B6).

**Status: UNTESTED. No performance expectation is stated or implied until results are reported against this protocol.**

---

# PART B — BACKTESTING & VALIDATION PROTOCOL

The purpose of this protocol is to make it hard to fool yourself. Most ICT strategies that look profitable on a screenshot die under proper data, proper costs, and out-of-sample testing.

## B1. Data Requirements

- Execution TF is 5m → **tick data or, at minimum, 1-minute data is mandatory.** Sweeps, FVG taps, and SL-vs-TP "which came first" live inside 5m candles; 5m OHLC alone misrepresents fills.
- MT5: **"Every tick based on real ticks"** mode only. Reject any result produced with "Open prices only" or "1 minute OHLC" modes.
- Independent tick sources (e.g., Dukascopy exports) are acceptable — document the source in every report.
- **Minimum history: 2 full years**, and the window must include at least one high-volatility and one low-volatility regime (check the ATR percentile range across the window; if the whole window sits in one volatility quartile, extend it).

## B2. Costs Model (mandatory — zero-cost backtests are rejected)

| Cost | Assumption | Note |
|---|---|---|
| Spread | Variable if data supports it; else fixed at the pair's 75th-percentile session spread (EURUSD NY AM ≈ 0.6–1.0 pip) | Session-specific: Asian spreads ≠ NY spreads |
| Commission | $7 per lot round-turn (raw-spread account model) | Set 0 only if modeling a spread-markup account |
| Slippage | 0.3 pip per market execution side; 0 on limit fills, BUT a limit only counts as filled if price trades **through** it by ≥ 1 tick | The trade-through rule kills phantom fills at wick extremes |
| Swap | Not required — strategy is flat by 12:00 NY | Include only if a rule ever changes to hold past 17:00 NY |

Run every final result twice: at **1.0×** and **1.5×** assumed costs. If the edge dies at 1.5×, it is a costs artifact, not an edge.

## B3. Sample Size & Splits

- Minimum **100 total trades** AND **2 years** — whichever demands more data wins.
- **70% in-sample (IS) / 30% out-of-sample (OOS), chronological.** Never random-shuffle a time series.
- All parameter tuning happens on IS only. **OOS is looked at ONCE per strategy version.** Repeated OOS peeking converts OOS into IS — if another iteration is needed, reserve a NEW, later OOS window (walk-forward: rolling 6-month train / 2-month test).
- Minimum **30 trades in the OOS window** for the gates to mean anything.

## B4. Metrics (compute exactly these, exactly this way)

- **R** = initial risk per trade (entry→SL distance × size). All results reported in R, not currency.
- **Win rate** = winners / total closed trades.
- **Average RR** = mean(winner profit in R) / mean(|loser loss in R|).
- **Expectancy (R)** = (win_rate × avg_win_R) − (loss_rate × avg_loss_R). *The single most important number.*
- **Profit Factor (PF)** = gross profit / gross loss.
- **Max drawdown** = worst peak-to-trough, reported in R AND in % at 0.5% risk per trade.
- **Longest losing streak** (count) — sets sizing and psychological expectations.
- **Trades/month** — an edge that fires twice a quarter cannot be evaluated or compounded.
- **MAE / MFE** per trade (maximum adverse / favorable excursion) — the ONLY legitimate evidence base for tuning `sl_buffer` and TP placement in later versions.

## B5. Pass Gates

A version **PASSES** only if ALL six hold on the OOS window:

| # | Gate | Threshold |
|---|---|---|
| 1 | Expectancy | ≥ 0.15 R / trade |
| 2 | Profit factor | ≥ 1.3 |
| 3 | Max drawdown | ≤ 12 R |
| 4 | OOS trades | ≥ 30 |
| 5 | Stability | OOS PF ≥ 0.6 × IS PF |
| 6 | Concentration | no month > 40% of net R |

Fail any gate → status **TESTED-FAIL** for that version. **Two failed versions of the same concept pair → archive the concept pair on this instrument/session.** That recommendation is written plainly, not softened.

## B6. Robustness Checks (run after gates pass, before forward test)

1. **Parameter perturbation:** shift each free parameter ±20%, one at a time. If expectancy flips negative on any single perturbation → knife-edge fit → FAIL.
2. **Cost stress:** the 1.5× costs run must keep expectancy > 0.
3. **Session shift:** move the killzone ±15 minutes. Real session effects degrade gracefully; curve-fits collapse.
4. **Month-by-month table:** inspect for regime dependence. Note (don't necessarily fail) if all profit comes from one volatility regime.

## B7. Anti-Overfitting Rules (enforced at spec time, not just test time)

- ≤ 8 free parameters per strategy (this spec uses 7).
- Optimize **≤ 3 parameters at a time**, coarse grids (3–5 values each), never exhaustive fine grids.
- **Never optimize `sl_buffer` and `entry_level` in the same pass** — they interact. `entry_level` is fixed at CE in v1.0; `sl_buffer` is set from MAE data, not grid search.
- Version every change: v1.0 → v1.1 = parameter change. **A new concept = a new strategy at v1.0** — never bolt a third trigger concept onto this one to "rescue" it.
- Keep the archive log (Part C5). Failed hypotheses are data; re-testing an archived idea without new reasoning is how weeks disappear.

---

# PART C — FINE-TUNING LOOP (Refinement Discipline)

This is the iteration procedure. Follow it in order; do not improvise between steps.

## C1. Pre-Flight (before any test run)

1. **Verify time handling first.** Print the NY-time conversion of one known session open (e.g., confirm 08:30 NY maps to the expected server bar). Wrong `ServerToNYOffsetH` is the single most common bug in ICT EAs — every downstream number is garbage if this is wrong.
2. **Verify day-boundary logic:** PDH/PDL computed on the 17:00→17:00 NY day; daily counters (`trades_today`, `dayR`) reset at 17:00 NY, not server midnight.
3. **Smoke test:** run 3 months of data. Confirm in the logs: swings confirm `k` bars late (no repainting), state transitions follow A7 exactly, no same-bar entry+exit fills, limit fills require trade-through by ≥ 1 tick.

## C2. Baseline Run

4. Run the **IS window (first 70%)** at all defaults. Record the full Part B4 metric set plus the MAE/MFE distribution per trade.
5. **Sanity check trade frequency:** target ≥ ~4 trades/month (100 trades ÷ 24 months). If frequency is far below this, the only levers are the frequency-governing parameters — `mss_window`, `fvg_min`, `expiry_bars` — within their stated ranges. Do not widen ranges to manufacture trades.

## C3. IS Optimization Pass (one pass, bounded)

6. Choose **≤ 3 parameters**, coarse grid of 3–5 values each, from the Section A6 ranges only. Recommended first pass: `disp_mult` × `fvg_min` × `expiry_bars`.
7. `sl_buffer` is NOT grid-searched. Set it from evidence: place the SL beyond the 90th-percentile MAE of winning IS trades, rounded to a value inside the 0–10 point range, then re-verify the IS result once.
8. Select the parameter cell by **expectancy**, tie-broken by max drawdown — not by net profit (net profit rewards over-trading).

## C4. The OOS Gate (one look)

9. **Lock parameters. Run the OOS window (last 30%) exactly once.** Evaluate all six B5 gates.
10. **PASS →** run all four B6 robustness checks. All pass → status **TESTED-PASS** → proceed to Part E forward test.
11. **FAIL →** create **v1.1** with **at most ONE parameter-table change**, justified in writing by the MAE/MFE data or the monthly table — not by vibes. Because OOS was already seen, v1.1 must be judged on a **new, later OOS window** (walk-forward: 6-month train / 2-month test rolling forward).
12. **v1.1 also fails → ARCHIVE** NYAM-SWEEP-FVG on EURUSD/NY-AM. Write the archive entry (C5). The next attempt is a NEW strategy at v1.0 — different instrument (e.g., GBPUSD), different session (e.g., London 02:00–05:00 NY time), or a different ≤2-concept trigger (e.g., breaker-block model) — never a third concept stacked on this one.

## C5. Archive Log (append one entry per failed version)

```
[date] | strategy vX.Y | instrument/session | window tested
Gates failed: <#s>   Key numbers: exp= PF= maxDD= oosN=
Diagnosis (from data, one line):
Decision: iterate (v-next, single change = ...) / ARCHIVE
```

## C6. Standing Prohibitions

- Never tune on OOS data. Never peek twice at the same OOS window.
- Never exceed the A6 test ranges.
- Never add a trigger concept to an existing strategy.
- Never compare versions on different data windows or different cost models.
- Never report or act on results produced without the B2 costs model.

---

# PART D — IMPLEMENTATION ARCHITECTURE

One architecture, many parameter sets: every strategy compiles to the same state machine; only detector functions and parameters change. This keeps EAs comparable and debuggable, and lets the backtest harness be reused.

## D1. DEF-ID → Function Name Map (names must match across spec, EA, and backtester)

| DEF-ID | Function |
|---|---|
| DEF-SWING-01 | `get_swings(k)` |
| DEF-SWEEP-01 | `sweep_detected(level)` → stores `sweep_extreme` |
| DEF-DISP-01 | `is_displacement(i)` |
| DEF-MSS-01 | `mss_confirmed(dir)` |
| DEF-FVG-01 | `detect_fvg(i)` / `fvg_alive(zone)` |
| DEF-BIAS-01 | `htf_bias()` |
| DEF-DOL-01 | `dol_exists(level)` |
| DEF-KZ-01 / TIME-01 | `in_killzone(t)`, `to_ny_time(t)` |
| DEF-ENTRY-01 | `place_tap_limit(zone)` |
| Risk formula | `calc_lots(sl_points, risk_pct)` |

## D2. MQL5 EA Skeleton (MetaTrader 5)

```mql5
//+------------------------------------------------------------------+
//| NYAM-SWEEP-FVG v1.0 — generated from spec. New-bar logic only.   |
//+------------------------------------------------------------------+
#include <Trade/Trade.mqh>
CTrade trade;

//--- Parameter table (Section A6) maps 1:1 to inputs
input double RiskPct            = 0.5;    // % equity per trade (fixed constant)
input int    ServerToNYOffsetH  = 7;      // VERIFY per broker (DEF-TIME-01)
input int    KZStartHH=8, KZStartMM=30, KZEndHH=11, KZEndMM=0; // NY time
input int    SwingK             = 1;      // DEF-SWING-01 (LTF)
input int    SweepCloseN        = 3;      // DEF-SWEEP-01
input int    MssWindow          = 12;     // DEF-MSS-01
input double DispMult           = 1.5;    // DEF-DISP-01
input double FvgMinATR          = 0.5;    // DEF-FVG-01
input double FvgMaxATR          = 3.0;    // fixed
input int    ExpiryBars         = 15;     // DEF-ENTRY-01
input double SlBufferPts        = 2;      // added beyond sweep_extreme
input int    MaxTradesPerDay    = 2;
input double DailyStopR         = 2.0;
input int    NewsBlockMin       = 15;     // ± around high-impact USD/EUR
input double MaxSpreadPips      = 1.2;

int      atrHandle;
enum SetupState {IDLE, SWEPT, WAIT_RETRACE, IN_TRADE};
SetupState state = IDLE;
double   sweepExtreme=0, fvgTop=0, fvgBot=0;
int      barsSince=0, bars2=0, tradesToday=0; double dayR=0;

int OnInit(){ atrHandle=iATR(_Symbol,_Period,14); return INIT_SUCCEEDED; }

datetime ToNY(datetime srv){ return srv - ServerToNYOffsetH*3600; }

bool InKillzone(datetime srv){
   MqlDateTime ny; TimeToStruct(ToNY(srv), ny);
   int m = ny.hour*60 + ny.min;
   return m >= KZStartHH*60+KZStartMM && m < KZEndHH*60+KZEndMM;
}

bool NewBar(){ static datetime last=0; datetime t=iTime(_Symbol,_Period,0);
   if(t==last) return false; last=t; return true; }

double CalcLots(double slPoints){
   double tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSz  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double riskCash= AccountInfoDouble(ACCOUNT_EQUITY)*RiskPct/100.0;
   double lots    = riskCash / (slPoints*_Point/tickSz*tickVal);
   return NormalizeDouble(MathMax(lots, SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN)), 2);
}

// Detector functions — implement EXACTLY per Appendix 1 definitions:
// bool SweepDetected();   // DEF-SWEEP-01: penetration + close-back + records sweepExtreme
// bool MssConfirmed();    // DEF-MSS-01: close beyond swing + displacement + leaves FVG
// bool DetectFVG();       // DEF-FVG-01: 3-candle gap + size band + lowest/highest rule
// bool FvgAlive();        // fill-state tracking (dead at 100% fill)
// bool HtfBias();         // DEF-BIAS-01 on 1H series
// bool DolExists();       // DEF-DOL-01: unswept PDH/PDL within 3.0×ATR(1H)
// bool SpreadOK();        // current spread <= MaxSpreadPips
// bool NewsClear();       // CalendarValueHistory, USD+EUR, importance=high, ±NewsBlockMin

void OnTick(){
   if(!NewBar()) return;
   // guards: tradesToday < MaxTradesPerDay, dayR > -DailyStopR,
   //         one open position, InKillzone, SpreadOK, NewsClear
   // then run the A7 state machine verbatim.
   // Reset tradesToday/dayR on the 17:00-NY boundary, NOT server midnight.
}
```

**Backtest this EA only in "Every tick based on real ticks" mode.**

## D3. Python Backtest Harness Skeleton (pandas, event-driven per LTF bar)

```python
from zoneinfo import ZoneInfo
import pandas as pd

NY = ZoneInfo("America/New_York")
P = dict(swing_k=1, sweep_close_n=3, mss_window=12, disp_mult=1.5,
         fvg_min=0.5, fvg_max=3.0, expiry_bars=15, sl_buffer=0.00002,
         risk_pct=0.005, kz=("08:30", "11:00"), flat=("12:00"),
         max_trades=2, daily_stop_R=2.0, max_bars=42)

def in_killzone(ts_utc):                      # DEF-KZ-01 / DEF-TIME-01
    t = ts_utc.tz_convert(NY).time()
    lo, hi = (pd.Timestamp(x).time() for x in P["kz"])
    return lo <= t < hi

# Detectors — one function per DEF-ID (D1 map). Each takes df + index i,
# uses ONLY data up to and including bar i (no look-ahead), returns bool/zone:
# get_swings, sweep_detected, is_displacement, mss_confirmed,
# detect_fvg, fvg_alive, htf_bias, dol_exists

def run(df):                                  # df: UTC-indexed OHLCV, 5m
    state, trades = "IDLE", []
    for i in range(50, len(df)):
        # guards -> A7 state machine verbatim
        ...
    return pd.DataFrame(trades)               # entry, exit, R, MAE, MFE

def report(tr):
    e  = tr.R.mean()
    pf = tr.R[tr.R > 0].sum() / abs(tr.R[tr.R < 0].sum())
    dd = (tr.R.cumsum().cummax() - tr.R.cumsum()).max()
    print(f"n={len(tr)} exp={e:.2f}R PF={pf:.2f} maxDD={dd:.1f}R "
          f"win%={(tr.R > 0).mean():.1%}")
    # print IS and OOS blocks separately (chronological date split)
```

**Look-ahead rules (non-negotiable):** swings confirm `k` bars late; the FVG on bar *i* uses bars *i−2…i*; fills are modeled with next-bar or intrabar 1-minute data, never a same-bar close; a limit counts as filled only if price trades through it by ≥ 1 tick.

## D4. Pine Script v5 (visual validation only)

Use TradingView/Pine only to eyeball signal placement against the chart (`ta.pivothigh/low(k,k)` confirms k bars late — matches DEF-SWING-01; session string `"0830-1100"` with `"America/New_York"`). Pine's LTF fill assumptions are optimistic — **numbers come from MT5/Python only.**

## D5. News Filter Implementation

- **Live / MQL5:** `CalendarValueHistory` filtered to USD + EUR, importance = high; block NEW entries within ±15 min. Open positions are not flattened (`news_flat = false`).
- **Backtests:** historical calendar CSV (e.g., exported ForexFactory data) joined on timestamp, same ±window. State the source in every report — an untestable filter is a discretionary filter.

## D6. Known Bug Traps (check each explicitly during C1 smoke test)

1. Repainting swings (acting on unconfirmed pivots) — backtests look great, trades terribly.
2. Wrong `ServerToNYOffsetH` — every killzone and every PDH/PDL is wrong.
3. PDH/PDL on calendar-UTC days instead of the 17:00→17:00 NY day.
4. Daily counters reset at server midnight instead of 17:00 NY.
5. Same-bar SL/TP ambiguity resolved optimistically — requires tick/1m data.
6. Phantom limit fills at wick extremes — enforce the trade-through-by-1-tick rule.
7. "Open prices only" backtest mode — reject all such results.

---

# PART E — GO-LIVE LADDER

1. **TESTED-PASS → demo/forward test:** ≥ **40 trades** or **8 weeks**, whichever is LATER, at locked parameters. Forward expectancy must stay > 0.
2. **Live at 0.25% risk** for the first **30 trades** regardless of backtest quality — execution reality check (fills, spread, platform bugs).
3. **Scale to spec risk (0.5%)** only after the probation sample confirms real costs and slippage within 25% of the modeled values.
4. **Standing kill-switch:** the strategy is suspended immediately if live drawdown exceeds **1.5× the backtest max drawdown (in R)**. Suspension → back to Part C with the live data as evidence.

---

# PART F — REPORTING TEMPLATE (paste this back after every run)

```
Strategy: NYAM-SWEEP-FVG vX.Y   Instrument/Session: EURUSD / NY AM
Window: <dates>   Data: <tick|1m, source>   MT5 mode: <real ticks?>
Costs: spread=      commission=      slippage=      (1.0x / 1.5x run?)

IS : trades=   win%=   avgRR=   expectancy(R)=   PF=   maxDD(R)=   streak=
OOS: trades=   win%=   avgRR=   expectancy(R)=   PF=   maxDD(R)=   streak=
Trades/month =        MAE p90 (winners) =        MFE median =

Monthly net R table: <12+ rows>

Gates: 1[ ] 2[ ] 3[ ] 4[ ] 5[ ] 6[ ]   ->  PASS / FAIL
Robustness (if gates passed): perturb[ ] cost1.5x[ ] session±15[ ] monthly[ ]
```

Evaluation of every report is strict against the gates; each iteration proposes **at most one parameter-table change**, justified by MAE/MFE or the monthly table; the strategy's status is restated every time.

---

# APPENDIX 1 — QUANTIFIED DEFINITIONS USED (self-contained vocabulary)

**DEF-SWING-01 — Swing High/Low (fractal).** Swing High = candle whose high is strictly greater than the highs of `k` candles on each side (Swing Low mirrored). `swing_k` = 1 on LTF (fast internal structure), 2 on HTF. A swing is only CONFIRMED `k` candles after it forms — code must never act on unconfirmed swings.

**DEF-STRUCT-01 — Break of Structure (BOS).** In an uptrend state, a candle CLOSE (not wick) above the most recent confirmed Swing High = bullish BOS. Mirrored for downtrend. Wick-only breaks are sweeps, not structure breaks — this close-vs-wick distinction is the entire difference between "structure shifted" and "liquidity taken."

**DEF-STRUCT-02 — Change of Character (CHoCH).** The FIRST close beyond the most recent opposite swing against the prevailing structure state. Flips the structure state.

**DEF-DISP-01 — Displacement.** A single candle, or run of ≤ 3 consecutive same-direction candles, whose summed body size (|close − open|) ≥ `disp_mult` × ATR(14) on the working timeframe, AND which leaves at least one DEF-FVG-01 behind. Upper bound: body > 4.0 × ATR → reject (news-print behavior with untradeable retracements).

**DEF-MSS-01 — Market Structure Shift (with displacement).** ALL must be true: (1) a DEF-SWEEP-01 occurred within the last `mss_window` LTF candles; (2) a candle CLOSES beyond the most recent opposite confirmed swing (swing_k = 1 allowed for speed); (3) the breaking move qualifies as DEF-DISP-01 (i.e., it leaves an FVG).

**DEF-LIQ-01 — Liquidity pools used here.** PDH/PDL = high/low of the previous trading day, where the trading day runs **17:00–17:00 New York time** (a calendar-UTC day gives different, wrong levels).

**DEF-SWEEP-01 — Liquidity Sweep.** ALL must be true: (1) price trades ≥ 1 tick beyond the named DEF-LIQ-01 level (wick counts); (2) within `sweep_close_n` candles of first penetration, a candle CLOSES back on the original side; (3) record `sweep_extreme` = the most extreme price reached (this anchors the SL). No close-back within the window → breakout, not sweep → setup void.

**DEF-FVG-01 — Fair Value Gap.** Bullish: three consecutive candles c1, c2, c3 with `low(c3) > high(c1)`; zone = [high(c1), low(c3)]. Bearish mirrored: `high(c3) < low(c1)`; zone = [high(c3), low(c1)]. **CE** = 50% midpoint of the zone. Size filters (both required): height ≥ `fvg_min` × ATR(14) AND ≤ 3.0 × ATR. A gap is DEAD once price has traded through 100% of it; dead gaps are never reused. Nested-FVG rule: if displacement leaves multiple valid gaps, use the LOWEST bullish / HIGHEST bearish — one deterministic choice so chart and code always agree.

**DEF-ENTRY-01 — Tap Entry (limit).** Limit order at the CE of the array. Expires if unfilled within `expiry_bars` LTF candles of setup completion, or at killzone end, whichever is first. Stated trade-off: better price, more missed winners. (The alternative, confirmation-close market entry, is NOT used in v1.0 — a spec picks exactly one entry mechanic.)

**DEF-KZ-01 — Killzones (defined in America/New_York wall-clock time).**

| Killzone | NY time | UTC winter (NY=UTC−5) | UTC summer (NY=UTC−4) |
|---|---|---|---|
| Asian | 20:00–00:00 | 01:00–05:00 (+1d) | 00:00–04:00 (+1d) |
| London | 02:00–05:00 | 07:00–10:00 | 06:00–09:00 |
| **NY AM (used)** | **08:30–11:00** | **13:30–16:00** | **12:30–15:00** |
| NY Lunch | 12:00–13:00 | 17:00–18:00 | 16:00–17:00 (no-trade) |
| NY PM | 13:30–16:00 | 18:30–21:00 | 17:30–20:00 |

**DEF-TIME-01 — Day boundaries, server time, DST.** Trading day = 17:00→17:00 NY; compute PDH/PDL on this boundary. Implement killzones with the `America/New_York` timezone (Python `zoneinfo`; Pine session strings), NOT fixed UTC offsets. MT5: most brokers run UTC+2 (winter) / UTC+3 (summer) synchronized to US DST so 17:00 NY = 00:00 server → `NY = server − 7 h` year-round; expose `ServerToNYOffsetH` and verify against one known session open before the first run. Never hardcode. Two DST-transition weeks per year: tradeable here, but journal-tagged.

**DEF-BIAS-01 — HTF Order Flow State.** On the 1H, maintain a structure state via DEF-STRUCT-01/02 events. Bias = BULLISH if the last event was a bullish BOS and price has not closed below the last 1H higher-low. BEARISH mirrored. Anything else = NEUTRAL → no trades.

**DEF-DOL-01 — Draw on Liquidity.** The nearest UNSWEPT DEF-LIQ-01 pool in the bias direction within 3.0 × ATR(1H, 14) of current price. None within reach → no trade (no target worth drawing to).

---

*End of document. Version v1.0 · Status UNTESTED · Next action: implement per Part D, pre-flight per C1, baseline per C2, then report via Part F.*

# NYAM-SWEEP-FVG v2.0 — deliberate spec revision (user-authorized)

**Why this document exists:** v1.0 produced 0 trades over 3 years of real EURUSD
data (see `reports/v1.0_2022-2024_run1_findings.md`). The failure was structural,
not tunable: two of the spec's design choices contradict EURUSD's actual NY-AM
geometry. The user (strategy owner) directed a revision that keeps EURUSD and the
core concept pair. These are **spec changes, versioned v2.0** — not parameter
tuning, and they are logged as such per the v1.0 discipline ("a spec change is a
spec-author decision"). Status resets to **UNTESTED** until v2.0 passes its own
gates on its own OOS window.

## Change 1 — Sweep pool: PDL/PDH → overnight session low/high (DEF-LIQ-02)

**v1.0:** longs required a killzone sweep of the **previous day's low** while 1H
bias was BULLISH.

**Evidence of failure:** on the 195 narrative-eligible days in 2022-2024, the
sweep-side pool was even *touched* during the killzone on only 25 (~13%). A
bullish 1H bias and an NY-AM trade through PDL are near-mutually-exclusive: that
is a deep countertrend flush, not the normal manipulation leg.

**v2.0 (DEF-LIQ-02):** the sweep pool for longs is the **overnight session low**
— the lowest low printed from the 17:00-NY trading-day start up to (not
including) the first killzone bar. Shorts mirror with the overnight session
high. This is the classic NY-AM "Judas swing" pool: the liquidity resting under
the overnight range gets run at/after the open, then price displaces with the
HTF trend. It is a *with-trend pullback sweep*, so it coexists naturally with
the bias filter instead of contradicting it. The level is frozen at the
killzone open (no repainting; it is fully known at 08:30 NY).

Note: when the overnight range has already traded below PDL, the overnight low
lies below PDL and *contains* it — so the deeper pool is automatically the one
that must be swept. Sweep mechanics (DEF-SWEEP-01: ≥1-tick penetration,
close-back within `sweep_close_n`, `sweep_extreme` recorded) are unchanged —
only the level definition changed.

**Fuel condition (N3) update:** by construction the overnight low has not been
"swept" before the killzone (it *is* the running minimum), so N3 reduces to: the
first killzone penetration of the level is the sweep — there is no earlier
same-day penetration to disqualify it. The engine still checks this explicitly.

## Change 2 — `dol_reach` becomes free parameter #8 (was fixed 3.0)

**v1.0:** `dol_reach_atr_1h = 3.0` fixed → typical reach ≈ 44-46 pips.

**Evidence of failure:** median EURUSD PDH-PDL day range 2022-2024 was 66.7
pips; the fixed reach disqualified ~60% of days at the narrative stage before
any other logic ran, and no free parameter could touch it.

**v2.0:** `dol_reach_atr` joins the parameter table as free parameter **#8 of
the 8 allowed** (B7 cap now fully used): default **6.0**, test range **3.0–8.0**.
It obeys all existing anti-overfit rules (coarse grids only, ≤3 params per
optimization pass). The DOL concept itself is unchanged: an **unswept** PDH
(longs) within `dol_reach × ATR(1H)` of the killzone-open price must exist, or
no trade that day. TP2 remains that external pool.

## Change 3 — TP1: broken swing → displacement-leg extreme

**v1.0:** TP1 = the swing high whose break confirmed the MSS (a `swing_k=1`
pivot).

**Evidence of failure:** with the v2.0 overnight pool, funnel instrumentation on
2022-2024 showed 13 MSS-confirmed setups whose RR-to-TP1 had **median 0.28 and
minimum −0.49** — i.e. the "broken swing" frequently sits at or even *below*
the FVG's CE entry, because with `swing_k=1` the most recent confirmed pivot is
often a minor structure point inside the displacement leg itself. The RR ≥ 1
skip (correctly) rejected 10 of 13; the surviving 3 never filled. A TP1 that can
be below the entry is not a target definition — it is a geometry accident.

**v2.0:** TP1 = the **displacement-leg extreme**: for longs, the highest high
printed from the sweep's penetration bar through the MSS-confirmation bar
(mirrored for shorts). This is the internal liquidity the manipulation →
displacement sequence actually created, it is strictly above a long entry at CE
(the CE lies inside that leg), it is fully known at order placement, and it
cannot repaint. The RR ≥ 1-to-TP1 skip, the 50% partial + break-even move at
TP1, and TP2 = the frozen DOL pool are all unchanged.

## Unchanged (everything else)

Killzone 08:30–11:00 NY · 17:00-NY day boundary · 1H bias via BOS/CHoCH ·
DEF-SWEEP-01 mechanics · DEF-DISP-01 · DEF-MSS-01 · DEF-FVG-01 (+ nested rule,
CE entry) · RR≥1-to-TP1 skip · SL = sweep_extreme ± buffer · TP1 = broken swing,
50% + BE · TP2 = PDH/PDL · flat 12:00 NY · max_bars 42 · 2 trades/day · −2R
daily stop · one-attempt-per-pool · 0.5% risk · all six B5 gates · B6 robustness
· B2 cost model · single-look OOS discipline.

## Version & discipline notes

- v2.0 is a **new hypothesis**: fresh UNTESTED status, fresh IS/OOS split, its
  own single OOS look. v1.0's OOS look is not reused or contaminated.
- The narrative gate (bias + DOL + shallow floor) is evaluated **once per day at
  the killzone open** and frozen — codifying spec A2's "all three must be TRUE
  at 08:30 NY" (this was also fixed as a bug during the v1.0 run).
- Free parameters now: `sweep_close_n`, `mss_window`, `disp_mult`, `fvg_min`,
  `expiry_bars`, `sl_buffer_points`, `dol_reach_atr`, `ServerToNYOffsetH`
  (broker-verified, never optimized) — 8/8, cap reached. **No further parameters
  may be added to this strategy, ever** (B7).

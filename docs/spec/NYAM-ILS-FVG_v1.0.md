# NYAM-ILS-FVG v1.0 — Intraday Liquidity Sweep + FVG (successor hypothesis)

**Status: UNTESTED.** New strategy at v1.0 per the parent spec's C4 step 12,
created after **NYAM-SWEEP-FVG was archived on EURUSD / NY-AM with two failed
versions** (v1.0: 0 trades / 3 y; v2.0: 1–3 trades, negative expectancy — see
`reports/` and the C5 entries). Same instrument (EURUSD), same session (NY AM),
same two trigger concepts (DEF-SWEEP-01 + DEF-FVG-01), same risk framework and
validation gates. What changes is *which liquidity gets swept*.

## Why the predecessor starved (measured, not guessed)

The archived model required a sweep of a **day-scale pool** (PDL, then the
overnight extreme) while a stack of narrative gates (bias + unswept-DOL +
shallow floor) filtered days upstream. Measured on 2022–2024: 778 trading days
→ 326 narrative-eligible → 57 swept → 13 MSS → ~3 trades. Day-extreme sweeps
during one 2.5-hour window are simply rare events; no in-range parameter could
change that (the frequency grid confirmed: every cell n ≤ 2 in-sample).

What *does* get swept several times a week in NY AM is **intraday liquidity**:
the most recent confirmed 5m swing low/high. That is the pattern this
hypothesis trades — with-trend pullback sweeps of internal pools.

## Rules delta vs the archived spec (everything else inherited unchanged)

1. **DEF-LIQ-03 (sweep pool):** at each killzone bar, the pool for longs is the
   **most recent CONFIRMED 5m swing low** (`swing_k=1`, confirmed k bars late,
   never repainting — DEF-SWING-01); shorts mirror with the confirmed swing
   high. Sweep mechanics are DEF-SWEEP-01 verbatim: ≥1-tick penetration, a
   close back across the level within `sweep_close_n` bars, `sweep_extreme`
   recorded as the SL anchor. The N3 "fuel" check does not apply — internal
   pools are naturally revisited; staleness is bounded by the close-back
   window and `mss_window`.
2. **Narrative (once per day at 08:30 NY):** 1H bias (DEF-BIAS-01) must be
   non-NEUTRAL — longs only in BULLISH, shorts only in BEARISH. The **DOL
   existence gate is dropped** (it removed 57% of days in the archived model);
   PDH/PDL must merely be defined (they anchor TP2).
3. **TP1:** displacement-leg extreme (inherited from v2.0 Change 3).
   **TP2 (external liquidity):** for longs, `max(PDH, session high so far)`;
   shorts mirror with `min(PDL, session low so far)`. Both components are known
   at placement; no repaint.
4. **Parameters:** the 7 free parameters and every fixed constant carry over;
   `dol_reach` is unused (no DOL gate). One trade per swept level per day, all
   account guards unchanged.

## Validation

Full Part B applies unchanged: B2 costs (1.0×/1.5×), 70/30 chronological
IS/OOS, single OOS look, all six B5 gates, B6 robustness. Tuning only on IS,
frequency levers per C2 step 5. The 2024 tail of the current dataset has not
been used for any ILS parameter selection.

*Honest disclosure:* the 2022–2024 window was used for the predecessor's
failure diagnosis (funnel counts, frequency measurements). That is
structural-level contamination of this window for design purposes; performance
tuning of ILS itself starts fresh on the IS segment only, and a longer history
(2015–2021) has been requested to strengthen the eventual sample.

## v1.0 IS result (2026-07-18) — C2/C3 complete, OOS deliberately not consumed

Funnel on IS (2022-01→2024-02): 558 sweeps → 78 MSS (86% attrition) → 42 RR≥1
(median RR 1.05 after the leg-extreme TP1) → 11 CE fills (74% no-fill).

Two bounded IS passes (mss_window×fvg_min×expiry_bars, then
disp_mult×sweep_close_n from the winner; sl_buffer from MAE p90 → 10 pts):
best cell n=22, **expectancy −0.026R, PF 0.96**; every cell in both grids
negative (−0.03…−0.22R). Frequency ceiling ≈ 0.9 trades/month.

**Verdict: IS-FAIL.** With in-sample expectancy negative across the entire
bounded parameter space, running the single OOS look would be theater — it is
NOT consumed and remains available. Next legitimate steps, in order:
1. Extend history to 2015–2024 (10 y): a fresh 2015–2021 IS untouched by any of
   this iteration, with 2022–2024 as a clean OOS for a frozen design.
2. If (and only if) long-IS shows positive expectancy but fill starvation, the
   documented v1.1 single change is the entry mechanic (CE → FVG edge; the 74%
   no-fill measurement is the evidence base).
3. If long-IS is also flat/negative → archive the sweep+FVG family on EURUSD
   entirely; the system will have honestly demonstrated "no edge at these costs."

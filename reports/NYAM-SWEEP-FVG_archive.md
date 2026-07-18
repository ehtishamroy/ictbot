# Archive log — NYAM-SWEEP-FVG on EURUSD / NY-AM (spec C5 format)

Two versions failed → the concept pair is **ARCHIVED** on this instrument/session
per spec B5/C4. The successor hypothesis is NYAM-ILS-FVG v1.0
(`docs/spec/NYAM-ILS-FVG_v1.0.md`) — new strategy, fresh v1.0, per C4 step 12.

```
2026-07-18 | NYAM-SWEEP-FVG v1.0 | EURUSD / NY-AM | 2022-01-02..2024-12-31
Gates failed: 4 (1/2/3/5/6 undefined - insufficient sample)
Key numbers: exp=n/a PF=n/a maxDD=n/a oosN=0 (total trades = 0)
Diagnosis (from data): bias+PDL-sweep geometric contradiction (pool touched on
  13% of eligible NY-AM days) plus fixed dol_reach 3.0xATR(1H) (~44-46 pips)
  below the median EURUSD day range (66.7 pips).
Decision: iterate -> v2.0 (user-authorized structural spec revision)
```

```
2026-07-18 | NYAM-SWEEP-FVG v2.0 | EURUSD / NY-AM | IS 2022-01-02..2024-02-07
Gates failed: 4 (n=1-2 across ALL 27 IS grid cells; frequency-lever grid
  mss_window x fvg_min x expiry_bars could not lift n above 2)
Key numbers: best IS cell exp=-0.163 PF=0.73 n=2; defaults n=1 exp=-1.206
Diagnosis (from data): multiplicative confluence starvation - narrative gates
  (0.42) x session-extreme sweep rarity (0.17) x MSS-with-FVG (0.23) x RR/fill
  attrition ~= 0.003 setups/day. Cross-checked in the London killzone (02:00-
  05:00 NY): n=3, PF=0.28 - session-independent. The concept stack, not the
  session, is the constraint.
Decision: ARCHIVE the pair on EURUSD (v1.0 + v2.0 = two failed versions).
  Next hypothesis: NYAM-ILS-FVG v1.0 - intraday confirmed-swing pools
  (DEF-LIQ-03), no DOL gate, same sweep+FVG concepts, same discipline.
```

Note: the v2.0 OOS tail (2024-02..2024-12) was never consumed — the single-look
budget for that window remains intact for the successor.

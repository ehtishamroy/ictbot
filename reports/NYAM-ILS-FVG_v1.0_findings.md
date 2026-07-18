# NYAM-ILS-FVG v1.0 — 10-year validation findings (EURUSD 2015-2024)

**Status: TESTED-FAIL (out-of-sample).** The in-sample edge did not survive the
held-out window. This is the OOS discipline working exactly as intended.

## Protocol
- Data: HistData 1m EURUSD, 3,671,080 bars, 2015-01-01 .. 2024-12-31.
- IS = 2015-2021 (7 y, fresh). OOS = 2022-2024 (3 y, single look).
- Selection on IS only (bar-fill conservative), 2 bounded C3 grids; sl_buffer
  from IS winners' MAE p90. Final IS+OOS numbers use 1-minute intrabar fills.
- Full B2 costs; 1.5x cost-stress on OOS.
- **Locked params (from IS only):** mss_window=20, fvg_min=0.5, expiry_bars=8,
  disp_mult=1.5, sweep_close_n=1, sl_buffer_points=10.

## Result
| Window | n | win% | avgRR | expectancy | PF | maxDD(R) |
|---|---|---|---|---|---|---|
| IS 2015-2021 (intrabar) | 48 | 56.2 | 0.92 | **+0.202R** | 1.18 | 36.9 |
| OOS 2022-2024 (intrabar) | 23 | 60.9 | 0.51 | **−0.125R** | 0.79 | 4.6 |
| OOS @ 1.5x costs | 23 | — | — | **−0.336R** | 0.54 | — |

IS grid was tunable to look strong (best cell +0.489R, PF 1.62) — but that is
in-sample. The locked design went **negative out-of-sample**, and worse under
the mandatory 1.5x cost stress.

**Gates (OOS): 1[ ] 2[ ] 3[x] 4[ ] 5[x] 6[ ] → FAIL.** Only max-drawdown and the
PF-stability ratio passed; expectancy, PF, trade count (23 < 30), and monthly
concentration all failed.

## Diagnosis (from the data, not vibes)
1. **Overfit, caught.** +0.20R IS → −0.13R OOS is the classic IS→OOS decay. The
   grid found parameters that fit 2015-2021 noise; they did not generalize.
2. **Winners are marginal.** OOS avgRR 0.51 with MAE-p90(winners)=1.90R means most
   "wins" are TP1-partial-then-break-even scrapes after deep adverse excursion —
   the CE limit entry repeatedly catches falling knives before the move works.
3. **Structural frequency floor.** Even at 10 years and the highest-frequency
   in-range settings, the strategy trades ~0.65/month → ~78 lifetime trades,
   **below the spec's 100-trade minimum**. This concept in this session is
   effectively unvalidatable: too rare to ever reach significance.
4. **Not a session artifact.** The predecessor's London cross-check and this
   window-to-window decay both point at the concept stack, not the clock.

## Archive decision (spec C5)
```
2026-07-18 | NYAM-ILS-FVG v1.0 | EURUSD / NY-AM | IS 2015-2021 / OOS 2022-2024
Gates failed: 1,2,4,6   Key numbers: OOS exp=-0.125 PF=0.79 maxDD=4.6 oosN=23
  (IS exp=+0.202 PF=1.18; OOS@1.5x exp=-0.336)
Diagnosis: in-sample edge did not survive OOS (overfit); winners marginal
  (avgRR 0.51, MAE-p90 1.90R); frequency floor ~0.65/mo < 100-trade minimum.
Decision: ARCHIVE. This is the THIRD failed variant of the sweep->MSS->FVG
  concept family on EURUSD/NY-AM (NYAM-SWEEP-FVG v1.0, v2.0; NYAM-ILS-FVG v1.0).
  Per spec: archived, not tortured further. Any next attempt is a genuinely
  different concept or session (a new strategy at v1.0), not a 4th patch.
```

## Honest bottom line
Across **3 design variants and 10 years of real data**, under correct IS/OOS
discipline and realistic costs, the sweep→MSS→FVG family shows **no durable,
out-of-sample edge on EURUSD NY-AM**. The build is sound — the pipeline found and
*rejected* an overfit instead of shipping it. That negative result, honestly
obtained, is the correct and valuable outcome. What it is NOT is a green light to
keep mutating rules until a backtest smiles.

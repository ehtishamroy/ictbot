# ETF daily data — drop CSVs here

DIVTREND v1.0 reads every `*.csv` in this directory as one instrument.

## Format (Yahoo Finance "Download" default)
`Date,Open,High,Low,Close,Adj Close,Volume` — the loader uses **Adj Close**
(total return, dividend-adjusted). One file per ticker, named `<TICKER>.csv`
(e.g. `SPY.csv`). Column names are matched case-insensitively; a plain
`Date,Adj Close` file also works.

## Tickers to fetch (pre-registered A1 universe, ≥15 years each)
- **Equity:** SPY, QQQ, EFA, EEM, EWJ, IWM
- **Rates:** IEF, TLT, SHY, BWX
- **Commodity:** GLD, SLV, USO, UNG, DBB, DBA
- **FX:** UUP, FXE, FXY, FXB

Get them from Yahoo Finance (each ticker → Historical Data → Download), Stooq,
or any daily adjusted-close source. Longer history is better (the pre-reg wants
the 2009-19 flat trend period, 2022 surge, and post-2022 weakness all in-window).
Then run: `python3 scripts/run_divtrend_validation.py`

Raw CSVs are gitignored (only this README + SOURCE notes are tracked).

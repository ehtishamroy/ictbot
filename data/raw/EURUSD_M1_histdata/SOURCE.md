# EURUSD M1 data source

- Source: HistData.com free "Generic ASCII" 1-minute bar export
- Instrument: EURUSD
- Years: 2015-2024 (10 full years; 3,671,080 1-minute bars)
- Split for validation: IS = 2015-2021 (7 y), OOS = 2022-2024 (3 y)
- Format: no header, `;`-separated `YYYYMMDD HHMMSS;open;high;low;close;volume`
- Volume: always 0 in the free feed (not usable as a real volume signal)
- Timestamps: fixed GMT-5 ("EST"), **no DST adjustment**, per HistData's own
  documentation. Loaded via `ictbot.data.load.load_histdata_ascii_m1`, which
  localizes to `Etc/GMT+5` (fixed UTC-5) and converts to true UTC before any
  DST-aware killzone/PDH-PDL logic runs.
- No real bid/ask spread in this feed; the backtest cost model assumes a fixed
  75th-percentile session spread per spec B2 rather than measuring per-bar spread.

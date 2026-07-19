"""Multi-market daily data layer for DIVTREND.

Loads a directory of daily adjusted-close CSVs (Yahoo Finance "Download" format:
Date,Open,High,Low,Close,Adj Close,Volume) into a single wide price panel
(index = date, columns = tickers), aligned on the union calendar with
forward-filled prices so cross-market holiday gaps become 0-return days. Also
provides a synthetic generator with embedded trends for testing the backtester
before real data arrives.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# A1 sleeve map (pre-registered universe). Tickers -> asset-class sleeve.
SLEEVES: dict[str, str] = {
    # equity indices
    "SPY": "equity", "QQQ": "equity", "EFA": "equity", "EEM": "equity",
    "EWJ": "equity", "IWM": "equity",
    # rates / bonds
    "IEF": "rates", "TLT": "rates", "SHY": "rates", "BWX": "rates",
    # commodities
    "GLD": "commodity", "SLV": "commodity", "USO": "commodity", "UNG": "commodity",
    "DBB": "commodity", "DBA": "commodity",
    # fx
    "UUP": "fx", "FXE": "fx", "FXY": "fx", "FXB": "fx",
}

_ADJ = ["adj close", "adjclose", "adj_close", "close"]
_DATE = ["date", "timestamp", "time"]


def _find(cols, cands):
    low = {c.lower(): c for c in cols}
    for c in cands:
        if c in low:
            return low[c]
    return None


def load_etf_csv(path: str | Path) -> pd.Series:
    """Load one ticker's daily adjusted close as a UTC-naive date-indexed Series."""
    df = pd.read_csv(path)
    dcol = _find(df.columns, _DATE)
    acol = _find(df.columns, _ADJ)
    if dcol is None or acol is None:
        raise ValueError(f"{path}: need a date and adj-close column; got {list(df.columns)}")
    idx = pd.to_datetime(df[dcol], errors="coerce")
    s = pd.Series(pd.to_numeric(df[acol], errors="coerce").to_numpy(), index=idx)
    s = s[~s.index.isna()].sort_index()
    return s[~s.index.duplicated(keep="last")]


def load_etf_dir(path: str | Path, tickers: list[str] | None = None) -> pd.DataFrame:
    """Load all {TICKER}.csv in a directory into a wide adj-close panel."""
    path = Path(path)
    series = {}
    for f in sorted(path.glob("*.csv")):
        tk = f.stem.upper()
        if tickers is not None and tk not in tickers:
            continue
        series[tk] = load_etf_csv(f)
    if not series:
        raise ValueError(f"no CSVs found in {path}")
    panel = pd.DataFrame(series).sort_index()
    return align_panel(panel)


def align_panel(prices: pd.DataFrame) -> pd.DataFrame:
    """Union calendar, forward-fill prices; drop leading all-NaN rows."""
    prices = prices.sort_index()
    prices = prices.ffill()
    return prices.dropna(how="all")


def prices_to_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Daily simple returns; first row dropped. Forward-filled gaps -> 0 return."""
    return prices.pct_change().iloc[1:]


def sleeves_for(tickers) -> dict:
    """Map available tickers to sleeves (unknown tickers -> 'other')."""
    return {t: SLEEVES.get(t, "other") for t in tickers}


def synthetic_prices(n_days: int = 4000, seed: int = 0,
                     per_sleeve: int = 3, trend: float = 0.35) -> pd.DataFrame:
    """Synthetic daily prices across 4 sleeves with persistent trends.

    Each series is a random walk whose drift switches sign in multi-month regimes
    (so time-series momentum has real, detectable information), plus idiosyncratic
    noise and a mild per-sleeve common factor. ``trend`` scales drift strength.
    """
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2008-01-01", periods=n_days)
    sleeves = ["equity", "rates", "commodity", "fx"]
    cols, data = [], {}
    for s_i, sl in enumerate(sleeves):
        factor = rng.normal(0, 0.004, n_days)
        for j in range(per_sleeve):
            tk = f"{sl[:3].upper()}{j+1}"
            # regime drift: sign flips every ~2-6 months, magnitude ~ trend*vol
            drift = np.zeros(n_days)
            t = 0
            while t < n_days:
                seg = rng.integers(42, 130)
                drift[t:t + seg] = rng.choice([-1, 1]) * trend * 0.0006
                t += seg
            noise = rng.normal(0, 0.008, n_days)
            ret = drift + 0.3 * factor + noise
            price = 100 * np.exp(np.cumsum(ret))
            data[tk] = price
            cols.append(tk)
    return pd.DataFrame(data, index=idx)


SYNTH_SLEEVES = {f"{sl[:3].upper()}{j+1}": sl
                 for sl in ["equity", "rates", "commodity", "fx"] for j in range(6)}

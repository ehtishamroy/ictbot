"""Phase 1 — tick->bar and LTF->HTF resampling correctness (left-labelled, right-open)."""
import pandas as pd

from ictbot.data.resample import resample_ohlcv, ticks_to_bars


def test_ticks_to_bars_basic():
    idx = pd.DatetimeIndex([
        "2024-01-15 13:30:10", "2024-01-15 13:30:40",
        "2024-01-15 13:31:05", "2024-01-15 13:31:50",
    ], tz="UTC")
    ticks = pd.DataFrame(
        {"bid": [1.0, 1.2, 1.1, 1.3], "ask": [1.0002, 1.2002, 1.1002, 1.3002],
         "bid_vol": [1, 1, 1, 1], "ask_vol": [1, 1, 1, 1]},
        index=idx,
    )
    bars = ticks_to_bars(ticks, "1min")
    assert len(bars) == 2
    b0 = bars.iloc[0]
    assert b0["open"] == 1.0001            # mid of first tick
    assert b0["high"] == 1.2001
    assert b0["close"] == 1.2001
    assert round(b0["spread"], 4) == 0.0002


def test_resample_5m_to_1h():
    idx = pd.date_range("2024-01-15 13:00", periods=24, freq="5min", tz="UTC")
    bars = pd.DataFrame({
        "open": range(24), "high": [i + 1 for i in range(24)],
        "low": [i - 1 for i in range(24)], "close": range(24),
        "volume": [1] * 24,
    }, index=idx)
    h = resample_ohlcv(bars, "1h")
    assert len(h) == 2
    assert h.iloc[0]["open"] == 0
    assert h.iloc[0]["high"] == 12           # max high across first 12 bars
    assert h.iloc[0]["close"] == 11          # last close of first hour
    assert h.iloc[0]["volume"] == 12

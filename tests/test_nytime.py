"""Phase 1 — the time layer. If any of these fail, every downstream number is wrong.

Covers the two things the spec calls out as the #1 ICT-EA bug source:
  * DST-correct NY-AM killzone (winter NY=UTC-5, summer NY=UTC-4), and
  * the 17:00->17:00 NY trading-day boundary used for PDH/PDL.
"""
import pandas as pd

from ictbot.data import nytime as nt


def utc(s):
    return pd.Timestamp(s, tz="UTC")


# --- killzone, winter (January, NY = UTC-5): 08:30 NY == 13:30 UTC ----------
def test_killzone_winter():
    assert nt.to_ny(utc("2024-01-15 13:30")).strftime("%H:%M") == "08:30"
    assert nt.in_killzone(utc("2024-01-15 13:30"))          # 08:30 NY, inclusive start
    assert not nt.in_killzone(utc("2024-01-15 13:29"))      # 08:29 NY
    assert nt.in_killzone(utc("2024-01-15 15:59"))          # 10:59 NY
    assert not nt.in_killzone(utc("2024-01-15 16:00"))      # 11:00 NY, exclusive end


# --- killzone, summer (July, NY = UTC-4): 08:30 NY == 12:30 UTC -------------
def test_killzone_summer():
    assert nt.to_ny(utc("2024-07-15 12:30")).strftime("%H:%M") == "08:30"
    assert nt.in_killzone(utc("2024-07-15 12:30"))
    assert not nt.in_killzone(utc("2024-07-15 12:29"))
    assert nt.in_killzone(utc("2024-07-15 14:59"))          # 10:59 NY
    assert not nt.in_killzone(utc("2024-07-15 15:00"))      # 11:00 NY


def test_killzone_mask_matches_scalar():
    idx = pd.date_range("2024-01-15 12:00", "2024-01-15 17:00", freq="5min", tz="UTC")
    mask = nt.in_killzone_mask(idx)
    for ts in idx:
        assert bool(mask.loc[ts]) == nt.in_killzone(ts)


# --- trading-day boundary (17:00 NY): Mon 17:00 and Tue 08:30 share a day ---
def test_trading_day_boundary_winter():
    # Mon 2024-01-15 17:00 NY == 22:00 UTC -> belongs to Tuesday's session
    assert nt.trading_day(utc("2024-01-15 22:00")) == pd.Timestamp("2024-01-16")
    # one minute before the boundary is still Monday
    assert nt.trading_day(utc("2024-01-15 21:59")) == pd.Timestamp("2024-01-15")
    # Tuesday's NY-AM killzone is in Tuesday's session
    assert nt.trading_day(utc("2024-01-16 13:30")) == pd.Timestamp("2024-01-16")


def test_trading_day_series_matches_scalar():
    idx = pd.date_range("2024-01-15 20:00", "2024-01-16 20:00", freq="1h", tz="UTC")
    s = nt.trading_day_series(idx)
    for ts in idx:
        assert pd.Timestamp(s.loc[ts]) == nt.trading_day(ts)


# --- PDH/PDL come from the previous trading day, no look-ahead --------------
def test_previous_day_levels():
    # Day 1 session (labeled 01-16): a bar at 14:00 UTC 01-16 -> high 5, low 1
    # Day 2 session (labeled 01-17): a bar at 14:00 UTC 01-17 -> should see PDH=5, PDL=1
    idx = pd.DatetimeIndex([
        utc("2024-01-16 14:00"),   # trading day 01-16
        utc("2024-01-16 15:00"),   # trading day 01-16
        utc("2024-01-17 14:00"),   # trading day 01-17
    ])
    df = pd.DataFrame(
        {"high": [5.0, 4.0, 9.0], "low": [1.0, 2.0, 6.0]}, index=idx
    )
    out = nt.previous_day_levels(df)
    # first day has no previous day -> NaN
    assert pd.isna(out.iloc[0]["pdh"])
    # second day sees day-1 extremes
    assert out.iloc[2]["pdh"] == 5.0
    assert out.iloc[2]["pdl"] == 1.0


def test_naive_timestamp_treated_as_utc():
    # a tz-naive input must be interpreted as UTC, never local time
    assert nt.to_ny(pd.Timestamp("2024-01-15 13:30")).strftime("%H:%M") == "08:30"

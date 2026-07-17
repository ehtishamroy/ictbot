"""Phase 3 — context detectors: HTF bias, DOL, and the spread/news filters."""
import pandas as pd

from ictbot.detectors.bias import BEARISH, BULLISH, NEUTRAL, bias_at
from ictbot.detectors.dol import dol_exists
from ictbot.detectors.filters import news_clear, spread_ok


# --- bias_at: uses only the last fully-closed HTF bar (no look-ahead) --------
def test_bias_at_no_lookahead():
    idx = pd.to_datetime(["2024-01-15 13:00", "2024-01-15 14:00", "2024-01-15 15:00"]).tz_localize("UTC")
    bias = pd.Series([NEUTRAL, BULLISH, BEARISH], index=idx)
    # 14:30 -> last closed bar is the one labelled 14:00
    assert bias_at(bias, "2024-01-15 14:30") == BULLISH
    # exactly 14:00 -> that bar is still forming ([14:00,15:00)); use 13:00
    assert bias_at(bias, "2024-01-15 14:00") == NEUTRAL
    # before any bar -> NEUTRAL
    assert bias_at(bias, "2024-01-15 12:00") == NEUTRAL


# --- DOL: unswept pool in bias direction, within reach ----------------------
def test_dol_exists():
    # long: PDH above price, 20 pips away, reach 3*ATR(1H)=30 pips -> valid
    assert dol_exists(1.0000, 1.0020, atr_1h=0.001, direction="bull", swept=False)
    # already swept -> not a draw
    assert not dol_exists(1.0000, 1.0020, 0.001, "bull", swept=True)
    # out of reach: 50 pips away vs 30 pip reach
    assert not dol_exists(1.0000, 1.0050, 0.001, "bull", swept=False)
    # short mirror: PDL below price within reach
    assert dol_exists(1.0000, 0.9980, 0.001, "bear", swept=False)


# --- filters ----------------------------------------------------------------
def test_spread_ok():
    assert spread_ok(0.00008, max_spread_pips=1.2)     # 0.8 pip <= 1.2
    assert not spread_ok(0.00015, max_spread_pips=1.2)  # 1.5 pip > 1.2


def test_news_clear():
    entry = pd.Timestamp("2024-01-15 13:30", tz="UTC")
    close_evt = [pd.Timestamp("2024-01-15 13:40", tz="UTC")]   # 10 min away
    far_evt = [pd.Timestamp("2024-01-15 14:30", tz="UTC")]     # 60 min away
    assert not news_clear(entry, close_evt, window_min=15)
    assert news_clear(entry, far_evt, window_min=15)

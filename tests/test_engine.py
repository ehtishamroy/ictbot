"""Phase 4 — A7 state machine end-to-end.

Drives a hand-crafted one-day scenario through IDLE -> SWEPT -> WAIT_RETRACE ->
IN_TRADE -> TP1 -> TP2 and checks the resulting trade record. Every price level
and the expected R are computed by hand in the comments.
"""
import numpy as np
import pandas as pd

from ictbot.config import load_config
from ictbot.engine.features import prepare_features
from ictbot.engine.params import EngineParams
from ictbot.engine.state_machine import run
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "config" / "nyam_sweep_fvg_v1.0.yaml"


def _params():
    return EngineParams.from_config(load_config(CONFIG))


# Bars: 5m, 2024-01-16 (winter, NY AM killzone 13:30-16:00 UTC). All in killzone.
# pdl=1.0000 pdh=1.0050 bias BULLISH atr=0.0010 atr1h=0.0020 conf_sh=1.0030(TP1).
_ROWS = [
    # open,   high,    low,     close
    (1.0010, 1.0012, 1.0008, 1.0010),  # 0 idle
    (1.0010, 1.0011, 0.9994, 1.0002),  # 1 sweep of PDL (low pierces, closes back)
    (1.0002, 1.0008, 1.0000, 1.0006),  # 2 swept
    (1.0006, 1.0020, 1.0005, 1.0019),  # 3 displacement leg
    (1.0019, 1.0034, 1.0014, 1.0033),  # 4 MSS: close>1.0030, FVG 1.0008-1.0014, CE 1.0011
    (1.0025, 1.0026, 1.0009, 1.0013),  # 5 retrace fills limit at CE 1.0011
    (1.0013, 1.0031, 1.0012, 1.0028),  # 6 TP1 hit @1.0030 -> close 50%, SL->BE
    (1.0028, 1.0051, 1.0025, 1.0049),  # 7 TP2 hit @1.0050 -> close remainder
    (1.0049, 1.0050, 1.0045, 1.0047),  # 8 idle (PDH now swept -> no new setup)
    (1.0047, 1.0048, 1.0044, 1.0046),  # 9 idle
]


def _features():
    idx = pd.date_range("2024-01-16 13:30", periods=len(_ROWS), freq="5min", tz="UTC")
    df = pd.DataFrame(_ROWS, columns=["open", "high", "low", "close"], index=idx)
    df["atr"] = 0.0010
    df["atr1h"] = 0.0020
    df["conf_sh"] = 1.0030
    df["conf_sh_idx"] = 0
    df["conf_sl"] = 0.9990
    df["conf_sl_idx"] = 0
    df["pdh"] = 1.0050
    df["pdl"] = 1.0000
    df["in_kz"] = True
    df["bias"] = "BULLISH"
    df["spread"] = 0.00008           # 0.8 pip, under the 1.2 cap
    df["trading_day"] = pd.Timestamp("2024-01-16")
    return df


def test_full_long_trade_tp1_then_tp2():
    trades = run(_features(), _params(), news=[])
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["direction"] == "long"
    assert t["exit_reason"] == "TP2"
    assert bool(t["tp1_hit"]) is True
    assert abs(t["entry"] - 1.0011) < 1e-9
    # R = 0.5*(TP1-entry)/rd + 0.5*(TP2-entry)/rd, rd = 1.0011-0.99938 = 0.00172
    assert abs(t["r_total"] - 1.6860) < 5e-3
    assert t["mfe_r"] > 0


def test_rr_below_one_is_skipped():
    # Move the swing high (TP1) close to entry so RR-to-TP1 < 1 -> no trade.
    df = _features()
    df["conf_sh"] = 1.0015   # TP1 only ~4 pips over CE vs ~17 pip risk
    trades = run(df, _params(), news=[])
    assert len(trades) == 0


def test_news_blocks_fill():
    # High-impact event within +/-15 min of the fill bar (bar 5, 13:55 UTC).
    trades = run(_features(), _params(), news=[pd.Timestamp("2024-01-16 14:00", tz="UTC")])
    assert len(trades) == 0


# Mirrored SHORT scenario: sweep PDH, MSS down, sell limit at CE, TP1 then TP2.
# pdh=1.0050(sweep) pdl=1.0000(TP2) conf_sl=1.0015(TP1) atr=0.0010 atr1h=0.0020.
_ROWS_SHORT = [
    (1.0040, 1.0042, 1.0038, 1.0040),  # 0 idle
    (1.0040, 1.0056, 1.0039, 1.0048),  # 1 sweep of PDH (high pierces, closes back)
    (1.0048, 1.0050, 1.0042, 1.0044),  # 2 swept
    (1.0044, 1.0045, 1.0030, 1.0031),  # 3 displacement leg down
    (1.0031, 1.0032, 1.0010, 1.0013),  # 4 MSS: close<1.0015, bearish FVG 1.0032-1.0042, CE 1.0037
    (1.0018, 1.0038, 1.0016, 1.0034),  # 5 retrace up fills sell limit at CE 1.0037
    (1.0034, 1.0035, 1.0014, 1.0018),  # 6 TP1 hit @1.0015 -> close 50%, SL->BE
    (1.0018, 1.0019, 0.9999, 1.0001),  # 7 TP2 hit @1.0000 -> close remainder
    (1.0001, 1.0002, 0.9998, 1.0000),  # 8 idle (PDL now swept)
    (1.0000, 1.0001, 0.9997, 0.9999),  # 9 idle
]


def _features_short():
    idx = pd.date_range("2024-01-16 13:30", periods=len(_ROWS_SHORT), freq="5min", tz="UTC")
    df = pd.DataFrame(_ROWS_SHORT, columns=["open", "high", "low", "close"], index=idx)
    df["atr"] = 0.0010
    df["atr1h"] = 0.0020
    df["conf_sh"] = 1.0080          # far away; long path never triggers
    df["conf_sh_idx"] = 0
    df["conf_sl"] = 1.0015          # TP1
    df["conf_sl_idx"] = 0
    df["pdh"] = 1.0050
    df["pdl"] = 1.0000
    df["in_kz"] = True
    df["bias"] = "BEARISH"
    df["spread"] = 0.00008
    df["trading_day"] = pd.Timestamp("2024-01-16")
    return df


def test_full_short_trade_mirror():
    trades = run(_features_short(), _params(), news=[])
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["direction"] == "short"
    assert t["exit_reason"] == "TP2"
    assert bool(t["tp1_hit"]) is True
    assert abs(t["entry"] - 1.0037) < 1e-9
    # rd = 1.00562-1.0037 = 0.00192; R = 0.5*(0.0022 + 0.0037)/0.00192
    assert abs(t["r_total"] - 1.5365) < 5e-3


def test_prepare_features_smoke():
    # prepare_features runs and produces the columns the engine needs.
    idx5 = pd.date_range("2024-01-15 00:00", "2024-01-18 00:00", freq="5min", tz="UTC")
    rng = np.random.default_rng(0)
    price = 1.10 + np.cumsum(rng.normal(0, 0.0001, len(idx5)))
    df5 = pd.DataFrame({
        "open": price, "high": price + 0.0002, "low": price - 0.0002,
        "close": price, "volume": 1.0,
    }, index=idx5)
    df1h = df5.resample("1h").agg({"open": "first", "high": "max",
                                   "low": "min", "close": "last"}).dropna()
    feats = prepare_features(df5, df1h, _params())
    for col in ["atr", "conf_sh", "pdh", "pdl", "in_kz", "bias", "atr1h", "spread"]:
        assert col in feats.columns
    # engine runs without error on real-shaped features
    run(feats, _params(), news=[])

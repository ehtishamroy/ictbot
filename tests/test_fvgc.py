"""EURUSD-FVGC v1.0 — engine behavior with hand-computed outcomes."""
from pathlib import Path

import numpy as np
import pandas as pd

from ictbot.config import load_config
from ictbot.engine.fvgc import FvgcParams, prepare_fvgc_features, run_fvgc

CONFIG = Path(__file__).resolve().parents[1] / "config" / "eurusd_fvgc_v1.0.yaml"


def _params():
    return FvgcParams.from_config(load_config(CONFIG))


def test_config_loads():
    p = _params()
    assert p.ema_len == 50 and p.rr_target == 2.0 and p.fvg_min == 0.3
    assert len(p.ranges) == 6
    assert p.session_start_h == 7 and p.session_end_h == 16


# Bullish FVG at bar 3: gap [1.0004, 1.0014] (low[3] 1.0014 > high[1] 1.0004),
# middle candle (bar 2) body 0.0011 >= 1.0xATR. Uptrend (ema 1.0000 < price).
# entry = proximal top 1.0014; sl = 1.0004 - 0.00002 = 1.00038; risk 0.00102;
# tp = 1.0014 + 2.0*0.00102 = 1.00344.
_ROWS = [
    (1.0002, 1.0003, 1.0001, 1.0002),   # 0
    (1.0002, 1.0004, 1.0001, 1.0003),   # 1  high=1.0004 (gap bottom)
    (1.0004, 1.0016, 1.0004, 1.0015),   # 2  displacement candle
    (1.0015, 1.0018, 1.0014, 1.0016),   # 3  low=1.0014 (gap top) -> FVG, WAIT_FILL
    (1.0016, 1.0017, 1.0013, 1.0015),   # 4  fills limit at 1.0014
    (1.0015, 1.00345, 1.0014, 1.0034),  # 5  TP 1.00344 hit
    (1.0034, 1.0035, 1.0030, 1.0032),   # 6
]


def _features(rows, ema=1.0000, atr=0.0010):
    idx = pd.date_range("2022-06-01 08:00", periods=len(rows), freq="5min", tz="UTC")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["atr"] = atr
    df["ema"] = ema
    df["in_sess"] = True
    df["spread"] = 0.00008
    df["utc_day"] = idx.normalize()
    return df


def test_fvgc_long_continuation_tp():
    trades = run_fvgc(_features(_ROWS), _params())
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["direction"] == "long"
    assert t["exit_reason"] == "TP"
    assert abs(t["entry"] - 1.0014) < 1e-9
    assert abs(t["r_total"] - 2.0) < 1e-9        # fixed rr_target


def test_fvgc_wrong_trend_no_trade():
    # same FVG but EMA above price -> not an uptrend -> bull FVG rejected
    trades = run_fvgc(_features(_ROWS, ema=1.0050), _params())
    assert len(trades) == 0


def test_fvgc_no_displacement_no_trade():
    rows = [list(r) for r in _ROWS]
    rows[2] = [1.0004, 1.0016, 1.0004, 1.00075]   # middle body 0.00035 < 1.0xATR
    trades = run_fvgc(_features([tuple(r) for r in rows]), _params())
    assert len(trades) == 0


def test_fvgc_stop_out():
    rows = [list(r) for r in _ROWS]
    rows[5] = [1.0015, 1.0016, 1.00030, 1.0004]   # bar5 low pierces sl 1.00038
    trades = run_fvgc(_features([tuple(r) for r in rows]), _params())
    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "SL"
    assert abs(trades.iloc[0]["r_total"] + 1.0) < 1e-9


def test_prepare_features_smoke():
    idx = pd.date_range("2022-06-01", periods=400, freq="5min", tz="UTC")
    rng = np.random.default_rng(0)
    px = 1.10 + np.cumsum(rng.normal(0, 0.0001, len(idx)))
    df5 = pd.DataFrame({"open": px, "high": px + 2e-4, "low": px - 2e-4,
                        "close": px, "volume": 1.0}, index=idx)
    f = prepare_fvgc_features(df5, _params())
    for c in ["atr", "ema", "in_sess", "spread", "utc_day"]:
        assert c in f.columns
    run_fvgc(f, _params())          # runs without error

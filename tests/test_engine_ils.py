"""NYAM-ILS-FVG v1.0 — swing-pool (DEF-LIQ-03) engine behavior.

The pool is the most recent CONFIRMED swing low (conf_sl), not PDL/overnight:
the fixture sets pdl far below and asserts the trade sweeps conf_sl instead.
"""
from pathlib import Path

import pandas as pd

from ictbot.config import load_config
from ictbot.engine.params import EngineParams
from ictbot.engine.state_machine import run

CONFIG_ILS = Path(__file__).resolve().parents[1] / "config" / "nyam_ils_fvg_v1.0.yaml"


def _params():
    return EngineParams.from_config(load_config(CONFIG_ILS))


def test_ils_config():
    p = _params()
    assert p.pool_mode == "swing"
    assert len(p.ranges) == 6            # 7 free minus the never-tuned offset


_ROWS = [
    # open,   high,   low,    close
    (1.0010, 1.0012, 1.0008, 1.0010),   # 0 kz open
    (1.0010, 1.0011, 0.9994, 1.0002),   # 1 sweep of conf_sl 1.0000, ext 0.9994
    (1.0002, 1.0008, 1.0000, 1.0006),   # 2 swept
    (1.0006, 1.0020, 1.0005, 1.0019),   # 3 displacement leg
    (1.0019, 1.0034, 1.0014, 1.0033),   # 4 MSS >1.0030; FVG 1.0008-1.0014, CE 1.0011
    (1.0025, 1.0026, 1.0009, 1.0013),   # 5 retrace fills CE
    (1.0013, 1.0031, 1.0012, 1.0028),   # 6 (TP1 1.0034 not yet)
    (1.0028, 1.0051, 1.0025, 1.0049),   # 7 TP1 leg-high 1.0034 -> 50% + BE
    (1.0049, 1.0050, 1.0045, 1.0047),   # 8 TP2 1.0050 -> close
    (1.0047, 1.0048, 1.0044, 1.0046),   # 9
]


def _features():
    idx = pd.date_range("2024-01-16 13:30", periods=len(_ROWS), freq="5min", tz="UTC")
    df = pd.DataFrame(_ROWS, columns=["open", "high", "low", "close"], index=idx)
    df["atr"] = 0.0010
    df["atr1h"] = 0.0020
    df["conf_sh"] = 1.0030
    df["conf_sh_idx"] = 0
    df["conf_sl"] = 1.0000               # the ILS pool
    df["conf_sl_idx"] = 0
    df["pdh"] = 1.0050                   # TP2 anchor
    df["pdl"] = 0.9950                   # far away — must NOT be the pool
    df["in_kz"] = True
    df["bias"] = "BULLISH"
    df["spread"] = 0.00008
    df["trading_day"] = pd.Timestamp("2024-01-16")
    return df


def test_ils_sweeps_confirmed_swing_not_pdl():
    trades = run(_features(), _params(), news=[])
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["direction"] == "long"
    assert abs(t["swept_pool"] - 1.0000) < 1e-9      # conf_sl, NOT pdl 0.9950
    assert t["exit_reason"] == "TP2"
    assert abs(t["tp1"] - 1.0034) < 1e-9             # displacement-leg high
    assert abs(t["tp2"] - 1.0050) < 1e-9             # max(PDH, session high)
    # rd = 1.0011-0.99938 = 0.00172
    # R = 0.5*(1.0034-1.0011)/rd + 0.5*(1.0050-1.0011)/rd = 1.8023
    assert abs(t["r_total"] - 1.8023) < 5e-3


def test_ils_neutral_bias_blocks_day():
    df = _features()
    df["bias"] = "NEUTRAL"
    assert len(run(df, _params(), news=[])) == 0

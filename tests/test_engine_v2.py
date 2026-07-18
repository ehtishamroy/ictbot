"""v2.0 — DEF-LIQ-02 overnight sweep pool.

Verifies: (1) the day_run_low/high features equal the pre-bar intraday extremes;
(2) the engine sweeps the OVERNIGHT low (not PDL) when overnight bars exist, and
walks the full TP1->TP2 path with hand-computed R; (3) days whose overnight low
is never swept in the killzone produce no trade even though PDL logic would have.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from ictbot.config import load_config
from ictbot.engine.params import EngineParams
from ictbot.engine.state_machine import run

CONFIG_V2 = Path(__file__).resolve().parents[1] / "config" / "nyam_sweep_fvg_v2.0.yaml"


def _params_v2():
    return EngineParams.from_config(load_config(CONFIG_V2))


def test_v2_config_loads_dol_reach_free():
    p = _params_v2()
    assert p.dol_reach == 6.0
    assert "dol_reach" in p.ranges and p.ranges["dol_reach"] == (3.0, 8.0)


# Winter day: killzone starts 13:30 UTC (08:30 NY). Bars 0-5 are pre-killzone
# (overnight tail), establishing overnight low 1.0002 at bar 1. PDL is far
# deeper (0.9980) and is never touched — the sweep target must be the overnight
# low, not PDL. pdh (DOL/TP2) = 1.0050, conf_sh (TP1) = 1.0030.
_ROWS = [
    # open,   high,   low,    close        # UTC    state
    (1.0008, 1.0010, 1.0004, 1.0006),      # 13:00  overnight
    (1.0006, 1.0008, 1.0002, 1.0005),      # 13:05  overnight LOW = 1.0002
    (1.0005, 1.0009, 1.0004, 1.0008),      # 13:10  overnight
    (1.0008, 1.0010, 1.0006, 1.0009),      # 13:15  overnight
    (1.0009, 1.0011, 1.0007, 1.0010),      # 13:20  overnight
    (1.0010, 1.0012, 1.0008, 1.0010),      # 13:25  overnight
    (1.0010, 1.0012, 1.0008, 1.0010),      # 13:30  kz open (1.0010)
    (1.0010, 1.0011, 1.0000, 1.0006),      # 13:35  SWEEP of 1.0002, ext 1.0000
    (1.0006, 1.0008, 1.0004, 1.0006),      # 13:40  swept
    (1.0006, 1.0022, 1.0005, 1.0021),      # 13:45  displacement (body 15 pips)
    (1.0021, 1.0034, 1.0016, 1.0033),      # 13:50  MSS >1.0030; FVG 1.0008-1.0016
    (1.0025, 1.0026, 1.0010, 1.0014),      # 13:55  retrace fills CE 1.0012
    (1.0014, 1.0032, 1.0013, 1.0030),      # 14:00  TP1 1.0030 -> 50% + BE
    (1.0030, 1.0051, 1.0028, 1.0049),      # 14:05  TP2 1.0050 -> close
    (1.0049, 1.0050, 1.0045, 1.0047),      # 14:10
]


def _features(rows):
    idx = pd.date_range("2024-01-16 13:00", periods=len(rows), freq="5min", tz="UTC")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["atr"] = 0.0010
    df["atr1h"] = 0.0020
    df["conf_sh"] = 1.0030
    df["conf_sh_idx"] = 0
    df["conf_sl"] = 0.9990
    df["conf_sl_idx"] = 0
    df["pdh"] = 1.0050
    df["pdl"] = 0.9980
    df["in_kz"] = idx.hour * 60 + idx.minute >= 13 * 60 + 30
    df["bias"] = "BULLISH"
    df["spread"] = 0.00008
    df["trading_day"] = pd.Timestamp("2024-01-16")
    # same transform as prepare_features (DEF-LIQ-02)
    g = df.groupby("trading_day")
    df["day_run_low"] = g["low"].transform(lambda s: s.shift(1).cummin())
    df["day_run_high"] = g["high"].transform(lambda s: s.shift(1).cummax())
    return df


def test_day_run_columns_are_prebar_extremes():
    f = _features(_ROWS)
    assert np.isnan(f["day_run_low"].iloc[0])          # nothing before bar 0
    assert f["day_run_low"].iloc[2] == 1.0002          # bar-1 low visible at bar 2
    assert f["day_run_low"].iloc[6] == 1.0002          # kz open sees overnight low
    assert f["day_run_high"].iloc[6] == 1.0012


def test_v2_overnight_sweep_full_long():
    trades = run(_features(_ROWS), _params_v2(), news=[])
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["direction"] == "long"
    assert t["exit_reason"] == "TP2"
    assert abs(t["swept_pool"] - 1.0002) < 1e-9        # overnight low, NOT pdl
    assert abs(t["entry"] - 1.0012) < 1e-9
    # v2.0 TP1 = displacement-leg high (bars 7-10) = 1.0034; TP2 = PDH 1.0050
    # rd = 1.0012 - (1.0000 - 0.00002) = 0.00122
    # R  = 0.5*(1.0034-1.0012)/rd + 0.5*(1.0050-1.0012)/rd = 2.4590
    assert abs(t["tp1"] - 1.0034) < 1e-9
    assert abs(t["r_total"] - 2.4590) < 5e-3


def test_v2_no_trade_when_overnight_low_never_swept():
    rows = [list(r) for r in _ROWS]
    for j in (7, 8):                                   # keep lows above 1.0002
        rows[j][2] = 1.0005
    trades = run(_features([tuple(r) for r in rows]), _params_v2(), news=[])
    assert len(trades) == 0

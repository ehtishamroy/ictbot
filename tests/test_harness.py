"""Phase 5 — harness: chronological IS/OOS split + full-pipeline smoke on synthetic
1-minute data (the real 3-month smoke of C1 needs real data; this proves the
plumbing runs end-to-end and produces well-formed output)."""
from pathlib import Path

import numpy as np
import pandas as pd

from ictbot.backtest.costs import CostModel
from ictbot.backtest.harness import backtest, split_is_oos
from ictbot.config import load_config
from ictbot.engine.params import EngineParams

CONFIG = Path(__file__).resolve().parents[1] / "config" / "nyam_sweep_fvg_v1.0.yaml"


def _params():
    return EngineParams.from_config(load_config(CONFIG))


def test_split_is_oos_chronological():
    start = pd.Timestamp("2024-01-01", tz="UTC")
    end = pd.Timestamp("2024-01-11", tz="UTC")   # 10-day window, 70% boundary = day 8
    trades = pd.DataFrame({
        "entry_time": pd.to_datetime([
            "2024-01-02", "2024-01-05", "2024-01-08", "2024-01-09", "2024-01-10",
        ]).tz_localize("UTC"),
        "r_total": [1, -1, 1, 1, -1],
    })
    is_t, oos_t, boundary = split_is_oos(trades, start, end, 0.70)
    assert boundary == pd.Timestamp("2024-01-08", tz="UTC")
    assert len(is_t) == 2 and len(oos_t) == 3   # < boundary vs >= boundary


def _synthetic_1m(days=20, seed=0):
    idx = pd.date_range("2024-01-01", periods=days * 1440, freq="1min", tz="UTC")
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 0.00005, len(idx))
    mid = 1.10 + np.cumsum(steps)
    wobble = np.abs(rng.normal(0, 0.00008, len(idx)))
    return pd.DataFrame({
        "open": mid, "high": mid + wobble, "low": mid - wobble,
        "close": mid + rng.normal(0, 0.00003, len(idx)), "volume": 1.0,
    }, index=idx)


def test_backtest_pipeline_smoke_with_intrabar_and_costs():
    df1m = _synthetic_1m()
    df5 = df1m.resample("5min").agg({"open": "first", "high": "max", "low": "min",
                                     "close": "last", "volume": "sum"}).dropna()
    df1h = df1m.resample("1h").agg({"open": "first", "high": "max", "low": "min",
                                    "close": "last", "volume": "sum"}).dropna()
    cm = CostModel(spread_pips=0.8, commission_per_lot_roundturn=7.0, slippage_pips=0.3)
    trades = backtest(df5, df1h, _params(), news=[], cost_model=cm, df1m=df1m)
    # runs without error and returns a well-formed frame
    assert isinstance(trades, pd.DataFrame)
    for col in ["direction", "r_total", "risk_distance", "exit_reason"]:
        assert col in trades.columns
    if not trades.empty:                       # if any trades, costs must reduce R
        assert (trades["r_net"] <= trades["r_gross"]).all()
        assert trades["exit_reason"].isin(
            ["SL", "BE_STOP", "TP2", "FLAT", "MAX_BARS"]).all()

"""Forward-test tracker — position sheet, log, forward eval + kill-switch."""
from pathlib import Path

import numpy as np
import pandas as pd

from ictbot.config import load_config
from ictbot.portfolio.data import SYNTH_SLEEVES, synthetic_prices
from ictbot.portfolio.forward import (
    BACKTEST_MAXDD_PCT,
    KILL_MULT,
    append_forward_log,
    evaluate_forward,
    realized_forward_returns,
)
from ictbot.portfolio.live import position_sheet, weights_asof
from ictbot.portfolio.params import DivtrendParams

CONFIG = Path(__file__).resolve().parents[1] / "config" / "divtrend_v1.0.yaml"


def _params():
    return DivtrendParams.from_config(load_config(CONFIG))


def _prices():
    return synthetic_prices(n_days=1200, seed=5, per_sleeve=3, trend=0.5)


def test_position_sheet_shape_and_sides():
    prices = _prices()
    sheet = position_sheet(prices, _params(), SYNTH_SLEEVES)
    assert set(sheet.columns) == {"ticker", "sleeve", "side", "weight_pct"}
    assert sheet["side"].isin(["LONG", "SHORT", "FLAT"]).all()
    # at least some non-flat positions on trending data
    assert (sheet["side"] != "FLAT").any()


def test_locked_config_present():
    cfg = load_config(CONFIG)
    lk = cfg.raw.get("locked", {})
    assert lk["lookback_months"] == 9 and lk["vol_lookback_days"] == 30


def test_forward_log_append_and_dedup(tmp_path):
    log_path = tmp_path / "log.json"
    w = pd.Series({"EQU1": 0.5, "RAT1": -0.3})
    append_forward_log(log_path, pd.Timestamp("2024-01-31"), w)
    log = append_forward_log(log_path, pd.Timestamp("2024-02-29"), w)
    assert len(log) == 2
    # re-logging the same date replaces, not duplicates
    log = append_forward_log(log_path, pd.Timestamp("2024-02-29"), w)
    assert len(log) == 2


def test_forward_too_short():
    prices = _prices()
    log = [{"date": str(prices.index[-2].date()),
            "weights": {c: 0.1 for c in prices.columns[:3]}}]
    ev = evaluate_forward(prices, log)
    assert ev["status"] == "TOO_SHORT"


def test_realized_forward_returns_and_killswitch():
    prices = _prices()
    # two rebalances ~6 months apart so there is a realized forward stretch
    d1, d2 = prices.index[-260], prices.index[-130]
    w = {c: (0.4 if i % 2 == 0 else -0.4) for i, c in enumerate(prices.columns)}
    log = [{"date": str(d1.date()), "weights": w},
           {"date": str(d2.date()), "weights": w}]
    fwd = realized_forward_returns(prices, log)
    assert len(fwd) > 100
    ev = evaluate_forward(prices, log)
    assert ev["status"] in ("ON_TRACK", "WARN_NEGATIVE", "SUSPEND")
    assert ev["kill_threshold_pct"] == round(KILL_MULT * BACKTEST_MAXDD_PCT, 1)


def test_killswitch_triggers_on_big_drawdown():
    # craft a forward stretch with a deliberately huge drawdown
    idx = pd.bdate_range("2024-01-01", periods=200)
    prices = pd.DataFrame({"A": 100 * np.cumprod(1 + np.linspace(-0.02, -0.02, 200))},
                          index=idx)
    log = [{"date": str(idx[0].date()), "weights": {"A": 1.0}}]
    ev = evaluate_forward(prices, log)
    assert ev["killed"] is True and ev["status"] == "SUSPEND"

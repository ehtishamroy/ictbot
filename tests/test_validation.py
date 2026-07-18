"""Phase 7 — validation driver: perturbation, optimiser guards, robustness,
pre-flight, CSV loader, and the full driver smoke."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ictbot.backtest.costs import CostModel
from ictbot.config import load_config
from ictbot.engine.params import EngineParams
from ictbot.validation.driver import full_validation
from ictbot.validation.optimize import optimize_is, suggest_sl_buffer_points
from ictbot.validation.perturb import perturb_param, set_param, shift_session
from ictbot.validation.preflight import preflight
from ictbot.validation.robustness import run_robustness

CONFIG = Path(__file__).resolve().parents[1] / "config" / "nyam_sweep_fvg_v1.0.yaml"


def _params():
    return EngineParams.from_config(load_config(CONFIG))


def _trades(rvals, start="2024-06-01"):
    et = pd.date_range(start, periods=len(rvals), freq="3D", tz="UTC")
    return pd.DataFrame({
        "entry_time": et, "r_total": rvals, "r_net": rvals,
        "risk_distance": [0.0002] * len(rvals),
        "mae_r": [-0.3] * len(rvals), "mfe_r": [1.0] * len(rvals),
        "exit_reason": ["TP2"] * len(rvals), "tp1_hit": [True] * len(rvals),
    })


# --- perturbation -----------------------------------------------------------
def test_perturb_clamps_and_rounds():
    p = _params()
    # disp_mult 1.5 * 1.2 = 1.8 (in range 1.0-2.5)
    assert abs(perturb_param(p, "disp_mult", 0.2).disp_mult - 1.8) < 1e-9
    # mss_window 12 * 1.2 = 14.4 -> 14 (int)
    assert perturb_param(p, "mss_window", 0.2).mss_window == 14
    # expiry_bars 15 * 2.0 -> 30 clamped to range max 24
    assert set_param(p, "expiry_bars", 30).expiry_bars == 24
    with pytest.raises(KeyError):
        perturb_param(p, "server_to_ny_off_h", 0.2)


def test_shift_session():
    p = _params()
    s = shift_session(p, 15)
    assert s.kz_start.strftime("%H:%M") == "08:45"
    assert s.kz_end.strftime("%H:%M") == "11:15"


# --- optimiser guards + ranking --------------------------------------------
def test_optimize_selects_best_and_enforces_rules():
    p = _params()

    def run_fn_is(pp):   # expectancy peaks at disp_mult == 1.5
        e = 0.5 - abs(pp.disp_mult - 1.5)
        return _trades([e, e, e])

    ranked = optimize_is(p, {"disp_mult": [1.0, 1.5, 2.0]}, run_fn_is, r_col="r_total")
    assert abs(ranked.iloc[0]["disp_mult"] - 1.5) < 1e-9

    with pytest.raises(ValueError):   # >3 params
        optimize_is(p, {"disp_mult": [1], "mss_window": [6], "fvg_min": [0.3],
                        "expiry_bars": [8]}, run_fn_is)
    with pytest.raises(ValueError):   # sl_buffer never grid-searched
        optimize_is(p, {"sl_buffer_points": [1, 2, 3]}, run_fn_is)
    with pytest.raises(ValueError):   # coarse grid only (<=5 values)
        optimize_is(p, {"disp_mult": [1.0, 1.2, 1.4, 1.6, 1.8, 2.0]}, run_fn_is)


def test_suggest_sl_buffer_from_mae():
    p = _params()
    is_trades = _trades([1.0, 1.0])
    is_trades["risk_distance"] = [0.0001, 0.0001]
    is_trades["mae_r"] = [-0.3, -0.4]     # -> price 3,4 pts; p90 ~ 3.9 -> 4
    assert suggest_sl_buffer_points(is_trades, p, r_col="r_net") == 4


# --- robustness -------------------------------------------------------------
def test_robustness_pass():
    p, cm = _params(), CostModel(0.8, 7.0, 0.3)
    run_fn = lambda pp, c: _trades([0.4] * 35)       # always positive expectancy
    res = run_robustness(p, cm, run_fn, r_col="r_net")
    assert res.perturb_ok and res.cost_ok and res.session_ok and res.passed


def test_robustness_fails_on_perturbation():
    p, cm = _params(), CostModel(0.8, 7.0, 0.3)
    base_disp = p.disp_mult

    def run_fn(pp, c):   # any change to disp_mult flips expectancy negative
        return _trades([-0.4] * 35) if pp.disp_mult != base_disp else _trades([0.4] * 35)

    res = run_robustness(p, cm, run_fn, r_col="r_net")
    assert res.perturb_ok is False and res.passed is False


def test_robustness_fails_on_cost_stress():
    p, cm = _params(), CostModel(0.8, 7.0, 0.3)
    run_fn = lambda pp, c: _trades([-0.4] * 35) if c.multiplier != 1.0 else _trades([0.4] * 35)
    res = run_robustness(p, cm, run_fn, r_col="r_net")
    assert res.cost_ok is False and res.passed is False


# --- CSV loader -------------------------------------------------------------
def test_load_ohlcv_csv(tmp_path):
    from ictbot.data.load import load_ohlcv_csv
    csv = tmp_path / "d.csv"
    csv.write_text("Time,Open,High,Low,Close,Volume\n"
                   "2024-01-15 13:30:00,1.10,1.11,1.09,1.105,10\n"
                   "2024-01-15 13:31:00,1.105,1.12,1.10,1.115,12\n")
    df = load_ohlcv_csv(csv)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.tz is not None and len(df) == 2


# --- synthetic frames for preflight + driver --------------------------------
def _synthetic_frames(days=6, seed=1):
    idx = pd.date_range("2024-01-01", periods=days * 1440, freq="1min", tz="UTC")
    rng = np.random.default_rng(seed)
    mid = 1.10 + np.cumsum(rng.normal(0, 0.00005, len(idx)))
    w = np.abs(rng.normal(0, 0.00008, len(idx)))
    df1m = pd.DataFrame({"open": mid, "high": mid + w, "low": mid - w,
                         "close": mid, "volume": 1.0}, index=idx)
    df5 = df1m.resample("5min").agg({"open": "first", "high": "max", "low": "min",
                                     "close": "last", "volume": "sum"}).dropna()
    df1h = df1m.resample("1h").agg({"open": "first", "high": "max", "low": "min",
                                    "close": "last", "volume": "sum"}).dropna()
    return df1m, df5, df1h


def test_preflight_passes_on_clean_data():
    _, df5, df1h = _synthetic_frames()
    res = preflight(df5, df1h, _params())
    assert res.checks["time_conversion"] and res.checks["day_boundary"]
    assert res.checks["killzone_present"] and res.checks["pdh_pdl_present"]
    assert res.passed


def test_full_validation_smoke_fail_path():
    df1m, df5, df1h = _synthetic_frames()
    cm = CostModel(0.8, 7.0, 0.3)
    out = full_validation(df5, df1h, _params(), cm,
                          data_start=df5.index[0], data_end=df5.index[-1], df1m=df1m)
    # random data -> no edge -> gates fail, no robustness run
    assert out.status == "TESTED-FAIL"
    assert out.robustness is None
    assert "FAIL" in out.report and "NYAM-SWEEP-FVG" in out.report

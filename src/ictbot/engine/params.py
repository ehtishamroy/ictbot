"""EngineParams — flattened, typed strategy parameters for the state machine.

Built from a validated :class:`ictbot.config.Config`, converting the spec's
"points"/"pips" into absolute price distances for one instrument (EURUSD by
default: 1 point = 1e-5, 1 pip = 1e-4).
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import time as dtime

from ..config import Config
from ..data.nytime import parse_hhmm

POINT_EURUSD = 1e-5
PIP_EURUSD = 1e-4

# free parameters that must stay integer-valued when perturbed/optimised
INT_FREE = {"sweep_close_n", "mss_window", "expiry_bars"}
# EngineParams field name -> config free_params key (names differ for fvg_min)
_FREE_FIELD_TO_CFG = {
    "sweep_close_n": "sweep_close_n",
    "mss_window": "mss_window",
    "disp_mult": "disp_mult",
    "fvg_min": "fvg_min_atr",
    "expiry_bars": "expiry_bars",
    "sl_buffer_points": "sl_buffer_points",
}


@dataclass(frozen=True)
class EngineParams:
    # free (A6)
    sweep_close_n: int
    mss_window: int
    disp_mult: float
    fvg_min: float
    expiry_bars: int
    sl_buffer_points: float
    # fixed constants
    fvg_max: float
    disp_max: float
    swing_k_ltf: int
    swing_k_htf: int
    atr_len: int
    risk_pct: float
    max_trades: int
    daily_stop_r: float
    max_bars: int
    partial_close_pct: float
    news_window_min: int
    dol_reach: float
    max_spread_pips: float
    shallow_floor_points: float
    # instrument
    point: float
    pip: float
    # session (NY wall-clock)
    kz_start: dtime
    kz_end: dtime
    flat_time: dtime
    day_boundary: dtime

    # free-parameter test ranges (A6), keyed by EngineParams field name
    ranges: dict = field(default_factory=dict)

    # mutation helpers (for perturbation / optimisation) ----------------------
    def replace(self, **overrides) -> "EngineParams":
        """Return a copy with the given fields overridden (ranges preserved)."""
        return dataclasses.replace(self, **overrides)

    def clamp_free(self, field_name: str, value: float) -> float:
        """Clamp a free-param value to its A6 range and round ints."""
        lo, hi = self.ranges.get(field_name, (value, value))
        value = min(max(value, lo), hi)
        return int(round(value)) if field_name in INT_FREE else value

    # derived price distances -------------------------------------------------
    @property
    def tick(self) -> float:
        return self.point

    @property
    def sl_buffer_price(self) -> float:
        return self.sl_buffer_points * self.point

    @property
    def shallow_floor_price(self) -> float:
        return self.shallow_floor_points * self.point

    @property
    def max_spread_price(self) -> float:
        return self.max_spread_pips * self.pip

    @classmethod
    def from_config(cls, cfg: Config, point: float = POINT_EURUSD,
                    pip: float = PIP_EURUSD) -> "EngineParams":
        f = cfg.fixed
        s = cfg.session
        kz = s["killzone"]
        return cls(
            sweep_close_n=int(cfg.p("sweep_close_n")),
            mss_window=int(cfg.p("mss_window")),
            disp_mult=float(cfg.p("disp_mult")),
            fvg_min=float(cfg.p("fvg_min_atr")),
            expiry_bars=int(cfg.p("expiry_bars")),
            sl_buffer_points=float(cfg.p("sl_buffer_points")),
            fvg_max=float(f["fvg_max_atr"]),
            disp_max=4.0,
            swing_k_ltf=int(f["swing_k_ltf"]),
            swing_k_htf=int(f["swing_k_htf"]),
            atr_len=int(f["atr_len"]),
            risk_pct=float(f["risk_pct"]),
            max_trades=int(f["max_trades_per_day"]),
            daily_stop_r=float(f["daily_stop_r"]),
            max_bars=int(f["max_bars"]),
            partial_close_pct=float(f["partial_close_pct"]),
            news_window_min=int(f["news_window_min"]),
            dol_reach=float(f["dol_reach_atr_1h"]),
            max_spread_pips=float(f["max_spread_pips"]),
            shallow_floor_points=float(f["shallow_sweep_floor_points"]),
            point=point,
            pip=pip,
            kz_start=parse_hhmm(kz["start"]),
            kz_end=parse_hhmm(kz["end"]),
            flat_time=parse_hhmm(f["flat_time_ny"]),
            day_boundary=parse_hhmm(s["trading_day_boundary_ny"]),
            ranges={fld: tuple(cfg.free[cfgkey].__dict__[k] for k in ("lo", "hi"))
                    for fld, cfgkey in _FREE_FIELD_TO_CFG.items() if cfgkey in cfg.free},
        )

"""DivtrendParams — typed parameters for the DIVTREND portfolio strategy."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from ..config import Config

_FREE = {
    "lookback_months": "lookback_months",
    "skip_recent_month": "skip_recent_month",
    "vol_lookback_days": "vol_lookback_days",
    "rebal_band": "rebal_band",
}
_INT_FREE = {"lookback_months", "skip_recent_month", "vol_lookback_days"}


@dataclass(frozen=True)
class DivtrendParams:
    # free
    lookback_months: int
    skip_recent_month: int
    vol_lookback_days: int
    rebal_band: float
    # fixed
    target_vol_inst: float
    target_vol_port: float
    max_inst_weight: float
    max_sleeve_gross: float
    k_max: float
    trading_days_year: int
    month_days: int
    default_cost_bps: float
    is_frac: float
    ranges: dict = field(default_factory=dict)

    def replace(self, **kw) -> "DivtrendParams":
        return dataclasses.replace(self, **kw)

    def clamp_free(self, name: str, value: float) -> float:
        lo, hi = self.ranges.get(name, (value, value))
        value = min(max(value, lo), hi)
        return int(round(value)) if name in _INT_FREE else value

    @classmethod
    def from_config(cls, cfg: Config) -> "DivtrendParams":
        f, b = cfg.fixed, cfg.backtest
        return cls(
            lookback_months=int(cfg.p("lookback_months")),
            skip_recent_month=int(cfg.p("skip_recent_month")),
            vol_lookback_days=int(cfg.p("vol_lookback_days")),
            rebal_band=float(cfg.p("rebal_band")),
            target_vol_inst=float(f["target_vol_inst"]),
            target_vol_port=float(f["target_vol_port"]),
            max_inst_weight=float(f["max_inst_weight"]),
            max_sleeve_gross=float(f["max_sleeve_gross"]),
            k_max=float(f["k_max"]),
            trading_days_year=int(f["trading_days_year"]),
            month_days=int(f["month_days"]),
            default_cost_bps=float(b["default_cost_bps"]),
            is_frac=float(b["is_frac"]),
            ranges={fld: tuple(cfg.free[k].__dict__[x] for x in ("lo", "hi"))
                    for fld, k in _FREE.items() if k in cfg.free},
        )

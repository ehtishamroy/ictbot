"""Typed configuration loader for NYAM-SWEEP-FVG.

Loads the YAML parameter set and validates the spec's guard-rails at load time:
- every free parameter's value sits inside its declared test range (A6),
- the free-parameter cap (<= 8) is respected,
- ``server_to_ny_off_h`` is never treated as optimizable.

Loading is where we enforce "never exceed the A6 test ranges" — a bad config
should fail loudly here, not silently produce garbage numbers downstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

FREE_PARAM_CAP = 8


class ConfigError(ValueError):
    """Raised when a config violates a spec guard-rail."""


@dataclass(frozen=True)
class FreeParam:
    name: str
    value: float
    lo: float
    hi: float
    def_id: str

    def __post_init__(self) -> None:
        if not (self.lo <= self.value <= self.hi):
            raise ConfigError(
                f"{self.name}={self.value} outside A6 test range [{self.lo}, {self.hi}]"
            )


@dataclass(frozen=True)
class Config:
    raw: dict[str, Any]
    free: dict[str, FreeParam]
    fixed: dict[str, Any]
    session: dict[str, Any]
    backtest: dict[str, Any]

    # convenience accessors --------------------------------------------------
    def p(self, name: str) -> float:
        """Current value of a free parameter."""
        return self.free[name].value

    @property
    def name(self) -> str:
        return self.raw["strategy"]["name"]

    @property
    def version(self) -> str:
        return str(self.raw["strategy"]["version"])

    @property
    def status(self) -> str:
        return self.raw["strategy"]["status"]


def load_config(path: str | Path) -> Config:
    """Load and validate a strategy config YAML."""
    path = Path(path)
    with path.open() as fh:
        raw = yaml.safe_load(fh)

    fp_raw = raw.get("free_params", {})
    if len(fp_raw) > FREE_PARAM_CAP:
        raise ConfigError(
            f"{len(fp_raw)} free parameters exceeds cap of {FREE_PARAM_CAP} (B7)"
        )

    free: dict[str, FreeParam] = {}
    for name, spec in fp_raw.items():
        lo, hi = spec["range"]
        free[name] = FreeParam(
            name=name,
            value=float(spec["default"]),
            lo=float(lo),
            hi=float(hi),
            def_id=spec.get("def_id", ""),
        )

    # DEF-TIME-01: the server offset is broker-verified, never optimized.
    off = free.get("server_to_ny_off_h")
    if off is not None and off.lo != off.hi:
        raise ConfigError(
            "server_to_ny_off_h must have a fixed range (broker-verified, never optimized)"
        )

    return Config(
        raw=raw,
        free=free,
        fixed=raw.get("fixed", {}),
        session=raw.get("session", {}),
        backtest=raw.get("backtest", {}),
    )

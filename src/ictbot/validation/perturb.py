"""Parameter perturbation and session shifting (for B6 robustness / C3 tuning)."""
from __future__ import annotations

from datetime import datetime, time as dtime, timedelta

from ..engine.params import EngineParams


def perturb_param(params: EngineParams, field_name: str, pct: float) -> EngineParams:
    """Scale one free parameter by ``(1 + pct)``, clamped to its A6 range.

    Integer parameters are rounded. ``server_to_ny_off_h`` is not a free field here
    and cannot be perturbed (DEF-TIME-01: never optimised).
    """
    if field_name not in params.ranges:
        raise KeyError(f"{field_name!r} is not a perturbable free parameter")
    current = getattr(params, field_name)
    new_val = params.clamp_free(field_name, current * (1.0 + pct))
    return params.replace(**{field_name: new_val})


def set_param(params: EngineParams, field_name: str, value: float) -> EngineParams:
    """Set one free parameter to an explicit value, clamped to its range."""
    if field_name not in params.ranges:
        raise KeyError(f"{field_name!r} is not a free parameter")
    return params.replace(**{field_name: params.clamp_free(field_name, value)})


def shift_time(t: dtime, minutes: int) -> dtime:
    """Shift a wall-clock time by +/- minutes (wraps within a day)."""
    base = datetime(2000, 1, 1, t.hour, t.minute) + timedelta(minutes=minutes)
    return base.time()


def shift_session(params: EngineParams, minutes: int) -> EngineParams:
    """Move the whole killzone by +/- minutes (B6 session-shift check)."""
    return params.replace(
        kz_start=shift_time(params.kz_start, minutes),
        kz_end=shift_time(params.kz_end, minutes),
    )

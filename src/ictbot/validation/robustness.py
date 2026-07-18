"""B6 robustness checks — run after the gates pass, before the forward test.

1. **Parameter perturbation** — shift each free parameter +/-20%, one at a time;
   expectancy flipping negative on any single perturbation = knife-edge fit = FAIL.
2. **Cost stress** — the 1.5x-costs run must keep expectancy > 0.
3. **Session shift** — move the killzone +/-15 min; real edges degrade gracefully,
   curve-fits collapse (we require expectancy stays > 0).
4. **Month-by-month table** — inspect for regime dependence (noted, not auto-failed).

Decoupled from data plumbing via ``run_fn(params, cost_model) -> trades`` which
returns the trades of the evaluation (OOS) window.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..backtest.costs import CostModel
from ..engine.params import EngineParams
from ..reporting.metrics import compute_metrics, monthly_net_r
from .perturb import perturb_param, shift_session

PERTURB_PCTS = (-0.20, 0.20)
SESSION_SHIFTS_MIN = (-15, 15)


def _expectancy(trades: pd.DataFrame, r_col: str | None) -> float:
    return compute_metrics(trades, r_col=r_col).expectancy


@dataclass
class RobustnessResult:
    base_expectancy: float
    perturb: dict            # (field, pct) -> expectancy
    perturb_ok: bool
    cost_stress_expectancy: float
    cost_ok: bool
    session: dict            # minutes -> expectancy
    session_ok: bool
    monthly: pd.Series
    passed: bool

    def marks(self) -> dict:
        """Robustness marks for the Part F report."""
        return {"perturb": self.perturb_ok, "cost_stress": self.cost_ok,
                "session_shift": self.session_ok, "monthly": True}


def run_robustness(params: EngineParams, cost_model: CostModel, run_fn,
                   r_col: str | None = "r_net") -> RobustnessResult:
    base = run_fn(params, cost_model)
    base_exp = _expectancy(base, r_col)

    # 1. parameter perturbation, one free param at a time
    perturb: dict = {}
    perturb_ok = True
    for fld in params.ranges:
        for pct in PERTURB_PCTS:
            exp = _expectancy(run_fn(perturb_param(params, fld, pct), cost_model), r_col)
            perturb[(fld, pct)] = exp
            if not (np.isfinite(exp) and exp >= 0):
                perturb_ok = False

    # 2. cost stress at 1.5x
    cost_exp = _expectancy(run_fn(params, cost_model.scaled(1.5)), r_col)
    cost_ok = bool(np.isfinite(cost_exp) and cost_exp > 0)

    # 3. session shift +/-15 min
    session: dict = {}
    session_ok = True
    for m in SESSION_SHIFTS_MIN:
        exp = _expectancy(run_fn(shift_session(params, m), cost_model), r_col)
        session[m] = exp
        if not (np.isfinite(exp) and exp > 0):
            session_ok = False

    # 4. month-by-month regime table (informational)
    monthly = monthly_net_r(base, r_col)

    passed = perturb_ok and cost_ok and session_ok
    return RobustnessResult(base_exp, perturb, perturb_ok, cost_exp, cost_ok,
                            session, session_ok, monthly, passed)

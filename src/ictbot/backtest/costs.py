"""Cost model — spec B2 (mandatory; zero-cost backtests are rejected).

Costs are expressed in **R** so results stay size-independent and comparable:
  * spread — one full session spread per round trip, on the whole position;
  * slippage — 0.3 pip per **market-side** execution; limit fills (entry, TP1,
    TP2) incur none — only stop/flat/max-bars exits do;
  * commission — $7 per lot round-turn, converted to R via the contract size
    (the lot count cancels: commission_R = commission / (risk_distance x contract)).

Every final result is run at 1.0x and 1.5x via ``multiplier`` (B2): if the edge
dies at 1.5x it was a costs artifact, not an edge.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# exits that are market/stop executions (slippage applies) vs limit take-profits
_MARKET_EXITS = {"SL", "BE_STOP", "FLAT", "MAX_BARS"}


@dataclass(frozen=True)
class CostModel:
    spread_pips: float
    commission_per_lot_roundturn: float
    slippage_pips: float
    pip: float = 1e-4
    contract_size: float = 100_000.0   # 1.0 lot EURUSD
    multiplier: float = 1.0

    def _market_frac(self, tp1_hit: bool, exit_reason: str) -> float:
        """Fraction of the position closed via a market/stop execution."""
        if not tp1_hit:
            return 1.0                       # whole position exits on one event
        # TP1 leg is a limit (no slippage); the runner may exit market or at TP2
        return 0.0 if exit_reason == "TP2" else 0.5

    def cost_r(self, risk_distance: float, tp1_hit: bool, exit_reason: str) -> float:
        spread_price = self.spread_pips * self.pip
        slip_price = self.slippage_pips * self.pip
        mkt = self._market_frac(tp1_hit, exit_reason)
        c = (
            spread_price / risk_distance
            + slip_price * mkt / risk_distance
            + self.commission_per_lot_roundturn / (risk_distance * self.contract_size)
        )
        return self.multiplier * c

    def scaled(self, multiplier: float) -> "CostModel":
        return CostModel(self.spread_pips, self.commission_per_lot_roundturn,
                         self.slippage_pips, self.pip, self.contract_size, multiplier)


def apply_costs(trades: pd.DataFrame, cost_model: CostModel) -> pd.DataFrame:
    """Add ``r_gross``, ``cost_r`` and ``r_net`` columns to a trades frame."""
    out = trades.copy()
    if out.empty:
        for c in ("r_gross", "cost_r", "r_net"):
            out[c] = pd.Series(dtype=float)
        return out
    out["r_gross"] = out["r_total"]
    out["cost_r"] = [
        cost_model.cost_r(rd, bool(t1), er)
        for rd, t1, er in zip(out["risk_distance"], out["tp1_hit"], out["exit_reason"])
    ]
    out["r_net"] = out["r_gross"] - out["cost_r"]
    return out

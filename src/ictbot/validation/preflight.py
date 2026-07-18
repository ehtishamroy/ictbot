"""C1 pre-flight checks — run before trusting any backtest number.

The spec is blunt: wrong time handling is the single most common ICT-EA bug, and
every downstream number is garbage if it is wrong. So we verify time and the
day-boundary first, then a smoke pass over the features and trades:
  * known NY-AM open maps to the expected UTC bar (DST-correct);
  * the 17:00-NY trading-day boundary groups PDH/PDL correctly;
  * killzone bars exist and PDH/PDL populate after day one;
  * no trade has entry_time == exit_time (no same-bar entry+exit).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..data.nytime import to_ny, trading_day
from ..engine.features import prepare_features
from ..engine.params import EngineParams
from ..engine.state_machine import run


@dataclass
class PreflightResult:
    checks: dict          # name -> bool
    notes: dict           # name -> detail string

    @property
    def passed(self) -> bool:
        return all(self.checks.values())


def preflight(df5: pd.DataFrame, df1h: pd.DataFrame, params: EngineParams,
              news=None) -> PreflightResult:
    checks: dict = {}
    notes: dict = {}

    # 1. time conversion: 08:30 NY winter == 13:30 UTC, summer == 12:30 UTC
    winter = to_ny(pd.Timestamp("2024-01-15 13:30", tz="UTC")).strftime("%H:%M")
    summer = to_ny(pd.Timestamp("2024-07-15 12:30", tz="UTC")).strftime("%H:%M")
    checks["time_conversion"] = winter == "08:30" and summer == "08:30"
    notes["time_conversion"] = f"winter->{winter}, summer->{summer}"

    # 2. day boundary: Mon 17:00 NY belongs to Tue's session
    d = trading_day(pd.Timestamp("2024-01-15 22:00", tz="UTC"))  # 17:00 NY winter
    checks["day_boundary"] = d == pd.Timestamp("2024-01-16")
    notes["day_boundary"] = f"17:00 NY Mon -> {d.date()}"

    feats = prepare_features(df5, df1h, params, )
    checks["killzone_present"] = bool(feats["in_kz"].any())
    notes["killzone_present"] = f"{int(feats['in_kz'].sum())} killzone bars"

    pdh_ok = feats["pdh"].notna().any() and feats["pdl"].notna().any()
    checks["pdh_pdl_present"] = bool(pdh_ok)
    notes["pdh_pdl_present"] = "PDH/PDL populated after day 1" if pdh_ok else "missing"

    trades = run(feats, params, news=news)
    if trades.empty:
        checks["no_same_bar_exit"] = True
        notes["no_same_bar_exit"] = "no trades in smoke window"
    else:
        same_bar = (pd.to_datetime(trades["entry_time"])
                    == pd.to_datetime(trades["exit_time"])).any()
        checks["no_same_bar_exit"] = not bool(same_bar)
        notes["no_same_bar_exit"] = f"{len(trades)} trades, same-bar={bool(same_bar)}"

    return PreflightResult(checks, notes)

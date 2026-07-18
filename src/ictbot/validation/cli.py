"""Command-line validation runner.

Examples
--------
    python -m ictbot.validation.cli --csv data/raw/EURUSD_1m.csv
    python -m ictbot.validation.cli --dukascopy EURUSD --start 2022-01-01 --end 2024-01-01

Loads data -> pre-flight (C1) -> full validation (C2/C4 + robustness) -> prints the
Part F report. Requires real tick/1m data; without it the harness has nothing to run.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..backtest.costs import CostModel
from ..config import load_config
from ..engine.params import EngineParams
from .driver import full_validation
from .preflight import preflight

DEFAULT_CONFIG = "config/nyam_sweep_fvg_v1.0.yaml"


def _load_frames(args):
    from ..data.load import build_frames, load_ohlcv_csv
    if args.csv:
        df1m = load_ohlcv_csv(args.csv)
        return build_frames(df1m)
    if args.dukascopy:
        from ..data.dukascopy import download_range
        from ..data.resample import ticks_to_bars
        start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
        ticks = download_range(args.dukascopy, start, end)
        return build_frames(ticks_to_bars(ticks, "1min"))
    raise SystemExit("provide --csv PATH or --dukascopy SYMBOL --start --end")


def main(argv=None):
    ap = argparse.ArgumentParser(description="NYAM-SWEEP-FVG validation runner")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--csv", help="1-minute OHLCV CSV")
    ap.add_argument("--dukascopy", help="symbol, e.g. EURUSD")
    ap.add_argument("--start", help="ISO date (dukascopy)")
    ap.add_argument("--end", help="ISO date (dukascopy)")
    ap.add_argument("--spread", type=float, default=0.8)
    ap.add_argument("--commission", type=float, default=7.0)
    ap.add_argument("--slippage", type=float, default=0.3)
    ap.add_argument("--no-robustness", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    params = EngineParams.from_config(cfg)
    df1m, df5, df1h = _load_frames(args)

    pf = preflight(df5, df1h, params)
    print("== C1 PRE-FLIGHT ==")
    for name, ok in pf.checks.items():
        print(f"  [{'x' if ok else ' '}] {name}: {pf.notes.get(name, '')}")
    if not pf.passed:
        raise SystemExit("pre-flight failed — fix before trusting any numbers")

    cm = CostModel(args.spread, args.commission, args.slippage)
    outcome = full_validation(
        df5, df1h, params, cm,
        data_start=df5.index[0], data_end=df5.index[-1], df1m=df1m,
        run_robustness_flag=not args.no_robustness,
    )
    print("\n== PART F ==")
    print(outcome.report)


if __name__ == "__main__":
    main()

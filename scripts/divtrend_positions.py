"""DIVTREND monthly forward-test runner.

Run this once a month (after refreshing the ETF CSVs in data/raw/etf/):
    python3 scripts/divtrend_positions.py

It (1) prints THIS MONTH's target positions at the LOCKED params, (2) appends
them to the forward log, and (3) reports realized forward performance vs the
backtest with the kill-switch. The forward test is the go-live gate — paper-trade
these for 6-12 months before any real capital.
"""
import sys
from pathlib import Path

sys.path.insert(0, "src")

from ictbot.config import load_config
from ictbot.portfolio.data import load_etf_dir, sleeves_for
from ictbot.portfolio.forward import append_forward_log, evaluate_forward, format_forward
from ictbot.portfolio.live import format_sheet, position_sheet, weights_asof
from ictbot.portfolio.params import DivtrendParams

ETF_DIR = sys.argv[1] if len(sys.argv) > 1 else "data/raw/etf"
LOG = "reports/divtrend_forward_log.json"


def locked_params():
    cfg = load_config("config/divtrend_v1.0.yaml")
    p = DivtrendParams.from_config(cfg)
    lk = cfg.raw.get("locked", {})
    return p.replace(**{k: p.clamp_free(k, v) for k, v in lk.items()})


def main():
    prices = load_etf_dir(ETF_DIR).dropna()
    sleeves = sleeves_for(prices.columns)
    p = locked_params()
    asof = prices.index[-1]

    sheet = position_sheet(prices, p, sleeves)
    print(format_sheet(sheet, asof))

    weights = weights_asof(prices, p, sleeves)
    log = append_forward_log(LOG, asof, weights)
    print(f"\nlogged {len(log)} monthly rebalance(s) to {LOG}")

    print()
    print(format_forward(evaluate_forward(prices, log)))


if __name__ == "__main__":
    main()

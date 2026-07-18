"""Phase 5 — fill models. The key property: the intrabar model resolves same-bar
SL-vs-TP ambiguity by 1-minute time order, where the bar model can only guess."""
import pandas as pd

from ictbot.engine.fills import BarFillModel, IntrabarFillModel


def _df1m(pairs, start="2024-01-16 13:30"):
    idx = pd.date_range(start, periods=len(pairs), freq="1min", tz="UTC")
    return pd.DataFrame({"high": [h for h, _ in pairs],
                         "low": [l for _, l in pairs]}, index=idx)


TS = pd.Timestamp("2024-01-16 13:30", tz="UTC")


def test_pre_tp1_ambiguous_bar_vs_intrabar():
    entry, sl, tp1 = 1.0011, 1.0000, 1.0030
    # 5m bar touches BOTH sl and tp1
    assert BarFillModel().pre_tp1(TS, 1.0031, 0.9999, entry, sl, tp1, "long") == "SL"
    # intrabar, TP1 comes first in time -> TP1
    m_tp_first = IntrabarFillModel(_df1m([(1.0031, 1.0025), (1.0012, 0.9999)]))
    assert m_tp_first.pre_tp1(TS, 1.0031, 0.9999, entry, sl, tp1, "long") == "TP1"
    # intrabar, SL comes first -> SL
    m_sl_first = IntrabarFillModel(_df1m([(1.0012, 0.9999), (1.0031, 1.0025)]))
    assert m_sl_first.pre_tp1(TS, 1.0031, 0.9999, entry, sl, tp1, "long") == "SL"


def test_wait_ran_to_tp_before_fill():
    ce, tp1, tick = 1.0011, 1.0030, 1e-5
    # bar model: both fill and reach touched -> fill priority
    assert BarFillModel().wait(TS, 1.0031, 1.0009, ce, tp1, tick, "long") == "FILL"
    # intrabar: price ran to TP1 before ever trading down to CE -> TP1_FIRST (missed)
    m = IntrabarFillModel(_df1m([(1.0031, 1.0025), (1.0012, 1.0009)]))
    assert m.wait(TS, 1.0031, 1.0009, ce, tp1, tick, "long") == "TP1_FIRST"
    # intrabar: fills first -> FILL
    m2 = IntrabarFillModel(_df1m([(1.0012, 1.0009), (1.0031, 1.0025)]))
    assert m2.wait(TS, 1.0031, 1.0009, ce, tp1, tick, "long") == "FILL"


def test_intrabar_falls_back_when_no_1m():
    m = IntrabarFillModel(_df1m([(1.0, 1.0)], start="2024-02-01 13:30"))
    # no 1m bars for this 5m ts -> behaves like the bar model
    assert m.pre_tp1(TS, 1.0031, 0.9999, 1.0011, 1.0000, 1.0030, "long") == "SL"

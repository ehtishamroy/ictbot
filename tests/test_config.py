"""Phase 0 sanity: the config loads and its guard-rails actually fire."""
from pathlib import Path

import pytest

from ictbot.config import ConfigError, load_config

CONFIG = Path(__file__).resolve().parents[1] / "config" / "nyam_sweep_fvg_v1.0.yaml"


def test_loads_and_defaults_in_range():
    cfg = load_config(CONFIG)
    assert cfg.name == "NYAM-SWEEP-FVG"
    assert cfg.version == "1.0"
    assert cfg.status == "UNTESTED"
    # all 7 free params, each default inside its own range (validated at load)
    assert len(cfg.free) == 7
    assert cfg.p("disp_mult") == 1.5


def test_out_of_range_default_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "strategy: {name: X, version: '1.0', status: UNTESTED}\n"
        "free_params:\n"
        "  disp_mult: {default: 9.0, range: [1.0, 2.5], def_id: DEF-DISP-01}\n"
    )
    with pytest.raises(ConfigError):
        load_config(bad)


def test_offset_must_be_fixed(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "strategy: {name: X, version: '1.0', status: UNTESTED}\n"
        "free_params:\n"
        "  server_to_ny_off_h: {default: 7, range: [5, 9], def_id: DEF-TIME-01}\n"
    )
    with pytest.raises(ConfigError):
        load_config(bad)

from pathlib import Path

import pytest

from crypto_carry.config import Config


def test_resume_rejects_other_strategy_and_scenario():
    from scripts.cost_capacity_guards import validate_resume

    config = Config()
    state = dict(scenario="C02", strategy="conditional")
    manifest = dict(config=config.to_dict(), code_hash="a", input_hashes={},
                    label="E4-costos-capacidad-C02",
                    strategies=[dict(strategy="permanent", funding_filter_enabled=False)])
    with pytest.raises(ValueError, match="strategy"):
        validate_resume(state, manifest, config, "a", {}, "C02", "conditional")
    manifest["strategies"] = [dict(strategy="conditional", funding_filter_enabled=True)]
    validate_resume(state, manifest, config, "a", {}, "C02", "conditional")
    state["scenario"] = "C03"
    with pytest.raises(ValueError, match="scenario"):
        validate_resume(state, manifest, config, "a", {}, "C02", "conditional")


def test_root_mismatch_rejected_before_data_read(tmp_path):
    from scripts.cost_capacity_guards import verify_input_root
    from scripts.return_capital.common import write_json

    write_json(tmp_path/"preservacion_previa.json", dict(data_root=str(tmp_path/"original")))
    with pytest.raises(ValueError, match="root"):
        verify_input_root(tmp_path, Path("elsewhere"), Config())


def test_h3_retries_are_preserved_in_separate_attempts(tmp_path):
    from scripts.cost_capacity_guards import export_attempt_h3

    rows = [dict(time_ns=0, symbol="BTCUSDT", complete=True, eligible=True, value=".004")]
    a = export_attempt_h3(tmp_path, "attempt1", "run_x", "C02", "conditional", rows)
    b = export_attempt_h3(tmp_path, "attempt2", "run_x", "C02", "conditional", rows)
    assert a != b
    assert a.read_bytes() == b.read_bytes()

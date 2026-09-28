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


def test_resume_accepts_authenticated_technical_revision_only():
    from scripts.cost_capacity_guards import validate_resume

    config = Config()
    state = dict(scenario="C02", strategy="conditional")
    manifest = dict(config=config.to_dict(), code_hash="economic", label="E4-costos-capacidad-C02",
        strategies=[dict(strategy="conditional", funding_filter_enabled=True)],
        input_hashes=dict(market="same", cost_capacity_protocol_sha256="old"))
    inputs = dict(market="same", cost_capacity_protocol_sha256="new")
    known = {"old": dict(engine_code_hash="economic"), "new": dict(engine_code_hash="economic")}
    validate_resume(state, manifest, config, "economic", inputs, "C02", "conditional", known)
    for other in ({"new": known["new"]}, {"old": dict(engine_code_hash="other"), "new": known["new"]}):
        with pytest.raises(ValueError):
            validate_resume(state, manifest, config, "economic", inputs, "C02", "conditional", other)
    manifest["input_hashes"]["market"] = "changed"
    with pytest.raises(ValueError):
        validate_resume(state, manifest, config, "economic", inputs, "C02", "conditional", known)


def test_os_lock_serializes_two_processes_for_same_pair(tmp_path):
    import subprocess
    import sys
    import time

    from scripts.run_historical_rules_sensitivity import writer_lock

    key, marker = tmp_path/"pair", tmp_path/"acquired"
    code = ("from pathlib import Path; from scripts.run_historical_rules_sensitivity import writer_lock; "
            "import sys; exec('with writer_lock(Path(sys.argv[1])):\\n    Path(sys.argv[2]).write_text(\"yes\")')")
    with writer_lock(key):
        child = subprocess.Popen([sys.executable, "-B", "-c", code, str(key), str(marker)],
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        time.sleep(.3)
        assert not marker.exists()
    assert child.wait(timeout=15) == 0
    assert marker.read_text() == "yes"

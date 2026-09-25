"""Runner orchestration fixtures: no market replay or economic simulation."""

import hashlib
import json
from contextlib import nullcontext
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from test_rules_sensitivity_reproduction import command, put, run, seal
from test_rules_sensitivity_reproduction import package as package

from crypto_carry.config import Config, timestamp

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/run_historical_rules_sensitivity.py"
SCENARIO = "FUT4_REALIZADA"


def load_runner(path=RUNNER):
    module = ModuleType("runner_orchestration_fixture")
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


@pytest.fixture
def orchestration(tmp_path, monkeypatch):
    module = load_runner()
    project, destination, data = (tmp_path / name for name in ("snapshot", "new-output", "data"))
    config = Config.load(ROOT / f"configs/entrega_4/reglas_historicas/{SCENARIO}.toml").changed(
        start="2022-08-01T00:00:00Z", end="2022-08-02T00:00:00Z"
    )
    relative = f"configs/entrega_4/reglas_historicas/{SCENARIO}.toml"
    put(project / relative, config.to_toml())
    put(destination / "protocolo_previo.json", {
        "files": {relative: hashlib.sha256((project / relative).read_bytes()).hexdigest()}
    })
    original_flags = {"verification": {"valid": True}, "code_hash_exact": True,
                      "config_exact": True, "dependencies_exact": True, "input_hashes_exact": True}
    put(destination / "verificacion_base_previa.json", {
        "input_hashes": {"fixture_only": "no_market_data"}, "runs": [original_flags, original_flags]
    })
    put(destination / "comparacion_extension_apagada.json", {"passed": True})
    put(destination / "verificacion_publicacion/verificacion_actual.json", {"passed": True})
    put(data / "outputs" / module.BASES["conditional"] / "data_quality.json", {"status": "complete"})
    state = SimpleNamespace(status="complete", finish=True, writer_calls=0, consumed=[])

    class ControlledReplay:
        def __init__(self, configuration, rules, strategy, funding_filter, inputs):
            self.config = configuration
            self.status = state.status
            self.now = timestamp(configuration.end) - (1 if state.finish else 2)
            self.reasons = ["controlled orchestration fixture"]
            self.ledger = SimpleNamespace(reconcile=lambda *args: {"difference": Decimal(0)})
            self.native_fill_count = 1
            self.fills = [{"fixture": True}]
            self.opportunities = []

        def run(self, records):
            state.consumed = list(records)

        def spot_prices(self):
            return {}

        def mark_prices(self):
            return {}

        def equity(self):
            return Decimal("-25") if self.status == "insolvent" else Decimal("10100")

    def controlled_writer(root, configuration, backtests, quality, data_kind, **kwargs):
        state.writer_calls += 1
        result = kwargs["output_root"] / "run_controlled_fixture"
        put(result / "run_manifest.json", {
            "status": backtests[0].status, "final_equity": str(backtests[0].equity()),
            "fixture": True, "data_root": str(root),
        })
        put(result / "equity_daily.csv", f"equity\n{backtests[0].equity()}\n")
        return result

    monkeypatch.setattr(module, "PROJECT", project)
    monkeypatch.setattr(module, "GapAuditedBacktest", ControlledReplay)
    monkeypatch.setattr(module, "iter_records", lambda *args, **kwargs: iter(["fixture-record"]))
    monkeypatch.setattr(module, "write_run", controlled_writer)
    monkeypatch.setattr(module, "_code_identity", lambda: ("controlled-frozen-code", {}))
    monkeypatch.setattr(module, "writer_lock", lambda *args: nullcontext())
    return module, destination, data, state


@pytest.mark.parametrize("status,equity", [("complete", "10100"), ("insolvent", "-25")])
def test_finished_trajectory_is_saved_with_its_actual_engine_status(orchestration, status, equity):
    module, destination, data, state = orchestration
    state.status = status
    result = module.run_one(destination, data, SCENARIO, "conditional")
    assert state.consumed == ["fixture-record"]
    assert state.writer_calls == 1
    assert result["status"] == "ejecutado"
    assert result["engine_status"] == status
    assert result["final_equity"] == equity
    artifact = destination / result["path"]
    assert json.loads((artifact / "run_manifest.json").read_text())["status"] == status
    assert (artifact / "equity_daily.csv").read_text() == f"equity\n{equity}\n"
    assert json.loads((destination / f"ejecuciones/{SCENARIO}__conditional.json").read_text()) == result
    assert (destination / "h3_minutos/run_controlled_fixture.csv").is_file()


@pytest.mark.parametrize("status,finish", [("incomplete_data", True), ("complete", False),
                                         ("insolvent", False)])
def test_incomplete_trajectory_is_rejected_before_artifact_writer(orchestration, status, finish):
    module, destination, data, state = orchestration
    state.status, state.finish = status, finish
    with pytest.raises(ValueError, match="Incomplete scenario"):
        module.run_one(destination, data, SCENARIO, "conditional")
    assert state.writer_calls == 0
    assert not (destination / "corridas").exists()
    assert not (destination / "ejecuciones").exists()


def test_relocated_helper_finds_project_via_imported_config(tmp_path):
    helper = tmp_path / "herramientas/run_historical_rules_sensitivity.py"
    helper.parent.mkdir()
    helper.write_bytes(RUNNER.read_bytes())
    relocated = load_runner(helper)
    assert relocated.PROJECT == ROOT


def test_reproduction_selects_the_authenticated_packaged_helper(package):
    source, data, destination = package
    helper = source / "herramientas/run_historical_rules_sensitivity.py"
    put(helper, "raise RuntimeError('prepare-only must not execute helper')\n")
    seal(source)
    result = run(command(source, data, destination))
    assert result.returncode == 0, result.stderr + result.stdout
    preparation = json.loads((destination / "reproduccion_preparacion.json").read_text())
    assert str(helper) in preparation["runner_command"]
    assert preparation["runner_identity"] == {
        "path": "herramientas/run_historical_rules_sensitivity.py",
        "sha256": hashlib.sha256(helper.read_bytes()).hexdigest(),
        "selection": "corrected_helper",
    }
    assert preparation["runner_cwd"] == str(source / "codigo_ejecutado")
    assert str(source / "codigo_ejecutado/src") in preparation["runner_pythonpath"]


def test_reproduction_rejects_helper_changed_after_sealing(package):
    source, data, destination = package
    helper = source / "herramientas/run_historical_rules_sensitivity.py"
    put(helper, "# authenticated fixture helper\n")
    seal(source)
    put(helper, "# altered after seal\n")
    result = run(command(source, data, destination))
    assert result.returncode != 0, "The selected helper must be authenticated before preparation"
    assert not destination.exists()

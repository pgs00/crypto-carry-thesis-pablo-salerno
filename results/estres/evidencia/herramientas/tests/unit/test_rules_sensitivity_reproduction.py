"""Small sealed fixtures exercise preparation without executing any backtest."""

import hashlib
import json
import platform
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/reproduce_historical_rules_sensitivity.py"
BASES = ("run_ad71d751b20623006c195ff3", "run_dfea4b7ac1475668d5968c97")
PREREQUISITES = ("protocolo_previo.json", "verificacion_base_previa.json",
                 "comparacion_extension_apagada.json", "verificacion_publicacion/verificacion_actual.json")


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal(source):
    members = [{"path": p.relative_to(source).as_posix(), "size": p.stat().st_size,
                "sha256": digest(p)} for p in sorted(source.rglob("*"))
               if p.is_file() and p.name not in {"manifiesto_paquete.json", "manifiesto_paquete.sha256"}]
    put(source / "manifiesto_paquete.json", {"schema": "rules_sensitivity_package_v1", "members": members})
    put(source / "manifiesto_paquete.sha256", digest(source / "manifiesto_paquete.json"))


@pytest.fixture
def package(tmp_path):
    source, data = tmp_path / "sealed", tmp_path / "data-root"
    snapshot = source / "codigo_ejecutado"
    # Fixture modules implement the actual frozen interfaces, without an engine.
    put(snapshot / "src/crypto_carry/__init__.py", "")
    put(snapshot / "src/crypto_carry/config.py", """
import json
from types import SimpleNamespace
class Config:
    @staticmethod
    def load(path):
        return SimpleNamespace(**json.loads(path.read_text()))
""")
    put(snapshot / "src/crypto_carry/data/__init__.py", "")
    put(snapshot / "src/crypto_carry/data/replay.py", """
import hashlib
def input_hashes(root, config):
    path = root / 'data/input.txt'
    return {'data/input.txt': hashlib.sha256(path.read_bytes()).hexdigest()}
""")
    put(snapshot / "src/crypto_carry/reporting.py", """
def verify_run(path):
    return {'valid': (path / 'run_manifest.json').is_file()}
def _dependencies():
    return {'fixture': '1'}
""")
    put(snapshot / "configs/entrega_4/reglas_historicas/BASE_E3.toml",
        {"data_dir": "data", "rules_file": "data/rules.json"})
    put(snapshot / "scripts/run_historical_rules_sensitivity.py",
        "raise RuntimeError('Tests must never start a batch')\n")
    put(source / "herramientas/verify_rules_sensitivity_package.py", """
import json,sys
from pathlib import Path
root = Path(sys.argv[sys.argv.index('--package') + 1])
valid = json.loads((root/'fixture_validation.json').read_text())['valid']
print(json.dumps({'status':'passed' if valid else 'failed'}))
raise SystemExit(0 if valid else 1)
""")
    put(source / "fixture_validation.json", {"valid": True})
    put(data / "data/input.txt", "exact market bytes\n")
    put(source / "codigo_base/src/crypto_carry/config.py", "historical base\n")
    code_files = {"src/crypto_carry/config.py": digest(source / "codigo_base/src/crypto_carry/config.py")}
    runs = []
    for run_id in BASES:
        run = data / "outputs" / run_id
        put(run / "run_manifest.json", {"code_files": code_files, "python": platform.python_version()})
        put(run / "data_quality.json", {"original": True})
        runs.append({"run_id": run_id, "manifest_sha256": digest(run / "run_manifest.json"),
                     "protected_files": {p.name: digest(p) for p in run.iterdir()}})
    put(source / "verificacion_base_previa.json",
        {"input_hashes": {"data/input.txt": digest(data / "data/input.txt")},
         "runs": runs, "current_dependencies": {"fixture": "1"}, "started_at": 123})
    for name in PREREQUISITES:
        if not (source / name).exists():
            put(source / name, {"passed": True, "original_timestamp": "2026-09-25T01:04:10Z"})
    seal(source)
    return source, data, tmp_path / "NEW-destination"


def command(source, data, destination, *extra):
    return [sys.executable, "-B", "-X", "utf8", str(SCRIPT), "--source-package", str(source),
            "--destination", str(destination), "--data-root", str(data), "--prepare-only", *extra]


def run(arguments):
    return subprocess.run(arguments, capture_output=True, text=True, encoding="utf-8", check=False)


def test_reproduction_utility_exists():
    assert SCRIPT.is_file(), "The sealed-source reproduction utility is missing"


def test_prepare_preserves_original_prerequisites_and_uses_frozen_source(package):
    source, data, destination = package
    before = {p.relative_to(source): digest(p) for p in source.rglob("*") if p.is_file()}
    result = run(command(source, data, destination, "--workers", "2"))
    assert result.returncode == 0, result.stderr + result.stdout
    for name in PREREQUISITES:
        assert (destination / name).read_bytes() == (source / name).read_bytes()
    fresh = json.loads((destination / "reproduccion_preparacion.json").read_text("utf-8"))
    assert fresh["data_verification"]["input_hashes_exact"] is True
    assert fresh["data_verification"]["python_version"] == platform.python_version()
    assert fresh["data_verification"]["python_exact"] is True
    assert len(fresh["data_verification"]["runs"]) == 2
    assert all(row["python_version"] == platform.python_version() and row["python_exact"] is True
               for row in fresh["data_verification"]["runs"])
    assert fresh["runner_command"][fresh["runner_command"].index("--workers") + 1] == "2"
    assert str(source / "codigo_ejecutado/scripts/run_historical_rules_sensitivity.py") in fresh["runner_command"]
    assert fresh["runner_identity"] == {
        "path": "codigo_ejecutado/scripts/run_historical_rules_sensitivity.py",
        "sha256": digest(source / "codigo_ejecutado/scripts/run_historical_rules_sensitivity.py"),
        "selection": "frozen_fallback",
    }
    assert not (destination / "corridas").exists()
    assert before == {p.relative_to(source): digest(p) for p in source.rglob("*") if p.is_file()}


@pytest.mark.parametrize("failure", ["unsealed", "bad_seal", "rejected_verifier", "changed_verifier",
                                    "market", "base", "base_code", "missing_base", "escape"])
def test_invalid_prerequisites_fail_before_creating_destination(package, failure):
    source, data, destination = package
    if failure == "unsealed":
        (source / "manifiesto_paquete.json").unlink()
    elif failure == "bad_seal":
        put(source / "manifiesto_paquete.sha256", "0" * 64)
    elif failure == "rejected_verifier":
        put(source / "fixture_validation.json", {"valid": False})
        seal(source)
    elif failure == "changed_verifier":
        put(source / "herramientas/verify_rules_sensitivity_package.py", "raise RuntimeError('must not execute')")
    elif failure == "market":
        put(data / "data/input.txt", "changed")
    elif failure == "base":
        put(data / "outputs" / BASES[0] / "data_quality.json", "changed")
    elif failure == "missing_base":
        (data / "outputs" / BASES[1] / "run_manifest.json").unlink()
    elif failure == "base_code":
        put(source / "codigo_base/src/crypto_carry/config.py", "different historical code")
        seal(source)
    else:
        audit = json.loads((source / "verificacion_base_previa.json").read_text())
        audit["input_hashes"]["../outside.txt"] = "0" * 64
        put(source / "verificacion_base_previa.json", audit)
        seal(source)
    result = run(command(source, data, destination))
    assert result.returncode != 0
    assert not destination.exists()


@pytest.mark.parametrize("mode", ["existing", "inside_source", "workers_zero", "workers_five"])
def test_destination_and_worker_guards(package, mode):
    source, data, destination = package
    extra = []
    if mode == "existing":
        destination.mkdir()
        put(destination / "user.txt", "preserve")
    elif mode == "inside_source":
        destination = source / "new"
    else:
        extra = ["--workers", "0" if mode == "workers_zero" else "5"]
    result = run(command(source, data, destination, *extra))
    assert result.returncode != 0
    if mode == "existing":
        assert (destination / "user.txt").read_text() == "preserve"
    else:
        assert not destination.exists()


@pytest.mark.parametrize("run_id", BASES)
def test_each_base_requires_the_current_exact_python_version(package, run_id):
    source, data, destination = package
    manifest_path = data / "outputs" / run_id / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["python"] = "0.0.0"
    put(manifest_path, manifest)
    audit_path = source / "verificacion_base_previa.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    record = next(row for row in audit["runs"] if row["run_id"] == run_id)
    record["manifest_sha256"] = digest(manifest_path)
    record["protected_files"]["run_manifest.json"] = digest(manifest_path)
    put(audit_path, audit)
    seal(source)
    result = run(command(source, data, destination))
    assert result.returncode != 0, "A BASE from another Python version was accepted"
    assert "Python version" in result.stderr and run_id in result.stderr
    assert not destination.exists()


@pytest.mark.parametrize("field", ["input_hashes_exact", "dependencies_exact"])
def test_successful_probe_exit_cannot_hide_failed_contract(package, monkeypatch, field):
    source, data, destination = package
    utility = runpy.run_path(str(SCRIPT))
    original_run = subprocess.run
    probe_result = {"input_hashes_exact": True, "dependencies_exact": True, "python_exact": True}
    probe_result[field] = False

    def malformed_probe(arguments, **kwargs):
        if "-c" in arguments:
            return subprocess.CompletedProcess(arguments, 0, json.dumps(probe_result), "")
        return original_run(arguments, **kwargs)

    monkeypatch.setattr(subprocess, "run", malformed_probe)
    with pytest.raises(ValueError, match="probe contract"):
        utility["prepare"](source, destination, data, 1)
    assert not destination.exists()

"""Authenticate block-4 dependencies and freeze the prespecified local protocol."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crypto_carry.config import Config  # noqa: E402
from crypto_carry.reporting import _code_identity, verify_run  # noqa: E402
from scripts.execution_delays import BASES, scenario_configs, validate_variant  # noqa: E402
from scripts.return_capital.common import read_json, write_json  # noqa: E402
from scripts.verify_rules_sensitivity_package import sha256  # noqa: E402

PREVIOUS = ROOT / "entregas/entrega_4/senal_entradas/20260927T170230Z"


def authenticate(work, data):
    refs = read_json(PREVIOUS / "autenticacion_referencias.json")
    refs.append(dict(dependency="block2", path=str(PREVIOUS / "paquete_20260927T185305Z")))
    refs.append(dict(dependency="block3_current", path=str(ROOT / "entregas/entrega_4/costos_capacidad/20260927T200204Z/paquete_20260927T231610Z")))
    checked = []
    for ref in refs:
        path = Path(ref["path"])
        manifest = read_json(path / "manifiesto_paquete.json")
        members = manifest.get("members", manifest.get("files"))
        if isinstance(members, dict):
            members = [dict(path=k, **v) if isinstance(v, dict) else dict(path=k, sha256=v)
                       for k, v in members.items()]
        errors = [m["path"] for m in members if sha256(path / m["path"]) != m["sha256"]]
        item = dict(dependency=ref["dependency"], path=str(path),
                    manifest_sha256=sha256(path / "manifiesto_paquete.json"),
                    files_checked=len(members), errors=errors, passed=not errors)
        checked.append(item)
        print(ref["dependency"], len(members), "errors", len(errors), flush=True)
    write_json(work / "autenticacion_referencias.json", checked)
    assert all(r["passed"] for r in checked)
    runs = []
    for strategy, rid in BASES.items():
        run = data / "outputs" / rid
        check = verify_run(run)
        assert check["valid"], check
        config = Config.load(run / "effective_config.toml")
        assert config.to_dict() == read_json(run / "run_manifest.json")["config"]
        runs.append(dict(strategy=strategy, run_id=rid, path=str(run), verification=check,
                         config=config.to_dict(), config_digest=config.digest(),
                         manifest_sha256=sha256(run / "run_manifest.json")))
    assert runs[0]["config"] == runs[1]["config"]
    write_json(work / "verificacion_base_previa.json", dict(runs=runs))
    inputs = read_json(PREVIOUS / "input_hashes.json")
    errors = []
    for n, wanted in inputs.items():
        if n.startswith("data/") and sha256(data / n) != wanted:
            errors.append(n)
    write_json(work / "verificacion_datos.json", dict(
        passed=not errors, files_checked=sum(n.startswith("data/") for n in inputs),
        errors=errors, semantic_manifest_identity_reused_from_authenticated_block2=True,
        scope="Every byte-addressed original input rehashed; no downloads or data writes"))
    assert not errors, errors
    write_json(work / "input_hashes.json", inputs)
    configs = scenario_configs(Config.from_dict(runs[0]["config"]))
    registry = []
    for name, config in configs.items():
        text = config.to_toml()
        (work / "configuraciones" / f"{name}.toml").write_text(text, encoding="utf8")
        target = ROOT / "configs/entrega_4/ejecucion_demoras" / work.name / f"{name}.toml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf8")
        for strategy in BASES:
            registry.append(dict(scenario=name, strategy=strategy,
                diff=validate_variant(Config.from_dict(runs[0]["config"]), name, config),
                route_identity_changes={}, selection_mode=config.research_decision_fee_mode,
                status="pendiente", config_digest=config.digest()))
    write_json(work / "registro_escenarios_previo.json", registry)
    print("Authenticated", len(inputs), "input identities; configs", len(configs), flush=True)


def freeze(work):
    if (work / "protocolo_previo.json").exists():
        raise FileExistsError("Execution identity is already frozen")
    names = ["scripts/execution_delays.py", "scripts/run_execution_delays.py",
             "scripts/execution_delays_guards.py",
             "scripts/signal_sensitivity.py", "scripts/run_historical_rules_sensitivity.py",
             "scripts/continuous_delivery/portfolio.py", "scripts/continuous_delivery/common.py"]
    code, files = _code_identity()
    for name in (*files, *names):
        destination = work / "codigo_ejecutado" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    package_names = ["protocolo.md", "encargo_usuario.md", "registro_escenarios_previo.json",
                     "input_hashes.json", "verificacion_base_previa.json", "verificacion_datos.json",
                     "control_compatibilidad.json"]
    package_names += ["controles/aprobacion_reparacion.md"]
    package_names += ["configuraciones/" + p.name for p in (work / "configuraciones").glob("*.toml")]
    write_json(work / "protocolo_previo.json", dict(
        created_at=datetime.now(UTC).isoformat(), engine_code_hash=code,
        code_files=files, project_files={n: sha256(ROOT / n) for n in names},
        package_files={n: sha256(work / n) for n in package_names}))
    print("FROZEN", code)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("D:/Backtesting"))
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        freeze(args.work.resolve())
    else:
        authenticate(args.work.resolve(), args.data_root.resolve())

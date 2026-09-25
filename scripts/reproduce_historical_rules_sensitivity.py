"""Verify a sealed source and external data, then reproduce into a NEW directory.

Offline package verification does not supply the external market data or the two
original BASE_E3 runs. --prepare-only performs all checks but starts no backtest.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

BASES = ("run_ad71d751b20623006c195ff3", "run_dfea4b7ac1475668d5968c97")
PREREQUISITES = (
    "protocolo_previo.json", "verificacion_base_previa.json",
    "comparacion_extension_apagada.json", "verificacion_publicacion/verificacion_actual.json",
)
VERIFIER = "herramientas/verify_rules_sensitivity_package.py"
HELPER = "herramientas/run_historical_rules_sensitivity.py"
FROZEN_RUNNER = "codigo_ejecutado/scripts/run_historical_rules_sensitivity.py"


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def safe_path(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise ValueError(f"Unsafe relative path: {relative!r}")
    member = PurePosixPath(relative)
    if (member.is_absolute() or PureWindowsPath(relative).drive or ".." in member.parts
            or member.as_posix() != relative):
        raise ValueError(f"Unsafe relative path: {relative!r}")
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root) or target == root:
        raise ValueError(f"Path escapes root {root}: {relative}")
    return target


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require_hash(path, expected):
    if not path.is_file():
        raise ValueError(f"Missing required file: {path}")
    if digest(path) != expected:
        raise ValueError(f"File hash mismatch: {path}")


def snapshot_environment(snapshot):
    return {**os.environ, "PYTHONPATH": str(snapshot / "src") + os.pathsep + str(snapshot),
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1", "MPLBACKEND": "Agg"}


def verify_source(source):
    """Require the seal, authenticate the verifier member, and run its full audit."""
    manifest_path = safe_path(source, "manifiesto_paquete.json")
    sidecar = safe_path(source, "manifiesto_paquete.sha256")
    if not manifest_path.is_file() or not sidecar.is_file():
        raise ValueError(f"Source package must be sealed before reproduction: {source}")
    require_hash(manifest_path, sidecar.read_text(encoding="ascii").strip())
    manifest = read(manifest_path)
    if manifest.get("schema") != "rules_sensitivity_package_v1":
        raise ValueError("Unexpected source package manifest schema")
    members = {}
    for row in manifest["members"]:
        name = row["path"]
        if name in members:
            raise ValueError(f"Duplicate source member: {name}")
        safe_path(source, name)
        members[name] = row
    if VERIFIER not in members:
        raise ValueError(f"Sealed portable verifier is missing: {VERIFIER}")
    verifier = safe_path(source, VERIFIER)
    require_hash(verifier, members[VERIFIER]["sha256"])
    command = [sys.executable, "-B", "-X", "utf8", str(verifier), "--package", str(source)]
    result = subprocess.run(command, cwd=source, capture_output=True, text=True,
                            encoding="utf-8", check=False,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"})
    if result.returncode:
        raise ValueError(f"Source package verification failed ({result.returncode}): "
                         f"{result.stdout}\n{result.stderr}")
    verification = json.loads(result.stdout)
    if verification.get("status") != "passed":
        raise ValueError(f"Source verifier did not pass: {verification}")
    return {"manifest_sha256": digest(manifest_path), "command": command,
            "result": verification}


def select_runner(source, source_check):
    """Prefer the sealed corrected helper; never fall back from an untrusted helper."""
    manifest_path = safe_path(source, "manifiesto_paquete.json")
    require_hash(manifest_path, source_check["manifest_sha256"])
    members = {row["path"]: row for row in read(manifest_path)["members"]}
    helper = safe_path(source, HELPER)
    relative = HELPER if HELPER in members or helper.exists() else FROZEN_RUNNER
    if relative not in members:
        raise ValueError(f"Selected runner is not authenticated by source manifest: {relative}")
    runner = safe_path(source, relative)
    require_hash(runner, members[relative]["sha256"])
    return runner, {"path": relative, "sha256": members[relative]["sha256"],
                    "selection": "corrected_helper" if relative == HELPER else "frozen_fallback"}


def audit_snapshot(source, data_root):
    """Run in a fresh subprocess using only the authenticated frozen engine."""
    source, data_root = Path(source).resolve(), Path(data_root).resolve()
    snapshot = safe_path(source, "codigo_ejecutado")
    sys.path.insert(0, str(snapshot / "src"))
    from crypto_carry import config as config_module
    from crypto_carry import reporting
    from crypto_carry.data import replay

    for module in (config_module, reporting, replay):
        if not Path(module.__file__).resolve().is_relative_to(snapshot / "src"):
            raise ValueError(f"Engine import escaped frozen snapshot: {module.__file__}")
    audit = read(safe_path(source, "verificacion_base_previa.json"))
    config = config_module.Config.load(
        safe_path(snapshot, "configs/entrega_4/reglas_historicas/BASE_E3.toml")
    )
    expected = audit["input_hashes"]
    if not expected:
        raise ValueError("Original audit contains no input hashes")
    # Reject path escapes before the frozen hasher opens any local dependency.
    for name in expected:
        if name != "processed_manifest_semantics":
            path = safe_path(data_root, name)
            if not path.is_file():
                raise ValueError(f"Missing required replay input: {path}")
    safe_path(data_root, config.rules_file)
    manifests = safe_path(data_root, config.data_dir) / "manifests"
    for name in ("processed.json", "download.json"):
        path = safe_path(data_root, (manifests / name).relative_to(data_root).as_posix())
        if not path.is_file():
            continue
        payload = read(path)
        if payload.get("mark_gap_derivation"):
            for key in ("original_manifest", "audit_path"):
                safe_path(data_root, payload["mark_gap_derivation"][key])
        for entry in payload.get("entries", []):
            for record in (entry, *entry.get("supplements", [])):
                for key in ("path", "checksum_path"):
                    if record.get(key):
                        safe_path(data_root, record[key])
    actual = replay.input_hashes(data_root, config)
    if actual != expected:
        differences = sorted(k for k in expected.keys() | actual.keys()
                             if expected.get(k) != actual.get(k))
        raise ValueError(f"Local replay input hashes differ: {differences}")
    if reporting._dependencies() != audit["current_dependencies"]:
        raise ValueError("Installed dependencies differ from the original verified environment")
    by_id = {row["run_id"]: row for row in audit["runs"]}
    if len(by_id) != 2 or set(by_id) != set(BASES) or len(audit["runs"]) != 2:
        raise ValueError("Original audit must identify both unique BASE_E3 runs")
    runs = []
    for run_id in BASES:
        run = safe_path(data_root, f"outputs/{run_id}")
        record = by_id[run_id]
        require_hash(run / "run_manifest.json", record["manifest_sha256"])
        if not record["protected_files"]:
            raise ValueError(f"Missing original run artifact hashes: {run_id}")
        for name, wanted in record["protected_files"].items():
            require_hash(safe_path(run, name), wanted)
        verification = reporting.verify_run(run)
        if not verification["valid"]:
            raise ValueError(f"External BASE_E3 failed verification: {run}: {verification}")
        manifest = read(run / "run_manifest.json")
        if manifest.get("python") != platform.python_version():
            raise ValueError(f"Python version differs for BASE_E3 {run_id}: "
                             f"expected {manifest.get('python')}, current {platform.python_version()}")
        if not manifest.get("code_files"):
            raise ValueError(f"External BASE_E3 lacks code_files: {run_id}")
        for name, wanted in manifest["code_files"].items():
            require_hash(safe_path(source / "codigo_base", name), wanted)
        runs.append({"run_id": run_id, "verification": verification,
                     "python_version": manifest["python"], "python_exact": True,
                     "manifest_sha256": digest(run / "run_manifest.json"),
                     "protected_files_checked": len(record["protected_files"]),
                     "base_code_files_checked": len(manifest["code_files"])})
    return {"checked_at_utc": now(), "data_root": str(data_root), "input_hashes_exact": True,
            "input_hashes_count": len(actual), "input_hashes": actual, "runs": runs,
            "dependencies_exact": True, "python_version": platform.python_version(),
            "python_exact": True, "frozen_src": str(snapshot / "src")}


def prepare(source, destination, data_root, workers):
    if Path(destination).exists() or Path(destination).is_symlink():
        raise ValueError(f"Destination must be NEW: {destination}")
    source, destination, data_root = (Path(p).resolve() for p in (source, destination, data_root))
    if workers not in range(1, 5):
        raise ValueError("Workers must be between 1 and 4")
    if destination.exists() or destination.is_relative_to(source):
        raise ValueError(f"Destination must be NEW and outside the source package: {destination}")
    if not destination.parent.is_dir():
        raise ValueError(f"Destination parent must already exist: {destination.parent}")
    source_check = verify_source(source)
    snapshot = safe_path(source, "codigo_ejecutado")
    runner, runner_identity = select_runner(source, source_check)
    environment = snapshot_environment(snapshot)
    probe = (
        "import json,runpy,sys; "
        "audit=runpy.run_path(sys.argv[1])['audit_snapshot']; "
        "print(json.dumps(audit(sys.argv[2],sys.argv[3])))"
    )
    command = [sys.executable, "-B", "-X", "utf8", "-c", probe,
               str(Path(__file__).resolve()), str(source), str(data_root)]
    verified = subprocess.run(command, cwd=snapshot, env=environment, capture_output=True,
                              text=True, encoding="utf-8", check=False)
    if verified.returncode:
        raise ValueError(f"External data/BASE verification failed: {verified.stderr}\n{verified.stdout}")
    data_check = json.loads(verified.stdout)
    if not isinstance(data_check, dict) or any(
        data_check.get(flag) is not True
        for flag in ("input_hashes_exact", "dependencies_exact", "python_exact")
    ):
        raise ValueError("Invalid external audit probe contract: all exact checks must be true")
    # Read all prerequisites before creating the destination; preserve bytes and dates.
    contents = {name: safe_path(source, name).read_bytes() for name in PREREQUISITES}
    runner_command = [sys.executable, "-B", "-X", "utf8", "-u", str(runner),
                      "--package", str(destination), "--data-root", str(data_root),
                      "--workers", str(workers)]
    record = {"schema": "rules_sensitivity_reproduction_v1", "prepared_at_utc": now(),
              "source_package": str(source), "destination": str(destination),
              "source_verification": source_check, "data_verification": data_check,
              "prerequisite_sha256": {name: hashlib.sha256(value).hexdigest()
                                       for name, value in contents.items()},
              "runner_command": runner_command, "runner_identity": runner_identity,
              "runner_cwd": str(snapshot),
              "runner_pythonpath": environment["PYTHONPATH"], "batch_executed": False,
              "scope": "Fresh validation; original audit dates preserved. No market data copied."}
    destination.mkdir(exist_ok=False)
    for name, content in contents.items():
        target = safe_path(destination, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(content)
    with (destination / "reproduccion_preparacion.json").open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return record, environment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-package", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("D:/Backtesting"))
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        record, environment = prepare(args.source_package, args.destination, args.data_root, args.workers)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"status": "prepared", "destination": record["destination"],
                      "runner_command": record["runner_command"],
                      "batch_executed": False}, ensure_ascii=False), flush=True)
    if args.prepare_only:
        return 0
    started = now()
    result = subprocess.run(record["runner_command"], cwd=record["runner_cwd"],
                            env=environment, check=False)
    execution = {"started_at_utc": started, "completed_at_utc": now(),
                 "command": record["runner_command"], "exit_code": result.returncode,
                 "status": "completed" if result.returncode == 0 else "failed"}
    with (Path(record["destination"]) / "reproduccion_ejecucion.json").open("x", encoding="utf-8") as stream:
        json.dump(execution, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

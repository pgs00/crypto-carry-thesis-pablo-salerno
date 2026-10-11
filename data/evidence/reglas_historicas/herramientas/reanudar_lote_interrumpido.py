"""Finish only missing runs, preserving completed artifacts and interrupted logs."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import verify_rules_sensitivity_package as verify


def now():
    return datetime.now(UTC).isoformat()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    args = parser.parse_args()
    package, project, data_root = (p.resolve() for p in (args.package, args.project, args.data_root))
    if (package / verify.MANIFEST).exists():
        raise ValueError("Cannot resume a sealed package")
    fresh = read(package / "verificaciones_finales/datos_antes_reanudacion.json")
    if fresh["status"] != "passed" or not all(
        fresh["data_audit"].get(k) is True
        for k in ("input_hashes_exact", "dependencies_exact", "python_exact")
    ):
        raise ValueError("Fresh validation must pass before resuming")
    index_path = package / "indice_corridas.json"
    index = read(index_path)
    records = index["runs"]
    complete = {(r["scenario"], r["strategy"]) for r in records}
    if len(complete) != len(records):
        raise ValueError("Duplicate existing run states")
    for record in records:
        verify.check_run(package, record)
    reference = next(r for r in records if r["scenario"] != "BASE_E3")
    manifest = read(package / reference["path"] / "run_manifest.json")
    for name, expected in manifest["code_files"].items():
        if digest(project / name) != expected:
            raise ValueError(f"Frozen executing code changed: {name}")
    runner = project / "scripts/run_historical_rules_sensitivity.py"
    if digest(runner) != digest(package / "codigo_ejecutado/scripts" / runner.name):
        raise ValueError("Frozen runner changed")
    scenarios = ("BTC_PROMO_REALIZADA", "BTC_PROMO_DECISION", "FUT4_REALIZADA", "FUT4_DECISION", "MARGEN_2X")
    pending = [(s, t) for s in scenarios for t in ("conditional", "permanent") if (s, t) not in complete]
    if len(pending) != 4:
        raise ValueError(f"This recovery is scoped to four interrupted jobs: {pending}")
    logs = package / "logs_reanudacion"
    logs.mkdir(exist_ok=False)
    preserved = package / "registro_interrupcion"
    preserved.mkdir(exist_ok=False)
    (preserved / "indice_antes.json").write_bytes(index_path.read_bytes())
    initial = dict(started_at_utc=now(), driver_pid=os.getpid(), original_attempt_exit_code=None,
                   interruption="User turn interruption; no Python processes remained when checked",
                   preserved_complete_records=len(records), resumed_pairs=pending,
                   original_logs={f.relative_to(package).as_posix(): digest(f)
                                  for f in sorted((package / "logs_corridas").glob("*.txt"))},
                   validation="verificaciones_finales/datos_antes_reanudacion.json")
    save(preserved / "reanudacion_inicio.json", initial)
    active = []
    for scenario, strategy in pending:
        log_path = logs / f"{scenario}__{strategy}.txt"
        log = log_path.open("x", encoding="utf-8")
        command = [sys.executable, "-B", "-u", "-X", "utf8", str(runner),
                   "--package", str(package), "--data-root", str(data_root),
                   "--scenario", scenario, "--strategy", strategy]
        process = subprocess.Popen(command, cwd=project, stdout=log, stderr=subprocess.STDOUT,
                                   env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "MPLBACKEND": "Agg"},
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        active.append((process, log, log_path, scenario, strategy, command))
        print(f"LAUNCHED {scenario}/{strategy} pid={process.pid}", flush=True)
    while active:
        for job in list(active):
            process, log, log_path, scenario, strategy, command = job
            code = process.poll()
            if code is None:
                continue
            log.close()
            active.remove(job)
            result_path = package / "ejecuciones" / f"{scenario}__{strategy}.json"
            if code == 0 and result_path.exists():
                record = read(result_path)
                verify.check_run(package, record)
            else:
                record = dict(scenario=scenario, strategy=strategy, status="fallido",
                              engine_status="failed", reason=f"Exit {code}; see {log_path.relative_to(package)}")
            record.update(command=command, exit_code=code, resumed_after_interruption=True,
                          log_path=log_path.relative_to(package).as_posix())
            records.append(record)
            save(index_path, index)
            print(f"FINISHED {scenario}/{strategy} exit={code}", flush=True)
        if active:
            time.sleep(2)
    result = 0 if len(records) == 12 and all(r["status"] in verify.SUCCESS for r in records) else 1
    save(preserved / "reanudacion_resultado.json",
         dict(completed_at_utc=now(), exit_code=result, final_records=len(records),
              original_logs_unchanged=all(digest(package / n) == h for n, h in initial["original_logs"].items())))
    return result


if __name__ == "__main__":
    raise SystemExit(main())

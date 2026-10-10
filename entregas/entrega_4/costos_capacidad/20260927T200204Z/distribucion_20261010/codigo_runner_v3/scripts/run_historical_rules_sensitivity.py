"""Execute the sealed first batch, preserving original runs and market data."""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from contextlib import contextmanager
from decimal import Decimal as D
from pathlib import Path

from crypto_carry.config import DAY, Config, iso, timestamp
from crypto_carry.data.prescribed import prescribed_rules, research_assumptions
from crypto_carry.data.replay import iter_records
from crypto_carry.mark_gap_study import GapAuditedBacktest
from crypto_carry.reporting import _code_identity, verify_run, write_run

PROJECT = Path(sys.modules[Config.__module__].__file__).resolve().parents[2]
VARIANTS = ("BTC_PROMO_REALIZADA", "BTC_PROMO_DECISION", "FUT4_REALIZADA", "FUT4_DECISION", "MARGEN_2X")
BASES = {"conditional": "run_ad71d751b20623006c195ff3", "permanent": "run_dfea4b7ac1475668d5968c97"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def check_protocol(package):
    seal = read(package / "protocolo_previo.json")
    for name, expected in seal["files"].items():
        path = (PROJECT / name).resolve()
        if not path.is_relative_to(PROJECT) or digest(path) != expected:
            raise ValueError(f"Predeclared protocol or configuration changed: {name}")
    audit = read(package / "verificacion_base_previa.json")
    if not all(r["verification"]["valid"] and r["code_hash_exact"] and r["config_exact"]
               and r["dependencies_exact"] and r["input_hashes_exact"] for r in audit["runs"]):
        raise ValueError("Archived BASE_E3 failed pre-change verification")
    if not read(package / "comparacion_extension_apagada.json")["passed"]:
        raise ValueError("Extension-off regression failed")
    if not read(package / "verificacion_publicacion/verificacion_actual.json")["passed"]:
        raise ValueError("Original publication is not verified")
    return audit


@contextmanager
def writer_lock(package):
    """Serialize dataframe/figure materialization to bound peak RAM."""
    token = hashlib.sha256(str(package).encode()).hexdigest()[:16]
    path = Path(tempfile.gettempdir()) / f"backtesting-e4-writer-{token}.lock"
    with path.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        if os.name == "nt":
            import msvcrt
            while True:
                stream.seek(0)
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(2)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def export_h3(package, run_id, scenario, strategy, opportunities):
    daily = defaultdict(lambda: [0, 0, 0, D(0)])
    for row in opportunities:
        values = daily[row["time_ns"] // DAY, row["symbol"]]
        values[0] += 1
        values[1] += int(row["complete"])
        values[2] += int(row["eligible"])
        values[3] += D(row["value"])
    target = package / "h3_minutos" / f"{run_id}.csv"
    target.parent.mkdir(exist_ok=True)
    with target.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "scenario", "strategy", "run_id", "date", "symbol", "minutos_totales",
            "minutos_conocidos", "minutos_desconocidos", "minutos_elegibles",
            "suma_forecast_elegible",
        ])
        writer.writeheader()
        for (day, symbol), (total, known, eligible, value) in sorted(daily.items()):
            writer.writerow(dict(scenario=scenario, strategy=strategy, run_id=run_id,
                                 date=iso(day * DAY)[:10], symbol=symbol,
                                 minutos_totales=total, minutos_conocidos=known,
                                 minutos_desconocidos=total - known, minutos_elegibles=eligible,
                                 suma_forecast_elegible=str(value)))


def run_one(package, data_root, scenario, strategy):
    audit = check_protocol(package)
    config = Config.load(PROJECT / "configs/entrega_4/reglas_historicas" / f"{scenario}.toml")
    baseline = data_root / "outputs" / BASES[strategy]
    quality = read(baseline / "data_quality.json")
    quality["research_assumptions"] = research_assumptions(config)
    quality["reused_market_validation"] = {
        "run_id": baseline.name,
        "data_quality_sha256": digest(baseline / "data_quality.json"),
        "input_hashes_verified": True,
        "scope": "same prices, funding, coverage and mark derivation; scenario-specific fees/margin",
    }
    inputs = dict(audit["input_hashes"],
                  sensitivity_protocol_sha256=digest(package / "protocolo_previo.json"),
                  sensitivity_runner_sha256=digest(Path(__file__)))
    code_before = _code_identity()[0]
    started = time.monotonic()
    print(f"START {scenario}/{strategy} code={code_before}", flush=True)
    b = GapAuditedBacktest(config, prescribed_rules(config), strategy, strategy == "conditional", inputs)
    b.run(iter_records(data_root, timestamp(config.start), timestamp(config.end),
                       config.window_hours + 24, data_dir=config.data_dir,
                       execution_model=config.execution_model, include_closed_bars=True,
                       mark_gap_method=config.mark_gap_method))
    replay_seconds = time.monotonic() - started
    if code_before != _code_identity()[0]:
        raise ValueError("Executing source changed while replay was running")
    if b.status not in {"complete", "insolvent"} or b.now != timestamp(config.end) - 1:
        raise ValueError(f"Incomplete scenario: {b.status}: {b.reasons}")
    difference = b.ledger.reconcile(b.spot_prices(), b.mark_prices())["difference"]
    if abs(difference) > config.accounting_tolerance:
        raise ArithmeticError(f"Final ledger reconciliation: {difference}")
    print(f"REPLAY_COMPLETE {scenario}/{strategy} seconds={replay_seconds:.2f}", flush=True)
    with writer_lock(package):
        run = write_run(data_root, config, [b], quality, "historical_assumptions",
                        label=f"E4-reglas-{scenario}", inputs=inputs, output_root=package / "corridas")
        if code_before != _code_identity()[0]:
            raise ValueError("Executing source changed during artifact construction")
        export_h3(package, run.name, scenario, strategy, b.opportunities)
    record = dict(scenario=scenario, strategy=strategy, status="ejecutado", engine_status=b.status,
                  run_id=run.name, path=run.relative_to(package).as_posix(),
                  manifest_sha256=digest(run / "run_manifest.json"), code_hash=code_before,
                  replay_seconds=replay_seconds, total_seconds=time.monotonic() - started,
                  final_equity=str(b.equity()), ledger_difference=str(difference),
                  native_fills=b.native_fill_count, fills=len(b.fills),
                  input_hashes_verified_again_at_batch_end=False)
    save(package / "ejecuciones" / f"{scenario}__{strategy}.json", record)
    print(json.dumps(record), flush=True)
    return record


def prepare(package, data_root):
    audit = check_protocol(package)
    records = []
    for strategy, run_id in BASES.items():
        source, target = data_root / "outputs" / run_id, package / "corridas" / run_id
        expected = next(r for r in audit["runs"] if r["run_id"] == run_id)
        for name, sha in expected["protected_files"].items():
            if digest(source / name) != sha:
                raise ValueError(f"Original base changed: {source / name}")
        if not target.exists():
            shutil.copytree(source, target)
        if not verify_run(target)["valid"]:
            raise ValueError(f"Invalid portable copy: {target}")
        records.append(dict(scenario="BASE_E3", strategy=strategy, status="reutilizado_verificado",
                            engine_status="complete", run_id=run_id,
                            path=target.relative_to(package).as_posix(),
                            manifest_sha256=digest(target / "run_manifest.json"),
                            original_path=str(source), reason="Exact code/config/dependencies/data/output verification before extension"))
    save(package / "indice_corridas.json", {"schema": "rules_sensitivity_batch_v1", "runs": records})
    return records


def batch(package, data_root, workers):
    records = prepare(package, data_root)
    tasks = [(scenario, strategy) for scenario in VARIANTS for strategy in BASES]
    active = []
    log_dir = package / "logs_corridas"
    log_dir.mkdir(exist_ok=True)
    while tasks or active:
        while tasks and len(active) < workers:
            scenario, strategy = tasks.pop(0)
            result_path = package / "ejecuciones" / f"{scenario}__{strategy}.json"
            if result_path.exists():
                prior = read(result_path)
                if prior["status"] == "ejecutado" and verify_run(package / prior["path"])["valid"]:
                    records.append(prior)
                    continue
                raise ValueError(f"Unverified existing task result: {result_path}")
            log = (log_dir / f"{scenario}__{strategy}.txt").open("x", encoding="utf-8")
            command = [sys.executable, "-B", "-u", "-X", "utf8", str(Path(__file__).resolve()),
                       "--package", str(package), "--data-root", str(data_root),
                       "--scenario", scenario, "--strategy", strategy]
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                     env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "MPLBACKEND": "Agg"})
            active.append((child, log, scenario, strategy, command))
            print(f"LAUNCHED {scenario}/{strategy} pid={child.pid}", flush=True)
        for job in list(active):
            child, log, scenario, strategy, command = job
            code = child.poll()
            if code is None:
                continue
            log.close()
            active.remove(job)
            path = package / "ejecuciones" / f"{scenario}__{strategy}.json"
            result = read(path) if code == 0 and path.exists() else dict(
                scenario=scenario, strategy=strategy, status="fallido", engine_status="failed",
                reason=f"Process exit {code}; see logs_corridas/{scenario}__{strategy}.txt",
            )
            result.update(command=command, exit_code=code)
            records.append(result)
            save(package / "indice_corridas.json", {"schema": "rules_sensitivity_batch_v1", "runs": records})
            print(f"FINISHED {scenario}/{strategy} exit={code} status={result['status']}", flush=True)
            gc.collect()
        if active:
            time.sleep(2)
    save(package / "indice_corridas.json", {"schema": "rules_sensitivity_batch_v1", "runs": records})
    return 0 if len(records) == 12 and all(r["status"] != "fallido" for r in records) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--scenario", choices=VARIANTS)
    parser.add_argument("--strategy", choices=tuple(BASES))
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 5))
    args = parser.parse_args()
    package, data_root = args.package.resolve(), args.data_root.resolve()
    if args.scenario:
        if not args.strategy:
            parser.error("--strategy is required for --scenario")
        run_one(package, data_root, args.scenario, args.strategy)
        return 0
    return batch(package, data_root, args.workers)


if __name__ == "__main__":
    raise SystemExit(main())

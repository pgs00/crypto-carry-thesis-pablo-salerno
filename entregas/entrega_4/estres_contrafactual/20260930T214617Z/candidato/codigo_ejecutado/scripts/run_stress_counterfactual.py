"""Execute the approved block-5 matrix serially, with immutable original runs."""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from crypto_carry.config import Config, timestamp  # noqa: E402
from crypto_carry.data.prescribed import prescribed_rules, research_assumptions  # noqa: E402
from crypto_carry.data.replay import input_hashes, iter_records  # noqa: E402
from crypto_carry.reporting import _code_identity, verify_run, write_run  # noqa: E402
from crypto_carry.serialization import decode, encode  # noqa: E402
from crypto_carry.stress_counterfactual import ScenarioBacktest, record_hash  # noqa: E402
from scripts.check_execution_delays_base import compare  # noqa: E402
from scripts.continuous_delivery.portfolio import financial_daily  # noqa: E402
from scripts.cost_capacity_ledger import audit_ledger  # noqa: E402
from scripts.prepare_stress_counterfactual import immutable_json  # noqa: E402
from scripts.return_capital.common import parquet, read_csv  # noqa: E402
from scripts.run_execution_delays import peak_memory_bytes  # noqa: E402
from scripts.run_historical_rules_sensitivity import export_h3, save, writer_lock  # noqa: E402
from scripts.stress_counterfactual_contract import (  # noqa: E402
    BASES,
    CONTROLS,
    SCENARIOS,
    STRATEGIES,
    authenticate_approval,
    authenticated_references,
    digest,
    load_spec,
    read,
)


def verify_contract(candidate):
    authenticate_approval(candidate)
    frozen = read(candidate / "protocolo_ejecucion.json")
    if _code_identity()[0] != frozen["engine_code_hash"]:
        raise ValueError("Frozen economic code changed")
    for name, expected in frozen["project_files"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("Frozen runner dependency changed: " + name)
    for name, expected in frozen["candidate_files"].items():
        if digest(candidate / name) != expected:
            raise ValueError("Frozen approved evidence changed: " + name)
    return frozen


def run_inputs(candidate, data, config, spec, *, rehash=True):
    expected = read(candidate / "input_hashes_etapa_b.json")
    if rehash and input_hashes(data, config) != expected:
        raise ValueError("Original market inputs changed")
    return dict(expected, stress_protocol_sha256=digest(candidate / "protocolo_ejecucion.json"),
                stress_scenario_sha256=record_hash(encode(spec)))


def validate_completed(state, candidate, data, scenario, strategy):
    authenticated_references(candidate, data)
    if state["status"] != "ejecutado":
        raise ValueError("A prior attempt is not complete")
    path = Path(state["path"])
    manifest = read(path / "run_manifest.json")
    config = Config.load(data / "outputs" / BASES[strategy] / "effective_config.toml")
    spec = load_spec(candidate, scenario)
    expected = run_inputs(candidate, data, config, spec, rehash=False)
    if (state["scenario"] != scenario or state["strategy"] != strategy
            or manifest["config"] != config.to_dict()
            or manifest["code_hash"] != _code_identity()[0]
            or manifest["input_hashes"] != expected
            or manifest["label"] != "E4-estres-contrafactual-" + scenario
            or manifest["strategies"] != [dict(strategy=strategy,
                                               funding_filter_enabled=strategy == "conditional")]
            or state["manifest_sha256"] != digest(path / "run_manifest.json")
            or not verify_run(path)["valid"]):
        raise ValueError("Completed run identity/integrity differs")
    evidence = read(Path(state["evidence_manifest"]))
    if digest(Path(state["evidence_manifest"])) != state["evidence_manifest_sha256"]:
        raise ValueError("Attempt evidence manifest changed")
    for name, expected_sha in evidence["files"].items():
        if digest(Path(state["evidence_manifest"]).parent / name) != expected_sha:
            raise ValueError("Attempt intervention evidence changed")
    return path


def compare_control(candidate, data, scenario):
    checks = []
    for ref in authenticated_references(candidate, data):
        strategy = ref["strategy"]
        state = read(candidate / "ejecuciones" / f"{scenario}__{strategy}.json")
        path = validate_completed(state, candidate, data, scenario, strategy)
        checks.append(dict(strategy=strategy, **compare(Path(ref["original_control_path"]), path)))
    result = dict(scenario=scenario, passed=all(r["passed"] for r in checks), comparisons=checks,
                  scope="Exact ordered eleven economic artifacts; only run_id and units excluded")
    if not result["passed"]:
        target = candidate / "controles" / f"discrepancia_{scenario}_{datetime.now(UTC):%Y%m%dT%H%M%S}.json"
        immutable_json(target, result)
        raise ValueError("BASE discrepancy: interpretation blocked; comparator cannot be replaced")
    return result


def gate_controls(candidate, data, scenario):
    required = CONTROLS if scenario in SCENARIOS else (
        ("CONTROL_APAGADO",) if scenario == "CONTROL_CERO" else ())
    for control in required:
        compare_control(candidate, data, control)


def export_observations(destination, backtest):
    tables = {
        "intervenciones.parquet": [dict(
            scenario=r["scenario"], kind=r["kind"], symbol=r["symbol"],
            open_time=r["open_time"], available_at=r["available_at"],
            original_record_sha256=r["original_record_sha256"],
            modified_record_sha256=r["modified_record_sha256"],
            source_record_sha256=r["source_record_sha256"],
            original_json=json.dumps(r["original"], sort_keys=True),
            modified_json=json.dumps(r["modified"], sort_keys=True),
            source_json=json.dumps(r["source_record"], sort_keys=True),
            factor=str(r["factor"]) if r["factor"] is not None else None,
            formula=r["formula"], units=r["units"])
            for r in backtest.interventions],
        "observaciones_ventanas.parquet": [dict(
            time_ns=r["time_ns"], before_json=json.dumps(r["before"], default=str, sort_keys=True),
            before_fills_json=json.dumps(r["before_fills"], default=str, sort_keys=True),
            after_fills_json=json.dumps(r["after_fills"], default=str, sort_keys=True),
            after_json=json.dumps(r["after"], default=str, sort_keys=True))
            for r in backtest.scenario_observations],
        "oportunidad_ventanas.parquet": [dict(
            time_ns=r["time_ns"], symbol=r["symbol"],
            evidence_json=json.dumps(r, default=str, sort_keys=True))
            for r in backtest.opportunity_observations],
    }
    for filename, rows in tables.items():
        if rows:
            table = pa.Table.from_pylist(rows)
        else:
            table = pa.table({"no_observations": pa.array([], type=pa.bool_())})
        pq.write_table(table, destination / filename, compression="zstd")
    immutable_json(destination / "estado_capa.json", dict(
        scenario=encode(backtest.scenario), factors=encode(backtest.scenario_factors),
        anchor_verified=backtest.anchor_verified,
        windows=backtest.scenario_intervals, intervention_rows=len(backtest.interventions),
        observation_rows=len(backtest.scenario_observations), no_randomness=True))


def scenario_quality(base, config, spec, candidate):
    quality = read(base / "data_quality.json")
    quality["research_assumptions"] = research_assumptions(config)
    quality["scenario_layer"] = dict(
        id=spec["id"], kind=spec["kind"], prices_official=False if spec["kind"] != "off" else None,
        approval_sha256=digest(candidate / "aprobacion_recibida.json"),
        source_validation_sha256=digest(candidate / "controles/fuentes_intervencion_etapa_b.json"),
        coverage_scope="Original coverage retained outside exact approved spot keys; each synthetic bar validated",
        future_mark_funding_rates_unchanged=True,
        liquidity="Observed gross 1% cap; CF uses approved preclosure spot median volume",
        publication="Every transformed minute becomes observable only at its original exclusive end")
    quality["original_coverage_reference"] = dict(
        run_id=base.name, sha256=digest(base / "data_quality.json"),
        explanation="Coverage entries authenticate original inputs, not observations of the hypothetical path")
    if spec["kind"] == "counterfactual":
        quality["original_documented_closures"] = quality["documented_closures"]
        quality["documented_closures"] = [c for c in quality["documented_closures"]
            if not (c["market"] == "spot" and c["start"] >= spec["start"]
                    and c["end"] <= spec["end"] and set(c["symbols"]) <= set(spec["anchors"]))]
        quality["scenario_layer"]["replaced_original_closure"] = True
    return quality


def run_one(candidate, data, raw_root, scenario, strategy):
    with writer_lock(candidate / "serial_replay"):
        frozen = verify_contract(candidate)
        for ref in authenticated_references(candidate, data):
            for reference in (data / "outputs" / BASES[ref["strategy"]],
                              Path(ref["original_control_path"])):
                if not verify_run(reference)["valid"]:
                    raise ValueError("Preserved reference artifact changed: " + str(reference))
        spec = load_spec(candidate, scenario)
        serialized = read(candidate / "especificaciones_ejecutables.json")[scenario]
        if spec != decode(serialized):
            raise ValueError("Executable scenario differs from approved translation")
        config = Config.load(data / "outputs" / BASES[strategy] / "effective_config.toml")
        inputs = run_inputs(candidate, data, config, spec)
        gate_controls(candidate, data, scenario)
        path = candidate / "ejecuciones" / f"{scenario}__{strategy}.json"
        if path.exists() and read(path)["status"] == "ejecutado":
            result = read(path)
            validate_completed(result, candidate, data, scenario, strategy)
            print("REUSED VERIFIED", scenario, strategy, flush=True)
            return result
        attempt = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        if path.exists():
            immutable_json(candidate / "ejecuciones" / f"{scenario}__{strategy}__prior_{attempt}.json", read(path))
        state = dict(scenario=scenario, strategy=strategy, technical_control=scenario in CONTROLS,
                     status="en_ejecucion", attempt=attempt, pid=os.getpid(),
                     started_utc=datetime.now(UTC).isoformat(), code_hash=frozen["engine_code_hash"],
                     config_hash=config.digest(), protocol_sha256=digest(candidate / "protocolo_ejecucion.json"))
        save(path, state)
        print("START", scenario, strategy, attempt, flush=True)
        started = time.monotonic()
        backtest = ScenarioBacktest(config, prescribed_rules(config), strategy,
                                    strategy == "conditional", inputs, scenario=spec)
        try:
            backtest.run(iter_records(data, timestamp(config.start), timestamp(config.end),
                config.window_hours + 24, data_dir=config.data_dir,
                execution_model=config.execution_model, include_closed_bars=True,
                mark_gap_method=config.mark_gap_method))
            elapsed = time.monotonic() - started
            peak = peak_memory_bytes()
            verify_contract(candidate)
            authenticated_references(candidate, data)
            if backtest.status == "complete" and backtest.now != timestamp(config.end) - 1:
                raise ValueError("Complete replay did not reach its exclusive end")
            daily, _ = financial_daily(backtest.daily, config)
            difference = backtest.ledger.reconcile(backtest.spot_prices(), backtest.mark_prices())["difference"]
            if abs(difference) > config.accounting_tolerance:
                raise ValueError("Final ledger reconciliation failed")
            if any(D(r["estimated_cycle_cost"]) != D(".0034") for r in backtest.signals
                   if r.get("estimated_cycle_cost") is not None):
                raise ValueError("Selection cost is not BASE 34 bp")
            print(f"REPLAY_COMPLETE status={backtest.status} seconds={elapsed:.2f} peak={peak}", flush=True)
            attempt_root = raw_root / scenario / strategy / attempt
            attempt_root.mkdir(parents=True, exist_ok=False)
            quality = scenario_quality(data / "outputs" / BASES[strategy], config, spec, candidate)
            run = write_run(data, config, [backtest], quality, "historical_assumptions",
                            label="E4-estres-contrafactual-" + scenario, inputs=inputs,
                            output_root=attempt_root)
            evidence = attempt_root / "evidencia_intervencion"
            evidence.mkdir(exist_ok=False)
            export_observations(evidence, backtest)
            export_h3(evidence, run.name, scenario, strategy, backtest.opportunities)
            audit = audit_ledger(config, parquet(run / "ledger.parquet"),
                                 read_csv(run / "equity_daily.csv"), parquet(run / "positions.parquet"))
            immutable_json(evidence / "conciliacion_ledger.json", audit)
            files = {p.relative_to(evidence).as_posix(): digest(p) for p in evidence.rglob("*") if p.is_file()}
            immutable_json(evidence / "manifiesto_evidencia.json", dict(
                scenario=scenario, strategy=strategy, run_id=run.name, files=files,
                run_manifest_sha256=digest(run / "run_manifest.json"),
                interpretation="Hypothetical continuous scenario; no calibrated changes after execution"))
            verify_contract(candidate)
            authenticated_references(candidate, data)
            result = dict(state, status="ejecutado", engine_status=backtest.status,
                run_id=run.name, path=str(run), manifest_sha256=digest(run / "run_manifest.json"),
                evidence_manifest=str(evidence / "manifiesto_evidencia.json"),
                evidence_manifest_sha256=digest(evidence / "manifiesto_evidencia.json"),
                h3_path=str(evidence / "h3_minutos" / f"{run.name}.csv"),
                replay_seconds=elapsed, total_seconds=time.monotonic() - started,
                peak_replay_bytes=peak, peak_process_bytes=peak_memory_bytes(),
                daily_reconciled=len(daily), max_daily_residual=str(max(
                    (abs(r["reconciliation_residual_usdt"]) for r in daily), default=D(0))),
                fills=len(backtest.fills), native_fills=backtest.native_fill_count,
                ledger_difference=str(difference), final_equity=str(backtest.equity()),
                intervention_rows=len(backtest.interventions), observation_rows=len(backtest.scenario_observations),
                finished_utc=datetime.now(UTC).isoformat())
            save(path, result)
            print(json.dumps(result), flush=True)
            return result
        except Exception as exc:
            save(path, dict(state, status="fallido", engine_status=backtest.status,
                            last_time_ns=backtest.now, fills=len(backtest.fills),
                            reason=f"{type(exc).__name__}: {exc}"))
            raise


def all_serial(candidate, data, raw_root):
    verify_contract(candidate)
    log_dir = candidate / "logs_corridas"
    log_dir.mkdir(exist_ok=True)
    for scenario in CONTROLS + SCENARIOS:
        for strategy in STRATEGIES:
            token = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            command = [sys.executable, "-B", "-u", "-X", "utf8", str(Path(__file__).resolve()),
                       "--candidate", str(candidate), "--data-root", str(data),
                       "--raw-root", str(raw_root), "--scenario", scenario, "--strategy", strategy]
            log_path = log_dir / f"{scenario}__{strategy}__{token}.txt"
            with log_path.open("x", encoding="utf-8") as log:
                print("LAUNCHED", scenario, strategy, str(log_path), flush=True)
                completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "MPLBACKEND": "Agg"})
            if completed.returncode:
                raise RuntimeError(f"Stopped after failed {scenario}/{strategy}; inspect {log_path}")
            print("FINISHED", scenario, strategy, flush=True)
        if scenario in CONTROLS:
            report = compare_control(candidate, data, scenario)
            target = candidate / "controles" / f"compatibilidad_{scenario}.json"
            if not target.exists():
                immutable_json(target, report)
        else:
            for strategy in STRATEGIES:
                state = read(candidate / "ejecuciones" / f"{scenario}__{strategy}.json")
                validate_completed(state, candidate, data, scenario, strategy)
        print("FAMILY CHECKED", scenario, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--data-root", type=Path, default=Path("D:/Backtesting"))
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--scenario", choices=CONTROLS + SCENARIOS)
    parser.add_argument("--strategy", choices=STRATEGIES)
    args = parser.parse_args()
    candidate, data, raw = args.candidate.resolve(), args.data_root.resolve(), args.raw_root.resolve()
    if args.all:
        all_serial(candidate, data, raw)
    elif args.scenario and args.strategy:
        run_one(candidate, data, raw, args.scenario, args.strategy)
    else:
        parser.error("Specify --all or both --scenario and --strategy")


if __name__ == "__main__":
    main()

"""Additional guards for the frozen block-2 runner and its evidence consumers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.return_capital.common import read_json
from scripts.signal_sensitivity import BASES
from scripts.verify_rules_sensitivity_package import safe_path, sha256


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def economic_identity(code_root):
    paths = list((code_root/"src").rglob("*.py"))
    paths.extend(p for p in (code_root/"pyproject.toml", code_root/"uv.lock") if p.is_file())
    return digest({p.relative_to(code_root).as_posix(): sha256(p) for p in sorted(paths)})


def validate_protocol(protocol, code_root, documents):
    if economic_identity(code_root) != protocol["engine_code_hash"]:
        raise ValueError("Economic code differs from predeclared protocol")
    for group, root in (("project_files", code_root), ("package_files", documents)):
        for name, wanted in protocol[group].items():
            if sha256(safe_path(root, name)) != wanted:
                raise ValueError(f"Predeclared protocol member changed: {group}/{name}")


def validate_run_identity(item, manifest):
    strategy = item["strategy"]
    if strategy not in BASES or manifest["strategies"] != [dict(
            strategy=strategy, funding_filter_enabled=strategy == "conditional")]:
        raise ValueError("Portfolio strategy or funding filter was relabelled")
    if item["engine_status"] != manifest["status"] or manifest["status"] not in {"complete", "insolvent"}:
        raise ValueError("Economic status differs from original manifest")
    expected_status = "reutilizado_verificado" if item["scenario"] == "BASE_E3" else "ejecutado"
    if item["status"] != expected_status or not manifest.get("artifacts_complete"):
        raise ValueError("Execution/reuse status does not match authenticated evidence")
    identity = {k: manifest[k] for k in ("config", "code_hash", "input_hashes", "strategies", "data_kind", "label")}
    expected_id = "run_"+digest(identity)[:24]
    if item["run_id"] != manifest["run_id"] or manifest["run_id"] != expected_id:
        raise ValueError("Run identifier differs from its economic identity")
    if manifest["data_kind"] != "historical_assumptions":
        raise ValueError("Historical research provenance changed")
    if item["scenario"] != "BASE_E3" and manifest["label"] != "E4-senal-"+item["scenario"]:
        raise ValueError("Scenario label changed")


def reject_overlaps(destination, protected):
    target = Path(destination).resolve()
    for value in protected:
        source = Path(value).resolve()
        if target.is_relative_to(source) or source.is_relative_to(target):
            raise ValueError(f"Destination overlaps protected source: {source}")


def reject_sealed_ancestor(destination):
    target = Path(destination).resolve()
    if any((parent/"manifiesto_paquete.json").exists() or (parent/"run_manifest.json").exists()
           for parent in target.parents):
        raise ValueError("Audit destination lies inside protected sealed evidence")


def stage_preflight(work, data_root, raw_root, project):
    """Invoke before each stage; frozen execution files remain byte-identical."""
    validate_protocol(read_json(work/"protocolo_previo.json"), project, work)
    if raw_root.resolve() != (data_root/"outputs/senal_entradas"/work.name).resolve():
        raise ValueError("Output root is outside the predeclared block-2 namespace")
    protected = [data_root/"outputs"/rid for rid in BASES.values()]
    protected += [Path(r["path"]) for r in read_json(work/"autenticacion_referencias.json")]
    protected += [data_root/"data"]
    reject_overlaps(raw_root, protected)
    for path in (work/"ejecuciones").glob("*.json"):
        item = read_json(path)
        if item.get("status") == "ejecutado":
            manifest = read_json(Path(item["path"])/"run_manifest.json")
            validate_run_identity(item, manifest)
            if manifest["code_hash"] != read_json(work/"protocolo_previo.json")["engine_code_hash"]:
                raise ValueError("Completed run differs from predeclared engine")
    return dict(passed=True, protocol_enforced=True, original_runner_unchanged=True)


def audit_completed_stage(work, stage):
    from crypto_carry.config import Config
    from crypto_carry.reporting import verify_run
    from scripts.return_capital.common import read_csv
    from scripts.signal_sensitivity import CHANGES
    from scripts.signal_sensitivity_report import compare_archived_metrics, financial_tables

    records, metrics = [], []
    for scenario in (s for s in CHANGES if s.startswith(stage)):
        for strategy in BASES:
            item = read_json(work/"ejecuciones"/f"{scenario}__{strategy}.json")
            run = Path(item["path"])
            manifest = read_json(run/"run_manifest.json")
            validate_run_identity(item, manifest)
            verified = verify_run(run)
            if not verified["valid"] or sha256(run/"run_manifest.json") != item["manifest_sha256"]:
                raise ValueError("Completed stage contains unauthenticated run")
            config = Config.load(run/"effective_config.toml")
            daily, _, periods = financial_tables(read_csv(run/"equity_daily.csv"), config)
            for archived in read_csv(run/"metrics.csv"):
                compare_archived_metrics(archived, next(r for r in periods if r["period"] == archived["period"]))
            records.append(dict(scenario=scenario, strategy=strategy, run_id=item["run_id"],
                                days_reconciled=len(daily), periods_reconciled=len(periods),
                                max_daily_residual=str(max(abs(r["reconciliation_residual_usdt"]) for r in daily)),
                                max_period_residual=str(max(abs(r["reconciliation_residual_usdt"]) for r in periods)),
                                raw_authentication=verified))
            metrics += [dict(scenario=scenario, strategy=strategy, run_id=item["run_id"], **r) for r in periods]
    if len(records) != 4:
        raise ValueError("Stage requires four completed portfolios")
    return dict(passed=True, stage=stage, runs=records, financial_metrics=metrics,
                h1_h3_independent_package_check="pending_final_package")


def main():
    import argparse

    from scripts.return_capital.common import write_json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--completed-stage", choices=["H", "V", "B"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reject_sealed_ancestor(args.output)
    if args.output.exists() or args.output.resolve().is_relative_to(args.data_root.resolve()):
        raise ValueError("Preflight audit must be new and outside source data")
    result = stage_preflight(args.work.resolve(), args.data_root.resolve(), args.raw_root.resolve(),
                             Path(__file__).resolve().parents[1])
    if args.completed_stage:
        result["completed_stage"] = audit_completed_stage(args.work, args.completed_stage)
    write_json(args.output, result)
    print(json.dumps(dict(passed=True, completed_stage=args.completed_stage)))


if __name__ == "__main__":
    main()

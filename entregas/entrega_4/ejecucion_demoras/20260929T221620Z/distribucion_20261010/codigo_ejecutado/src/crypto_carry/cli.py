"""Research commands; incomplete historical evidence is an explicit non-success status."""

import argparse
import json
import platform
import shutil
import sys
from collections import Counter
from importlib.metadata import version
from pathlib import Path

from .config import Config, timestamp
from .data.download import download
from .data.normalize import normalize
from .data.prescribed import prescribed_rules
from .data.replay import input_hashes, iter_records
from .data.rules import RuleBook, synthetic_rules
from .data.validate import validate_data
from .fixtures import demo_config, demo_records
from .strategy import Backtest


def write_run(*args, **kwargs):
    from .reporting import write_run as save

    return save(*args, **kwargs)


def _inside(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    if path == root or root not in path.parents:
        raise ValueError("Path must stay within the project root")
    return path


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m crypto_carry", description="Backtesting auditable de crypto carry"
    )
    p.add_argument("--root", default=".", help="Project directory (default: current directory)")
    commands = p.add_subparsers(dest="command", required=True)
    for name in (
        "doctor",
        "preflight",
        "download",
        "validate-data",
        "backtest",
        "robustness",
        "demo",
    ):
        sub = commands.add_parser(name)
        sub.add_argument(
            "--config",
            default="configs/robustness.toml" if name == "robustness" else "configs/base.toml",
        )
        if name in ("download", "validate-data"):
            sub.add_argument("--scope", choices=("sample", "full"), default="sample")
        if name == "validate-data":
            sub.add_argument(
                "--skip-normalize", action="store_true", help="Validate existing Parquet only"
            )
            sub.add_argument(
                "--clip-price-warmup",
                action="store_true",
                help="Normalize minute prices from required antecedents; keep full funding/mark warmup",
            )
        if name == "backtest":
            sub.add_argument(
                "--sample",
                action="store_true",
                help="Use configured sample dates, clearly labelled",
            )
            sub.add_argument(
                "--strategy", choices=("both", "conditional", "permanent"), default="both"
            )
            sub.add_argument(
                "--stop-at", help="UTC checkpoint cutoff, inclusive; no artificial close"
            )
            sub.add_argument(
                "--checkpoint-dir", help="New relative directory for immutable checkpoints"
            )
            sub.add_argument("--resume-dir", help="Resume from a prior checkpoint directory")
        if name == "robustness":
            sub.add_argument(
                "--scenario",
                action="append",
                help="Optional named subset; baseline always runs first",
            )
    sub = commands.add_parser("report")
    sub.add_argument("--run-id", required=True)
    sub = commands.add_parser("prepare-mark-gaps")
    sub.add_argument("--config", required=True)
    sub.add_argument("--method", choices=("futures_scaled", "last_official"), required=True)
    sub = commands.add_parser("continuous-mark-study")
    sub.add_argument("--config", required=True)
    sub = commands.add_parser("execution-revision")
    sub.add_argument("--early-config", required=True)
    sub.add_argument("--late-config", required=True)
    sub.add_argument("--sample", action="store_true", help="Run configured short samples first")
    sub.add_argument("--no-reuse-references", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.command == "execution-revision":
            from .execution_revision import run_execution_revision, verify_execution_revision

            path = run_execution_revision(
                root,
                Path(args.early_config).resolve(),
                Path(args.late_config).resolve(),
                reuse_references=not args.no_reuse_references,
                sample=args.sample,
            )
            verification = verify_execution_revision(path)
            print(
                json.dumps(
                    {
                        "revision_id": path.name,
                        "report": str(path / "execution_revision_report.md"),
                        "verification": verification,
                    },
                    ensure_ascii=False,
                )
            )
            return 0 if verification.get("status") == "complete" else 2
        if args.command == "report":
            if (
                not args.run_id
                or Path(args.run_id).name != args.run_id
                or any(c in args.run_id for c in "/\\:")
            ):
                raise ValueError("Invalid run-id")
            from .reporting import regenerate_report, verify_run

            path = _inside(root, "outputs/" + args.run_id)
            if (path / "revision_manifest.json").is_file():
                from .execution_revision import (
                    rebuild_execution_revision,
                    verify_execution_revision,
                )

                rebuilt = rebuild_execution_revision(root, path)
                result = verify_execution_revision(rebuilt)
                print(
                    json.dumps(
                        {
                            "report": str(rebuilt / "execution_revision_report.md"),
                            "verification": result,
                        },
                        ensure_ascii=False,
                    )
                )
                return 0 if result.get("status") == "complete" else 2
            manifest = json.loads((path / "run_manifest.json").read_text(encoding="utf-8"))
            if isinstance(manifest, dict) and manifest.get("kind") == "robustness_index":
                from .robustness import regenerate_robustness, verify_robustness

                report = regenerate_robustness(path)
                result = verify_robustness(path)
            else:
                report = regenerate_report(path)
                result = verify_run(path)
            print(json.dumps({"report": str(report), "verification": result}, ensure_ascii=False))
            return 0
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = root / config_path
        config = Config.load(config_path) if config_path.exists() else Config()
        if not config_path.exists() and args.command != "demo":
            raise FileNotFoundError(config_path)
        if args.command == "prepare-mark-gaps":
            from .data.mark_gaps import prepare_mark_gaps

            derived = prepare_mark_gaps(config, root, args.method)
            print(
                json.dumps(
                    {
                        "method": derived.mark_gap_method,
                        "config": str(root / derived.data_dir / "manifests/effective_config.toml"),
                        "status": "prepared_pending_full_validation",
                    }
                )
            )
            return 0
        if args.command == "continuous-mark-study":
            from .mark_gap_study import run_mark_gap_study, verify_mark_gap_study

            study = run_mark_gap_study(root, config)
            print(
                json.dumps(
                    {
                        "report": str(study / "mark_gap_report.md"),
                        "verification": verify_mark_gap_study(study),
                    }
                )
            )
            return 0
        if args.command == "preflight":
            from .preflight import preflight

            result = preflight(config, root)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "ready_for_validation" else 2
        if args.command == "doctor":
            import nautilus_trader

            used = sum(p.stat().st_size for p in (root / config.data_dir).rglob("*") if p.is_file())
            result = dict(
                status="complete",
                python=platform.python_version(),
                nautilus_trader=nautilus_trader.__version__,
                dependencies={
                    n: version(n) for n in ("numpy", "pandas", "pyarrow", "matplotlib", "httpx")
                },
                config_hash=config.digest(),
                data_budget_bytes=config.data_budget_bytes,
                data_bytes=used,
                project_root=str(root),
                free_workspace_bytes=shutil.disk_usage(root).free,
                historical_rules_present=(root / config.rules_file).exists(),
            )
            if Path("D:/").exists():
                result["free_D_bytes"] = shutil.disk_usage("D:/").free
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "download":
            if config.execution_model in ("minute_open", "next_minute_vwap"):
                from .data.minute_download import download_minutes

                if args.scope == "sample":
                    config = config.changed(
                        history_start=config.sample_start,
                        start=config.sample_start,
                        end=config.sample_end,
                    )
                result = download_minutes(config, root)
            else:
                result = download(config, root, scope=args.scope)
            counts = dict(Counter(e["status"] for e in result["entries"]))
            print(
                json.dumps(dict(counts=counts, bytes_used=result["bytes_used"], scope=args.scope))
            )
            return 1 if counts.get("failed", 0) else 0
        if args.command == "validate-data":
            if config.mark_gap_method != "strict" and not args.skip_normalize:
                raise ValueError("Derived mark layers must be validated with --skip-normalize")
            if not args.skip_normalize:
                if args.clip_price_warmup:
                    normalize(config, root, clip_price_warmup=True)
                else:
                    normalize(config, root)
            result = validate_data(config, root, scope=args.scope)
            print(
                json.dumps(
                    {k: result[k] for k in ("status", "scope", "start", "end", "issues")},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0 if result["status"] == "complete" else 2
        if args.command == "robustness":
            from .robustness import run_robustness

            path = run_robustness(root, config, selected=args.scenario)
            status = json.loads((path / "run_manifest.json").read_text(encoding="utf-8"))["status"]
            print(json.dumps(dict(run_id=path.name, status=status, report=str(path / "report.md"))))
            return 0 if status == "complete" else 2
        synthetic = args.command == "demo"
        if synthetic and config.analysis_mode == "prescribed_research":
            raise ValueError(
                "Use backtest with research configuration; demo requires its synthetic configuration"
            )
        if synthetic:
            config = demo_config(config)
            quality = dict(
                status="complete",
                historical=False,
                issues=[],
                coverage=[],
                start=timestamp(config.start),
                end=timestamp(config.end),
            )
            inputs = {"fixture": "synthetic:demo-v1"}
            rules = synthetic_rules(config)
            label = "demo-synthetic"
        else:
            if args.sample:
                quality = validate_data(config, root, scope="sample")
                config = config.changed(start=config.sample_start, end=config.sample_end)
            else:
                quality = validate_data(config, root, scope="full")
            inputs = input_hashes(root, config)
            rules = (
                prescribed_rules(config)
                if config.analysis_mode == "prescribed_research"
                else RuleBook.load(root / config.rules_file)
                if (root / config.rules_file).exists()
                else RuleBook([])
            )
            label = "sample" if args.sample else "baseline"
        results = []
        if quality["status"] == "complete":
            strategies = (("conditional", True), ("permanent", False))
            if not synthetic and args.strategy != "both":
                strategies = tuple(s for s in strategies if s[0] == args.strategy)
            for strategy, enabled in strategies:
                engine_class = Backtest
                if config.mark_gap_method != "strict":
                    from .mark_gap_study import GapAuditedBacktest

                    engine_class = GapAuditedBacktest
                b = (
                    engine_class.load_checkpoint(
                        _inside(root, args.resume_dir) / f"{strategy}.json", config, rules, inputs
                    )
                    if not synthetic and args.resume_dir
                    else engine_class(config, rules, strategy, enabled, inputs)
                )
                records = (
                    demo_records(config)
                    if synthetic
                    else iter_records(
                        root,
                        timestamp(config.start),
                        timestamp(config.end),
                        config.window_hours + 24,
                        data_dir=config.data_dir,
                        execution_model=config.execution_model,
                        include_closed_bars=config.signal_price_model == "closed_minute",
                        mark_gap_method=config.mark_gap_method,
                    )
                )
                b.run(
                    records,
                    stop_at=timestamp(args.stop_at) if not synthetic and args.stop_at else None,
                )
                if not synthetic and args.checkpoint_dir:
                    b.checkpoint(_inside(root, args.checkpoint_dir) / f"{strategy}.json")
                if (
                    not synthetic
                    and args.stop_at
                    and timestamp(args.stop_at) < timestamp(config.end) - 1
                ):
                    b.status = "incomplete_data"
                    b.reasons.append(
                        "Intentional checkpoint cutoff; requested evaluation not finished"
                    )
                    label = "checkpoint-prefix"
                results.append(b)
        data_kind = (
            "synthetic"
            if synthetic
            else "historical_assumptions"
            if config.analysis_mode == "prescribed_research"
            else "historical"
        )
        path = write_run(
            root,
            config,
            results,
            quality,
            data_kind=data_kind,
            label=label,
            inputs=inputs,
        )
        status = (
            "incomplete_data"
            if quality["status"] != "complete"
            else "insolvent"
            if any(b.status == "insolvent" for b in results)
            else "incomplete_data"
            if any(b.status != "complete" for b in results)
            else "complete"
        )
        print(
            json.dumps(
                dict(
                    run_id=path.name,
                    status=status,
                    data_kind=data_kind,
                    report=str(path / "report.md"),
                ),
                ensure_ascii=False,
            )
        )
        return 0 if status in ("complete", "insolvent") else 2
    except (OSError, ValueError, RuntimeError, ArithmeticError, KeyError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

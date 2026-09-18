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
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.command == "report":
            if (
                not args.run_id
                or Path(args.run_id).name != args.run_id
                or any(c in args.run_id for c in "/\\:")
            ):
                raise ValueError("Invalid run-id")
            from .reporting import regenerate_report, verify_run

            path = _inside(root, "outputs/" + args.run_id)
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
            result = download(config, root, scope=args.scope)
            counts = dict(Counter(e["status"] for e in result["entries"]))
            print(
                json.dumps(dict(counts=counts, bytes_used=result["bytes_used"], scope=args.scope))
            )
            return 1 if counts.get("failed", 0) else 0
        if args.command == "validate-data":
            if not args.skip_normalize:
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
                RuleBook.load(root / config.rules_file)
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
                b = (
                    Backtest.load_checkpoint(
                        _inside(root, args.resume_dir) / f"{strategy}.json", config, rules, inputs
                    )
                    if not synthetic and args.resume_dir
                    else Backtest(config, rules, strategy, enabled, inputs)
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
        path = write_run(
            root,
            config,
            results,
            quality,
            data_kind="synthetic" if synthetic else "historical",
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
                    data_kind="synthetic" if synthetic else "historical",
                    report=str(path / "report.md"),
                ),
                ensure_ascii=False,
            )
        )
        return 0 if status in ("complete", "insolvent") else 2
    except (OSError, ValueError, RuntimeError, ArithmeticError, KeyError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

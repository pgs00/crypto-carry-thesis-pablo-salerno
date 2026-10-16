"""Replay prepared data with the unchanged engine, or verify a saved run."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .config import Config, timestamp
from .data.prepared import verify_prepared_inputs
from .data.prescribed import prescribed_rules
from .data.replay import input_hashes, iter_records
from .data.rules import RuleBook
from .mark_gap_study import GapAuditedBacktest
from .reporting import verify_run, write_run
from .strategy import Backtest


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--root", default=".")
    commands = result.add_subparsers(dest="command", required=True)
    replay = commands.add_parser("backtest", help="Replay already prepared and validated data")
    replay.add_argument("--config", default="configs/reglas_historicas/BASE_E3.toml")
    replay.add_argument("--quality", help="Existing coverage JSON; defaults to the data manifests")
    replay.add_argument("--output", required=True, help="Output parent outside the retained evidence")
    replay.add_argument("--strategy", choices=("both", "conditional", "permanent"), default="both")
    verify = commands.add_parser("verify-run", help="Check a saved run's manifest and artifact hashes")
    verify.add_argument("run", type=Path)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.command == "verify-run":
            result = verify_run(args.run)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["valid"] else 1
        config_path = Path(args.config)
        config = Config.load(config_path if config_path.is_absolute() else root / config_path)
        quality_path = Path(args.quality) if args.quality else root / config.data_dir / "manifests/coverage.json"
        if not quality_path.is_absolute():
            quality_path = root / quality_path
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
        if quality.get("status") != "complete" or quality.get("issues"):
            raise ValueError("Prepared coverage evidence is incomplete")
        if (quality.get("start"), quality.get("end")) != (timestamp(config.start), timestamp(config.end)):
            raise ValueError("Prepared coverage does not match the requested period")
        if quality.get("analysis_mode") != config.analysis_mode:
            raise ValueError("Prepared coverage analysis mode differs from the configuration")
        if quality.get("mark_gap_method", "strict") != config.mark_gap_method:
            raise ValueError("Prepared mark-gap method differs from the configuration")
        rules = (prescribed_rules(config) if config.analysis_mode == "prescribed_research"
                 else RuleBook.load(root / config.rules_file))
        inputs = input_hashes(root, config)
        verify_prepared_inputs(root, config, quality, inputs)
        inputs["prepared_coverage"] = hashlib.sha256(quality_path.read_bytes()).hexdigest()
        engine = GapAuditedBacktest if config.mark_gap_method != "strict" else Backtest
        results = []
        for strategy in ("conditional", "permanent"):
            if args.strategy not in ("both", strategy):
                continue
            backtest = engine(config, rules, strategy, strategy == "conditional", inputs)
            backtest.run(iter_records(
                root, timestamp(config.start), timestamp(config.end), config.window_hours + 24,
                data_dir=config.data_dir, execution_model=config.execution_model,
                include_closed_bars=config.signal_price_model == "closed_minute",
                mark_gap_method=config.mark_gap_method,
            ))
            results.append(backtest)
        kind = "historical_assumptions" if config.analysis_mode == "prescribed_research" else "historical"
        run = write_run(root, config, results, quality, kind, inputs=inputs,
                        output_root=Path(args.output).resolve())
        result = verify_run(run)
        print(json.dumps(dict(run=str(run), **result), ensure_ascii=False, indent=2))
        return 0 if result["valid"] and result["status"] in {"complete", "insolvent"} else 2
    except (OSError, ValueError, RuntimeError, ArithmeticError, KeyError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

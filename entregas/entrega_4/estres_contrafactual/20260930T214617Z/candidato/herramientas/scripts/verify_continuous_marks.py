"""Verify saved continuous runs, original inputs and mark/risk evidence without replay."""

import argparse
import csv
import json
from collections import Counter
from decimal import Decimal as D
from pathlib import Path

import pyarrow.parquet as pq

from crypto_carry.config import DAY, Config, iso, timestamp
from crypto_carry.data.mark_gaps import (
    APPROVED_MINUTES,
    MINUTE,
    official_anchor,
    verify_mark_derivation,
)
from crypto_carry.data.prescribed import prescribed_rules
from crypto_carry.data.replay import _sha256
from crypto_carry.margin import margin_state
from crypto_carry.mark_gap_study import verify_mark_gap_study


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def portfolio_at_gap_times(root: Path, run: Path, config: Config, strategy: str) -> list[dict]:
    """Reconstruct both assets at gap boundaries from the saved ledger and marks.

    A minute-VWAP fill precedes risk checks. Ledger snapshots at these boundaries
    must agree with the last runtime check for each affected asset.
    """
    processed = json.loads(
        (root / config.data_dir / "manifests/processed.json").read_text(encoding="utf-8")
    )
    times = sorted({t for _, t in APPROVED_MINUTES})
    marks = {}
    for entry in processed["entries"]:
        if entry["dataset"] != "marks" or not any(
            entry["start"] <= t + MINUTE <= entry["end"] for t in times
        ):
            continue
        for row in pq.ParquetFile(root / entry["path"]).read().to_pylist():
            if row["open_time"] in times:
                key = (row["symbol"], row["open_time"])
                if key in marks:
                    raise ValueError("Duplicate mark for portfolio gap reconstruction")
                marks[key] = row
    ledger = pq.ParquetFile(run / "ledger.parquet").read().to_pylist()
    checks = pq.ParquetFile(run / "mark_gap_checks.parquet").read().to_pylist()
    events = pq.ParquetFile(run / "risk_events.parquet").read().to_pylist()
    rules = prescribed_rules(config)
    output = []
    for t in times:
        available = t + MINUTE
        for symbol in config.symbols:
            mark = marks[symbol, t]
            if mark["available_at"] != available:
                raise ValueError("Noncausal reconstructed portfolio valuation")
            prior = [r for r in ledger if r["symbol"] == symbol and r["time_ns"] <= available]
            last = prior[-1] if prior else {}
            position = {
                k: D(last.get(k) or "0") for k in ("spot", "short", "average", "collateral")
            }
            observed = [r for r in checks if r["symbol"] == symbol and r["time_ns"] == available]
            if observed and any(position[k] != D(observed[-1][k]) for k in position):
                raise ValueError("Reconstructed ledger position differs from runtime risk evidence")
            margin = (
                margin_state(
                    position["short"],
                    position["average"],
                    position["collateral"],
                    D(mark["close"]),
                    rules.get(symbol, "futures", available),
                    config,
                )
                if position["short"] > 0
                else {}
            )
            output.append(
                dict(
                    method=config.mark_gap_method,
                    strategy=strategy,
                    symbol=symbol,
                    open_time_utc=iso(t),
                    available_at_utc=iso(available),
                    **position,
                    mark_close=mark["close"],
                    mark_method=mark.get("estimation_method", "official"),
                    **margin,
                    runtime_position_match=bool(observed),
                    close_causes=[
                        r["cause"]
                        for r in events
                        if r["symbol"] == symbol
                        and r["time_ns"] == available
                        and r["kind"] == "close_requested"
                    ],
                    source="persisted_ledger_and_causal_mark",
                )
            )
    return output


def verify(root: Path, study: Path, portfolio_output: Path | None = None) -> dict:
    verification = verify_mark_gap_study(study)
    if not verification["valid"]:
        raise ValueError(verification)
    index = json.loads((study / "study_index.json").read_text(encoding="utf-8"))
    expected_pairs = {
        (m, s) for m in ("futures_scaled", "last_official") for s in ("conditional", "permanent")
    }
    pairs = {(r["method"], r["strategy"]) for r in index["runs"]}
    if pairs != expected_pairs or len(index["runs"]) != 4:
        raise ValueError("Study must contain exactly the four requested portfolios")
    original_config = index["identity"]["config"]
    start, end = timestamp(original_config["start"]), timestamp(original_config["end"])
    if (start, end) != (timestamp("2022-01-01T00:00:00Z"), timestamp("2026-09-01T00:00:00Z")):
        raise ValueError("Unexpected continuous evaluation period")
    hashed = {}
    checked_methods = set()
    results = []
    portfolio_rows = []
    funding_reference = None
    for item in index["runs"]:
        method, strategy = item["method"], item["strategy"]
        run = root / item["path"]
        manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
        config = Config.from_dict(manifest["config"])
        expected_config = Config.from_dict(original_config).changed(
            mark_gap_method=method, data_dir=f"{original_config['data_dir']}/derived_marks/{method}"
        )
        if config != expected_config or manifest["strategies"] != [
            {"strategy": strategy, "funding_filter_enabled": strategy == "conditional"}
        ]:
            raise ValueError("Run changes strategy or approved economic parameters")
        if manifest["status"] != "complete" or manifest["observed_range"]["end"] != iso(end - 1):
            raise ValueError("Run did not complete its uninterrupted evaluation interval")
        portfolio_rows.extend(portfolio_at_gap_times(root, run, config, strategy))
        for name, digest in manifest["input_hashes"].items():
            if name == "processed_manifest_semantics":
                continue
            path = (root / name).resolve()
            if not path.is_relative_to(root):
                raise ValueError("Input path escapes the data root")
            if path not in hashed:
                hashed[path] = _sha256(path)
            if hashed[path] != digest:
                raise ValueError(f"Input source changed: {name}")
        if method not in checked_methods:
            processed = json.loads(
                (root / config.data_dir / "manifests/processed.json").read_text(encoding="utf-8")
            )
            audit = verify_mark_derivation(config, root, processed)
            for row in audit:
                t, symbol = row["open_time"], row["symbol"]
                if (
                    row["anchor_open_time"] != official_anchor(symbol, t)
                    or row["available_at"] != t + MINUTE
                ):
                    raise ValueError("Noncausal estimate or drifting anchor")
                anchor_close = D(row["anchor_mark"]["close"])
                for field in ("open", "high", "low", "close"):
                    expected = (
                        anchor_close
                        if method == "last_official"
                        else (
                            D(row["current_future"][field])
                            * (anchor_close / D(row["anchor_future"]["close"]))
                        )
                    )
                    if D(row[field]) != expected:
                        raise ValueError("Estimated OHLC differs from the approved formula")
            checked_methods.add(method)
        daily = read_csv(run / "equity_daily.csv")
        if [int(r["time_ns"]) for r in daily] != list(range(start + DAY - 1, end, DAY)):
            raise ValueError("Missing daily valuation or annual reset/prefix")
        peak = D(config.capital)
        drawdown = D(0)
        for row in daily:
            equity = D(row["equity"])
            peak = max(peak, equity)
            drawdown = min(drawdown, equity / peak - 1)
        metric = next(r for r in read_csv(run / "metrics.csv") if r["period"] == "full")
        net_return = D(daily[-1]["equity"]) / config.capital - 1
        if abs(D(metric["net_return"]) - net_return) > D("1e-12") or abs(
            D(metric["max_drawdown"]) - drawdown
        ) > D("1e-12"):
            raise ValueError("Published return or daily drawdown differs from daily equity")
        checks = pq.ParquetFile(run / "mark_gap_checks.parquet").read().to_pylist()
        estimated = [r for r in checks if r["stage"] == "estimated"]
        if {(r["symbol"], int(r["mark_open_time"])) for r in estimated} != APPROVED_MINUTES:
            raise ValueError("Risk audit does not cover exactly the 15 estimated observations")
        for row in estimated:
            if int(row["mark_available_at"]) != int(row["mark_open_time"]) + MINUTE or int(
                row["time_ns"]
            ) < int(row["mark_available_at"]):
                raise ValueError("Risk used a candle before it was available")
            if D(row["short"]) > 0:
                balance = D(row["collateral"]) + D(row["short"]) * (
                    D(row["average"]) - D(row["mark_close"])
                )
                if balance != D(row["balance"]):
                    raise ValueError("Risk margin balance differs from the actual position")
        funding = json.loads((run / "funding_mark_audit.json").read_text(encoding="utf-8"))[
            "consumed"
        ]
        economic = [
            {k: v for k, v in r.items() if k not in ("strategy", "funding_filter_enabled")}
            for r in funding
            if r["economic_window"]
        ]
        if funding_reference is not None and economic != funding_reference:
            raise ValueError("Funding observations or proxy convention changed between portfolios")
        funding_reference = economic
        results.append(
            dict(
                method=method,
                strategy=strategy,
                days=len(daily),
                independent_net_return=str(net_return),
                independent_daily_drawdown=str(drawdown),
                risk_checks=len(checks),
                estimated_risk_checks=len(estimated),
                funding_methods=dict(Counter(r["settlement_mark_method"] for r in economic)),
                accounting_difference=item["accounting_difference"],
            )
        )
    if portfolio_output:
        portfolio_output.parent.mkdir(parents=True, exist_ok=True)
        fields = list(dict.fromkeys(k for row in portfolio_rows for k in row))
        with portfolio_output.open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(
                {k: json.dumps(v) if isinstance(v, list) else v for k, v in row.items()}
                for row in portfolio_rows
            )
    return dict(
        status="verified",
        study=study.name,
        source_files_verified=len(hashed),
        methods_recomputed=sorted(checked_methods),
        portfolio_positions_checked=len(portfolio_rows),
        portfolio_csv_sha256=_sha256(portfolio_output) if portfolio_output else None,
        runs=results,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--portfolio-output", type=Path)
    args = parser.parse_args()
    result = verify(args.root.resolve(), args.study.resolve(), args.portfolio_output)
    content = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        if args.output.exists() and args.output.read_text(encoding="utf-8") != content:
            raise ValueError("Verification evidence already exists with different bytes")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)


if __name__ == "__main__":
    main()

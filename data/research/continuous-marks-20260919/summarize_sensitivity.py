"""Recompute the compact sensitivity evidence without market data or a replay."""

import argparse
import csv
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def summarize(directory):
    checks = read_csv(directory / "gap_risk_checks.csv")
    positions = read_csv(directory / "portfolio_positions_during_gaps.csv")
    result = {}
    for strategy in ("conditional", "permanent"):
        paired = {}
        for method in ("futures_scaled", "last_official"):
            rows = [
                r
                for r in checks
                if r["method"] == method and r["strategy"] == strategy and r["stage"] == "estimated"
            ]
            paired[method] = {(r["time_ns"], r["symbol"]): r for r in rows}
            if len(rows) != 15 or len(paired[method]) != 15:
                raise ValueError("Expected exactly 15 distinct estimated risk checks")
        primary, alternative = paired["futures_scaled"], paired["last_official"]
        if primary.keys() != alternative.keys():
            raise ValueError("Methods cover different gap observations")
        deltas = {}
        for field in ("mark_close", "equity_before_risk", "ratio", "distance"):
            comparable = [
                (abs(D(row[field]) - D(alternative[key][field])), row)
                for key, row in primary.items()
                if row[field] != "" and alternative[key][field] != ""
            ]
            largest, row = max(comparable, key=lambda item: item[0])
            deltas[field] = {
                "max_absolute_difference": str(largest),
                "symbol": row["symbol"],
                "available_at_utc": row["timestamp_utc"],
            }
        decisions = (
            "state_before",
            "state_after",
            "risk_events",
            "pending_orders_before",
            "pending_orders_after",
            "liquidate",
            "preventive",
        )
        position_fields = ("spot", "short", "average", "collateral")
        portfolio = {
            method: {
                (r["open_time_utc"], r["symbol"]): r
                for r in positions
                if r["method"] == method and r["strategy"] == strategy
            }
            for method in paired
        }
        if (
            len(portfolio["futures_scaled"]) != 26
            or portfolio["futures_scaled"].keys() != portfolio["last_official"].keys()
        ):
            raise ValueError("Expected both assets at all 13 gap timestamps")
        controls = []
        for method, rows in portfolio.items():
            groups = sorted(
                {(r["symbol"], r["mark_method"]) for r in rows.values() if D(r["short"]) > 0}
            )
            for symbol, mark_method in groups:
                group = [
                    r
                    for r in rows.values()
                    if r["symbol"] == symbol
                    and r["mark_method"] == mark_method
                    and D(r["short"]) > 0
                ]
                controls.append(
                    {
                        "method": method,
                        "symbol": symbol,
                        "mark_method": mark_method,
                        "max_margin_ratio": str(max(D(r["ratio"]) for r in group)),
                        "min_liquidation_distance": str(min(D(r["distance"]) for r in group)),
                        "close_requests": sum(len(json.loads(r["close_causes"])) for r in group),
                    }
                )
        result[strategy] = {
            "estimated_checks_per_method": len(primary),
            "positions_per_method": len(portfolio["futures_scaled"]),
            "max_differences": deltas,
            "gap_decisions_identical": all(
                row[field] == alternative[key][field]
                for key, row in primary.items()
                for field in decisions
            ),
            "portfolio_positions_identical": all(
                row[field] == portfolio["last_official"][key][field]
                for key, row in portfolio["futures_scaled"].items()
                for field in position_fields
            ),
            "gap_risk_events": {
                method: sum(len(json.loads(r["risk_events"])) for r in rows.values())
                for method, rows in paired.items()
            },
            "controls": controls,
        }
    return result


def verify(directory, summary):
    manifest_path = directory / "evidence_manifest.json"
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if digest != (directory / "evidence_manifest.sha256").read_text().strip():
        raise ValueError("Evidence manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, expected in manifest["file_hashes"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Evidence path escapes its directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Evidence hash mismatch: {name}")
    source_path = directory / "source_study_manifest.json"
    source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if source_digest != (directory / "source_study_manifest.sha256").read_text().strip():
        raise ValueError("Original study manifest hash mismatch")
    provenance = json.loads((directory / "copy_provenance.json").read_text(encoding="utf-8"))
    for name, source in provenance.items():
        if manifest["file_hashes"][name] != source["sha256"]:
            raise ValueError(f"Copied source bytes changed: {name}")
    saved = json.loads((directory / "sensitivity_summary.json").read_text(encoding="utf-8"))
    if saved != summary:
        raise ValueError("Sensitivity summary differs from the saved evidence")
    return {
        "status": "verified",
        "files": len(manifest["file_hashes"]),
        "scope": "compact_evidence_and_recomputed_sensitivity",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    summary = summarize(args.directory)
    content = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    print(json.dumps(verify(args.directory, summary), indent=2) if args.verify else content)


if __name__ == "__main__":
    main()

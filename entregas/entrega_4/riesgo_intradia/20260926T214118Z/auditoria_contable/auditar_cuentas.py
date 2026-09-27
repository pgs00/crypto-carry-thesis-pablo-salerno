"""Read persisted accounting only; never invoke the simulator or write inputs.

Default output is JSON on stdout. --output writes only the explicitly named file,
which must be outside the preserved source package. Prices used here are the
original daily prices, so passing does not establish minute-price coverage.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tomllib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq

D = Decimal
RUNS = {
    "run_ad71d751b20623006c195ff3": ("BASE_E3", "conditional", "codigo_base"),
    "run_dfea4b7ac1475668d5968c97": ("BASE_E3", "permanent", "codigo_base"),
    "run_70383794701c4f0fc157b2ed": ("MARGEN_2X", "conditional", "codigo_ejecutado"),
    "run_3f5d9cce8ff1c2ba5447e3b6": ("MARGEN_2X", "permanent", "codigo_ejecutado"),
}
TABLES = (
    "ledger", "fills", "funding_payments", "positions", "orders",
    "risk_events", "signals", "renewal_diagnostics",
)
CASH = ("free_spot", "free_futures", "debt")
POSITION = ("spot", "short", "average", "collateral")
DERIVATION = {
    "equity": "free_spot + free_futures - debt; then for each configured symbol add collateral, spot*spot_reference, short*(average-mark) in that order",
    "margin_balance_B": "C + q*(a-m)",
    "maintenance_M": "q*m*tier.rate - tier.deduction",
    "tier_selection": "sort by (floor,cap), first floor <= notional <= cap; no quantize",
    "liquidation_price_L": "minimum valid (C+q*a+tier.deduction)/(q*(1+tier.rate)), requiring candidate>=0 and floor<=q*candidate<=cap",
    "liquidate": "q>0 and (B<=0 or B<=M or m>=L)",
    "preventive": "q>0 and (liquidate or M/B>=0.50 or (L-m)/m<0.15); B<=0 is unsafe",
    "maintenance_deficit": "max(0,M-B); equality is still liquidation boundary",
    "preventive_transfer_conditions": [
        "x>=0",
        "x>M(q*m)/0.50-B (strict)",
        "x>=q*m*0.15+M(q*m*1.15)-B (non-strict, continuous prescribed tiers)",
    ],
    "preventive_infimum": "max(0, ratio_lower_bound, distance_lower_bound); unattained if ratio binds at equality; do not silently add epsilon",
    "maintenance_tiers_base": {
        "BTCUSDT": [["0", "50000", "0.004", "0"], ["50000", "100000000", "0.01", "300"]],
        "ETHUSDT": [["0", "50000", "0.0065", "0"], ["50000", "100000000", "0.01", "175"]],
    },
    "margin_2x": "multiply rate AND deduction by 2; leverage stays 2",
    "liquidity": "max(0,free_spot+free_futures-sum(reservations)) only when reservation trajectory is verified; debt must be accounted for, no other-contract collateral or unsold spot",
    "reservation_assign": "accepted signals or actual renewal_rebalance: budget_required_cash from corresponding diagnostics",
    "reservation_decrement": "after full spot buy without deferred cancellation: max(0,reservation-order.quantity*latest_available_spot_close), not fill VWAP/price; partial fills do not decrement",
    "reservation_clear": "_complete_pair; successful _finish_close; _failed_first_adjustment; failed initial submission",
    "simultaneous_need": "sum needs at the same timestamp and phase; compare pooled free cash once; never sum peaks across times or minute deficits through time",
    "source_line_references": {
        "codigo_base/src/crypto_carry/ledger.py": ["29-53", "84-148", "150-366"],
        "codigo_base/src/crypto_carry/margin.py": ["12-83"],
        "codigo_base/src/crypto_carry/data/prescribed.py": ["29-85", "105-121"],
        "codigo_ejecutado/src/crypto_carry/data/prescribed.py": ["30-85"],
        "codigo_base/src/crypto_carry/strategy.py": ["202-207", "288-315", "458-509", "522-572", "622-659", "786-838", "1004-1094", "1182-1212"],
        "codigo_base/src/crypto_carry/reporting.py": ["498-574", "802-827"],
        "codigo_base/src/crypto_carry/diagnostics.py": ["152-205", "459-486", "515-518"],
    },
    "limits": [
        "This audit does not read the minute price sources; accounting integrity does not establish fresh market prices or complete minute-risk coverage.",
        "No global cross-table sequence column exists. The ledger's physical row ordinal is authoritative for financial mutations; original code supplies phase relationships to other tables.",
        "Reservation initial amounts are available but the entire reservation path is not verified here; do not claim all free cash is redistributable during commitments.",
        "Zero short: maintenance=0 and ratio/distance are not applicable; original helper can return numeric values but risk code bypasses closed contracts.",
        "Price targets outside maintenance coverage are non-evaluable, not extrapolated. Equal distance 0.15 passes; equal ratio 0.50 triggers preventive exit.",
        "No backtest, replay, prices download, original-source modification, or Git index mutation occurs.",
    ],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def strip_units(row: dict, keys: set[str]) -> dict:
    return {key: value for key, value in row.items() if key in keys and key != "units"}


def audit_run(package: Path, run_id: str) -> tuple[dict, dict[str, str]]:
    scenario, strategy, code_folder = RUNS[run_id]
    run = package / "corridas" / run_id
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    config = tomllib.loads((run / "effective_config.toml").read_text(encoding="utf-8"))
    tables = {name: pq.read_table(run / f"{name}.parquet").to_pylist() for name in TABLES}
    daily = read_csv(run / "equity_daily.csv")
    files = [run / f"{name}.parquet" for name in TABLES]
    files += [run / name for name in (
        "equity_daily.csv", "effective_config.toml", "research_assumptions.json",
        "run_manifest.json", "run_manifest.sha256",
    )]
    files += [package / code_folder / name for name in manifest["code_files"]]
    hashes_before = {path.relative_to(package).as_posix(): digest(path) for path in files}
    errors = []
    frozen_matches = {
        name: digest(package / code_folder / name) == expected
        for name, expected in manifest["code_files"].items()
    }
    outputs_match = {
        path.name: digest(path) == manifest["output_hashes"][path.name]
        for path in files if path.parent == run and path.name in manifest["output_hashes"]
    }
    if not all(frozen_matches.values()):
        errors.append("frozen_code_hash_mismatch")
    if not all(outputs_match.values()):
        errors.append("persisted_output_hash_mismatch")

    ledger = tables["ledger"]
    monotonic = all(a["time_ns"] <= b["time_ns"] for a, b in zip(ledger, ledger[1:]))
    unique = len({row["event_id"] for row in ledger}) == len(ledger)
    if not monotonic or not unique:
        errors.append("ledger_order_or_identity_invalid")
    keys = set(tables["funding_payments"][0]) if tables["funding_payments"] else set()
    funding_equal = [strip_units(row, keys) for row in ledger if row["kind"] == "funding"] == [
        strip_units(row, keys) for row in tables["funding_payments"]
    ]
    fill_ids = {f"fill:{row['fill_id']}" for row in tables["fills"]}
    ledger_fill_ids = {row["event_id"] for row in ledger if row["kind"] != "funding"}
    if not funding_equal or fill_ids != ledger_fill_ids:
        errors.append("financial_event_inventory_mismatch")

    symbols = config["symbols"]
    cash = {"free_spot": D(config["capital"]), "free_futures": D(0), "debt": D(0)}
    positions = {symbol: {key: D(0) for key in POSITION} for symbol in symbols}
    event_checks = []
    tolerance = D(config["accounting_tolerance"])
    for ordinal, row in enumerate(ledger):
        symbol, kind = row["symbol"], row["kind"]
        old = positions[symbol]
        new = {key: D(row[key]) for key in POSITION}
        dc = {key: D(row[key]) - cash[key] for key in CASH}
        collateral_delta = new["collateral"] - old["collateral"]
        financial_flow = dc["free_spot"] + dc["free_futures"] - dc["debt"] + collateral_delta
        quantity = D(row["quantity"]) if row["quantity"] is not None else D(0)
        price = D(row["price"]) if row["price"] is not None else D(0)
        fee = D(row["fee"])
        if kind == "funding":
            expected_flow = D(row["funding"])
            expected_spot, expected_short = old["spot"], old["short"]
        elif kind == "spot_buy":
            expected_flow = -quantity * price
            expected_spot = old["spot"] + quantity - D(row["base_fee_quantity"])
            expected_short = old["short"]
        elif kind == "spot_sell":
            expected_flow = quantity * price - fee
            expected_spot, expected_short = old["spot"] - quantity, old["short"]
        elif kind == "futures_sell":
            expected_flow = -fee
            expected_spot, expected_short = old["spot"], old["short"] + quantity
        elif kind == "futures_buy":
            expected_flow = quantity * (old["average"] - price) - fee - D(row["liquidation_fee"])
            expected_spot, expected_short = old["spot"], old["short"] - quantity
        else:
            raise ValueError(f"Unreviewed ledger kind: {kind}")
        residuals = [financial_flow - expected_flow, new["spot"] - expected_spot,
                     new["short"] - expected_short,
                     collateral_delta - D(row["collateral_change"])]
        for key, delta in dc.items():
            stored_key = {"free_spot": "cash_spot_change", "free_futures": "cash_futures_change",
                          "debt": "debt_change"}[key]
            if row[stored_key] is not None:
                residuals.append(delta - D(row[stored_key]))
        maximum = max(abs(value) for value in residuals)
        if maximum > tolerance:
            event_checks.append({"ordinal": ordinal, "event_id": row["event_id"],
                                 "max_residual": str(maximum)})
        for key in CASH:
            cash[key] = D(row[key])
        positions[symbol] = new
    if event_checks:
        errors.append("event_movement_reconciliation_failed")

    cash = {"free_spot": D(config["capital"]), "free_futures": D(0), "debt": D(0)}
    positions = {symbol: {key: D(0) for key in POSITION} for symbol in symbols}
    cursor = 0
    reconciliations = []
    for row in daily:
        moment = int(row["time_ns"])
        while cursor < len(ledger) and ledger[cursor]["time_ns"] <= moment:
            event = ledger[cursor]
            cash = {key: D(event[key]) for key in CASH}
            positions[event["symbol"]] = {key: D(event[key]) for key in POSITION}
            cursor += 1
        mismatches = {key: str(value - D(row[key])) for key, value in cash.items()
                      if value != D(row[key])}
        for symbol in symbols:
            mismatches.update({f"{symbol}_{key}": str(value - D(row[f"{symbol}_{key}"]))
                               for key, value in positions[symbol].items()
                               if value != D(row[f"{symbol}_{key}"])})
        equity = cash["free_spot"] + cash["free_futures"] - cash["debt"]
        for symbol in symbols:
            position = positions[symbol]
            equity += position["collateral"]
            equity += position["spot"] * D(row[f"{symbol}_spot_price"])
            equity += position["short"] * (position["average"] - D(row[f"{symbol}_mark"]))
        residual = equity - D(row["equity"])
        reconciliations.append({"time_ns": moment, "timestamp_utc": row["timestamp_utc"],
                                "original_equity": row["equity"], "derived_equity": str(equity),
                                "residual_usdt": str(residual), "account_mismatches": mismatches})
    if any(row["account_mismatches"] or abs(D(row["residual_usdt"])) > tolerance
           for row in reconciliations):
        errors.append("daily_reconciliation_failed")
    if cursor != len(ledger):
        errors.append("unconsumed_ledger_events_after_last_daily_close")

    groups = defaultdict(list)
    for row in ledger:
        groups[row["time_ns"]].append(row)
    accepted = [row for row in tables["signals"] if row["decision"] == "accepted"]
    rebalanced = [row for row in tables["renewal_diagnostics"] if row["state_after"] == "REBALANCING"]
    summary = {
        "run_id": run_id, "scenario": scenario, "strategy": strategy, "status": "pass" if not errors else "fail",
        "errors": errors, "initial_accounts": {"free_spot": config["capital"], "free_futures": "0", "debt": "0",
                                                   "positions": "zero quantities, average and collateral per configured symbol"},
        "range": [config["start"], config["end"]], "accounting_tolerance": str(tolerance),
        "source_code_folder": code_folder, "manifest_code_hash": manifest["code_hash"],
        "frozen_code_hash_matches": frozen_matches, "persisted_output_hash_matches": outputs_match,
        "row_counts": {key: len(value) for key, value in tables.items()},
        "daily_count": len(daily), "ledger_kind_counts": dict(Counter(row["kind"] for row in ledger)),
        "ledger_timestamps_monotonic": monotonic, "ledger_ids_unique": unique,
        "ledger_funding_subset_exact": funding_equal, "ledger_fill_ids_exact": fill_ids == ledger_fill_ids,
        "event_movement_failures": event_checks,
        "daily_account_mismatch_count": sum(len(row["account_mismatches"]) for row in reconciliations),
        "daily_equity_max_abs_residual_usdt": str(max(abs(D(row["residual_usdt"])) for row in reconciliations)),
        "all_ledger_consumed": cursor == len(ledger),
        "debt_nonzero_rows": sum(D(row["debt"]) != 0 for row in ledger),
        "negative_funding_rows": sum(D(row["amount_usdt"]) < 0 for row in tables["funding_payments"]),
        "collateral_changed_by_funding_rows": sum(D(row["collateral_change"]) != 0 for row in ledger if row["kind"] == "funding"),
        "simultaneous_ledger_groups": sum(len(group) > 1 for group in groups.values()),
        "simultaneous_funding_and_fill_groups": sum(len({row["kind"] == "funding" for row in group}) > 1 for group in groups.values()),
        "reservation_evidence": {"accepted_entries": len(accepted), "actual_rebalances": len(rebalanced),
                                 "missing_initial_budget_required_cash": sum(row["budget_required_cash"] is None for row in accepted + rebalanced),
                                 "full_reservation_trajectory_verified": False,
                                 "reason": "Requires source close at full spot fills plus order/transition phase merge; not performed by this accounting-only audit."},
        "daily_reconciliation": reconciliations,
    }
    return summary, hashes_before


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-package", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    package = args.source_package.resolve()
    if args.output is not None and args.output.resolve().is_relative_to(package):
        parser.error("Output may not be inside the preserved source package")
    summaries, inventory = [], {}
    for run_id in RUNS:
        summary, hashes = audit_run(package, run_id)
        summaries.append(summary)
        inventory.update(hashes)
    changes = [name for name, expected in inventory.items() if digest(package / name) != expected]
    result = {
        "schema": "intraday_accounting_audit_v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": [sys.executable, "-B", "-X", "utf8", *sys.argv],
        "source_package": str(package), "status": "pass" if not changes and all(row["status"] == "pass" for row in summaries) else "fail",
        "scope": "Persisted financial states, event algebra and original daily valuation only; no simulation, no minute prices, no drawdown calculation.",
        "formulas_sources_and_limits": DERIVATION,
        "sources_sha256": inventory, "source_changes_during_audit": changes,
        "total_daily_closes": sum(row["daily_count"] for row in summaries), "runs": summaries,
    }
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
        print(json.dumps({"status": result["status"], "output": str(args.output.resolve()),
                          "total_daily_closes": result["total_daily_closes"],
                          "source_changes": len(changes)}, ensure_ascii=False))
    else:
        print(serialized, end="")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

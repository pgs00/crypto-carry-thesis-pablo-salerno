"""Audit persisted revision runs without importing the engine or its financial helpers.

Recompute cash, inventory and funding using Decimal; check VWAP directly against
cached Binance ZIP rows and enforce one shared capacity per strategy/instrument.
"""

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import defaultdict
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext
from pathlib import Path

import pyarrow.parquet as pq

D = Decimal
MINUTE = 60_000_000_000
TOLERANCE = D("1e-8")


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def parquet_rows(path):
    return pq.read_table(path).to_pylist()


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            result.update(chunk)
    return result.hexdigest()


def source_bars(run, fills, issues):
    manifest = json.loads((run / "source_manifests/processed.json").read_text())
    parts = [row for row in manifest["entries"] if row["dataset"] == "minute_bars"]
    requests = defaultdict(set)
    hashes = {}
    keys = {}
    for fill in fills:
        part = next(
            row
            for row in parts
            if row["symbol"] == fill["symbol"]
            and row["market"] == fill["market"]
            and Path(row["source_path"]).name == fill["source_file"]
        )
        path = run.parents[1] / part["source_path"]
        requests[path].add(int(fill["window_start"]))
        hashes[path] = part["source_sha256"]
        keys[(fill["strategy"], fill["fill_id"])] = (path, int(fill["window_start"]))
    found = {}
    for path, wanted in requests.items():
        if digest(path) != hashes[path]:
            issues.append(f"Source ZIP checksum mismatch: {path}")
        with zipfile.ZipFile(path) as archive:
            name = next(name for name in archive.namelist() if name.endswith(".csv"))
            with archive.open(name) as binary:
                for row in csv.reader(io.TextIOWrapper(binary, encoding="utf-8")):
                    if not row or not row[0].isdigit():
                        continue
                    original_time = int(row[0])
                    start = original_time * (
                        1000 if original_time >= 100_000_000_000_000 else 1_000_000
                    )
                    if start in wanted:
                        found[(path, start)] = (D(row[5]), D(row[7]))
    return {key: found[source] for key, source in keys.items()}, len(requests)


def audit_run(run):
    manifest = json.loads((run / "run_manifest.json").read_text())
    config = manifest["config"]
    fills = parquet_rows(run / "fills.parquet")
    orders = {
        r["order_id"]: r
        for r in parquet_rows(run / "orders.parquet")
        if r["record_type"] == "final"
    }
    finals = {
        (r["strategy"], r["symbol"]): r
        for r in parquet_rows(run / "positions.parquet")
        if r["snapshot_kind"] == "final"
    }
    summaries = csv_rows(run / "run_summary.csv")
    payments = {
        (r["strategy"], r["symbol"], int(r["time_ns"])): r
        for r in parquet_rows(run / "funding_payments.parquet")
    }
    consumed = json.loads((run / "funding_mark_audit.json").read_text())["consumed"]
    rules = {
        (r["symbol"], r["market"]): r["values"]
        for r in json.loads((run / "research_assumptions.json").read_text())["rules"]
    }
    issues = []
    bars, source_count = (
        source_bars(run, fills, issues)
        if config["execution_model"] == "next_minute_vwap"
        else ({}, 0)
    )
    capacity = defaultdict(lambda: D(0))
    order_filled = defaultdict(lambda: D(0))
    for fill in fills:
        rule = rules[(fill["symbol"], fill["market"])]
        quantity, price, reference = (
            D(fill[key]) for key in ("quantity", "price", "reference_price")
        )
        side = fill["side"]
        slip = D(config["slippage"]) * D(config["cost_multiplier"])
        raw_price = reference * (1 + slip if side == "BUY" else 1 - slip)
        tick = D(rule["tick"])
        expected_price = (raw_price / tick).to_integral_value(
            rounding=ROUND_CEILING if side == "BUY" else ROUND_FLOOR
        ) * tick
        if expected_price != price:
            issues.append(f"Adverse price differs: {fill['fill_id']}")
        if D(fill["fee_rate"]) != D(rule["taker_fee"]) * D(config["cost_multiplier"]):
            issues.append(f"Fee rate differs: {fill['fill_id']}")
        if quantity % D(rule["step"]) or not D(rule["min_qty"]) <= quantity <= D(rule["max_qty"]):
            issues.append(f"Quantity filter differs: {fill['fill_id']}")
        if not D(rule["min_notional"]) <= quantity * price <= D(rule["max_notional"]):
            issues.append(f"Notional filter differs: {fill['fill_id']}")
        order = orders[fill["order_id"]]
        order_filled[fill["order_id"]] += quantity
        if order_filled[fill["order_id"]] > D(order["quantity"]):
            issues.append(f"Order overfill: {fill['fill_id']}")
        if bars:
            start = ((int(order["submitted_at"]) + MINUTE - 1) // MINUTE) * MINUTE
            if start != int(fill["window_start"]) or int(fill["time_ns"]) != start + MINUTE:
                issues.append(f"Noncausal window: {fill['fill_id']}")
            base, quote = bars[(fill["strategy"], fill["fill_id"])]
            if base <= 0 or abs(reference - quote / base) > D("1e-18"):
                issues.append(f"Source VWAP differs: {fill['fill_id']}")
            if base != D(fill["window_base_volume"]) or quote != D(fill["window_quote_volume"]):
                issues.append(f"Source volumes differ: {fill['fill_id']}")
            key = (fill["strategy"], fill["symbol"], fill["market"], start)
            capacity[key] += quantity
            if capacity[key] > base * D(config["max_volume_participation"]):
                issues.append(f"Shared volume capacity exceeded: {fill['fill_id']}")
            if (
                D(fill["remaining_quantity"])
                != D(order["quantity"]) - order_filled[fill["order_id"]]
            ):
                issues.append(f"Wrong remaining quantity: {fill['fill_id']}")
        elif not int(order["submitted_at"]) < int(fill["time_ns"]) < int(order["deadline"]):
            issues.append(f"Legacy timing differs: {fill['fill_id']}")

    results = []
    for summary in summaries:
        strategy = summary["strategy"]
        cash = D(summary["capital_usdt"])
        state = defaultdict(lambda: defaultdict(lambda: D(0)))
        events = [
            (int(r["funding_time"]), 0, r)
            for r in consumed
            if r["strategy"] == strategy and r["economic_window"]
        ]
        events += [(int(r["time_ns"]), 1, r) for r in fills if r["strategy"] == strategy]
        paid = 0
        for _, kind, row in sorted(
            events, key=lambda event: (event[0], event[1], event[2]["symbol"])
        ):
            position = state[row["symbol"]]
            if kind == 0:
                amount = (
                    position["short"] * D(row["funding_rate"]) * D(row["settlement_mark_price"])
                )
                actual = payments.get((strategy, row["symbol"], int(row["funding_time"])))
                if (amount and actual is None) or (
                    actual and abs(D(actual["amount_usdt"]) - amount) > TOLERANCE
                ):
                    issues.append(
                        f"Funding mismatch: {strategy}/{row['symbol']}/{row['funding_time']}"
                    )
                cash += amount
                position["funding"] += amount
                paid += bool(amount)
                continue
            quantity, price, rate = (D(row[key]) for key in ("quantity", "price", "fee_rate"))
            fee = quantity * price * rate
            position["fees"] += fee
            if row["market"] == "spot" and row["side"] == "BUY":
                net = quantity * (1 - rate)
                position["spot"] += net
                position["spot_cost"] += net * price
                cash -= quantity * price
            elif row["market"] == "spot":
                if quantity > position["spot"]:
                    issues.append(f"Spot oversell: {row['fill_id']}")
                basis = position["spot_cost"] * quantity / position["spot"]
                position["spot"] -= quantity
                position["spot_cost"] -= basis
                position["realized_spot"] += quantity * price - basis
                cash += quantity * price - fee
            elif row["side"] == "SELL":
                position["average"] = (
                    position["average"] * position["short"] + quantity * price
                ) / (position["short"] + quantity)
                position["short"] += quantity
                cash -= fee
            else:
                if quantity > position["short"]:
                    issues.append(f"Futures over-close: {row['fill_id']}")
                realized = quantity * (position["average"] - price)
                position["realized_futures"] += realized
                position["short"] -= quantity
                if not position["short"]:
                    position["average"] = D(0)
                liquidation_fee = (
                    quantity * price * D(rules[(row["symbol"], "futures")]["liquidation_fee"])
                    if row["liquidation"]
                    else D(0)
                )
                position["liquidation_fees"] += liquidation_fee
                cash += realized - fee - liquidation_fee
        equity, collateral = cash, D(0)
        for (owner, symbol), final in finals.items():
            if owner != strategy:
                continue
            position = state[symbol]
            for name in (
                "spot",
                "short",
                "average",
                "spot_cost",
                "realized_spot",
                "realized_futures",
                "funding",
                "fees",
                "liquidation_fees",
            ):
                if abs(position[name] - D(final[name])) > TOLERANCE:
                    issues.append(f"Terminal {name} mismatch: {strategy}/{symbol}")
            equity += position["spot"] * D(final["spot_price"]) + position["short"] * (
                position["average"] - D(final["mark_price"])
            )
            collateral += D(final["collateral"])
        cash_error = cash - (
            D(summary["free_spot"])
            + D(summary["free_futures"])
            + collateral
            - D(summary["debt_usdt"])
        )
        equity_error = equity - D(summary["final_equity_usdt"])
        if abs(cash_error) > TOLERANCE or abs(equity_error) > TOLERANCE:
            issues.append(f"Cash/equity does not reconcile: {strategy}")
        results.append(
            {
                "strategy": strategy,
                "equity_recomputed": str(equity),
                "cash_residual": str(cash_error),
                "equity_residual": str(equity_error),
                "funding_payments_checked": paid,
            }
        )
    return {
        "run_id": run.name,
        "manifest_sha256": digest(run / "run_manifest.json"),
        "fills_checked": len(fills),
        "source_zips_checked": source_count,
        "strategies": results,
        "issues": issues,
        "valid": not issues,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", type=Path)
    parser.add_argument("--run", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runs = args.run
    if args.revision:
        revision = json.loads((args.revision / "revision_manifest.json").read_text())
        runs += [Path(row["path"]) for row in revision["input_runs"]]
    if not runs:
        parser.error("Supply --revision or --run")
    with localcontext() as context:
        context.prec = 60
        results = [audit_run(run) for run in sorted(set(runs))]
    result = {
        "valid": all(r["valid"] for r in results),
        "tolerance_usdt": str(TOLERANCE),
        "auditor_sha256": digest(Path(__file__)),
        "runs": results,
    }
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

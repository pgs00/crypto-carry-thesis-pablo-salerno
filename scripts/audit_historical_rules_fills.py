"""Check persisted fill tariffs and ledger charges against the sealed protocol.

This reads Parquet with PyArrow, imports no trading engine, and creates only a
new requested JSON. It does not simulate or change any original artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path

import pyarrow.parquet as pq

START = 1657288800000000000  # 2022-07-08T14:00:00Z
END = 1679443200000000000  # 2023-03-22T00:00:00Z
MINUTE = 60_000_000_000
CHANGES = {
    "BASE_E3": {},
    "BTC_PROMO_REALIZADA": {
        "research_spot_fee_schedule": "btc_promo_2022_2023",
        "research_decision_fee_mode": "base_e3",
    },
    "BTC_PROMO_DECISION": {"research_spot_fee_schedule": "btc_promo_2022_2023"},
    "FUT4_REALIZADA": {
        "research_futures_taker_fee": "0.0004",
        "research_decision_fee_mode": "base_e3",
    },
    "FUT4_DECISION": {"research_futures_taker_fee": "0.0004"},
    "MARGEN_2X": {"research_maintenance_multiplier": "2"},
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def expected_fee(scenario, symbol, market, at):
    if scenario not in CHANGES or market not in {"spot", "futures"}:
        raise ValueError(f"Unknown protocol scope: {scenario}/{market}")
    if market == "futures":
        return D("0.0004") if scenario.startswith("FUT4_") else D("0.0005")
    if scenario.startswith("BTC_PROMO_") and symbol == "BTCUSDT" and START <= at < END:
        return D(0)
    return D("0.001")


def check_equal(actual, expected, label):
    if actual != expected:
        raise ValueError(f"{label}: {actual!r} != {expected!r}")


def self_checks():
    check_equal(datetime.fromtimestamp(START // 1_000_000_000, UTC).isoformat(),
                "2022-07-08T14:00:00+00:00", "start timestamp")
    check_equal(datetime.fromtimestamp(END // 1_000_000_000, UTC).isoformat(),
                "2023-03-22T00:00:00+00:00", "end timestamp")
    cases = [(START - 1, ".001"), (START, "0"), (END - 1, "0"), (END, ".001")]
    for at, expected in cases:
        check_equal(expected_fee("BTC_PROMO_DECISION", "BTCUSDT", "spot", at),
                    D(expected), "promotion boundary")
    check_equal(expected_fee("BTC_PROMO_REALIZADA", "ETHUSDT", "spot", START),
                D(".001"), "ETH exclusion")
    check_equal(expected_fee("BTC_PROMO_REALIZADA", "BTCUSDT", "futures", START),
                D(".0005"), "perpetual exclusion")
    check_equal(expected_fee("FUT4_REALIZADA", "ETHUSDT", "futures", START),
                D(".0004"), "four basis points")
    try:
        check_equal(D(".0004"), D(".0005"), "negative mutated tariff")
    except ValueError:
        return 10
    raise AssertionError("The mismatch guard accepted a mutated tariff")


def audit(package):
    cases = self_checks()
    index = read(package / "indice_corridas.json")["runs"]
    expected_pairs = {(s, t) for s in CHANGES for t in ("conditional", "permanent")}
    check_equal({(r["scenario"], r["strategy"]) for r in index}, expected_pairs, "batch scope")
    check_equal(len(index), 12, "unique batch states")
    base = next(r for r in index if r["scenario"] == "BASE_E3")
    base_config = read(package / base["path"] / "run_manifest.json")["config"]
    output = []
    for item in index:
        if item["status"] not in {"ejecutado", "reutilizado_verificado"}:
            raise ValueError(f"No fill audit for incomplete scenario: {item}")
        run = (package / item["path"]).resolve()
        if not run.is_relative_to(package):
            raise ValueError(f"Run escapes package: {run}")
        manifest = read(run / "run_manifest.json")
        check_equal(digest(run / "run_manifest.json"), item["manifest_sha256"], "run manifest")
        check_equal(manifest["config"], base_config | CHANGES[item["scenario"]], "effective config")
        for name in ("fills.parquet", "ledger.parquet"):
            check_equal(digest(run / name), manifest["output_hashes"][name], name)
        fills = pq.read_table(run / "fills.parquet").to_pylist()
        ledger = pq.read_table(run / "ledger.parquet").to_pylist()
        by_event = {"fill:" + r["fill_id"]: r for r in fills}
        check_equal(len(by_event), len(fills), "unique fill ids")
        inventory, seen, counts = {}, set(), Counter()
        fee_total, base_fees = D(0), {s: D(0) for s in ("BTCUSDT", "ETHUSDT")}
        for row in ledger:
            symbol = row["symbol"]
            if symbol not in base_fees:
                continue
            previous = inventory.get(symbol, D(0))
            if row["event_id"] in by_event:
                fill = by_event[row["event_id"]]
                if row["event_id"] in seen:
                    raise ValueError(f"Duplicate ledger fill: {row['event_id']}")
                seen.add(row["event_id"])
                check_equal(row["symbol"], fill["symbol"], "ledger symbol")
                check_equal(row["time_ns"], fill["time_ns"], "ledger fill time")
                check_equal(fill["execution_model"], "next_minute_vwap", "execution model")
                check_equal(fill["window_end"] - fill["window_start"], MINUTE, "full minute")
                check_equal(fill["time_ns"], fill["window_end"], "booking time")
                fee = expected_fee(item["scenario"], symbol, fill["market"], fill["window_start"])
                quantity, price = D(fill["quantity"]), D(fill["price"])
                check_equal(D(fill["fee_rate"]), fee, "realized rate")
                check_equal(D(fill["slippage_rate"]), D(".0001"), "slippage unchanged")
                check_equal(D(fill["max_volume_participation"]), D(".01"), "capacity unchanged")
                check_equal(D(row["fee"]), quantity * price * fee, "one ledger fee")
                check_equal(D(row["quantity"]), quantity, "ledger gross quantity")
                is_spot_buy = fill["market"] == "spot" and fill["side"] == "BUY"
                asset = symbol.removesuffix("USDT") if is_spot_buy else "USDT"
                check_equal(row["fee_asset"], asset, "fee currency")
                if is_spot_buy:
                    check_equal(D(row["base_fee_quantity"]), quantity * fee, "base units fee")
                    check_equal(D(row["spot"]) - previous, quantity * (1 - fee), "net spot units")
                    base_fees[symbol] += quantity * fee
                elif fill["market"] == "spot":
                    check_equal(D(row["spot"]) - previous, -quantity, "spot sale units")
                else:
                    check_equal(D(row["spot"]), previous, "futures preserve spot units")
                fee_total += D(row["fee"])
                counts[f"{symbol}/{fill['market']}/fee={fee}"] += 1
                counts["liquidation_fills"] += int(fill["liquidation"])
                for boundary, name in ((START, "start"), (END, "end")):
                    counts[f"window_crosses_{name}"] += int(fill["window_start"] < boundary < fill["window_end"])
                    counts[f"booking_equals_{name}"] += int(fill["time_ns"] == boundary)
            else:
                check_equal(D(row.get("fee") or "0"), D(0), "no extra ordinary fee outside fills")
            inventory[symbol] = D(row["spot"])
        check_equal(seen, set(by_event), "one ledger booking for every fill")
        output.append(dict(scenario=item["scenario"], strategy=item["strategy"],
                           run_id=item["run_id"], fills_checked=len(fills),
                           config_exactly_matches_predeclared_change=True,
                           tariffs_and_unique_ledger_fees_exact=True,
                           spot_net_units_exact=True, fee_total_usdt=str(fee_total),
                           base_fee_quantities={k: str(v) for k, v in base_fees.items()},
                           counts=dict(sorted(counts.items()))))
    return dict(status="passed", checked_at_utc=datetime.now(UTC).isoformat(),
                self_checks=cases, runs=output,
                scope="Persisted fills and ledger, independently prescribed tariffs; no engine import",
                limitations="Does not independently reconstruct market prices or the native engine account")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = audit(args.package.resolve())
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(dict(status=result["status"], runs=len(result["runs"]),
                          fills_checked=sum(r["fills_checked"] for r in result["runs"]))))


if __name__ == "__main__":
    main()

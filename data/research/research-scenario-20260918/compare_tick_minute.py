"""Compare minute opens with the retained, verified ten-minute trade pilot.

Run from the repository root. This is an execution/accounting comparison, not
annual profitability evidence. Minute bars are derived from the same observed
trades, so no new market-data download or duplicate source dataset is needed.
"""

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from time import perf_counter

from crypto_carry.config import SECOND, Config, timestamp
from crypto_carry.data.prescribed import prescribed_rules
from crypto_carry.data.replay import input_hashes, iter_records
from crypto_carry.data.validate import validate_data
from crypto_carry.events import event_key
from crypto_carry.models import MinutePrice, MinuteVolume, Trade
from crypto_carry.serialization import encode
from crypto_carry.strategy import Backtest

ROOT = Path.cwd().resolve()
OUT = ROOT / "data/research/research-scenario-20260918"
MINUTE = 60 * SECOND


def aggregate(records, config):
    start, end = timestamp(config.start), timestamp(config.end)
    groups = defaultdict(list)
    derived = []
    for record in records:
        if isinstance(record, Trade):
            if start <= record.event_time < end:
                opening = record.event_time // MINUTE * MINUTE
                groups[(record.symbol, record.market, opening)].append(record)
        else:
            derived.append(record)
    coverage = []
    expected = set(range(start, end, MINUTE))
    for symbol in config.symbols:
        for market in ("spot", "futures"):
            observed = {opening for s, m, opening in groups if (s, m) == (symbol, market)}
            if observed != expected:
                raise ValueError(f"Pilot lacks observed trades in a minute: {symbol}/{market}")
            coverage.append({"symbol": symbol, "market": market, "minutes": len(observed)})
    for (symbol, market, opening), trades in sorted(groups.items()):
        first = min(trades, key=event_key)
        reference = f"bar:{symbol}:{market}:{opening}"
        source = "derived:verified-2024-01-01-ten-minute-trades"
        derived.append(
            MinutePrice(symbol, market, reference, opening, opening, first.price, source)
        )
        derived.append(
            MinuteVolume(
                symbol,
                market,
                opening,
                opening + MINUTE - 1_000_000,
                opening + MINUTE,
                sum((trade.quantity for trade in trades), Decimal(0)),
                len(trades),
                source,
            )
        )
    return sorted(derived, key=event_key), coverage


def run():
    config = Config.load(OUT / "pilot.toml")
    quality = validate_data(config, ROOT, scope="full")
    if quality["status"] != "complete":
        raise ValueError(f"Original trade pilot failed validation: {quality['issues']}")
    inputs = input_hashes(ROOT, config)
    records = list(
        iter_records(
            ROOT,
            timestamp(config.start),
            timestamp(config.end),
            config.window_hours + 24,
            data_dir=config.data_dir,
        )
    )
    derived, coverage = aggregate(records, config)
    derived_hash = hashlib.sha256(
        json.dumps(encode(derived), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    profiles = [
        ("tick_original_30s", config, records),
        ("tick_matched_120s", config.changed(order_timeout_seconds=120), records),
        (
            "minute_open_120s",
            config.changed(execution_model="minute_open", order_timeout_seconds=120),
            derived,
        ),
    ]
    results = []
    for label, effective, feed in profiles:
        for strategy, enabled in (("conditional", True), ("permanent", False)):
            clock = perf_counter()
            result = Backtest(
                effective, prescribed_rules(effective), strategy, enabled, inputs
            ).run(feed)
            reconciliation = result.ledger.reconcile(result.spot_prices(), result.mark_prices())
            if result.status != "complete" or reconciliation["difference"] != 0:
                raise ValueError(f"Pilot failed: {label}/{strategy}: {result.reasons}")
            if result.native_fill_count != len(result.fills):
                raise ValueError("Native fill count differs from economic ledger")
            orders = {row["order_id"]: row for row in result.order_rows}
            for fill in result.fills:
                order = orders[fill["order_id"]]
                if not order["submitted_at"] < fill["time_ns"] < order["deadline"]:
                    raise ValueError("A fill violates strict subsequent-price timing")
            item = {
                "label": label,
                "strategy": strategy,
                "status": result.status,
                "config": effective.to_dict(),
                "config_hash": effective.digest(),
                "wall_seconds": perf_counter() - clock,
                "final_equity_usdt": str(result.equity()),
                "native_fills": result.native_fill_count,
                "native_reconciliations": result.native_reconciliation_count,
                "accounting": {key: str(value) for key, value in reconciliation.items()},
                "terminal_positions": {
                    key: asdict(value) for key, value in result.ledger.positions.items()
                },
                "fills": result.fills,
                "orders": result.order_rows,
            }
            results.append(item)
            print(
                json.dumps(
                    {
                        key: item[key]
                        for key in (
                            "label",
                            "strategy",
                            "native_fills",
                            "final_equity_usdt",
                            "wall_seconds",
                        )
                    }
                ),
                flush=True,
            )
    artifact = {
        "purpose": "Short observed execution and accounting comparison; not annual or out-of-sample validation",
        "window": [config.start, config.end],
        "window_end_exclusive": True,
        "source_quality_status": quality["status"],
        "source_trade_rows": sum(isinstance(row, Trade) for row in records),
        "input_hashes": inputs,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "derived_event_sha256": derived_hash,
        "derived_coverage": coverage,
        "recipe": "First observed trade price in each minute assigned to the opening boundary; volume published at next minute; funding/marks unchanged",
        "limitations": [
            "Minute opening-boundary timestamps approximate unknown first-trade arrival times.",
            "This short, pre-existing pilot does not estimate annual return error or stress-period execution risk.",
            "The 120-second tick control separates timeout changes from minute aggregation.",
            "Terminal positions are marked without a forced exit or hypothetical exit costs.",
        ],
        "results": results,
    }
    target = OUT / "tick-minute-comparison.json"
    target.write_text(json.dumps(artifact, indent=2, default=str) + "\n", encoding="utf-8")
    print(str(target), flush=True)


if __name__ == "__main__":
    run()

"""Bounded real-data replay and exact economic digest; writes only a new JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from time import monotonic

from crypto_carry.config import Config, timestamp
from crypto_carry.data.prescribed import prescribed_rules
from crypto_carry.data.replay import iter_records
from crypto_carry.mark_gap_study import GapAuditedBacktest
from crypto_carry.reporting import _code_identity, _plain


def benchmark(data_root: Path, config_path: Path, end: str) -> dict:
    config = Config.load(config_path).changed(end=end)
    results = []
    for strategy, enabled in (("conditional", True), ("permanent", False)):
        started = monotonic()
        records = iter_records(
            data_root,
            timestamp(config.start),
            timestamp(config.end),
            config.window_hours + 24,
            data_dir=config.data_dir,
            execution_model=config.execution_model,
            include_closed_bars=True,
            mark_gap_method=config.mark_gap_method,
        )
        backtest = GapAuditedBacktest(config, prescribed_rules(config), strategy, enabled)
        backtest.run(records)
        fields = {
            key: getattr(backtest, key)
            for key in (
                "daily", "fills", "order_rows", "positions", "signals", "risk_events",
                "opportunities", "renewal_diagnostics", "durations", "all_funding",
                "native_fill_count", "native_reconciliation_count", "status", "reasons",
            )
        }
        fields["ledger"] = backtest.ledger.rows
        fields["funding_payments"] = backtest.ledger.funding_rows
        digests = {
            key: hashlib.sha256(
                json.dumps(_plain(value), sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            for key, value in fields.items()
        }
        row = {
            "strategy": strategy,
            "seconds": monotonic() - started,
            "status": backtest.status,
            "fills": len(backtest.fills),
            "equity": str(backtest.equity()),
            "reconciliation": str(
                backtest.ledger.reconcile(backtest.spot_prices(), backtest.mark_prices())[
                    "difference"
                ]
            ),
            "economic_digests": digests,
        }
        results.append(row)
        print(json.dumps(row), flush=True)
    return {"config": config.to_dict(), "code_hash": _code_identity()[0], "runs": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--end", default="2022-01-15T00:00:00Z")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = benchmark(args.data_root, args.config, args.end)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")

"""Entry filter and outage evidence from persisted decisions and fills."""

import json
from collections import Counter, defaultdict
from decimal import Decimal as D

import pyarrow.parquet as pq

from crypto_carry.config import DAY, iso, timestamp
from crypto_carry.costs import execution_price
from crypto_carry.data.prescribed import prescribed_rules

from .common import SYMBOLS, decimal, yes
from .portfolio import exposure_summary


def filter_summary(signals, periods):
    output = []
    for period, start, end in periods:
        for symbol in SYMBOLS:
            selected = [
                r for r in signals if r["symbol"] == symbol and start <= int(r["time_ns"]) < end
            ]
            counts = Counter()
            for row in selected:
                order = json.loads(row["filter_order"])
                expected = None
                for field in order:
                    applied = field != "funding" or yes(row["funding_filter_enabled"])
                    state = row["filter_" + field]
                    counts[("simultaneous", field, state, applied)] += 1
                    if applied and expected is None and state != "pass":
                        expected = ("not_evaluable:" if state == "not_evaluable" else "") + field
                if (row.get("sequential_rejection") or None) != expected:
                    raise ValueError(
                        "Stored first rejection differs from the applicable filter order"
                    )
                counts[("first_rejection", expected or "all_pass", "selected", True)] += 1
                counts[("actual_decision", row["decision"], "selected", True)] += 1
            output.extend(
                dict(
                    period=period,
                    symbol=symbol,
                    scope=scope,
                    filter=field,
                    state=state,
                    applied=applied,
                    count=count,
                    denominator=len(selected),
                )
                for (scope, field, state, applied), count in sorted(counts.items())
            )
    return output


def event_counts(events, periods):
    output = []
    for period, start, end in periods:
        counter = Counter(
            (r["symbol"], r["kind"], r.get("cause") or "", r.get("purpose") or "")
            for r in events
            if start <= int(r["time_ns"]) < end
        )
        output.extend(
            dict(period=period, symbol=symbol, kind=kind, cause=cause, purpose=purpose, count=n)
            for (symbol, kind, cause, purpose), n in sorted(counter.items())
        )
    return output


def check_daily_cashflows(daily, funding, ledger, tolerance):
    payments, fees = defaultdict(lambda: D(0)), defaultdict(lambda: D(0))
    for row in funding:
        payments[iso(int(row["time_ns"]))[:10]] += decimal(row["amount_usdt"])
    for row in ledger:
        fees[iso(int(row["time_ns"]))[:10]] += decimal(row.get("fee"))
    for row in daily:
        if abs(row["funding_usdt"] - payments[row["date"]]) > tolerance:
            raise ValueError("Daily funding differs from actual ledger cash flows")
        if abs(row["fees_usdt"] + fees[row["date"]]) > tolerance:
            raise ValueError("Daily commissions differ from the ledger")


def outage_summary(daily, intervals, periods):
    start = timestamp("2023-03-24T00:00:00Z")
    row = next(r for r in daily if r["date"] == "2023-03-24")
    durations = exposure_summary(intervals, [("2023-03-24", start, start + DAY)])
    portfolio = next(r for r in durations if r["symbol"] == "PORTFOLIO")
    result = dict(row, **{k: v for k, v in portfolio.items() if k not in {"period", "symbol"}})
    for name, low, high in periods + [
        ("2023", timestamp("2023-01-01T00:00:00Z"), timestamp("2024-01-01T00:00:00Z"))
    ]:
        pnl = sum((r["net_pnl_usdt"] for r in daily if low <= r["time_ns"] < high), D(0))
        result[f"net_pnl_{name}_usdt"] = pnl
        result[f"daily_share_of_positive_profit_{name}"] = (
            row["net_pnl_usdt"] / pnl if pnl > 0 and low <= start < high else None
        )
    return result, durations


def outage_market(root, manifest):
    lower = timestamp("2023-03-24T11:20:00Z")
    upper = timestamp("2023-03-24T14:11:00Z")
    rows = []
    for entry in manifest["entries"]:
        if entry["dataset"] != "minute_bars" or entry["end"] < lower or entry["start"] >= upper:
            continue
        table = pq.ParquetFile(root / entry["path"]).read()
        for row in table.to_pylist():
            if lower <= row["open_time"] < upper:
                rows.append(
                    dict(row, open_time_utc=iso(row["open_time"]), source_partition=entry["path"])
                )
    return sorted(rows, key=lambda r: (r["open_time"], r["symbol"], r["market"]))


def outage_fill_audit(fills, bars, config):
    lookup = {(r["symbol"], r["market"], r["open_time"]): r for r in bars}
    rules = prescribed_rules(config)
    result = []
    for fill in fills:
        if not str(fill["timestamp_utc"]).startswith("2023-03-24"):
            continue
        bar = lookup[fill["symbol"], fill["market"], int(fill["window_start"])]
        volume = decimal(bar["base_volume"])
        reference = decimal(bar["quote_volume"]) / volume
        rule = rules.get(fill["symbol"], fill["market"], int(fill["time_ns"]))
        expected, _ = execution_price(reference, fill["side"].lower(), rule, config)
        valid = (
            abs(reference - decimal(fill["reference_price"])) <= config.accounting_tolerance
            and expected == decimal(fill["price"])
            and int(fill["time_ns"]) == int(bar["available_at"])
            and decimal(fill["quantity"]) <= volume * config.max_volume_participation
        )
        if not valid:
            raise ValueError("Outage fill does not match its closed execution candle")
        result.append(
            dict(
                symbol=fill["symbol"],
                market=fill["market"],
                fill_id=fill["fill_id"],
                time_ns=fill["time_ns"],
                timestamp_utc=fill["timestamp_utc"],
                quantity=fill["quantity"],
                price=fill["price"],
                reference_vwap=reference,
                expected_adverse_price=expected,
                volume_base=volume,
                realized_participation=decimal(fill["quantity"]) / volume,
                window_start=fill["window_start"],
                available_at=bar["available_at"],
                verified=valid,
            )
        )
    return result

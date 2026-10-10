"""Read-only USD-M archive diagnostics; never certify historical completeness.

Compare individual trades with separately published one-minute trade klines.
Keep raw quote-volume anomalies distinct from price/quantity reconciliation.
Memory grows with minutes, not with the number of individual trades.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from decimal import Decimal, Inexact, InvalidOperation, localcontext
from pathlib import Path

_EXAMPLES = 20
_TRADE_HEADER = ("id", "price", "qty", "quote_qty", "time", "is_buyer_maker")
_KLINE_HEADER = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "count",
    "taker_buy_volume",
    "taker_buy_quote_volume",
    "ignore",
)


def _rows(path: Path, header: tuple[str, ...]):
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"Expected one CSV in {path}")
        with archive.open(names[0]) as binary:
            for index, row in enumerate(csv.reader(io.TextIOWrapper(binary, encoding="utf-8"))):
                if len(row) != len(header):
                    raise ValueError(f"Unexpected CSV width in {path}")
                if index == 0 and row[0].strip().lower() in {"id", "trade_id", "open_time"}:
                    if tuple(field.strip().lower() for field in row) != header:
                        raise ValueError(f"Unexpected CSV header in {path}")
                    continue
                if not row:
                    raise ValueError(f"Empty CSV row in {path}")
                yield row


def _number(value: str, *, zero: bool = False) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal: {value}") from exc
    if not result.is_finite() or result < 0 or (result == 0 and not zero):
        raise ValueError(f"Invalid nonnegative/positive decimal: {value}")
    return result


def _identity(path: Path) -> dict:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": digest}


def reconcile_futures_archives(trades_path: Path, klines_path: Path) -> dict:
    """Compare USD-M millisecond archives without altering either source.

    Success means agreement on the observed kline interval only. Both archives
    could share omissions; ID gaps retain their diagnostic status. No rulebook,
    coverage manifest, Parquet, or backtest certification is modified.
    """
    trades_path, klines_path = Path(trades_path), Path(klines_path)
    inputs = [_identity(trades_path), _identity(klines_path)]
    reference = {}
    previous_minute = None
    for row in _rows(klines_path, _KLINE_HEADER):
        opened, closed = int(row[0]), int(row[6])
        if opened < 0 or opened % 60_000 or closed != opened + 59_999:
            raise ValueError("Kline is not an aligned closed UTC minute")
        minute = opened // 60_000
        if previous_minute is not None and minute <= previous_minute:
            raise ValueError("Duplicate or unordered kline minute")
        previous_minute = minute
        item = {
            key: _number(row[index])
            for key, index in zip(("open", "high", "low", "close"), range(1, 5))
        }
        item.update(
            count=int(row[8]), quantity=_number(row[5], zero=True), quote=_number(row[7], zero=True)
        )
        if (
            item["count"] < 0
            or not item["low"]
            <= min(item["open"], item["close"])
            <= max(item["open"], item["close"])
            <= item["high"]
        ):
            raise ValueError("Invalid kline count or OHLC ordering")
        reference[minute] = item
    if not reference:
        raise ValueError("No reference klines")

    minutes = {}
    gap_examples, quote_examples = [], []
    gap_count = absent_ids = quote_mismatches = trade_count = 0
    previous_id = previous_time = None
    with localcontext() as context:
        context.prec = 50
        context.traps[Inexact] = True
        for row in _rows(trades_path, _TRADE_HEADER):
            trade_id, time_ms = int(row[0]), int(row[4])
            price, quantity = _number(row[1]), _number(row[2])
            if trade_id < 0 or time_ms < 0:
                raise ValueError("Negative trade ID or timestamp")
            if previous_id is not None:
                if trade_id <= previous_id or time_ms < previous_time:
                    raise ValueError("Duplicate or unordered trade ID/timestamp")
                if trade_id != previous_id + 1:
                    gap_count += 1
                    absent_ids += trade_id - previous_id - 1
                    if len(gap_examples) < _EXAMPLES:
                        gap_examples.append(
                            {
                                "previous_id": str(previous_id),
                                "next_id": str(trade_id),
                                "previous_time_ms": previous_time,
                                "next_time_ms": time_ms,
                            }
                        )
            previous_id, previous_time = trade_id, time_ms
            quote = price * quantity
            try:
                reported_quote = Decimal(row[3])
            except InvalidOperation:
                reported_quote = Decimal("NaN")
            if not reported_quote.is_finite() or reported_quote != quote:
                quote_mismatches += 1
                if len(quote_examples) < _EXAMPLES:
                    quote_examples.append(
                        {
                            "trade_id": str(trade_id),
                            "time_ms": time_ms,
                            "price": str(price),
                            "quantity": str(quantity),
                            "reported_quote": row[3],
                            "computed_quote": str(quote),
                        }
                    )
            minute = time_ms // 60_000
            if minute not in minutes:
                minutes[minute] = dict(
                    count=0,
                    quantity=Decimal(0),
                    quote=Decimal(0),
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                )
            observed = minutes[minute]
            observed["count"] += 1
            observed["quantity"] += quantity
            observed["quote"] += quote
            observed["high"] = max(observed["high"], price)
            observed["low"] = min(observed["low"], price)
            observed["close"] = price
            trade_count += 1

    mismatching_minutes = 0
    differences = []
    for minute in sorted(reference.keys() | minutes.keys()):
        observed, expected = minutes.get(minute), reference.get(minute)
        if expected is None:
            difference = {"missing": "kline"}
        elif observed is None:
            difference = (
                {}
                if expected["count"] == 0 and expected["quantity"] == expected["quote"] == 0
                else {"missing": "trades"}
            )
        else:
            difference = {
                key: {"trades": str(observed[key]), "klines": str(expected[key])}
                for key in expected
                if observed[key] != expected[key]
            }
        if difference:
            mismatching_minutes += 1
            if len(differences) < _EXAMPLES:
                differences.append({"minute_ms": minute * 60_000, "differences": difference})
    missing_minutes = max(reference) - min(reference) + 1 - len(reference)
    if inputs != [_identity(trades_path), _identity(klines_path)]:
        raise ValueError("Input archive changed during reconciliation")
    return {
        "version": 1,
        "scope": "USD-M minute aggregates; does not prove exhaustive public-market history",
        "historical_certified": False,
        "inputs": inputs,
        "market_values_match": not mismatching_minutes and not missing_minutes,
        "start_ms": min(reference) * 60_000,
        "end_ms_exclusive": (max(reference) + 1) * 60_000,
        "trade_count": trade_count,
        "kline_trade_count": sum(item["count"] for item in reference.values()),
        "kline_minutes": len(reference),
        "missing_kline_minutes": missing_minutes,
        "mismatching_minutes": mismatching_minutes,
        "mismatch_examples": differences,
        "id_gap_count": gap_count,
        "absent_id_count": absent_ids,
        "id_gap_examples": gap_examples,
        "quote_field_mismatch_count": quote_mismatches,
        "quote_field_examples": quote_examples,
        "example_limit": _EXAMPLES,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", required=True, type=Path)
    parser.add_argument("--klines", required=True, type=Path)
    args = parser.parse_args(argv)
    result = reconcile_futures_archives(args.trades, args.klines)
    print(json.dumps(result, indent=2))
    return 0 if result["market_values_match"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

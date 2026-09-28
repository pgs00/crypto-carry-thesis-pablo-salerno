"""Small file and numeric helpers for the return/capital evidence package."""

import csv
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

TOLERANCE = Decimal("1E-8")
SYMBOLS = ("BTCUSDT", "ETHUSDT")
RUNS = {
    "conditional": "run_ad71d751b20623006c195ff3",
    "permanent": "run_dfea4b7ac1475668d5968c97",
}
DAY = 86_400_000_000_000
COMPONENTS = (
    "spot_realized_pnl_usdt",
    "spot_unrealized_pnl_usdt",
    "futures_realized_pnl_usdt",
    "futures_unrealized_pnl_usdt",
    "funding_usdt",
    "fees_usdt",
    "liquidation_fees_usdt",
)


def number(value, *, optional=False):
    if value in (None, "") and optional:
        return Decimal(0)
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid number {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"Nonfinite number {value!r}")
    return result


def truth(value):
    if value is True or value == "True":
        return True
    if value is False or value == "False":
        return False
    raise ValueError(f"Unknown boolean {value!r}")


def close(actual, expected, label):
    if abs(number(actual) - number(expected)) > TOLERANCE:
        raise ValueError(f"{label}: {actual} != {expected}")


def utc_ns(value):
    text = value.removesuffix("Z")
    main, _, fraction = text.partition(".")
    dt = datetime.fromisoformat(main).replace(tzinfo=UTC)
    return int(dt.timestamp()) * 1_000_000_000 + int((fraction + "000000000")[:9])


def iso(value):
    seconds, nanos = divmod(int(value), 1_000_000_000)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S") + f".{nanos:09d}Z"


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        raise ValueError(f"Empty table requires an explicit schema: {path}")
    fields = list(dict.fromkeys(key for row in rows for key in row))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {
                k: json.dumps(v, ensure_ascii=False, separators=(",", ":"))
                if isinstance(v, (list, dict))
                else v
                for k, v in row.items()
            }
            for row in rows
        )


def parquet(path):
    import pyarrow.parquet as pq

    return pq.ParquetFile(path).read().to_pylist()


def periods(metrics):
    result = []
    for row in metrics:
        item = row["period"], utc_ns(row["start_utc"]), utc_ns(row["end_exclusive_utc"])
        if item not in result:
            result.append(item)
    return result

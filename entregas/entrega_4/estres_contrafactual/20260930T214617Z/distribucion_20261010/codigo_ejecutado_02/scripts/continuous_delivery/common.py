"""Small serialization helpers for auditable CSV evidence."""

import csv
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path

import pyarrow.parquet as pq

from crypto_carry.config import timestamp

SYMBOLS = ("BTCUSDT", "ETHUSDT")
PERIODS = [
    ("full", timestamp("2022-01-01T00:00:00Z"), timestamp("2026-09-01T00:00:00Z")),
    ("2022-2023", timestamp("2022-01-01T00:00:00Z"), timestamp("2024-01-01T00:00:00Z")),
    ("2024-2026-08", timestamp("2024-01-01T00:00:00Z"), timestamp("2026-09-01T00:00:00Z")),
]
IGNORED = {"units", "data_kind", "run_id"}


def decimal(value):
    return D(0) if value in (None, "") else D(str(value))


def yes(value):
    return str(value).lower() in {"true", "1"}


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_rows(path):
    path = Path(path)
    if path.suffix == ".parquet":
        rows = pq.ParquetFile(path).read().to_pylist()
    else:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
    return [{k: v for k, v in row.items() if k not in IGNORED} for row in rows]


def write_rows(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            {
                k: json.dumps(v, sort_keys=True, default=str) if isinstance(v, (dict, list)) else v
                for k, v in row.items()
            }
            for row in rows
        )


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )

"""Extract exact small execution windows from the authenticated local minute partitions."""

import csv
import gzip
import io
from collections import defaultdict

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from crypto_carry.config import iso
from scripts.execution_delays_audit import key
from scripts.return_capital.common import read_json, sha256


def forecast_bytes(run):
    """Recover the exact original diagnostic bytes without writing inside evidence."""
    plain = run/"forecast_evaluation.csv"
    compressed = run/"forecast_evaluation.csv.gz"
    if plain.exists() and compressed.exists():
        raise ValueError("Ambiguous forecast evidence representations")
    if plain.is_file():
        return plain.read_bytes()
    return gzip.decompress(compressed.read_bytes())


def forecast_rows(run):
    return list(csv.DictReader(io.StringIO(forecast_bytes(run).decode("utf-8-sig"), newline="")))


def extract_windows(data_root, config, orders, inputs):
    wanted = set(key(r) for r in orders)
    by_partition = defaultdict(set)
    for symbol, market, start in wanted:
        by_partition[symbol, market, iso(start)[:7]].add(start)
    manifest = read_json(data_root/config.data_dir/"manifests/processed.json")
    found = {}
    for entry in manifest["entries"]:
        partition = entry["symbol"], entry["market"], entry["date"]
        if entry["dataset"] != "minute_bars" or partition not in by_partition:
            continue
        name = entry["path"]
        expected = inputs.get(name)
        if expected != entry["sha256"] or sha256(data_root/name) != expected:
            raise ValueError("Execution volume partition failed authentication: "+name)
        table = pq.ParquetFile(data_root/name).read(columns=["symbol", "market", "open_time",
              "end_time", "available_at", "open", "high", "low", "close", "base_volume", "quote_volume", "source_file", "trade_count"])
        selected = table.filter(pc.is_in(table["open_time"],
                                value_set=pa.array(sorted(by_partition[partition]), type=pa.int64())))
        for row in selected.to_pylist():
            k = key(row)
            if k in found:
                raise ValueError("Duplicate authenticated execution minute")
            found[k] = dict(row, present=True, source_path=name, source_sha256=expected)
    return [found.get(k, dict(symbol=k[0], market=k[1], open_time=k[2],
                 end_time=k[2]+60_000_000_000, base_volume=None, quote_volume=None,
                 source_file=None, trade_count=None, present=False, source_path=None,
                 source_sha256=None)) for k in sorted(wanted)]

"""Build a 10-minute observed pilot, verifying source hashes and actual trade IDs.

Run from the project root. No source files are changed, gaps are not filled, and
no result is used to choose the interval. This is an execution/accounting pilot.
"""

import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from crypto_carry.config import SECOND, Config, timestamp
from crypto_carry.data.validate import validate_data

ROOT = Path.cwd()
OUT = Path("data/research/research-scenario-20260918")
DATA = OUT / "pilot-data"
START = "2024-01-01T00:00:00Z"
END = "2024-01-01T00:10:00Z"


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


config = Config.load("configs/research.toml").changed(
    start=START, end=END, sample_start=START, sample_end=END, data_dir=DATA.as_posix()
)
start, end = timestamp(START), timestamp(END)
manifest_path = Path("data/manifests/processed.json")
source = json.loads(manifest_path.read_text(encoding="utf-8"))
assert not source.get("errors")
entries = []
proof = {
    "purpose": "Observed execution pilot, not full-window evidence or parameter selection",
    "start": START,
    "end": END,
    "source_manifest_sha256": digest(manifest_path),
    "sources": [],
    "streams": [],
}
(DATA / "processed").mkdir(parents=True, exist_ok=True)
(DATA / "manifests").mkdir(parents=True, exist_ok=True)
for symbol in config.symbols:
    for dataset, market in (("trades", "spot"), ("trades", "futures"), ("marks", "futures")):
        field = "event_time" if dataset == "trades" else "available_at"
        pieces = []
        for entry in source["entries"]:
            if (entry["symbol"], entry["dataset"], entry["market"]) != (symbol, dataset, market):
                continue
            if int(entry["end"]) < start or int(entry["start"]) >= end:
                continue
            path = Path(entry["path"])
            assert digest(path) == entry["sha256"], path
            assert entry["complete"] and not entry["conflict_count"], path
            table = pq.ParquetFile(path).read()
            table = table.filter(
                pc.and_(pc.greater_equal(table[field], start), pc.less(table[field], end))
            )
            if len(table):
                pieces.append(table)
                proof["sources"].append({"path": entry["path"], "sha256": entry["sha256"]})
        assert pieces, (symbol, dataset, market)
        table = pa.concat_tables(pieces).sort_by([(field, "ascending")])
        times = table[field].to_pylist()
        assert all(a <= b for a, b in zip(times, times[1:]))
        first_id = last_id = None
        if dataset == "trades":
            ids = [int(value) for value in table["trade_id"].to_pylist()]
            # Stable physical order is ascending ID within equal timestamps.
            assert all(b == a + 1 for a, b in zip(ids, ids[1:])), (symbol, market, "pilot ID gap")
            first_id, last_id = str(ids[0]), str(ids[-1])
        else:
            assert times == list(range(start, end, 60 * SECOND)), (symbol, "pilot mark gap")
        path = DATA / "processed" / f"{dataset}-{symbol}-{market}.parquet"
        pq.write_table(table, path, compression="zstd")
        entries.append(
            {
                "dataset": dataset,
                "symbol": symbol,
                "market": market,
                "date": START[:10],
                "path": path.as_posix(),
                "sha256": digest(path),
                "bytes": path.stat().st_size,
                "rows": len(table),
                "start": times[0],
                "end": times[-1],
                "schema": {f.name: str(f.type) for f in table.schema},
                "duplicate_count": 0,
                "conflict_count": 0,
                "complete": True,
                "trade_id_continuous": True if dataset == "trades" else None,
                "minute_coverage_complete": True if dataset == "marks" else None,
                "first_trade_id": first_id,
                "last_trade_id": last_id,
            }
        )
        proof["streams"].append(
            {
                "symbol": symbol,
                "dataset": dataset,
                "market": market,
                "rows": len(table),
                "first_trade_id": first_id,
                "last_trade_id": last_id,
            }
        )
entries.extend(entry for entry in source["entries"] if entry["dataset"] == "funding")
(DATA / "manifests/processed.json").write_text(
    json.dumps(
        {"entries": entries, "errors": [], "source_manifest_sha256": digest(manifest_path)},
        indent=2,
    ),
    encoding="utf-8",
)
(DATA / "manifests/download.json").write_bytes(Path("data/manifests/download.json").read_bytes())
(OUT / "pilot.toml").write_text(config.to_toml(), encoding="utf-8")
quality = validate_data(config, ROOT, scope="full")
proof["validation_status"] = quality["status"]
proof["issues"] = quality["issues"]
(OUT / "pilot-input-audit.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
print(
    json.dumps(
        {"status": quality["status"], "issues": quality["issues"], "streams": proof["streams"]}
    )
)
assert quality["status"] == "complete", quality["issues"]

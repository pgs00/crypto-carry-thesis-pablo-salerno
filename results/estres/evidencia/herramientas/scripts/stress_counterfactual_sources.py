"""Small authentic source extraction for persisted window witnesses, no replay."""

import json

import pyarrow as pa
import pyarrow.parquet as pq

from scripts.execution_delays_sources import extract_windows
from scripts.return_capital.common import parquet, read_json, sha256, write_json

MINUTE = 60_000_000_000


def witness_keys(evidence):
    keys = set()
    for row in parquet(evidence / "oportunidad_ventanas.parquet"):
        witness = json.loads(row["evidence_json"])
        current_open = (int(witness["time_ns"]) // MINUTE - 1) * MINUTE
        keys.update((witness["symbol"], market, current_open) for market in ("spot", "futures"))
        for field in ("spot_bar", "future_bar"):
            bar = witness.get(field)
            if bar:
                keys.add((bar["symbol"], bar["market"], int(bar["open_time"])))
                if bar["market"] == "spot":
                    keys.add((bar["symbol"], "futures", int(bar["open_time"])))
    for row in parquet(evidence / "observaciones_ventanas.parquet"):
        for phase in ("before", "before_fills", "after_fills", "after"):
            snapshot = json.loads(row[phase + "_json"])
            if snapshot is None:
                continue
            for symbol, asset in snapshot["assets"].items():
                for field in ("original_spot_available_at", "spot_source_available_at"):
                    if asset[field] is not None:
                        opening = int(asset[field]) - MINUTE
                        keys.add((symbol, "spot", opening))
                        keys.add((symbol, "futures", opening))
    return keys


def extract_witness_sources(package, item, data, config, inputs):
    evidence = package / "intervenciones" / item["run_id"]
    target = package / "evidencia_mercado/testigos" / (item["run_id"] + ".parquet")
    provenance = target.with_suffix(".json")
    if target.exists():
        meta = read_json(provenance)
        if sha256(target) != meta["sha256"] or meta["evidence_manifest_sha256"] != item["evidence_manifest_sha256"]:
            raise ValueError("Window witness source extract changed")
        return parquet(target)
    keys = witness_keys(evidence)
    requested = [dict(symbol=s, market=m, open_time=u) for s, m, u in sorted(keys)]
    rows = extract_windows(data, config, requested, inputs)
    target.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows) if rows else pa.table({"no_observations": pa.array([], type=pa.bool_())})
    pq.write_table(table, target, compression="zstd")
    write_json(provenance, dict(sha256=sha256(target), rows=len(rows),
        evidence_manifest_sha256=item["evidence_manifest_sha256"], original_partitions_rehashed=True,
        scope="Exact small source windows consumed by persisted price and H3 witnesses; not a full market copy"))
    # Use the persisted schema on the first call as on subsequent reads. Parquet
    # adds null columns to absent-minute rows when present rows define the schema.
    return parquet(target)


def verified_witness_sources(package, item, inputs):
    target = package / "evidencia_mercado/testigos" / (item["run_id"] + ".parquet")
    meta = read_json(target.with_suffix(".json"))
    if sha256(target) != meta["sha256"] or meta["evidence_manifest_sha256"] != item["evidence_manifest_sha256"]:
        raise ValueError("Window witness source extract identity changed")
    rows = parquet(target)
    if len(rows) != meta["rows"]:
        raise ValueError("Window witness source extract count changed")
    keys = {(r["symbol"], r["market"], int(r["open_time"])) for r in rows}
    if len(keys) != len(rows) or keys != witness_keys(package / "intervenciones" / item["run_id"]):
        raise ValueError("Window witness source extract population differs")
    for row in rows:
        if row["present"] and inputs.get(row["source_path"]) != row["source_sha256"]:
            raise ValueError("Witness source is not in original authenticated input identities")
    return rows

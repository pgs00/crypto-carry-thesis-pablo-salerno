"""Annotate causal price-reference quality without changing reconstructed accounts."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

if __package__:
    from . import intraday_risk_sources as sources
else:
    import intraday_risk_sources as sources

REFERENCES = tuple(
    (symbol, label) for symbol in sources.SYMBOLS for label in ("spot", "mark", "futures")
)
REASON_DICTIONARY = {
    "0": {
        "name": "causal_current",
        "description": "La última barra de minuto completamente disponible es válida para esta referencia.",
    },
    "1": {
        "name": "no_causal_valid_reference",
        "description": "No hay ningún cierre válido causal disponible; no se inventa precio ni causa de arrastre.",
    },
    "2": {
        "name": "carried_expected_minute_absent",
        "description": "Existe una referencia válida anterior, pero falta el registro de la última barra esperada.",
    },
    "3": {
        "name": "carried_zero_volume_omitted",
        "description": "La última barra esperada tiene precio válido y volumen cero: se omite según la política original.",
    },
    "4": {
        "name": "carried_invalid_price_omitted",
        "description": "La última barra esperada tiene cierre no finito o no positivo: se mantiene una referencia válida anterior.",
    },
    "5": {
        "name": "carried_invalid_volume_omitted",
        "description": "La última barra esperada tiene precio válido pero volumen negativo o NaN; no satisface volumen > 0.",
    },
}


def quality_codes(prices, times, *, require_volume):
    """Explain the last expected available bar, using only records available at t.

    Availability must lie on the authenticated UTC minute grid. A daily timestamp
    at 23:59:59.999999999 therefore expects availability 23:59, never next midnight.
    Code 1 takes precedence when no valid prior price exists; otherwise invalid
    close precedes volume rejection. Marks do not require positive trading volume.
    Estimated provenance is orthogonal and remains in the original observation.
    """
    times = np.asarray(times, dtype=np.int64)
    available = np.asarray(prices["available_at"], dtype=np.int64)
    close = np.asarray(prices["close"], dtype=np.float64)
    if available.ndim != 1 or close.shape != available.shape or times.ndim != 1:
        raise ValueError("Invalid price availability dimensions")
    if np.any(np.diff(available) <= 0) or np.any(available % sources.MINUTE):
        raise ValueError("Price availability must be strictly increasing on the UTC minute grid")
    result = np.ones(len(times), dtype=np.uint8)
    if not len(available):
        return result
    valid_close = np.isfinite(close) & (close > 0)
    eligible = valid_close.copy()
    if require_volume:
        volume = np.asarray(prices["base_volume"], dtype=np.float64)
        if volume.shape != available.shape:
            raise ValueError("Invalid volume dimensions")
        # Match price_at exactly: do not introduce a different eligibility rule.
        eligible &= volume > 0
    known = np.searchsorted(available[eligible], times, side="right") > 0
    result[known] = 2
    expected = (times // sources.MINUTE) * sources.MINUTE
    locations = np.searchsorted(available, expected)
    clipped = np.minimum(locations, len(available) - 1)
    present = known & (locations < len(available)) & (available[clipped] == expected)
    result[present & ~valid_close[clipped]] = 4
    valid_expected = present & valid_close[clipped]
    if require_volume:
        result[valid_expected & (volume[clipped] == 0)] = 3
        result[valid_expected & ~(volume[clipped] > 0) & (volume[clipped] != 0)] = 5
    result[present & eligible[clipped]] = 0
    return result


def annotate_package(package, series_root, data_root):
    """Write only the shared annotation Parquet and its dictionary/provenance JSON."""
    begun = time.perf_counter()
    package, series_root, data_root = map(Path, (package, series_root, data_root))
    destination = package / "evidencia/calidad_precios.parquet"
    metadata_path = destination.with_suffix(".json")
    temporary = destination.with_suffix(".parquet.incomplete")
    if any(path.exists() for path in (destination, metadata_path, temporary)):
        raise ValueError("Price-quality output must be new; existing evidence is not overwritten")
    manifest_path, price_sources_path = (
        package / "series_locales.json",
        package / "fuentes_precios.json",
    )
    series_hash, price_sources_hash = (
        sources.sha256(manifest_path),
        sources.sha256(price_sources_path),
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pinned_sources = json.loads(price_sources_path.read_text(encoding="utf-8"))
    reader = sources.LocalPrices(data_root)
    processed_hash = sources.sha256(reader.manifest_path)
    if processed_hash != pinned_sources["manifest_sha256"]:
        raise ValueError("Processed price manifest hash mismatch")
    if reader.entries != pinned_sources["entries"]:
        raise ValueError("Price source identities do not match the reconstructed series")
    source_hashes = {}
    for entry in reader.entries:
        actual = sources.sha256(data_root / entry["path"])
        if actual != entry["sha256"]:
            raise ValueError(f"Price partition hash mismatch: {entry['path']}")
        source_hashes[str(entry["source_id"])] = actual
    groups = defaultdict(list)
    for entry in manifest["entries"]:
        month = datetime.fromtimestamp(entry["start_ns"] // sources.SECOND, UTC).strftime("%Y-%m")
        groups[month].append(entry)
    run_ids = sorted({entry["run_id"] for entry in manifest["entries"]})
    if len(run_ids) != 4:
        raise ValueError("Expected the four preserved portfolio trajectories")
    reason_columns = [f"{symbol}_{label}_reason_code" for symbol, label in REFERENCES]
    schema = pa.schema([("time_ns", pa.int64())] + [(name, pa.uint8()) for name in reason_columns])
    schema = schema.with_metadata(
        {
            b"join_key": b"time_ns",
            b"cardinality": b"many_series_observations_to_one_price_quality_row",
            b"time_zone": b"UTC",
            b"phase_independent": b"true",
            b"reason_dictionary": json.dumps(REASON_DICTIONARY, ensure_ascii=False).encode("utf-8"),
        }
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    coverage, monthly_counts = [], []
    row_count, previous_last = 0, None
    with pq.ParquetWriter(
        temporary, schema, compression="zstd", use_dictionary=reason_columns
    ) as writer:
        for month, entries in sorted(groups.items()):
            block_begun = time.perf_counter()
            if sorted(entry["run_id"] for entry in entries) != run_ids:
                raise ValueError(f"Expected one partition per portfolio in {month}")
            bounds = {(entry["start_ns"], entry["end_exclusive_ns"]) for entry in entries}
            if len(bounds) != 1:
                raise ValueError(f"Different portfolio observation bounds in {month}")
            lower, upper = next(iter(bounds))
            observed = []
            for entry in entries:
                path = series_root / entry["path"]
                if sources.sha256(path) != entry["sha256"]:
                    raise ValueError(f"Series partition hash mismatch: {entry['path']}")
                times = pq.ParquetFile(path).read(columns=["time_ns"])["time_ns"].to_numpy()
                if (
                    len(times) != entry["rows"]
                    or not len(times)
                    or np.any(np.diff(times) < 0)
                    or times[0] < lower
                    or times[-1] >= upper
                ):
                    raise ValueError(f"Invalid observation clock: {entry['path']}")
                observed.append(times)
            union = np.unique(np.concatenate(observed))
            if previous_last is not None and union[0] <= previous_last:
                raise ValueError("Monthly annotation keys are not globally unique")
            previous_last = int(union[-1])
            raw = reader.block(month)
            columns, counts = {"time_ns": union}, {}
            for symbol, label in REFERENCES:
                codes = quality_codes(raw[symbol, label], union, require_volume=label != "mark")
                reference = f"{symbol}_{label}"
                columns[reference + "_reason_code"] = codes
                counts[reference] = {str(i): int(np.count_nonzero(codes == i)) for i in range(6)}
            writer.write_table(pa.table(columns, schema=schema), row_group_size=len(union))
            for entry, times in zip(entries, observed, strict=True):
                locations = np.searchsorted(union, times)
                matched = int(np.count_nonzero(union[locations] == times))
                if matched != len(times):
                    raise ValueError(f"Annotation join lost observations: {entry['path']}")
                coverage.append(
                    {
                        "run_id": entry["run_id"],
                        "path": entry["path"],
                        "sha256": entry["sha256"],
                        "rows": len(times),
                        "unique_timestamps": len(np.unique(times)),
                        "matched_observations": matched,
                        "missing_observations": len(times) - matched,
                    }
                )
            monthly_counts.append(
                {
                    "month": month,
                    "start_ns": lower,
                    "end_exclusive_ns": upper,
                    "row_count": len(union),
                    "first_time_ns": int(union[0]),
                    "last_time_ns": int(union[-1]),
                    "reference_counts": counts,
                    "elapsed_seconds": time.perf_counter() - block_begun,
                }
            )
            row_count += len(union)
            print(json.dumps({"month": month, "shared_price_quality_rows": len(union)}), flush=True)
    if (
        sources.sha256(manifest_path) != series_hash
        or sources.sha256(price_sources_path) != price_sources_hash
    ):
        raise ValueError("Input provenance changed during price-quality annotation")
    temporary.replace(destination)
    script, reader_script = Path(__file__).resolve(), Path(sources.__file__).resolve()
    record = {
        "schema_version": 1,
        "status": "annotated_from_authenticated_local_prices",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "elapsed_seconds": time.perf_counter() - begun,
        "argv": list(sys.orig_argv),
        "engine_replay": False,
        "source_series_modified": False,
        "row_count": row_count,
        "columns": {field.name: str(field.type) for field in schema},
        "reason_dictionary": REASON_DICTIONARY,
        "reason_scope": {
            "expected_available_at_formula": "floor(time_ns / 60000000000) * 60000000000",
            "expected_open_time_formula": "expected_available_at - 60000000000",
            "policy": "Last valid available close; spot/futures require base_volume > 0; marks do not.",
            "precedence": "No causal valid reference first; otherwise missing expected bar, invalid close, rejected volume, or current valid bar.",
            "causality": "Expected bar availability never exceeds observation time; future records do not explain current carry.",
            "limits": "Reason explains the latest expected bar. It does not invent a market cause for an absent source record. Estimated flags are orthogonal.",
        },
        "join_contract": {
            "key": ["time_ns"],
            "cardinality": "many_series_observations_to_one_price_quality_row",
            "series_manifest": "series_locales.json",
            "phase_independent": True,
            "references": [f"{symbol}_{label}" for symbol, label in REFERENCES],
            "existing_observation_provenance": "{symbol}_{label}_{source_id,open_time,end_time/close_time,available_at,age_ns,estimated,evaluable}",
            "coverage_definition": "Every physical row, including all PRE/POST phases and daily snapshots, joins to exactly one annotation key.",
        },
        "coverage": coverage,
        "monthly_counts": monthly_counts,
        "provenance": {
            "series_manifest": {"path": "series_locales.json", "sha256": series_hash},
            "price_sources": {"path": "fuentes_precios.json", "sha256": price_sources_hash},
            "processed_manifest": {
                "path": str(reader.manifest_path.resolve()),
                "sha256": processed_hash,
            },
            "script": {
                "path": "herramientas/scripts/intraday_risk_price_quality.py",
                "executed_path": str(script),
                "sha256": sources.sha256(script),
            },
            "reader_script": {
                "path": "herramientas/scripts/intraday_risk_sources.py",
                "executed_path": str(reader_script),
                "sha256": sources.sha256(reader_script),
            },
            "source_partitions": {
                "count": len(source_hashes),
                "all_manifest_hashes_match": True,
                "sha256_by_source_id": source_hashes,
            },
            "series_partitions": {"count": len(coverage), "all_manifest_hashes_match": True},
            "run_ids": run_ids,
            "source_root_recorded": str(data_root.resolve()),
        },
        "parquet": {
            "path": destination.relative_to(package).as_posix(),
            "sha256": sources.sha256(destination),
            "bytes": destination.stat().st_size,
        },
    }
    metadata_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("package", "series-root", "data-root"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    record = annotate_package(args.package, args.series_root, args.data_root)
    print(
        json.dumps(
            {
                "row_count": record["row_count"],
                "covered_observations": sum(
                    row["matched_observations"] for row in record["coverage"]
                ),
                "elapsed_seconds": record["elapsed_seconds"],
                "parquet": record["parquet"],
            }
        )
    )


if __name__ == "__main__":
    main()

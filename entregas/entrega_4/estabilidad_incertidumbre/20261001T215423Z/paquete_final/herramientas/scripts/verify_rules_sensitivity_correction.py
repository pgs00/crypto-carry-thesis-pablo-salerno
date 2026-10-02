"""Offline read-only verification of a v2 derivative and its explicit sealed parent.

Financial verification uses the parent's archived v1 verifier. Exposure is
independently reconstructed from parent positions.parquet (requires PyArrow),
then integrated without importing the builder or its exposure implementation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import sys
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path, PurePosixPath, PureWindowsPath

_bytecode_setting = sys.dont_write_bytecode
try:
    sys.dont_write_bytecode = True
    if __package__:
        from .rules_sensitivity_h2 import validate_h2_rows
    else:
        from rules_sensitivity_h2 import validate_h2_rows
finally:
    sys.dont_write_bytecode = _bytecode_setting

SCHEMA = "rules_sensitivity_correction_v2"
KNOWN_PARENT_SCHEMA = "rules_sensitivity_package_v1"
VERSION = "exposure_h2_v2"
SECOND = 1_000_000_000
SYMBOLS = ("BTCUSDT", "ETHUSDT")
EXPOSURE_FIELDS = {
    "invested_seconds", "unhedged_seconds", "covered_seconds", "both_covered_seconds",
    "cash_seconds", "calendar_seconds", "invested_fraction",
}
PRESERVED_TABLES = (
    "diario_carteras.csv", "componentes_por_activo_periodo.csv", "conciliaciones.csv",
    "h1_invariancia.csv", "h1_resumen.csv", "h3_diario.csv", "h3_invariancia.csv",
    "h3_regimen.csv", "registro_corridas.csv", "eventos_periodo.csv", "fronteras_promocion.csv",
)
POSTPROCESSORS = {
    "herramientas/" + name for name in (
        "correct_rules_sensitivity_report.py", "rules_sensitivity_correction_docs.py",
        "rules_sensitivity_exposure.py", "rules_sensitivity_h2.py",
        "verify_rules_sensitivity_package.py", "verify_rules_sensitivity_correction.py",
    )
}
E3_FILES = {
    "tablas/exposicion_intervalos.csv", "tablas/tiempo_invertido.csv",
    "tablas/episodio_2023_03_24_exposicion.csv",
    "codigo/scripts/continuous_delivery/portfolio.py",
    "codigo/scripts/continuous_delivery/common.py", "codigo/scripts/continuous_delivery/build.py",
    "codigo/src/crypto_carry/strategy.py", "codigo/src/crypto_carry/reporting.py",
}


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"missing/duplicate CSV fields: {path}")
        result = list(reader)
        if any(None in row or None in row.values() for row in result):
            raise ValueError(f"malformed CSV: {path}")
        return result


def safe_path(root, relative):
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or PurePosixPath(relative).is_absolute() or PureWindowsPath(relative).drive
            or ".." in PurePosixPath(relative).parts):
        raise ValueError(f"invalid member path: {relative!r}")
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError(f"member path escapes package: {relative!r}")
    return path


def check_manifest(package, schema):
    package = Path(package).resolve()
    path = package / "manifiesto_paquete.json"
    digest = sha256(path)
    if (package / "manifiesto_paquete.sha256").read_text(encoding="utf-8-sig").split()[0] != digest:
        raise ValueError("manifest sidecar mismatch")
    manifest = read_json(path)
    if manifest.get("schema") != schema:
        raise ValueError(f"unsupported schema, require {schema}")
    seen = set()
    for member in manifest["members"]:
        name = member["path"]
        if name in seen:
            raise ValueError(f"duplicate manifest member: {name}")
        seen.add(name)
        target = safe_path(package, name)
        if target.stat().st_size != member["size"] or sha256(target) != member["sha256"]:
            raise ValueError(f"manifest member changed: {name}")
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    if actual != seen | {"manifiesto_paquete.json", "manifiesto_paquete.sha256"}:
        raise ValueError("unlisted or missing package members")
    return manifest


def timestamp(value):
    match = re.fullmatch(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?Z", value)
    if not match:
        raise ValueError(f"invalid UTC boundary: {value!r}")
    dt = datetime.fromisoformat(match[1]).replace(tzinfo=UTC)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    return int((dt - epoch).total_seconds()) * SECOND + int((match[2] or "").ljust(9, "0"))


def iso(value):
    seconds, fraction = divmod(value, SECOND)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S") + f".{fraction:09d}Z"


def number(value):
    result = D(str(value))
    if not result.is_finite():
        raise ValueError(f"nonfinite number: {value}")
    return result


def truth(value):
    if value is True or value == "True":
        return True
    if value is False or value == "False":
        return False
    raise ValueError(f"invalid boolean: {value!r}")


def equal(actual, expected, label):
    if isinstance(expected, bool):
        valid = truth(actual) is expected
    elif isinstance(expected, D):
        valid = number(actual) == expected
    elif isinstance(expected, int):
        valid = number(actual) == expected
    elif expected is None:
        valid = actual in (None, "")
    else:
        valid = actual == expected
    if not valid:
        raise ValueError(f"{label}: {actual!r} != {expected!r}")


def unique_index(rows, keys):
    result = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        if key in result:
            raise ValueError(f"duplicate row: {key}")
        result[key] = row
    return result


def check_financial_preservation(actual, original):
    keys = ("scenario", "strategy", "run_id", "period")
    new, old = unique_index(actual, keys), unique_index(original, keys)
    if set(new) != set(old):
        raise ValueError("financial row identity/coverage changed")
    for key, before in old.items():
        for field, value in before.items():
            if field not in EXPOSURE_FIELDS and new[key].get(field) != value:
                raise ValueError(f"financial preservation {key}/{field}")


def _reconstruct(positions, start, end, tolerance, symbols):
    """Independent E3 state walk: classify full history before clipping."""
    tolerance = number(tolerance)
    if start >= end or tolerance < 0 or not symbols or len(set(symbols)) != len(symbols):
        raise ValueError("invalid source window, symbols or hedge tolerance")
    positions = list(positions)
    for row in positions:
        if row.get("symbol") not in symbols or row.get("time_ns") in (None, ""):
            raise ValueError("missing/unknown source symbol or timestamp metadata")
    result = []
    for symbol in symbols:
        # Stable sorting preserves the last persisted event at equal timestamps.
        last_at_time = {}
        for row in sorted(positions, key=lambda r: int(r["time_ns"])):
            if row["symbol"] == symbol and int(row["time_ns"]) < end:
                last_at_time[int(row["time_ns"])] = row
        if not last_at_time or min(last_at_time) > start:
            last_at_time[start] = dict(spot="0", short="0", dust_spot="0", state="FLAT",
                                       collateral="0")
        times = sorted(last_at_time)
        dust_seen = D(0)
        for offset, lower in enumerate(times):
            source = last_at_time[lower]
            if any(source.get(key) in (None, "") for key in (
                "spot", "short", "state"
            )):
                raise ValueError(f"missing exposure metadata {symbol}/{lower}")
            spot, short = number(source["spot"]), number(source["short"])
            residual = number(source.get("dust_spot") or "0")
            collateral = number(source.get("collateral") or "0")
            if min(spot, short, residual, collateral) < 0:
                raise ValueError("negative inventory metadata")
            if spot > 0 and short == 0 and (
                residual > 0 or source["state"] in {"FLAT", "COOLDOWN"} or spot <= dust_seen
            ):
                state, dust_seen = "dust", spot
            elif spot > 0 and short > 0 and abs(spot - short) / spot <= tolerance:
                state = "covered"
            elif spot > 0 or short > 0:
                state = "unhedged"
            else:
                state = "flat"
            upper = times[offset + 1] if offset + 1 < len(times) else end
            lower, upper = max(lower, start), min(upper, end)
            if lower >= upper:
                continue
            error = abs(spot - short) / spot if spot else D(1) if short else D(0)
            result.append(dict(
                symbol=symbol, start_ns=lower, end_ns=upper, start_utc=iso(lower),
                end_exclusive_utc=iso(upper), seconds=D(upper-lower)/SECOND,
                exposure=state, spot=spot, short=short, state=source["state"],
                collateral_usdt=collateral,
                raw_invested=spot > 0 or short > 0,
                raw_unhedged=(spot > 0 or short > 0) and error > tolerance,
            ))
    return sorted(result, key=lambda r: (r["start_ns"], r["symbol"]))


def check_interval_rows(actual, positions, start, end, tolerance, symbols=SYMBOLS):
    expected = _reconstruct(positions, start, end, tolerance, symbols)
    keys = ("symbol", "start_ns", "end_ns")
    def normalized(rows):
        return [dict(r, start_ns=int(r["start_ns"]), end_ns=int(r["end_ns"])) for r in rows]
    observed = unique_index(normalized(actual), keys)
    calculated = unique_index(expected, keys)
    if set(observed) != set(calculated):
        raise ValueError("exposure interval boundary/coverage mismatch")
    for key, row in calculated.items():
        for field, value in row.items():
            equal(observed[key].get(field), value, f"interval {key}/{field}")
    return expected


def aggregate_intervals(intervals, periods, symbols=SYMBOLS):
    """Integrate disjoint common time cells, never sum overlapping assets."""
    intervals, periods = list(intervals), list(periods)
    if not symbols or len(set(symbols)) != len(symbols):
        raise ValueError("missing/duplicate exposure symbols")
    if {row["symbol"] for row in intervals} != set(symbols):
        raise ValueError("incomplete or unknown exposure symbols")
    for row in intervals:
        lower, upper = int(row["start_ns"]), int(row["end_ns"])
        if lower >= upper or row["exposure"] not in {"covered", "unhedged", "dust", "flat"}:
            raise ValueError("invalid exposure interval bounds or classification")
        equal(row["seconds"], D(upper-lower)/SECOND, "interval seconds")
        raw = truth(row["raw_invested"])
        if raw != (row["exposure"] != "flat") or (truth(row["raw_unhedged"]) and not raw):
            raise ValueError("raw inventory contradicts exposure classification")
    output = []
    grouped = {
        symbol: sorted((r for r in intervals if r["symbol"] == symbol),
                       key=lambda r: int(r["start_ns"])) for symbol in symbols
    }
    for rows in grouped.values():
        if any(int(left["end_ns"]) != int(right["start_ns"])
               for left, right in zip(rows, rows[1:])):
            raise ValueError("interval gap or overlap")
    if len({row[0] for row in periods}) != len(periods):
        raise ValueError("duplicate exposure period")
    fields = ("invested_seconds", "unhedged_seconds", "covered_seconds", "both_covered_seconds",
              "raw_invested_seconds", "raw_unhedged_seconds", "dust_seconds", "dust_only_seconds",
              "no_active_seconds", "no_inventory_seconds", "flat_seconds", "cash_seconds")
    for period, start, end in periods:
        if start >= end:
            raise ValueError("nonpositive exposure period")
        if any(int(rows[0]["start_ns"]) > start or int(rows[-1]["end_ns"]) < end
               for rows in grouped.values()):
            raise ValueError("incomplete exposure coverage")
        pointers = dict.fromkeys(symbols, 0)
        totals = {symbol: dict.fromkeys(fields, D(0)) for symbol in (*symbols, "PORTFOLIO")}
        cuts = sorted({start, end} | {
            max(start, min(end, int(row[field]))) for row in intervals
            for field in ("start_ns", "end_ns")
        })
        for lower, upper in zip(cuts, cuts[1:]):
            active = {}
            for symbol in symbols:
                rows = grouped[symbol]
                while pointers[symbol] < len(rows) and int(rows[pointers[symbol]]["end_ns"]) <= lower:
                    pointers[symbol] += 1
                if (pointers[symbol] >= len(rows)
                        or int(rows[pointers[symbol]]["start_ns"]) > lower
                        or int(rows[pointers[symbol]]["end_ns"]) < upper):
                    raise ValueError(f"interval gap or overlap: {symbol}/{lower}")
                active[symbol] = rows[pointers[symbol]]
            seconds = D(upper-lower)/SECOND
            for symbol in (*symbols, "PORTFOLIO"):
                rows = list(active.values()) if symbol == "PORTFOLIO" else [active[symbol]]
                states = [r["exposure"] for r in rows]
                invested = any(s in {"covered", "unhedged"} for s in states)
                raw = any(truth(r["raw_invested"]) for r in rows)
                flags = dict(
                    invested_seconds=invested, unhedged_seconds="unhedged" in states,
                    covered_seconds="covered" in states,
                    both_covered_seconds=all(s == "covered" for s in states)
                    if symbol == "PORTFOLIO" else False,
                    raw_invested_seconds=raw,
                    raw_unhedged_seconds=any(truth(r["raw_unhedged"]) for r in rows),
                    dust_seconds="dust" in states,
                    dust_only_seconds=not invested and "dust" in states,
                    no_active_seconds=not invested, no_inventory_seconds=not raw,
                    flat_seconds=all(s == "flat" for s in states), cash_seconds=not raw,
                )
                for field, flag in flags.items():
                    totals[symbol][field] += seconds * flag
        calendar = D(end-start)/SECOND
        for symbol, values in totals.items():
            if symbol == "PORTFOLIO":
                values.pop("flat_seconds")
                values["any_covered_seconds"] = values["covered_seconds"]
                values["any_unhedged_seconds"] = values["unhedged_seconds"]
                values["cash_or_dust_seconds"] = values["no_active_seconds"]
            else:
                values.pop("both_covered_seconds")
            row = dict(period=period, symbol=symbol, **values, calendar_seconds=calendar)
            row.update({key.removesuffix("_seconds") + "_fraction": value/calendar
                        for key, value in values.items()})
            if any(not D(0) <= value <= calendar for value in values.values()):
                raise ValueError("exposure duration outside calendar")
            if (values["invested_seconds"] + values["no_active_seconds"] != calendar
                    or values["no_active_seconds"] != values["dust_only_seconds"]
                    + values["no_inventory_seconds"]
                    or values["raw_invested_seconds"] != values["invested_seconds"]
                    + values["dust_only_seconds"]):
                raise ValueError("exposure partitions do not reconcile")
            output.append(row)
    return output


def check_summaries(actual, expected):
    observed = unique_index(actual, ("period", "symbol"))
    calculated = unique_index(expected, ("period", "symbol"))
    if set(observed) != set(calculated):
        raise ValueError("exposure summary coverage mismatch")
    for key, values in calculated.items():
        for field, value in values.items():
            equal(observed[key].get(field), value, f"summary {key}/{field}")


def check_output(output, package, parent):
    output = Path(output)
    if (output.exists() or output.resolve().is_relative_to(Path(package).resolve())
            or output.resolve().is_relative_to(Path(parent).resolve())):
        raise ValueError("verification output must be a NEW path outside both packages")
    for ancestor in output.resolve().parents:
        if any((ancestor / name).is_file() for name in (
            "manifiesto_paquete.json", "manifest.json", "evidence_manifest.json",
        )):
            raise ValueError("verification output cannot enter any sealed package")


def _archived_verifier(parent):
    path = parent / "herramientas/verify_rules_sensitivity_package.py"
    spec = importlib.util.spec_from_file_location("_preserved_rules_v1_verifier", path)
    module = importlib.util.module_from_spec(spec)
    # Execute authenticated source directly: loading must never create a pyc
    # inside a preserved package, even when the caller did not pass python -B.
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def _check_provenance(package, parent, manifest):
    provenance = read_json(package / "procedencia.json")
    parent_hash = sha256(parent / "manifiesto_paquete.json")
    for record in (manifest, provenance):
        if record.get("parent_manifest_sha256") != parent_hash:
            raise ValueError("parent manifest identity mismatch")
        if record.get("postprocessor_version") != VERSION:
            raise ValueError("incorrect postprocessor provenance/version")
    if (provenance.get("schema") != SCHEMA
            or provenance.get("parent_schema") != KNOWN_PARENT_SCHEMA
            or provenance.get("parent_argument_required") is not True
            or provenance.get("engine_reexecution") is not False):
        raise ValueError("incorrect postprocessor provenance/version")
    parent_members = read_json(parent / "manifiesto_paquete.json")["members"]
    required_sources = {row["path"] for row in parent_members} | {
        "manifiesto_paquete.json", "manifiesto_paquete.sha256"}
    reference = package / "referencia_e3"
    for name, root, mandatory in (
        ("source_files", parent, required_sources),
        ("postprocessor_files", package, POSTPROCESSORS),
        ("e3_reference_files", reference, E3_FILES | {"manifest.json", "manifest.sha256"}),
    ):
        rows = provenance.get(name, [])
        indexed = unique_index(rows, ("path",))
        if {key[0] for key in indexed} != mandatory:
            raise ValueError(f"incomplete or unexpected mandatory provenance: {name}")
        for row in rows:
            path = safe_path(root, row["path"])
            if path.stat().st_size != row["size"] or sha256(path) != row["sha256"]:
                raise ValueError(f"provenance source changed: {row['path']}")
    if (reference / "manifest.sha256").read_text(encoding="utf-8-sig").strip() != sha256(
        reference / "manifest.json"
    ):
        raise ValueError("E3 manifest checksum mismatch")
    e3_hashes = read_json(reference / "manifest.json")["file_hashes"]
    for name in E3_FILES:
        if e3_hashes.get(name) != sha256(reference / name):
            raise ValueError(f"E3 preserved manifest member changed: {name}")
    return provenance


def check_run_provenance(json_rows, csv_rows, expected):
    """Bind original economic identities and the new postprocessor separately."""
    calculated = unique_index(expected, ("run_id",))
    for rows in (json_rows, csv_rows):
        observed = unique_index(rows, ("run_id",))
        if set(observed) != set(calculated):
            raise ValueError("run provenance coverage mismatch")
        for key, values in calculated.items():
            if set(observed[key]) != set(values):
                raise ValueError(f"run provenance fields mismatch: {key}")
            for field, value in values.items():
                equal(observed[key][field], value, f"run provenance {key}/{field}")


def _check_e3_summaries(original, calculated, periods):
    """Compare every populated editorial cell, including source run identities."""
    period_map = {"2024-2026-08": "2024+"}
    aliases = {"cash_or_dust_seconds": "no_active_seconds", "flat_seconds": "no_inventory_seconds",
               "any_covered_seconds": "covered_seconds", "any_unhedged_seconds": "unhedged_seconds"}
    keys = ("strategy", "period", "symbol")
    observed = unique_index([r for r in calculated if r["scenario"] == "BASE_E3"
                             and r["period"] in periods], keys)
    reference = unique_index([dict(r, period=period_map.get(r["period"], r["period"]))
                              for r in original], keys)
    required = {(strategy, period, symbol) for strategy in ("conditional", "permanent")
                for period in periods for symbol in (*SYMBOLS, "PORTFOLIO")}
    if set(observed) != required or set(reference) != required:
        raise ValueError("E3 summary period/strategy/symbol coverage mismatch")
    for key, source in reference.items():
        row = observed[key]
        equal(row.get("run_id"), source["source_run_id"], f"E3 summary {key}/source_run_id")
        mandatory = {"invested_seconds", "calendar_seconds"}
        mandatory |= ({"any_unhedged_seconds", "any_covered_seconds", "both_covered_seconds",
                       "cash_or_dust_seconds"} if source["symbol"] == "PORTFOLIO" else
                      {"covered_seconds", "unhedged_seconds", "dust_seconds", "flat_seconds"})
        if any(source.get(name) in (None, "") for name in mandatory):
            raise ValueError(f"E3 missing summary evidence: {key}")
        for field, value in source.items():
            if field in {*keys, "source_run_id"} or value == "":
                continue
            target = aliases.get(field, field)
            equal(row.get(target), number(value), f"E3 summary {key}/{field}")


def check_e3_equivalence(package, intervals, summaries, episode):
    """Require exact E3 intervals and seconds, without a rounding tolerance."""
    reference = Path(package) / "referencia_e3/tablas"
    originals = read_csv(reference / "exposicion_intervalos.csv")
    keys = ("strategy", "symbol", "start_ns", "end_ns")
    def indexed(rows):
        return unique_index([dict(r, start_ns=int(r["start_ns"]), end_ns=int(r["end_ns"]))
                             for r in rows], keys)
    old = indexed(originals)
    new = indexed([r for r in intervals if r["scenario"] == "BASE_E3"])
    if set(old) != set(new) or {r["strategy"] for r in originals} != {"conditional", "permanent"}:
        raise ValueError("E3 exact interval boundary/coverage mismatch")
    numeric = {"start_ns", "end_ns", "seconds", "spot", "short", "collateral_usdt"}
    required = {*numeric, "symbol", "start_utc", "end_exclusive_utc", "exposure", "state",
                "strategy", "source_run_id"}
    for key, source in old.items():
        if set(source) != required:
            raise ValueError(f"E3 missing/unexpected interval fields: {key}")
        for field, value in source.items():
            target = "run_id" if field == "source_run_id" else field
            expected = number(value) if field in numeric else value
            equal(new[key].get(target), expected, f"E3 interval {key}/{field}")
    _check_e3_summaries(read_csv(reference / "tiempo_invertido.csv"), summaries,
                        ("full", "2022-2023", "2024+"))
    _check_e3_summaries(read_csv(reference / "episodio_2023_03_24_exposicion.csv"), episode,
                        ("2023-03-24",))
    return [dict(strategy=strategy,
                 intervals_checked=sum(r["strategy"] == strategy for r in originals),
                 summaries_checked=9, episode_rows_checked=3, exact=True, terminal_difference_ns=0)
            for strategy in ("conditional", "permanent")]


def check_derived_tables(package, parent, metrics, previous, h2, summaries, episode):
    comparison = package / "comparacion"
    keys = ("scenario", "strategy", "run_id", "period")
    before = unique_index(previous, keys)
    after = unique_index(metrics, keys)
    portfolio = unique_index([r for r in summaries if r["symbol"] == "PORTFOLIO"], keys)
    old_h2 = unique_index(read_csv(parent / "comparacion/h2.csv"), ("scenario", "period"))
    new_h2 = unique_index(h2, ("scenario", "period"))
    change_rows = read_csv(comparison / "antes_despues.csv")
    changes = unique_index(change_rows, keys)
    if set(changes) != set(before):
        raise ValueError("before/after table coverage mismatch")
    for key, row in changes.items():
        old, current = before[key], portfolio[key]
        for field in ("start_utc", "end_exclusive_utc"):
            equal(row.get(field), old[field], f"before/after {field}")
        for field in ("invested_seconds", "unhedged_seconds", "invested_fraction"):
            equal(row.get(f"old_{field}"), number(old[field]), f"before/after old_{field}")
        for field in (
            "raw_invested_seconds", "raw_unhedged_seconds", "raw_invested_fraction",
            "invested_seconds", "unhedged_seconds", "covered_seconds", "dust_seconds",
            "dust_only_seconds", "no_active_seconds", "no_inventory_seconds",
            "calendar_seconds", "invested_fraction",
        ):
            equal(row.get(field), current[field], f"before/after {field}")
        for field in ("invested_seconds", "unhedged_seconds"):
            equal(row.get(f"delta_{field}"), current[field] - number(old[field]), f"delta {field}")
        hkey = row["scenario"], row["period"]
        equal(row.get("h2_before"), old_h2[hkey]["verdict"], "before/after old H2")
        equal(row.get("h2_after"), new_h2[hkey]["verdict"], "before/after new H2")
        equal(row.get("h2_changed"), old_h2[hkey]["verdict"] != new_h2[hkey]["verdict"], "H2 changed")
    h2_changes = unique_index(read_csv(comparison / "h2_cambios.csv"), ("scenario", "period"))
    if set(h2_changes) != set(new_h2):
        raise ValueError("H2 change table coverage mismatch")
    for key, row in h2_changes.items():
        for field in ("conditional_run_id", "permanent_run_id"):
            equal(row.get(field), new_h2[key][field], f"H2 changes {field}")
        equal(row.get("verdict_before"), old_h2[key]["verdict"], "H2 before")
        equal(row.get("verdict_after"), new_h2[key]["verdict"], "H2 after")
        equal(row.get("changed"), old_h2[key]["verdict"] != new_h2[key]["verdict"], "H2 change")
    preserved = unique_index(read_csv(comparison / "preservacion_financiera.csv"), (*keys, "metric"))
    expected_preserved = {
        (*key, field): value for key, row in before.items() for field, value in row.items()
        if field not in EXPOSURE_FIELDS
    }
    if set(preserved) != set(expected_preserved):
        raise ValueError("financial preservation table coverage mismatch")
    for key, value in expected_preserved.items():
        row = preserved[key]
        equal(row.get("value_before"), value, f"preservation before {key}")
        equal(row.get("value_after"), after[key[:4]][key[-1]], f"preservation after {key}")
        equal(row.get("unchanged"), True, f"preservation flag {key}")
    preserved_files = unique_index(read_csv(comparison / "preservacion_tablas.csv"), ("path",))
    mandatory = {f"comparacion/{name}" for name in PRESERVED_TABLES} | {"indice_corridas.json"}
    if not mandatory <= {key[0] for key in preserved_files}:
        raise ValueError("incomplete preserved-file table")
    for (name,), row in preserved_files.items():
        old_hash = sha256(safe_path(parent, name))
        new_hash = sha256(safe_path(package, name))
        equal(row.get("parent_sha256"), old_hash, "preserved table parent hash")
        equal(row.get("corrected_sha256"), new_hash, "preserved table corrected hash")
        equal(row.get("equal_bytes"), old_hash == new_hash, "preserved table bytes")
        if old_hash != new_hash:
            raise ValueError(f"preserved table differs: {name}")
    figure_rows = read_csv(comparison / "figuras/exposicion_datos.csv")
    if figure_rows != [r for r in change_rows if r["period"] == "full"]:
        raise ValueError("figure source data differs from full-period comparison")
    actual_episode = read_csv(comparison / "episodio_2023_03_24.csv")
    episode_keys = (*keys, "symbol")
    observed_episode = unique_index(actual_episode, episode_keys)
    expected_episode = unique_index(episode, episode_keys)
    if set(observed_episode) != set(expected_episode):
        raise ValueError("episode table coverage mismatch")
    for key, row in expected_episode.items():
        for field, value in row.items():
            equal(observed_episode[key].get(field), value, f"episode {key}/{field}")
        if row["scenario"] == "BASE_E3" and (
            row["symbol"] == "PORTFOLIO" or row["strategy"] == "permanent"
            or row["symbol"] == "ETHUSDT"
        ):
            equal(row["unhedged_seconds"], D(7260), "BASE March-24 active exposure")
    _check_deltas(package, parent, metrics)


def _check_deltas(package, parent, metrics):
    keys = ("scenario", "strategy", "period", "metric")
    old = unique_index(read_csv(parent / "comparacion/deltas.csv"), keys)
    new = unique_index(read_csv(package / "comparacion/deltas.csv"), keys)
    metric_index = unique_index(metrics, ("scenario", "strategy", "period"))
    exposure = {k for r in metrics for k in r if k.endswith(("_seconds", "_fraction"))}
    # The financial table includes no unrelated fraction counters; only declared
    # operational fields are recalculated. All other original cells stay exact.
    for key, row in old.items():
        if key not in new:
            raise ValueError("missing previous delta")
        if key[-1] not in exposure and new[key] != row:
            raise ValueError(f"financial delta changed: {key}")
    comparators = {
        "BASE_E3": None, "BTC_PROMO_REALIZADA": "BASE_E3",
        "BTC_PROMO_DECISION": "BTC_PROMO_REALIZADA", "FUT4_REALIZADA": "BASE_E3",
        "FUT4_DECISION": "FUT4_REALIZADA", "MARGEN_2X": "BASE_E3",
    }
    expected_exposure = set()
    for (scenario, strategy, period), row in metric_index.items():
        comparator = comparators[scenario]
        if comparator is None:
            continue
        peer = metric_index[comparator, strategy, period]
        for field in exposure:
            if field not in row:
                continue
            key = scenario, strategy, period, field
            expected_exposure.add(key)
            if key not in new:
                raise ValueError(f"missing exposure delta: {key}")
            actual = new[key]
            for name, value in (
                ("comparator", comparator), ("run_id", row["run_id"]),
                ("comparator_run_id", peer["run_id"]), ("value", number(row[field])),
                ("comparator_value", number(peer[field])),
                ("delta", number(row[field]) - number(peer[field])), ("reason", ""),
            ):
                equal(actual.get(name), value, f"exposure delta {key}/{name}")
    if set(new) != set(old) | expected_exposure:
        raise ValueError("unexpected new delta rows")


def verify_package(package, parent):
    package, parent = Path(package).resolve(), Path(parent).resolve()
    if package == parent or package.is_relative_to(parent) or parent.is_relative_to(package):
        raise ValueError("correction and parent must be separate packages")
    manifest = check_manifest(package, SCHEMA)
    check_manifest(parent, KNOWN_PARENT_SCHEMA)
    provenance = _check_provenance(package, parent, manifest)
    original = _archived_verifier(parent)
    parent_result = original.verify_package(parent)
    if parent_result.get("status") != "passed":
        raise ValueError("parent original verification failed")
    if (package / "indice_corridas.json").read_bytes() != (parent / "indice_corridas.json").read_bytes():
        raise ValueError("run registry changed")
    items = read_json(parent / "indice_corridas.json")["runs"]
    if len(items) != 12 or any(i["status"] not in {"ejecutado", "reutilizado_verificado"} for i in items):
        raise ValueError("correction requires the twelve successful parent portfolios")
    unique_index(items, ("run_id",))
    unique_index(items, ("scenario", "strategy"))
    for name in PRESERVED_TABLES:
        relative = f"comparacion/{name}"
        if (package / relative).read_bytes() != (parent / relative).read_bytes():
            raise ValueError(f"preserved table changed: {relative}")
    comparison = package / "comparacion"
    metrics = read_csv(comparison / "metricas_cartera_periodo.csv")
    previous = read_csv(parent / "comparacion/metricas_cartera_periodo.csv")
    check_financial_preservation(metrics, previous)
    h2 = read_csv(comparison / "h2.csv")
    validate_h2_rows(h2, metrics)
    intervals = read_csv(comparison / "exposicion_intervalos.csv")
    summaries = read_csv(comparison / "exposicion_periodo.csv")
    from pyarrow import parquet
    all_expected = []
    all_expected_intervals = []
    episode_expected = []
    run_provenance = []
    checked_intervals = 0
    for item in items:
        run = safe_path(parent, item["path"])
        run_manifest = read_json(run / "run_manifest.json")
        config = run_manifest["config"]
        source = parquet.ParquetFile(run / "positions.parquet").read().to_pylist()
        start, end = timestamp(config["start"]), timestamp(config["end"])
        identity = {key: item[key] for key in ("scenario", "strategy", "run_id")}
        selected = [r for r in intervals if r["run_id"] == item["run_id"]]
        for row in selected:
            if any(row[key] != value for key, value in identity.items()):
                raise ValueError("interval run/scenario/strategy mismatch")
        expected_intervals = check_interval_rows(selected, source, start, end, number(config["hedge_tolerance"]))
        checked_intervals += len(expected_intervals)
        all_expected_intervals.extend(dict(identity, **row) for row in expected_intervals)
        periods = original.periods(config)
        expected_summary = [dict(identity, **row) for row in aggregate_intervals(
            expected_intervals, periods)]
        stored_summary = [r for r in summaries if r["run_id"] == item["run_id"]]
        check_summaries(stored_summary, expected_summary)
        all_expected.extend(expected_summary)
        day = timestamp("2023-03-24T00:00:00Z")
        if item["scenario"] == "BASE_E3":
            episode_expected.extend(dict(identity, **row) for row in aggregate_intervals(
                expected_intervals, [("2023-03-24", day, day + 86400*SECOND)]))
        run_provenance.append(dict(
            identity, status=item["status"], engine_status=run_manifest["status"],
            engine_code_hash=run_manifest["code_hash"],
            run_manifest_sha256=sha256(run / "run_manifest.json"),
            positions_rows=len(source), postprocessor_version=VERSION))
    if checked_intervals != len(intervals) or len(all_expected) != len(summaries):
        raise ValueError("unexpected exposure run rows")
    check_run_provenance(provenance.get("runs", []),
                         read_csv(comparison / "procedencia_corridas.csv"), run_provenance)
    expected_portfolio = unique_index([r for r in all_expected if r["symbol"] == "PORTFOLIO"],
                                      ("scenario", "strategy", "run_id", "period"))
    for row in metrics:
        key = tuple(row[k] for k in ("scenario", "strategy", "run_id", "period"))
        for field, value in expected_portfolio[key].items():
            if field.endswith(("_seconds", "_fraction")):
                equal(row.get(field), value, f"metric exposure {key}/{field}")
    check_derived_tables(package, parent, metrics, previous, h2, all_expected, episode_expected)
    e3_equivalence = check_e3_equivalence(package, all_expected_intervals, all_expected,
                                        episode_expected)
    rounded_controls = {}
    for strategy, rounded in (("conditional", D("28.32")), ("permanent", D("98.21"))):
        full = next(r for r in all_expected if r["scenario"] == "BASE_E3"
                    and r["strategy"] == strategy and r["period"] == "full"
                    and r["symbol"] == "PORTFOLIO")
        percentage = (full["invested_fraction"] * 100).quantize(D("0.01"))
        equal(percentage, rounded, f"E3 printed rounding control {strategy}")
        rounded_controls[strategy] = str(percentage)
    return dict(status="passed", schema=SCHEMA, members_checked=len(manifest["members"]),
                parent_manifest_sha256=sha256(parent / "manifiesto_paquete.json"),
                parent_verification=parent_result, runs_checked=len(items),
                h2_rows_checked=len(h2), intervals_checked=checked_intervals,
                exposure_summaries_checked=len(summaries), financial_rows_unchanged=len(metrics),
                base_e3_equivalence=e3_equivalence, base_e3_percent_rounded=rounded_controls,
                source_files_checked=len(provenance["source_files"]),
                run_provenance_checked=len(run_provenance),
                package_read_only=True, parent_read_only=True, engine_reexecution=False,
                dependency="explicit parent package and PyArrow required; not self-contained")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output:
            check_output(args.output, args.package, args.parent)
        result = verify_package(args.package, args.parent)
    except (ValueError, OSError, KeyError, TypeError, ImportError, ArithmeticError) as exc:
        result = dict(status="failed", error=str(exc), package_read_only=True, parent_read_only=True)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output and result["status"] == "passed":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(text)
    sys.stdout.write(text)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

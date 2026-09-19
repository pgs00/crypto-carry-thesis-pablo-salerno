"""Audit persisted entry basis directly against Binance's original one-minute CSVs.

This script deliberately imports no crypto_carry modules. Market observations
are keyed by symbol and decision timestamp; strategy decisions stay separate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import platform
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

D = Decimal
SECOND = 1_000_000_000
MINUTE = 60 * SECOND
TOLERANCE = D("1e-12")
ENTRY_ORDER = (
    "state_active",
    "cooldown",
    "pending_orders",
    "debt",
    "coverage",
    "forecast",
    "rules",
    "operational",
    "mark",
    "price_alignment",
    "freshness",
    "funding",
    "basis_negative",
    "basis_above_max",
    "sizing",
    "budget",
)
HEADER = (
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
STRATEGIES = ("conditional", "permanent")
PROJECT = Path(__file__).resolve().parents[3]


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def utc(value):
    seconds, nanoseconds = divmod(int(value), SECOND)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S") + (
        f".{nanoseconds:09d}Z"
    )


def iso_ns(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()) * SECOND


def raw_basis(spot, future):
    with localcontext() as context:
        context.prec = 60
        return D(future) / D(spot) - 1


def classify(value):
    if value is None:
        return "not_evaluable"
    value = D(value)
    if value < 0:
        return "negative"
    if value == 0:
        return "zero"
    return "positive_eligible" if value <= D("0.005") else "above_max"


def compare_basis(independent, stored):
    if independent is None or stored in (None, ""):
        return dict(
            difference=None,
            exceeds_tolerance=False,
            classification_changed=classify(independent) != classify(stored or None),
        )
    with localcontext() as context:
        context.prec = 60
        difference = D(stored) - independent
    return dict(
        difference=difference,
        exceeds_tolerance=abs(difference) > TOLERANCE,
        classification_changed=classify(independent) != classify(stored),
    )


def parse_kline(values, unit):
    if len(values) != 12:
        raise ValueError("Expected 12 Binance kline fields")
    if unit not in ("ms", "us"):
        raise ValueError(f"Unsupported timestamp unit: {unit}")
    scale = {"ms": 1_000_000, "us": 1_000}[unit]
    opening, closing = int(values[0]) * scale, int(values[6]) * scale
    if opening % MINUTE or closing != opening + MINUTE - scale:
        raise ValueError("Not a complete, aligned one-minute interval")
    prices = [D(values[i]) for i in (1, 2, 3, 4)]
    if any(not p.is_finite() or p <= 0 for p in prices):
        raise ValueError("Non-positive or non-finite OHLC")
    op, high, low, close = prices
    if not low <= op <= high or not low <= close <= high:
        raise ValueError("Invalid OHLC order")
    volume, quote, trades = D(values[5]), D(values[7]), int(values[8])
    if not volume.is_finite() or not quote.is_finite() or min(volume, quote, trades) < 0:
        raise ValueError("Invalid volume or trade count")
    return dict(
        open_time=opening,
        end_time=opening + MINUTE,
        available_at=opening + MINUTE,
        reported_close_ns=closing,
        source_open_raw=values[0],
        source_close_raw=values[6],
        timestamp_unit=unit,
        open=values[1],
        high=values[2],
        low=values[3],
        close=values[4],
        base_volume=values[5],
        quote_volume=values[7],
        trade_count=trades,
        raw_record=",".join(values),
    )


def pair_issues(spot, future, now):
    issues = []
    expected_open = now // MINUTE * MINUTE - MINUTE
    for market, row in (("spot", spot), ("futures", future)):
        if row is None:
            issues.append(f"source_missing:{market}")
            continue
        if row["available_at"] > now or row["end_time"] > now:
            issues.append(f"future_bar:{market}")
        if row["open_time"] != expected_open:
            issues.append(f"not_latest_closed_minute:{market}")
        if D(row["base_volume"]) <= 0 or row["trade_count"] <= 0:
            issues.append(f"no_activity:{market}")
    if (
        spot
        and future
        and (spot["open_time"], spot["end_time"]) != (future["open_time"], future["end_time"])
    ):
        issues.append("interval_mismatch")
    return issues


def price_chain_issues(original, normalized, selected):
    if original is None:
        return ["original_source_missing"]
    if normalized is None:
        return ["normalized_source_missing"]
    issues = []
    for field in (
        "open",
        "high",
        "low",
        "close",
        "base_volume",
        "quote_volume",
        "trade_count",
        "open_time",
        "end_time",
        "available_at",
    ):
        if D(str(original[field])) != D(str(normalized[field])):
            issues.append(f"source_to_normalized:{field}")
    if selected is None or D(normalized["close"]) != D(selected):
        issues.append("normalized_to_signal:close")
    return issues


def read_original_rows(path, unit, wanted):
    """Read original CSV records by timestamp, preserving physical line numbers."""
    result, previous, gaps, count, header_seen = {}, None, 0, 0, False
    multiplier = {"ms": 1_000_000, "us": 1_000}[unit]
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"Expected one CSV in {path}")
        member = members[0]
        with archive.open(member) as stream:
            for line, values in enumerate(csv.reader(io.TextIOWrapper(stream)), 1):
                if line == 1 and values and not values[0].isdigit():
                    if tuple(values) != HEADER:
                        raise ValueError(f"Unexpected kline header: {path}")
                    header_seen = True
                    continue
                if len(values) != 12:
                    raise ValueError(f"Expected 12 fields: {path}:{line}")
                opening = int(values[0]) * multiplier
                # Independent magnitude check catches incorrect declared units.
                if not iso_ns("2017-01-01T00:00:00Z") <= opening < iso_ns("2100-01-01T00:00:00Z"):
                    raise ValueError(f"Timestamp magnitude/unit mismatch: {path}:{line}")
                if previous is not None:
                    if opening <= previous:
                        raise ValueError(f"Out-of-order or duplicate open: {path}:{line}")
                    gaps += max(0, (opening - previous) // MINUTE - 1)
                previous, count = opening, count + 1
                if opening in wanted:
                    row = parse_kline(values, unit)
                    result[opening] = dict(row, member=member, source_line=line)
    return result, dict(
        csv_member=member,
        header=header_seen,
        scanned_rows=count,
        missing_minutes_between_rows=gaps,
        selected_rows=len(result),
    )


def first_rejection(filters, funding_enabled):
    for name in ENTRY_ORDER:
        if name == "funding" and not funding_enabled:
            continue
        value = filters[name]
        if value == "fail":
            return name
        if value == "not_evaluable":
            return f"not_evaluable:{name}"
    return None


def select_sample(rows):
    """Select 20 unique rows: extrema, four nearest zero, then spread in time."""
    rows = sorted(rows, key=lambda row: int(row["decision_time_ns"]))
    if len(rows) < 20:
        raise ValueError("The prescribed sample requires at least 20 observations")
    valid = [r for r in rows if r.get("basis_independent") not in (None, "")]
    choices = {}

    def add(row, reason):
        key = row["decision_time_ns"]
        if key not in choices and len(choices) < 20:
            choices[key] = dict(row, sample_reason=reason)

    if valid:
        add(min(valid, key=lambda r: D(r["basis_independent"])), "minimum")
        add(max(valid, key=lambda r: D(r["basis_independent"])), "maximum")
        for row in sorted(
            valid, key=lambda r: (abs(D(r["basis_independent"])), r["decision_time_ns"])
        )[:4]:
            add(row, "nearest_zero")
    slots = 20 - len(choices)
    for index in range(slots):
        add(rows[index * (len(rows) - 1) // (slots - 1)], f"temporal_grid_{index}/{slots - 1}")
    # Fill overlaps by maximizing distance to existing selections, with an early tie break.
    while len(choices) < 20:
        remaining = [r for r in rows if r["decision_time_ns"] not in choices]
        row = max(remaining, key=lambda r: min(abs(r["decision_time_ns"] - t) for t in choices))
        add(row, "largest_temporal_distance")
    return sorted(choices.values(), key=lambda row: row["decision_time_ns"])


def read_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def verify_manifest(folder, name):
    path = folder / (name + ".json")
    expected = (folder / (name + ".sha256")).read_text().strip()
    if sha256(path) != expected:
        raise ValueError(f"Manifest checksum mismatch: {path}")
    manifest = read_json(path)
    for relative, digest in manifest["output_hashes"].items():
        if sha256(folder / relative) != digest:
            raise ValueError(f"Artifact checksum mismatch: {folder / relative}")
    return manifest


def verify_code(run_manifest):
    audited = (
        "data/normalize.py",
        "data/replay.py",
        "strategy.py",
        "models.py",
        "events.py",
        "risk.py",
        "diagnostics.py",
        "config.py",
    )
    for name in audited:
        relative = "src/crypto_carry/" + name
        if sha256(PROJECT / relative) != run_manifest["code_files"][relative]:
            raise ValueError(f"Current audited engine differs from the saved run: {relative}")


def load_sources(root, run, manifest, groups):
    processed = read_json(run / "source_manifests/processed.json")
    downloaded = read_json(run / "source_manifests/download.json")
    downloads = {entry["path"]: entry for entry in downloaded["entries"]}
    wanted = defaultdict(set)
    for symbol, now in groups:
        opening = now // MINUTE * MINUTE - MINUTE
        for market in ("spot", "futures"):
            wanted[(symbol, market, utc(opening)[:7])].add(opening)
    raw, normalized, evidence = {}, {}, []
    for key, openings in sorted(wanted.items()):
        symbol, market, month = key
        entries = [
            e
            for e in processed["entries"]
            if e.get("dataset") == "minute_bars" and (e["symbol"], e["market"], e["date"]) == key
        ]
        if len(entries) != 1:
            raise ValueError(f"Missing or ambiguous processed partition: {key}")
        entry = entries[0]
        download = downloads[entry["source_path"]]
        branch = "spot" if market == "spot" else "futures/um"
        filename = f"{symbol}-1m-{month}.zip"
        expected_url = (
            f"https://data.binance.vision/data/{branch}/monthly/klines/{symbol}/1m/{filename}"
        )
        if (
            download["source_url"] != expected_url
            or download["dataset"] != "klines"
            or (download["symbol"], download["market"]) != (symbol, market)
        ):
            raise ValueError(f"Unexpected instrument or source: {download['source_url']}")
        unit = "us" if market == "spot" and month >= "2025-01" else "ms"
        if download["timestamp_unit"] != unit or entry["timestamp_unit"] != unit:
            raise ValueError(f"Timestamp convention mismatch: {key}")
        source = root / entry["source_path"]
        partition = root / entry["path"]
        checksum_file = root / download["checksum_path"]
        source_digest = sha256(source)
        checksum_tokens = checksum_file.read_text().split()
        if (
            source_digest != download["sha256"]
            or source_digest != entry["source_sha256"]
            or source_digest != checksum_tokens[0]
            or checksum_tokens[1].lstrip("*") != filename
            or sha256(checksum_file) != download["checksum_file_sha256"]
        ):
            raise ValueError(f"Original ZIP checksum mismatch: {source}")
        if sha256(partition) != entry["sha256"] or entry["sha256"] != manifest["input_hashes"].get(
            entry["path"]
        ):
            raise ValueError(f"Processed input differs from run: {partition}")
        originals, stats = read_original_rows(source, unit, openings)
        table = pq.ParquetFile(partition).read()
        times = table["open_time"].to_pylist()
        if len(times) != len(set(times)) or times != sorted(times):
            raise ValueError(f"Duplicate or unordered normalized timestamps: {partition}")
        selected = table.filter(pc.is_in(table["open_time"], value_set=pa.array(sorted(openings))))
        normalized_rows = {r["open_time"]: r for r in selected.to_pylist()}
        for opening in openings:
            row_key = symbol, market, opening
            original = originals.get(opening)
            if original:
                raw[row_key] = dict(
                    original,
                    source_path=entry["source_path"],
                    source_url=expected_url,
                    source_sha256=source_digest,
                )
            if opening in normalized_rows:
                item = normalized_rows[opening]
                if (item["symbol"], item["market"], item["source_file"]) != (
                    symbol,
                    market,
                    filename,
                ):
                    raise ValueError(f"Normalized instrument/source mismatch: {row_key}")
                normalized[row_key] = dict(item, partition_path=entry["path"])
        evidence.append(
            dict(
                symbol=symbol,
                market=market,
                month=month,
                source_path=entry["source_path"],
                source_url=expected_url,
                source_sha256=source_digest,
                timestamp_unit=unit,
                checksum_path=download["checksum_path"],
                checksum_sha256=sha256(checksum_file),
                partition_path=entry["path"],
                partition_sha256=entry["sha256"],
                **stats,
            )
        )
    return raw, normalized, evidence


def audit_market(window, run_id, symbol, now, signals, raw, normalized):
    opening = now // MINUTE * MINUTE - MINUTE
    originals = [raw.get((symbol, market, opening)) for market in ("spot", "futures")]
    issues = pair_issues(*originals, now)
    independent = raw_basis(originals[0]["close"], originals[1]["close"]) if not issues else None
    row = dict(
        window=window,
        symbol=symbol,
        observation_id=f"{window}:{symbol}:{now}",
        run_id=run_id,
        decision_time_ns=now,
        decision_utc=utc(now),
        expected_open_ns=opening,
        expected_open_utc=utc(opening),
        basis_independent=str(independent) if independent is not None else None,
        classification_audited=classify(independent),
        original_source_covered=all(item is not None for item in originals),
    )
    strategy_rows = {signal["strategy"]: signal for signal in signals}
    if len(signals) != 2 or set(strategy_rows) != set(STRATEGIES):
        issues.append("duplicate_or_missing_strategy_observation")
    price_errors, basis_errors, classification_errors = [], [], []
    for market, original in zip(("spot", "futures"), originals):
        normal = normalized.get((symbol, market, opening))
        if original:
            for field in (
                "source_path",
                "source_url",
                "source_sha256",
                "member",
                "source_line",
                "raw_record",
                "source_open_raw",
                "source_close_raw",
                "timestamp_unit",
                "reported_close_ns",
                "open_time",
                "end_time",
                "available_at",
                "close",
            ):
                row[f"{market}_original_{field}"] = original[field]
            row[f"{market}_interval_utc"] = (
                f"[{utc(original['open_time'])},{utc(original['end_time'])})"
            )
            row[f"{market}_available_utc"] = utc(original["available_at"])
        if normal:
            for field in ("partition_path", "close", "open_time", "end_time", "available_at"):
                row[f"{market}_normalized_{field}"] = normal[field]
        for strategy, signal in sorted(strategy_rows.items()):
            prefix = f"{market}_{strategy}"
            for field in ("price", "open_time", "end_time", "available_at", "price_time"):
                row[f"{prefix}_{field}"] = signal.get(f"{market}_{field}")
            selected = signal.get(f"{market}_price")
            for issue in price_chain_issues(original, normal, selected):
                price_errors.append(f"{market}:{strategy}:{issue}")
            if normal:
                for field in ("open_time", "end_time", "available_at"):
                    if int(signal.get(f"{market}_{field}") or -1) != normal[field]:
                        price_errors.append(f"{market}:{strategy}:normalized_to_signal:{field}")
                if int(signal.get(f"{market}_price_time") or -1) != normal["end_time"]:
                    price_errors.append(f"{market}:{strategy}:signal_event_time")
    for strategy, signal in sorted(strategy_rows.items()):
        row[f"{strategy}_signal_id"] = signal["audit_signal_id"]
        row[f"{strategy}_funding_anchor_ns"] = signal["anchor"]
        row[f"{strategy}_funding_anchor_utc"] = utc(signal["anchor"])
        row[f"{strategy}_basis_persisted"] = signal.get("basis")
        row[f"{strategy}_basis_raw_persisted"] = signal.get("basis_raw")
        row[f"{strategy}_classification_original"] = classify(signal.get("basis"))
        for field in ("basis", "basis_raw"):
            comparison = compare_basis(independent, signal.get(field))
            row[f"{strategy}_{field}_difference"] = comparison["difference"]
            if comparison["exceeds_tolerance"]:
                basis_errors.append(f"{strategy}:{field}:numeric_difference")
            if comparison["classification_changed"]:
                classification_errors.append(f"{strategy}:{field}:classification_changed")
        if int(signal["anchor"]) + 60 * SECOND != now:
            issues.append(f"{strategy}:decision_not_anchor_plus_60s")
        if int(signal["forecast_available_at"]) > now:
            issues.append(f"{strategy}:future_forecast")
    row["source_to_normalized_discrepancies"] = sum(
        "source_to_normalized" in e for e in price_errors
    )
    row["normalized_to_signal_discrepancies"] = sum(
        "normalized_to_signal" in e for e in price_errors
    )
    row["classification_discrepancies"] = len(classification_errors)
    row["basis_discrepancies"] = len(basis_errors)
    issues += price_errors + basis_errors + classification_errors
    row["first_divergence"] = issues[0] if issues else "none"
    row["discrepancy_reasons"] = json_text(issues)
    row["audit_status"] = "discrepancy" if issues else "verified"
    return row


def audit_decision(window, signal, market, opening_orders):
    """Reconcile basis/funding gates and their persisted ordering, not the full portfolio."""
    strategy, symbol = signal["strategy"], signal["symbol"]
    now = int(signal["time_ns"])
    enabled = strategy == "conditional"
    filters = {name: signal[f"filter_{name}"] for name in ENTRY_ORDER}
    original_filters = dict(filters)
    value = market["basis_independent"]
    value = D(value) if value is not None else None
    filters["basis_negative"] = (
        "not_evaluable" if value is None else "fail" if value < 0 else "pass"
    )
    filters["basis_above_max"] = (
        "not_evaluable" if value is None else "fail" if value > D("0.005") else "pass"
    )
    forecast, cost = signal.get("forecast"), signal.get("estimated_cycle_cost")
    filters["funding"] = (
        "not_evaluable"
        if forecast is None or cost is None or signal["filter_forecast"] != "pass"
        else "pass"
        if D(forecast) > D(cost)
        else "fail"
    )
    filters["state_active"] = (
        "pass" if signal["portfolio_state"] in {"FLAT", "COOLDOWN"} else "fail"
    )
    filters["cooldown"] = "fail" if now < int(signal["cooldown_until"]) else "pass"
    expected = first_rejection(filters, enabled)
    errors = []
    for name in ("basis_negative", "basis_above_max", "funding", "state_active", "cooldown"):
        if original_filters[name] != filters[name]:
            errors.append(f"filter_classification:{name}")
    if bool(signal["funding_filter_enabled"]) != enabled:
        errors.append("funding_enablement")
    if json.loads(signal["filter_order"]) != list(ENTRY_ORDER):
        errors.append("filter_order")
    if signal["sequential_rejection"] != expected:
        errors.append("sequential_rejection")
    if int(signal["decision_time"]) != now:
        errors.append("decision_time")
    decision_map = {
        None: "accepted",
        "state_active": "state_or_cooldown",
        "cooldown": "state_or_cooldown",
        "pending_orders": "state_or_cooldown",
        "debt": "debt_or_insolvency",
        "funding": "funding_not_above_cost",
        "basis_negative": "basis_outside_entry_range",
        "basis_above_max": "basis_outside_entry_range",
        "budget": "insufficient_free_funds",
        "sizing": "joint_sizing_infeasible",
    }
    expected_decision = decision_map.get(expected, "invalid_or_stale_data")
    if signal["decision"] != expected_decision:
        errors.append("actual_decision")
    order_ids = sorted(opening_orders.get((strategy, symbol, now), set()))
    if bool(order_ids) != (signal["decision"] == "accepted") or len(order_ids) > 1:
        errors.append("entry_order_link")
    theoretical = [name for name, state in filters.items() if state == "fail"]
    operative = [name for name in theoretical if name != "funding" or enabled]
    return dict(
        window=window,
        symbol=symbol,
        strategy=strategy,
        observation_id=market["observation_id"],
        signal_id=signal["audit_signal_id"],
        decision_time_ns=now,
        decision_utc=utc(now),
        portfolio_state=signal["portfolio_state"],
        cooldown_until=signal["cooldown_until"],
        funding_filter_enabled=enabled,
        forecast=forecast,
        estimated_cycle_cost=cost,
        basis_original=signal.get("basis"),
        basis_audited=market["basis_independent"],
        classification_original=classify(signal.get("basis")),
        classification_audited=market["classification_audited"],
        theoretical_failures=json_text(theoretical),
        applicable_failures=json_text(operative),
        original_filters=json_text(original_filters),
        audited_filters=json_text(filters),
        sequential_original=signal["sequential_rejection"],
        sequential_audited=expected,
        actual_decision=signal["decision"],
        audited_decision=expected_decision,
        entry_order_ids=json_text(order_ids),
        discrepancy_reasons=json_text(errors),
        audit_status="discrepancy" if errors else "verified",
    )


def summarize(markets, decisions):
    result = []
    for key in sorted({(r["window"], r["symbol"]) for r in markets}):
        rows = [r for r in markets if (r["window"], r["symbol"]) == key]
        values = sorted(
            D(r["basis_independent"]) for r in rows if r["basis_independent"] is not None
        )
        errors = [
            abs(D(r[f"{strategy}_{field}_difference"]))
            for r in rows
            for strategy in STRATEGIES
            for field in ("basis", "basis_raw")
            if r.get(f"{strategy}_{field}_difference") is not None
        ]
        classifications = Counter(classify(v) for v in values)
        strategy_rows = [r for r in decisions if (r["window"], r["symbol"]) == key]
        result.append(
            dict(
                window=key[0],
                symbol=key[1],
                observations=len(rows),
                original_source_covered=sum(r["original_source_covered"] for r in rows),
                evaluated=len(values),
                verified=sum(r["audit_status"] == "verified" for r in rows),
                discrepancies=sum(r["audit_status"] != "verified" for r in rows),
                decision_discrepancies=sum(r["audit_status"] != "verified" for r in strategy_rows),
                source_to_normalized_discrepancies=sum(
                    r["source_to_normalized_discrepancies"] for r in rows
                ),
                normalized_to_signal_discrepancies=sum(
                    r["normalized_to_signal_discrepancies"] for r in rows
                ),
                classification_discrepancies=sum(r["classification_discrepancies"] for r in rows),
                max_absolute_error=max(errors, default=None),
                nonzero_rounding_differences=sum(e != 0 for e in errors),
                minimum=values[0] if values else None,
                median=(values[(len(values) - 1) // 2] + values[len(values) // 2]) / 2
                if values
                else None,
                maximum=values[-1] if values else None,
                negative=classifications["negative"],
                zero=classifications["zero"],
                positive_eligible=classifications["positive_eligible"],
                eligible_inclusive=classifications["zero"] + classifications["positive_eligible"],
                above_max=classifications["above_max"],
            )
        )
    return result


def reconcile_report(revision, markets, decisions, phase):
    """Read persisted report CSVs, without using the report's aggregation functions."""
    quantiles = read_csv(revision / "diagnostic_quantiles.csv")
    diagnostics = read_csv(revision / "diagnostics_summary.csv")
    result = []

    def compare(window, strategy, symbol, metric, actual, expected, scope):
        difference = D(str(actual)) - D(str(expected))
        result.append(
            dict(
                report_id=revision.name,
                phase=phase,
                window=window,
                strategy=strategy,
                symbol=symbol,
                metric=metric,
                original=actual,
                audited=expected,
                difference=str(difference),
                scope=scope,
                audit_status="verified" if abs(difference) <= TOLERANCE else "discrepancy",
            )
        )

    for window, symbol in sorted({(r["window"], r["symbol"]) for r in markets}):
        observations = [r for r in markets if (r["window"], r["symbol"]) == (window, symbol)]
        values = sorted(
            D(r["basis_independent"]) for r in observations if r["basis_independent"] is not None
        )
        for strategy in STRATEGIES:
            rows = [
                r
                for r in decisions
                if (r["window"], r["symbol"], r["strategy"]) == (window, symbol, strategy)
            ]
            qs = [
                r
                for r in quantiles
                if (r["window"], r["symbol"], r["strategy"], r["scenario"], r["measure"])
                == (window, symbol, strategy, "vwap_joint", "basis")
            ]
            if len(qs) != 1:
                raise ValueError(
                    f"Missing/ambiguous report quantiles: {window}/{symbol}/{strategy}"
                )
            compare(
                window,
                strategy,
                symbol,
                "basis_observations",
                qs[0]["observations"],
                len(values),
                "market",
            )
            for name, numerator in (("p10", 1), ("p50", 5), ("p90", 9)):
                compare(
                    window,
                    strategy,
                    symbol,
                    name,
                    qs[0][name],
                    values[(len(values) - 1) * numerator // 10],
                    "market",
                )
            persisted = {
                r["diagnostic"]: int(r["count"])
                for r in diagnostics
                if (r["window"], r["symbol"], r["strategy"], r["scenario"])
                == (window, symbol, strategy, "vwap_joint")
            }
            compare(
                window,
                strategy,
                symbol,
                "filter_basis_negative:reject",
                persisted.get("filter_basis_negative:reject", 0),
                sum(v < 0 for v in values),
                "theoretical_basis_condition",
            )
            sequential = Counter(r["sequential_audited"] for r in rows)
            for reason in sorted(
                {r for r in sequential if r}
                | {
                    k.removeprefix("ordered_reject:")
                    for k in persisted
                    if k.startswith("ordered_reject:")
                }
            ):
                compare(
                    window,
                    strategy,
                    symbol,
                    f"ordered_reject:{reason}",
                    persisted.get(f"ordered_reject:{reason}", 0),
                    sequential[reason],
                    "operational_block",
                )
            expected_funding = sum(
                json.loads(r["audited_filters"])["funding"] == "fail" for r in rows
            )
            compare(
                window,
                strategy,
                symbol,
                "filter_funding:reject",
                persisted.get("filter_funding:reject", 0),
                expected_funding if strategy == "conditional" else 0,
                "applicable_condition",
            )
            compare(
                window,
                strategy,
                symbol,
                "simultaneous_reject",
                persisted.get("simultaneous_reject", 0),
                sum(bool(json.loads(r["applicable_failures"])) for r in rows),
                "applicable_conditions_union",
            )
            if phase == "corrected" and strategy == "permanent":
                compare(
                    window,
                    strategy,
                    symbol,
                    "filter_funding:diagnostic_fail_not_applied",
                    persisted.get("filter_funding:diagnostic_fail_not_applied", 0),
                    expected_funding,
                    "theoretical_not_applied",
                )
    return result


def audit_window(root, window, run):
    manifest = verify_manifest(run, "run_manifest")
    verify_code(manifest)
    config = manifest["config"]
    if (config["execution_model"], config["sizing_model"], config["signal_price_model"]) != (
        "next_minute_vwap",
        "joint_quantity",
        "closed_minute",
    ) or (D(config["basis_min"]), D(config["basis_max"])) != (D(0), D("0.005")):
        raise ValueError("This audit is specified for the unchanged vwap_joint scenario")
    if config["symbols"] != ["BTCUSDT", "ETHUSDT"] or config["signal_delay_seconds"] != 60:
        raise ValueError("Unexpected instrument universe or signal delay")
    groups, key_counts = defaultdict(list), Counter()
    for number, signal in enumerate(pq.ParquetFile(run / "signals.parquet").read().to_pylist(), 1):
        signal["audit_signal_id"] = f"{run.name}:signals.parquet:row={number}"
        key = signal["symbol"], int(signal["time_ns"])
        groups[key].append(signal)
        key_counts[(signal["strategy"], *key)] += 1
    if any(count != 1 for count in key_counts.values()):
        raise ValueError("Duplicate strategy signal key")
    expected = set()
    lower, upper = iso_ns(config["start"]), iso_ns(config["end"])
    for relative, digest in manifest["input_hashes"].items():
        if "/dataset=funding/" not in relative:
            continue
        path = root / relative
        if sha256(path) != digest:
            raise ValueError(f"Funding input checksum changed: {path}")
        for record in pq.ParquetFile(path).read().to_pylist():
            due = max(int(record["available_at"]), int(record["funding_time"]) + 60 * SECOND)
            if lower <= due < upper:
                expected.add((record["symbol"], due))
    if set(groups) != expected or set(key_counts) != {
        (s, *key) for key in expected for s in STRATEGIES
    }:
        raise ValueError("Persisted evaluations do not match the funding decision calendar")
    print(f"Auditing {window}: {len(groups)} market observations from original ZIPs", flush=True)
    raw, normalized, sources = load_sources(root, run, manifest, groups)
    openings = defaultdict(set)
    for order in pq.ParquetFile(run / "orders.parquet").read().to_pylist():
        if order["purpose"] == "open_spot":
            openings[(order["strategy"], order["symbol"], int(order["submitted_at"]))].add(
                order["order_id"]
            )
    markets, decisions = [], []
    for (symbol, now), signals in sorted(groups.items()):
        market = audit_market(window, run.name, symbol, now, signals, raw, normalized)
        markets.append(market)
        decisions += [audit_decision(window, signal, market, openings) for signal in signals]
    return markets, decisions, [dict(window=window, **r) for r in sources], manifest


def markdown_table(headers, rows):
    return ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)] + [
        "| " + " | ".join(str(v) for v in row) + " |" for row in rows
    ]


def render_report(target, manifest, markets, decisions, summary, reconciliation, sources):
    clean = all(r["audit_status"] == "verified" for r in markets + decisions)
    changed = [
        r for r in reconciliation if r["phase"] == "original" and r["audit_status"] != "verified"
    ]
    corrected_errors = [
        r for r in reconciliation if r["phase"] == "corrected" and r["audit_status"] != "verified"
    ]
    max_error = max(D(r["max_absolute_error"]) for r in summary)
    operational = []
    for window, strategy, symbol in sorted(
        {(r["window"], r["strategy"], r["symbol"]) for r in decisions}
    ):
        rows = [
            r
            for r in decisions
            if (r["window"], r["strategy"], r["symbol"]) == (window, strategy, symbol)
        ]
        counts = Counter(r["sequential_audited"] or "accepted" for r in rows)
        operational.append(
            [
                window,
                strategy,
                symbol,
                len(rows),
                "; ".join(f"{k}: {v}" for k, v in sorted(counts.items())),
            ]
        )
    offsets = [r["decision_time_ns"] - r["expected_open_ns"] - MINUTE for r in markets]
    examples = []
    for key in sorted({(r["window"], r["symbol"]) for r in markets}):
        rows = [r for r in markets if (r["window"], r["symbol"]) == key]
        for label, row in (
            ("mínimo", min(rows, key=lambda r: D(r["basis_independent"]))),
            ("más próximo a cero", min(rows, key=lambda r: abs(D(r["basis_independent"])))),
        ):
            examples.append(
                [
                    *key,
                    label,
                    row["decision_utc"],
                    row["spot_original_close"],
                    row["futures_original_close"],
                    f"{D(row['basis_independent']):.12f}",
                ]
            )
    lines = [
        "# Auditoría independiente del basis",
        "",
        (
            "**Conclusión: el basis predominantemente negativo queda confirmado contra las velas originales.**"
            if clean
            else "**Conclusión: existen discrepancias; revisar la evidencia antes de validar el basis.**"
        ),
        "",
        f"Se contrastaron {len(markets):,} observaciones únicas de mercado y {len(decisions):,} decisiones, "
        f"con {len(sources)} ZIP originales locales y sus CHECKSUM de Binance. "
        "Las dos estrategias comparten la observación, pero conservan sus estados y decisiones separados. "
        "No se descargaron datos ni se usaron trades, aggTrades o datos subminuto.",
        "",
        f"Discrepancias de observación: {sum(r['audit_status'] != 'verified' for r in markets)}. "
        f"Discrepancias en decisiones: {sum(r['audit_status'] != 'verified' for r in decisions)}. "
        f"Máximo error absoluto del basis persistido: `{max_error}`, frente a tolerancia fija `1e-12`. "
        "Las diferencias no nulas provienen de la división Decimal del motor con 28 cifras significativas "
        "frente a las 60 del auditor. No se compara usando el Markdown redondeado a seis decimales; "
        "los límites operativos permanecen exactamente en cero y 0,005.",
        "",
        "## Artefactos y versiones auditados",
        "",
        f"Informe de partida: `{manifest['original_revision']['id']}`, "
        f"creado {manifest['original_revision']['created_at']}. Era el informe más reciente al iniciar. "
        f"Código de presentación: `{manifest['original_revision']['code_hash']}`.",
        "",
        *markdown_table(
            ["Ventana UTC [inicio, fin)", "Corrida principal", "Código de simulación"],
            [
                [f"{m['config']['start']} — {m['config']['end']}", m["run_id"], m["code_hash"]]
                for m in manifest["runs"]
            ],
        ),
        "",
        "Los SHA-256 del parser, replay, modelos, estrategia, riesgo, configuración y diagnóstico actuales "
        "coinciden con los registrados por estas corridas. Los manifiestos originales, sus configuraciones "
        "efectivas y el código del auditor están preservados en `evidence_snapshot.zip`. "
        "`basis_audit_manifest.json` registra hashes de entradas, salidas y comando ejecutado.",
        "",
        "## Cadena revisada",
        "",
        "1. **Fuente original:** ZIP mensuales de `data.binance.vision/data/spot/monthly/klines/` y "
        "`data.binance.vision/data/futures/um/monthly/klines/`, exclusivamente `BTCUSDT` y `ETHUSDT`, "
        "intervalo `1m`. Se cotejó cada URL exacta, símbolo, mercado, archivo, checksum oficial guardado "
        "y hash del manifiesto. `um` identifica USD-M y los nombres sin sufijo de vencimiento identifican "
        "los perpetuos; no se utilizó COIN-M, markPriceKlines ni índices como precios de basis.",
        "2. **Parser:** `src/crypto_carry/data/normalize.py::_kline_records`. Esquema original de 12 columnas, "
        "con apertura en columna 0, OHLC en 1–4, volumen base 5, cierre reportado 6 y volumen quote 7. "
        "El auditor usa `csv` y `zipfile` propios y la columna 4; no importa el parser ni `risk.basis`.",
        "3. **Normalización:** `minute_bars` conserva OHLC y volúmenes como texto decimal exacto, "
        "`open_time` en ns UTC, `end_time=open_time+60s` y `available_at=end_time`. "
        "Se compararon precios, OHLC, actividad y tiempos originales contra los Parquet efectivamente "
        "incluidos en cada corrida, identificados por su hash.",
        "4. **Selección:** `data/replay.py::_records` produce `MinuteBar`; `events.event_time` ordena por "
        "disponibilidad. `strategy.py::Backtest.process` actualiza `closed_bars`; "
        "`_signal_prices` elige el mismo símbolo y los mercados spot/futures. "
        "`models.MinuteBar.price` es el cierre, no el VWAP. `_fresh` exige intervalo alineado y actividad.",
        "5. **Basis y filtros:** `risk.py::basis` calcula `F/S-1`; `entry_basis` acepta "
        "`0 <= basis <= 0.005`. `strategy.py::_entry` aplica funding sólo si está habilitado, "
        "y después basis. `diagnostics.signal_diagnostics` registra todas las condiciones y el primer bloqueo. "
        "El auditor recalcula el cociente directamente con Decimal de 60 cifras, sin fees, slippage, "
        "ajustes de cantidad ni anualización.",
        "6. **Persistencia y reporte:** `signals.parquet` conserva `spot_price`, `futures_price`, "
        "intervalos, disponibilidad, `basis_raw`, `basis`, `filter_*`, `sequential_rejection` y `decision`. "
        "`execution_revision.py::_diagnostics` genera `diagnostics_summary.csv` y "
        "`diagnostic_quantiles.csv`; `_revision_report_lines` los presenta. La conciliación por campo "
        "queda en `basis_report_reconciliation.csv`.",
        "",
        "El esquema y el cambio de unidad se contrastaron con la "
        "[documentación oficial de Binance Public Data](https://github.com/binance/binance-public-data). "
        "El CSV original no contiene el símbolo en cada fila: la identidad se demuestra con la ruta "
        "oficial, miembro del ZIP y manifiestos, no por la magnitud del precio.",
        "",
        "## Tiempos, selección y cobertura",
        "",
        "Spot temprano y USD-M usan milisegundos; spot desde enero de 2025 usa microsegundos. "
        "Se comprobó la unidad declarada contra magnitud, período y calendario. En fuentes ms, "
        "`close_time=end_time-1ms`; en spot us, `close_time=end_time-1us`. "
        "El motor adopta disponibilidad en el fin exclusivo común, sin confundirlo con el cierre reportado.",
        "",
        "En cada decisión `t=tau+60s`, la vela esperada se obtuvo independientemente como "
        "`[floor(t/60s)*60s-60s, floor(t/60s)*60s)`. Si `tau=08:00:00.011`, "
        "se decide a `08:01:00.011` usando la vela `08:00–08:01` de ambos mercados. "
        "Su cierre ya estaba disponible a `08:01:00`, y no se usa la vela de ejecución posterior. "
        f"La edad observada de las velas al decidir va de {min(offsets) // 1_000_000} a "
        f"{max(offsets) // 1_000_000} ms. La señal no pierde los milisegundos originales del funding.",
        "",
        "La grilla de evaluaciones se cotejó además contra los eventos de funding de entrada: "
        "no faltan ni se duplican decisiones de ninguna estrategia. Los joins son por símbolo, mercado "
        "y apertura UTC; nunca por número de fila. Se revisó orden estricto y ausencia de duplicados "
        "en las particiones leídas. Los huecos de marzo de 2023 constan en el inventario de fuentes; "
        "ninguno coincide con una observación de esta muestra de decisiones. No se rellenaron huecos.",
        "",
        *markdown_table(
            [
                "Ventana",
                "Activo",
                "Originales/N",
                "Discrepancias",
                "Mínimo",
                "Mediana",
                "Máximo",
                "Error máx.",
            ],
            [
                [
                    r["window"],
                    r["symbol"],
                    f"{r['original_source_covered']}/{r['observations']}",
                    r["discrepancies"],
                    f"{D(r['minimum']):.12f}",
                    f"{D(r['median']):.12f}",
                    f"{D(r['maximum']):.12f}",
                    f"{D(r['max_absolute_error']):.3E}",
                ]
                for r in summary
            ],
        ),
        "",
        *markdown_table(
            [
                "Ventana",
                "Activo",
                "Negativo",
                "Cero",
                "Positivo ≤0,005",
                "Elegible [0;0,005]",
                ">0,005",
            ],
            [
                [
                    r["window"],
                    r["symbol"],
                    r["negative"],
                    r["zero"],
                    r["positive_eligible"],
                    r["eligible_inclusive"],
                    r["above_max"],
                ]
                for r in summary
            ],
        ),
        "",
        "**Cero también pertenece al intervalo elegible.** Para sumar categorías excluyentes se usan "
        "negativo, cero, positivo ≤0,005 y superior a 0,005; no se suma elegible otra vez. "
        "Estas frecuencias describen los 1.095 instantes de evaluación por activo y ventana, "
        "no todos los minutos del año. El signo del funding no se usó como prueba del signo del basis.",
        "",
        "## Rechazos y defecto demostrado de presentación",
        "",
        *markdown_table(
            ["Ventana", "Estrategia", "Activo", "N", "Primer bloqueo o aceptación"], operational
        ),
        "",
        "En BTC tardío hay 1.090 basis negativos, pero sólo 1.063 bloqueos efectivos por basis "
        "en la permanente: 27 negativos ocurren cuando la posición ya está activa. De las cinco "
        "observaciones elegibles, una abre la posición y cuatro encuentran el estado activo. "
        "La condicional se bloquea antes por funding en sus 2.190 decisiones tardías. "
        "Un incumplimiento teórico no equivale necesariamente a una orden rechazada.",
        "",
        "**Defecto confirmado:** el agregador del reporte incorporaba `filter_funding=fail` "
        "de la permanente en `filter_funding:reject` y en la unión `simultaneous_reject`, "
        "aun con `funding_filter_enabled=False`. El motor y su primer rechazo secuencial estaban correctos. "
        "La reproducción mínima contiene una entrada permanente con basis cero, funding bajo costos "
        "y ninguna otra condición incumplida: el reporte anterior la contaba como rechazo simultáneo. "
        "La prueba `test_disabled_funding_is_a_diagnostic_and_never_a_permanent_rejection` "
        "falló antes de la corrección y pasó después.",
        "",
        *markdown_table(
            ["Ventana", "Activo", "Campo del reporte", "Antes", "Auditado/después"],
            [[r["window"], r["symbol"], r["metric"], r["original"], r["audited"]] for r in changed],
        ),
        "",
        "Se corrigió únicamente la agregación y sus rótulos: funding omitido queda como "
        "`diagnostic_fail_not_applied`, fuera del conteo de rechazos; los rechazos secuenciales "
        "tienen su propio scope. No se modificaron velas, señales, precios, estrategia ni resultados económicos.",
        "",
        (
            f"Informe corregido: [{manifest['corrected_revision']['id']}]"
            f"({manifest['corrected_revision']['path']}/execution_revision_report.md). "
            f"Discrepancias de conciliación del nuevo reporte: {len(corrected_errors)}. "
            "Se regeneró el reporte desde las mismas diez corridas; **no se volvió a simular**. "
            "`report_preservation_comparison.csv` demuestra que los artefactos económicos y las "
            "identidades de las corridas permanecen iguales."
            if manifest.get("corrected_revision")
            else "El reporte corregido no fue provisto a esta ejecución del auditor."
        ),
        "",
        "## Muestra y reproducción",
        "",
        "`basis_audit_all.csv`: todas las observaciones de mercado, con registros originales, "
        "líneas físicas (base 1, incluyendo la cabecera cuando existe), fuente, checksum, campos normalizados "
        "y seleccionados por ambas estrategias. `basis_audit_decisions.csv`: decisiones separadas. "
        "Los identificadores de señal son referencias derivadas `run:signals.parquet:row=N`, "
        "ya que el archivo original no tiene una columna de ID individual de señal.",
        "",
        "`basis_audit_sample.csv` contiene exactamente 20 observaciones por activo y ventana (80 total). "
        "Selección determinista: mínimo, máximo, cuatro más próximas a cero (empates por tiempo), "
        "y los lugares restantes repartidos uniformemente entre la primera y última evaluación. "
        "Los solapamientos se completan maximizando la distancia temporal a lo ya elegido. "
        "Cada fila conserva el motivo de selección. Ejemplos legibles:",
        "",
        *markdown_table(
            ["Ventana", "Activo", "Criterio", "Decisión UTC", "S original", "F original", "Basis"],
            examples,
        ),
        "",
        "Comando efectivamente ejecutado desde la raíz del proyecto:",
        "",
        "```powershell",
        manifest["command_powershell"],
        "```",
        "",
        "Pruebas reproducibles:",
        "",
        "```powershell",
        "& '.\\.venv\\Scripts\\python.exe' -m pytest tests/unit/test_basis_audit.py tests/unit/test_execution_revision.py -q --tb=short",
        "```",
        "",
        "Las pruebas cubren los cuatro cocientes calculables a mano del instructivo, límites inclusivos, "
        "unidades ms/us, disponibilidad, vela futura, desalineación, fuente faltante, duplicados, "
        "cambios de signo inferiores a la tolerancia y clasificación de funding no aplicado. "
        "El auditor no amplía su tolerancia para conseguir coincidencias.",
        "",
        "## Límites",
        "",
        "Esta auditoría verifica basis de entrada y su clasificación en los instantes persistidos; "
        "no vuelve a certificar EWMA, márgenes, sizing, rentabilidad, liquidaciones intraminuto ni "
        "cada renovación. Para el orden de otros filtros utiliza el estado persistido; no reconstruye "
        "toda la cartera. Los cierres spot y perpetuo pertenecen al mismo minuto, pero no prueban "
        "precios simultáneamente ejecutables ni bid/ask. La disponibilidad al fin del minuto es "
        "la convención explícita del proyecto, no una medición de latencia de publicación del exchange. "
        "La evidencia original es la versión descargada localmente, autenticada contra sus CHECKSUM "
        "guardados; no se volvió a descargar una versión posterior del archivo de Binance. "
        "Validar el basis no demuestra por sí solo la rentabilidad ni la corrección completa del backtest.",
    ]
    (target / "basis_audit_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def report_comparison(original, corrected):
    rows = []
    before, after = (
        read_json(original / "revision_manifest.json"),
        read_json(corrected / "revision_manifest.json"),
    )
    same_runs = before["identity"]["input_runs"] == after["identity"]["input_runs"]
    rows.append(
        dict(
            artifact="input_run_identity",
            before=json_text(before["identity"]["input_runs"]),
            after=json_text(after["identity"]["input_runs"]),
            unchanged=same_runs,
        )
    )
    for name, digest in before["output_hashes"].items():
        revised = after["output_hashes"].get(name)
        rows.append(dict(artifact=name, before=digest, after=revised, unchanged=digest == revised))
        if (
            name not in {"execution_revision_report.md", "diagnostics_summary.csv"}
            and digest != revised
        ):
            raise ValueError(f"Presentation correction changed an unrelated artifact: {name}")
    if not same_runs:
        raise ValueError("Presentation correction changed the input run identities")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--corrected-revision")
    parser.add_argument("--output-root", type=Path, default=PROJECT / "outputs")
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_root.resolve()
    if not output.is_relative_to(PROJECT):
        raise ValueError("New audit artifacts must stay inside the Backtesting project")
    revision = root / "outputs" / args.revision
    original = verify_manifest(revision, "revision_manifest")
    # Protect all original simulation artifacts, not only the two audited runs.
    protected = {}
    for item in original["input_runs"]:
        path = Path(item["path"])
        run_manifest = verify_manifest(path, "run_manifest")
        digest = sha256(path / "run_manifest.json")
        if digest != item["manifest_sha256"]:
            raise ValueError(f"Run identity changed: {path}")
        protected[str(path)] = digest
        if run_manifest["status"] != "complete":
            raise ValueError(f"Incomplete input run: {path}")
    markets, decisions, sources, run_manifests = [], [], [], []
    for item in sorted(original["input_runs"], key=lambda r: r["window"]):
        if item["scenario"] != "vwap_joint":
            continue
        m, d, s, manifest = audit_window(root, item["window"], Path(item["path"]))
        markets += m
        decisions += d
        sources += s
        run_manifests.append(manifest)
    if len(run_manifests) != 2:
        raise ValueError("The audit requires two principal windows")
    with localcontext() as context:
        context.prec = 60
        summary = summarize(markets, decisions)
        reconciliation = reconcile_report(revision, markets, decisions, "original")
    corrected, comparison = None, []
    if args.corrected_revision:
        corrected_path = root / "outputs" / args.corrected_revision
        corrected_manifest = verify_manifest(corrected_path, "revision_manifest")
        corrected = dict(
            id=corrected_path.name,
            path=corrected_path.as_posix(),
            manifest_sha256=sha256(corrected_path / "revision_manifest.json"),
            code_hash=corrected_manifest["report_code_hash"],
        )
        with localcontext() as context:
            context.prec = 60
            reconciliation += reconcile_report(corrected_path, markets, decisions, "corrected")
        comparison = report_comparison(revision, corrected_path)
    identity = dict(
        auditor_sha256=sha256(__file__),
        original_manifest_sha256=sha256(revision / "revision_manifest.json"),
        corrected=corrected,
        source_checksums=sources,
    )
    audit_id = "basis_audit_" + hashlib.sha256(json_text(identity).encode()).hexdigest()[:24]
    target = output / audit_id
    if target.exists():
        previous = verify_manifest(target, "basis_audit_manifest")
        print(json_text(dict(path=str(target), status=previous["status"], preserved_existing=True)))
        return 0 if previous["status"] == "verified_with_presentation_correction" else 1
    sample = []
    for key in sorted({(r["window"], r["symbol"]) for r in markets}):
        sample += select_sample([r for r in markets if (r["window"], r["symbol"]) == key])
    sample_fields = (
        "window",
        "symbol",
        "sample_reason",
        "decision_utc",
        "conditional_funding_anchor_utc",
        "spot_interval_utc",
        "spot_available_utc",
        "futures_interval_utc",
        "futures_available_utc",
        "spot_original_source_path",
        "spot_original_source_line",
        "spot_original_timestamp_unit",
        "futures_original_source_path",
        "futures_original_source_line",
        "futures_original_timestamp_unit",
        "spot_original_close",
        "futures_original_close",
        "basis_independent",
        "conditional_basis_persisted",
        "permanent_basis_persisted",
        "classification_audited",
        "conditional_basis_difference",
        "permanent_basis_difference",
        "audit_status",
        "conditional_signal_id",
        "permanent_signal_id",
    )
    clean = all(r["audit_status"] == "verified" for r in markets + decisions)
    clean_corrected = corrected is not None and all(
        r["audit_status"] == "verified" for r in reconciliation if r["phase"] == "corrected"
    )
    status = (
        "verified_with_presentation_correction" if clean and clean_corrected else "requires_review"
    )
    command = "& " + " ".join(
        "'" + str(x).replace("'", "''") + "'" for x in [sys.executable, *sys.argv]
    )
    audit_manifest = dict(
        audit_id=audit_id,
        status=status,
        created_at=datetime.now(UTC).isoformat(),
        identity=identity,
        command_powershell=command,
        cwd=str(Path.cwd()),
        root=str(root),
        python=platform.python_version(),
        pyarrow=pa.__version__,
        tolerance=str(TOLERANCE),
        original_revision=dict(
            id=revision.name,
            path=revision.as_posix(),
            created_at=original["created_at"],
            code_hash=original["report_code_hash"],
            manifest_sha256=sha256(revision / "revision_manifest.json"),
        ),
        corrected_revision=corrected,
        runs=run_manifests,
        observations=len(markets),
        decisions=len(decisions),
        sample_observations=len(sample),
        sources=sources,
        protected_runs=protected,
        complete_original_coverage=clean,
    )
    # Recheck original inputs after the audit before writing new artifacts.
    verify_manifest(revision, "revision_manifest")
    for path, digest in protected.items():
        verify_manifest(Path(path), "run_manifest")
        if sha256(Path(path) / "run_manifest.json") != digest:
            raise ValueError("Original run changed during audit")
    for source in sources:
        for path_field, hash_field in (
            ("source_path", "source_sha256"),
            ("partition_path", "partition_sha256"),
        ):
            if sha256(root / source[path_field]) != source[hash_field]:
                raise ValueError("Source changed during audit")
    target.mkdir(parents=True)
    for name, rows in (
        ("basis_audit_all.csv", markets),
        ("basis_audit_decisions.csv", decisions),
        ("basis_audit_sample.csv", [{k: r.get(k) for k in sample_fields} for r in sample]),
        ("basis_audit_summary.csv", summary),
        ("basis_audit_sources.csv", sources),
        ("basis_report_reconciliation.csv", reconciliation),
        ("report_preservation_comparison.csv", comparison),
    ):
        write_csv(target / name, rows)
    with zipfile.ZipFile(target / "evidence_snapshot.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in [
            Path(__file__),
            PROJECT / "tests/unit/test_basis_audit.py",
            PROJECT / "tests/unit/test_execution_revision.py",
            PROJECT / "docs/sources/Prompt_Codex_Auditoria_Basis.md",
        ]:
            archive.write(path, path.relative_to(PROJECT).as_posix())
        for path in sorted((PROJECT / "src/crypto_carry").rglob("*.py")):
            archive.write(path, path.relative_to(PROJECT).as_posix())
        for item in original["input_runs"]:
            if item["scenario"] != "vwap_joint":
                continue
            run = Path(item["path"])
            for name in (
                "run_manifest.json",
                "run_manifest.sha256",
                "effective_config.toml",
                "source_manifests/processed.json",
                "source_manifests/download.json",
            ):
                archive.write(run / name, f"inputs/{run.name}/{name}")
        archive.write(revision / "revision_manifest.json", "inputs/original_revision_manifest.json")
    render_report(target, audit_manifest, markets, decisions, summary, reconciliation, sources)
    audit_manifest["output_hashes"] = {
        p.name: sha256(p) for p in sorted(target.iterdir()) if p.is_file()
    }
    path = target / "basis_audit_manifest.json"
    path.write_text(
        json.dumps(audit_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (target / "basis_audit_manifest.sha256").write_text(sha256(path) + "\n", encoding="ascii")
    verify_manifest(target, "basis_audit_manifest")
    print(
        json_text(
            dict(
                path=str(target),
                status=status,
                observations=len(markets),
                decisions=len(decisions),
                original_zip_count=len(sources),
            )
        )
    )
    return 0 if status == "verified_with_presentation_correction" else 1


if __name__ == "__main__":
    raise SystemExit(main())

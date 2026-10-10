"""Offline read-only compact arithmetic or complete local-source risk verification.

Compact evidence cannot establish global maxima or completeness of minute prices.
Complete mode rebuilds states/prices with the archived postprocessor, independently
checks account arithmetic, and recomputes drawdown extrema from the entire series.
Neither mode imports the economic engine or depends on Git state.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from bisect import bisect_right
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path, PurePosixPath, PureWindowsPath

import numpy as np
import pyarrow.parquet as pq

# This precedes every local import, including a relocated CLI launched without -B.
sys.dont_write_bytecode = True

SCHEMA = "intraday_risk_package_v1"
SECOND, DAY = 1_000_000_000, 86_400_000_000_000
TOLERANCE = 1e-8
SYMBOLS = ("BTCUSDT", "ETHUSDT")
IDENTITY = ("scenario", "strategy", "run_id")
MANIFEST = "manifiesto_paquete.json"
SIDECAR = "manifiesto_paquete.sha256"
QUALITY_REASONS = {
    "0": "causal_current",
    "1": "no_causal_valid_reference",
    "2": "carried_expected_minute_absent",
    "3": "carried_zero_volume_omitted",
    "4": "carried_invalid_price_omitted",
    "5": "carried_invalid_volume_omitted",
}
QUALITY_REFERENCES = tuple(
    f"{symbol}_{source}" for symbol in SYMBOLS for source in ("spot", "mark", "futures")
)


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    def unique(pairs):
        output = {}
        for key, value in pairs:
            if key in output:
                raise ValueError(f"duplicate JSON key: {key}")
            output[key] = value
        return output

    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"missing/duplicate CSV fields: {path}")
        rows = list(reader)
    if any(None in row or None in row.values() for row in rows):
        raise ValueError(f"malformed CSV: {path}")
    return rows


def read_arrays(path):
    table = pq.ParquetFile(path).read()
    return {
        key: table[key].combine_chunks().to_numpy(zero_copy_only=False)
        for key in table.column_names
    }


def safe_path(root, relative):
    if (
        not isinstance(relative, str)
        or not relative
        or "\\" in relative
        or PureWindowsPath(relative).drive
        or PurePosixPath(relative).is_absolute()
        or ".." in PurePosixPath(relative).parts
    ):
        raise ValueError(f"unsafe member path: {relative!r}")
    root = Path(root).resolve()
    result = (root / relative).resolve()
    if result == root or not result.is_relative_to(root):
        raise ValueError(f"member escapes package: {relative}")
    return result


def indexed(rows, fields):
    result = {}
    for row in rows:
        key = tuple(row[field] for field in fields)
        if key in result:
            raise ValueError(f"duplicate row: {key}")
        result[key] = row
    return result


def _files(root, entries, size_field="bytes"):
    seen = set()
    for row in entries:
        name = row["path"]
        if name in seen:
            raise ValueError(f"duplicate file: {name}")
        seen.add(name)
        if "__pycache__" in PurePosixPath(name).parts or name.endswith(".pyc"):
            raise ValueError("bytecode/cache is not a permitted evidence member")
        path = safe_path(root, name)
        if path.stat().st_size != row[size_field] or sha256(path) != row["sha256"]:
            raise ValueError(f"file identity mismatch: {name}")
    return seen


def verify_manifest(package):
    package = Path(package).resolve()
    tokens = (package / SIDECAR).read_text(encoding="utf-8-sig").split()
    if not tokens or tokens[0] != sha256(package / MANIFEST):
        raise ValueError("manifest sidecar mismatch")
    manifest = read_json(package / MANIFEST)
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("full_series_in_compact_package") is not False
    ):
        raise ValueError("unsupported intraday schema or invalid compact dependency declaration")
    for key in ("parent_manifest_sha256", "correction_manifest_sha256"):
        if not re.fullmatch("[0-9a-f]{64}", manifest.get(key, "")):
            raise ValueError(f"missing reference manifest identity: {key}")
    names = _files(package, manifest["files"])
    if not names or {MANIFEST, SIDECAR} & names:
        raise ValueError("empty/self-referential package manifest")
    actual = {path.relative_to(package).as_posix() for path in package.rglob("*") if path.is_file()}
    if actual != names | {MANIFEST, SIDECAR}:
        raise ValueError("unlisted or missing package files")
    return manifest


def number(value):
    if value in (None, ""):
        return None
    result = D(str(value))
    return result if result.is_finite() else None


def yes(value):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value in ("True", "False"):
        return value == "True"
    raise ValueError(f"invalid boolean: {value!r}")


def close(actual, expected, label, tolerance="1E-8"):
    a, b = number(actual), number(expected)
    if (a is None) != (b is None) or (a is not None and abs(a - b) > D(tolerance)):
        raise ValueError(f"arithmetic {label}: {actual!r} != {expected!r}")


def array_close(actual, expected, label, tolerance=TOLERANCE):
    actual, expected = np.asarray(actual), np.asarray(expected)
    if actual.shape != expected.shape:
        raise ValueError(f"column shape: {label}")
    if expected.dtype.kind in "iub" or expected.dtype.kind not in "fc":
        valid = np.array_equal(actual, expected)
    else:
        observed = actual.astype(float)
        valid = (
            np.array_equal(np.isnan(observed), np.isnan(expected))
            and not np.any(np.isinf(observed))
            and np.all(
                np.abs(observed[np.isfinite(expected)] - expected[np.isfinite(expected)])
                <= tolerance
            )
        )
    if not valid:
        raise ValueError(f"column arithmetic/coverage mismatch: {label}")


def timestamp(value):
    match = re.fullmatch(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?Z", value)
    if not match:
        raise ValueError(f"invalid UTC boundary: {value!r}")
    date = datetime.fromisoformat(match[1]).replace(tzinfo=UTC)
    seconds = int((date - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds())
    return seconds * SECOND + int((match[2] or "").ljust(9, "0"))


def check_drawdown_rows(rows):
    indexed(rows, (*IDENTITY, "period", "peak_policy", "valuation"))
    for row in rows:
        for prefix in ("daily", "intraday"):
            complete = yes(row[f"{prefix}_complete"])
            dd = number(row[f"{prefix}_drawdown"])
            missing = int(row[f"{prefix}_missing_observations"])
            if missing < 0 or (complete and (missing or dd is None)):
                raise ValueError("drawdown coverage contradicts complete flag")
            if not complete:
                if dd is not None or not row[f"{prefix}_reason"]:
                    raise ValueError("incomplete drawdown must remain ND with reason")
                continue
            peak, trough = (number(row[f"{prefix}_{field}_equity"]) for field in ("peak", "trough"))
            if peak is None or trough is None or peak <= 0 or dd > 0:
                raise ValueError("invalid drawdown peak/trough")
            close(dd, trough / peak - 1, prefix + " drawdown", "1E-12")
            close(row[f"{prefix}_loss_usdt"], peak - trough, prefix + " loss")
            peak_time, trough_time = (
                int(row[f"{prefix}_{field}_time_ns"]) for field in ("peak", "trough")
            )
            recovery = row[f"{prefix}_recovery_time_ns"]
            if peak_time > trough_time or (
                recovery not in (None, "") and int(recovery) < trough_time
            ):
                raise ValueError("drawdown chronological order")
            for field in ("peak", "trough", "recovery"):
                key, utc = f"{prefix}_{field}_time_ns", f"{prefix}_{field}_utc"
                if (
                    utc in row
                    and row[key] not in (None, "")
                    and timestamp(row[utc]) != int(row[key])
                ):
                    raise ValueError("drawdown UTC identity mismatch")
        daily, intraday = number(row["daily_drawdown"]), number(row["intraday_drawdown"])
        if daily is not None and intraday is not None:
            close(row["extra_drawdown_pp"], 100 * (daily - intraday), "drawdown pp", "1E-10")
            close(
                row["extra_peak_to_trough_loss_usdt"],
                number(row["intraday_loss_usdt"]) - number(row["daily_loss_usdt"]),
                "drawdown loss difference",
            )
            if intraday > daily + D("1E-12"):
                raise ValueError("nested daily declaration contradicts reported drawdowns")
        elif number(row["extra_drawdown_pp"]) is not None:
            raise ValueError("incomplete drawdown difference must remain ND")
        if yes(row["daily_zero_dd"]) != (daily == 0) or not yes(row["nested_daily_check"]):
            raise ValueError("drawdown declaration mismatch")
    return len(rows)


def check_reconciliations(rows):
    indexed(rows, ("run_id", "time_ns"))
    for row in rows:
        original, actual, residual = (
            number(row[key]) for key in ("original_equity", "reconstructed_equity", "residual_usdt")
        )
        if any(value is None for value in (original, actual, residual)) or not yes(row["ok"]):
            raise ValueError("non-evaluable daily reconciliation")
        close(residual, actual - original, "daily residual")
        if abs(residual) > D("1E-8") or abs(actual - original) > D("1E-8"):
            raise ValueError("daily reconciliation exceeds original tolerance")
    return len(rows)


def check_reused_metrics(actual, source):
    keys = (*IDENTITY, "period")
    observed = indexed(actual, keys)
    run_ids = {row["run_id"] for row in actual}
    expected = indexed([row for row in source if row["run_id"] in run_ids], keys)
    if observed != expected:
        raise ValueError("reused financial values or coverage changed")


def check_episode_catalog(intervals, episodes, start, end):
    paths = defaultdict(list)
    for row in intervals:
        lower, upper = int(row["start_ns"]), int(row["end_ns"])
        if lower >= upper or row["exposure"] not in {"flat", "dust", "covered", "unhedged"}:
            raise ValueError("invalid exposure interval")
        close(row["seconds"], D(upper - lower) / SECOND, "interval duration", "0")
        paths[tuple(row[key] for key in (*IDENTITY, "symbol"))].append(row)
    indexed(episodes, ("episode_id",))
    grouped = defaultdict(list)
    for row in episodes:
        grouped[tuple(row[key] for key in (*IDENTITY, "symbol"))].append(row)
    if set(grouped) - set(paths):
        raise ValueError("unknown episode identity")
    for identity, trajectory in paths.items():
        trajectory.sort(key=lambda row: int(row["start_ns"]))
        if (
            int(trajectory[0]["start_ns"]) != start
            or int(trajectory[-1]["end_ns"]) != end
            or any(
                int(a["end_ns"]) != int(b["start_ns"]) for a, b in zip(trajectory, trajectory[1:])
            )
        ):
            raise ValueError("exposure path has gaps/overlap or incomplete coverage")
        selected = sorted(grouped[identity], key=lambda row: int(row["start_ns"]))
        assigned = set()
        previous = None
        for episode in selected:
            lower, upper = int(episode["start_ns"]), int(episode["end_ns"])
            if lower >= upper:
                raise ValueError("nonpositive episode duration")
            close(episode["seconds"], D(upper - lower) / SECOND, "episode duration", "0")
            parts = [
                (i, row)
                for i, row in enumerate(trajectory)
                if int(row["start_ns"]) < upper and int(row["end_ns"]) > lower
            ]
            if (
                not parts
                or int(parts[0][1]["start_ns"]) != lower
                or int(parts[-1][1]["end_ns"]) != upper
                or any(row["exposure"] != "unhedged" or i in assigned for i, row in parts)
            ):
                raise ValueError("episode merges nonactive time, overlaps or misaligns intervals")
            assigned.update(i for i, _ in parts)
            if episode["states"] != ";".join(sorted({row["state"] for _, row in parts})):
                raise ValueError("episode states do not match exposure path")
            if (
                previous
                and int(previous["end_ns"]) == lower
                and previous["cycle_id"] == episode["cycle_id"]
            ):
                raise ValueError("contiguous same-cycle episode was split")
            previous = episode
            close(
                episode["portfolio_change_usdt"],
                number(episode["end_post_equity_usdt"]) - number(episode["start_post_equity_usdt"]),
                "episode portfolio change",
            )
        if assigned != {i for i, row in enumerate(trajectory) if row["exposure"] == "unhedged"}:
            raise ValueError("catalog does not cover every active unhedged interval")
    return len(episodes)


def check_source_episode_groups(episodes, runs):
    expected = {}
    for run in runs:
        for symbol in SYMBOLS:
            events = sorted(
                [row for row in run["events"] if row["symbol"] == symbol and row.get("cycle_id")],
                key=lambda row: int(row["time_ns"]),
            )
            times = [int(row["time_ns"]) for row in events]
            groups = []
            active = sorted(
                [
                    row
                    for row in run["intervals"]
                    if row["symbol"] == symbol and row["exposure"] == "unhedged"
                ],
                key=lambda row: int(row["start_ns"]),
            )
            for interval in active:
                lower, upper = int(interval["start_ns"]), int(interval["end_ns"])
                latest = bisect_right(times, lower) - 1
                cycle = events[latest]["cycle_id"] if latest >= 0 else "unrecorded"
                if groups and groups[-1]["end"] == lower and groups[-1]["cycle"] == cycle:
                    groups[-1]["end"] = upper
                    groups[-1]["states"].add(interval["state"])
                else:
                    groups.append(
                        dict(start=lower, end=upper, cycle=cycle, states={interval["state"]})
                    )
            for group in groups:
                key = (run["identity"]["run_id"], symbol, group["start"], group["end"])
                expected[key] = group["cycle"], ";".join(sorted(group["states"]))
    actual = {
        (row["run_id"], row["symbol"], int(row["start_ns"]), int(row["end_ns"])): (
            row["cycle_id"],
            row["states"],
        )
        for row in episodes
    }
    if len(actual) != len(episodes) or actual != expected:
        raise ValueError("episode grouping/cycle differs from original physical event order")


def check_evidence_columns(values, group_key, *, complete_financial=False):
    length = len(values["time_ns"])
    if any(len(column) != length for column in values.values()):
        raise ValueError("unaligned evidence columns")
    for group in dict.fromkeys(values[group_key]):
        ix = np.flatnonzero(values[group_key] == group)
        times, sequence, phase, states = (
            values[key][ix] for key in ("time_ns", "sequence", "phase", "state_index")
        )
        if (
            np.any(np.diff(times) < 0)
            or np.any(np.diff(states) < 0)
            or np.any((np.diff(times) == 0) & (np.diff(sequence) <= 0))
            or np.any(~np.isin(phase, [0, 1, 2]))
            or np.any((phase < 2) & (sequence != 0))
            or np.any((phase == 2) & (sequence < 1))
        ):
            raise ValueError("evidence chronological order/phase/sequence mismatch")
        if complete_financial and np.any(phase == 0):
            raise ValueError("regular row in financial-event evidence")
        first_rows = np.flatnonzero(np.r_[True, np.diff(times) != 0])
        if complete_financial and np.any(phase[first_rows] != 1):
            raise ValueError("financial evidence misses pre state")
        for first in np.flatnonzero(phase == 1):
            last = int(np.searchsorted(times, times[first], side="right"))
            if (
                last - first < 2
                or not np.array_equal(sequence[first:last], np.arange(last - first))
                or np.any(phase[first + 1 : last] != 2)
                or not np.array_equal(states[first:last], states[first] + sequence[first:last])
            ):
                raise ValueError("financial pre/post sequence incomplete")
    equity = values["free_spot_usdt"] + values["free_futures_usdt"] - values["debt_usdt"]
    proxy = equity.copy()
    needs, topups, strict = [], [], []
    for symbol in SYMBOLS:

        def get(key):
            return np.asarray(values[f"{symbol}_{key}"])

        spot, short, average, collateral = (
            get(key) for key in ("spot", "short", "average", "collateral")
        )
        mark, spot_price = get("mark_price"), get("spot_price")
        if np.any(spot < 0) or np.any(short < 0):
            raise ValueError("negative inventory in evidence")
        upnl = np.where(short == 0, 0, short * (average - mark))
        balance, maintenance = collateral + upnl, get("maintenance_usdt")
        equity += collateral + upnl + np.where(spot == 0, 0, spot * spot_price)
        proxy += collateral + upnl + np.where(spot == 0, 0, spot * get("spot_proxy"))
        array_close(get("margin_balance_usdt"), balance, symbol + " margin balance")
        array_close(get("headroom_usdt"), balance - maintenance, symbol + " headroom")
        array_close(get("notional_usdt"), short * mark, symbol + " notional")
        array_close(
            get("net_exposure_usdt"), spot * spot_price - short * mark, symbol + " net exposure"
        )
        if np.any((short == 0) & (maintenance != 0)) or np.any(maintenance < 0):
            raise ValueError("maintenance on absent short or negative requirement")
        ratio = np.full(length, np.nan)
        np.divide(maintenance, balance, out=ratio, where=(short > 0) & (balance > 0))
        array_close(get("margin_ratio"), ratio, symbol + " maintenance ratio", 1e-12)
        liquidation = get("liquidation_price")
        distance = np.full(length, np.nan)
        np.divide(liquidation - mark, mark, out=distance, where=(short > 0) & (mark > 0))
        array_close(get("liquidation_distance"), distance, symbol + " liquidation distance", 1e-12)
        if np.any((short == 0) & np.isfinite(liquidation)):
            raise ValueError("liquidation price on absent short")
        need = np.where(short > 0, np.maximum(0, maintenance - balance), 0.0)
        array_close(get("maintenance_shortfall_usdt"), need, symbol + " maintenance shortfall")
        topup = get("preventive_topup_infimum_usdt")
        if np.any(topup < 0) or np.any((short == 0) & (topup != 0)):
            raise ValueError("invalid preventive requirement")
        needs.append(need)
        topups.append(topup)
        strict.append(get("preventive_topup_strict").astype(bool))
        for label in ("spot", "mark", "futures"):
            key = f"{symbol}_{label}_available_at"
            if key in values:
                available = values[key]
                known = available >= 0
                if np.any(known & (available > values["time_ns"])):
                    raise ValueError("future price availability")
                array_close(
                    values[f"{symbol}_{label}_age_ns"],
                    np.where(known, values["time_ns"] - available, -1),
                    key + " age",
                )
    array_close(values["equity_usdt"], equity, "account equity")
    array_close(values["equity_proxy_usdt"], proxy, "hypothetical proxy equity")
    array_close(values["maintenance_need_joint_usdt"], np.sum(needs, axis=0), "joint maintenance")
    array_close(
        values["preventive_need_joint_infimum_usdt"], np.sum(topups, axis=0), "joint prevention"
    )
    array_close(values["preventive_joint_strict"], np.any(strict, axis=0), "joint strict flag")
    cash = values["free_spot_usdt"] + values["free_futures_usdt"]
    array_close(values["free_cash_usdt"], cash, "shared cash")
    cash = np.maximum(0, cash - values["debt_usdt"])
    known = values["reservations_available_known"].astype(bool)
    if any(not str(reason or "").strip() for reason in values["reservations_reason"][~known]):
        raise ValueError("unknown reservations must retain their reason")
    available = np.where(known, np.maximum(0, cash - values["reservations_reserved_cash"]), np.nan)
    array_close(values["redistributable_cash_usdt"], available, "redistributable cash")
    for prefix, amount in (
        ("maintenance", np.sum(needs, axis=0)),
        ("preventive", np.sum(topups, axis=0)),
    ):
        deficit = np.where(amount == 0, 0.0, np.maximum(0, amount - available))
        for suffix, expected in (
            ("external_deficit_usdt", deficit),
            ("external_lower_bound_usdt", np.maximum(0, amount - cash)),
            ("external_upper_bound_usdt", np.where(known, deficit, amount)),
        ):
            array_close(values[f"{prefix}_{suffix}"], expected, prefix + " " + suffix)
    return length


def check_output(output, inputs):
    path = Path(output).resolve()
    if path.exists() or any(path.is_relative_to(Path(root).resolve()) for root in inputs if root):
        raise ValueError("audit output must be a new external file")
    for ancestor in path.parents:
        if any(
            (ancestor / name).is_file()
            for name in (MANIFEST, "manifest.json", "evidence_manifest.json")
        ):
            raise ValueError("audit output cannot enter a sealed package")


def _reference(root, expected_hash, schema):
    root = Path(root).resolve()
    if sha256(root / MANIFEST) != expected_hash:
        raise ValueError("reference manifest identity mismatch")
    sidecar = (root / SIDECAR).read_text(encoding="utf-8-sig").split()
    if not sidecar or sidecar[0] != expected_hash:
        raise ValueError("reference manifest sidecar mismatch")
    manifest = read_json(root / MANIFEST)
    if manifest.get("schema") != schema:
        raise ValueError("reference manifest schema mismatch")
    names = _files(root, manifest["members"], "size")
    if {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} != names | {
        MANIFEST,
        SIDECAR,
    }:
        raise ValueError("unlisted reference package files")


def _check_series_index(meta, reconstruction):
    if meta.get("full_series_in_compact_package") is not False:
        raise ValueError("compact series dependency is not declared")
    entries = meta["entries"]
    indexed(entries, ("path",))
    identities = indexed(reconstruction["runs"], ("run_id",))
    if len(identities) != 4 or {(r["scenario"], r["strategy"]) for r in reconstruction["runs"]} != {
        (s, t) for s in ("BASE_E3", "MARGEN_2X") for t in ("conditional", "permanent")
    }:
        raise ValueError("expected the four preserved BASE and MARGEN_2X portfolios")
    for (run_id,), identity in identities.items():
        parts = [row for row in entries if row["run_id"] == run_id]
        if not parts or any(any(row[key] != identity[key] for key in IDENTITY) for row in parts):
            raise ValueError("series partition run identity mismatch")
        parts.sort(key=lambda row: row["start_ns"])
        if (
            parts[0]["start_ns"] != reconstruction["start_ns"]
            or parts[-1]["end_exclusive_ns"] != reconstruction["end_exclusive_ns"]
            or any(a["end_exclusive_ns"] != b["start_ns"] for a, b in zip(parts, parts[1:]))
        ):
            raise ValueError("series partition bounds have gaps/overlaps")
        for row in parts:
            safe_path(Path.cwd(), row["path"])
            if row["start_ns"] >= row["end_exclusive_ns"] or row["rows"] <= 0 or row["bytes"] <= 0:
                raise ValueError("invalid series partition declaration")
    if {r["run_id"] for r in entries} != {key[0] for key in identities} or sum(
        r["rows"] for r in entries
    ) != reconstruction["rows"]:
        raise ValueError("series row-count/identity declaration mismatch")
    return identities


def _compare_rows(actual, expected, keys, label):
    def normalize(rows):
        return [dict(row, **{key: str(row[key]) for key in keys}) for row in rows]

    observed, calculated = indexed(normalize(actual), keys), indexed(normalize(expected), keys)
    if set(observed) != set(calculated):
        raise ValueError(f"{label}: row coverage mismatch")
    for key, row in calculated.items():
        if set(observed[key]) != set(row):
            raise ValueError(f"{label}: column coverage mismatch")
        for field, value in row.items():
            if isinstance(value, (float, int, np.number)) and not isinstance(
                value, (bool, np.bool_)
            ):
                close(observed[key][field], value, f"{label}/{key}/{field}")
            elif value is None:
                if observed[key][field] not in (None, "", "nan"):
                    raise ValueError(f"{label}: undefined field changed")
            elif str(observed[key][field]) != str(value):
                raise ValueError(f"{label}: {key}/{field} changed")


def _episode_values(values, episodes):
    observed = set(values["episode_id"])
    expected = {row["episode_id"] for row in episodes}
    if observed != expected:
        raise ValueError("episode detail coverage mismatch")
    for row in episodes:
        ix = np.flatnonzero(values["episode_id"] == row["episode_id"])
        if values["time_ns"][ix[0]] != int(row["start_ns"]) or values["time_ns"][ix[-1]] != int(
            row["end_ns"]
        ):
            raise ValueError("episode detail temporal endpoints mismatch")
        symbol = row["symbol"]
        times = values["time_ns"][ix]
        active = times < int(row["end_ns"])
        previous = np.flatnonzero(active)
        if not len(previous):
            raise ValueError("episode lacks an active observation")
        last_active = previous[-1]
        for position in np.flatnonzero(~active):
            if values["phase"][ix[position]] == 0 or any(
                values[f"{symbol}_{field}"][ix[position]]
                != values[f"{symbol}_{field}"][ix[last_active]]
                for field in ("spot", "short")
            ):
                break
            active[position] = True
        equity, proxy, asset = (
            values[key][ix]
            for key in ("equity_usdt", "equity_proxy_usdt", f"{symbol}_asset_pnl_usdt")
        )
        net = values[f"{symbol}_net_exposure_usdt"][ix]
        expected_values = dict(
            start_post_equity_usdt=equity[0],
            end_post_equity_usdt=equity[-1],
            portfolio_change_usdt=equity[-1] - equity[0],
            worst_portfolio_change_usdt=np.min(equity[active]) - equity[0],
            asset_change_usdt=asset[-1] - asset[0],
            worst_asset_change_usdt=np.min(asset[active]) - asset[0],
            worst_proxy_portfolio_change_usdt=np.min(proxy[active]) - proxy[0],
            maximum_spot_quantity=np.max(values[f"{symbol}_spot"][ix][active]),
            maximum_short_quantity=np.max(values[f"{symbol}_short"][ix][active]),
            maximum_signed_net_exposure_usdt=np.max(net[active]),
            minimum_signed_net_exposure_usdt=np.min(net[active]),
            maximum_absolute_net_exposure_usdt=np.max(np.abs(net[active])),
            maximum_spot_age_seconds=np.max(values[f"{symbol}_spot_age_ns"][ix][active]) / SECOND,
        )
        for field, amount in expected_values.items():
            close(row[field], amount, "episode evidence " + field)


def _daily_tables(package, metrics):
    daily = read_csv(package / "tablas/riesgo_diario.csv")
    margin = read_csv(package / "tablas/garantias_diarias_activo.csv")
    period = read_csv(package / "tablas/garantias_periodo.csv")
    indexed(daily, (*IDENTITY, "date"))
    indexed(margin, (*IDENTITY, "date", "symbol"))
    for row in daily:
        opening, low = number(row["day_open_equity_usdt"]), number(row["minimum_equity_usdt"])
        close(row["drop_from_day_open_usdt"], low - opening, "daily opening loss")
        close(
            row["drop_from_day_open_fraction"],
            low / opening - 1 if opening > 0 else None,
            "daily opening fraction",
            "1E-12",
        )
        if int(row["unknown_equity"]) and number(row["within_day_peak_drawdown"]) is not None:
            raise ValueError("unknown daily equity reported as complete drawdown")
        if not D(0) <= number(row["unknown_redistributable_seconds"]) <= D(86400):
            raise ValueError("unknown cash duration outside day")
    before = indexed(metrics, (*IDENTITY, "period"))
    after = indexed(period, (*IDENTITY, "period"))
    if set(before) != set(after):
        raise ValueError("margin-period coverage differs from financial periods")
    for key, source in before.items():
        lower, upper = timestamp(source["start_utc"]), timestamp(source["end_exclusive_utc"])
        days = [
            r
            for r in daily
            if r["run_id"] == source["run_id"] and lower <= int(r["day_ns"]) < upper
        ]
        positions = [
            r
            for r in margin
            if r["run_id"] == source["run_id"]
            and lower <= int(r["day_ns"]) < upper
            and int(r["active_observations"])
        ]
        row = after[key]
        for field, source_field, function, default in (
            ("min_headroom_usdt", "minimum_headroom_usdt", min, None),
            ("min_margin_balance_usdt", "minimum_margin_balance_usdt", min, None),
            ("max_contract_maintenance_usdt", "maximum_maintenance_usdt", max, D(0)),
            ("max_margin_ratio", "maximum_ratio", max, None),
            ("min_liquidation_distance", "minimum_liquidation_distance", min, None),
        ):
            vals = [number(r[source_field]) for r in positions]
            if any(value is None for value in vals):
                raise ValueError("non-evaluable contract summary omitted its reason")
            close(row[field], function(vals) if vals else default, "period margin " + field)
        for field, source_field, function in (
            ("max_joint_maintenance_need_usdt", "maximum_maintenance_need_joint_usdt", max),
            (
                "max_joint_preventive_need_infimum_usdt",
                "maximum_preventive_need_joint_infimum_usdt",
                max,
            ),
            ("max_external_lower_bound_usdt", "maximum_external_lower_bound_usdt", max),
            ("max_external_upper_bound_usdt", "maximum_external_upper_bound_usdt", max),
            ("unknown_redistributable_seconds", "unknown_redistributable_seconds", sum),
            ("max_within_day_peak_loss_usdt", "within_day_peak_loss_usdt", max),
        ):
            close(
                row[field], function(number(r[source_field]) for r in days), "period risk " + field
            )
        close(
            row["max_loss_from_day_open_usdt"],
            -min(number(r["drop_from_day_open_usdt"]) for r in days),
            "period opening loss",
        )
    return daily, margin


def check_series_evidence(compact, source, positions, label):
    """Authenticate a compact slice against exact full-series clocks and values."""
    if len(compact["time_ns"]) != len(positions):
        raise ValueError(f"{label}: compact row coverage mismatch")
    metadata = {"run_id", "episode_id"}
    if set(compact) - metadata != set(source) - metadata:
        raise ValueError(f"{label}: compact column coverage mismatch")
    for key in set(source) - metadata:
        array_close(compact[key], source[key][positions], label + "/" + key)


def check_quality_clock(quality_times, observations, *, exact):
    """Unique causal-price keys; only full mode establishes the series union."""
    quality_times, observations = np.asarray(quality_times), np.asarray(observations)
    if (
        quality_times.ndim != 1
        or quality_times.dtype != np.dtype("int64")
        or observations.ndim != 1
        or observations.dtype != np.dtype("int64")
        or np.any(np.diff(quality_times) <= 0)
    ):
        raise ValueError("price quality clock must contain unique increasing int64 keys")
    if exact:
        valid = np.array_equal(quality_times, np.unique(observations))
    else:
        positions = np.searchsorted(quality_times, observations)
        valid = np.all(positions < len(quality_times))
        if valid:
            valid = np.array_equal(quality_times[positions], observations)
    if not valid:
        raise ValueError("price quality coverage does not match observation clocks")
    return len(quality_times)


def check_quality_values(values, start, end):
    expected = {"time_ns"} | {reference + "_reason_code" for reference in QUALITY_REFERENCES}
    if set(values) != expected:
        raise ValueError("price quality column coverage mismatch")
    times = values["time_ns"]
    count = check_quality_clock(times, np.array([], dtype=np.int64), exact=False)
    if not count or times[0] != start or times[-1] != end - 1:
        raise ValueError("price quality clock does not cover declared sample endpoints")
    for reference in QUALITY_REFERENCES:
        codes = values[reference + "_reason_code"]
        if (
            codes.dtype != np.dtype("uint8")
            or codes.shape != times.shape
            or np.any(codes > 5)
            or (reference.endswith("_mark") and np.any(np.isin(codes, [3, 5])))
        ):
            raise ValueError("price quality reason code is invalid for " + reference)
    return count


def check_quality_metadata(package, values, meta, series, prices, reconstruction):
    """Check exported coverage declarations, without claiming source recomputation."""
    count = check_quality_values(
        values, reconstruction["start_ns"], reconstruction["end_exclusive_ns"]
    )
    columns = {key: "int64" if key == "time_ns" else "uint8" for key in values}
    if (
        type(meta["schema_version"]) is not int
        or meta["schema_version"] != 1
        or meta["row_count"] != count
        or meta["columns"] != columns
    ):
        raise ValueError("price quality schema/row declaration mismatch")
    dictionary = meta["reason_dictionary"]
    if set(dictionary) != set(QUALITY_REASONS) or any(
        dictionary[code].get("name") != name
        or not isinstance(dictionary[code].get("description"), str)
        or not dictionary[code]["description"].strip()
        for code, name in QUALITY_REASONS.items()
    ):
        raise ValueError("price quality reason dictionary mismatch")
    expected_join = dict(
        key=["time_ns"],
        cardinality="many_series_observations_to_one_price_quality_row",
        series_manifest="series_locales.json",
        phase_independent=True,
        references=list(QUALITY_REFERENCES),
    )
    if any(meta["join_contract"].get(key) != value for key, value in expected_join.items()):
        raise ValueError("price quality join contract mismatch")
    partitions = indexed(series["entries"], ("run_id", "path"))
    coverage = indexed(meta["coverage"], ("run_id", "path"))
    if set(partitions) != set(coverage):
        raise ValueError("price quality partition coverage mismatch")
    for key, entry in partitions.items():
        row = coverage[key]
        if (
            row["sha256"] != entry["sha256"]
            or row["rows"] != entry["rows"]
            or row["matched_observations"] != entry["rows"]
            or row["missing_observations"] != 0
            or type(row["unique_timestamps"]) is not int
            or not 1 <= row["unique_timestamps"] <= entry["rows"]
        ):
            raise ValueError("price quality matched-observation declaration mismatch")
    blocks = {(row["start_ns"], row["end_exclusive_ns"]) for row in series["entries"]}
    months = indexed(meta["monthly_counts"], ("start_ns", "end_exclusive_ns"))
    if set(months) != blocks:
        raise ValueError("price quality monthly coverage mismatch")
    for (lower, upper), row in months.items():
        first, last = np.searchsorted(values["time_ns"], [lower, upper])
        if (
            row["month"] != datetime.fromtimestamp(lower // SECOND, UTC).strftime("%Y-%m")
            or row["row_count"] != last - first
            or first == last
            or row["first_time_ns"] != int(values["time_ns"][first])
            or row["last_time_ns"] != int(values["time_ns"][last - 1])
        ):
            raise ValueError("price quality monthly clock/count mismatch")
        if set(row["reference_counts"]) != set(QUALITY_REFERENCES):
            raise ValueError("price quality reference-count coverage mismatch")
        for reference in QUALITY_REFERENCES:
            counts = np.bincount(values[reference + "_reason_code"][first:last], minlength=6)
            if row["reference_counts"][reference] != {
                str(code): int(n) for code, n in enumerate(counts)
            }:
                raise ValueError("price quality reason counts mismatch")
    provenance = meta["provenance"]
    for label, path in (
        ("series_manifest", "series_locales.json"),
        ("price_sources", "fuentes_precios.json"),
        ("script", "herramientas/scripts/intraday_risk_price_quality.py"),
        ("reader_script", "herramientas/scripts/intraday_risk_sources.py"),
    ):
        recorded = provenance[label]
        if recorded["path"] != path or recorded["sha256"] != sha256(safe_path(package, path)):
            raise ValueError("price quality provenance mismatch: " + label)
    processed = provenance["processed_manifest"]
    if (
        processed["path"] != prices["manifest_path"]
        or processed["sha256"] != prices["manifest_sha256"]
    ):
        raise ValueError("price quality processed-manifest identity mismatch")
    price_hashes = {str(row["source_id"]): row["sha256"] for row in prices["entries"]}
    source = provenance["source_partitions"]
    if (
        len(price_hashes) != len(prices["entries"])
        or source["count"] != len(price_hashes)
        or source["all_manifest_hashes_match"] is not True
        or source["sha256_by_source_id"] != price_hashes
    ):
        raise ValueError("price quality source partition provenance mismatch")
    series_source = provenance["series_partitions"]
    run_ids = {row["run_id"] for row in series["entries"]}
    if (
        series_source["count"] != len(partitions)
        or series_source["all_manifest_hashes_match"] is not True
        or len(provenance["run_ids"]) != len(run_ids)
        or set(provenance["run_ids"]) != run_ids
    ):
        raise ValueError("price quality series partition provenance mismatch")
    parquet = meta["parquet"]
    path = safe_path(package, "evidencia/calidad_precios.parquet")
    if (
        parquet["path"] != "evidencia/calidad_precios.parquet"
        or parquet["bytes"] != path.stat().st_size
        or parquet["sha256"] != sha256(path)
    ):
        raise ValueError("price quality Parquet identity mismatch")
    return count


def check_quality_block(values, prices, observations, lower, upper, *, classifier):
    """Recompute via the declared shared causal helper on authenticated source data."""
    first, last = np.searchsorted(values["time_ns"], [lower, upper])
    times = values["time_ns"][first:last]
    check_quality_clock(times, observations, exact=True)
    for symbol in SYMBOLS:
        for source in ("spot", "mark", "futures"):
            expected = classifier(prices[symbol, source], times, require_volume=source != "mark")
            key = f"{symbol}_{source}_reason_code"
            array_close(values[key][first:last], expected, "price quality " + key)
    return len(times)


def check_extreme_points(rows, drawdowns, margin_days):
    indexed(rows, (*IDENTITY, "label"))
    full_dd = {
        row["run_id"]: row
        for row in drawdowns
        if row["period"] == "full"
        and row["peak_policy"] == "period_reset"
        and row["valuation"] == "original_reconstructed"
    }
    for row in rows:
        if timestamp(row["timestamp_utc"]) != int(row["time_ns"]):
            raise ValueError("extreme point UTC mismatch")
        joint_maintenance, joint_prevention = D(0), D(0)
        for symbol in SYMBOLS:

            def get(field):
                return number(row[f"{symbol}_{field}"])

            short, collateral, average, mark = (
                get(key) for key in ("short", "collateral", "average", "mark_price")
            )
            spot, spot_price, maintenance = (
                get(key) for key in ("spot", "spot_price", "maintenance_usdt")
            )
            if any(
                value is None
                for value in (short, collateral, average, mark, spot, spot_price, maintenance)
            ):
                raise ValueError("non-evaluable extreme point lacks complete arithmetic")
            if short < 0 or spot < 0 or maintenance < 0 or (short == 0 and maintenance != 0):
                raise ValueError("invalid extreme point inventory/maintenance")
            balance = collateral + short * (average - mark)
            close(get("margin_balance_usdt"), balance, "extreme margin balance")
            close(get("headroom_usdt"), balance - maintenance, "extreme headroom")
            close(
                get("net_exposure_usdt"), spot * spot_price - short * mark, "extreme net exposure"
            )
            close(
                get("margin_ratio"),
                maintenance / balance if short > 0 and balance > 0 else None,
                "extreme maintenance ratio",
                "1E-12",
            )
            liquidation = get("liquidation_price")
            if short == 0 and liquidation is not None:
                raise ValueError("extreme liquidation price without a short")
            close(
                get("liquidation_distance"),
                (liquidation - mark) / mark if short > 0 and liquidation is not None else None,
                "extreme liquidation distance",
                "1E-12",
            )
            topup = get("preventive_topup_infimum_usdt")
            if topup is None or topup < 0 or (short == 0 and topup != 0):
                raise ValueError("invalid extreme preventive requirement")
            joint_maintenance += max(D(0), maintenance - balance) if short else D(0)
            joint_prevention += topup
        close(row["maintenance_need_joint_usdt"], joint_maintenance, "extreme joint maintenance")
        close(
            row["preventive_need_joint_infimum_usdt"], joint_prevention, "extreme joint prevention"
        )
        if row["label"] == "worst_equity_drawdown":
            dd = full_dd[row["run_id"]]
            if int(row["time_ns"]) != int(dd["intraday_trough_time_ns"]):
                raise ValueError("extreme drawdown time differs from summary")
            close(row["equity_usdt"], dd["intraday_trough_equity"], "extreme drawdown equity")
        elif row["label"].startswith("full_min_headroom_"):
            symbol = row["label"].removeprefix("full_min_headroom_")
            candidates = [
                r
                for r in margin_days
                if r["run_id"] == row["run_id"]
                and r["symbol"] == symbol
                and int(r["active_observations"])
            ]
            if not candidates:
                raise ValueError("extreme contract has no active observations")
            minimum = min(candidates, key=lambda r: number(r["minimum_headroom_usdt"]))
            close(
                row[f"{symbol}_headroom_usdt"],
                minimum["minimum_headroom_usdt"],
                "extreme daily headroom",
            )
            if int(row["time_ns"]) != int(minimum["minimum_headroom_time_ns"]):
                raise ValueError("extreme headroom timestamp differs from daily evidence")
        else:
            raise ValueError("unknown extreme label")
    return len(rows)


def _subset(values, selection):
    return {key: column[selection] for key, column in values.items()}


def _link_compact_block(compact, episodes, points, expected, identity, lower, upper):
    run_id = identity["run_id"]
    times = expected["time_ns"]
    for label in ("eventos_financieros", "marzo_2023"):
        values = compact[label]
        selection = (
            (values["run_id"] == run_id)
            & (values["time_ns"] >= lower)
            & (values["time_ns"] < upper)
        )
        mask = (
            expected["phase"] > 0
            if label == "eventos_financieros"
            else (
                (times >= timestamp("2023-03-23T00:00:00Z"))
                & (times < timestamp("2023-03-26T00:00:00Z"))
            )
        )
        check_series_evidence(_subset(values, selection), expected, np.flatnonzero(mask), label)
    values = compact["episodios"]
    for row in episodes:
        start, end = int(row["start_ns"]), int(row["end_ns"])
        if row["run_id"] != run_id or end < lower or start >= upper:
            continue
        selection = (
            (values["episode_id"] == row["episode_id"])
            & (values["time_ns"] >= lower)
            & (values["time_ns"] < upper)
        )
        mask = (times >= start) & (times <= end)
        starts = np.flatnonzero(times == start)
        if len(starts):
            mask[starts[:-1]] = False
        check_series_evidence(
            _subset(values, selection), expected, np.flatnonzero(mask), row["episode_id"]
        )
    for row in points:
        if row["run_id"] != run_id or not lower <= int(row["time_ns"]) < upper:
            continue
        positions = np.flatnonzero(
            (times == int(row["time_ns"])) & (expected["sequence"] == int(row["sequence"]))
        )
        if len(positions) != 1:
            raise ValueError("complete extreme clock missing or ambiguous")
        reconstructed = {key: expected[key][positions[0]] for key in row if key in expected}
        reconstructed.update(identity, label=row["label"], timestamp_utc=row["timestamp_utc"])
        _compare_rows([row], [reconstructed], (*IDENTITY, "label"), "complete extreme")


def _summary(times, equity, initial, initial_time):
    finite = np.isfinite(equity)
    peak_path = np.fmax.accumulate(np.r_[initial, np.where(finite, equity, np.nan)])[1:]
    path = (
        np.divide(
            equity, peak_path, out=np.full(len(equity), np.nan), where=finite & (peak_path > 0)
        )
        - 1
    )
    complete = bool(finite.all() and initial > 0)
    if not np.any(np.isfinite(path)):
        raise ValueError("complete-source drawdown has no evaluable observations")
    trough = int(np.nanargmin(path))
    candidates = np.r_[initial, np.where(finite[: trough + 1], equity[: trough + 1], -np.inf)]
    peak = int(np.argmax(candidates)) - 1
    peak_value = initial if peak == -1 else equity[peak]
    recovered = np.flatnonzero(finite[trough:] & (equity[trough:] >= peak_value))
    recovery = int(trough + recovered[0]) if len(recovered) else None
    return dict(
        drawdown=float(path[trough]) if complete else np.nan,
        loss_usdt=float(peak_value - equity[trough]) if complete else np.nan,
        peak_equity=float(peak_value),
        trough_equity=float(equity[trough]),
        peak_time_ns=int(initial_time if peak == -1 else times[peak]),
        trough_time_ns=int(times[trough]),
        recovery_time_ns=None if recovery is None else int(times[recovery]),
        complete=complete,
        missing_observations=int(np.count_nonzero(~finite)),
    )


def check_full_drawdowns(rows, runs, metrics, equities):
    run_index = {run["identity"]["run_id"]: run for run in runs}
    metric_index = indexed(metrics, ("run_id", "period"))
    for row in rows:
        run, values = run_index[row["run_id"]], equities[row["run_id"]]
        source = metric_index[row["run_id"], row["period"]]
        start, end = timestamp(source["start_utc"]), timestamp(source["end_exclusive_utc"])
        initial = float(source["starting_equity_usdt"])
        sample_start, capital = timestamp(run["config"]["start"]), float(run["config"]["capital"])
        daily_times = np.array([int(r["time_ns"]) for r in run["daily"]], dtype=np.int64)
        daily_equity = np.array([float(r["equity"]) for r in run["daily"]])
        selected_equity = (
            values["equity_proxy_usdt"]
            if row["valuation"] == "valoracion_proxy_hipotetica"
            else values["equity_usdt"]
        )
        positions = np.searchsorted(values["time_ns"], daily_times, side="right") - 1
        if np.any(positions < 0) or not np.array_equal(values["time_ns"][positions], daily_times):
            raise ValueError("complete series misses exact daily timestamps")
        array_close(selected_equity[positions], daily_equity, "complete daily nested values")
        for prefix, times, equity in (
            ("daily", daily_times, daily_equity),
            ("intraday", values["time_ns"], selected_equity),
        ):
            initial_time = start if start == sample_start else start - 1
            starting = initial
            if row["peak_policy"] == "full_trajectory_peak":
                previous = np.flatnonzero((times < start) & (equity > capital))
                if len(previous):
                    peak = int(previous[np.argmax(equity[previous])])
                    starting, initial_time = float(equity[peak]), int(times[peak])
                else:
                    starting, initial_time = capital, sample_start
            select = (times >= start) & (times < end)
            result = _summary(times[select], equity[select], starting, initial_time)
            for field, value in result.items():
                actual = row[f"{prefix}_{field}"]
                if isinstance(value, bool):
                    if yes(actual) != value:
                        raise ValueError("complete drawdown coverage flag mismatch")
                elif field.endswith("_time_ns") or field == "missing_observations":
                    if (value is None and actual not in (None, "")) or (
                        value is not None and int(actual) != value
                    ):
                        raise ValueError("complete drawdown timing mismatch")
                else:
                    close(
                        actual,
                        value,
                        "complete " + prefix + " " + field,
                        "1E-12" if field == "drawdown" else "1E-8",
                    )
    return len(rows)


def _complete(
    package,
    parent,
    correction,
    series_root,
    data_root,
    series_meta,
    price_meta,
    metrics,
    dd,
    quality,
    quality_meta,
):
    if __package__:
        from . import build_intraday_risk as builder
        from .intraday_risk_price_quality import quality_codes
        from .intraday_risk_sources import LocalPrices, observation_grid, reconcile_daily
        from .intraday_risk_tables import daily_block
    else:
        import build_intraday_risk as builder
        from intraday_risk_price_quality import quality_codes
        from intraday_risk_sources import LocalPrices, observation_grid, reconcile_daily
        from intraday_risk_tables import daily_block
    runs = builder.load_runs(parent)
    prices = LocalPrices(data_root)
    if (
        sha256(prices.manifest_path) != price_meta["manifest_sha256"]
        or prices.entries != price_meta["entries"]
    ):
        raise ValueError("local price manifest/source-id identity mismatch")
    _files(data_root, prices.entries)
    _files(series_root, series_meta["entries"])
    run_index = {run["identity"]["run_id"]: run for run in runs}
    all_equity, all_daily, all_margin, reconciliations = defaultdict(list), [], [], []
    compact = {
        name: read_arrays(package / "evidencia" / (name + ".parquet"))
        for name in ("eventos_financieros", "episodios", "marzo_2023")
    }
    episodes = read_csv(package / "tablas/catalogo_incidentes.csv")
    check_source_episode_groups(episodes, runs)
    points = read_csv(package / "tablas/puntos_extremos.csv")
    blocks = defaultdict(list)
    quality_coverage = indexed(quality_meta["coverage"], ("run_id", "path"))
    for entry in series_meta["entries"]:
        blocks[entry["start_ns"], entry["end_exclusive_ns"]].append(entry)
    for (lower, upper), entries in sorted(blocks.items()):
        month = datetime.fromtimestamp(lower // SECOND, UTC).strftime("%Y-%m")
        block = prices.block(month)
        block_times = []
        for entry in entries:
            run = run_index[entry["run_id"]]
            daily = [row for row in run["daily"] if lower <= int(row["time_ns"]) < upper]
            extra = [
                int(row["time_ns"])
                for row in run["events"] + run["orders"]
                if lower <= int(row["time_ns"]) < upper
            ]
            grid = observation_grid(
                lower,
                upper,
                run["history"],
                [int(row["time_ns"]) for row in daily],
                extra_times=extra,
            )
            expected = builder.value_grid(
                run["history"],
                grid,
                block,
                run["tiers"],
                ratio_limit=float(run["config"]["margin_exit_ratio"]),
                distance_limit=float(run["config"]["liquidation_distance"]),
            )
            builder.add_liquidity(expected, run)
            unique_times = np.unique(expected["time_ns"])
            if (
                len(unique_times)
                != quality_coverage[(entry["run_id"], entry["path"])]["unique_timestamps"]
            ):
                raise ValueError("price quality per-partition unique timestamp coverage mismatch")
            block_times.append(unique_times)
            actual = read_arrays(safe_path(series_root, entry["path"]))
            if set(actual) != set(expected) or len(actual["time_ns"]) != entry["rows"]:
                raise ValueError("complete series schema or row coverage mismatch")
            for key, values in expected.items():
                array_close(actual[key], values, entry["path"] + "/" + key)
            identity = run["identity"]
            _link_compact_block(compact, episodes, points, expected, identity, lower, upper)
            actual["run_id"] = np.full(len(actual["time_ns"]), entry["run_id"])
            check_evidence_columns(actual, "run_id")
            reconciliations.extend(
                dict(identity, **row)
                for row in reconcile_daily(
                    daily, expected["time_ns"], expected["equity_usdt"], TOLERANCE
                )
            )
            risk_days, margin_days, _ = daily_block(expected, lower, upper, identity)
            all_daily.extend(risk_days)
            all_margin.extend(margin_days)
            all_equity[entry["run_id"]].append(
                {key: expected[key] for key in ("time_ns", "equity_usdt", "equity_proxy_usdt")}
            )
        check_quality_block(
            quality, block, np.concatenate(block_times), lower, upper, classifier=quality_codes
        )
        print(f"verified complete block {month}", file=sys.stderr, flush=True)
    equities = {
        run: {key: np.concatenate([part[key] for part in chunks]) for key in chunks[0]}
        for run, chunks in all_equity.items()
    }
    _compare_rows(
        read_csv(package / "tablas/conciliaciones_diarias.csv"),
        reconciliations,
        (*IDENTITY, "time_ns"),
        "daily reconstruction",
    )
    _compare_rows(
        read_csv(package / "tablas/riesgo_diario.csv"),
        all_daily,
        (*IDENTITY, "date"),
        "daily risk reconstruction",
    )
    _compare_rows(
        read_csv(package / "tablas/garantias_diarias_activo.csv"),
        all_margin,
        (*IDENTITY, "date", "symbol"),
        "daily margin reconstruction",
    )
    check_full_drawdowns(dd, runs, metrics, equities)
    return dict(
        partitions_reconstructed=len(series_meta["entries"]),
        series_rows_reconstructed=sum(row["rows"] for row in series_meta["entries"]),
        source_price_files_checked=len(prices.entries),
        global_drawdown_recomputed=True,
        daily_nesting_recomputed=True,
        price_quality_union_recomputed=True,
        price_quality_reason_codes_recomputed=True,
        price_quality_dependency="shared quality_codes causal helper reused against authenticated local price blocks; not an independent classifier",
        reconstruction_dependency="archived producer state/grid/price functions reused; account arithmetic and global DD independently checked",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--scope", choices=("compact", "complete"), default="compact")
    for name in ("parent", "correction", "series-root", "data-root", "output"):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args(argv)
    output_allowed = False
    try:
        if args.output:
            check_output(
                args.output,
                [args.package, args.parent, args.correction, args.series_root, args.data_root],
            )
            output_allowed = True
        result = verify_package(
            args.package,
            scope=args.scope,
            parent=args.parent,
            correction=args.correction,
            series_root=args.series_root,
            data_root=args.data_root,
        )
    except (ValueError, OSError, KeyError, TypeError, ImportError, ArithmeticError) as exc:
        result = dict(
            status="failed",
            scope=args.scope,
            error=str(exc),
            sources_read_only=True,
            package_read_only=True,
            engine_replay=False,
        )
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output and output_allowed:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(text)
    sys.stdout.write(text)
    return 0 if result["status"] == "passed" else 1


def verify_package(
    package, *, scope="compact", parent=None, correction=None, series_root=None, data_root=None
):
    if scope not in {"compact", "complete"}:
        raise ValueError("unknown verification scope")
    if scope == "complete" and any(
        value is None for value in (parent, correction, series_root, data_root)
    ):
        raise ValueError("complete scope requires --parent --correction --series-root --data-root")
    package = Path(package).resolve()
    manifest = verify_manifest(package)
    names = {row["path"] for row in manifest["files"]}
    required = {
        "series_locales.json",
        "fuentes_precios.json",
        "reconstruccion.json",
        "tablas_procedencia.json",
        "evidencia/calidad_precios.parquet",
        "evidencia/calidad_precios.json",
    }
    required |= {
        "tablas/" + name + ".csv"
        for name in (
            "drawdown_comparativo",
            "conciliaciones_diarias",
            "intervalos_exposicion_reutilizados",
            "catalogo_incidentes",
            "metricas_reutilizadas",
            "riesgo_diario",
            "garantias_diarias_activo",
            "garantias_periodo",
            "puntos_extremos",
            "h1_resumen",
            "h1_invariancia",
            "h2",
            "h3_regimen",
            "h3_invariancia",
        )
    }
    required |= {
        "evidencia/" + name + ".parquet"
        for name in ("eventos_financieros", "episodios", "marzo_2023")
    }
    if not required <= names:
        raise ValueError(
            "missing mandatory semantic evidence: " + ", ".join(sorted(required - names))
        )
    reconstruction = read_json(package / "reconstruccion.json")
    if reconstruction.get("engine_replay") is not False:
        raise ValueError("this product must declare persisted-state postprocessing")
    series, prices = (
        read_json(package / "series_locales.json"),
        read_json(package / "fuentes_precios.json"),
    )
    identities = _check_series_index(series, reconstruction)
    quality = read_arrays(package / "evidencia/calidad_precios.parquet")
    quality_meta = read_json(package / "evidencia/calidad_precios.json")
    quality_count = check_quality_metadata(
        package, quality, quality_meta, series, prices, reconstruction
    )
    for root, key, schema in (
        (parent, "parent_manifest_sha256", "rules_sensitivity_package_v1"),
        (correction, "correction_manifest_sha256", "rules_sensitivity_correction_v2"),
    ):
        if root is not None:
            _reference(root, manifest[key], schema)
    metrics = read_csv(package / "tablas/metricas_reutilizadas.csv")
    if {row["run_id"] for row in metrics} != {key[0] for key in identities} or any(
        any(row[key] != identities[(row["run_id"],)][key] for key in IDENTITY) for row in metrics
    ):
        raise ValueError("financial run coverage mismatch")
    dd = read_csv(package / "tablas/drawdown_comparativo.csv")
    expected_dd = {
        (*tuple(row[key] for key in (*IDENTITY, "period")), policy, valuation)
        for row in metrics
        for policy in ("period_reset", "full_trajectory_peak")
        for valuation in ("original_reconstructed", "valoracion_proxy_hipotetica")
    }
    if set(indexed(dd, (*IDENTITY, "period", "peak_policy", "valuation"))) != expected_dd:
        raise ValueError("drawdown identity/policy/valuation coverage mismatch")
    check_drawdown_rows(dd)
    reconciliations = read_csv(package / "tablas/conciliaciones_diarias.csv")
    check_reconciliations(reconciliations)
    expected_daily = {
        (key[0], str(t))
        for key in identities
        for t in range(
            reconstruction["start_ns"] + DAY - 1, reconstruction["end_exclusive_ns"], DAY
        )
    }
    if set(indexed(reconciliations, ("run_id", "time_ns"))) != expected_daily:
        raise ValueError("daily reconciliation coverage mismatch")
    intervals = read_csv(package / "tablas/intervalos_exposicion_reutilizados.csv")
    episodes = read_csv(package / "tablas/catalogo_incidentes.csv")
    interval_ids = {tuple(row[key] for key in (*IDENTITY, "symbol")) for row in intervals}
    if interval_ids != {
        (*tuple(row[key] for key in IDENTITY), symbol)
        for row in identities.values()
        for symbol in SYMBOLS
    }:
        raise ValueError("reused interval portfolio/symbol coverage mismatch")
    check_episode_catalog(
        intervals, episodes, reconstruction["start_ns"], reconstruction["end_exclusive_ns"]
    )
    if correction is not None:
        check_reused_metrics(
            metrics, read_csv(Path(correction) / "comparacion/metricas_cartera_periodo.csv")
        )
        source_intervals = [
            row
            for row in read_csv(Path(correction) / "comparacion/exposicion_intervalos.csv")
            if (row["run_id"],) in identities
        ]
        if indexed(intervals, (*IDENTITY, "symbol", "start_ns", "end_ns")) != indexed(
            source_intervals, (*IDENTITY, "symbol", "start_ns", "end_ns")
        ):
            raise ValueError("corrected exposure intervals changed")
        for name in (
            "h1_resumen.csv",
            "h1_invariancia.csv",
            "h2.csv",
            "h3_regimen.csv",
            "h3_invariancia.csv",
        ):
            if (package / "tablas" / name).read_bytes() != (
                Path(correction) / "comparacion" / name
            ).read_bytes():
                raise ValueError("preserved hypothesis table changed: " + name)
    counts = {}
    for name, group in (
        ("eventos_financieros", "run_id"),
        ("episodios", "episode_id"),
        ("marzo_2023", "run_id"),
    ):
        values = read_arrays(package / "evidencia" / (name + ".parquet"))
        check_quality_clock(quality["time_ns"], values["time_ns"], exact=False)
        counts[name] = check_evidence_columns(
            values, group, complete_financial=name == "eventos_financieros"
        )
        if name == "episodios":
            _episode_values(values, episodes)
        elif set(values["run_id"]) != {key[0] for key in identities}:
            raise ValueError("compact evidence misses portfolios")
    daily, margin = _daily_tables(package, metrics)
    expected_days = {
        (*tuple(row[key] for key in IDENTITY), str(t))
        for row in identities.values()
        for t in range(reconstruction["start_ns"], reconstruction["end_exclusive_ns"], DAY)
    }
    if set(indexed(daily, (*IDENTITY, "day_ns"))) != expected_days or set(
        indexed(margin, (*IDENTITY, "day_ns", "symbol"))
    ) != {(*key, symbol) for key in expected_days for symbol in SYMBOLS}:
        raise ValueError("daily portfolio/symbol coverage mismatch")
    for row in daily + margin:
        if timestamp(row["date"] + "T00:00:00Z") != int(row["day_ns"]):
            raise ValueError("daily calendar identity mismatch")
    point_rows = read_csv(package / "tablas/puntos_extremos.csv")
    expected_points = {
        (*tuple(row[key] for key in IDENTITY), label)
        for row in identities.values()
        for label in (
            "worst_equity_drawdown",
            "full_min_headroom_BTCUSDT",
            "full_min_headroom_ETHUSDT",
        )
    }
    if set(indexed(point_rows, (*IDENTITY, "label"))) != expected_points:
        raise ValueError("extreme point portfolio/label coverage mismatch")
    check_extreme_points(point_rows, dd, margin)
    provenance = read_json(package / "tablas_procedencia.json")
    for field, value in (
        ("daily_risk_rows", len(daily)),
        ("margin_daily_asset_rows", len(margin)),
        ("incidents", len(episodes)),
        ("drawdown_rows", len(dd)),
    ):
        if provenance[field] != value:
            raise ValueError("table provenance count mismatch: " + field)
    result = dict(
        status="passed",
        scope=scope,
        schema=SCHEMA,
        manifest_sha256=sha256(package / MANIFEST),
        members_checked=len(manifest["files"]),
        drawdown_rows_checked=len(dd),
        incidents_checked=len(episodes),
        daily_reconciliations_checked=len(reconciliations),
        compact_evidence_rows_checked=counts,
        global_drawdown_recomputed=False,
        daily_nesting_recomputed=False,
        price_quality_rows_checked=quality_count,
        price_quality_union_recomputed=False,
        price_quality_reason_codes_recomputed=False,
        parent_authenticated=parent is not None,
        correction_authenticated=correction is not None,
        package_read_only=True,
        sources_read_only=True,
        engine_replay=False,
        external_funding_is_hypothetical=True,
        limitations="compact scope checks exported arithmetic and coverage declarations, not global extrema or minute-price completeness",
    )
    if scope == "complete":
        result.update(
            _complete(
                package,
                Path(parent),
                Path(correction),
                Path(series_root),
                Path(data_root),
                series,
                prices,
                metrics,
                dd,
                quality,
                quality_meta,
            )
        )
        result["limitations"] = (
            "price convention retains documented carry/estimates; proxy is hypothetical fixed-position valuation"
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())

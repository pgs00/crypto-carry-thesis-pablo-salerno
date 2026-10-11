"""Read-only persisted account states and causal local price selection.

This module never instantiates a strategy or applies a simulated fill. Physical
ledger order is authoritative. Decimal builds account movements; float64 arrays
are the bulk valuation representation, checked against every original daily row.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

SECOND = 1_000_000_000
MINUTE = 60 * SECOND
DAY = 86400 * SECOND
SYMBOLS = ("BTCUSDT", "ETHUSDT")
ACCOUNT = ("free_spot", "free_futures", "debt")
POSITION = ("spot", "short", "average", "collateral")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_parquet(path):
    return pq.ParquetFile(path).read().to_pylist()


def utc_ns(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()) * SECOND


def iso(value):
    if value is None:
        return ""
    seconds, nanos = divmod(int(value), SECOND)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S") + f".{nanos:09d}Z"


def account_history(rows, capital, symbols=SYMBOLS):
    """Expand every post-ledger row to full accounts, preserving ties and cash flows.

    Index zero is the original initial account. asset_cash assigns each global
    cash/debt change to the event's symbol; with that symbol's marked inventory
    it gives cumulative PnL, without counting transfers or collateral twice.
    """
    zero = Decimal(0)
    cash = {key: zero for key in ACCOUNT}
    cash["free_spot"] = Decimal(str(capital))
    positions = {key: [zero] * len(symbols) for key in POSITION}
    asset_cash = [zero] * len(symbols)
    result = {key: [float(cash[key])] for key in ACCOUNT}
    result.update({key: [[float(v) for v in values]] for key, values in positions.items()})
    result["asset_cash"] = [[0.0] * len(symbols)]
    times, identities, kinds = [np.iinfo(np.int64).min], ["initial"], ["initial"]
    seen = set()
    for row in rows:
        time = int(row["time_ns"])
        identity = row["event_id"]
        if time < times[-1] or identity in seen:
            raise ValueError("Unordered or duplicated persisted ledger")
        seen.add(identity)
        try:
            asset = symbols.index(row["symbol"])
            values = {key: Decimal(str(row[key])) for key in (*ACCOUNT, *POSITION)}
        except (KeyError, ValueError, ArithmeticError) as exc:
            raise ValueError("Incomplete ledger post-state") from exc
        if any(not value.is_finite() for value in values.values()):
            raise ValueError("Nonfinite ledger post-state")
        before = cash["free_spot"] + cash["free_futures"] - cash["debt"]
        for key in ACCOUNT:
            cash[key] = values[key]
            result[key].append(float(cash[key]))
        after = cash["free_spot"] + cash["free_futures"] - cash["debt"]
        asset_cash[asset] += after - before
        for key in POSITION:
            positions[key][asset] = values[key]
            result[key].append([float(v) for v in positions[key]])
        result["asset_cash"].append([float(v) for v in asset_cash])
        times.append(time)
        identities.append(identity)
        kinds.append(row["kind"])
    result = {key: np.asarray(value, dtype=np.float64) for key, value in result.items()}
    result.update(time_ns=np.array(times, dtype=np.int64), event_id=identities, kind=kinds)
    return result


def observation_grid(start_ns, end_ns, history, daily_times, *, extra_times=(), step_ns=MINUTE):
    """Minute union exact timestamps; financial times contain pre + every post state."""
    if end_ns <= start_ns or step_ns <= 0:
        raise ValueError("Invalid observation bounds")
    financial = history["time_ns"][1:]
    selected = np.flatnonzero((financial >= start_ns) & (financial < end_ns)) + 1
    financial_times = history["time_ns"][selected]
    unique_financial = np.unique(financial_times)
    regular = np.unique(np.concatenate((
        np.arange(start_ns, end_ns, step_ns, dtype=np.int64),
        np.asarray(daily_times, dtype=np.int64), np.asarray(extra_times, dtype=np.int64),
    )))
    regular = regular[(regular >= start_ns) & (regular < end_ns)]
    regular = regular[~np.isin(regular, unique_financial)]
    pre_indices = np.searchsorted(history["time_ns"], unique_financial, side="left") - 1
    regular_indices = np.searchsorted(history["time_ns"], regular, side="right") - 1
    times = np.concatenate((regular, unique_financial, financial_times))
    indices = np.concatenate((regular_indices, pre_indices, selected))
    post_sequence = selected - np.searchsorted(history["time_ns"], financial_times) + 1
    sequence = np.concatenate((np.zeros(len(regular) + len(unique_financial), int), post_sequence))
    phase = np.concatenate((
        np.zeros(len(regular), dtype=np.int8),
        np.ones(len(unique_financial), dtype=np.int8),
        np.full(len(selected), 2, dtype=np.int8),
    ))
    order = np.lexsort((sequence, times))
    return dict(time_ns=times[order], sequence=sequence[order],
                state_index=indices[order], phase=phase[order])


def price_at(prices, times, *, require_volume):
    """Last available close; zero-volume bars cannot refresh execution references."""
    available = np.asarray(prices["available_at"], dtype=np.int64)
    close = np.asarray(prices["close"], dtype=float)
    valid = np.isfinite(close) & (close > 0)
    if require_volume:
        valid &= np.asarray(prices["base_volume"], dtype=float) > 0
    candidates = np.flatnonzero(valid)
    if np.any(np.diff(available) < 0):
        raise ValueError("Unordered price availability")
    found = np.searchsorted(available[candidates], times, side="right") - 1
    known = found >= 0
    selected = candidates[np.maximum(found, 0)] if len(candidates) else np.zeros(len(times), int)
    output = {"price": np.full(len(times), np.nan)}
    output["price"][known] = close[selected[known]]
    for key in ("available_at", "open_time", "end_time", "close_time", "source_id", "estimated"):
        if key in prices:
            data = np.asarray(prices[key])
            values = np.full(len(times), -1, dtype=np.int64)
            values[known] = data[selected[known]]
            output[key] = values
    output["age_ns"] = np.where(known, times - output["available_at"], -1)
    output["evaluable"] = known
    return output


def reconcile_daily(expected, times, equity, tolerance=1e-8):
    """No nearest timestamp joins and no tolerance expansion."""
    output = []
    for row in expected:
        time = int(row["time_ns"])
        index = np.searchsorted(times, time, side="right") - 1
        if index < 0 or times[index] != time:
            raise ValueError(f"missing daily timestamp: {time}")
        residual = float(equity[index]) - float(row["equity"])
        ok = bool(np.isfinite(residual) and abs(residual) <= tolerance)
        output.append(dict(time_ns=time, original_equity=row["equity"],
                           reconstructed_equity=float(equity[index]), residual_usdt=residual, ok=ok))
        if not ok:
            raise ValueError(f"daily reconciliation failed at {time}: {residual}")
    return output


class LocalPrices:
    """Monthly reads shared by all portfolios, with one predecessor partition.

    Manifest source ids are stable within this reader. Inputs are opened read-only.
    The external audit authenticates the complete original processed manifest.
    """

    def __init__(self, data_root, manifest_path=None):
        self.root = Path(data_root)
        self.manifest_path = self.root / (manifest_path or (
            "data/minutes/2022_2026_continuous/derived_marks/futures_scaled/manifests/processed.json"
        ))
        all_entries = json.loads(self.manifest_path.read_text(encoding="utf-8"))["entries"]
        self.entries = [dict(row, source_id=i) for i, row in enumerate(all_entries)
                        if row["dataset"] in {"minute_bars", "marks"}]

    def block(self, month):
        result = {}
        for symbol in SYMBOLS:
            for market, dataset, label in (("spot", "minute_bars", "spot"),
                                           ("futures", "minute_bars", "futures"),
                                           ("futures", "marks", "mark")):
                candidates = [row for row in self.entries if row["symbol"] == symbol
                              and row["market"] == market and row["dataset"] == dataset]
                present = [row for row in candidates if row["date"] == month]
                previous = sorted((row for row in candidates if row["date"] < month),
                                  key=lambda row: row["date"])[-1:]
                if not present:
                    raise ValueError(f"Missing local price partition: {month}/{symbol}/{label}")
                chunks = []
                for entry in previous + present:
                    parquet = pq.ParquetFile(self.root / entry["path"])
                    columns = [key for key in (
                        "available_at", "open_time", "end_time", "close_time", "close", "base_volume",
                        "estimation_method",
                    ) if key in parquet.schema_arrow.names]
                    table = parquet.read(columns=columns)
                    values = {}
                    for key in columns:
                        if key == "estimation_method":
                            values["estimated"] = np.array([
                                value not in (None, "", "official") for value in table[key].to_pylist()
                            ], dtype=np.int8)
                        else:
                            dtype = pa.float64() if key in {"close", "base_volume"} else pa.int64()
                            values[key] = table[key].cast(dtype).to_numpy(zero_copy_only=False)
                    values.setdefault("estimated", np.zeros(len(table), dtype=np.int8))
                    values["source_id"] = np.full(len(table), entry["source_id"], dtype=np.int32)
                    chunks.append(values)
                names = set.intersection(*(set(chunk) for chunk in chunks))
                result[symbol, label] = {key: np.concatenate([c[key] for c in chunks]) for key in names}
        return result

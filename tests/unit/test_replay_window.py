import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from crypto_carry.config import HOUR, SECOND
from crypto_carry.data.replay import iter_records
from crypto_carry.events import event_time


def trade(time_ns, trade_id, *, symbol="BTCUSDT", market="spot"):
    return {
        "symbol": symbol,
        "market": market,
        "trade_id": str(trade_id),
        "event_time": time_ns,
        "available_at": time_ns,
        "price": "100",
        "quantity": "1",
        "source_file": "test.csv",
    }


def funding(time_ns, rate="0.001"):
    return {
        "symbol": "BTCUSDT",
        "funding_time": time_ns,
        "available_at": time_ns + 60 * SECOND,
        "funding_rate": rate,
        "interval_hours": "1",
        "settlement_mark_price": "100",
        "source_file": "test.json",
        "interval_verified": True,
    }


def partition(root, name, rows, *, dataset="trades", bounds=True):
    path = root / f"{name}.parquet"
    pq.write_table(pa.Table.from_pylist(rows), path)
    entry = {
        "dataset": dataset,
        "symbol": rows[0]["symbol"],
        "market": rows[0].get("market", "futures"),
        "path": path.name,
        "rows": len(rows),
    }
    if bounds:
        times = [row.get("funding_time", row["available_at"]) for row in rows]
        entry.update(start=min(times), end=max(times))
    return entry


def manifest(root, entries, *, data_dir="data"):
    destination = root / data_dir / "manifests" / "processed.json"
    destination.parent.mkdir(parents=True)
    destination.write_text(json.dumps({"entries": entries}), encoding="utf-8")


def test_window_does_not_open_obsolete_or_future_partitions(tmp_path):
    prior = partition(tmp_path, "prior", [trade(8, 8), trade(9, 9)])
    current = partition(tmp_path, "current", [trade(10, 10), trade(11, 11)])
    obsolete = dict(prior, path="unread-obsolete.parquet", start=0, end=1)
    future = dict(prior, path="unread-future.parquet", start=12, end=13)
    manifest(tmp_path, [future, current, obsolete, prior])

    records = list(iter_records(tmp_path, 10, 12, warmup_hours=0))

    assert [record.trade_id for record in records] == ["9", "10", "11"]


def test_crossing_partition_prunes_strictly_older_antecedent_partition(tmp_path):
    crossing = partition(tmp_path, "crossing", [trade(t, t) for t in (9, 10, 11)])
    obsolete = dict(crossing, path="unread-prior.parquet", start=1, end=8)
    manifest(tmp_path, [obsolete, crossing])

    records = list(iter_records(tmp_path, 10, 12, warmup_hours=0))

    assert [record.trade_id for record in records] == ["9", "10", "11"]


def test_crossing_partition_retains_antecedent_partition_tied_at_its_start(tmp_path):
    prior = partition(tmp_path, "prior", [trade(9, 9)])
    crossing = partition(tmp_path, "crossing", [trade(9, 8), trade(10, 10)])
    manifest(tmp_path, [prior, crossing])

    records = list(iter_records(tmp_path, 10, 12, warmup_hours=0))

    assert [record.trade_id for record in records] == ["9", "10"]


def test_last_observation_before_window_is_retained_at_eof(tmp_path):
    entries = [
        partition(tmp_path, "old", [trade(1, 1), trade(3, 3)]),
        partition(tmp_path, "last", [trade(7, 7), trade(9, 9)]),
    ]
    manifest(tmp_path, entries)

    records = list(iter_records(tmp_path, 10, 12, warmup_hours=0))

    assert [record.trade_id for record in records] == ["9"]


def test_antecedent_uses_latest_end_not_latest_partition_start(tmp_path):
    entries = [
        partition(tmp_path, "long", [trade(1, 1), trade(9, 9)]),
        partition(tmp_path, "short", [trade(5, 5), trade(6, 6)]),
        partition(tmp_path, "current", [trade(10, 10)]),
    ]
    manifest(tmp_path, entries)

    records = list(iter_records(tmp_path, 10, 12, warmup_hours=0))

    assert [record.trade_id for record in records] == ["9", "10"]


def test_overlapping_partitions_merge_before_selecting_single_antecedent(tmp_path):
    entries = [
        partition(tmp_path, "first", [trade(t, t) for t in (1, 8, 12, 16)]),
        partition(tmp_path, "second", [trade(t, t) for t in (2, 9, 10, 14)]),
    ]
    manifest(tmp_path, entries)

    records = list(iter_records(tmp_path, 10, 15, warmup_hours=0))

    assert [record.trade_id for record in records] == ["9", "10", "12", "14"]


def test_equal_timestamp_partitions_preserve_numeric_trade_order(tmp_path):
    entries = [
        partition(tmp_path, "prior-a", [trade(1, 1), trade(5, 9)]),
        partition(tmp_path, "prior-b", [trade(2, 2), trade(5, 8)]),
        partition(tmp_path, "current-a", [trade(10, 10), trade(11, 30)]),
        partition(tmp_path, "current-b", [trade(10, 2), trade(11, 20)]),
    ]
    manifest(tmp_path, entries)

    records = list(iter_records(tmp_path, 10, 12, warmup_hours=0))

    assert [record.trade_id for record in records] == ["9", "2", "10", "20", "30"]


def test_funding_warmup_uses_settlement_time_and_keeps_one_prior_observation(tmp_path):
    prior = partition(tmp_path, "prior-funding", [funding(7 * HOUR)], dataset="funding")
    active = partition(
        tmp_path,
        "active-funding",
        [funding(t * HOUR) for t in (8, 9, 10, 11)],
        dataset="funding",
    )
    obsolete = dict(prior, path="unread-funding.parquet", start=HOUR, end=2 * HOUR)
    manifest(tmp_path, [obsolete, active, prior], data_dir="custom")

    records = list(iter_records(tmp_path, 10 * HOUR, 11 * HOUR, 2, data_dir="custom"))

    assert [event_time(record) for record in records] == [
        7 * HOUR,
        8 * HOUR,
        9 * HOUR,
        10 * HOUR,
    ]


def test_antecedents_are_separate_for_each_symbol_and_market(tmp_path):
    entries = [
        partition(tmp_path, "btc-spot", [trade(6, "spot")]),
        partition(tmp_path, "btc-futures", [trade(7, "futures", market="futures")]),
        partition(tmp_path, "eth-spot", [trade(8, "eth", symbol="ETHUSDT")]),
    ]
    manifest(tmp_path, entries)

    records = list(iter_records(tmp_path, 10, 12, warmup_hours=2))

    assert [record.trade_id for record in records] == ["spot", "futures", "eth"]


def test_entries_without_bounds_are_read_and_merged_conservatively(tmp_path):
    entries = [
        partition(tmp_path, "unknown", [trade(1, 1), trade(11, 11)], bounds=False),
        partition(tmp_path, "known", [trade(9, 9), trade(10, 10)]),
    ]
    manifest(tmp_path, entries)

    records = list(iter_records(tmp_path, 10, 12, warmup_hours=0))

    assert [record.trade_id for record in records] == ["9", "10", "11"]


def test_replay_opens_later_partitions_only_when_reached(tmp_path):
    first = partition(tmp_path, "first", [trade(10, 10), trade(11, 11)])
    later = dict(first, path="later.parquet", start=15, end=15, rows=1)
    manifest(tmp_path, [later, first])
    records = iter_records(tmp_path, 10, 20, warmup_hours=0)

    assert next(records).trade_id == "10"
    partition(tmp_path, "later", [trade(15, 15)])

    assert [record.trade_id for record in records] == ["11", "15"]


@pytest.mark.parametrize("bad_range", [(12, 10), ("invalid", 12)])
def test_invalid_partition_bounds_are_not_silently_pruned(tmp_path, bad_range):
    entry = partition(tmp_path, "bad-bounds", [trade(10, 10)])
    entry.update(start=bad_range[0], end=bad_range[1])
    manifest(tmp_path, [entry])

    with pytest.raises(ValueError):
        list(iter_records(tmp_path, 10, 12, warmup_hours=0))


def test_unordered_selected_partition_raises(tmp_path):
    entry = partition(tmp_path, "unordered", [trade(t, t) for t in (10, 12, 11)])
    manifest(tmp_path, [entry])

    with pytest.raises(ValueError, match="order"):
        list(iter_records(tmp_path, 10, 20, warmup_hours=0))


def test_selected_records_outside_declared_bounds_raise(tmp_path):
    entry = partition(tmp_path, "wrong-bounds", [trade(9, 9), trade(10, 10)])
    entry.update(start=10, end=11)
    manifest(tmp_path, [entry])

    with pytest.raises(ValueError, match="bounds"):
        list(iter_records(tmp_path, 10, 12, warmup_hours=0))


def test_truncated_antecedent_partition_does_not_silently_lose_prior_observation(tmp_path):
    entry = partition(tmp_path, "truncated", [trade(7, 7)])
    entry.update(end=9, rows=2)
    manifest(tmp_path, [entry])

    with pytest.raises(ValueError, match="bounds|rows"):
        list(iter_records(tmp_path, 10, 12, warmup_hours=0))


@pytest.mark.parametrize("bounds", [(9, 9), (10, 11)])
def test_corrupt_antecedent_or_window_partition_still_raises(tmp_path, bounds):
    entry = partition(tmp_path, "corrupt", [trade(bounds[0], 1)])
    entry.update(start=bounds[0], end=bounds[1])
    (tmp_path / entry["path"]).write_bytes(b"corrupt parquet")
    manifest(tmp_path, [entry])

    with pytest.raises(pa.ArrowInvalid):
        list(iter_records(tmp_path, 10, 12, warmup_hours=0))


def test_conflicting_funding_observations_are_not_deduplicated(tmp_path):
    entries = [
        partition(tmp_path, "first", [funding(10), funding(12)], dataset="funding"),
        partition(tmp_path, "second", [funding(10, "0.002"), funding(14)], dataset="funding"),
    ]
    manifest(tmp_path, entries)

    records = list(iter_records(tmp_path, 10, 15, warmup_hours=0))

    assert [event_time(record) for record in records] == [10, 10, 12, 14]
    assert [str(record.funding_rate) for record in records[:2]] == ["0.001", "0.002"]

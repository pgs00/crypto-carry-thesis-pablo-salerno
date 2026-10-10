"""E3 editorial exposure excludes persisted dust but retains active inventory."""

import csv
from decimal import Decimal as D
from pathlib import Path

import pytest

from crypto_carry.config import timestamp
from scripts.rules_sensitivity_exposure import exposure_intervals, exposure_summary

SECOND = 1_000_000_000


def position(time=0, symbol="BTCUSDT", spot="0", short="0", state="FLAT", **extra):
    return dict(time_ns=time * SECOND, symbol=symbol, spot=spot, short=short, state=state, **extra)


def summarize(rows, end=10, start=0, periods=None):
    intervals = exposure_intervals(rows, start * SECOND, end * SECOND, D("0.005"))
    return intervals, exposure_summary(
        intervals, periods or [("full", start * SECOND, end * SECOND)]
    )


def portfolio(rows):
    return next(row for row in rows if row["symbol"] == "PORTFOLIO")


def test_dust_is_not_active_investment():
    _, result = summarize([position(spot="0.00001")])
    row = portfolio(result)
    assert row["invested_seconds"] == 0
    assert row["unhedged_seconds"] == 0
    assert row["raw_invested_seconds"] == 10
    assert row["raw_unhedged_seconds"] == 10
    assert row["dust_only_seconds"] == 10
    assert row["no_inventory_seconds"] == 0


def test_dust_with_other_asset_covered_is_invested_once():
    _, result = summarize(
        [position(spot="0.01"), position(symbol="ETHUSDT", spot="1", short="1", state="HOLDING")]
    )
    row = portfolio(result)
    assert row["invested_seconds"] == row["covered_seconds"] == 10
    assert row["dust_seconds"] == row["raw_unhedged_seconds"] == 10
    assert row["unhedged_seconds"] == row["dust_only_seconds"] == 0
    assert row["no_active_seconds"] == 0


def test_persisted_dust_metadata_and_covered_tolerance_are_respected():
    intervals, result = summarize([position(spot="0.01", state="CLOSING_SPOT", dust_spot="0.01")])
    assert intervals[0]["exposure"] == "dust"
    assert portfolio(result)["dust_only_seconds"] == 10
    _, covered = summarize([position(spot="1", short="0.995", state="HOLDING")])
    _, uncovered = summarize([position(spot="1", short="0.994999999", state="HOLDING")])
    assert portfolio(covered)["covered_seconds"] == 10
    assert portfolio(uncovered)["unhedged_seconds"] == 10


def test_simultaneous_positions_and_cross_asset_coverage_overlap():
    _, result = summarize(
        [
            position(spot="1", short="1", state="HOLDING"),
            position(symbol="ETHUSDT", spot="1", short="0", state="OPENING_SPOT"),
            position(5, "ETHUSDT", spot="1", short="1", state="HOLDING"),
        ]
    )
    row = portfolio(result)
    assert row["invested_seconds"] == 10
    assert row["covered_seconds"] == 10
    assert row["unhedged_seconds"] == 5
    assert row["both_covered_seconds"] == 5
    assert row["raw_invested_fraction"] == row["invested_fraction"] == 1


@pytest.mark.parametrize(
    "spot,short,state",
    [
        ("0", "1", "CLOSING_PERP"),
        ("0.00001", "0", "OPENING_SPOT"),
        ("2", "1", "CLOSING_SPOT"),
        ("1", "0", "CLOSING_SPOT"),
    ],
)
def test_partial_or_pending_active_inventory_is_not_dust(spot, short, state):
    intervals, result = summarize([position(spot=spot, short=short, state=state)])
    assert intervals[0]["exposure"] == "unhedged"
    assert portfolio(result)["unhedged_seconds"] == 10


def test_dust_memory_survives_reentry_and_period_cut():
    rows = [
        position(spot="0.01"),
        position(2, spot="0.01", state="OPENING_SPOT"),
        position(4, spot="1.01", state="OPENING_SPOT"),
        position(6, spot="1.01", short="1.01", state="HOLDING"),
        position(8, spot="0.01", state="CLOSING_SPOT"),
    ]
    intervals, result = summarize(rows, periods=[("cut", SECOND, 10 * SECOND)])
    btc = [r["exposure"] for r in intervals if r["symbol"] == "BTCUSDT"]
    assert btc == ["dust", "dust", "unhedged", "covered", "dust"]
    row = portfolio(result)
    assert row["dust_only_seconds"] == 5
    assert row["invested_seconds"] == 4
    assert row["covered_seconds"] == row["unhedged_seconds"] == 2


def test_prior_history_preserves_known_dust_at_requested_start():
    _, result = summarize(
        [position(-2, spot="0.01"), position(-1, spot="0.01", state="OPENING_SPOT")], start=0
    )
    assert portfolio(result)["dust_only_seconds"] == 10


def test_last_persisted_same_timestamp_wins_and_end_is_exclusive():
    rows = [
        position(spot="1", state="CLOSING_SPOT"),
        position(spot="0.01"),
        position(10, spot="10", short="10", state="HOLDING"),
    ]
    _, result = summarize(rows)
    assert portfolio(result)["dust_only_seconds"] == 10
    _, result_reversed = summarize(rows[:2][::-1])
    assert portfolio(result_reversed)["unhedged_seconds"] == 10


def test_one_nanosecond_terminal_interval_is_not_dropped():
    intervals = exposure_intervals(
        [
            position(spot="0.01"),
            dict(position(spot="1", short="1", state="HOLDING"), time_ns=SECOND - 1),
        ],
        0,
        SECOND,
        D("0.005"),
    )
    result = portfolio(exposure_summary(intervals, [("full", 0, SECOND)]))
    assert result["invested_seconds"] == D("0.000000001")
    assert result["dust_only_seconds"] == D("0.999999999")


@pytest.mark.parametrize(
    "field,value",
    [("spot", None), ("short", ""), ("state", None), ("spot", "NaN"), ("short", "Infinity")],
)
def test_missing_or_nonfinite_metadata_fails_with_affected_interval(field, value):
    row = position(spot="0.01")
    row[field] = value
    with pytest.raises(ValueError, match="BTCUSDT.*\\[0, 10000000000\\)"):
        summarize([row])


def test_flat_dust_and_active_partitions_and_fractions():
    _, result = summarize(
        [position(2, spot="0.01"), position(4, spot="1", short="1", state="HOLDING")]
    )
    row = portfolio(result)
    assert row["no_inventory_seconds"] == 2
    assert row["dust_only_seconds"] == 2
    assert row["no_active_seconds"] == 4
    assert row["invested_seconds"] == 6
    assert row["raw_invested_seconds"] == 8
    for record in result:
        assert all(
            D(0) <= value <= D(1) for key, value in record.items() if key.endswith("_fraction")
        )


def test_summary_rejects_gaps_or_overlapping_asset_intervals():
    intervals, _ = summarize([position(5, spot="1", short="1", state="HOLDING")])
    intervals[0]["end_ns"] -= 1
    with pytest.raises(ValueError):
        exposure_summary(intervals, [("full", 0, 10 * SECOND)])


@pytest.mark.parametrize(
    "strategy,expected_seconds,expected_unhedged,count",
    [
        ("conditional", 41691120, 11340, 3710),
        ("permanent", 144587820, 16440, 3913),
    ],
)
def test_exact_archived_e3_intervals_seconds_and_121_minute_episode(
    strategy, expected_seconds, expected_unhedged, count
):
    root = Path(__file__).resolve().parents[2]
    source = root / "Paquete de evidencia"
    with (source / "evidencia/positions.csv").open(encoding="utf-8", newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row["strategy"] == strategy]
    start, end = timestamp("2022-01-01T00:00:00Z"), timestamp("2026-09-01T00:00:00Z")
    intervals = exposure_intervals(rows, start, end, D("0.005"))
    assert len(intervals) == count
    with (source / "tablas/exposicion_intervalos.csv").open(encoding="utf-8", newline="") as stream:
        originals = [row for row in csv.DictReader(stream) if row["strategy"] == strategy]
    for actual, expected in zip(intervals, originals, strict=True):
        for field, value in expected.items():
            if field not in {"strategy", "source_run_id"}:
                assert str(actual[field]) == value
    result = portfolio(exposure_summary(intervals, [("full", start, end)]))
    assert result["invested_seconds"] == expected_seconds
    assert result["unhedged_seconds"] == expected_unhedged
    assert result["calendar_seconds"] == 147225600
    day = timestamp("2023-03-24T00:00:00Z")
    episode = exposure_summary(intervals, [("episode", day, day + 86400 * SECOND)])
    assert portfolio(episode)["unhedged_seconds"] == 7260
    expected_assets = {"ETHUSDT"} if strategy == "conditional" else {"BTCUSDT", "ETHUSDT"}
    for row in episode:
        if row["symbol"] in expected_assets:
            assert row["unhedged_seconds"] == 7260

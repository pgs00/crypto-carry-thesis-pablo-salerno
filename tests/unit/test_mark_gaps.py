"""Literal mark-gap causality contracts from the approved original evidence."""
from copy import deepcopy
from decimal import Decimal as D

import pytest

from crypto_carry.config import Config, timestamp

MINUTE = 60_000_000_000
T = timestamp("2024-08-12T10:02:00Z")


def inputs():
    def mark(t, close):
        return dict(
            symbol="BTCUSDT",
            open_time=t,
            close_time=t + MINUTE - 1_000_000,
            available_at=t + MINUTE,
            open=close,
            high=close,
            low=close,
            close=close,
            source_file="official-mark.zip",
        )

    def future(t, close):
        return dict(
            symbol="BTCUSDT",
            market="futures",
            open_time=t,
            end_time=t + MINUTE,
            available_at=t + MINUTE,
            open="100",
            high="120",
            low="90",
            close=close,
            base_volume="10",
            quote_volume="1000",
            trade_count=3,
            source_file="official-futures.zip",
        )

    marks = {T - MINUTE: mark(T - MINUTE, "101"), T + 2 * MINUTE: mark(T + 2 * MINUTE, "999")}
    bars = {t: future(t, p) for t, p in [(T - MINUTE, "100"), (T, "110"), (T + MINUTE, "120")]}
    return marks, bars


def test_strict_is_default_and_cannot_opt_in_outside_research():
    assert getattr(Config(), "mark_gap_method", None) == "strict"
    with pytest.raises(ValueError, match="research"):
        Config(mark_gap_method="futures_scaled")


def test_documented_allowlist_matches_original_evidence():
    from crypto_carry.data.mark_gaps import APPROVED_MINUTES

    # Literal rows from the original unresolved_mark_minutes.csv evidence.
    documented = {
        ('ETHUSDT', timestamp('2022-07-12T12:57:00.000000000Z')),
        ('ETHUSDT', timestamp('2022-07-12T13:07:00.000000000Z')),
        ('ETHUSDT', timestamp('2022-07-12T13:15:00.000000000Z')),
        ('ETHUSDT', timestamp('2022-07-12T13:16:00.000000000Z')),
        ('ETHUSDT', timestamp('2022-07-12T13:17:00.000000000Z')),
        ('ETHUSDT', timestamp('2022-07-12T13:18:00.000000000Z')),
        ('ETHUSDT', timestamp('2022-07-12T13:19:00.000000000Z')),
        ('ETHUSDT', timestamp('2022-07-12T13:20:00.000000000Z')),
        ('ETHUSDT', timestamp('2022-07-12T13:21:00.000000000Z')),
        ('ETHUSDT', timestamp('2022-07-12T13:52:00.000000000Z')),
        ('ETHUSDT', timestamp('2022-07-13T06:59:00.000000000Z')),
        ('BTCUSDT', timestamp('2024-08-12T10:02:00.000000000Z')),
        ('BTCUSDT', timestamp('2024-08-12T10:03:00.000000000Z')),
        ('ETHUSDT', timestamp('2024-08-12T10:02:00.000000000Z')),
        ('ETHUSDT', timestamp('2024-08-12T10:03:00.000000000Z')),
    }
    assert APPROVED_MINUTES == documented
    assert len(documented) == 15


@pytest.mark.parametrize(
    "method,closes", [("futures_scaled", ["111.10", "121.20"]), ("last_official", ["101", "101"])]
)
def test_consecutive_gap_uses_one_official_anchor_and_next_minute_availability(method, closes):
    from crypto_carry.data.mark_gaps import estimate_gap

    marks, bars = inputs()
    originals = deepcopy((marks, bars))
    rows, audit = estimate_gap("BTCUSDT", [T, T + MINUTE], marks, bars, method)
    assert [D(r["close"]) for r in rows] == list(map(D, closes))
    assert [r["available_at"] for r in rows] == [T + MINUTE, T + 2 * MINUTE]
    assert [r["anchor_open_time"] for r in audit] == [T - MINUTE, T - MINUTE]
    assert all(r["estimation_method"] == method for r in rows)
    assert (marks, bars) == originals
    if method == "futures_scaled":
        assert {k: D(rows[0][k]) for k in ("open", "high", "low")} == {
            "open": D("101"),
            "high": D("121.2"),
            "low": D("90.9"),
        }
    else:
        assert all(D(r[k]) == 101 for r in rows for k in ("open", "high", "low", "close"))


def test_future_official_values_do_not_affect_estimates():
    from crypto_carry.data.mark_gaps import estimate_gap

    marks, bars = inputs()
    before = estimate_gap("BTCUSDT", [T, T + MINUTE], marks, bars, "futures_scaled")
    marks[T + 2 * MINUTE]["close"] = "0.01"
    bars[T + 3 * MINUTE] = dict(bars[T], open_time=T + 3 * MINUTE, close="50000")
    assert estimate_gap("BTCUSDT", [T, T + MINUTE], marks, bars, "futures_scaled") == before


@pytest.mark.parametrize(
    "damage",
    [
        "anchor_mark",
        "anchor_future",
        "missing_future",
        "early_future",
        "late_anchor",
        "estimated_anchor",
        "bad_price",
        "extra_gap",
        "official_exists",
    ],
)
def test_unavailable_inputs_and_extra_gaps_keep_block(damage):
    from crypto_carry.data.mark_gaps import estimate_gap

    marks, bars = inputs()
    missing = [T, T + MINUTE]
    if damage == "anchor_mark":
        del marks[T - MINUTE]
    elif damage == "anchor_future":
        del bars[T - MINUTE]
    elif damage == "missing_future":
        del bars[T]
    elif damage == "early_future":
        bars[T]["available_at"] = T
    elif damage == "late_anchor":
        marks[T - MINUTE]["available_at"] = T + 2 * MINUTE
    elif damage == "estimated_anchor":
        marks[T - MINUTE]["estimation_method"] = "last_official"
    elif damage == "bad_price":
        bars[T]["close"] = "0"
    elif damage == "extra_gap":
        missing.append(T + 2 * MINUTE)
    elif damage == "official_exists":
        marks[T] = dict(marks[T - MINUTE], open_time=T)
    with pytest.raises(ValueError):
        estimate_gap("BTCUSDT", missing, marks, bars, "futures_scaled")


def test_constant_method_does_not_require_unused_future_data():
    from crypto_carry.data.mark_gaps import estimate_gap

    marks, _ = inputs()
    rows, _ = estimate_gap("BTCUSDT", [T, T + MINUTE], marks, {}, "last_official")
    assert [D(r["close"]) for r in rows] == [101, 101]

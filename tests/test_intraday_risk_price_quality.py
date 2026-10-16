"""Literal causal reference-quality classifications, independent of package writers."""
import importlib
import importlib.util

import numpy as np
import pytest

MINUTE = 60_000_000_000
DAY = 86_400_000_000_000


def implementation():
    name = "scripts.analysis.risk"
    assert importlib.util.find_spec(name) is not None, "price-quality annotator is missing"
    return importlib.import_module(name)


def prices(available, close, volume=None):
    result = {"available_at": np.array(available, dtype=np.int64), "close": np.array(close)}
    if volume is not None:
        result["base_volume"] = np.array(volume)
    return result


def test_missing_expected_bar_is_carry_until_available_reopening_without_future_lookup():
    raw = prices([0, 2 * MINUTE], [100.0, 103.0], [1.0, 1.0])
    times = np.array([0, MINUTE - 1, MINUTE, 2 * MINUTE - 1, 2 * MINUTE])
    result = implementation().quality_codes(raw, times, require_volume=True)
    assert result.tolist() == [0, 0, 2, 2, 0]
    assert result.dtype == np.uint8


def test_zero_volume_does_not_refresh_spot_but_volume_is_irrelevant_for_mark():
    raw = prices([0, MINUTE, 2 * MINUTE], [100.0, 90.0, 95.0], [1.0, 0.0, 1.0])
    times = np.array([MINUTE, MINUTE + 1, 2 * MINUTE])
    quality = implementation().quality_codes
    assert quality(raw, times, require_volume=True).tolist() == [3, 3, 0]
    assert quality(raw, times, require_volume=False).tolist() == [0, 0, 0]


@pytest.mark.parametrize("invalid", [np.nan, np.inf, 0.0, -1.0])
def test_invalid_close_has_its_own_reason_even_if_volume_is_zero(invalid):
    raw = prices([0, MINUTE], [100.0, invalid], [1.0, 0.0])
    result = implementation().quality_codes(raw, np.array([MINUTE]), require_volume=True)
    assert result.tolist() == [4]


@pytest.mark.parametrize("invalid", [np.nan, -1.0])
def test_invalid_volume_is_not_described_as_zero_volume(invalid):
    raw = prices([0, MINUTE], [100.0, 99.0], [1.0, invalid])
    result = implementation().quality_codes(raw, np.array([MINUTE]), require_volume=True)
    assert result.tolist() == [5]


def test_unavailable_reference_is_not_fabricated_from_a_future_or_invalid_bar():
    raw = prices([MINUTE, 2 * MINUTE], [0.0, 100.0], [1.0, 1.0])
    times = np.array([0, MINUTE, 2 * MINUTE - 1, 2 * MINUTE])
    assert implementation().quality_codes(raw, times, require_volume=True).tolist() == [1, 1, 1, 0]
    empty = prices([], [], [])
    assert implementation().quality_codes(empty, times, require_volume=True).tolist() == [1] * 4


def test_original_daily_timestamp_uses_last_available_minute_not_next_midnight():
    raw = prices([DAY - MINUTE, DAY], [100.0, 90.0], [1.0, 0.0])
    result = implementation().quality_codes(raw, np.array([DAY - 1, DAY]), require_volume=True)
    assert result.tolist() == [0, 3]


@pytest.mark.parametrize("available", [[MINUTE, 0], [0, 0], [0, MINUTE + 1]])
def test_ambiguous_or_nonminute_source_clock_fails_instead_of_inventing_a_reason(available):
    raw = prices(available, [100.0, 101.0], [1.0, 1.0])
    with pytest.raises(ValueError, match="availability"):
        implementation().quality_codes(raw, np.array([MINUTE]), require_volume=True)

from decimal import Decimal

import pytest

from crypto_carry.config import Config, iso, timestamp


def test_frozen_baseline_and_storage_limit():
    c = Config()
    assert c.capital == Decimal("10000")
    assert c.window_hours == 336
    assert c.signal_delay_seconds == 60
    assert c.data_budget_bytes == 20_000_000_000
    assert c.symbols == ("BTCUSDT", "ETHUSDT")


def test_invalid_timings_and_paths_fail_visibly():
    with pytest.raises(ValueError):
        Config(signal_delay_seconds=-1)
    with pytest.raises(ValueError):
        Config(window_hours=0)
    with pytest.raises(ValueError):
        Config(data_dir="../outside")


def test_nanosecond_timestamp_roundtrip_keeps_strict_order_boundaries():
    value = 1704067200000000001
    assert timestamp(iso(value)) == value

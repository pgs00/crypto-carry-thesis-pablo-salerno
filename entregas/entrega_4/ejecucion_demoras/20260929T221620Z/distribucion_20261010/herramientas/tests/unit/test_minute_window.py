"""Independent arithmetic checks for the one-window execution contract."""

from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from crypto_carry import execution
from crypto_carry.config import SECOND, Config, timestamp


def test_minute_window_uses_only_intervals_starting_at_or_after_submission():
    boundary = timestamp("2024-01-01T12:01:00Z")
    assert hasattr(execution, "minute_window")
    assert execution.minute_window(boundary) == (boundary, boundary + 60 * SECOND)
    assert execution.minute_window(boundary + 15 * SECOND) == (
        boundary + 60 * SECOND,
        boundary + 120 * SECOND,
    )


def test_minute_vwap_is_quote_over_base_and_zero_has_no_execution_price():
    assert hasattr(execution, "minute_vwap")
    assert execution.minute_vwap(SimpleNamespace(base_volume=D(2), quote_volume=D(200))) == 100
    assert execution.minute_vwap(SimpleNamespace(base_volume=D(0), quote_volume=D(0))) is None


def test_capacity_is_shared_and_rounded_down_in_base_units():
    assert hasattr(execution, "minute_capacity")
    first = execution.minute_capacity(D(".15"), D(10), D(".01"), D(".01"))
    assert first == D(".10")
    assert D(".15") - first == D(".05")
    assert execution.minute_capacity(D(".15"), D(10), D(".01"), D(".01"), first) == 0
    assert execution.minute_capacity(D(".15"), D(0), D(".01"), D(".01")) == 0


def test_new_policy_config_declares_participation_and_joint_sizing():
    config = Config(
        analysis_mode="prescribed_research",
        fee_profile="prescribed_fixed_no_discounts",
        execution_model="next_minute_vwap",
        sizing_model="joint_quantity",
    )
    assert config.max_volume_participation == D(".01")
    for value in (D(0), D("1.01")):
        with pytest.raises(ValueError, match="participation"):
            config.changed(max_volume_participation=value)

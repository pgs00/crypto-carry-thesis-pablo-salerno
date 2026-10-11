"""Hand-derived contracts for the approved, deterministic market intervention."""

from dataclasses import replace
from decimal import Decimal as D

import pytest

from crypto_carry.config import SECOND
from crypto_carry.data.stress_counterfactual import (
    compile_shock,
    counterfactual_bar,
    shock_bar,
)
from crypto_carry.models import MinuteBar

M = 60 * SECOND


def candle(market="spot", symbol="BTCUSDT", opening=0):
    return MinuteBar(symbol, market, opening, opening + M, opening + M,
                     D(100), D(110), D(90), D(105), D(10), D(1020), 5, "observed")


def test_calendar_ceiling_and_one_minute_minimum_do_not_modify_consumed_bar():
    factors = compile_shock([("BTCUSDT", M + 1, M + 2)], {"BTCUSDT": D(".12")})
    assert factors.get(("BTCUSDT", M), D(1)) == 1
    assert factors["BTCUSDT", 2 * M] == D(".88")
    assert factors["BTCUSDT", 3 * M] == D(".88")
    assert factors["BTCUSDT", 4 * M] == D(".882")
    assert factors["BTCUSDT", 62 * M] == D(".998")
    assert factors.get(("BTCUSDT", 63 * M), D(1)) == 1
    assert factors.get(("ETHUSDT", 2 * M), D(1)) == 1


def test_overlap_uses_max_intensity_without_compounding_and_is_order_independent():
    episodes = [("BTCUSDT", 0, M), ("BTCUSDT", 30 * M, 31 * M)]
    factors = compile_shock(episodes, {"BTCUSDT": D(".12")})
    assert factors == compile_shock(list(reversed(episodes)), {"BTCUSDT": D(".12")})
    assert factors["BTCUSDT", 30 * M] == D(".88")
    assert factors["BTCUSDT", 60 * M] == D(".938")
    assert factors.get(("BTCUSDT", 91 * M), D(1)) == 1


def test_scaled_price_quote_and_vwap_preserve_base_activity_and_original():
    original = candle()
    changed = shock_bar(original, D(".9"), "fixture")
    assert (changed.open, changed.high, changed.low, changed.close) == (
        D(90), D(99), D(81), D("94.5"))
    assert changed.quote_volume == 918
    assert changed.quote_volume / changed.base_volume == D("91.8")
    assert (changed.base_volume, changed.trade_count) == (10, 5)
    assert (changed.open_time, changed.end_time, changed.available_at) == (0, M, M)
    assert original.close == 105 and original.source_file == "observed"
    assert shock_bar(original, D(1), "zero") is original
    assert shock_bar(candle("futures"), D(".9"), "fixture") == candle("futures")


def test_inactive_shock_candle_never_acquires_volume():
    changed = shock_bar(replace(candle(), base_volume=D(0), quote_volume=D(0), trade_count=0),
                        D(".9"), "fixture")
    assert changed.base_volume == changed.quote_volume == changed.trade_count == 0


def test_counterfactual_uses_fixed_preclosure_anchor_and_spot_volume():
    future = candle("futures")
    result = counterfactual_bar(future, D(101), D(100), D(4), 7, "fixture")
    assert result.market == "spot"
    assert (result.open, result.high, result.low, result.close) == (
        D(101), D("111.1"), D("90.9"), D("106.05"))
    assert result.base_volume == 4 and result.quote_volume == D("412.08")
    assert result.quote_volume / result.base_volume == D("103.02")
    assert result.trade_count == 7
    assert (future.close - result.close) / result.close < 0
    assert result.available_at == future.end_time
    assert future.base_volume == 10 and future.quote_volume == 1020


@pytest.mark.parametrize("change", [
    {"high": D(99)}, {"base_volume": D(0)}, {"quote_volume": D(2000)},
    {"available_at": M - 1}, {"trade_count": 0},
])
def test_counterfactual_rejects_incoherent_or_early_future_source(change):
    with pytest.raises(ValueError):
        counterfactual_bar(replace(candle("futures"), **change), D(101), D(100),
                           D(4), 7, "fixture")


def test_zero_volume_assumption_stays_inactive_and_incompatible_activity_is_rejected():
    result = counterfactual_bar(candle("futures"), D(101), D(100), D(0), 0, "fixture")
    assert result.base_volume == result.quote_volume == result.trade_count == 0
    with pytest.raises(ValueError):
        counterfactual_bar(candle("futures"), D(101), D(100), D(4), 0, "fixture")


@pytest.mark.parametrize("magnitude", [D(-1), D(1), D("NaN")])
def test_invalid_magnitude_cannot_create_nonpositive_or_reversed_prices(magnitude):
    with pytest.raises(ValueError):
        compile_shock([("BTCUSDT", 0, M)], {"BTCUSDT": magnitude})

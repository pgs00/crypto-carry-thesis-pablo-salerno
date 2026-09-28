from dataclasses import replace
from decimal import Decimal as D

import pytest

from crypto_carry.config import SECOND, Config, timestamp
from crypto_carry.data.funding_proxy import resolve_funding_mark
from crypto_carry.models import Funding, Mark


def case(**changes):
    config = Config(
        analysis_mode="prescribed_research", fee_profile="prescribed_fixed_no_discounts", **changes
    )
    time = timestamp(config.start)
    funding = Funding(
        "BTCUSDT", time, time + 60 * SECOND, D(".001"), D(8), None, "rates.json", True
    )
    mark = Mark(
        "BTCUSDT",
        time - 60 * SECOND,
        time - 1_000_000,
        time,
        D(99),
        D(101),
        D(98),
        D(100),
        "marks.zip",
    )
    return config, funding, mark


def test_previous_close_preserves_raw_source_and_records_provenance():
    config, funding, mark = case()
    resolved = resolve_funding_mark(funding, mark, config)
    assert funding.settlement_mark_price is None
    assert resolved.settlement_mark_price == D(100)
    assert resolved.source_file == "rates.json"
    assert resolved.settlement_mark_method == "previous_closed_1m"
    assert resolved.settlement_mark_source_file == "marks.zip"
    assert resolved.settlement_mark_close_time == mark.close_time
    assert resolved.settlement_mark_available_at == funding.funding_time
    assert resolved.settlement_mark_proxy_base == D(100)


def test_strict_mode_does_not_impute_and_exact_marks_are_never_stressed():
    config, funding, mark = case(funding_proxy_stress_bps=D(10))
    exact = replace(funding, settlement_mark_price=D("100.123"))
    assert resolve_funding_mark(exact, mark, config) is exact
    assert resolve_funding_mark(funding, mark, Config()) is funding


@pytest.mark.parametrize(
    "rate,stress,expected",
    [
        (".001", "10", "99.9"),
        ("-.001", "10", "100.1"),
        (".001", "-10", "100.1"),
        ("-.001", "-10", "99.9"),
        ("0", "10", "100"),
    ],
)
def test_stress_direction_is_cashflow_adverse_for_both_funding_signs(rate, stress, expected):
    config, funding, mark = case(funding_proxy_stress_bps=D(stress))
    resolved = resolve_funding_mark(replace(funding, funding_rate=D(rate)), mark, config)
    assert resolved.settlement_mark_price == D(expected)
    assert resolved.settlement_mark_stress_bps == D(stress)


@pytest.mark.parametrize(
    "defect", ["missing", "future", "current", "stale", "symbol", "zero", "nan", "unclosed"]
)
def test_missing_economic_mark_cannot_use_noncausal_or_invalid_candle(defect):
    config, funding, mark = case()
    if defect == "missing":
        mark = None
    elif defect == "future":
        mark = replace(mark, available_at=funding.funding_time + 1)
    elif defect == "current":
        mark = replace(mark, open_time=funding.funding_time)
    elif defect == "stale":
        mark = replace(mark, open_time=mark.open_time - 60 * SECOND)
    elif defect == "symbol":
        mark = replace(mark, symbol="ETHUSDT")
    elif defect in {"zero", "nan"}:
        mark = replace(mark, close=D(0) if defect == "zero" else D("NaN"))
    else:
        mark = replace(mark, close_time=funding.funding_time)
    with pytest.raises(ValueError, match="BTCUSDT"):
        resolve_funding_mark(funding, mark, config)


def test_missing_warmup_mark_does_not_invent_settlement_price():
    config, funding, _ = case()
    funding = replace(funding, funding_time=funding.funding_time - 8 * 3600 * SECOND)
    resolved = resolve_funding_mark(funding, None, config)
    assert resolved.settlement_mark_price is None
    assert resolved.settlement_mark_method == "not_required_before_start"


def test_millisecond_offset_uses_same_preceding_closed_minute():
    config, funding, mark = case()
    funding = replace(funding, funding_time=funding.funding_time + 1_000_000)
    assert resolve_funding_mark(funding, mark, config).settlement_mark_price == D(100)


@pytest.mark.parametrize("bad", [D(0), D(-1), D("NaN"), D("Infinity")])
def test_present_but_invalid_exact_mark_is_not_replaced(bad):
    config, funding, mark = case()
    with pytest.raises(ValueError, match="settlement mark"):
        resolve_funding_mark(replace(funding, settlement_mark_price=bad), mark, config)

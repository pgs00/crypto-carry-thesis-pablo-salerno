from dataclasses import replace
from decimal import Decimal as D

import pytest

from crypto_carry.config import Config, timestamp
from crypto_carry.data.funding_proxy import MINUTE
from crypto_carry.models import Funding, Mark
from scripts.funding_price_analysis import (
    event_impact,
    paired_proxy,
    positions_before,
    price_stats,
    relative_error_bps,
    scenario_totals,
)


def timing_case():
    config = Config(
        analysis_mode="prescribed_research", fee_profile="prescribed_fixed_no_discounts"
    )
    boundary = timestamp(config.start)
    funding = Funding("BTCUSDT", boundary + 6_000_000, boundary + MINUTE, D(".001"), D(8), D(100))
    mark = Mark(
        "BTCUSDT", boundary - MINUTE, boundary - 1_000_000, boundary, D(101), D(101), D(101), D(101)
    )
    return config, funding, mark


def test_known_price_is_paired_without_mutation_using_millisecond_engine_rule():
    config, funding, mark = timing_case()
    proxy = paired_proxy(funding, mark, config)
    assert proxy.settlement_mark_price == D(101)
    assert proxy.settlement_mark_method == "previous_closed_1m"
    assert funding.settlement_mark_price == D(100)
    assert proxy.funding_time == funding.funding_time
    assert proxy.funding_rate == funding.funding_rate


@pytest.mark.parametrize("defect", ["future", "stale", "current"])
def test_pairing_refuses_candles_the_engine_cannot_use(defect):
    config, funding, mark = timing_case()
    if defect == "future":
        mark = replace(mark, available_at=funding.funding_time + 1)
    elif defect == "stale":
        mark = replace(mark, open_time=mark.open_time - MINUTE)
    else:
        mark = replace(mark, open_time=mark.open_time + MINUTE)
    with pytest.raises(ValueError, match="previous closed"):
        paired_proxy(funding, mark, config)


def test_error_uses_official_denominator_and_p95_is_absolute_linear_quantile():
    errors = [relative_error_bps(D(p), D(100)) for p in (99, 102, 100)]
    assert errors == [D(-100), D(200), D(0)]
    result = price_stats(errors)
    assert result["paired_observations"] == 3
    assert result["bias_bps"] == D(100) / 3
    assert result["mae_bps"] == 100
    assert result["p95_abs_bps"] == 190
    assert result["max_abs_bps"] == 200


def test_no_official_prices_does_not_mean_zero_error():
    result = price_stats([])
    assert result["paired_observations"] == 0
    assert all(result[k] is None for k in ("bias_bps", "mae_bps", "p95_abs_bps", "max_abs_bps"))


def test_position_is_before_same_time_fills_and_keeps_prior_same_time_order():
    events = [{"symbol": "BTCUSDT", "funding_time": t} for t in (10, 11, 12)]
    ledger = [
        {"symbol": "BTCUSDT", "time_ns": 9, "short": "2", "event_id": "open"},
        {"symbol": "BTCUSDT", "time_ns": 10, "short": "2", "event_id": "funding"},
        {"symbol": "BTCUSDT", "time_ns": 10, "short": "3", "event_id": "resize"},
        {"symbol": "BTCUSDT", "time_ns": 11, "short": "0", "event_id": "close"},
    ]
    actual = positions_before(events, ledger)
    assert [actual["BTCUSDT", t]["short_before"] for t in (10, 11, 12)] == [D(2), D(3), D(0)]
    assert actual["BTCUSDT", 10]["prior_ledger_event_id"] == "open"


@pytest.mark.parametrize("rate", [".001", "-.001", "0"])
def test_missing_price_scenarios_follow_cashflow_sign_and_are_symmetric(rate):
    row = event_impact(D(3), D(rate), D(200), D(200), "previous_closed_1m", D(20))
    expected = D(".0012") if D(rate) else D(0)
    assert row["favorable_delta_usdt"] == expected
    assert row["adverse_delta_usdt"] == -expected
    assert row["known_proxy_delta_usdt"] is None
    assert row["favorable_price"] > D(200) if D(rate) > 0 else row["favorable_price"] <= D(200)


def test_official_prices_only_contribute_to_observed_impact_never_sensitivity():
    row = event_impact(D(3), D("-.001"), D(200), D(202), "exact", D(20))
    assert row["base_funding_usdt"] == D("-.6")
    assert row["known_proxy_delta_usdt"] == D("-.006")
    assert row["favorable_delta_usdt"] == row["adverse_delta_usdt"] == 0
    assert row["favorable_price"] == row["adverse_price"] == D(200)


def test_no_position_has_no_cash_impact_even_if_price_error_is_large():
    row = event_impact(D(0), D(".001"), D(200), D(220), "exact", D(20))
    assert row["base_funding_usdt"] == row["known_proxy_delta_usdt"] == 0


def test_scenarios_keep_original_capital_and_do_not_add_observed_proxy_effect():
    events = [
        event_impact(D(3), D(".001"), D(200), D(220), "exact", D(20)),
        event_impact(D(3), D(".001"), D(200), D(200), "previous_closed_1m", D(20)),
    ]
    rows = scenario_totals(events, D(10000), D(11000))
    by_name = {r["scenario"]: r for r in rows}
    assert by_name["favorable"]["delta_usdt"] == D(".0012")
    assert by_name["favorable"]["delta_return_bps"] == D(".0012")
    assert by_name["favorable"]["net_return"] == D(".10000012")
    assert by_name["adverse"]["net_return"] == D(".09999988")
    assert by_name["base"]["net_return"] == D(".1")


def test_analysis_rejects_nonzero_existing_stress_instead_of_changing_parameters():
    config, funding, mark = timing_case()
    with pytest.raises(ValueError, match="zero stress"):
        paired_proxy(funding, mark, config.changed(funding_proxy_stress_bps=D(10)))

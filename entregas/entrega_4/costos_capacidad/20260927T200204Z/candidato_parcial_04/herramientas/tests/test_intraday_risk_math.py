"""Literal accounting/risk expectations, without invoking a backtest."""

import importlib

import numpy as np
import pytest

BTC = [
    dict(floor=0, cap=50_000, rate=".004", deduction=0),
    dict(floor=50_000, cap=100_000_000, rate=".01", deduction=300),
]
ETH = [
    dict(floor=0, cap=50_000, rate=".0065", deduction=0),
    dict(floor=50_000, cap=100_000_000, rate=".01", deduction=175),
]


def risk():
    return importlib.import_module("scripts.intraday_risk_math")


def test_intraday_loss_is_visible_even_when_daily_drawdown_is_zero():
    module = risk()
    np.testing.assert_allclose(module.drawdown_path([100, 80, 101], 100), [0, -0.2, 0])
    np.testing.assert_allclose(module.drawdown_path([101], 100), [0])
    result = module.drawdown_summary([1, 2, 3], [100, 80, 101], 100, 0)
    assert result["drawdown"] == pytest.approx(-0.2)
    assert result["peak_time_ns"] == 0
    assert result["trough_time_ns"] == 2
    assert result["recovery_time_ns"] == 3
    assert result["peak_equity"] == 100
    assert result["trough_equity"] == 80
    assert result["loss_usdt"] == 20
    assert result["missing_observations"] == 0


def test_equal_peaks_and_troughs_choose_first_persisted_observation():
    summary = risk().drawdown_summary([1, 2, 2, 3, 4], [110, 110, 88, 88, 111], 100, 0)
    assert summary["peak_time_ns"] == 1
    assert summary["peak_index"] == 0
    assert summary["trough_index"] == 2
    assert summary["recovery_time_ns"] == 4
    assert summary["loss_usdt"] == 22


def test_unrecovered_drawdown_and_exact_nanosecond_timestamps():
    start = 1_700_000_000_000_000_000
    summary = risk().drawdown_summary([start + 1, start + 2], [100, 90], 100, start)
    assert summary["trough_time_ns"] == start + 2
    assert summary["recovery_time_ns"] is None
    assert summary["recovery_observed"] is False


def test_gaps_are_nd_for_complete_maximum_but_observed_risk_is_retained():
    summary = risk().drawdown_summary([1, 2, 3, 4], [100, np.nan, 80, 101], 100, 0)
    assert np.isnan(summary["drawdown"])
    assert summary["observed_drawdown"] == pytest.approx(-0.2)
    assert summary["observed_loss_usdt"] == 20
    assert summary["missing_observations"] == 1
    assert summary["complete"] is False
    assert summary["reason"] == "incomplete_equity_coverage_observed_only"
    np.testing.assert_allclose(
        risk().drawdown_path([100, np.nan, 80], 100), [0, np.nan, -0.2], equal_nan=True
    )


def test_nonpositive_equity_is_not_clipped_to_zero_or_safe():
    np.testing.assert_allclose(risk().drawdown_path([0, -20], 100), [-1, -1.2])
    result = risk().drawdown_summary([1, 2], [0, -20], 100, 0)
    assert result["drawdown"] == pytest.approx(-1.2)
    assert result["loss_usdt"] == 120
    assert result["nonpositive_equity_observations"] == 2
    invalid_initial = risk().drawdown_summary([1, 2], [0, -1], 0, 0)
    assert np.isnan(invalid_initial["drawdown"])
    assert invalid_initial["reason"] == "initial_equity_not_positive"


@pytest.mark.parametrize("times,equity", [([2, 1], [100, 90]), ([1], [100, 90])])
def test_drawdown_rejects_reordered_or_misaligned_states(times, equity):
    with pytest.raises(ValueError):
        risk().drawdown_summary(times, equity, 100, 0)


def test_paired_spot_short_can_preserve_equity_while_margin_worsens():
    module = risk()
    equity = module.equity_value(
        0, 0, 0, [[1], [1]], [[1], [1]], 100, 20, [[100], [110]], [[100], [110]]
    )
    np.testing.assert_allclose(equity, [120, 120])
    margin = module.short_margin(1, 100, 20, [100, 110], 0.004, 0)
    np.testing.assert_allclose(margin["margin_balance"], [20, 10])
    np.testing.assert_allclose(margin["maintenance"], [0.4, 0.44])
    np.testing.assert_allclose(margin["ratio"], [0.02, 0.044])


def test_transfer_of_ten_from_common_cash_to_collateral_creates_no_equity():
    values = risk().equity_value([20, 10], 0, 0, [[0], [0]], 0, 0, [[0], [10]], 100, 100)
    np.testing.assert_allclose(values, [20, 20])


def test_symbol_axis_sums_assets_once_and_preserves_account_axis():
    equity = risk().equity_value(
        [10, 20],
        [2, 3],
        [1, 2],
        [[1, 2], [2, 1]],
        [[1, 0], [0, 1]],
        100,
        [[5, 7], [11, 13]],
        [[100, 10], [110, 20]],
        [[101, 11], [111, 21]],
    )
    np.testing.assert_allclose(equity, [142, 364])


def test_closed_future_retains_spot_price_risk_but_requires_no_maintenance():
    margin = risk().short_margin(0, np.nan, 0, np.nan, 0.004, 0)
    assert margin["maintenance"] == 0
    assert np.isnan(margin["ratio"])
    assert margin["no_short"]
    assert not margin["unsafe"]
    equity = risk().equity_value(0, 0, 0, [[2], [2]], 0, np.nan, 0, [[100], [90]], np.nan)
    np.testing.assert_allclose(equity, [200, 180])
    liquidation = risk().liquidation_distance(0, np.nan, 0, np.nan, BTC)
    assert np.isnan(liquidation["distance"])
    assert liquidation["reason"] == "no_open_short"


def test_financial_posting_states_include_funding_and_each_fee_once():
    equity = risk().equity_value(
        [200, 79, 79, 200],
        [0, 0, 2, 0],
        0,
        [[0], [1], [1], [0]],
        [[0], [1], [1], [0]],
        100,
        [[0], [20], [20], [0]],
        100,
        100,
    )
    np.testing.assert_allclose(equity, [200, 199, 201, 200])
    debt = risk().equity_value([100, 130], 0, [0, 30], [[0], [0]], 0, 0, 0, 1, 1)
    np.testing.assert_allclose(debt, [100, 100])


def test_simultaneous_liquidity_shares_cash_once_and_does_not_sum_across_time():
    result = risk().joint_liquidity([[60, 60], [60, 0], [0, 60]], 100)
    np.testing.assert_allclose(result["total_need"], [120, 60, 60])
    np.testing.assert_allclose(result["external_shortfall"], [20, 0, 0])
    reserved = risk().joint_liquidity([[60, 60]], 100, reserved_cash=30)
    np.testing.assert_allclose(reserved["redistributable"], [70])
    np.testing.assert_allclose(reserved["external_shortfall"], [50])


def test_unknown_commitments_or_needs_do_not_assert_available_liquidity():
    result = risk().joint_liquidity([[60, 60], [60, np.nan]], 100, reserved_cash=[np.nan, 0])
    assert np.isnan(result["external_shortfall"]).all()
    assert not result["evaluable"].any()
    with pytest.raises(ValueError):
        risk().joint_liquidity([[-1, 2]], 100)


def test_proxy_uses_fixed_causal_anchor_and_available_futures_only():
    result = risk().causal_spot_proxy(100, 200, [180, 220, 230], 10, [11, 12, 14], [11, 12, 13])
    np.testing.assert_allclose(result["price"], [90, 110, np.nan], equal_nan=True)
    assert result["evaluable"].tolist() == [True, True, False]
    assert result["reason"].tolist() == ["", "", "future_futures_price"]


@pytest.mark.parametrize(
    "anchor,anchor_time,futures,reason",
    [
        (np.nan, 1, 110, "missing_or_nonpositive_anchor"),
        (100, 9, 110, "future_anchor"),
        (100, 1, np.nan, "missing_or_nonpositive_futures_price"),
    ],
)
def test_proxy_absent_or_future_evidence_is_nd(anchor, anchor_time, futures, reason):
    result = risk().causal_spot_proxy(anchor, 100, futures, anchor_time, 5, 5)
    assert np.isnan(result["price"])
    assert not result["evaluable"]
    assert result["reason"] == reason


def test_nonpositive_margin_is_unsafe_with_nd_ratio():
    margin = risk().short_margin(1, 100, 10, [110, 111], 0.004, 0)
    np.testing.assert_allclose(margin["margin_balance"], [0, -1])
    np.testing.assert_allclose(margin["maintenance_shortfall"], [0.44, 1.444])
    assert np.isnan(margin["ratio"]).all()
    assert margin["unsafe"].all()


@pytest.mark.parametrize("tiers,expected", [(BTC, 200), (ETH, 325)])
def test_maintenance_at_inclusive_first_tier_boundary_and_m2_deduction(tiers, expected):
    result = risk().preventive_topup(1, 50_000, 20_000, 50_000, tiers)
    assert result["maintenance"] == expected
    second = risk().short_margin(
        1, 60_000, 20_000, 60_000, tiers[1]["rate"], tiers[1]["deduction"], multiplier=2
    )
    assert second["maintenance"] == (600 if tiers is BTC else 850)


def test_liquidation_searches_all_tiers_and_scales_whole_m2_requirement():
    normal = risk().liquidation_distance(1, 50_000, 200, 40_000, BTC)
    stressed = risk().liquidation_distance(1, 50_000, 400, 40_000, BTC, multiplier=2)
    assert normal["liquidation_price"] == pytest.approx(50_000)
    assert stressed["liquidation_price"] == pytest.approx(50_000)
    assert normal["distance"] == pytest.approx(0.25)


def test_preventive_distance_crosses_tier_at_adverse_mark():
    normal = risk().preventive_topup(1, 49_900, 1000, 49_900, BTC)
    stressed = risk().preventive_topup(1, 49_900, 1000, 49_900, BTC, multiplier=2)
    assert normal["topup_infimum"] == pytest.approx(6758.85)
    assert stressed["topup_infimum"] == pytest.approx(7032.7)
    assert not normal["strict_infimum"]


def test_ratio_equality_requires_strictly_more_without_an_invented_quantum():
    tiers = [dict(floor=0, cap=100_000_000, rate=".2", deduction=0)]
    collateral = [np.nextafter(40.0, -np.inf), 40.0, np.nextafter(40.0, np.inf)]
    result = risk().preventive_topup(1, 100, collateral, 100, tiers)
    assert result["ratio_triggered"].tolist() == [True, True, False]
    assert result["strict_infimum"].tolist() == [True, True, False]
    assert result["topup_infimum"][1] == 0
    assert result["distance_triggered"].tolist() == [False, False, False]


def test_distance_equality_passes_and_both_immediate_neighbours_are_distinguished():
    collateral = [np.nextafter(15.46, -np.inf), 15.46, np.nextafter(15.46, np.inf)]
    result = risk().preventive_topup(1, 100, collateral, 100, BTC)
    assert result["distance_triggered"].tolist() == [True, False, False]
    assert result["topup_infimum"][0] > 0
    assert result["topup_infimum"][1] == 0
    assert result["topup_infimum"][2] == 0
    assert result["strict_infimum"].tolist() == [False, False, False]


def test_closed_future_needs_no_topup_and_uncovered_tier_is_nd():
    closed = risk().preventive_topup(0, np.nan, 0, np.nan, BTC)
    assert closed["topup_infimum"] == 0
    assert not closed["strict_infimum"]
    assert not closed["preventive"]
    missing = risk().liquidation_distance(1, 100, 1_000_000_000, 100, BTC)
    assert np.isnan(missing["distance"])
    assert missing["reason"] == "liquidation_price_outside_tiers"


def test_maintenance_requirement_uses_first_inclusive_match_and_absent_short_zero():
    tiers = [
        dict(floor=0, cap=50_000, rate=".01", deduction=0),
        dict(floor=50_000, cap=100_000, rate=".02", deduction=0),
    ]
    requirement = risk().maintenance_requirement(
        [1, 1, 1, 0], [49_999, 50_000, 50_001, np.nan], tiers
    )
    np.testing.assert_allclose(requirement, [499.99, 500, 1000.02, 0])
    assert risk().maintenance_requirement(0.7, 71_428.57142857143, tiers) == 1000
    assert np.isnan(risk().maintenance_requirement(1, 100_001, tiers))


def test_whole_maintenance_multiplier_matches_already_scaled_tiers():
    scaled = [dict(row, rate=float(row["rate"]) * 2, deduction=row["deduction"] * 2) for row in BTC]
    np.testing.assert_allclose(
        risk().maintenance_requirement(1, [50_000, 60_000], BTC, 2), [400, 600]
    )
    result = risk().preventive_topup(1, 49_900, 1000, 49_900, scaled)
    assert result["topup_infimum"] == pytest.approx(7032.7)
    assert result["strict_boundary"] == result["strict_infimum"]


def test_dust_is_still_valued_and_inputs_are_not_modified():
    spot = np.array([[0.00001, 0], [0.00001, 0]])
    before = spot.copy()
    equity = risk().equity_value(
        [10, 10], 0, 0, spot, 0, np.nan, 0, [[30_000, np.nan], [20_000, np.nan]], np.nan
    )
    np.testing.assert_allclose(equity, [10.3, 10.2])
    np.testing.assert_array_equal(spot, before)


def test_daily_subset_cannot_show_larger_drawdown_under_same_initial_peak():
    intraday = risk().drawdown_summary([1, 2, 3, 4, 5], [100, 80, 110, 77, 120], 100, 0)
    daily = risk().drawdown_summary([3, 5], [110, 120], 100, 0)
    assert intraday["drawdown"] == pytest.approx(-0.3)
    assert intraday["loss_usdt"] == 33
    assert daily["drawdown"] == 0


def test_unknown_quantity_is_not_a_safe_margin_state_and_no_short_has_no_shortfall():
    unknown = risk().short_margin(np.nan, 100, 20, 100, 0.004, 0)
    assert unknown["unsafe"]
    assert not unknown["evaluable"]
    assert np.isnan(unknown["maintenance"])
    closed = risk().short_margin(0, np.nan, np.nan, np.nan, 0.004, 0)
    assert closed["maintenance_shortfall"] == 0


def test_infinite_need_is_nd_and_cannot_claim_sufficient_cash():
    liquidity = risk().joint_liquidity([[np.inf, 1]], 100)
    assert np.isnan(liquidity["total_need"]).all()
    assert np.isnan(liquidity["external_shortfall"]).all()
    assert not liquidity["evaluable"].any()

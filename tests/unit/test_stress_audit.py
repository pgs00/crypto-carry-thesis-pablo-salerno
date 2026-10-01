"""Independent literals for accounting diagnostics, never scenario selection."""

from decimal import Decimal as D

import pytest

from crypto_carry.config import Config
from crypto_carry.models import MarketRule, Tier
from scripts.stress_counterfactual_audit import (
    audit_opportunity,
    joint_requirement,
    preventive_requirement,
    price_attribution,
)


def account(**changes):
    return dict(spot="10", short="1", average="100", collateral="20", mark="110",
                spot_price="90", original_spot_price="100", factor=".9", **changes)


def rule():
    return MarketRule("BTCUSDT", "futures", D(".001"), D(".01"), D(".001"), D("10000"),
                      D(5), D("1000000"), D(".0005"),
                      (Tier(D(0), D("1000000"), D(".005"), D(0)),))


def test_recovery_and_underlying_move_use_pre_event_inventory_and_sum_once():
    before = account()
    after = {**before, "spot": "3", "spot_price": "104.5", "original_spot_price": "110",
             "factor": ".95"}
    r = price_attribution(before, after)
    assert r["factor_valuation_usdt"] == 50
    assert r["imposed_recovery_usdt"] == 50
    assert r["imposed_drop_usdt"] == 0
    assert r["underlying_price_usdt"] == 95
    assert r["total_preinventory_price_effect_usdt"] == 145
    assert r["decomposition_residual_usdt"] == 0
    assert r["inventory_scope"] == "pre_event_spot_quantity"


def test_transient_factor_loss_is_not_booked_as_a_cash_flow():
    before = {**account(), "spot_price": "100", "factor": "1"}
    after = account()
    r = price_attribution(before, after)
    assert r["imposed_drop_usdt"] == -100
    assert r["imposed_recovery_usdt"] == 0
    assert r["ledger_movement_created"] is False


def test_preventive_topup_is_distinct_from_maintenance_and_headroom():
    r = preventive_requirement(account(), rule(), Config())
    assert r["margin_balance_usdt"] == 10
    assert r["maintenance_usdt"] == D(".55")
    assert r["headroom_usdt"] == D("9.45")
    assert r["maintenance_shortfall_usdt"] == 0
    assert r["preventive_topup_infimum_usdt"] == D("7.1325")
    assert r["strict_infimum"] is False
    joint = joint_requirement([r], D(7), D(3), D(0))
    assert joint["uncommitted_cash_usdt"] == 4
    assert joint["external_shortfall_infimum_usdt"] == D("3.1325")


def test_no_short_has_no_margin_even_if_old_collateral_field_remains():
    r = preventive_requirement({**account(), "short": "0"}, rule(), Config())
    assert r["no_open_short"]
    assert r["margin_balance_usdt"] is None and r["margin_ratio"] is None
    assert r["preventive_topup_infimum_usdt"] == 0
    assert r["maintenance_usdt"] == 0


def test_ratio_equality_reports_infimum_not_an_invented_epsilon_transfer():
    r = preventive_requirement({**account(), "mark": "100", "collateral": "1"}, rule(),
                              Config(liquidation_distance=D(".001")))
    assert r["preventive_topup_infimum_usdt"] == 0
    assert r["strict_infimum"] is True


def test_unverified_cash_reservation_keeps_external_need_unknown():
    r = preventive_requirement(account(), rule(), Config())
    joint = joint_requirement([r], D(100), None, D(0))
    assert joint["external_shortfall_infimum_usdt"] is None
    assert joint["external_need_reason"] == "unknown_cash_commitment"


def witness():
    return dict(time_ns=120_000_000_000, symbol="BTCUSDT", complete=True, eligible=False,
                value="0", bad_symbol=False, mark_present=True, rules_present=True,
                operational=True, fresh=True, selection_cost=".0034", position_independent=True,
                forecast=dict(value=".01", valid=True, available_at=60_000_000_000),
                spot_bar=dict(open_time=60_000_000_000, end_time=120_000_000_000,
                              available_at=120_000_000_000, close="101", base_volume="4"),
                future_bar=dict(open_time=60_000_000_000, end_time=120_000_000_000,
                                available_at=120_000_000_000, close="100", base_volume="10"))


def test_h3_known_negative_basis_is_zero_and_full_eligible_forecast_is_not_truncated():
    row = witness()
    assert audit_opportunity(row, Config())["opportunity"] == 0
    row["spot_bar"]["close"] = "99.8"
    row.update(eligible=True, value=".01")
    assert audit_opportunity(row, Config())["opportunity"] == D(".01")
    row["value"] = ".0066"
    with pytest.raises(ValueError, match="opportunity"):
        audit_opportunity(row, Config())


def test_h3_unknown_forecast_is_unknown_not_a_known_zero():
    row = witness()
    row["forecast"]["valid"] = False
    row["complete"] = False
    result = audit_opportunity(row, Config())
    assert result["opportunity"] is None and not result["complete"]


def test_h3_future_availability_is_rejected_even_if_output_looks_plausible():
    row = witness()
    row["forecast"]["available_at"] = row["time_ns"] + 1
    with pytest.raises(ValueError, match="availability"):
        audit_opportunity(row, Config())

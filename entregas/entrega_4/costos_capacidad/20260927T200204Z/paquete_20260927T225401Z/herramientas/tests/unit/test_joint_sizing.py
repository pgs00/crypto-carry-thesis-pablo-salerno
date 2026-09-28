from decimal import Decimal

import pytest

from crypto_carry.config import Config
from crypto_carry.models import MarketRule
from crypto_carry.portfolio import joint_quantity

D = Decimal


def rule(
    market: str,
    *,
    step: str,
    fee: str = "0",
    min_qty: str | None = None,
    max_qty: str = "1000",
    min_notional: str = "0",
    max_notional: str = "1000000",
    tick: str = "0.01",
) -> MarketRule:
    return MarketRule(
        symbol="BTCUSDT",
        market=market,
        step=D(step),
        tick=D(tick),
        min_qty=D(min_qty or step),
        max_qty=D(max_qty),
        min_notional=D(min_notional),
        max_notional=D(max_notional),
        taker_fee=D(fee),
    )


def test_joint_quantity_matches_the_base_fee_numeric_example() -> None:
    plan = joint_quantity(
        equity=D("13.1"),
        spot_price=D("100"),
        futures_price=D("100"),
        mark=D("100"),
        existing_spot=D("0"),
        existing_short=D("0"),
        available_cash=D("100"),
        spot_rule=rule("spot", step="0.00001", fee="0.001"),
        futures_rule=rule("futures", step="0.001", fee="0.0005"),
        config=Config(),
    )

    assert plan.feasible
    assert plan.reason == "ok"
    assert plan.spot_side == "buy"
    assert plan.spot_quantity == D("0.03904")
    assert plan.futures_side == "sell"
    assert plan.futures_quantity == D("0.039")
    assert plan.spot_net_total == D("0.03900096")
    assert plan.short_total == D("0.039")
    assert plan.hedge_error == D("0.00000096") / D("0.03900096")
    assert plan.required_cash == D("5.856535205")
    assert plan.unallocated_target_usdt == D("0.029904")


@pytest.mark.parametrize(
    ("cost_multiplier", "gross_spot", "net_spot", "required_cash"),
    [
        ("1", "0.03904", "0.03900096", "5.856535205"),
        ("2", "0.03908", "0.03900184", "5.86307082"),
        ("3", "0.03912", "0.03900264", "5.869606845"),
    ],
)
def test_joint_quantity_recalculates_quantities_and_cash_for_cost_stress(
    cost_multiplier: str,
    gross_spot: str,
    net_spot: str,
    required_cash: str,
) -> None:
    plan = joint_quantity(
        equity=D("13.1"),
        spot_price=D("100"),
        futures_price=D("100"),
        mark=D("100"),
        existing_spot=D("0"),
        existing_short=D("0"),
        available_cash=D("100"),
        spot_rule=rule("spot", step="0.00001", fee="0.001"),
        futures_rule=rule("futures", step="0.001", fee="0.0005"),
        config=Config(cost_multiplier=D(cost_multiplier)),
    )

    assert plan.feasible
    assert plan.spot_quantity == D(gross_spot)
    assert plan.spot_net_total == D(net_spot)
    assert plan.required_cash == D(required_cash)


def test_joint_quantity_drops_a_step_when_base_fee_would_exceed_target() -> None:
    plan = joint_quantity(
        equity=D("13"),
        spot_price=D("100"),
        futures_price=D("100"),
        mark=D("100"),
        existing_spot=D("0"),
        existing_short=D("0"),
        available_cash=D("100"),
        spot_rule=rule("spot", step="0.00001", fee="0.001"),
        futures_rule=rule("futures", step="0.001", fee="0.0005"),
        config=Config(),
    )

    assert plan.feasible
    assert plan.short_total == D("0.038")
    assert plan.spot_quantity == D("0.03804")
    assert plan.spot_net_total == D("0.03800196")
    assert plan.spot_net_total * D("100") <= D("3.9")


def test_joint_quantity_does_not_reduce_inventory_when_an_increase_is_unaffordable() -> None:
    plan = joint_quantity(
        equity=D("13.1"),
        spot_price=D("100"),
        futures_price=D("100"),
        mark=D("100"),
        existing_spot=D("0.021"),
        existing_short=D("0.020"),
        available_cash=D("0"),
        spot_rule=rule("spot", step="0.00001", fee="0.001"),
        futures_rule=rule("futures", step="0.001", fee="0.0005"),
        config=Config(slippage=D("0")),
    )

    assert not plan.feasible
    assert plan.reason == "insufficient_cash"
    assert plan.spot_side is None
    assert plan.futures_side is None
    assert plan.spot_net_total == D("0.021")
    assert plan.short_total == D("0.020")


def test_joint_quantity_applies_notional_filters_at_adverse_execution_prices() -> None:
    plan = joint_quantity(
        equity=D("13.1"),
        spot_price=D("100"),
        futures_price=D("100"),
        mark=D("100"),
        existing_spot=D("0"),
        existing_short=D("0"),
        available_cash=D("100"),
        spot_rule=rule("spot", step="0.00001", fee="0.001", max_notional="3.82", tick="0.01"),
        futures_rule=rule("futures", step="0.001", tick="0.01"),
        config=Config(slippage=D("0.01")),
    )

    assert plan.feasible
    assert plan.short_total == D("0.037")
    assert plan.spot_quantity == D("0.03704")


def test_joint_quantity_chooses_largest_pair_that_fits_cash_budget() -> None:
    plan = joint_quantity(
        equity=D("13"),
        spot_price=D("100"),
        futures_price=D("100"),
        mark=D("100"),
        existing_spot=D("0"),
        existing_short=D("0"),
        available_cash=D("5.704"),
        spot_rule=rule("spot", step="0.00001", fee="0.001"),
        futures_rule=rule("futures", step="0.001"),
        config=Config(slippage=D("0")),
    )

    assert plan.feasible
    assert plan.spot_quantity == D("0.03804")
    assert plan.futures_quantity == D("0.038")
    assert plan.short_total == D("0.038")
    assert plan.required_cash == D("5.704")
    assert plan.unallocated_target_usdt == D("0.099804")


@pytest.mark.parametrize(
    ("available_cash", "futures_min_qty", "reason"),
    [
        ("100", "0.05", "market_rules"),
        ("1", "0.01", "insufficient_cash"),
    ],
)
def test_joint_quantity_rejects_before_trading_when_no_pair_is_viable(
    available_cash: str,
    futures_min_qty: str,
    reason: str,
) -> None:
    plan = joint_quantity(
        equity=D("13"),
        spot_price=D("100"),
        futures_price=D("100"),
        mark=D("100"),
        existing_spot=D("0"),
        existing_short=D("0"),
        available_cash=D(available_cash),
        spot_rule=rule("spot", step="0.00001", fee="0.001", min_qty="0.01"),
        futures_rule=rule("futures", step="0.001", min_qty=futures_min_qty),
        config=Config(slippage=D("0")),
    )

    assert not plan.feasible
    assert plan.reason == reason
    assert plan.spot_side is None
    assert plan.spot_quantity == 0
    assert plan.futures_side is None
    assert plan.futures_quantity == 0
    assert plan.required_cash == 0


def test_joint_quantity_uses_total_inventory_when_increasing_around_spot_dust() -> None:
    plan = joint_quantity(
        equity=D("13.1"),
        spot_price=D("100"),
        futures_price=D("100"),
        mark=D("100"),
        existing_spot=D("0.0105"),
        existing_short=D("0.010"),
        available_cash=D("100"),
        spot_rule=rule("spot", step="0.00001", fee="0.001"),
        futures_rule=rule("futures", step="0.001", fee="0.0005"),
        config=Config(slippage=D("0")),
    )

    assert plan.feasible
    assert plan.spot_side == "buy"
    assert plan.spot_quantity == D("0.02853")
    assert plan.futures_side == "sell"
    assert plan.futures_quantity == D("0.029")
    assert plan.spot_net_total == D("0.03900147")
    assert plan.short_total == D("0.039")


def test_joint_quantity_reduction_preserves_spot_dust_and_does_not_reserve_open_margin() -> None:
    plan = joint_quantity(
        equity=D("13.1"),
        spot_price=D("100"),
        futures_price=D("100"),
        mark=D("100"),
        existing_spot=D("0.050006"),
        existing_short=D("0.050"),
        available_cash=D("1"),
        spot_rule=rule("spot", step="0.00001", fee="0.001"),
        futures_rule=rule("futures", step="0.001", fee="0.0005"),
        config=Config(slippage=D("0")),
    )

    assert plan.feasible
    assert plan.spot_side == "sell"
    assert plan.spot_quantity == D("0.01100")
    assert plan.futures_side == "buy"
    assert plan.futures_quantity == D("0.011")
    assert plan.spot_net_total == D("0.039006")
    assert plan.short_total == D("0.039")
    assert plan.required_cash == D("0.00055")
    assert plan.hedge_error <= D("0.005")


def test_joint_quantity_reduction_uses_only_its_released_collateral_for_cash() -> None:
    plan = joint_quantity(
        equity=D("13.1"),
        spot_price=D("100"),
        futures_price=D("100"),
        mark=D("100"),
        existing_spot=D("0.050006"),
        existing_short=D("0.050"),
        available_cash=D("0"),
        spot_rule=rule("spot", step="0.00001", fee="0.001"),
        futures_rule=rule("futures", step="0.001", fee="0.0005"),
        config=Config(slippage=D("0")),
        existing_collateral=D("2.5"),
        existing_average=D("100"),
    )

    assert plan.feasible
    assert plan.futures_side == "buy"
    assert plan.futures_quantity == D("0.011")
    assert plan.required_cash == 0


def test_joint_quantity_requires_complete_valid_reduction_metadata() -> None:
    arguments = dict(
        equity=D("13.1"),
        spot_price=D("100"),
        futures_price=D("100"),
        mark=D("100"),
        existing_spot=D("0.050006"),
        existing_short=D("0.050"),
        available_cash=D("1"),
        spot_rule=rule("spot", step="0.00001", fee="0.001"),
        futures_rule=rule("futures", step="0.001", fee="0.0005"),
        config=Config(slippage=D("0")),
    )

    with pytest.raises(ValueError, match="together"):
        joint_quantity(**arguments, existing_collateral=D("2.5"))
    with pytest.raises(ValueError, match="non-negative"):
        joint_quantity(**arguments, existing_collateral=D("-1"), existing_average=D("100"))


def test_joint_quantity_rejects_losing_reduction_when_own_collateral_is_insufficient() -> None:
    common = dict(
        equity=D("13.1"),
        spot_price=D("100"),
        futures_price=D("100"),
        mark=D("100"),
        existing_spot=D("0.050006"),
        existing_short=D("0.050"),
        spot_rule=rule("spot", step="0.00001", fee="0.001"),
        futures_rule=rule("futures", step="0.001", fee="0.0005"),
        config=Config(slippage=D("0")),
        existing_collateral=D("0.001"),
        existing_average=D("99"),
    )

    rejected = joint_quantity(**common, available_cash=D("0"))
    funded = joint_quantity(**common, available_cash=D("0.01133"))

    assert not rejected.feasible
    assert rejected.reason == "insufficient_cash"
    assert funded.feasible
    assert funded.required_cash == D("0.01133")

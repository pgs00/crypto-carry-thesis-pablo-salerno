from dataclasses import replace
from decimal import Decimal

import pytest

from crypto_carry.config import HOUR, Config
from crypto_carry.costs import cycle_cost, execution_price, floor_step, valid_quantity
from crypto_carry.forecast import forecast, weight
from crypto_carry.ledger import Ledger
from crypto_carry.margin import liquidation_price, maintenance, margin_state
from crypto_carry.models import Fill, Funding, MarketRule, Tier
from crypto_carry.portfolio import hedge_error, needs_rebalance, required_cash, target_quantity

D = Decimal


def rule(
    market: str,
    *,
    fee: str = "0",
    step: str = "0.01",
    tick: str = "0.1",
    tiers: tuple[Tier, ...] = (),
    liquidation_fee: str = "0",
    liquidation_regular_fee: bool = True,
    liquidation_fee_basis: str = "execution_notional",
) -> MarketRule:
    return MarketRule(
        symbol="BTCUSDT",
        market=market,
        step=D(step),
        tick=D(tick),
        min_qty=D(step),
        max_qty=D("1000000"),
        min_notional=D("1"),
        max_notional=D("1000000000"),
        taker_fee=D(fee),
        tiers=tiers,
        liquidation_fee=D(liquidation_fee),
        liquidation_regular_fee=liquidation_regular_fee,
        liquidation_fee_basis=liquidation_fee_basis,
    )


def funding(
    time_hours: int,
    *,
    rate: str = "0.00008",
    interval: str = "8",
    available_at: int | None = None,
    verified: bool = True,
    mark: str = "100",
) -> Funding:
    time_ns = time_hours * HOUR
    return Funding(
        symbol="BTCUSDT",
        funding_time=time_ns,
        available_at=time_ns if available_at is None else available_at,
        funding_rate=D(rate),
        interval_hours=D(interval),
        settlement_mark_price=D(mark),
        interval_verified=verified,
    )


def fill(
    fill_id: str,
    market: str,
    side: str,
    quantity: str,
    price: str,
    *,
    reference: str | None = None,
    fee: str = "0",
    liquidation: bool = False,
) -> Fill:
    return Fill(
        fill_id=fill_id,
        order_id=f"order-{fill_id}",
        symbol="BTCUSDT",
        market=market,
        side=side,
        quantity=D(quantity),
        price=D(price),
        reference_price=D(price if reference is None else reference),
        time_ns=1,
        trade_id=f"trade-{fill_id}",
        fee_rate=D(fee),
        liquidation=liquidation,
    )


def test_duration_weighted_forecast_matches_constant_hourly_rate():
    history = [funding(0)]
    elapsed = 0
    for _ in range(14):
        for interval in (4, 8, 12):
            elapsed += interval
            history.append(
                funding(elapsed, rate=str(D("0.00001") * interval), interval=str(interval))
            )

    result = forecast(history, 336 * HOUR, 337 * HOUR, Config())

    assert result.valid
    assert result.value == D("0.00168")
    assert result.no_change == D("0.00168")
    assert result.history_start == 0


def test_forecast_weights_and_exact_lower_boundary_antecedent():
    assert weight(D("0"), D("24")) == D("1")
    assert weight(D("24"), D("24")) == D("0.5")
    assert weight(D("48"), D("24")) == D("0.25")
    history = [funding(hour) for hour in range(0, 337, 8)]
    history[0] = funding(0, rate="999")

    result = forecast(history, 336 * HOUR, 337 * HOUR, Config())

    assert result.valid
    assert result.value < D("1")
    assert result.history_start == 0


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda rows: rows.__setitem__(20, funding(160, interval="16")), "gap"),
        (lambda rows: rows.__setitem__(20, funding(160, verified=False)), "unverified"),
        (lambda rows: rows.__setitem__(20, funding(160, interval="0")), "positive"),
        (lambda rows: rows.__setitem__(20, funding(160, available_at=400 * HOUR)), "available"),
    ],
)
def test_forecast_blocks_incomplete_or_unavailable_history(mutate, reason):
    rows = [funding(hour) for hour in range(0, 337, 8)]
    mutate(rows)

    result = forecast(rows, 336 * HOUR, 337 * HOUR, Config())

    assert not result.valid
    assert reason in result.reason.lower()


def test_cost_rounding_cycle_cost_and_quantity_boundaries():
    cfg = Config(slippage=D("0.0001"))
    spot_rule = rule("spot", fee="0.001", step="0.01", tick="0.1")
    futures_rule = rule("futures", fee="0.0005", step="0.01", tick="0.1")

    assert floor_step(D("1.239"), D("0.01")) == D("1.23")
    assert execution_price(D("100.03"), "buy", spot_rule, cfg) == (D("100.1"), D("0.059997"))
    assert execution_price(D("100.03"), "sell", spot_rule, cfg) == (D("100.0"), D("0.019997"))
    assert cycle_cost(spot_rule, futures_rule, cfg) == D("0.0034")
    assert valid_quantity(D("0.01"), D("100"), spot_rule)
    assert valid_quantity(D("1000000"), D("100"), spot_rule)
    assert not valid_quantity(D("0.011"), D("100"), spot_rule)


def test_margin_tiers_liquidation_equality_and_prevention():
    tiers = (
        Tier(D("0"), D("100"), D("0.005"), D("0")),
        Tier(D("100"), D("1000"), D("0.01"), D("0.5")),
    )
    market_rule = rule("futures", tiers=tiers)
    expected = D("150.5") / D("1.01")

    assert maintenance(D("1"), D("100"), market_rule) == D("0.5")
    assert liquidation_price(D("1"), D("100"), D("50"), market_rule) == expected
    state = margin_state(D("1"), D("100"), D("50"), expected, market_rule, Config())
    assert abs(state["balance"] - state["maintenance"]) <= Config().accounting_tolerance
    assert state["liquidate"]
    assert state["preventive"]
    assert liquidation_price(D("0"), D("100"), D("50"), market_rule) is None


def test_liquidation_price_rejects_when_no_tier_covers_solution():
    market_rule = rule(
        "futures",
        tiers=(Tier(D("0"), D("10"), D("0.005"), D("0")),),
    )
    with pytest.raises(ValueError, match="tier"):
        liquidation_price(D("1"), D("100"), D("50"), market_rule)


def test_preventive_distance_is_strict_at_fifteen_percent():
    market_rule = rule(
        "futures",
        tiers=(Tier(D("0"), D("1000"), D("0.005"), D("0")),),
    )
    collateral = D("115") * D("1.005") - D("100")

    state = margin_state(D("1"), D("100"), collateral, D("100"), market_rule, Config())

    assert state["distance"] == D("0.15")
    assert state["ratio"] < D("0.50")
    assert not state["preventive"]


def test_spot_base_fee_is_received_units_and_reconciles_once():
    ledger = Ledger(Config(), "filtered")
    spot_rule = rule("spot", fee="0.001")

    assert ledger.apply_fill(
        fill("spot-buy", "spot", "buy", "10", "100", fee="0.001"), spot_rule, D("100")
    )

    position = ledger.positions["BTCUSDT"]
    assert position.spot == D("9.990")
    assert position.spot_cost == D("999.000")
    assert position.fees == D("1.000")
    assert ledger.free_spot == D("9000")
    assert ledger.equity({"BTCUSDT": D("100")}, {}) == D("9999")
    assert ledger.reconcile({"BTCUSDT": D("100")}, {})["difference"] == 0


def test_price_pnl_uses_absolute_spread_change():
    ledger = Ledger(Config(), "carry")
    zero_fee_spot = rule("spot")
    zero_fee_futures = rule("futures")
    assert ledger.apply_fill(fill("s", "spot", "buy", "1", "100"), zero_fee_spot, D("100"))
    assert ledger.apply_fill(fill("f", "futures", "sell", "1", "101"), zero_fee_futures, D("101"))

    assert ledger.equity({"BTCUSDT": D("110")}, {"BTCUSDT": D("111")}) == D("10000")
    assert ledger.equity({"BTCUSDT": D("110")}, {"BTCUSDT": D("112")}) == D("9999")
    assert ledger.reconcile({"BTCUSDT": D("110")}, {"BTCUSDT": D("112")})["difference"] == 0


def test_funding_waterfall_transfer_and_deduplication():
    ledger = Ledger(Config(), "carry")
    futures_rule = rule("futures")
    before = ledger.equity({}, {})
    assert ledger.transfer(D("1000"), 1, "transfer-1")
    assert ledger.equity({}, {}) == before
    assert ledger.rows[-1]["amount_usdt"] == D("1000")
    assert ledger.apply_fill(fill("open", "futures", "sell", "2", "100"), futures_rule, D("100"))

    credit = funding(8, rate="0.001", mark="100")
    assert ledger.apply_funding(credit)
    assert ledger.positions["BTCUSDT"].funding == D("0.2")
    assert not ledger.apply_funding(credit)
    conflicting = funding(8, rate="0.002", mark="100")
    with pytest.raises(ValueError, match="Conflicting"):
        ledger.apply_funding(conflicting)


def test_negative_funding_consumes_futures_then_contract_collateral_then_spot_then_debt():
    ledger = Ledger(Config(capital=D("100")), "carry")
    futures_rule = rule("futures")
    assert ledger.apply_fill(fill("open", "futures", "sell", "1", "100"), futures_rule, D("100"))
    ledger.free_futures = D("5")
    ledger.free_spot = D("3")

    debit = funding(8, rate="-0.60", mark="100")
    assert ledger.apply_funding(debit)

    position = ledger.positions["BTCUSDT"]
    assert ledger.free_futures == 0
    assert position.collateral == 0
    assert ledger.free_spot == 0
    assert ledger.debt == D("2")
    assert position.funding == D("-60")


def test_insolvency_preserves_negative_equity_and_reconciles():
    ledger = Ledger(Config(capital=D("100")), "carry")
    futures_rule = rule("futures")
    assert ledger.apply_fill(
        fill("open-insolvent", "futures", "sell", "1", "100"), futures_rule, D("100")
    )

    assert ledger.apply_funding(funding(8, rate="-2", mark="100"))

    assert ledger.debt == D("100")
    assert ledger.equity({}, {"BTCUSDT": D("100")}) == D("-100")
    assert ledger.reconcile({}, {"BTCUSDT": D("100")}) == {
        "equity": D("-100"),
        "pnl": D("-200"),
        "difference": D("0"),
    }


def test_partial_close_releases_collateral_and_realizes_loss_without_hidden_cash():
    ledger = Ledger(Config(capital=D("1000")), "carry")
    futures_rule = rule("futures", fee="0.001")
    assert ledger.apply_fill(
        fill("open", "futures", "sell", "2", "100", fee="0.001"), futures_rule, D("100")
    )
    collateral = ledger.positions["BTCUSDT"].collateral

    assert ledger.apply_fill(
        fill("close", "futures", "buy", "1", "110", fee="0.001"), futures_rule, D("110")
    )

    position = ledger.positions["BTCUSDT"]
    assert position.short == D("1")
    assert position.average == D("100")
    assert position.collateral == collateral / 2
    assert position.realized_futures == D("-10")
    assert ledger.free_spot >= 0
    assert ledger.free_futures >= 0
    assert ledger.reconcile({}, {"BTCUSDT": D("110")})["difference"] == 0


def test_released_collateral_repayments_existing_debt_before_becoming_free_cash():
    ledger = Ledger(Config(capital=D("200")), "carry")
    futures_rule = rule("futures")
    assert ledger.apply_fill(
        fill("btc-open", "futures", "sell", "1", "100"), futures_rule, D("100")
    )
    eth_rule = replace(futures_rule, symbol="ETHUSDT")
    eth_open = replace(fill("eth-open", "futures", "sell", "1", "100"), symbol="ETHUSDT")
    assert ledger.apply_fill(eth_open, eth_rule, D("100"))
    eth_debit = replace(funding(8, rate="-1.6", mark="100"), symbol="ETHUSDT")
    assert ledger.apply_funding(eth_debit)
    assert ledger.debt == D("10")

    assert ledger.apply_fill(
        fill("btc-close", "futures", "buy", "1", "110"), futures_rule, D("110")
    )

    assert ledger.debt == 0
    assert ledger.free_futures == D("30")
    assert ledger.reconcile({}, {"ETHUSDT": D("100")})["difference"] == 0


def test_unaffordable_voluntary_increase_is_atomic_and_duplicate_fill_conflicts():
    ledger = Ledger(Config(capital=D("10")), "carry")
    spot_rule = rule("spot")
    unaffordable = fill("too-large", "spot", "buy", "1", "100")
    assert not ledger.apply_fill(unaffordable, spot_rule, D("100"))
    assert ledger.free_spot == D("10")
    assert "BTCUSDT" not in ledger.positions

    affordable = fill("ok", "spot", "buy", "0.1", "100")
    assert ledger.apply_fill(affordable, spot_rule, D("100"))
    assert not ledger.apply_fill(affordable, spot_rule, D("100"))
    conflict = fill("ok", "spot", "buy", "0.1", "99")
    with pytest.raises(ValueError, match="Conflicting"):
        ledger.apply_fill(conflict, spot_rule, D("99"))


def test_liquidation_fee_is_charged_once_on_configured_basis():
    ledger = Ledger(Config(capital=D("1000")), "carry")
    futures_rule = rule(
        "futures",
        fee="0.001",
        liquidation_fee="0.01",
        liquidation_regular_fee=False,
        liquidation_fee_basis="mark_notional",
    )
    assert ledger.apply_fill(
        fill("open", "futures", "sell", "1", "100", fee="0.001"), futures_rule, D("100")
    )
    liquidation = fill("liq", "futures", "buy", "1", "120", fee="0.001", liquidation=True)
    assert ledger.apply_fill(liquidation, futures_rule, D("110"))
    position = ledger.positions["BTCUSDT"]
    assert position.liquidation_fees == D("1.10")
    assert position.fees == D("0.100")
    assert not ledger.apply_fill(liquidation, futures_rule, D("110"))


def test_portfolio_sizing_rebalance_hedge_and_required_cash():
    cfg = Config(slippage=D("0.0001"))
    spot_rule = rule("spot", fee="0.001", step="0.01", tick="0.1")
    futures_rule = rule("futures", fee="0.0005", step="0.01", tick="0.1")

    assert target_quantity(D("10000"), D("100"), D("0.003"), spot_rule, cfg) == D("29.993")
    assert not needs_rebalance(D("3150"), D("10000"), cfg)
    assert needs_rebalance(D("3150.01"), D("10000"), cfg)
    assert hedge_error(D("0"), D("0")) == 0
    assert hedge_error(D("0"), D("1")).is_infinite()
    assert hedge_error(D("10"), D("9.8")) == D("0.02")
    assert required_cash(D("10"), D("100"), D("101"), D("101"), spot_rule, futures_rule, cfg) == D(
        "1506.4984955"
    )

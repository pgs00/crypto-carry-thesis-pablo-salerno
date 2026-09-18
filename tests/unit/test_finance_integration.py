from dataclasses import replace
from decimal import Decimal as D

from crypto_carry.config import Config
from crypto_carry.costs import execution_price
from crypto_carry.ledger import Ledger
from crypto_carry.margin import liquidation_price, margin_state
from crypto_carry.models import Fill, Funding
from crypto_carry.portfolio import target_quantity


def test_sizing_can_reduce_an_overweight_position(rules):
    assert target_quantity(D(10000), D(100), D(40), rules.get("BTCUSDT", "spot", 0), Config()) == D(
        30
    )


def test_transaction_cost_multiplier_changes_actual_slippage(rules):
    rule = rules.get("BTCUSDT", "spot", 0)
    price, rounding = execution_price(D(100), "BUY", rule, Config(cost_multiplier=D(3)))
    assert price == D("100.03")


def test_two_funding_sources_have_one_economic_movement(rules):
    ledger = Ledger(Config(), "test")
    fill = Fill("f", "o", "BTCUSDT", "futures", "SELL", D(1), D(100), D(100), 1, "t", D(0))
    ledger.apply_fill(fill, rules.get("BTCUSDT", "futures", 0), D(100))
    f = Funding("BTCUSDT", 10, 70, D(".001"), D(8), D(100), "source-a", True)
    assert ledger.apply_funding(f)
    assert not ledger.apply_funding(replace(f, source_file="source-b"))
    assert ledger.positions["BTCUSDT"].funding == D(".1")


def test_spot_purchase_can_use_free_futures_cash_through_internal_transfer(rules):
    ledger = Ledger(Config(), "test")
    ledger.transfer(D(10000), 0, "cash-location")
    fill = Fill("f", "o", "BTCUSDT", "spot", "BUY", D(1), D(100), D(100), 1, "t", D(".001"))
    assert ledger.apply_fill(fill, rules.get("BTCUSDT", "spot", 0), D(100))
    assert ledger.free_futures == D(9900)
    assert ledger.free_spot == 0
    assert ledger.reconcile({"BTCUSDT": D(100)}, {})["equity"] == D("9999.9")


def test_accounting_tolerance_does_not_widen_liquidation_threshold(rules):
    rule = rules.get("BTCUSDT", "futures", 0)
    price = liquidation_price(D(1), D(100), D(50), rule)
    assert margin_state(D(1), D(100), D(50), price, rule, Config())["liquidate"]
    assert not margin_state(D(1), D(100), D(50), price - D(".0000000001"), rule, Config())[
        "liquidate"
    ]

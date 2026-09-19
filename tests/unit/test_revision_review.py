"""Independent review regressions for diagnostics and quantity planning."""

from dataclasses import replace
from decimal import Decimal as D
from types import SimpleNamespace

from crypto_carry.config import Config
from crypto_carry.diagnostics import signal_diagnostics
from crypto_carry.forecast import Forecast
from crypto_carry.ledger import Ledger, Position
from crypto_carry.models import Fill, Mark, Trade
from crypto_carry.portfolio import joint_quantity
from crypto_carry.strategy import Backtest


def test_legacy_diagnostics_do_not_invent_a_futures_gate_before_spot_entry(rules, start):
    """Legacy defers futures filters until its second leg; audit must reflect that."""
    symbol = "BTCUSDT"
    rules.items[(symbol, "futures")] = replace(rules.items[(symbol, "futures")], min_qty=D("40"))
    config = Config(sizing_model="legacy", slippage=D("0"))
    backtest = Backtest(config, rules, funding_filter_enabled=False)
    backtest.now = start
    backtest.native = SimpleNamespace(submit=lambda *args: None)
    backtest.forecasts[symbol] = Forecast(
        value=D("0.1"),
        no_change=D("0.1"),
        anchor=start,
        available_at=start,
        history_start=start,
        valid=True,
        reason="",
    )
    for market in ("spot", "futures"):
        backtest.trades[(symbol, market)] = Trade(
            symbol, market, market, start, start, D("100"), D("100")
        )
    backtest.marks[symbol] = Mark(
        symbol,
        start - 60_000_000_000,
        start - 1,
        start,
        D("100"),
        D("100"),
        D("100"),
        D("100"),
    )

    diagnostic = signal_diagnostics(backtest, symbol, D("10000"))
    decision = backtest._entry(symbol, D("10000"))

    assert decision == "accepted"
    assert diagnostic["sequential_rejection"] is None


def test_joint_reduction_can_use_released_collateral_without_free_cash(rules, start):
    """A closing short can pay its fee from the collateral it releases."""
    symbol = "BTCUSDT"
    config = Config(sizing_model="joint_quantity", slippage=D("0"))
    spot_rule = replace(rules.items[(symbol, "spot")], step=D("0.00001"))
    futures_rule = rules.items[(symbol, "futures")]
    ledger = Ledger(config, "review")
    ledger.free_spot = D("0")
    ledger.positions[symbol] = Position(
        spot=D("0.050006"),
        short=D("0.050"),
        average=D("100"),
        collateral=D("2.5"),
        spot_cost=D("5.0006"),
    )
    equity = ledger.equity({symbol: D("100")}, {symbol: D("100")})

    plan = joint_quantity(
        equity,
        D("100"),
        D("100"),
        D("100"),
        ledger.positions[symbol].spot,
        ledger.positions[symbol].short,
        D("0"),
        spot_rule,
        futures_rule,
        config,
        existing_collateral=D("2.5"),
        existing_average=D("100"),
    )

    # Independently demonstrate that the greatest target-compliant reduction
    # fills through the authoritative ledger without debt or extra capital.
    fill = Fill(
        "review-fill",
        "review-order",
        symbol,
        "futures",
        "buy",
        D("0.028"),
        D("100"),
        D("100"),
        start,
        "review-price",
        futures_rule.taker_fee,
    )
    assert ledger.apply_fill(fill, futures_rule, D("100"))
    assert ledger.debt == 0
    assert ledger.free_futures == D("1.39860000")
    assert ledger.positions[symbol].short == D("0.022")
    assert plan.feasible
    assert plan.short_total == D("0.022")

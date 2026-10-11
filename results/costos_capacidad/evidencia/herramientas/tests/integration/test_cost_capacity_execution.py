"""Fixtures execute real native orders and Decimal balances under the eight variants."""

from decimal import Decimal as D
from pathlib import Path

import pytest
from conftest import warmup
from test_next_minute_vwap import bars

from crypto_carry.config import SECOND, Config, iso
from crypto_carry.events import event_key
from crypto_carry.strategy import Backtest
from scripts.cost_capacity import CHANGES, scenario_configs


@pytest.mark.parametrize("scenario", list(CHANGES))
@pytest.mark.parametrize("strategy", ["conditional", "permanent"])
def test_scenario_fees_capacity_and_portfolio_reconcile(start, rules, scenario, strategy):
    base = Config.load(Path(__file__).resolve().parents[2] /
                       "configs/entrega_4/reglas_historicas/BASE_E3.toml")
    config = scenario_configs(base)[scenario].changed(start=iso(start),
                                                     end=iso(start+600*SECOND))
    rows = sorted(warmup(start) + bars(start, base="100"), key=event_key)
    result = Backtest(config, rules, strategy, strategy == "conditional").run(rows)
    assert result.status == "complete"
    assert result.fills
    capacity = {}
    for row in result.fills:
        key = row["symbol"], row["market"], row["window_start"]
        capacity[key] = capacity.get(key, D(0)) + D(row["quantity"])
        assert capacity[key] <= D(100)*config.max_volume_participation
        expected_fee = D(".001") if row["market"] == "spot" else D(".0005")
        assert D(row["fee_rate"]) == expected_fee*config.cost_multiplier
        assert D(row["slippage_rate"]) == config.slippage*config.cost_multiplier
    assert all(D(row["estimated_cycle_cost"]) == D(".0034") for row in result.signals)
    assert abs(result.ledger.reconcile(result.spot_prices(), result.mark_prices())["difference"]) <= D("1E-8")
    reference = Backtest(base.changed(start=config.start, end=config.end), rules,
                         strategy, strategy == "conditional").run(rows)
    assert result.opportunities == reference.opportunities
    if scenario in {"A050", "A100"}:
        submitted = next(r for r in result.order_rows if r["action"] == "submitted")
        old = next(r for r in reference.order_rows if r["action"] == "submitted")
        assert D(submitted["quantity"]) > D(old["quantity"])
        # Same binding cap: executed quantity cannot be scaled from BASE.
        assert D(result.fills[0]["quantity"]) == D(reference.fills[0]["quantity"])

"""Closed block-3 contract: selection cost is distinct from realized friction."""

from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path

import pytest

from crypto_carry.config import Config, timestamp
from crypto_carry.costs import cycle_cost, execution_price
from crypto_carry.data.prescribed import prescribed_rules, research_assumptions
from crypto_carry.diagnostics import signal_diagnostics
from crypto_carry.execution import minute_capacity

BASE = Path(__file__).resolve().parents[2] / "configs/entrega_4/reglas_historicas/BASE_E3.toml"


def base():
    return Config.load(BASE)


@pytest.mark.parametrize("mode", ["realized", "base_e3"])
@pytest.mark.parametrize("mult,slip,wanted", [(2, ".0001", ".0068"),
                                               (3, ".0001", ".0102"),
                                               (1, ".0005", ".0050")])
def test_legacy_coupling_is_preserved(mode, mult, slip, wanted):
    config = base().changed(research_decision_fee_mode=mode,
                            cost_multiplier=D(mult), slippage=D(slip))
    rules = prescribed_rules(config)
    assert cycle_cost(rules.get("BTCUSDT", "spot", timestamp(config.start)),
                      rules.get("BTCUSDT", "futures", timestamp(config.start)), config) == D(wanted)


@pytest.mark.parametrize("mult,slip,price,fee", [
    (1, ".0001", "100.01", ".001"), (2, ".0001", "100.02", ".002"),
    (3, ".0001", "100.03", ".003"), (1, ".0002", "100.02", ".001"),
    (1, ".0005", "100.05", ".001"),
])
def test_fixed_selection_leaves_execution_costs_live(mult, slip, price, fee):
    config = base().changed(research_decision_fee_mode="base_e3_total",
                            cost_multiplier=D(mult), slippage=D(slip))
    rules = prescribed_rules(config)
    spot = rules.get("BTCUSDT", "spot", timestamp(config.start))
    future = rules.get("BTCUSDT", "futures", timestamp(config.start))
    assert cycle_cost(spot, future, config) == D(".0034")
    assert spot.taker_fee * config.cost_multiplier == D(fee)
    assert future.taker_fee * config.cost_multiplier == D(fee)/2
    assert execution_price(D(100), "buy", replace(spot, tick=D(".01")), config)[0] == D(price)
    assert execution_price(D(100), "sell", replace(spot, tick=D(".01")), config)[0] == 200-D(price)
    assert execution_price(D("100.001"), "buy", replace(spot, tick=D(".1")), config)[0] == D("100.1")
    assert future.liquidation_fee == D(".0125")
    assert Config.from_dict(config.to_dict()) == config


def test_new_mode_is_research_only_and_default_digest_is_unchanged():
    with pytest.raises(ValueError, match="prescribed_research"):
        Config(research_decision_fee_mode="base_e3_total")
    assert "research_decision_fee_mode" not in base().to_dict()
    assert base().digest() == Config.from_dict(base().to_dict()).digest()


def test_diagnostic_components_explain_34bp_and_scenario_is_separate():
    from test_diagnostics import FakeBacktest

    backtest = FakeBacktest()
    backtest.config = base().changed(cost_multiplier=D(2),
                                    research_decision_fee_mode="base_e3_total")
    row = signal_diagnostics(backtest, "BTCUSDT", D(10000))
    fields = ("cost_spot_open_fee", "cost_spot_close_fee", "cost_futures_open_fee",
              "cost_futures_close_fee", "cost_slippage_total")
    assert sum(D(row[k]) for k in fields) == D(row["estimated_cycle_cost"]) == D(".0034")
    assert D(row["scenario_spot_taker_fee"]) == D(".002")
    assert D(row["scenario_futures_taker_fee"]) == D(".001")
    assert D(row["scenario_slippage_per_order"]) == D(".0002")
    assert row["decision_fee_mode"] == "base_e3_total"
    assert research_assumptions(backtest.config)["fee_sensitivity"]["selection_cost"] == "0.0034"


@pytest.mark.parametrize("forecast,entry", [(".0034", "fail"), (".00340001", "pass")])
def test_diagnostic_strict_entry_boundary(forecast, entry):
    from test_diagnostics import FakeBacktest

    backtest = FakeBacktest()
    backtest.config = base().changed(cost_multiplier=D(3),
                                    research_decision_fee_mode="base_e3_total")
    backtest.forecasts["BTCUSDT"] = replace(backtest.forecasts["BTCUSDT"], value=D(forecast))
    assert signal_diagnostics(backtest, "BTCUSDT", D(10000))["filter_funding"] == entry


def test_shared_capacity_rounds_remaining_budget_and_zero_volume():
    assert minute_capacity(D(".4"), D(100), D(".1"), D(".005"), D(".3")) == D(".2")
    assert minute_capacity(D(".4"), D(100), D(".1"), D(".005"), D(".5")) == 0
    assert minute_capacity(D(1), D(0), D(".1"), D(".005")) == 0


def test_spot_base_fee_numeric_contract_and_liquidation_charge_unscaled():
    from test_finance import fill, rule

    from crypto_carry.ledger import Ledger

    ledger = Ledger(base().changed(cost_multiplier=D(2),
                                  research_decision_fee_mode="base_e3_total"), "conditional")
    assert ledger.apply_fill(fill("buy", "spot", "buy", "1", "1000", fee=".002"),
                             rule("spot", fee=".001"), D(1000))
    position = ledger.positions["BTCUSDT"]
    assert position.spot == D(".998")
    assert position.fees == D(2)
    assert ledger.free_spot == D(9000)
    assert ledger.rows[-1]["base_fee_quantity"] == D("0.002")
    for multiplier in (1, 2, 3):
        ledger = Ledger(base().changed(cost_multiplier=D(multiplier)), "conditional")
        future = rule("futures", fee=".0005", liquidation_fee=".0125")
        fee = str(D(".0005")*multiplier)
        assert ledger.apply_fill(fill("open", "futures", "sell", "1", "1000", fee=fee),
                                 future, D(1000))
        assert ledger.apply_fill(fill("close", "futures", "buy", "1", "1000", fee=fee,
                                      liquidation=True), future, D(1000))
        assert ledger.positions["BTCUSDT"].liquidation_fees == D("12.5")
        assert ledger.positions["BTCUSDT"].fees == D(multiplier)


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("value,wanted", [("0", "fail"), (".0001", "pass")])
def test_new_cost_mode_preserves_renewal_contract(enabled, value, wanted):
    from test_diagnostics import FakeBacktest

    from crypto_carry.diagnostics import renewal_diagnostics
    from crypto_carry.models import State

    backtest = FakeBacktest(funding_filter_enabled=enabled)
    backtest.config = base().changed(cost_multiplier=D(3),
                                    research_decision_fee_mode="base_e3_total")
    backtest.pairs["BTCUSDT"].state = State.HOLDING
    backtest.forecasts["BTCUSDT"] = replace(backtest.forecasts["BTCUSDT"], value=D(value))
    row = renewal_diagnostics(backtest, "BTCUSDT", D(10000))
    assert row["filter_funding_positive"] == wanted
    assert row["entry_funding_cost_filter_applied"] is False
    assert row["funding_filter_enabled"] is enabled


def test_closed_matrix_rejects_crosses_and_preserves_every_other_field():
    from scripts.cost_capacity import CHANGES, scenario_configs, validate_variant

    configs = scenario_configs(base())
    assert set(configs) == {"C02", "C03", "S02", "S05", "P050", "P025", "A050", "A100"}
    for name, config in configs.items():
        assert validate_variant(base(), name, config)
        for key, value in base().to_dict().items():
            if key not in CHANGES[name]:
                assert config.to_dict()[key] == value
        with pytest.raises(ValueError, match="Unauthorized"):
            validate_variant(base(), name, config.changed(half_life_hours=48))
    with pytest.raises(ValueError, match="Unauthorized"):
        validate_variant(base(), "C03", configs["C03"].changed(capital=D(100000)))
    for name in ("P050", "P025", "A050", "A100"):
        assert configs[name].research_decision_fee_mode == "realized"

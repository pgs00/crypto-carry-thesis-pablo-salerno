import json
from collections import defaultdict
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

from crypto_carry.config import Config
from crypto_carry.diagnostics import renewal_diagnostics, signal_diagnostics
from crypto_carry.forecast import Forecast
from crypto_carry.ledger import Position
from crypto_carry.models import Mark, MarketRule, Pair, State, Trade

D = Decimal


def rule(market: str, *, fee: str, step: str) -> MarketRule:
    return MarketRule(
        symbol="BTCUSDT",
        market=market,
        step=D(step),
        tick=D("0.01"),
        min_qty=D(step),
        max_qty=D("1000"),
        min_notional=D("0"),
        max_notional=D("1000000"),
        taker_fee=D(fee),
    )


class FakeBacktest:
    def __init__(
        self, *, funding_filter_enabled: bool = True, sizing_model: str = "joint_quantity"
    ):
        self.now = 1_000
        self.config = Config(sizing_model=sizing_model, slippage=D("0"))
        self.funding_filter_enabled = funding_filter_enabled
        self.status = "complete"
        self.bad_symbols = set()
        self.forecasts = {
            "BTCUSDT": Forecast(
                value=D("0.001"),
                no_change=D("0.002"),
                anchor=900,
                available_at=950,
                history_start=100,
                valid=True,
                reason="",
            )
        }
        self.history = defaultdict(list)
        self.pairs = {"BTCUSDT": Pair(state=State.FLAT, cooldown_until=0)}
        self.ledger = SimpleNamespace(
            positions={"BTCUSDT": Position()},
            free_spot=D("100"),
            free_futures=D("0"),
            debt=D("0"),
        )
        self.reservations = defaultdict(lambda: D(0))
        self.orders = {}
        self.marks = {
            "BTCUSDT": Mark(
                symbol="BTCUSDT",
                open_time=800,
                close_time=900,
                available_at=900,
                open=D("100"),
                high=D("101"),
                low=D("99"),
                close=D("100"),
            )
        }
        self._rules = {
            "spot": rule("spot", fee="0.001", step="0.00001"),
            "futures": rule("futures", fee="0.0005", step="0.001"),
        }
        self._prices = (
            Trade("BTCUSDT", "spot", "s", 900, 900, D("100"), D("1")),
            Trade("BTCUSDT", "futures", "f", 900, 900, D("99"), D("1")),
        )
        self.trades = {
            ("BTCUSDT", "spot"): self._prices[0],
            ("BTCUSDT", "futures"): self._prices[1],
        }
        self.closed_signals = False
        self.fresh = True
        self.required_calls: list[tuple[str, Decimal]] = []

    def _signal_prices(self, symbol: str):
        return self._prices

    def _rule(self, symbol: str, market: str):
        return self._rules.get(market)

    def _fresh(self, symbol: str) -> bool:
        return self.fresh and self._prices[0] is not None and self._prices[1] is not None

    def _uses_closed_signals(self) -> bool:
        return self.closed_signals

    def _data_valid(self, symbol: str) -> bool:
        return (
            symbol not in self.bad_symbols
            and symbol in self.marks
            and self._fresh(symbol)
            and all(rule is not None and rule.operational for rule in self._rules.values())
        )

    def _available(self, symbol: str) -> Decimal:
        return self.ledger.free_spot + self.ledger.free_futures

    def _pending(self, symbol: str) -> list:
        return []

    def _required(self, symbol: str, quantity: Decimal) -> Decimal:
        self.required_calls.append((symbol, quantity))
        return D("42")


def test_signal_diagnostics_keeps_simultaneous_funding_and_basis_failures() -> None:
    backtest = FakeBacktest()

    row = signal_diagnostics(backtest, "BTCUSDT", D("13.1"))

    assert row["filter_funding"] == "fail"
    assert row["filter_basis_negative"] == "fail"
    assert row["filter_basis_above_max"] == "pass"
    assert json.loads(row["simultaneous_rejections"]) == ["funding", "basis_negative"]
    assert row["sequential_rejection"] == "funding"
    assert row["forecast"] == "0.001"
    assert row["estimated_cycle_cost"] == "0.0030"
    assert row["forecast_cost_gap"] == "-0.0020"
    assert row["spot_price_time"] == 900
    assert row["futures_price_time"] == 900
    assert row["basis"] == "-0.01"
    assert row["sizing_feasible"] is True
    assert row["proposed_gross_spot"] == "0.03904"
    assert row["proposed_net_spot"] == "0.03900096"
    assert row["proposed_short"] == "0.039"


def test_disabled_funding_filter_keeps_economic_status_but_skips_it_sequentially() -> None:
    backtest = FakeBacktest(funding_filter_enabled=False)

    row = signal_diagnostics(backtest, "BTCUSDT", D("13.1"))

    assert row["funding_filter_enabled"] is False
    assert row["filter_funding"] == "fail"
    assert row["sequential_rejection"] == "basis_negative"


def test_missing_inputs_are_not_evaluable_and_not_economic_failures() -> None:
    backtest = FakeBacktest()
    backtest.forecasts.clear()
    backtest._prices = (None, None)
    backtest._rules.clear()
    backtest.marks.clear()

    row = signal_diagnostics(backtest, "BTCUSDT", D("13.1"))

    assert row["filter_forecast"] == "not_evaluable"
    assert row["filter_rules"] == "not_evaluable"
    assert row["filter_price_alignment"] == "not_evaluable"
    assert row["filter_freshness"] == "not_evaluable"
    assert row["filter_funding"] == "not_evaluable"
    assert row["filter_basis_negative"] == "not_evaluable"
    assert row["filter_sizing"] == "not_evaluable"
    assert json.loads(row["simultaneous_rejections"]) == []
    assert row["sequential_rejection"] == "not_evaluable:forecast"
    assert row["forecast"] is None
    assert row["basis"] is None
    assert row["sizing_feasible"] is None


def test_state_and_cooldown_are_distinct_filters() -> None:
    backtest = FakeBacktest()
    backtest.pairs["BTCUSDT"].state = State.HOLDING
    backtest.pairs["BTCUSDT"].cooldown_until = 2_000

    row = signal_diagnostics(backtest, "BTCUSDT", D("13.1"))

    assert row["filter_state_active"] == "fail"
    assert row["filter_cooldown"] == "fail"
    assert row["portfolio_state"] == "HOLDING"
    assert row["cooldown_until"] == 2_000
    assert json.loads(row["simultaneous_rejections"])[:2] == ["state_active", "cooldown"]


def test_legacy_diagnostics_use_the_engine_target_and_required_cash_paths() -> None:
    backtest = FakeBacktest(sizing_model="legacy")
    backtest._prices = (
        Trade("BTCUSDT", "spot", "s", 900, 900, D("100"), D("1")),
        Trade("BTCUSDT", "futures", "f", 900, 900, D("100"), D("1")),
    )
    backtest.trades = {
        ("BTCUSDT", "spot"): backtest._prices[0],
        ("BTCUSDT", "futures"): backtest._prices[1],
    }

    row = signal_diagnostics(backtest, "BTCUSDT", D("13.1"))

    assert backtest.required_calls == [("BTCUSDT", D("0.03930"))]
    assert row["target_quantity"] == "0.0393"
    assert row["proposed_gross_spot"] == "0.0393"
    assert row["budget_required_cash"] == "42"
    assert row["filter_budget"] == "pass"


def test_legacy_entry_gate_defers_prospective_futures_failure() -> None:
    backtest = FakeBacktest(sizing_model="legacy", funding_filter_enabled=False)
    backtest._rules["futures"] = replace(backtest._rules["futures"], min_qty=D("40"))
    backtest._prices = (
        Trade("BTCUSDT", "spot", "s", 900, 900, D("100"), D("1")),
        Trade("BTCUSDT", "futures", "f", 900, 900, D("100"), D("1")),
    )
    backtest.trades = {
        ("BTCUSDT", "spot"): backtest._prices[0],
        ("BTCUSDT", "futures"): backtest._prices[1],
    }

    row = signal_diagnostics(backtest, "BTCUSDT", D("10000"))

    assert row["filter_sizing"] == "pass"
    assert row["filter_budget"] == "pass"
    assert row["sequential_rejection"] is None
    assert row["sizing_feasible"] is True
    assert row["sizing_enforcement"] == "spot_entry_only"
    assert row["prospective_pair_feasible"] is False
    assert row["prospective_sizing_reason"] == "futures_quantity_filter"


def test_diagnostics_do_not_consume_future_forecasts_prices_or_funding() -> None:
    backtest = FakeBacktest()
    backtest.forecasts["BTCUSDT"] = Forecast(
        value=D("9"),
        no_change=D("8"),
        anchor=1_100,
        available_at=1_100,
        history_start=100,
        valid=True,
        reason="future forecast must stay hidden",
    )
    backtest._prices = (
        Trade("BTCUSDT", "spot", "future-s", 1_100, 1_100, D("999"), D("1")),
        Trade("BTCUSDT", "futures", "future-f", 1_100, 1_100, D("998"), D("1")),
    )
    backtest.history["BTCUSDT"] = [
        SimpleNamespace(funding_time=900, available_at=950),
        SimpleNamespace(funding_time=1_100, available_at=1_100),
    ]

    row = signal_diagnostics(backtest, "BTCUSDT", D("13.1"))

    assert row["forecast"] is None
    assert row["forecast_reason"] == "unavailable"
    assert row["spot_price"] is None
    assert row["futures_price"] is None
    assert row["latest_funding_time"] == 900
    assert row["latest_funding_available_at"] == 950


def test_budget_rejection_keeps_the_structurally_valid_proposed_quantities() -> None:
    backtest = FakeBacktest()
    backtest.ledger.free_spot = D("0")

    row = signal_diagnostics(backtest, "BTCUSDT", D("13.1"))

    assert row["sizing_feasible"] is False
    assert row["sizing_reason"] == "insufficient_cash"
    assert row["filter_sizing"] == "pass"
    assert row["filter_budget"] == "fail"
    assert row["proposed_gross_spot"] == "0.03904"
    assert row["proposed_net_spot"] == "0.03900096"
    assert row["proposed_short"] == "0.039"
    assert D(row["budget_required_cash"]) > 0


def test_closed_policy_does_not_classify_stale_misaligned_basis_as_economic_failure() -> None:
    backtest = FakeBacktest(funding_filter_enabled=False)
    backtest.closed_signals = True
    backtest.fresh = False
    backtest._prices = (
        Trade("BTCUSDT", "spot", "closed-s", 900, 900, D("100"), D("1")),
        Trade("BTCUSDT", "futures", "closed-f", 800, 800, D("99"), D("1")),
    )

    row = signal_diagnostics(backtest, "BTCUSDT", D("13.1"))

    assert row["filter_price_alignment"] == "fail"
    assert row["filter_freshness"] == "fail"
    assert row["basis_raw"] == "-0.01"
    assert row["basis"] is None
    assert row["filter_basis_negative"] == "not_evaluable"
    assert "basis_negative" not in json.loads(row["simultaneous_rejections"])
    assert row["sequential_rejection"] == "price_alignment"


def test_legacy_policy_audits_alignment_without_using_it_as_a_sequential_gate() -> None:
    backtest = FakeBacktest(funding_filter_enabled=False)
    backtest._prices = (
        Trade("BTCUSDT", "spot", "legacy-s", 900, 900, D("100"), D("1")),
        Trade("BTCUSDT", "futures", "legacy-f", 800, 800, D("99"), D("1")),
    )

    row = signal_diagnostics(backtest, "BTCUSDT", D("13.1"))

    assert row["price_alignment_enforced"] is False
    assert row["filter_price_alignment"] == "fail"
    assert row["basis"] == "-0.01"
    assert row["sequential_rejection"] == "basis_negative"


def test_legacy_proposal_uses_engine_sizing_prices_not_closed_basis_references() -> None:
    backtest = FakeBacktest(sizing_model="legacy")
    backtest._prices = (
        Trade("BTCUSDT", "spot", "closed-s", 900, 900, D("200"), D("1")),
        Trade("BTCUSDT", "futures", "closed-f", 900, 900, D("200"), D("1")),
    )
    backtest.trades = {
        ("BTCUSDT", "spot"): Trade("BTCUSDT", "spot", "open-s", 900, 900, D("100"), D("1")),
        ("BTCUSDT", "futures"): Trade("BTCUSDT", "futures", "open-f", 900, 900, D("100"), D("1")),
    }

    row = signal_diagnostics(backtest, "BTCUSDT", D("13.1"))

    assert row["spot_price"] == "200"
    assert row["sizing_spot_price"] == "100"
    assert row["sizing_futures_price"] == "100"
    assert row["target_quantity"] == "0.0393"


def test_bad_symbol_coverage_is_not_evaluable_instead_of_an_economic_failure() -> None:
    backtest = FakeBacktest()
    backtest.bad_symbols.add("BTCUSDT")

    row = signal_diagnostics(backtest, "BTCUSDT", D("13.1"))

    assert row["filter_coverage"] == "not_evaluable"
    assert row["sequential_rejection"] == "not_evaluable:coverage"
    assert "coverage" not in json.loads(row["simultaneous_rejections"])


def test_invalid_forecast_preserves_observed_values_but_is_not_evaluable() -> None:
    backtest = FakeBacktest()
    backtest.forecasts["BTCUSDT"] = Forecast(
        value=D("0.123"),
        no_change=D("0.456"),
        anchor=900,
        available_at=950,
        history_start=100,
        valid=False,
        reason="window gap",
    )

    row = signal_diagnostics(backtest, "BTCUSDT", D("13.1"))

    assert row["forecast"] == "0.123"
    assert row["forecast_no_change"] == "0.456"
    assert row["filter_forecast"] == "not_evaluable"
    assert row["filter_funding"] == "not_evaluable"


def test_nonpositive_equity_and_negative_available_cash_are_diagnostic_rejections() -> None:
    backtest = FakeBacktest()
    equity_row = signal_diagnostics(backtest, "BTCUSDT", D("0"))

    assert equity_row["sizing_feasible"] is False
    assert equity_row["sizing_reason"] == "nonpositive_equity"
    assert equity_row["filter_budget"] == "fail"
    assert equity_row["proposed_gross_spot"] == "0"

    backtest.ledger.free_spot = D("-1")
    cash_row = signal_diagnostics(backtest, "BTCUSDT", D("13.1"))

    assert cash_row["sizing_feasible"] is False
    assert cash_row["sizing_reason"] == "negative_available_cash"
    assert cash_row["filter_budget"] == "fail"
    assert cash_row["available_cash"] == "-1"


def test_renewal_uses_positive_funding_without_entry_cost_or_basis_filters() -> None:
    backtest = FakeBacktest()
    backtest.pairs["BTCUSDT"].state = State.HOLDING

    row = renewal_diagnostics(backtest, "BTCUSDT", D("13.1"))

    assert row["decision_kind"] == "renewal"
    assert json.loads(row["filter_order"]) == [
        "state_holding",
        "data_valid",
        "forecast",
        "debt",
        "funding_positive",
    ]
    assert row["renewal_funding_threshold"] == "0"
    assert row["filter_state_holding"] == "pass"
    assert row["filter_funding_positive"] == "pass"
    assert row["sequential_rejection"] is None
    assert row["renewal_status_kind"] == "eligible"
    assert row["filter_funding"] == "fail"
    assert row["filter_basis_negative"] == "fail"
    assert row["entry_funding_cost_filter_applied"] is False
    assert row["entry_basis_filter_applied"] is False
    assert row["entry_sizing_filter_applied"] is False


def test_renewal_nonholding_state_is_recorded_as_a_state_skip() -> None:
    backtest = FakeBacktest()
    backtest.pairs["BTCUSDT"].state = State.REBALANCING

    row = renewal_diagnostics(backtest, "BTCUSDT", D("13.1"))

    assert row["filter_state_holding"] == "fail"
    assert row["sequential_rejection"] == "state_holding"
    assert row["renewal_status_kind"] == "skipped_not_holding"

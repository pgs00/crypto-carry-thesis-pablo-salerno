"""Opt-in fee execution through the native adapter and the actual ledger."""

from decimal import Decimal as D
from pathlib import Path

import pytest
from conftest import warmup

from crypto_carry.config import SECOND, Config, iso, timestamp
from crypto_carry.data.prescribed import prescribed_rules
from crypto_carry.events import event_key
from crypto_carry.models import Funding, Mark, MinuteBar
from crypto_carry.strategy import Backtest

ROOT = Path(__file__).resolve().parents[2]


def execute(name, start, *, rate=".001", strategy="conditional", extra=()):
    config = Config.load(ROOT / "configs/entrega_4/reglas_historicas" / f"{name}.toml")
    config = config.changed(start=iso(start), end=iso(start + 600 * SECOND))
    rows = warmup(start, rate=rate) + list(extra)
    for offset in range(0, 601, 60):
        end = start + offset * SECOND
        for symbol in config.symbols:
            for market, price in (("spot", D(100)), ("futures", D("100.3"))):
                rows.append(MinuteBar(
                    symbol, market, end - 60 * SECOND, end, end,
                    price, price, price, price, D(100000), D(100000) * price,
                    100, "synthetic:fee-boundary-test",
                ))
            rows.append(Mark(symbol, end - 60 * SECOND, end - 1, end,
                             D("100.3"), D("100.3"), D("100.3"), D("100.3")))
    return Backtest(config, prescribed_rules(config), strategy, strategy == "conditional").run(
        sorted(rows, key=event_key)
    )


@pytest.mark.parametrize("boundary,offset,want", [
    ("2022-07-08T14:00:00Z", -120, ".001"),
    ("2022-07-08T14:00:00Z", -60, "0"),
    ("2023-03-22T00:00:00Z", -120, "0"),
    ("2023-03-22T00:00:00Z", -60, ".001"),
])
def test_minute_fee_uses_window_start_while_booking_at_close(boundary, offset, want):
    start = timestamp(boundary) + offset * SECOND
    result = execute("BTC_PROMO_REALIZADA", start)
    btc = [f for f in result.fills if f["symbol"] == "BTCUSDT" and f["market"] == "spot"]
    assert btc and btc[0]["time_ns"] == start + 120 * SECOND
    assert btc[0]["window_start"] == start + 60 * SECOND
    assert D(btc[0]["fee_rate"]) == D(want)
    p = result.ledger.positions["BTCUSDT"]
    assert p.spot == D(btc[0]["quantity"]) * (1 - D(want))
    assert result.native_fill_count == len(result.fills)
    assert abs(result.ledger.reconcile(result.spot_prices(), result.mark_prices())["difference"]) < D("1e-8")


def test_lower_decision_threshold_changes_entry_without_changing_eth_or_forecast():
    start = timestamp("2022-08-01T00:00:00Z")
    realized = execute("BTC_PROMO_REALIZADA", start, rate=".0001")
    decision = execute("BTC_PROMO_DECISION", start, rate=".0001")
    assert not realized.fills
    assert {f["symbol"] for f in decision.fills} == {"BTCUSDT"}
    assert [s["forecast"] for s in realized.signals] == [s["forecast"] for s in decision.signals]
    costs = {s["symbol"]: D(s["estimated_cycle_cost"]) for s in decision.signals}
    assert costs == {"BTCUSDT": D(".0014"), "ETHUSDT": D(".0034")}
    assert D(decision.fills[0]["fee_rate"]) == 0


def test_opportunity_is_independent_of_portfolio_cash_and_positions():
    start = timestamp("2022-08-01T00:00:00Z")
    conditional = execute("BTC_PROMO_REALIZADA", start, rate=".0001")
    permanent = execute("BTC_PROMO_REALIZADA", start, rate=".0001", strategy="permanent")
    assert not conditional.fills and permanent.fills
    assert conditional.opportunities == permanent.opportunities


def test_funding_boundary_precedes_new_short_and_fees_are_charged_once():
    start = timestamp("2022-08-01T00:00:00Z")
    funding = Funding("BTCUSDT", start + 180 * SECOND, start + 180 * SECOND,
                      D(".001"), D(8), D("100.3"), "synthetic:fee-test", True)
    result = execute("BTC_PROMO_REALIZADA", start, extra=[funding])
    assert result.ledger.positions["BTCUSDT"].funding == 0  # Short fills after settlement.
    btc = [f for f in result.fills if f["symbol"] == "BTCUSDT"]
    assert [(f["market"], f["side"]) for f in btc] == [("spot", "BUY"), ("futures", "SELL")]
    fee = D(btc[1]["quantity"]) * D(btc[1]["price"]) * D(".0005")
    assert result.ledger.positions["BTCUSDT"].fees == fee
    assert result.native_fill_count == len(result.fills)

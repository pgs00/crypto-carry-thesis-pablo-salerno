"""Actual 72/336-hour expiry clocks using the original next-minute engine."""

from decimal import Decimal as D
from pathlib import Path

import pytest
from conftest import warmup

from crypto_carry.config import HOUR, SECOND, Config, iso
from crypto_carry.costs import cycle_cost
from crypto_carry.events import event_key
from crypto_carry.models import Funding, Mark, MinuteBar, State
from crypto_carry.strategy import Backtest


@pytest.mark.parametrize("horizon", [72, 336])
@pytest.mark.parametrize("strategy", ["conditional", "permanent"])
@pytest.mark.parametrize("risk_at_expiry", [False, True])
def test_horizon_opens_and_renews_on_its_clock_with_fixed_cycle_cost(start, rules, horizon, strategy, risk_at_expiry):
    base = Config.load(Path(__file__).resolve().parents[2] /
                       "configs/entrega_4/reglas_historicas/BASE_E3.toml")
    seconds = (horizon + 1) * 3600
    config = base.changed(start=iso(start), end=iso(start + seconds * SECOND),
                          horizon_hours=horizon, holding_hours=horizon)
    rows = warmup(start)
    for second in range(0, seconds + 1, 60):
        end = start + second * SECOND
        future = D("103") if risk_at_expiry and end >= start+180*SECOND+horizon*HOUR else D("100.3")
        for symbol in config.symbols:
            for market, price in (("spot", D(100)), ("futures", future)):
                rows.append(MinuteBar(symbol, market, end-60*SECOND, end, end,
                                     price, price, price, price, D(100000),
                                     D(100000)*price, 100, "synthetic"))
            rows.append(Mark(symbol, end-60*SECOND, end-1, end,
                             future, future, future, future))
    rows.extend(Funding(symbol, start+h*HOUR, start+h*HOUR+60*SECOND,
                        D(".000001"), D(8), D("100.3"), "synthetic", True)
                for h in range(8, horizon+1, 8) for symbol in config.symbols)
    result = Backtest(config, rules, strategy, strategy == "conditional").run(
        sorted(rows, key=event_key))
    assert result.status == "complete"
    assert len(result.fills) == (8 if risk_at_expiry else 4)
    cost = cycle_cost(rules.get("BTCUSDT", "spot", start),
                      rules.get("BTCUSDT", "futures", start), config)
    assert cost == D(".0034")
    if risk_at_expiry:
        assert not [r for r in result.risk_events if r["kind"] == "renewal"]
        closes = [r for r in result.risk_events if r["kind"] == "close_requested"]
        # Repeated risk requests are not additional cycles or executed closures.
        assert {r["symbol"] for r in closes} == set(config.symbols)
        assert all(min(r["time_ns"] for r in closes if r["symbol"] == symbol)
                   == start+180*SECOND+horizon*HOUR for symbol in config.symbols)
        assert all(result.ledger.positions[s].short == 0 for s in config.symbols)
        return
    for symbol in config.symbols:
        pair = result.pairs[symbol]
        assert pair.state == State.HOLDING
        assert pair.opened_at == start + 180 * SECOND
        assert pair.expiry == pair.opened_at + 2 * horizon * HOUR
        assert D(0) < result.forecasts[symbol].value < cost
    assert len([r for r in result.risk_events if r["kind"] == "renewal"]) == 2
    assert result.now == start + seconds * SECOND - 1
    assert abs(result.ledger.reconcile(result.spot_prices(), result.mark_prices())["difference"]) <= D("1E-8")

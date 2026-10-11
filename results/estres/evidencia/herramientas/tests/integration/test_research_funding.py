from decimal import Decimal as D

from conftest import prices, warmup

from crypto_carry.config import SECOND, Config, iso
from crypto_carry.events import event_key
from crypto_carry.models import Funding
from crypto_carry.strategy import Backtest


def test_native_replay_uses_simultaneous_closed_candle_and_charges_proxy_once(start, rules):
    config = Config(
        start=iso(start),
        end=iso(start + 180 * SECOND),
        analysis_mode="prescribed_research",
        fee_profile="prescribed_fixed_no_discounts",
        funding_proxy_stress_bps=D(10),
    )
    event = Funding(
        "BTCUSDT", start + 120 * SECOND, start + 180 * SECOND, D(".001"), D(8), None, "rates", True
    )
    rows = warmup(start) + prices(start, [0, 60, 61, 62, 63, 120], mark="100.3") + [event, event]
    backtest = Backtest(config, rules).run(sorted(rows, key=event_key))
    resolved = [f for f in backtest.all_funding if f.funding_time == event.funding_time]
    assert len(resolved) == 1
    assert resolved[0].settlement_mark_price == D("100.1997")
    position = backtest.ledger.positions["BTCUSDT"]
    assert position.short > 0
    assert position.funding == position.short * D("100.1997") * D(".001")
    assert len(backtest.ledger.funding_rows) == 1
    assert backtest.status == "complete"
    assert backtest.native_fill_count == 4
    assert (
        backtest.ledger.reconcile(backtest.spot_prices(), backtest.mark_prices())["difference"] == 0
    )


def test_proxy_checkpoint_keeps_provenance_and_does_not_charge_again(start, rules, tmp_path):
    config = Config(
        start=iso(start),
        end=iso(start + 300 * SECOND),
        analysis_mode="prescribed_research",
        fee_profile="prescribed_fixed_no_discounts",
    )
    events = [
        Funding(
            "BTCUSDT",
            start + t * SECOND,
            start + (t + 60) * SECOND,
            D(".001"),
            D(8),
            None,
            "rates",
            True,
        )
        for t in (120, 240)
    ]
    rows = sorted(
        warmup(start) + prices(start, [0, 60, 61, 62, 63, 120, 180, 240], mark="100.3") + events,
        key=event_key,
    )
    whole = Backtest(config, rules).run(rows)
    part = Backtest(config, rules).run(rows, stop_at=start + 180 * SECOND)
    path = tmp_path / "research-checkpoint.json"
    part.checkpoint(path)
    restored = Backtest.load_checkpoint(path, config, rules).run(rows)
    assert restored.ledger.funding_rows == whole.ledger.funding_rows
    assert restored.ledger.rows == whole.ledger.rows
    assert restored.all_funding == whole.all_funding
    assert len(restored.ledger.funding_rows) == 2

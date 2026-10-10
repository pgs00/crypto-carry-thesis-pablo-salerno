"""Minute execution has an explicit clock and never borrows future bar volume."""

from dataclasses import asdict, replace
from decimal import Decimal as D

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import prices, warmup

from crypto_carry import models
from crypto_carry.config import HOUR, SECOND, Config, iso
from crypto_carry.data.replay import _records
from crypto_carry.events import event_key
from crypto_carry.models import Funding, Mark, State
from crypto_carry.serialization import decode, encode
from crypto_carry.strategy import Backtest


def _types():
    assert hasattr(models, "MinutePrice"), "Explicit minute event contracts are not implemented"
    return models.MinutePrice, models.MinuteVolume


def _config(start, seconds=240, **changes):
    return Config(
        start=iso(start),
        end=iso(start + seconds * SECOND),
        analysis_mode="prescribed_research",
        fee_profile="prescribed_fixed_no_discounts",
        execution_model="minute_open",
        order_timeout_seconds=120,
    ).changed(**changes)


def _bars(start, seconds, quantity="5"):
    price_type, volume_type = _types()
    rows = []
    for offset in seconds:
        now = start + offset * SECOND
        for symbol in Config().symbols:
            for market, price in (("spot", "100"), ("futures", "100.3")):
                rows.append(
                    price_type(
                        symbol,
                        market,
                        f"bar:{symbol}:{market}:{now}",
                        now,
                        now,
                        D(price),
                        "synthetic:minute-test",
                    )
                )
                rows.append(
                    volume_type(
                        symbol,
                        market,
                        now - 60 * SECOND,
                        now - 1_000_000,
                        now,
                        D(quantity),
                        10,
                        "synthetic:minute-test",
                    )
                )
            rows.append(
                Mark(
                    symbol,
                    now - 60 * SECOND,
                    now - 1_000_000,
                    now,
                    D("100.3"),
                    D("100.3"),
                    D("100.3"),
                    D("100.3"),
                )
            )
    return rows


def test_minute_config_cannot_claim_strict_history_or_timeout_before_next_quote():
    with pytest.raises(ValueError, match="prescribed_research"):
        Config(execution_model="minute_open", order_timeout_seconds=120)
    with pytest.raises(ValueError, match="60"):
        Config(
            execution_model="minute_open",
            order_timeout_seconds=60,
            analysis_mode="prescribed_research",
            fee_profile="prescribed_fixed_no_discounts",
        )


def test_minute_legs_wait_for_strictly_later_opens_and_reconcile(start, rules):
    rows = warmup(start) + _bars(start, [0, 60, 120, 180])
    result = Backtest(_config(start), rules).run(sorted(rows, key=event_key))
    fills = [fill for fill in result.fills if fill["symbol"] == "BTCUSDT"]
    assert [(fill["market"], fill["time_ns"] - start) for fill in fills] == [
        ("spot", 120 * SECOND),
        ("futures", 180 * SECOND),
    ]
    assert all(fill["trade_id"].startswith("bar:") for fill in fills)
    assert D(fills[0]["recent_volume_quantity"]) == 5
    assert result.pairs["BTCUSDT"].state == State.HOLDING
    assert result.native_fill_count == len(result.fills)
    assert result.ledger.reconcile(result.spot_prices(), result.mark_prices())["difference"] == 0


def test_future_closed_volume_does_not_change_submitted_order_or_fill(start, rules):
    _, volume_type = _types()
    rows = warmup(start) + _bars(start, [0, 60, 120, 180])
    changed = [
        replace(row, quantity=D("999999"))
        if isinstance(row, volume_type) and row.available_at > start + 60 * SECOND
        else row
        for row in rows
    ]
    before = Backtest(_config(start), rules).run(sorted(rows, key=event_key))
    after = Backtest(_config(start), rules).run(sorted(changed, key=event_key))
    assert before.fills[:2] == after.fills[:2]
    assert [o for o in before.order_rows if o["submitted_at"] == start + 60 * SECOND] == [
        o for o in after.order_rows if o["submitted_at"] == start + 60 * SECOND
    ]


def test_minute_checkpoint_between_legs_matches_continuous_run(start, rules, tmp_path):
    config = _config(start)
    rows = sorted(warmup(start) + _bars(start, [0, 60, 120, 180]), key=event_key)
    whole = Backtest(config, rules).run(rows)
    partial = Backtest(config, rules).run(rows, stop_at=start + 120 * SECOND)
    path = tmp_path / "minute-checkpoint.json"
    partial.checkpoint(path)
    restored = Backtest.load_checkpoint(path, config, rules).run(rows)
    assert restored.fills == whole.fills
    assert restored.ledger.rows == whole.ledger.rows
    assert restored.durations == whole.durations
    assert restored.native_fill_count == whole.native_fill_count
    assert restored.native_reconciliation_count == whole.native_reconciliation_count
    assert restored.orders == whole.orders
    assert restored.pairs == whole.pairs
    assert restored.positions == whole.positions
    assert restored.order_rows == whole.order_rows
    assert restored.signals == whole.signals
    assert restored.risk_events == whole.risk_events
    assert restored.daily == whole.daily
    assert restored.opportunities == whole.opportunities
    assert restored.ledger.positions == whole.ledger.positions
    assert (restored.status, restored.reasons, restored.stopped_at) == (
        whole.status,
        whole.reasons,
        whole.stopped_at,
    )


@pytest.mark.parametrize("minute_model", [False, True])
def test_mismatched_price_feed_fails_closed(start, rules, minute_model):
    config = (
        _config(start) if minute_model else Config(start=iso(start), end=iso(start + 240 * SECOND))
    )
    rows = prices(start, [0, 60], mark="100.3") if minute_model else _bars(start, [0, 60])
    result = Backtest(config, rules).run(sorted(warmup(start) + rows, key=event_key))
    assert result.status == "incomplete_data"
    assert any("execution model" in reason for reason in result.reasons)
    assert result.fills == []


def test_minute_events_replay_without_fabricating_trade_records(start, tmp_path):
    price_type, volume_type = _types()
    for dataset, kind in (("minute_prices", price_type), ("minute_volumes", volume_type)):
        originals = [row for row in _bars(start, [0, 60]) if isinstance(row, kind)]
        rows = [
            {
                key: str(value) if isinstance(value, D) else value
                for key, value in asdict(row).items()
            }
            for row in originals
        ]
        path = tmp_path / f"{dataset}.parquet"
        pq.write_table(pa.Table.from_pylist(rows), path)
        restored = list(_records(path, dataset))
        assert restored == originals
        assert all(decode(encode(row)) == row for row in restored)


def test_funding_before_minute_fill_is_not_paid_to_a_new_short(start, rules):
    rows = warmup(start) + _bars(start, [0, 60, 120, 180])
    rows.append(
        Funding(
            "BTCUSDT",
            start + 180 * SECOND,
            start + 240 * SECOND,
            D(".001"),
            D(".05"),
            D("100.3"),
            "synthetic",
            True,
        )
    )
    result = Backtest(_config(start), rules).run(sorted(rows, key=event_key))
    assert result.ledger.positions["BTCUSDT"].short > 0
    assert result.ledger.positions["BTCUSDT"].funding == 0


def test_minute_renewal_after_one_holding_period_preserves_open_hedge(start, rules):
    config = _config(start, seconds=3900, holding_hours=1, window_hours=1)
    rows = warmup(start, interval=1) + _bars(start, range(0, 3900, 60))
    rows.extend(
        Funding(
            symbol,
            start + HOUR,
            start + HOUR + 60 * SECOND,
            D(".000001"),
            D(1),
            D("100.3"),
            "synthetic",
            True,
        )
        for symbol in config.symbols
    )
    result = Backtest(config, rules).run(sorted(rows, key=event_key))
    assert len(result.fills) == 4
    assert result.pairs["BTCUSDT"].expiry == start + 180 * SECOND + 2 * HOUR
    assert result.ledger.reconcile(result.spot_prices(), result.mark_prices())["difference"] == 0


def test_minute_weekly_renewal_keeps_a_real_168_hour_clock(start, rules):
    seconds = 169 * 3600
    config = _config(start, seconds=seconds)
    rows = warmup(start) + _bars(start, range(0, seconds, 60))
    rows.extend(
        Funding(
            symbol,
            start + hour * HOUR,
            start + hour * HOUR + 60 * SECOND,
            D(".001"),
            D(8),
            D("100.3"),
            "synthetic",
            True,
        )
        for hour in range(8, 169, 8)
        for symbol in config.symbols
    )
    result = Backtest(config, rules).run(sorted(rows, key=event_key))
    assert result.status == "complete"
    assert len(result.fills) == 4
    assert result.pairs["BTCUSDT"].expiry == start + 180 * SECOND + 336 * HOUR
    assert result.ledger.positions["BTCUSDT"].funding > 0
    assert result.native_fill_count == len(result.fills)
    assert result.ledger.reconcile(result.spot_prices(), result.mark_prices())["difference"] == 0

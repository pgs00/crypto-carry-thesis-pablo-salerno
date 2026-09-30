from dataclasses import replace
from decimal import Decimal

import pytest
from conftest import prices, warmup

from crypto_carry.config import SECOND, Config, iso
from crypto_carry.events import event_key
from crypto_carry.strategy import Backtest


def test_resume_with_open_spot_and_pending_hedge_matches_uninterrupted_run(start, rules, tmp_path):
    rows = sorted(
        warmup(start) + prices(start, [0, 60, 61, 62, 63, 100], mark="100.3"), key=event_key
    )
    config = Config(start=iso(start), end=iso(start + 200 * SECOND))
    whole = Backtest(config, rules).run(rows)
    partial = Backtest(config, rules).run(rows, stop_at=start + 61 * SECOND)
    path = tmp_path / "checkpoint.json"
    partial.checkpoint(path)
    restored = Backtest.load_checkpoint(path, config, rules).run(rows)
    assert restored.fills == whole.fills
    assert restored.ledger.rows == whole.ledger.rows
    assert restored.daily == whole.daily
    assert restored.durations == whole.durations


def test_checkpoint_rejects_changed_rules_or_inputs(start, rules, tmp_path):
    config = Config(start=iso(start), end=iso(start + 200 * SECOND))
    b = Backtest(config, rules, inputs={"fixture": "sha256-original"})
    b.run(
        sorted(warmup(start) + prices(start, [0, 60, 61], mark="100.3"), key=event_key),
        stop_at=start + 61 * SECOND,
    )
    path = tmp_path / "bound.json"
    b.checkpoint(path)
    with pytest.raises(ValueError, match="input hashes"):
        Backtest.load_checkpoint(path, config, rules, {"fixture": "changed"})
    key = ("BTCUSDT", "spot")
    rules.items[key] = replace(rules.items[key], taker_fee=Decimal(".0001"))
    with pytest.raises(ValueError, match="market rules"):
        Backtest.load_checkpoint(path, config, rules, {"fixture": "sha256-original"})

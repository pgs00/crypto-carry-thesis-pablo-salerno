from crypto_carry.config import DAY, iso, timestamp
from crypto_carry.data.rules import synthetic_rules
from crypto_carry.fixtures import demo_config, demo_records
from crypto_carry.strategy import Backtest


def test_offline_demo_uses_both_native_carry_strategies_and_valid_minute_history():
    c = demo_config()
    c = c.changed(end=iso(timestamp(c.start) + DAY))
    results = [
        Backtest(c, synthetic_rules(c), strategy, enabled).run(demo_records(c))
        for strategy, enabled in (("conditional", True), ("permanent", False))
    ]
    for result in results:
        assert result.status == "complete"
        assert result.native_fill_count == 4
        assert result.native_reconciliation_count == 4
        assert len(result.daily) == 1
        assert len(result.opportunities) == 2880
        assert all(row["complete"] for row in result.opportunities)
        assert (
            result.ledger.reconcile(result.spot_prices(), result.mark_prices())["difference"] == 0
        )
    assert results[0].ledger.positions is not results[1].ledger.positions

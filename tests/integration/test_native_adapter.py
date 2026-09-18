from decimal import Decimal as D

from crypto_carry.config import SECOND, Config, timestamp
from crypto_carry.models import Fill, Order
from crypto_carry.nautilus_adapter import NautilusAdapter


def test_native_replay_fills_positions_and_keeps_position_at_end():
    start = timestamp("2024-01-01T00:00:00Z")
    config = Config(start="2024-01-01T00:00:00Z", end="2024-01-01T00:01:00Z")
    order = Order("test-1", "BTCUSDT", "spot", "BUY", D("10"), start, start + 30 * SECOND, "open")
    seen = []

    def on_batch(t, records, native):
        seen.append(t)
        if t == start:
            native.submit(order, D("100"))
            assert native.quantity("BTCUSDT", "spot") == 0
        if t == start + SECOND:
            fill = Fill(
                "fill-1",
                order.order_id,
                order.symbol,
                order.market,
                order.side,
                D("10"),
                D("100.01"),
                D("100"),
                t,
                "tiny-trade",
                D("0"),
            )
            native.execute(fill)
            assert native.quantity("BTCUSDT", "spot") == D("10")

    adapter = NautilusAdapter(config)
    adapter.replay([(start, []), (start + SECOND, [])], on_batch)
    assert seen == [start, start + SECOND]
    assert len(adapter.fill_events) == 1
    assert adapter.quantity("BTCUSDT", "spot") == D("10")
    assert adapter.fill_events[0]["time_ns"] == start + SECOND
    adapter.dispose()


def test_native_timer_fires_without_trades_and_same_timestamp_data_precedes_timer():
    start = timestamp("2024-01-01T00:00:00Z")
    config = Config(start="2024-01-01T00:00:00Z", end="2024-01-01T00:00:06Z")
    seen = []
    adapter = NautilusAdapter(config)
    adapter.replay(
        [(start, []), (start + 2 * SECOND, ["market_update"])],
        lambda t, rows, native: seen.append((t, rows)),
        next_timer=lambda t: t + 2 * SECOND,
    )
    assert seen == [(start, []), (start + 2 * SECOND, ["market_update"]), (start + 4 * SECOND, [])]
    adapter.dispose()

from decimal import Decimal as D

from crypto_carry.config import SECOND, Config
from crypto_carry.execution import eligible_trade, observe_vwap
from crypto_carry.models import Order, Trade


def test_fill_strictly_after_submit_and_before_deadline_and_ignores_trade_size():
    o = Order("o", "BTCUSDT", "spot", "BUY", D(10), SECOND, 31 * SECOND, "open")
    for second, expected in [(0, False), (1, False), (2, True), (30, True), (31, False)]:
        t = Trade(
            "BTCUSDT", "spot", str(second), second * SECOND, second * SECOND, D(100), D(".0001")
        )
        assert eligible_trade(o, t) == expected


def test_vwap_only_uses_strictly_posterior_window_and_actual_volume():
    o = Order("o", "BTCUSDT", "spot", "BUY", D(10), SECOND, 31 * SECOND, "open")
    c = Config(execution_model="vwap")
    for second, price, qty in [(1, 1, 100), (2, 100, 1), (6, 110, 3), (7, 999, 10)]:
        observe_vwap(
            o,
            Trade(
                "BTCUSDT", "spot", str(second), second * SECOND, second * SECOND, D(price), D(qty)
            ),
            c,
        )
    assert o.vwap_notional / o.vwap_quantity == D("107.5")

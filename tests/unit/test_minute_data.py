"""Closed-minute economic event and checkpoint representation."""
from decimal import Decimal

from crypto_carry.config import SECOND
from crypto_carry.models import MinuteBar
from crypto_carry.serialization import decode, encode


def test_minute_bar_contract_is_closed_causal_and_checkpoint_safe():
    bar = MinuteBar(
        symbol="BTCUSDT",
        market="spot",
        open_time=0,
        end_time=60 * SECOND,
        available_at=60 * SECOND,
        open=Decimal("99"),
        high=Decimal("101"),
        low=Decimal("98"),
        close=Decimal("100"),
        base_volume=Decimal("2"),
        quote_volume=Decimal("200"),
        trade_count=4,
        source_file="fixture.zip",
    )

    assert bar.event_time == bar.available_at == bar.end_time
    assert bar.price == Decimal("100")
    assert bar.reference_id == "bar:BTCUSDT:spot:0"
    assert decode(encode(bar)) == bar

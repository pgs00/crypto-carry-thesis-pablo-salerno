from decimal import Decimal as D

import pytest

from crypto_carry.config import HOUR, SECOND, Config, timestamp
from crypto_carry.models import Funding, Mark, MarketRule, Tier, Trade


class FixedRules:
    def __init__(self, fee=True):
        self.items = {}
        for symbol in Config().symbols:
            for market in ("spot", "futures"):
                self.items[(symbol, market)] = MarketRule(
                    symbol,
                    market,
                    D(".001"),
                    D(".01"),
                    D(".001"),
                    D("1000000"),
                    D(".01"),
                    D("1000000000"),
                    (D(".001") if market == "spot" else D(".0005")) if fee else D(0),
                    (Tier(D(0), D("1000000000"), D(".005"), D(0)),),
                    D(".01"),
                )

    def get(self, symbol, market, time_ns):
        return self.items.get((symbol, market))


@pytest.fixture
def rules():
    return FixedRules()


@pytest.fixture
def start():
    return timestamp("2024-01-01T00:00:00Z")


def warmup(start, rate=".001", interval=8):
    return [
        Funding(
            symbol,
            start + h * HOUR,
            start + h * HOUR + 60 * SECOND,
            D(rate),
            D(interval),
            D("100.3"),
            "synthetic",
            True,
        )
        for h in range(-336, 1, interval)
        for symbol in Config().symbols
    ]


def prices(start, seconds, spot="100", future="100.3", mark=None):
    rows = []
    for second in seconds:
        time_ns = start + int(second * SECOND)
        for symbol in Config().symbols:
            for market, price in (("spot", spot), ("futures", future)):
                rows.append(
                    Trade(
                        symbol,
                        market,
                        f"{second}-{symbol}-{market}",
                        time_ns,
                        time_ns,
                        D(price),
                        D(".001"),
                    )
                )
            if mark is not None:
                rows.append(
                    Mark(
                        symbol,
                        time_ns - 60 * SECOND,
                        time_ns - 1,
                        time_ns,
                        D(mark),
                        D(mark),
                        D(mark),
                        D(mark),
                    )
                )
    return rows

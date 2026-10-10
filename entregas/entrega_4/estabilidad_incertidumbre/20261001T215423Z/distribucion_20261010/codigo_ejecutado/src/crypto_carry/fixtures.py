"""Small deterministic synthetic market; never a substitute for Binance observations."""

from decimal import Decimal as D

from .config import DAY, HOUR, SECOND, Config, timestamp
from .events import event_key
from .models import Funding, Mark, Trade


def demo_config(base: Config | None = None) -> Config:
    return (base or Config()).changed(start="2023-12-28T00:00:00Z", end="2024-01-07T00:00:00Z")


def demo_records(config: Config):
    """Generate only the current timestamp batch, including a complete forecast warmup."""
    start, end = timestamp(config.start), timestamp(config.end)
    warmup = start - (config.window_hours + 48) * HOUR
    warmup = warmup // (8 * HOUR) * (8 * HOUR)
    for time_ns in range(warmup, start, 8 * HOUR):
        for symbol in config.symbols:
            yield Funding(
                symbol,
                time_ns,
                time_ns + 60 * SECOND,
                D(".0004"),
                D(8),
                D("100.3"),
                "synthetic:demo-v1",
                True,
            )
    for minute in range(start, end, 60 * SECOND):
        day = (minute - start) // DAY
        spot = D(100) + D(day) / 10
        future = spot + D(".3")
        rate = D(".0004") if day < 5 else D("-.0002") if day < 8 else D(".0001")
        for offset in (0, 1, 3, 8, 11, 14):
            time_ns = minute + offset * SECOND
            if time_ns >= end:
                continue
            rows = []
            for symbol in config.symbols:
                if offset == 0:
                    rows.append(
                        Mark(
                            symbol,
                            minute - 60 * SECOND,
                            minute - 1,
                            minute,
                            future,
                            future,
                            future,
                            future,
                            "synthetic:demo-v1",
                        )
                    )
                    if minute % (8 * HOUR) == 0:
                        rows.append(
                            Funding(
                                symbol,
                                minute,
                                minute + 60 * SECOND,
                                rate,
                                D(8),
                                future,
                                "synthetic:demo-v1",
                                True,
                            )
                        )
                for market, price in (("spot", spot), ("futures", future)):
                    rows.append(
                        Trade(
                            symbol,
                            market,
                            str(time_ns),
                            time_ns,
                            time_ns,
                            price,
                            D(20),
                            "synthetic:demo-v1",
                        )
                    )
            yield from sorted(rows, key=event_key)

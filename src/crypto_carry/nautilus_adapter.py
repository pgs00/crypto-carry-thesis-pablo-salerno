"""Verified Nautilus 1.231 integration for the study's explicit matching convention.

The native engine replays timestamp batches and maintains real native orders,
fills and positions. Native resting limit orders are inert carriers: market data
are custom batches, never a native book. Only the domain's strictly subsequent
trade gate calls OrderMatchingEngine.fill_order. This explicitly replaces the
native liquidity/matching policy, not the native execution event lifecycle.
Native accounts are frozen and fees zero: the project's ledger owns economics.
"""

from decimal import Decimal
from itertools import islice
from typing import Callable, Iterable

import nautilus_trader
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.modules import SimulationModule
from nautilus_trader.config import (
    BacktestEngineConfig,
    LoggingConfig,
    RiskEngineConfig,
    SimulationModuleConfig,
    StrategyConfig,
)
from nautilus_trader.core.data import Data
from nautilus_trader.model.currencies import BTC, ETH, USDT
from nautilus_trader.model.data import CustomData, DataType
from nautilus_trader.model.enums import AccountType, LiquiditySide, OmsType, OrderSide, TimeInForce
from nautilus_trader.model.identifiers import ClientId, ClientOrderId, InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import CryptoPerpetual, CurrencyPair
from nautilus_trader.model.objects import Money, Price, Quantity
from nautilus_trader.trading.strategy import Strategy

from .config import Config, timestamp
from .models import Fill, Order


class TimestampBatch(Data):
    def __init__(self, time_ns: int, records: list):
        self.time_ns = time_ns
        self.records = records

    @property
    def ts_event(self):
        return self.time_ns

    @property
    def ts_init(self):
        return self.time_ns


class DomainModule(SimulationModule):
    """Expose the supported simulation exchange extension point."""

    def __init__(self):
        super().__init__(SimulationModuleConfig())
        self.processed_timestamps = 0

    def process(self, ts_now):
        self.processed_timestamps += 1

    def log_diagnostics(self, logger):
        logger.debug(f"Domain exchange timestamps: {self.processed_timestamps}")

    def reset(self):
        self.processed_timestamps = 0


class ReplayStrategy(Strategy):
    def __init__(self, owner):
        super().__init__(StrategyConfig(manage_stop=False, log_events=False, log_commands=False))
        self.owner = owner

    def on_start(self):
        self.subscribe_data(DataType(TimestampBatch), client_id=ClientId("RESEARCH"))

    def on_data(self, data):
        if isinstance(data, TimestampBatch):
            self.owner.dispatch(data.time_ns, data.records)

    def on_domain_timer(self, event):
        # Nautilus dispatches timers at the current data timestamp after data.
        # The already processed batch has included every due domain timer.
        if event.ts_event > self.owner.last_dispatched:
            self.owner.dispatch(event.ts_event, [])

    def on_order_filled(self, event):
        self.owner.fill_events.append(
            {
                "order_id": str(event.client_order_id),
                "time_ns": event.ts_event,
                "quantity": str(event.last_qty),
                "price": str(event.last_px),
            }
        )


class NautilusAdapter:
    def __init__(self, config: Config):
        if nautilus_trader.__version__ != "1.231.0":
            raise RuntimeError("The adapter requires the verified NautilusTrader 1.231.0 API")
        self.config = config
        self.fill_events: list[dict] = []
        self.orders = {}
        self.callback: Callable | None = None
        self.next_timer: Callable | None = None
        self.last_dispatched = -1
        self.engine = BacktestEngine(
            BacktestEngineConfig(
                logging=LoggingConfig(log_level="ERROR"),
                risk_engine=RiskEngineConfig(bypass=True),
            )
        )
        self.module = DomainModule()
        self.venue = Venue("RESEARCH")
        self.engine.add_venue(
            self.venue,
            OmsType.NETTING,
            AccountType.MARGIN,
            [Money(config.capital, USDT)],
            base_currency=USDT,
            modules=[self.module],
            frozen_account=True,
            use_message_queue=False,
            trade_execution=False,
            bar_execution=False,
            use_random_ids=False,
        )
        self.instruments = {}
        for symbol, currency in (("BTCUSDT", BTC), ("ETHUSDT", ETH)):
            for market in ("spot", "futures"):
                instrument_id = InstrumentId.from_str(f"{symbol}-{market}.RESEARCH")
                common = dict(
                    instrument_id=instrument_id,
                    raw_symbol=Symbol(symbol),
                    base_currency=currency,
                    quote_currency=USDT,
                    price_precision=8,
                    size_precision=8,
                    price_increment=Price.from_str("0.00000001"),
                    size_increment=Quantity.from_str("0.00000001"),
                    ts_event=0,
                    ts_init=0,
                    maker_fee=Decimal(0),
                    taker_fee=Decimal(0),
                )
                instrument = (
                    CurrencyPair(**common)
                    if market == "spot"
                    else CryptoPerpetual(**common, settlement_currency=USDT, is_inverse=False)
                )
                self.instruments[(symbol, market)] = instrument
                self.engine.add_instrument(instrument)
        self.strategy = ReplayStrategy(self)
        self.engine.add_strategy(self.strategy)

    def submit(self, order: Order, known_price: Decimal) -> None:
        instrument = self.instruments[(order.symbol, order.market)]
        native = self.strategy.order_factory.limit(
            instrument_id=instrument.id,
            order_side=OrderSide.BUY if order.side == "BUY" else OrderSide.SELL,
            quantity=instrument.make_qty(order.quantity),
            price=instrument.make_price(known_price),
            time_in_force=TimeInForce.GTC,
            client_order_id=ClientOrderId(order.order_id),
        )
        self.orders[order.order_id] = native
        self.strategy.submit_order(native)
        if native.is_closed:
            raise RuntimeError(f"Native order rejected: {order.order_id}: {native.status_string()}")

    def cancel(self, order_id: str) -> None:
        native = self.orders.get(order_id)
        if native is not None and not native.is_closed:
            self.strategy.cancel_order(native)

    def execute(self, fill: Fill) -> None:
        native = self.orders[fill.order_id]
        if not native.is_open:
            raise RuntimeError(f"Cannot fill native order in state {native.status_string()}")
        if self.strategy.clock.timestamp_ns() != fill.time_ns:
            raise RuntimeError("Native clock and economic fill time differ")
        instrument = self.instruments[(fill.symbol, fill.market)]
        matcher = self.module.exchange.get_matching_engine(instrument.id)
        previous = len(self.fill_events)
        matcher.fill_order(
            native,
            instrument.make_price(fill.price),
            instrument.make_qty(fill.quantity),
            LiquiditySide.TAKER,
        )
        if len(self.fill_events) != previous + 1 or not native.is_closed:
            raise RuntimeError("Native full-fill event was not produced exactly once")
        event = self.fill_events[-1]
        if Decimal(event["quantity"]) != fill.quantity or Decimal(event["price"]) != fill.price:
            raise RuntimeError("Native quantity/price diverged from the domain fill")

    def quantity(self, symbol: str, market: str) -> Decimal:
        instrument = self.instruments[(symbol, market)]
        return sum(
            (
                Decimal(str(p.signed_qty))
                for p in self.engine.cache.positions_open(instrument_id=instrument.id)
            ),
            Decimal(0),
        )

    def dispatch(self, time_ns: int, records: list) -> None:
        self.last_dispatched = time_ns
        self.callback(time_ns, records, self)
        if self.next_timer is not None:
            due = self.next_timer(time_ns)
            if due is not None and time_ns < due < timestamp(self.config.end):
                if "domain" in self.strategy.clock.timer_names:
                    self.strategy.clock.cancel_timer("domain")
                self.strategy.clock.set_time_alert_ns(
                    "domain",
                    due,
                    callback=self.strategy.on_domain_timer,
                    allow_past=False,
                )

    def replay(
        self,
        batches: Iterable[tuple[int, list]],
        callback: Callable,
        chunk_size: int = 10000,
        finalize: bool = True,
        next_timer: Callable | None = None,
    ) -> None:
        self.callback = callback
        self.next_timer = next_timer
        source = iter(batches)
        end = timestamp(self.config.end)
        previous = -1
        while chunk := list(islice(source, chunk_size)):
            data = []
            for time_ns, records in chunk:
                if time_ns <= previous:
                    raise ValueError("Timestamp groups must be strictly increasing")
                previous = time_ns
                if time_ns < end:
                    data.append(
                        CustomData(DataType(TimestampBatch), TimestampBatch(time_ns, records))
                    )
            if not data:
                continue
            self.engine.add_data(data, client_id=ClientId("RESEARCH"))
            self.engine.run(
                start=min(data[0].ts_init, timestamp(self.config.start)),
                end=end - 1,
                streaming=True,
            )
            self.engine.clear_data()
        if finalize and self.engine.run_started is not None:
            self.engine.end()

    def dispose(self) -> None:
        self.engine.dispose()

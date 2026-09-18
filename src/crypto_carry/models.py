"""Public data contracts, with integer UTC nanoseconds and exact decimal quantities."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

D = Decimal


@dataclass(frozen=True)
class Trade:
    symbol: str
    market: str
    trade_id: str
    event_time: int
    available_at: int
    price: Decimal
    quantity: Decimal
    source_file: str = "synthetic"


@dataclass(frozen=True)
class Funding:
    symbol: str
    funding_time: int
    available_at: int
    funding_rate: Decimal
    interval_hours: Decimal
    settlement_mark_price: Decimal | None
    source_file: str = "synthetic"
    interval_verified: bool = False
    settlement_mark_method: str = "exact"
    settlement_mark_source_file: str = ""
    settlement_mark_close_time: int | None = None
    settlement_mark_available_at: int | None = None
    settlement_mark_proxy_base: Decimal | None = None
    settlement_mark_stress_bps: Decimal = D(0)


@dataclass(frozen=True)
class Mark:
    symbol: str
    open_time: int
    close_time: int
    available_at: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    source_file: str = "synthetic"


@dataclass(frozen=True)
class Tier:
    floor: Decimal
    cap: Decimal
    rate: Decimal
    deduction: Decimal


@dataclass(frozen=True)
class MarketRule:
    symbol: str
    market: str
    step: Decimal
    tick: Decimal
    min_qty: Decimal
    max_qty: Decimal
    min_notional: Decimal
    max_notional: Decimal
    taker_fee: Decimal
    tiers: tuple[Tier, ...] = ()
    liquidation_fee: Decimal = D("0")
    liquidation_regular_fee: bool = True
    liquidation_fee_basis: str = "execution_notional"
    operational: bool = True


class State(StrEnum):
    FLAT = "FLAT"
    OPENING_SPOT = "OPENING_SPOT"
    OPENING_PERP = "OPENING_PERP"
    HOLDING = "HOLDING"
    REBALANCING = "REBALANCING"
    CORRECTING_HEDGE = "CORRECTING_HEDGE"
    CLOSING_PERP = "CLOSING_PERP"
    CLOSING_SPOT = "CLOSING_SPOT"
    LIQUIDATING = "LIQUIDATING"
    COOLDOWN = "COOLDOWN"


@dataclass
class Order:
    order_id: str
    symbol: str
    market: str
    side: str
    quantity: Decimal
    submitted_at: int
    deadline: int
    purpose: str
    status: str = "pending"
    vwap_notional: Decimal = D("0")
    vwap_quantity: Decimal = D("0")
    reference_ids: list[str] = field(default_factory=list)
    recent_volume_quantity: Decimal = D("0")


@dataclass(frozen=True)
class Fill:
    fill_id: str
    order_id: str
    symbol: str
    market: str
    side: str
    quantity: Decimal
    price: Decimal
    reference_price: Decimal
    time_ns: int
    trade_id: str
    fee_rate: Decimal
    liquidation: bool = False


@dataclass
class Pair:
    state: State = State.FLAT
    cycle_id: str = ""
    basis_reference: Decimal | None = None
    expiry: int | None = None
    cooldown_until: int = 0
    cooldown_required: bool = False
    next_leg_at: int | None = None
    next_leg: str = ""
    adjustment_quantity: Decimal = D("0")
    correction_deadline: int | None = None
    opened_at: int | None = None
    liquidation_pending: bool = False

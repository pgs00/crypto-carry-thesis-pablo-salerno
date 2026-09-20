"""Exact-decimal cash, inventory, isolated collateral, funding, and debt ledger."""

from dataclasses import dataclass
from decimal import Decimal

from .config import Config
from .models import Fill, Funding, MarketRule

D = Decimal
ZERO = D(0)


@dataclass
class Position:
    spot: Decimal = ZERO
    short: Decimal = ZERO
    average: Decimal = ZERO
    collateral: Decimal = ZERO
    spot_cost: Decimal = ZERO
    realized_spot: Decimal = ZERO
    realized_futures: Decimal = ZERO
    funding: Decimal = ZERO
    fees: Decimal = ZERO
    liquidation_fees: Decimal = ZERO
    slippage: Decimal = ZERO


class Ledger:
    def __init__(self, config: Config, strategy: str):
        self.config = config
        self.strategy = strategy
        self.free_spot = config.capital
        self.free_futures = D(0)
        self.debt = D(0)
        self.positions: dict[str, Position] = {}
        self.rows: list[dict] = []
        self.funding_rows: list[dict] = []
        self.seen: set[str] = set()
        self._events: dict[str, object] = {}

    def equity(self, spot_prices: dict, marks: dict) -> Decimal:
        value = self.free_spot + self.free_futures - self.debt
        for symbol, position in self.positions.items():
            value += position.collateral
            if position.spot:
                if symbol not in spot_prices:
                    raise ValueError(f"Missing spot price for {symbol}")
                value += position.spot * spot_prices[symbol]
            if position.short:
                if symbol not in marks:
                    raise ValueError(f"Missing mark for {symbol}")
                value += position.short * (position.average - marks[symbol])
        return value

    def _event_value(
        self, symbol: str, *, spot_price: Decimal | None = None, mark: Decimal | None = None
    ) -> Decimal:
        value = self.free_spot + self.free_futures - self.debt
        value += sum(position.collateral for position in self.positions.values())
        position = self.positions.get(symbol)
        if position is not None:
            if spot_price is not None:
                value += position.spot * spot_price
            if mark is not None:
                value += position.short * (position.average - mark)
        return value

    def _assert_movement(self, before: Decimal, after: Decimal, expected: Decimal) -> None:
        difference = after - before - expected
        if abs(difference) > self.config.accounting_tolerance:
            raise AssertionError(f"Accounting movement differs by {difference}")

    def _check_duplicate(self, event_id: str, event: object) -> bool:
        if event_id not in self.seen:
            return False
        if self._events[event_id] != event:
            raise ValueError(f"Conflicting duplicate event: {event_id}")
        return True

    def _remember(self, event_id: str, event: object) -> None:
        self.seen.add(event_id)
        self._events[event_id] = event

    def _reserve(self, amount: Decimal) -> bool:
        if amount < 0:
            raise ValueError("Cannot reserve a negative amount")
        if self.debt > 0 or self.free_futures + self.free_spot < amount:
            return False
        from_futures = min(self.free_futures, amount)
        self.free_futures -= from_futures
        self.free_spot -= amount - from_futures
        return True

    def _receive(self, amount: Decimal, *, account: str) -> None:
        if amount < 0:
            raise ValueError("Incoming amount must be non-negative")
        repaid = min(self.debt, amount)
        self.debt -= repaid
        remainder = amount - repaid
        if account == "spot":
            self.free_spot += remainder
        elif account == "futures":
            self.free_futures += remainder
        else:
            raise ValueError(f"Unknown account: {account}")

    def _pay(self, amount: Decimal, *, released_collateral: Decimal = ZERO) -> None:
        if amount < 0 or released_collateral < 0:
            raise ValueError("Outgoing amounts must be non-negative")
        from_futures = min(self.free_futures, amount)
        self.free_futures -= from_futures
        remaining = amount - from_futures
        from_spot = min(self.free_spot, remaining)
        self.free_spot -= from_spot
        remaining -= from_spot
        from_released = min(released_collateral, remaining)
        remaining -= from_released
        self.debt += remaining
        self._receive(released_collateral - from_released, account="futures")

    def _record(
        self,
        event_id: str,
        time_ns: int,
        symbol: str,
        kind: str,
        amount_usdt: Decimal,
        **details,
    ) -> dict:
        position = self.positions.get(symbol, Position())
        row = {
            "event_id": event_id,
            "time_ns": time_ns,
            "strategy": self.strategy,
            "symbol": symbol,
            "kind": kind,
            "amount_usdt": amount_usdt,
            "free_spot": self.free_spot,
            "free_futures": self.free_futures,
            "debt": self.debt,
            "spot": position.spot,
            "short": position.short,
            "average": position.average,
            "collateral": position.collateral,
            **details,
        }
        self.rows.append(row)
        return row

    def apply_fill(self, fill: Fill, rule: MarketRule, mark: Decimal) -> bool:
        event_id = f"fill:{fill.fill_id}"
        event = (fill, rule, mark)
        if self._check_duplicate(event_id, event):
            return False
        if fill.quantity <= 0 or fill.price <= 0 or fill.fee_rate < 0 or mark <= 0:
            raise ValueError("Fill quantity, prices, and fee must be valid")
        market = fill.market.lower()
        side = fill.side.lower()
        if market not in {"spot", "futures"} or side not in {"buy", "sell"}:
            raise ValueError("Unknown fill market or side")
        position = self.positions.get(fill.symbol)
        before_spot_cash, before_futures_cash, before_debt = (
            self.free_spot,
            self.free_futures,
            self.debt,
        )
        cash_transfer = D(0)

        if market == "spot" and side == "buy":
            gross_cost = fill.quantity * fill.price
            if self.debt > 0 or self.free_spot + self.free_futures < gross_cost:
                return False
            if position is None:
                position = Position()
                self.positions[fill.symbol] = position
            before = self._event_value(fill.symbol, spot_price=fill.reference_price, mark=mark)
            cash_transfer = max(D(0), gross_cost - self.free_spot)
            self.free_futures -= cash_transfer
            self.free_spot += cash_transfer
            base_fee = fill.quantity * fill.fee_rate
            received = fill.quantity - base_fee
            self.free_spot -= gross_cost
            position.spot += received
            position.spot_cost += received * fill.price
            fee_value = base_fee * fill.price
            position.fees += fee_value
            position.slippage += max(D(0), fill.quantity * (fill.price - fill.reference_price))
            after = self._event_value(fill.symbol, spot_price=fill.reference_price, mark=mark)
            expected = received * fill.reference_price - gross_cost
            self._assert_movement(before, after, expected)
            details = {
                "fee": fee_value,
                "spot_cost": gross_cost,
                "collateral_change": D(0),
                "pnl": D(0),
                "base_fee_quantity": base_fee,
                "transfer_futures_to_spot": cash_transfer,
            }

        elif market == "spot" and side == "sell":
            if position is None or position.spot < fill.quantity:
                return False
            before = self._event_value(fill.symbol, spot_price=fill.reference_price, mark=mark)
            allocated_cost = position.spot_cost * fill.quantity / position.spot
            gross_proceeds = fill.quantity * fill.price
            fee_value = gross_proceeds * fill.fee_rate
            position.spot -= fill.quantity
            position.spot_cost -= allocated_cost
            position.realized_spot += gross_proceeds - allocated_cost
            position.fees += fee_value
            position.slippage += max(D(0), fill.quantity * (fill.reference_price - fill.price))
            self._receive(gross_proceeds - fee_value, account="spot")
            after = self._event_value(fill.symbol, spot_price=fill.reference_price, mark=mark)
            expected = gross_proceeds - fee_value - fill.quantity * fill.reference_price
            self._assert_movement(before, after, expected)
            details = {
                "fee": fee_value,
                "spot_proceeds": gross_proceeds,
                "collateral_change": D(0),
                "pnl": gross_proceeds - allocated_cost,
            }

        elif market == "futures" and side == "sell":
            ordinary_fee = fill.quantity * fill.price * fill.fee_rate
            collateral = fill.quantity * fill.price / self.config.leverage
            open_loss = max(D(0), fill.quantity * (mark - fill.price))
            required = ordinary_fee + collateral + open_loss
            if not self._reserve(required):
                return False
            if position is None:
                position = Position()
                self.positions[fill.symbol] = position
            before = self._event_value(fill.symbol, mark=mark) + required
            prior_short = position.short
            new_short = prior_short + fill.quantity
            position.average = (
                position.average * prior_short + fill.price * fill.quantity
            ) / new_short
            position.short = new_short
            position.collateral += collateral + open_loss
            position.fees += ordinary_fee
            position.slippage += max(D(0), fill.quantity * (fill.reference_price - fill.price))
            after = self._event_value(fill.symbol, mark=mark)
            expected = fill.quantity * (fill.price - mark) - ordinary_fee
            self._assert_movement(before, after, expected)
            details = {
                "fee": ordinary_fee,
                "collateral_change": collateral + open_loss,
                "open_loss": open_loss,
                "pnl": D(0),
            }

        else:
            if position is None or position.short < fill.quantity:
                return False
            before = self._event_value(fill.symbol, mark=mark)
            fraction = fill.quantity / position.short
            released = position.collateral * fraction
            realized = fill.quantity * (position.average - fill.price)
            ordinary_fee = D(0)
            if not fill.liquidation or rule.liquidation_regular_fee:
                ordinary_fee = fill.quantity * fill.price * fill.fee_rate
            liquidation_fee = D(0)
            if fill.liquidation:
                if rule.liquidation_fee_basis == "execution_notional":
                    fee_basis = fill.quantity * fill.price
                elif rule.liquidation_fee_basis == "mark_notional":
                    fee_basis = fill.quantity * mark
                else:
                    raise ValueError("Unknown liquidation fee basis")
                liquidation_fee = fee_basis * rule.liquidation_fee
            position.short -= fill.quantity
            position.collateral -= released
            position.realized_futures += realized
            position.fees += ordinary_fee
            position.liquidation_fees += liquidation_fee
            position.slippage += max(D(0), fill.quantity * (fill.price - fill.reference_price))
            net_flow = realized - ordinary_fee - liquidation_fee
            if net_flow >= 0:
                self._receive(released + net_flow, account="futures")
            else:
                self._pay(-net_flow, released_collateral=released)
            if position.short == 0:
                position.average = D(0)
            after = self._event_value(fill.symbol, mark=mark)
            expected = fill.quantity * (mark - fill.price) - ordinary_fee - liquidation_fee
            self._assert_movement(before, after, expected)
            details = {
                "fee": ordinary_fee,
                "liquidation_fee": liquidation_fee,
                "collateral_change": -released,
                "pnl": realized,
            }

        self._remember(event_id, event)
        self._record(
            event_id,
            fill.time_ns,
            fill.symbol,
            f"{market}_{side}",
            expected,
            quantity=fill.quantity,
            price=fill.price,
            reference_price=fill.reference_price,
            fee_asset=fill.symbol.removesuffix("USDT")
            if market == "spot" and side == "buy"
            else "USDT",
            cash_spot_change=self.free_spot - before_spot_cash,
            cash_futures_change=self.free_futures - before_futures_cash,
            debt_change=self.debt - before_debt,
            **details,
        )
        return True

    def apply_funding(self, funding: Funding) -> bool:
        event_id = f"funding:{funding.symbol}:{funding.funding_time}"
        economic = (
            funding.symbol,
            funding.funding_time,
            funding.funding_rate,
            funding.interval_hours,
            funding.settlement_mark_price,
        )
        if self._check_duplicate(event_id, economic):
            return False
        if funding.settlement_mark_price is None:
            raise ValueError("Funding settlement mark is required")
        position = self.positions.get(funding.symbol)
        if position is None:
            position = Position()
            self.positions[funding.symbol] = position
        before = self._event_value(funding.symbol, mark=funding.settlement_mark_price)
        amount = position.short * funding.settlement_mark_price * funding.funding_rate
        position.funding += amount
        collateral_change = D(0)
        if amount >= 0:
            self._receive(amount, account="futures")
        else:
            obligation = -amount
            from_futures = min(self.free_futures, obligation)
            self.free_futures -= from_futures
            obligation -= from_futures
            from_collateral = min(position.collateral, obligation)
            position.collateral -= from_collateral
            collateral_change = -from_collateral
            obligation -= from_collateral
            from_spot = min(self.free_spot, obligation)
            self.free_spot -= from_spot
            obligation -= from_spot
            self.debt += obligation
        after = self._event_value(funding.symbol, mark=funding.settlement_mark_price)
        self._assert_movement(before, after, amount)
        self._remember(event_id, economic)
        row = self._record(
            event_id,
            funding.funding_time,
            funding.symbol,
            "funding",
            amount,
            funding=amount,
            collateral_change=collateral_change,
            fee=D(0),
            pnl=D(0),
        )
        self.funding_rows.append(dict(row))
        return True

    def transfer(self, amount: Decimal, time_ns: int, event_id: str) -> bool:
        key = f"transfer:{event_id}"
        event = (amount, time_ns)
        if self._check_duplicate(key, event):
            return False
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")
        if self.free_spot < amount:
            return False
        before = self._event_value("")
        self.free_spot -= amount
        self.free_futures += amount
        after = self._event_value("")
        self._assert_movement(before, after, D(0))
        self._remember(key, event)
        self._record(key, time_ns, "", "transfer", amount, transfer=amount, fee=D(0), pnl=D(0))
        return True

    def reconcile(self, spot_prices: dict, marks: dict) -> dict:
        current_equity = self.equity(spot_prices, marks)
        attributed = D(0)
        for symbol, position in self.positions.items():
            spot_unrealized = D(0)
            futures_unrealized = D(0)
            if position.spot:
                spot_unrealized = position.spot * spot_prices[symbol] - position.spot_cost
            if position.short:
                futures_unrealized = position.short * (position.average - marks[symbol])
            attributed += (
                position.realized_spot
                + spot_unrealized
                + position.realized_futures
                + futures_unrealized
                + position.funding
                - position.fees
                - position.liquidation_fees
            )
        pnl = current_equity - self.config.capital
        difference = pnl - attributed
        if abs(difference) > self.config.accounting_tolerance:
            raise AssertionError(f"Ledger reconciliation differs by {difference}")
        return {"equity": current_equity, "pnl": pnl, "difference": difference}

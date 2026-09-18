"""One state machine for filtered and permanent carry; ledger owns all economics."""

import hashlib
import json
from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import asdict
from decimal import Decimal as D
from pathlib import Path

from .config import DAY, HOUR, SECOND, Config, iso, timestamp
from .costs import cycle_cost, execution_price, floor_step, valid_quantity
from .data.funding_proxy import resolve_funding_mark
from .events import DataGap, event_time, group_events
from .execution import eligible_trade, observe_vwap
from .forecast import forecast
from .ledger import Ledger, Position
from .models import Fill, Funding, Mark, Order, Pair, State, Trade
from .nautilus_adapter import NautilusAdapter
from .portfolio import hedge_error, needs_rebalance, required_cash, target_quantity
from .risk import basis, entry_basis, needs_hedge_correction, position_risk
from .serialization import decode, encode


class Backtest:
    def __init__(
        self,
        config: Config,
        rules,
        strategy: str = "conditional",
        funding_filter_enabled: bool = True,
        inputs: dict | None = None,
    ):
        self.config = config
        self.rules = rules
        self.strategy = strategy
        self.funding_filter_enabled = funding_filter_enabled
        self.inputs = dict(inputs or {})
        self.ledger = Ledger(config, strategy)
        self.ledger.positions = {s: Position() for s in config.symbols}
        self.pairs = {s: Pair() for s in config.symbols}
        self.trades: dict[tuple, Trade] = {}
        self.marks: dict[str, Mark] = {}
        self.history = defaultdict(list)
        self.all_funding: list[Funding] = []
        self.funding_seen = {}
        self.signal_due = {}
        self.forecasts = {}
        self.orders: dict[str, Order] = {}
        self.order_rows: list[dict] = []
        self.fills: list[dict] = []
        self.signals: list[dict] = []
        self.positions: list[dict] = []
        self.risk_events: list[dict] = []
        self.daily: list[dict] = []
        self.opportunities: list[dict] = []
        self.reservations = defaultdict(lambda: D(0))
        self.native_base_fees = defaultdict(lambda: D(0))
        self.recent_volume = defaultdict(deque)
        self.bad_symbols: set[str] = set()
        self.status = "complete"
        self.reasons: list[str] = []
        self.stopped_at = None
        self.now = 0
        self.serial = 0
        self.native = None
        self.last_minute = -1
        self.last_daily = -1
        self.start = timestamp(config.start)
        self.end = timestamp(config.end)
        self.native_reconciliation_count = 0
        self.durations = defaultdict(lambda: D(0))
        self.last_economic_time = self.start

    def spot_prices(self) -> dict:
        return {
            s: self.trades[(s, "spot")].price
            for s in self.config.symbols
            if (s, "spot") in self.trades
        }

    def mark_prices(self) -> dict:
        return {s: m.close for s, m in self.marks.items()}

    def equity(self) -> D:
        return self.ledger.equity(self.spot_prices(), self.mark_prices())

    def _event(self, symbol: str, kind: str, **values) -> None:
        self.risk_events.append(
            dict(time_ns=self.now, strategy=self.strategy, symbol=symbol, kind=kind, **values)
        )

    def _transition(self, symbol: str, state: State, cause: str, order_id: str = "") -> None:
        pair = self.pairs[symbol]
        self._event(
            symbol,
            "transition",
            previous=pair.state.value,
            state=state.value,
            cause=cause,
            order_id=order_id,
            cycle_id=pair.cycle_id,
        )
        pair.state = state
        self._position_row(symbol)

    def _position_row(self, symbol: str) -> None:
        p = self.ledger.positions[symbol]
        self.positions.append(
            dict(
                time_ns=self.now,
                strategy=self.strategy,
                symbol=symbol,
                state=self.pairs[symbol].state.value,
                **{k: str(v) for k, v in asdict(p).items()},
            )
        )

    def _pending(self, symbol: str) -> list[Order]:
        return [o for o in self.orders.values() if o.symbol == symbol and o.status == "pending"]

    def _rule(self, symbol: str, market: str):
        return self.rules.get(symbol, market, self.now)

    def _fresh(self, symbol: str) -> bool:
        return all(
            (symbol, m) in self.trades
            and self.now - self.trades[(symbol, m)].event_time
            <= self.config.freshness_seconds * SECOND
            for m in ("spot", "futures")
        )

    def _data_valid(self, symbol: str, fresh: bool = True) -> bool:
        return (
            symbol not in self.bad_symbols
            and symbol in self.marks
            and (not fresh or self._fresh(symbol))
            and all(
                (r := self._rule(symbol, m)) is not None and r.operational
                for m in ("spot", "futures")
            )
        )

    def _observed_basis(self, symbol: str) -> D:
        return basis(self.trades[(symbol, "spot")].price, self.trades[(symbol, "futures")].price)

    def _available(self, symbol: str) -> D:
        return (
            self.ledger.free_spot
            + self.ledger.free_futures
            - sum((v for s, v in self.reservations.items() if s != symbol), D(0))
        )

    def _submit(self, symbol: str, market: str, side: str, quantity: D, purpose: str) -> bool:
        if quantity <= 0 or self._pending(symbol):
            return False
        rule = self._rule(symbol, market)
        trade = self.trades.get((symbol, market))
        if rule is None or trade is None or not valid_quantity(quantity, trade.price, rule):
            self._event(
                symbol, "order_blocked", cause="historical_quantity_filter", purpose=purpose
            )
            return False
        self.serial += 1
        order_id = f"{self.strategy}-{self.serial:08d}"
        order = Order(
            order_id,
            symbol,
            market,
            side,
            quantity,
            self.now,
            self.now + self.config.order_timeout_seconds * SECOND,
            purpose,
        )
        order.recent_volume_quantity = sum(
            (
                q
                for t, q in self.recent_volume[(symbol, market)]
                if self.now - self.config.participation_seconds * SECOND <= t < self.now
            ),
            D(0),
        )
        self.orders[order_id] = order
        self.native.submit(order, trade.price)
        self.order_rows.append(self._order_row(order, "submitted"))
        return True

    def _order_row(self, order: Order, action: str) -> dict:
        return dict(
            time_ns=self.now,
            strategy=self.strategy,
            action=action,
            **{k: str(v) if isinstance(v, D) else v for k, v in asdict(order).items()},
        )

    def _cancel(self, symbol: str, cause: str) -> None:
        for order in self._pending(symbol):
            self.native.cancel(order.order_id)
            order.status = "cancelled"
            self.order_rows.append(self._order_row(order, cause))

    def _tradable_spot(self, symbol: str) -> D:
        rule = self._rule(symbol, "spot")
        trade = self.trades.get((symbol, "spot"))
        if rule is None or trade is None:
            return D(0)
        q = floor_step(self.ledger.positions[symbol].spot, rule.step)
        return q if valid_quantity(q, trade.price, rule) else D(0)

    def _spot_is_dust(self, symbol: str) -> bool:
        p = self.ledger.positions[symbol]
        if p.spot <= 0:
            return True
        rule, trade = self._rule(symbol, "spot"), self.trades.get((symbol, "spot"))
        if rule is None or trade is None:
            return False
        q = floor_step(p.spot, rule.step)
        return q < rule.min_qty or q * trade.price < rule.min_notional

    def _finish_close(self, symbol: str) -> None:
        pair = self.pairs[symbol]
        if self.ledger.positions[symbol].short > 0 or not self._spot_is_dust(symbol):
            state = (
                State.CLOSING_PERP
                if self.ledger.positions[symbol].short > 0
                else State.CLOSING_SPOT
            )
            if pair.state != state:
                self._transition(symbol, state, "inventory_blocked_not_dust")
            return
        self.reservations[symbol] = D(0)
        pair.expiry = pair.next_leg_at = pair.correction_deadline = None
        pair.next_leg = ""
        pair.liquidation_pending = False
        pair.opened_at = None
        if pair.cooldown_required:
            pair.cooldown_until = self.now + self.config.cooldown_hours * HOUR
            self._transition(symbol, State.COOLDOWN, "unwind_complete")
        else:
            self._transition(symbol, State.FLAT, "ordinary_close_complete")
        pair.cooldown_required = False

    def _close(
        self, symbol: str, cause: str, cooldown: bool = True, liquidate: bool = False
    ) -> None:
        pair = self.pairs[symbol]
        pair.cooldown_required |= cooldown
        if pair.state in (State.CLOSING_PERP, State.CLOSING_SPOT, State.LIQUIDATING):
            if not liquidate or pair.liquidation_pending:
                return
        self._cancel(symbol, cause)
        pair.next_leg_at = pair.correction_deadline = pair.expiry = None
        pair.next_leg = ""
        pair.liquidation_pending |= liquidate
        p = self.ledger.positions[symbol]
        self._event(symbol, "close_requested", cause=cause, liquidation=liquidate)
        if p.short > 0:
            self._transition(symbol, State.LIQUIDATING if liquidate else State.CLOSING_PERP, cause)
            self._submit(
                symbol,
                "futures",
                "BUY",
                p.short,
                "liquidate" if pair.liquidation_pending else "close_perp",
            )
        elif (q := self._tradable_spot(symbol)) > 0:
            self._transition(symbol, State.CLOSING_SPOT, cause)
            self._submit(symbol, "spot", "SELL", q, "close_spot")
        else:
            self._finish_close(symbol)

    def _risk(self, symbol: str, periodic: bool = False) -> None:
        p, pair = self.ledger.positions[symbol], self.pairs[symbol]
        if not (p.spot > 0 or p.short > 0 or self._pending(symbol)):
            return
        if symbol in self.bad_symbols or any(
            self._rule(symbol, m) is None for m in ("spot", "futures")
        ):
            self._halt(f"Missing indispensable data/rules for open {symbol}")
            return
        if p.short and symbol in self.marks:
            try:
                cause = position_risk(
                    p, self.marks[symbol].close, self._rule(symbol, "futures"), self.config
                )
            except ValueError as exc:
                self._halt(f"Unverified maintenance coverage for {symbol}: {exc}")
                return
            if cause:
                self._close(symbol, cause, liquidate=cause == "liquidation")
                return
        if not all(self._rule(symbol, m).operational for m in ("spot", "futures")):
            self._close(symbol, "market_suspended")
            return
        if periodic:
            if any(
                (symbol, m) in self.trades
                and self.now - self.trades[(symbol, m)].event_time
                > self.config.inactivity_seconds * SECOND
                for m in ("spot", "futures")
            ):
                self._close(symbol, "real_market_inactivity")
                return
            if pair.basis_reference is not None and self._fresh(symbol):
                if self._observed_basis(symbol) - pair.basis_reference >= self.config.basis_exit:
                    self._close(symbol, "basis_widening")
                    return
        if pair.state == State.HOLDING and needs_hedge_correction(p, self.config):
            if p.spot == 0:
                self._close(symbol, "uncovered_short")
                return
            pair.correction_deadline = self.now + self.config.correction_seconds * SECOND
            self._transition(symbol, State.CORRECTING_HEDGE, "hedge_mismatch")
            self._correct(symbol)

    def _correct(self, symbol: str) -> None:
        p = self.ledger.positions[symbol]
        target = floor_step(p.spot, self._rule(symbol, "futures").step)
        delta = target - p.short
        if delta == 0 and hedge_error(p.spot, p.short) <= self.config.hedge_tolerance:
            self.pairs[symbol].correction_deadline = None
            self._transition(symbol, State.HOLDING, "hedge_corrected")
        elif delta:
            self._submit(symbol, "futures", "SELL" if delta > 0 else "BUY", abs(delta), "correct")

    def _debt_close(self) -> None:
        if self.ledger.debt <= 0:
            return
        for symbol in self.config.symbols:
            if self.ledger.positions[symbol].short > 0 or self._tradable_spot(symbol) > 0:
                self._close(symbol, "debt")
                break

    def _halt(self, reason: str) -> None:
        self.status = "incomplete_data"
        self.reasons.append(reason)
        self.stopped_at = self.now

    def _timeout(self, order: Order) -> None:
        self.native.cancel(order.order_id)
        order.status = "expired"
        self.order_rows.append(self._order_row(order, "timeout"))
        self._event(
            order.symbol,
            "attempt_failed",
            cause="timeout",
            purpose=order.purpose,
            order_id=order.order_id,
        )
        if order.purpose in ("close_perp", "liquidate", "close_spot"):
            quantity = (
                self.ledger.positions[order.symbol].short
                if order.market == "futures"
                else self._tradable_spot(order.symbol)
            )
            if quantity:
                self._submit(order.symbol, order.market, order.side, quantity, order.purpose)
            else:
                self._after_fill(order)
        elif order.purpose == "correct":
            self._correct(order.symbol)
        elif order.purpose in ("increase_spot", "reduce_perp"):
            self._failed_first_adjustment(order.symbol)
        else:
            self._close(order.symbol, "opening_or_second_leg_failed")

    def _failed_first_adjustment(self, symbol: str) -> None:
        self.reservations[symbol] = D(0)
        self.pairs[symbol].cooldown_until = self.now + self.config.cooldown_hours * HOUR
        self._transition(symbol, State.HOLDING, "rebalance_first_leg_failed")

    def _entry(self, symbol: str, equity_snapshot: D) -> str:
        pair = self.pairs[symbol]
        fc = self.forecasts.get(symbol)
        if pair.state == State.COOLDOWN and self.now >= pair.cooldown_until:
            self._transition(symbol, State.FLAT, "cooldown_elapsed")
        if pair.state != State.FLAT or self.now < pair.cooldown_until or self._pending(symbol):
            return "state_or_cooldown"
        if self.ledger.debt > 0 or self.status == "insolvent":
            return "debt_or_insolvency"
        if not fc or not fc.valid or not self._data_valid(symbol):
            return "invalid_or_stale_data"
        cost = cycle_cost(self._rule(symbol, "spot"), self._rule(symbol, "futures"), self.config)
        if self.funding_filter_enabled and fc.value <= cost:
            return "funding_not_above_cost"
        if not entry_basis(self._observed_basis(symbol), self.config):
            return "basis_outside_entry_range"
        p = self.ledger.positions[symbol]
        rule = self._rule(symbol, "spot")
        target = target_quantity(
            equity_snapshot, self.trades[(symbol, "spot")].price, p.spot, rule, self.config
        )
        quantity = floor_step(max(D(0), target - p.spot), rule.step)
        if quantity <= 0:
            return "no_positive_increment"
        needed = self._required(symbol, quantity)
        if needed > self._available(symbol):
            return "insufficient_free_funds"
        self.reservations[symbol] = needed
        pair.cycle_id = f"{symbol}-{self.now}"
        if not self._submit(symbol, "spot", "BUY", quantity, "open_spot"):
            self.reservations[symbol] = D(0)
            return "historical_quantity_filter"
        self._transition(symbol, State.OPENING_SPOT, "entry", self._pending(symbol)[0].order_id)
        return "accepted"

    def _required(self, symbol: str, quantity: D) -> D:
        return required_cash(
            quantity,
            self.trades[(symbol, "spot")].price,
            self.trades[(symbol, "futures")].price,
            self.marks[symbol].close,
            self._rule(symbol, "spot"),
            self._rule(symbol, "futures"),
            self.config,
        )

    def _renew(self, symbol: str, equity_snapshot: D) -> None:
        pair = self.pairs[symbol]
        if pair.state != State.HOLDING:
            return
        fc = self.forecasts.get(symbol)
        if (
            not self._data_valid(symbol)
            or not fc
            or not fc.valid
            or self.ledger.debt > 0
            or (self.funding_filter_enabled and fc.value <= 0)
        ):
            self._close(symbol, "holding_expiry", cooldown=False)
            return
        pair.expiry += self.config.holding_hours * HOUR
        self._event(symbol, "renewal", next_expiry=pair.expiry)
        p = self.ledger.positions[symbol]
        spot = self.trades[(symbol, "spot")].price
        if not needs_rebalance(p.spot * spot, equity_snapshot, self.config):
            return
        if equity_snapshot <= 0:
            self._close(symbol, "nonpositive_equity")
            return
        sr, fr = self._rule(symbol, "spot"), self._rule(symbol, "futures")
        target = target_quantity(equity_snapshot, spot, p.spot, sr, self.config)
        if target > p.spot:
            if self.now < pair.cooldown_until:
                self._event(symbol, "rebalance_skipped", cause="cooldown")
                return
            quantity = floor_step(target - p.spot, sr.step)
            needed = self._required(symbol, quantity)
            if needed > self._available(symbol):
                self._event(symbol, "rebalance_skipped", cause="insufficient_free_funds")
                return
            self.reservations[symbol] = needed
            sent = self._submit(symbol, "spot", "BUY", quantity, "increase_spot")
        else:
            pair.adjustment_quantity = floor_step(p.spot - target, sr.step)
            reduction = p.short - floor_step(target, fr.step)
            sent = self._submit(symbol, "futures", "BUY", reduction, "reduce_perp")
        if sent:
            self._transition(symbol, State.REBALANCING, "renewal_rebalance")

    def _next_leg(self, symbol: str) -> None:
        pair = self.pairs[symbol]
        purpose = pair.next_leg
        pair.next_leg_at = None
        pair.next_leg = ""
        p = self.ledger.positions[symbol]
        if purpose in ("open_perp", "increase_perp"):
            quantity = floor_step(p.spot, self._rule(symbol, "futures").step) - p.short
            sent = self._submit(symbol, "futures", "SELL", quantity, purpose)
            if not sent:
                self._close(symbol, "unhedgeable_quantity")
        elif purpose in ("close_spot", "reduce_spot"):
            quantity = (
                self._tradable_spot(symbol) if purpose == "close_spot" else pair.adjustment_quantity
            )
            if quantity <= 0:
                self._finish_close(symbol) if purpose == "close_spot" else self._complete_pair(
                    symbol, False
                )
            elif not self._submit(symbol, "spot", "SELL", quantity, purpose):
                self._close(symbol, "spot_adjustment_failed")

    def _complete_pair(self, symbol: str, opening: bool) -> None:
        p, pair = self.ledger.positions[symbol], self.pairs[symbol]
        self.reservations[symbol] = D(0)
        if hedge_error(p.spot, p.short) > self.config.hedge_tolerance or not self._fresh(symbol):
            self._close(symbol, "completion_hedge_or_freshness_failure")
            return
        pair.basis_reference = self._observed_basis(symbol)
        if opening:
            pair.expiry = self.now + self.config.holding_hours * HOUR
            pair.opened_at = self.now
        self._transition(
            symbol, State.HOLDING, "opening_complete" if opening else "rebalance_complete"
        )

    def _after_fill(self, order: Order) -> None:
        symbol, purpose = order.symbol, order.purpose
        pair = self.pairs[symbol]
        if purpose in ("open_spot", "increase_spot"):
            pair.next_leg_at = self.now + self.config.leg_delay_seconds * SECOND
            pair.next_leg = "open_perp" if purpose == "open_spot" else "increase_perp"
            self.reservations[symbol] = max(
                D(0),
                self.reservations[symbol] - order.quantity * self.trades[(symbol, "spot")].price,
            )
            if purpose == "open_spot":
                self._transition(symbol, State.OPENING_PERP, "spot_filled_waiting_hedge")
        elif purpose in ("open_perp", "increase_perp", "reduce_spot"):
            self._complete_pair(symbol, purpose == "open_perp")
        elif purpose in ("close_perp", "liquidate", "reduce_perp"):
            pair.next_leg_at = self.now + self.config.leg_delay_seconds * SECOND
            pair.next_leg = "reduce_spot" if purpose == "reduce_perp" else "close_spot"
            if purpose != "reduce_perp":
                self._transition(symbol, State.CLOSING_SPOT, "perpetual_closed_waiting_spot")
        elif purpose == "close_spot":
            self._finish_close(symbol)
        elif purpose == "correct":
            p = self.ledger.positions[symbol]
            if hedge_error(p.spot, p.short) <= self.config.hedge_tolerance:
                pair.correction_deadline = None
                self._transition(symbol, State.HOLDING, "hedge_corrected")

    def _execute(self, order: Order, reference: D, trade_id: str) -> None:
        rule = self._rule(order.symbol, order.market)
        if rule is None or not rule.operational:
            return
        if order.purpose in (
            "open_spot",
            "open_perp",
            "increase_spot",
            "increase_perp",
        ) and not self._fresh(order.symbol):
            if order.purpose == "increase_spot":
                self._cancel(order.symbol, "stale_data_at_fill")
                self._event(
                    order.symbol,
                    "attempt_failed",
                    cause="stale_data_at_fill",
                    purpose=order.purpose,
                )
                self._failed_first_adjustment(order.symbol)
            else:
                self._close(order.symbol, "stale_data_at_fill")
            return
        price, rounding = execution_price(reference, order.side, rule, self.config)
        if not valid_quantity(order.quantity, price, rule):
            return
        fill = Fill(
            f"fill-{order.order_id}",
            order.order_id,
            order.symbol,
            order.market,
            order.side,
            order.quantity,
            price,
            reference,
            self.now,
            trade_id,
            rule.taker_fee * self.config.cost_multiplier,
            order.purpose == "liquidate",
        )
        trial = deepcopy(self.ledger)
        try:
            if not trial.apply_fill(fill, rule, self.marks[order.symbol].close):
                raise ValueError("Fill cannot be funded or exceeds actual inventory")
            if (order.market == "spot" and order.side == "BUY") or (
                order.market == "futures" and order.side == "SELL"
            ):
                reserved_others = sum(
                    (v for s, v in self.reservations.items() if s != order.symbol), D(0)
                )
                if trial.free_spot + trial.free_futures < reserved_others:
                    raise ValueError("Fill would spend another asset's reserved cash")
        except ValueError as exc:
            self.native.cancel(order.order_id)
            order.status = "rejected"
            self.order_rows.append(self._order_row(order, "insufficient_funds"))
            self._event(order.symbol, "attempt_failed", cause=str(exc), purpose=order.purpose)
            if order.purpose in ("increase_spot", "reduce_perp"):
                self._failed_first_adjustment(order.symbol)
            else:
                self._close(order.symbol, "fill_unaffordable")
            return
        self.native.execute(fill)
        self.ledger = trial
        order.status = "filled"
        self.order_rows.append(self._order_row(order, "filled"))
        volume = order.recent_volume_quantity
        row = {k: str(v) if isinstance(v, D) else v for k, v in asdict(fill).items()}
        row.update(
            strategy=self.strategy,
            rounding_cost=str(rounding * fill.quantity),
            participation=str(fill.quantity / volume) if volume > 0 else None,
            recent_volume_quantity=str(volume),
            participation_window_seconds=self.config.participation_seconds,
            purpose=order.purpose,
        )
        self.fills.append(row)
        if order.market == "spot" and order.side == "BUY":
            self.native_base_fees[order.symbol] += fill.quantity * fill.fee_rate
        self._reconcile_native(order.symbol)
        self._after_fill(order)
        self._position_row(order.symbol)
        self._risk(order.symbol)
        self._debt_close()

    def _reconcile_native(self, symbol: str) -> None:
        p = self.ledger.positions[symbol]
        for market, expected in (
            ("spot", p.spot + self.native_base_fees[symbol]),
            ("futures", -p.short),
        ):
            if (
                abs(self.native.quantity(symbol, market) - expected)
                > self.config.accounting_tolerance
            ):
                raise ArithmeticError(f"Native/domain position mismatch for {symbol} {market}")
        self.native_reconciliation_count += 1

    def process(self, time_ns: int, records: list, native) -> None:
        if self.stopped_at is not None or time_ns >= self.end:
            return
        self.now, self.native = time_ns, native
        if time_ns >= self.start:
            elapsed = D(time_ns - self.last_economic_time) / D(SECOND)
            any_invested = False
            for symbol, p in self.ledger.positions.items():
                invested = p.spot > 0 or p.short > 0
                any_invested |= invested
                if invested:
                    self.durations[f"{symbol}_invested_seconds"] += elapsed
                if invested and hedge_error(p.spot, p.short) > self.config.hedge_tolerance:
                    self.durations[f"{symbol}_unhedged_seconds"] += elapsed
                if self.pairs[symbol].state == State.COOLDOWN:
                    self.durations[f"{symbol}_cooldown_seconds"] += elapsed
            self.durations["portfolio_invested_seconds" if any_invested else "cash_seconds"] += (
                elapsed
            )
            self.last_economic_time = time_ns
        trades, settlements = [], []
        # Phase 1: all data at this timestamp, in stable symbol/event order.
        for r in records:
            if isinstance(r, Trade):
                self.trades[(r.symbol, r.market)] = r
                trades.append(r)
                volume = self.recent_volume[(r.symbol, r.market)]
                volume.append((r.event_time, r.quantity))
                while (
                    volume and volume[0][0] < self.now - self.config.participation_seconds * SECOND
                ):
                    volume.popleft()
            elif isinstance(r, Mark):
                self.marks[r.symbol] = r
            elif isinstance(r, Funding):
                if self.config.analysis_mode == "prescribed_research":
                    # Funding sorts before Mark at equal timestamps. The candle
                    # just closed at this boundary is nevertheless available.
                    candidate = next(
                        (m for m in records if isinstance(m, Mark) and m.symbol == r.symbol),
                        self.marks.get(r.symbol),
                    )
                    try:
                        r = resolve_funding_mark(r, candidate, self.config)
                    except ValueError as exc:
                        self._halt(str(exc))
                        return
                key = (r.symbol, r.funding_time)
                economic = (r.funding_rate, r.interval_hours, r.settlement_mark_price)
                if key in self.funding_seen:
                    if self.funding_seen[key] != economic:
                        self._halt("Conflicting funding duplicates")
                    continue
                self.funding_seen[key] = economic
                self.history[r.symbol].append(r)
                self.all_funding.append(r)
                settlements.append(r)
                available = max(
                    r.available_at, r.funding_time + self.config.signal_delay_seconds * SECOND
                )
                self.signal_due[(r.symbol, r.funding_time)] = available
            elif isinstance(r, DataGap):
                if r.resolved:
                    self.bad_symbols.discard(r.symbol)
                else:
                    self.bad_symbols.add(r.symbol)
                    self.history[r.symbol].clear()
                    self.status = "incomplete_data"
                    self.reasons.append(r.reason)
        if self.now < self.start:
            for key, due in list(self.signal_due.items()):
                if due <= self.now:
                    symbol, anchor = key
                    self.forecasts[symbol] = forecast(
                        self.history[symbol], anchor, self.now, self.config
                    )
                    del self.signal_due[key]
            return
        # Phase 2: funding settles on the position BEFORE every fill at this time.
        for r in settlements:
            if self.ledger.positions[r.symbol].short:
                if r.settlement_mark_price is None:
                    self._halt(f"Missing funding settlement mark: {r.symbol} {iso(self.now)}")
                    return
                self.ledger.apply_funding(r)
        # Phases 3/4: liquidation, debt and risk invalidate exposure increases.
        periodic = self.now // (60 * SECOND) > self.last_minute
        for symbol in self.config.symbols:
            self._risk(symbol, periodic)
        if self.stopped_at is not None:
            return
        self._debt_close()
        due_renewals = []
        for symbol, pair in self.pairs.items():
            if pair.correction_deadline is not None and self.now >= pair.correction_deadline:
                if (
                    hedge_error(
                        self.ledger.positions[symbol].spot, self.ledger.positions[symbol].short
                    )
                    > self.config.hedge_tolerance
                ):
                    self._close(symbol, "hedge_correction_deadline")
                else:
                    pair.correction_deadline = None
                    self._transition(symbol, State.HOLDING, "hedge_corrected")
            for order in list(self._pending(symbol)):
                if self.now >= order.deadline:
                    self._timeout(order)
            if pair.next_leg_at is not None and pair.next_leg_at <= self.now:
                self._next_leg(symbol)
            if (
                pair.state in (State.CLOSING_PERP, State.CLOSING_SPOT, State.LIQUIDATING)
                and not self._pending(symbol)
                and pair.next_leg_at is None
            ):
                p = self.ledger.positions[symbol]
                if p.short > 0:
                    self._submit(
                        symbol,
                        "futures",
                        "BUY",
                        p.short,
                        "liquidate" if pair.liquidation_pending else "close_perp",
                    )
                elif (q := self._tradable_spot(symbol)) > 0:
                    self._submit(symbol, "spot", "SELL", q, "close_spot")
                else:
                    self._finish_close(symbol)
            if pair.expiry is not None and pair.expiry <= self.now:
                due_renewals.append(symbol)
        # Phase 5: delayed forecasts, then joint-equity decisions with BTC first.
        new_signals = []
        for (symbol, anchor), due in sorted(list(self.signal_due.items())):
            if due <= self.now:
                del self.signal_due[(symbol, anchor)]
                if due < self.start:
                    continue
                fc = forecast(self.history[symbol], anchor, self.now, self.config)
                self.forecasts[symbol] = fc
                new_signals.append((symbol, fc))
        snapshot = self.equity()
        for symbol in self.config.symbols:
            if any(self._rule(symbol, m) is None for m in ("spot", "futures")):
                self.status = "incomplete_data"
                reason = f"Historical market rules unavailable for {symbol}"
                if reason not in self.reasons:
                    self.reasons.append(reason)
        for symbol in due_renewals:
            self._renew(symbol, snapshot)
        for symbol, fc in new_signals:
            reason = self._entry(symbol, snapshot)
            rules_valid = all(self._rule(symbol, m) is not None for m in ("spot", "futures"))
            self.signals.append(
                dict(
                    time_ns=self.now,
                    strategy=self.strategy,
                    symbol=symbol,
                    anchor=fc.anchor,
                    history_start=fc.history_start,
                    forecast=str(fc.value),
                    no_change=str(fc.no_change),
                    valid=fc.valid,
                    forecast_reason=fc.reason,
                    decision=reason,
                    estimated_cycle_cost=str(
                        cycle_cost(
                            self._rule(symbol, "spot"), self._rule(symbol, "futures"), self.config
                        )
                    )
                    if rules_valid
                    else None,
                    basis=str(self._observed_basis(symbol)) if self._fresh(symbol) else None,
                )
            )
        # Phase 6: the first eligible trade; an order sent now cannot use this batch.
        for trade in trades:
            for order in list(self._pending(trade.symbol)):
                if eligible_trade(order, trade):
                    if self.config.execution_model == "vwap":
                        observe_vwap(order, trade, self.config)
                    else:
                        self._execute(order, trade.price, trade.trade_id)
        if self.config.execution_model == "vwap":
            for order in list(self.orders.values()):
                if (
                    order.status == "pending"
                    and self.now == order.submitted_at + self.config.vwap_seconds * SECOND
                    and order.vwap_quantity > 0
                ):
                    self._execute(
                        order,
                        order.vwap_notional / order.vwap_quantity,
                        ",".join(order.reference_ids),
                    )
        if periodic:
            self.last_minute = self.now // (60 * SECOND)
            if self.now % (60 * SECOND) == 0:
                self._opportunity()
        if (self.now + 1) % DAY == 0 or self.now == self.end - 1:
            self._daily()
        if (
            self.equity() <= 0
            and all(p.short == 0 for p in self.ledger.positions.values())
            and not any(self._tradable_spot(s) for s in self.config.symbols)
        ):
            self.status = "insolvent"

    def _opportunity(self) -> None:
        for symbol in self.config.symbols:
            fc = self.forecasts.get(symbol)
            complete = (
                symbol not in self.bad_symbols
                and symbol in self.marks
                and fc is not None
                and fc.valid
                and all(self._rule(symbol, m) is not None for m in ("spot", "futures"))
            )
            eligible = (
                complete
                and self._data_valid(symbol)
                and entry_basis(self._observed_basis(symbol), self.config)
                and fc.value
                > cycle_cost(self._rule(symbol, "spot"), self._rule(symbol, "futures"), self.config)
            )
            self.opportunities.append(
                dict(
                    time_ns=self.now,
                    symbol=symbol,
                    complete=complete,
                    eligible=bool(eligible),
                    value=str(fc.value if eligible else D(0)),
                )
            )

    def _daily(self) -> None:
        if self.now // DAY == self.last_daily:
            return
        self.last_daily = self.now // DAY
        values = self.ledger.reconcile(self.spot_prices(), self.mark_prices())
        self.daily.append(
            dict(
                time_ns=self.now,
                strategy=self.strategy,
                symbol="PORTFOLIO",
                equity=str(values["equity"]),
                free_spot=str(self.ledger.free_spot),
                free_futures=str(self.ledger.free_futures),
                debt=str(self.ledger.debt),
                status=self.status,
                partial_day=(self.now + 1) % DAY != 0,
                **{
                    f"{s}_spot_price": str(self.trades[(s, "spot")].price)
                    for s in self.config.symbols
                    if (s, "spot") in self.trades
                },
                **{f"{s}_mark": str(m.close) for s, m in self.marks.items()},
                **{
                    f"{s}_{k}": str(v)
                    for s, p in self.ledger.positions.items()
                    for k, v in asdict(p).items()
                },
            )
        )
        for symbol in self.config.symbols:
            self._position_row(symbol)

    def next_timer(self, now: int) -> int | None:
        if self.stopped_at is not None:
            return None
        due = list(self.signal_due.values())
        if hasattr(self.rules, "transition_times"):
            due.extend(self.rules.transition_times(now + 1, self.end))
        if now < self.start:
            due.append(self.start)
        else:
            due.extend(
                ((now // (60 * SECOND) + 1) * 60 * SECOND, (now // DAY + 1) * DAY - 1, self.end - 1)
            )
        due.extend(o.deadline for o in self.orders.values() if o.status == "pending")
        if self.config.execution_model == "vwap":
            due.extend(
                o.submitted_at + self.config.vwap_seconds * SECOND
                for o in self.orders.values()
                if o.status == "pending"
            )
        for p in self.pairs.values():
            due.extend(t for t in (p.next_leg_at, p.expiry, p.correction_deadline) if t is not None)
        return min((t for t in due if now < t < self.end), default=None)

    def checkpoint(self, path: Path) -> None:
        state = {
            k: v
            for k, v in self.__dict__.items()
            if k not in ("native", "rules", "config", "ledger")
        }
        payload = {
            "config": self.config.to_dict(),
            "state": encode(state),
            "rules_hash": self._rules_hash(self.rules),
            "code_hash": self._code_hash(),
        }
        # Config is encoded explicitly above, not as an arbitrary importable type.
        ledger_state = dict(self.ledger.__dict__)
        ledger_state.pop("config")
        payload["ledger"] = encode(ledger_state)
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        wrapper = {"sha256": hashlib.sha256(text.encode()).hexdigest(), "payload": payload}
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError("Checkpoint files are immutable; use a new path")
        path.write_text(json.dumps(wrapper, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_checkpoint(cls, path: Path, config: Config, rules, inputs: dict | None = None):
        wrapper = json.loads(Path(path).read_text(encoding="utf-8"))
        payload = wrapper["payload"]
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if hashlib.sha256(text.encode()).hexdigest() != wrapper["sha256"]:
            raise ValueError("Checkpoint checksum mismatch")
        if payload["config"] != config.to_dict():
            raise ValueError("Checkpoint configuration differs")
        if payload["rules_hash"] != cls._rules_hash(rules):
            raise ValueError("Checkpoint market rules differ")
        if payload["code_hash"] != cls._code_hash():
            raise ValueError("Checkpoint code differs")
        state = decode(payload["state"])
        if state["inputs"] != dict(inputs or {}):
            raise ValueError("Checkpoint input hashes differ")
        obj = cls(config, rules, state["strategy"], state["funding_filter_enabled"], inputs)
        obj.__dict__.update(state)
        obj.ledger.__dict__.update(decode(payload["ledger"]))
        for name in ("reservations", "native_base_fees", "durations"):
            setattr(obj, name, defaultdict(lambda: D(0), getattr(obj, name)))
        obj.history = defaultdict(list, obj.history)
        obj.recent_volume = defaultdict(deque, obj.recent_volume)
        obj.resuming = True
        return obj

    @staticmethod
    def _rules_hash(rules) -> str:
        records = getattr(rules, "records", getattr(rules, "items", None))
        if records is None:
            raise ValueError("Checkpoint requires serializable market rules")
        payload = {
            "records": encode(records),
            "allow_synthetic": getattr(rules, "allow_synthetic", False),
            "allow_prescribed": getattr(rules, "allow_prescribed", False),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _code_hash() -> str:
        digest = hashlib.sha256()
        base = Path(__file__).parent
        for path in sorted(base.rglob("*.py")):
            digest.update(path.relative_to(base).as_posix().encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()

    def _seed_native(self, native) -> None:
        """Reconstruct native position carriers without a second economic movement."""
        for symbol, p in self.ledger.positions.items():
            for market, q, price in (
                (
                    "spot",
                    p.spot + self.native_base_fees[symbol],
                    self.spot_prices().get(symbol, D(1)),
                ),
                ("futures", p.short, p.average),
            ):
                if not q:
                    continue
                side = "BUY" if market == "spot" else "SELL"
                order_id = f"seed-{symbol}-{market}"
                order = Order(
                    order_id,
                    symbol,
                    market,
                    side,
                    q,
                    self.now,
                    self.now + SECOND,
                    "checkpoint_seed",
                )
                native.submit(order, price)
                seed_price = D(str(native.instruments[(symbol, market)].make_price(price)))
                native.execute(
                    Fill(
                        order_id,
                        order_id,
                        symbol,
                        market,
                        side,
                        q,
                        seed_price,
                        seed_price,
                        self.now,
                        "checkpoint_state",
                        D(0),
                    )
                )
        native.fill_events.clear()
        for order in self.orders.values():
            if order.status == "pending":
                native.submit(order, self.trades[(order.symbol, order.market)].price)

    def run(self, records, chunk_size: int = 10000, stop_at: int | None = None):
        cutoff = self.end - 1 if stop_at is None else min(stop_at, self.end - 1)
        native_config = self.config.changed(end=iso(cutoff + 1))
        native = NautilusAdapter(native_config)
        resumed = getattr(self, "resuming", False)
        resume_time = self.now
        prior_fills = getattr(self, "native_fill_count", 0)

        def batches():
            last = -1
            if resumed:
                yield resume_time, []
                last = resume_time
            filtered = (r for r in records if not resumed or event_time(r) > resume_time)
            for t, rows in group_events(filtered):
                if t > cutoff:
                    break
                yield t, rows
                last = t
            if last < cutoff:
                yield cutoff, []

        def callback(t, rows, adapter):
            if resumed and t == resume_time:
                self._seed_native(adapter)
                self.resuming = False
            else:
                self.process(t, rows, adapter)

        try:
            native.replay(batches(), callback, chunk_size=chunk_size, next_timer=self.next_timer)
            self.native_fill_count = prior_fills + len(native.fill_events)
            if self.stopped_at is None and self.now < cutoff:
                raise RuntimeError("Replay failed to reach the sample cutoff timer")
        finally:
            self.native = None
            native.dispose()
        return self

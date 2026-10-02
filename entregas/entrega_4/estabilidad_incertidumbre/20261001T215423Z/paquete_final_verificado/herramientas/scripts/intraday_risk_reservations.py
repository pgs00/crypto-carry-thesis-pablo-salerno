"""Conservative cash commitments derived from persisted observations, never replay.

``reservation_grid(run_path, times_ns, phases=None)`` accepts ``post`` (end of
timestamp, the default), ``pre`` (before that timestamp), and ``intermediate``.
Unknown commitments are NaN with bounds, never zero. Decimal validates source
diagnostics; returned money arrays are floats for joining the minute grid.

The frozen strategy's full spot fill decrements its reservation by order gross
quantity times its current spot close. Event position snapshots usually omit
that close, so the remaining amount is bounded until a later diagnostic or
release identifies it. No future observation is backfilled to an earlier time.
"""

from __future__ import annotations

import tomllib
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

D = Decimal
ZERO = D(0)
RELEASES = {
    "unwind_complete", "ordinary_close_complete", "rebalance_first_leg_failed",
    "opening_complete", "rebalance_complete",
}
ASSIGNING_ORDERS = {"open_spot", "increase_spot", "reduce_perp", "reduce_spot", "increase_perp"}
FIELDS = {
    "signals": {"time_ns", "symbol", "decision", "available_cash", "budget_required_cash", "sizing_feasible"},
    "renewal_diagnostics": {"time_ns", "symbol", "state_after", "available_cash", "budget_required_cash", "sizing_feasible"},
    "orders": {"time_ns", "symbol", "order_id", "status", "action", "purpose", "record_type", "cancel_requested_at", "quantity", "market", "side"},
    "fills": {"time_ns", "symbol", "order_id", "purpose", "partial", "remaining_quantity"},
    "risk_events": {"time_ns", "symbol", "kind", "cause"},
    "ledger": {"time_ns", "free_spot", "free_futures", "debt"},
    "positions": {"time_ns", "symbol", "spot_price"},
}


def _yes(value) -> bool:
    return value is True or str(value).lower() == "true"


def _tables(run: Path) -> dict:
    result = {}
    for name, fields in FIELDS.items():
        path = run / f"{name}.parquet"
        if not path.is_file():
            raise ValueError(f"Missing reservation evidence: {path}")
        schema = pq.read_schema(path)
        rows = pq.read_table(path, columns=[key for key in schema.names if key in fields]).to_pylist()
        if name == "orders":
            rows = [row for row in rows if row.get("record_type", "event") == "event"]
        # Final positions can be appended after event snapshots; they are used
        # only for prices at the very same timestamp, never as a state stream.
        if name != "positions" and any(a["time_ns"] > b["time_ns"] for a, b in zip(rows, rows[1:])):
            raise ValueError(f"Nonmonotonic reservation source: {name}")
        result[name] = rows
    return result


def _history(run: Path) -> tuple[dict, dict]:
    config = tomllib.loads((run / "effective_config.toml").read_text(encoding="utf-8"))
    symbols = config["symbols"]
    tolerance = D(config.get("accounting_tolerance", "1E-8"))
    grouped = defaultdict(lambda: defaultdict(list))
    for name, rows in _tables(run).items():
        for row in rows:
            grouped[int(row["time_ns"])][name].append(row)
    bounds = {symbol: [ZERO, ZERO, "verified_no_reservation"] for symbol in symbols}
    tracked = {symbol: False for symbol in symbols}
    latest_orders = {}
    cash, debt = D(config["capital"]), ZERO
    columns = defaultdict(list)
    checks = {"diagnostics_checked": 0, "diagnostics_resolved_unknown": 0,
              "accepted_assignments": 0, "renewal_assignments": 0}

    def totals():
        lo = sum((value[0] for value in bounds.values()), ZERO)
        hi = sum((value[1] for value in bounds.values()), ZERO)
        reason = next((value[2] for value in bounds.values() if value[0] != value[1]),
                      "verified_no_reservation" if hi == 0 else "verified_reservation")
        pending = [row for row in latest_orders.values() if row["status"] == "pending"]
        # These closing/correction orders have no explicit strategy reservation.
        # Their future execution loss/fee is unknown until the persisted fill.
        unpriced = any(row.get("market") == "futures"
                       and row.get("purpose") in {"close_perp", "liquidate", "correct"}
                       for row in pending)
        if unpriced:
            hi = D("Infinity")
            reason = "unpriced_pending_futures_commitment"
        return lo, hi, reason, len(pending), unpriced

    def append(moment, *, interim=None):
        lo, hi, reason, pending, unpriced = totals()
        known = lo == hi and not unpriced
        spendable = max(ZERO, cash - debt)
        values = dict(time_ns=moment, reserved_cash=float(lo) if known else np.nan,
                      reserved_cash_lower=float(lo), reserved_cash_upper=float(hi),
                      available_known=known, reason=reason, pending_orders_count=pending,
                      cash_available_lower=float(max(ZERO, spendable - hi)),
                      cash_available_upper=float(max(ZERO, spendable - lo)))
        for key, value in values.items():
            columns[key].append(value)
        if interim is None:
            interim = values
        for key in values:
            if key != "time_ns":
                columns[f"intermediate_{key}"].append(interim[key])

    append(np.iinfo(np.int64).min)
    for moment in sorted(grouped):
        groups = grouped[moment]
        pre_lo, pre_hi, _, pre_pending, _ = totals()
        cash_candidates = [max(ZERO, cash - debt)]
        envelope_hi = {symbol: bounds[symbol][1] for symbol in symbols}
        envelope_lo = {symbol: bounds[symbol][0] for symbol in symbols}
        reserve_activity = False

        def assign_bound(symbol, lo, hi, reason):
            nonlocal reserve_activity
            if symbol not in bounds or lo < 0 or hi < lo:
                raise ValueError(f"Invalid reservation bound for {symbol} at {moment}")
            reserve_activity = True
            envelope_lo[symbol] = min(envelope_lo[symbol], lo)
            envelope_hi[symbol] = max(envelope_hi[symbol], hi)
            bounds[symbol] = [lo, hi, reason]

        # Orders retain their physical event order. Final report copies were
        # filtered out; a deferred cancel remains pending.
        for row in groups["orders"]:
            latest_orders[row["order_id"]] = row
        for row in groups["ledger"]:
            cash = D(row["free_spot"]) + D(row["free_futures"])
            debt = D(row["debt"])
            cash_candidates.append(max(ZERO, cash - debt))

        same_time_prices = defaultdict(set)
        for row in groups["positions"]:
            if row.get("spot_price") not in (None, ""):
                same_time_prices[row["symbol"]].add(D(row["spot_price"]))
        for row in groups["fills"]:
            symbol, purpose = row["symbol"], row["purpose"]
            full = not _yes(row.get("partial")) and D(row.get("remaining_quantity") or "0") == 0
            order = latest_orders.get(row["order_id"])
            cancelled = order is not None and order.get("cancel_requested_at") not in (None, "", "None")
            if not full or cancelled:
                continue
            if purpose in {"open_spot", "increase_spot"}:
                lo, hi, _ = bounds[symbol]
                prices = same_time_prices[symbol]
                if order is not None and len(prices) == 1:
                    reduction = D(order["quantity"]) * next(iter(prices))
                    assign_bound(symbol, max(ZERO, lo - reduction), max(ZERO, hi - reduction),
                                 "verified_reservation" if lo == hi else "bounded_reservation")
                else:
                    assign_bound(symbol, ZERO, hi, "missing_spot_close_at_full_fill")
            elif purpose in {"open_perp", "increase_perp", "reduce_spot"}:
                assign_bound(symbol, ZERO, ZERO, "verified_no_reservation")
                tracked[symbol] = False
        for row in groups["risk_events"]:
            if row.get("kind") == "transition" and row.get("cause") in RELEASES:
                assign_bound(row["symbol"], ZERO, ZERO, "verified_no_reservation")
                tracked[row["symbol"]] = False

        def diagnostic(row):
            if row.get("available_cash") in (None, ""):
                return
            other = [symbol for symbol in symbols if symbol != row["symbol"]]
            observed = cash - D(row["available_cash"])
            lower = sum((bounds[symbol][0] for symbol in other), ZERO)
            upper = sum((bounds[symbol][1] for symbol in other), ZERO)
            if observed < lower - tolerance or observed > upper + tolerance:
                raise ValueError(f"available_cash inconsistent at {moment} {row['symbol']}: "
                                 f"other reservations observed={observed}, derived=[{lower},{upper}]")
            checks["diagnostics_checked"] += 1
            uncertain = [symbol for symbol in other if bounds[symbol][0] != bounds[symbol][1]]
            if len(uncertain) == 1:
                symbol = uncertain[0]
                known_other = sum((bounds[name][0] for name in other if name != symbol), ZERO)
                exact = min(bounds[symbol][1], max(bounds[symbol][0], observed - known_other))
                assign_bound(symbol, exact, exact, "verified_by_available_cash")
                checks["diagnostics_resolved_unknown"] += 1

        def assign(row, category):
            if row.get("budget_required_cash") in (None, "") or not _yes(row.get("sizing_feasible", True)):
                assign_bound(row["symbol"], ZERO, max(ZERO, cash), "missing_reservation_assignment")
            else:
                amount = D(row["budget_required_cash"])
                assign_bound(row["symbol"], amount, amount, "verified_reservation")
            tracked[row["symbol"]] = True
            checks[category] += 1

        renewal_symbols = {row["symbol"] for row in groups["risk_events"]
                           if row.get("kind") == "transition" and row.get("cause") == "renewal_rebalance"}
        for row in groups["renewal_diagnostics"]:
            diagnostic(row)
            if row["symbol"] in renewal_symbols:
                assign(row, "renewal_assignments")
        for row in groups["signals"]:
            diagnostic(row)
            if row.get("decision") == "accepted":
                assign(row, "accepted_assignments")
        for row in groups["orders"]:
            symbol = row["symbol"]
            if row.get("action") == "submitted" and row.get("purpose") in ASSIGNING_ORDERS and not tracked[symbol]:
                # A first-leg order without its sizing diagnostic cannot make
                # cash appear freely redistributable merely because a table is missing.
                assign_bound(symbol, ZERO, max(bounds[symbol][1], max(ZERO, cash)), "missing_reservation_assignment")
                tracked[symbol] = True

        lo, hi, reason, pending, unpriced = totals()
        if reserve_activity or unpriced or pending != pre_pending:
            lower = min(pre_lo, lo, sum(envelope_lo.values(), ZERO))
            upper = max(pre_hi, hi, sum(envelope_hi.values(), ZERO))
            interim = dict(reserved_cash=np.nan, reserved_cash_lower=float(lower),
                           reserved_cash_upper=float(upper), available_known=False,
                           reason="ambiguous_simultaneous_phase", pending_orders_count=-1,
                           cash_available_lower=float(max(ZERO, min(cash_candidates) - upper)),
                           cash_available_upper=float(max(ZERO, max(cash_candidates) - lower)))
        else:
            known = lo == hi
            interim = dict(reserved_cash=float(lo) if known else np.nan,
                           reserved_cash_lower=float(lo), reserved_cash_upper=float(hi),
                           available_known=known, reason=reason, pending_orders_count=pending,
                           cash_available_lower=float(max(ZERO, min(cash_candidates) - hi)),
                           cash_available_upper=float(max(ZERO, max(cash_candidates) - lo)))
        append(moment, interim=interim)
    return {key: np.asarray(values, dtype=object if key.endswith("reason") else None)
            for key, values in columns.items()}, checks


def reservation_grid(run_path, times_ns, phases=None) -> dict:
    """Return commitments and availability bounds, preserving query order.

    ``available_known`` refers to the commitment amount, not future execution
    prices. ``cash_available_*`` deduct current debt as well as reservations.
    An unpriced futures closing/correction commitment has an infinite upper
    liability bound, while its available-cash bounds remain finite [0, cash].
    ``pending_orders_count=-1`` means the intermediate cross-table phase is not
    identifiable. ``validation`` records actual diagnostic comparisons.
    """
    times = np.asarray(times_ns, dtype=np.int64)
    if times.ndim != 1:
        raise ValueError("times_ns must be one-dimensional")
    phase = np.full(len(times), "post", dtype="U12") if phases is None else np.asarray(phases)
    if phase.shape != times.shape or not np.isin(phase, ["pre", "post", "intermediate"]).all():
        raise ValueError("phases must match times and contain pre/post/intermediate")
    history, validation = _history(Path(run_path))
    indices = np.searchsorted(history["time_ns"], times, side="right") - 1
    pre = phase == "pre"
    indices[pre] = np.searchsorted(history["time_ns"], times[pre], side="left") - 1
    if (indices < 0).any():
        raise ValueError("times outside supported int64 range")
    result = {key: values[indices].copy() for key, values in history.items()
              if key != "time_ns" and not key.startswith("intermediate_")}
    at_exact = history["time_ns"][indices] == times
    middle = (phase == "intermediate") & at_exact
    for key in result:
        result[key][middle] = history[f"intermediate_{key}"][indices[middle]]
    result["validation"] = validation
    return result

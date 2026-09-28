"""Offline execution arithmetic from orders, fills, ledger and authenticated minute windows.

Builder and verifier deliberately share these routines; this is not an independent engine.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal as D

from crypto_carry.config import SECOND, iso
from crypto_carry.costs import execution_price, floor_step, valid_quantity
from crypto_carry.data.market_calendar import closure_for_minute
from crypto_carry.data.prescribed import prescribed_rules
from scripts.return_capital.common import number

TOL = D("1E-8")


def same(actual, expected, label, tolerance=TOL):
    if abs(number(actual)-number(expected)) > tolerance:
        raise ValueError(f"{label}: {actual} != {expected}")


def is_true(value):
    return value in (True, "True", "true", 1, "1")


def key(row):
    return row["symbol"], row["market"], int(row.get("window_start", row.get("open_time")))


def audit_execution(config, orders, fills, ledger, windows):
    rules = prescribed_rules(config)
    window_map = {key(r): r for r in windows}
    if len(window_map) != len(windows):
        raise ValueError("Duplicate source window denominator")
    ledger_map = {r["event_id"]: r for r in ledger if str(r["event_id"]).startswith("fill:")}
    if len(ledger_map) != sum(str(r["event_id"]).startswith("fill:") for r in ledger):
        raise ValueError("Duplicate ledger fill identity")
    if len({f["fill_id"] for f in fills}) != len(fills):
        raise ValueError("Duplicate fill identity")
    grouped_orders, grouped_fills, capacity = defaultdict(list), defaultdict(list), {}
    for row in orders:
        grouped_orders[row["order_id"]].append(row)
    fill_audit = []
    for fill in fills:
        oid, fid = fill["order_id"], fill["fill_id"]
        if oid not in grouped_orders:
            raise ValueError("Fill has no authenticated order")
        k = key(fill)
        window = window_map.get(k)
        if window is None or not is_true(window["present"]):
            raise ValueError("Executed fill has no source volume window")
        volume, quote = number(window["base_volume"]), number(window["quote_volume"])
        if volume <= 0 or quote <= 0:
            raise ValueError("Execution on zero or invalid volume")
        q, price, fee = number(fill["quantity"]), number(fill["price"]), number(fill["fee_rate"])
        rule = rules.get(fill["symbol"], fill["market"], int(fill["time_ns"]))
        if rule is None or not valid_quantity(q, price, rule):
            raise ValueError("Executed quantity violates prescribed rule")
        same(fill["reference_price"], quote/volume, "VWAP reference", D("1E-20"))
        expected, rounding = execution_price(quote/volume, fill["side"], rule, config)
        same(price, expected, "Adverse execution price", D(0))
        same(fee, rule.taker_fee*config.cost_multiplier, "Scenario fee", D(0))
        same(fill["slippage_rate"], config.slippage*config.cost_multiplier, "Slippage", D(0))
        same(fill["window_base_volume"], volume, "Window denominator", D(0))
        same(fill["window_quote_volume"], quote, "Window quote volume", D(0))
        if int(fill["time_ns"]) != int(window["end_time"]) or int(fill["window_end"]) != int(window["end_time"]):
            raise ValueError("Fill timestamp differs from eligible window end")
        ordinary_fee = q*price*fee
        special = q*price*rule.liquidation_fee if is_true(fill.get("liquidation")) else D(0)
        if is_true(fill.get("liquidation")) and not rule.liquidation_regular_fee:
            ordinary_fee = D(0)
        entry = ledger_map.get("fill:"+fid)
        if entry is None:
            raise ValueError("Fill missing from ledger")
        for field, expected_value in (("quantity", q), ("price", price), ("fee", ordinary_fee)):
            same(entry[field], expected_value, "Ledger "+field)
        same(entry.get("liquidation_fee") or 0, special, "Specific liquidation charge")
        base_fee = q*fee if fill["market"] == "spot" and fill["side"].upper() == "BUY" else D(0)
        same(entry.get("base_fee_quantity") or 0, base_fee, "Spot base fee", D(0))
        group = capacity.setdefault(k, dict(symbol=k[0], market=k[1], window_start=k[2],
            window_end=int(window["end_time"]), base_volume=volume, quote_volume=quote,
            executed_gross_quantity=D(0), fill_count=0, liquidation_fill_count=0,
            participation_limit=config.max_volume_participation,
            capacity_quantity=volume*config.max_volume_participation,
            source_path=window.get("source_path", "fixture"),
            source_sha256=window.get("source_sha256", "fixture")))
        before = group["executed_gross_quantity"]
        group["executed_gross_quantity"] += q
        group["fill_count"] += 1
        group["liquidation_fill_count"] += int(is_true(fill.get("liquidation")))
        if group["executed_gross_quantity"] > group["capacity_quantity"]:
            raise ValueError("Shared gross minute participation exceeded")
        if fill.get("capacity_used") not in (None, ""):
            same(fill["capacity_used"], group["executed_gross_quantity"], "Shared consumed capacity", D(0))
        if fill.get("participation") not in (None, ""):
            same(fill["participation"], q/volume, "Fill participation", D("1E-25"))
        grouped_fills[oid].append(fill)
        fill_audit.append(dict(fill_id=fid, order_id=oid, symbol=k[0], market=k[1],
            window_start=k[2], quantity=q, price=price, reference_price=quote/volume,
            gross_notional=q*price, ordinary_fee_usdt=ordinary_fee,
            base_fee_quantity=base_fee, specific_liquidation_charge_usdt=special,
            slippage_and_tick_usdt=q*abs(price-quote/volume), tick_rounding_usdt=q*rounding,
            capacity_used_before=before, capacity_used_after=group["executed_gross_quantity"],
            subject_to_participation=True, ledger_checked=True))
    if set(ledger_map) != {"fill:"+f["fill_id"] for f in fills}:
        raise ValueError("Ledger has unmatched executed fills")
    used = defaultdict(lambda: D(0))
    rows = []
    ordered = sorted(grouped_orders.items(), key=lambda item: (
        int(item[1][0]["submitted_at"]), item[0]))
    for oid, events in ordered:
        terminal = next((r for r in reversed(events) if r.get("record_type") == "final"), events[-1])
        first = next((r for r in events if r.get("action") == "submitted"), events[0])
        requested = number(first["quantity"])
        executions = grouped_fills[oid]
        executed = sum((number(r["quantity"]) for r in executions), D(0))
        if not 0 <= executed <= requested:
            raise ValueError("Order fill quantity exceeds request")
        same(terminal["filled_quantity"], executed, "Terminal order versus fills", D(0))
        remainder = next((r["remaining_quantity"] for r in reversed(events)
                          if r.get("remaining_quantity") is not None), None)
        if remainder is not None:
            same(remainder, requested-executed, "Terminal remainder", D(0))
        for field in ("symbol", "market", "side", "submitted_at", "window_start", "window_end", "quantity"):
            if any(str(r[field]) != str(first[field]) for r in events):
                raise ValueError("Order identity or eligible window changed")
        k = key(first)
        window = window_map.get(k)
        if window is None:
            raise ValueError("Missing requested source-window evidence")
        rule = rules.get(first["symbol"], first["market"], int(first["submitted_at"]))
        volume = number(window["base_volume"]) if is_true(window["present"]) else None
        remaining_cap = max(D(0), volume*config.max_volume_participation-used[k]) if volume is not None else None
        cap_q = floor_step(min(requested, remaining_cap), rule.step) if remaining_cap is not None else None
        shortfall = requested-executed
        cause = "none"
        rule_valid_at_cap = None
        if volume is not None and volume > 0 and number(window["quote_volume"]) > 0:
            price = execution_price(number(window["quote_volume"])/volume, first["side"], rule, config)[0]
            rule_valid_at_cap = valid_quantity(cap_q, price, rule)
        if shortfall:
            if terminal["status"] == "pending":
                cause = "pending_at_exclusive_end"
            elif terminal["status"] == "cancelled":
                cause = "cancelled"
            elif volume is None:
                cause = "documented_market_closure" if closure_for_minute(k[0], k[1], k[2]) else "missing_volume_not_evaluable"
            elif volume == 0:
                cause = "zero_volume"
            elif remaining_cap < rule.step:
                cause = "shared_budget_exhausted" if remaining_cap == 0 else "capacity_below_step"
            elif cap_q < requested and cap_q == executed:
                cause = "capacity"
            elif rule_valid_at_cap is False:
                cause = "rule_filter_after_capacity"
            else:
                cause = "funds_inventory_or_reservations_not_separately_identified"
        net = sum((number(f["quantity"])*(1-number(f["fee_rate"])) for f in executions
                   if f["market"] == "spot" and f["side"].upper() == "BUY"), D(0))
        previous = [r for r in rows if (r["symbol"], r["market"], r["side"], r["purpose"]) ==
                    (first["symbol"], first["market"], first["side"], first["purpose"])]
        retry = bool(previous and previous[-1]["terminal_status"] == "expired"
                     and previous[-1]["window_end"] == int(first["submitted_at"])
                     and first["purpose"] in {"close_spot", "close_perp", "liquidate", "correct"})
        rows.append(dict(order_id=oid, symbol=k[0], market=k[1], side=first["side"],
            purpose=first["purpose"], submitted_at=int(first["submitted_at"]),
            window_start=k[2], window_end=int(first["window_end"]), terminal_status=terminal["status"],
            requested_gross_quantity=requested, gross_executed_quantity=executed,
            net_spot_received=net if k[1] == "spot" and first["side"].upper() == "BUY" else None,
            fraction_executed=executed/requested, unfilled_quantity=shortfall,
            execution_outcome="complete" if executed == requested else "partial" if executed else "no_fill",
            intermediate_event_count=sum(r.get("record_type") == "event" for r in events),
            partial_fill_event_count=sum(r.get("action") == "partial_fill" for r in events),
            retry=retry, retry_of=previous[-1]["order_id"] if retry else None,
            shortfall_cause=cause, capacity_before_order=remaining_cap,
            quantity_allowed_by_cap_and_step=cap_q, rule_valid_at_cap=rule_valid_at_cap,
            recent_volume_at_submission=first.get("recent_volume_quantity"),
            eligible_window_volume=volume, unit=k[0].removesuffix("USDT")))
        used[k] += executed
    for row in capacity.values():
        row["realized_participation"] = row["executed_gross_quantity"]/row["base_volume"]
        row["capacity_utilization"] = row["executed_gross_quantity"]/row["capacity_quantity"]
    return dict(ordenes=rows, fills_conciliados=fill_audit,
                capacidad=sorted(capacity.values(), key=lambda r: (r["window_start"], r["symbol"], r["market"])))


def exposure_episodes(intervals):
    episodes = []
    for symbol in sorted({r["symbol"] for r in intervals}):
        current = None
        for row in sorted((r for r in intervals if r["symbol"] == symbol), key=lambda r: int(r["start_ns"])):
            if row["exposure"] != "unhedged":
                current = None
                continue
            start, end = int(row["start_ns"]), int(row["end_ns"])
            if current is None or current["end_ns"] != start:
                current = dict(episode_id=f"{symbol}-{start}", symbol=symbol, start_ns=start,
                               end_ns=end, max_abs_quantity_gap=D(0), states=[])
                episodes.append(current)
            current["end_ns"] = end
            current["max_abs_quantity_gap"] = max(current["max_abs_quantity_gap"],
                                                  abs(number(row["spot"])-number(row["short"])))
            current["states"] = sorted(set(current["states"]+[row["state"]]))
            current.update(seconds=D(end-current["start_ns"])/SECOND,
                           start_utc=iso(current["start_ns"]), end_exclusive_utc=iso(end))
    return sorted(episodes, key=lambda r: (r["start_ns"], r["symbol"]))


def summarize_execution(audit, periods):
    import numpy as np

    output = []
    for period, lower, upper in periods:
        for symbol, market in [(s, m) for s in ("BTCUSDT", "ETHUSDT") for m in ("spot", "futures")]+[("PORTFOLIO", "ALL")]:
            orders = [r for r in audit["ordenes"] if lower <= r["submitted_at"] < upper and
                      (symbol == "PORTFOLIO" or (r["symbol"], r["market"]) == (symbol, market))]
            cap = [r for r in audit["capacidad"] if lower <= r["window_start"] < upper and
                   (symbol == "PORTFOLIO" or (r["symbol"], r["market"]) == (symbol, market))]
            row = dict(period=period, symbol=symbol, market=market, orders=len(orders),
                capacity_population="instrument-minute keys with executed fills and positive source volume",
                fraction_weighting="one per instrument-minute key", capacity_keys=len(cap),
                requested_quantity=sum((r["requested_gross_quantity"] for r in orders), D(0)) if symbol != "PORTFOLIO" else None,
                executed_quantity=sum((r["gross_executed_quantity"] for r in orders), D(0)) if symbol != "PORTFOLIO" else None,
                retries=sum(r["retry"] for r in orders))
            for outcome in ("complete", "partial", "no_fill"):
                row["orders_"+outcome] = sum(r["execution_outcome"] == outcome for r in orders)
            for status in ("filled", "expired", "cancelled", "pending"):
                row["terminal_"+status] = sum(r["terminal_status"] == status for r in orders)
            for metric in ("realized_participation", "capacity_utilization"):
                values = [float(r[metric]) for r in cap]
                for label, percentile in (("p50", 50), ("p90", 90), ("p95", 95), ("p99", 99), ("max", 100)):
                    row[metric+"_"+label] = float(np.percentile(values, percentile)) if values else None
                row[metric+"_mean"] = float(np.mean(values)) if values else None
            output.append(row)
    return output

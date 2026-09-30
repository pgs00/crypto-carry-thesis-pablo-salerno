"""Offline execution arithmetic from orders, fills, ledger and authenticated minute windows.

Builder and verifier deliberately share these routines; this is not an independent engine.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal as D

from crypto_carry.config import SECOND, iso, timestamp
from crypto_carry.costs import execution_price, floor_step, valid_quantity
from crypto_carry.data.market_calendar import closure_for_minute
from crypto_carry.data.prescribed import prescribed_rules
from scripts.return_capital.common import number

TOL = D("1E-8")
MINUTE = 60 * SECOND
CLIENT = {"open_spot", "open_perp", "increase_spot", "increase_perp", "reduce_spot",
          "reduce_perp", "correct", "close_perp", "close_spot"}


def expected_delay(config, purpose):
    if purpose not in CLIENT | {"liquidate"}:
        raise ValueError("Unclassified order purpose")
    return config.research_execution_delay_seconds if purpose != "liquidate" and (
        config.research_execution_delay_scope == "all_client"
        or purpose in {"close_perp", "close_spot"}) else 0


def expected_window(config, order):
    eligible = int(order["submitted_at"]) + expected_delay(config, order["purpose"])*SECOND
    start = ((eligible + MINUTE - 1)//MINUTE)*MINUTE
    return start, start + MINUTE


def validate_records(config, orders, fills):
    events = [r for r in orders if r.get("record_type") == "event"]
    if any(int(b["time_ns"]) < int(a["time_ns"]) for a,b in zip(events, events[1:])):
        raise ValueError("Persisted order event sequence is not chronological")
    if any(int(b["time_ns"]) < int(a["time_ns"]) for a,b in zip(fills, fills[1:])):
        raise ValueError("Persisted fill sequence is not chronological")
    for i,row in enumerate(events):
        if config.execution_research_active and int(row["event_sequence"]) != i:
            raise ValueError("Persisted order event sequence changed")
    for i,row in enumerate(fills):
        if config.execution_research_active and int(row["fill_sequence"]) != i:
            raise ValueError("Persisted fill sequence changed")
        if int(row["time_ns"]) >= timestamp(config.end):
            raise ValueError("Fill beyond exclusive sample end")
    for row in orders + (fills if config.execution_research_active else []):
        start,end = expected_window(config,row)
        if (int(row["window_start"]),int(row["window_end"])) != (start,end):
            raise ValueError("Order window does not follow eligibility")
        if int(row["deadline"]) != end:
            raise ValueError("Order deadline is not its unique window end")
        if config.execution_research_active:
            expected = dict(reference_price_model=config.research_minute_price_model,
                delay_configured_seconds=config.research_execution_delay_seconds,
                delay_scope=config.research_execution_delay_scope,
                delay_applied_seconds=expected_delay(config,row["purpose"]),
                generated_at=int(row["submitted_at"]),
                eligible_at=int(row["submitted_at"])+expected_delay(config,row["purpose"])*SECOND)
            for key,value in expected.items():
                if str(row.get(key)) != str(value):
                    raise ValueError("Order/fill execution metadata changed: "+key)


def ohlc4(window):
    opened, high, low, close = [number(window[k]) for k in ("open","high","low","close")]
    if (not all(v.is_finite() and v > 0 for v in (opened, high, low, close))
            or not low <= opened <= high or not low <= close <= high):
        raise ValueError("Invalid source OHLC")
    return (opened + high + low + close)/4


def source_reference(config, window):
    if config.research_minute_price_model == "ohlc4":
        if int(window["trade_count"]) <= 0:
            raise ValueError("OHLC execution without activity")
        return ohlc4(window)
    return number(window["quote_volume"])/number(window["base_volume"])


def check_source_fields(fill, window):
    for key in ("open","high","low","close"):
        same(fill["window_"+key],window[key],"Source OHLC "+key,D(0))
    same(fill["window_vwap"],number(window["quote_volume"])/number(window["base_volume"]),
         "Unmodified VWAP",D("1E-20"))
    same(fill["window_ohlc4"],ohlc4(window),"Unmodified OHLC4",D(0))
    if int(fill["window_available_at"]) != int(window["available_at"]) or int(window["available_at"]) != int(window["end_time"]):
        raise ValueError("Candle availability differs from completed minute")


def temporal_summary(config, first, events, fills):
    submitted = int(first["submitted_at"])
    applied = expected_delay(config,first["purpose"])
    fill_time = int(fills[0]["time_ns"]) if fills else None
    requested = [int(r["time_ns"]) for r in events if
                 str(r.get("action", "")).startswith("deferred_cancel:") or r.get("status") == "cancelled"]
    effective = [int(r["time_ns"]) for r in events if r.get("record_type") == "event" and
                 (r.get("status") == "cancelled" or (r.get("action") == "timeout" and requested))]
    return dict(reference_price_model=config.research_minute_price_model,
        generated_at=submitted, delay_configured_seconds=config.research_execution_delay_seconds,
        delay_scope=config.research_execution_delay_scope,delay_applied_seconds=applied,
        eligible_at=submitted+applied*SECOND,deadline=int(first["deadline"]),
        cancellation_requested_at=min(requested,default=None),
        cancellation_effective_at=min(effective,default=None),fill_at=fill_time,
        submission_to_fill_seconds=D(fill_time-submitted)/SECOND if fill_time is not None else None,
        eligibility_to_fill_seconds=D(fill_time-submitted-applied*SECOND)/SECOND if fill_time is not None else None,
        cancel_actions=[r.get("action") for r in events if r.get("record_type") == "event" and
                        (r.get("status") == "cancelled" or str(r.get("action","")).startswith("deferred_cancel:"))])


def same(actual, expected, label, tolerance=TOL):
    if abs(number(actual)-number(expected)) > tolerance:
        raise ValueError(f"{label}: {actual} != {expected}")


def is_true(value):
    return value in (True, "True", "true", 1, "1")


def audit_lifecycle(config, events, fills):
    records=[r for r in events if r.get('record_type')=='event']
    finals=[r for r in events if r.get('record_type')=='final']
    if not records or len(finals)!=1 or records[0].get('action')!='submitted':
        raise ValueError('Order lacks submitted event or unique final snapshot')
    first=records[0]
    submitted,start,end=map(int,(first['submitted_at'],first['window_start'],first['window_end']))
    if int(first['time_ns'])!=submitted or first['status']!='pending' or number(first['filled_quantity'])!=0:
        raise ValueError('Invalid submission event')
    status,filled='pending',D(0)
    audit={}
    paired=[]
    for row in records:
        action,t=row.get('action'),int(row['time_ns'])
        if t<submitted or t>=timestamp(config.end):
            raise ValueError('Order event outside lifetime')
        if row is not first and status!='pending':
            raise ValueError('Event after terminal order state')
        if action=='submitted' and row is not first:
            raise ValueError('Repeated submission event')
        if action in ('filled','partial_fill'):
            if t!=end or len(paired)>=len(fills):
                raise ValueError('Fill event outside unique eligible window')
            fill=fills[len(paired)]
            if int(fill['time_ns'])!=t:
                raise ValueError('Fill time differs from order event')
            paired.append(fill)
            filled+=number(fill['quantity'])
            wanted='filled' if filled==number(first['quantity']) else 'pending'
            if row['status']!=wanted or (action=='filled')!=(wanted=='filled'):
                raise ValueError('Fill event status differs from executed amount')
            audit['fill_at']=t
        elif action=='timeout':
            if t!=end or row['status']!='expired':
                raise ValueError('Expiration against an incorrect attempt deadline')
            audit['expired_at']=t
            if 'cancel_requested_at' in audit:
                audit.setdefault('cancel_effective_at',t)
        elif str(action).startswith('deferred_cancel:'):
            if not start<t<end or row['status']!='pending':
                raise ValueError('Deferred cancellation outside committed interval')
            audit.setdefault('cancel_requested_at',t)
        elif row['status']=='cancelled':
            if start<t<end or t>end:
                raise ValueError('Immediate cancellation inside committed interval')
            audit.setdefault('cancel_requested_at',t)
            audit.setdefault('cancel_effective_at',t)
        elif row['status']=='rejected':
            if t!=end or action!='insufficient_funds':
                raise ValueError('Unknown rejected execution transition')
        elif action!='submitted':
            raise ValueError('Unclassified order lifecycle action')
        if number(row['filled_quantity'])!=filled:
            raise ValueError('Cumulative order quantity differs from events')
        if config.execution_research_active:
            for field in ('fill_at','cancel_requested_at','cancel_effective_at','expired_at'):
                value=None if row.get(field) in (None,'') else int(row[field])
                if value!=audit.get(field):
                    raise ValueError('Order lifecycle timestamp changed: '+field)
        if action in ('filled','partial_fill') and config.execution_research_active:
            for field in ('fill_at','cancel_requested_at','cancel_effective_at','expired_at'):
                value=None if fill.get(field) in (None,'') else int(fill[field])
                if value!=audit.get(field):
                    raise ValueError('Fill lifecycle timestamp changed: '+field)
        status=row['status']
    if len(paired)!=len(fills) or finals[0]['status']!=status:
        raise ValueError('Final state or fill population differs from order lifecycle')
    final_time=int(finals[0]['time_ns'])
    if not int(records[-1]['time_ns'])<=final_time<timestamp(config.end):
        raise ValueError('Final snapshot time outside observed order lifetime')
    if status=='pending' and final_time>=end:
        raise ValueError('Pending order survives its completed attempt deadline')
    if config.execution_research_active:
        for field in ('fill_at','cancel_requested_at','cancel_effective_at','expired_at'):
            value=None if finals[0].get(field) in (None,'') else int(finals[0][field])
            if value!=audit.get(field):
                raise ValueError('Final lifecycle timestamp changed: '+field)


def validate_purpose(row, *, fill=False):
    purposes={
        'open_spot':('spot',{'BUY'}),'increase_spot':('spot',{'BUY'}),
        'reduce_spot':('spot',{'SELL'}),'close_spot':('spot',{'SELL'}),
        'open_perp':('futures',{'SELL'}),'increase_perp':('futures',{'SELL'}),
        'reduce_perp':('futures',{'BUY'}),'close_perp':('futures',{'BUY'}),
        'correct':('futures',{'BUY','SELL'}),'liquidate':('futures',{'BUY'})}
    market,sides=purposes[row['purpose']]
    if row['market']!=market or row['side'] not in sides:
        raise ValueError('Purpose differs from executable market or side')
    if fill and is_true(row.get('liquidation'))!=(row['purpose']=='liquidate'):
        raise ValueError('Liquidation charge flag differs from purpose')


def key(row):
    return row["symbol"], row["market"], int(row.get("window_start", row.get("open_time")))


def validate_causal_purposes(orders, risk_events):
    states={
        'open_spot':'OPENING_SPOT','open_perp':'OPENING_PERP',
        'increase_spot':'REBALANCING','increase_perp':'REBALANCING',
        'reduce_spot':'REBALANCING','reduce_perp':'REBALANCING',
        'correct':'CORRECTING_HEDGE','close_spot':'CLOSING_SPOT',
        'close_perp':'CLOSING_PERP','liquidate':'LIQUIDATING'}
    submissions={r['order_id']:r for r in orders if r.get('action')=='submitted'}
    for row in submissions.values():
        t=int(row['submitted_at'])
        transitions=[r for r in risk_events if r['symbol']==row['symbol'] and
                     r.get('kind')=='transition' and int(r['time_ns'])<=t]
        before=[r for r in transitions if int(r['time_ns'])<t]
        candidates={r['state'] for r in transitions if int(r['time_ns'])==t}
        if before and not candidates:
            candidates.add(before[-1]['state'])
        if states[row['purpose']] not in candidates:
            raise ValueError('Order purpose lacks matching causal strategy state')
        linked=[r for r in risk_events if r.get('order_id')==row['order_id']]
        if row['purpose']=='open_spot' and not any(r.get('cause')=='entry' and
                r.get('state')=='OPENING_SPOT' and int(r['time_ns'])==t for r in linked):
            raise ValueError('Opening order lacks causal entry transition')
        for event in linked:
            if event.get('purpose') and event['purpose']!=row['purpose']:
                raise ValueError('Order purpose differs from causal failure event')
            if event.get('state')=='OPENING_SPOT' and row['purpose']!='open_spot':
                raise ValueError('Order purpose differs from causal entry transition')


def audit_execution(config, orders, fills, ledger, windows, *, risk_events=None):
    validate_records(config, orders, fills)
    if risk_events is not None:
        validate_causal_purposes(orders,risk_events)
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
        validate_purpose(row)
        grouped_orders[row["order_id"]].append(row)
    if [r['event_id'] for r in ledger if str(r['event_id']).startswith('fill:')]!=['fill:'+r['fill_id'] for r in fills]:
        raise ValueError('Fill sequence differs from ledger sequence')
    if [(r['order_id'],int(r['time_ns'])) for r in orders if r.get('record_type')=='event' and
            r.get('action') in ('filled','partial_fill')]!=[(r['order_id'],int(r['time_ns'])) for r in fills]:
        raise ValueError('Fill sequence differs from order event sequence')
    fill_audit = []
    for fill in fills:
        validate_purpose(fill,fill=True)
        oid, fid = fill["order_id"], fill["fill_id"]
        if oid not in grouped_orders:
            raise ValueError("Fill has no authenticated order")
        original = grouped_orders[oid][0]
        for field in ("symbol", "market", "side", "purpose", "window_start", "window_end"):
            if str(fill[field]) != str(original[field]):
                raise ValueError("Fill differs from original order "+field)
        if config.execution_research_active:
            for field in ('submitted_at','generated_at','eligible_at','deadline'):
                if int(fill[field])!=int(original[field]):
                    raise ValueError('Fill timing differs from original order '+field)
        if (int(original["window_start"]), int(original["window_end"])) != expected_window(config, original):
            raise ValueError("Order window does not follow eligibility")
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
        reference = source_reference(config, window)
        same(fill["reference_price"], reference, "Selected reference", D("1E-20"))
        if config.execution_research_active:
            check_source_fields(fill, window)
        expected, rounding = execution_price(reference, fill["side"], rule, config)
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
        if entry["symbol"] != fill["symbol"] or entry["kind"] != fill["market"]+"_"+fill["side"].lower():
            raise ValueError("Ledger identity differs from fill")
        if entry.get("time_ns") is not None and int(entry["time_ns"]) != int(fill["time_ns"]):
            raise ValueError("Ledger time differs from fill")
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
            side=fill['side'],purpose=fill['purpose'],time_ns=int(fill['time_ns']),
            submitted_at=int(original['submitted_at']),generated_at=int(original['submitted_at']),
            eligible_at=int(original['submitted_at'])+expected_delay(config,fill['purpose'])*SECOND,
            delay_applied_seconds=expected_delay(config,fill['purpose']),
            delay_configured_seconds=config.research_execution_delay_seconds,
            delay_scope=config.research_execution_delay_scope,
            reference_price_model=config.research_minute_price_model,
            fill_at=int(fill['time_ns']),window_end=int(fill['window_end']),
            window_start=k[2], quantity=q, net_quantity=q-base_fee, price=price, reference_price=reference,
            gross_notional=q*price, ordinary_fee_usdt=ordinary_fee,
            base_fee_quantity=base_fee, specific_liquidation_charge_usdt=special,
            slippage_and_tick_usdt=q*abs(price-reference), tick_rounding_usdt=q*rounding,
            capacity_used_before=before, capacity_used_after=group["executed_gross_quantity"],
            subject_to_participation=True, ledger_checked=True))
    if set(ledger_map) != {"fill:"+f["fill_id"] for f in fills}:
        raise ValueError("Ledger has unmatched executed fills")
    used = defaultdict(lambda: D(0))
    rows = []
    # Insertion order is the persisted submission order, never an arbitrary ID sort.
    ordered = grouped_orders.items()
    for oid, events in ordered:
        terminal = next((r for r in reversed(events) if r.get("record_type") == "final"), events[-1])
        if sum(r.get("record_type") == "final" for r in events) != 1:
            raise ValueError("Order requires one terminal snapshot")
        first = next((r for r in events if r.get("action") == "submitted"), events[0])
        if (int(first["window_start"]), int(first["window_end"])) != expected_window(config, first):
            raise ValueError("Order window does not follow eligibility")
        requested = number(first["quantity"])
        executions = grouped_fills[oid]
        audit_lifecycle(config,events,executions)
        executed = sum((number(r["quantity"]) for r in executions), D(0))
        if not 0 <= executed <= requested:
            raise ValueError("Order fill quantity exceeds request")
        same(terminal["filled_quantity"], executed, "Terminal order versus fills", D(0))
        if (terminal["status"] == "filled") != (executed == requested):
            raise ValueError("Terminal order status differs from executed quantity")
        if terminal["status"] not in {"filled", "expired", "cancelled", "pending", "rejected"}:
            raise ValueError("Unknown terminal order status")
        remainder = next((r["remaining_quantity"] for r in reversed(events)
                          if r.get("remaining_quantity") is not None), None)
        if remainder is not None:
            same(remainder, requested-executed, "Terminal remainder", D(0))
        for field in ("symbol", "market", "side", "purpose", "submitted_at", "window_start", "window_end", "quantity"):
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
            price = execution_price(source_reference(config, window), first["side"], rule, config)[0]
            rule_valid_at_cap = valid_quantity(cap_q, price, rule)
        if shortfall:
            if terminal["status"] == "pending":
                cause = "pending_at_exclusive_end"
            elif terminal["status"] == "cancelled":
                cause = ("preventive_correction_deadline" if any(r.get("action") == "hedge_correction_deadline" for r in events)
                         else "preventive_cancellation")
            elif volume is None:
                cause = "documented_market_closure" if closure_for_minute(k[0], k[1], k[2]) else "missing_volume_not_evaluable"
            elif volume == 0:
                cause = "zero_volume"
            elif number(window["quote_volume"]) <= 0:
                cause = "missing_or_invalid_executable_price"
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
        rows[-1].update(temporal_summary(config, first, events, executions))
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
            for status in ("filled", "expired", "cancelled", "pending", "rejected"):
                row["terminal_"+status] = sum(r["terminal_status"] == status for r in orders)
            for metric in ("realized_participation", "capacity_utilization"):
                values = [float(r[metric]) for r in cap]
                for label, percentile in (("p50", 50), ("p90", 90), ("p95", 95), ("p99", 99), ("max", 100)):
                    row[metric+"_"+label] = float(np.percentile(values, percentile)) if values else None
                row[metric+"_mean"] = float(np.mean(values)) if values else None
            output.append(row)
    return output

"""Read-only block-5 attribution and independent checks of persisted witnesses.

No function here generates an order, cash movement, price feed or scenario.
Builder and final verifier share these reporting routines; that sharing is
disclosed, rather than described as another independent economic engine.
"""

import hashlib
import json
from bisect import bisect_left
from collections import defaultdict
from decimal import Decimal as D

from crypto_carry.config import SECOND
from crypto_carry.margin import liquidation_price, maintenance

TOLERANCE = D("1E-8")
MINUTE = 60_000_000_000
BAR_FIELDS = ("symbol", "market", "open_time", "end_time", "available_at", "open", "high",
              "low", "close", "base_volume", "quote_volume", "trade_count", "source_file")
DECIMAL_FIELDS = ("open", "high", "low", "close", "base_volume", "quote_volume")


def record_digest(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def source_bar(row):
    if row is None or not row.get("present", True):
        return None
    return {key: str(number(row[key])) if key in DECIMAL_FIELDS else row[key]
            for key in BAR_FIELDS}


def factor_for_open(spec, symbol, opening):
    """Direct approved equation; does not call the replay's compiled factor map."""
    intensity = D(0)
    for asset, start, end in spec.get("episodes", []):
        if asset != symbol:
            continue
        a = ((start + MINUTE - 1) // MINUTE) * MINUTE
        b = max(a + MINUTE, ((end + MINUTE - 1) // MINUTE) * MINUTE)
        if a <= opening < b:
            intensity = D(1)
        elif b <= opening < b + 60 * MINUTE:
            intensity = max(intensity, 1 - D(opening - b) / D(60 * MINUTE))
    return 1 - number(spec["magnitudes"].get(symbol, 0)) * intensity


def derived_bar(spec, original, future, symbol, opening):
    """Independently derive one approved bar for evidence and execution checks."""
    if spec["kind"] == "shock":
        factor = factor_for_open(spec, symbol, opening)
        if original is None or factor == 1:
            return original
        return dict(original, **{field: str(number(original[field]) * factor)
                                for field in ("open", "high", "low", "close", "quote_volume")},
                    source_file=f"scenario:{spec['id']}|{original['source_file']}")
    if spec["kind"] != "counterfactual" or not spec["start"] <= opening < spec["end"]:
        return original
    if future is None or number(future["base_volume"]) <= 0:
        raise ValueError("Missing positive future source")
    anchor = spec["anchors"][symbol]
    k = number(anchor["spot"]) / number(anchor["futures"])
    volume, trades = spec["volumes"][symbol, opening]
    volume = number(volume)
    vwap = k * (number(future["quote_volume"]) / number(future["base_volume"]))
    return dict(future, market="spot", **{field: str(k * number(future[field]))
                                         for field in ("open", "high", "low", "close")},
                base_volume=str(volume), quote_volume=str(volume * vwap), trade_count=int(trades),
                source_file=f"scenario:{spec['id']}|{future['source_file']}")


def audit_intervention(spec, sources, row):
    symbol, opening = row["symbol"], int(row["open_time"])
    original = source_bar(sources.get((symbol, "spot", opening)))
    future = source_bar(sources.get((symbol, "futures", opening)))
    source = original if spec["kind"] == "shock" else future
    if row["original"] != original or row["source_record"] != source:
        raise ValueError("Intervention source differs from authenticated extract")
    for name, value in (("original", original), ("source", source), ("modified", row["modified"])):
        if record_digest(value) != row[name + "_record_sha256"]:
            raise ValueError("Intervention record checksum mismatch")
    expected = derived_bar(spec, original, future, symbol, opening)
    factor = factor_for_open(spec, symbol, opening) if spec["kind"] == "shock" else None
    if (row["scenario"] != spec["id"] or row["kind"] != spec["kind"] or expected is None
            or row["modified"] != expected or int(row["available_at"]) != opening + MINUTE
            or (number(row["factor"]) if row.get("factor") is not None else None) != factor):
        raise ValueError("Intervention transformation differs from approved equation")
    return dict(passed=True, symbol=symbol, open_time=opening, factor=factor,
                modified_record_sha256=record_digest(expected))


def audit_interventions(spec, sources, rows, observed_end):
    expected = set()
    if spec["kind"] == "shock":
        expected = {(s, t) for (s, market, t), row in sources.items()
                    if market == "spot" and row.get("present", True) and t + MINUTE <= observed_end
                    and factor_for_open(spec, s, t) != 1}
    elif spec["kind"] == "counterfactual":
        expected = {(s, t) for s, t in spec["volumes"] if t + MINUTE <= observed_end}
    actual, checked = set(), []
    for row in rows:
        key = row["symbol"], int(row["open_time"])
        if key in actual:
            raise ValueError("Duplicate intervention")
        actual.add(key)
        checked.append(audit_intervention(spec, sources, row))
    if actual != expected:
        raise ValueError("Intervention coverage differs from the approved calendar")
    fingerprints = [dict(symbol=r["symbol"], open_time=r["open_time"],
                         modified_record_sha256=r["modified_record_sha256"])
                    for r in sorted(checked, key=lambda r: (r["symbol"], r["open_time"]))]
    return dict(passed=True, intervention_rows=len(rows), expected_rows=len(expected),
                market_projection_sha256=record_digest(fingerprints))


def approved_windows_and_factors(spec):
    """Independent observation support; each pulse is revealed only at bar close."""
    spans, factors = [], {}
    if spec["kind"] == "shock":
        keys = set()
        for symbol, start, end in spec["episodes"]:
            a = ((start + MINUTE - 1) // MINUTE) * MINUTE
            b = max(a + MINUTE, ((end + MINUTE - 1) // MINUTE) * MINUTE)
            keys.update((symbol, u) for u in range(a, b + 60 * MINUTE, MINUTE))
            if number(spec["magnitudes"][symbol]) > 0:
                spans.append((a, b + 62 * MINUTE))
        factors = {(s, u): factor_for_open(spec, s, u) for s, u in sorted(keys)}
    elif spec["kind"] == "counterfactual":
        spans = [(spec["start"], spec["end"] + 2 * MINUTE)]
    windows = []
    for start, end in sorted(spans):
        if windows and start <= windows[-1][1]:
            windows[-1][1] = max(windows[-1][1], end)
        else:
            windows.append([start, end])
    return windows, factors


def audit_observation_population(spec, state, snapshots, witnesses, start, observed_end,
                                 symbols=("BTCUSDT", "ETHUSDT")):
    from crypto_carry.serialization import decode

    windows, factors = approved_windows_and_factors(spec)
    if state["windows"] != windows or decode(state["factors"]) != factors:
        raise ValueError("Declared window/factor support differs from approved protocol")
    required_times = set()
    for lower, upper in windows:
        required_times.update(range(max(start, lower), min(upper, observed_end) + 1, MINUTE))
    actual_times = [int(r["time_ns"]) for r in snapshots]
    if (len(set(actual_times)) != len(actual_times) or actual_times != sorted(actual_times)
            or len(snapshots) != state["observation_rows"]
            or not required_times <= set(actual_times)
            or any(not start <= t <= observed_end or not any(a <= t <= b for a, b in windows)
                   for t in actual_times)):
        raise ValueError("Intervention snapshot population is incomplete, duplicate or outside scope")
    actual_keys = [(int(r["time_ns"]), r["symbol"]) for r in witnesses]
    required_keys = {(t, s) for t in required_times for s in symbols}
    if len(actual_keys) != len(set(actual_keys)) or set(actual_keys) != required_keys:
        raise ValueError("Intervention opportunity witness population differs from required minutes/assets")
    return dict(passed=True, windows=len(windows), required_minute_snapshots=len(required_times),
                actual_event_snapshots=len(snapshots), required_asset_minute_witnesses=len(required_keys),
                terminal_scope="through observed final clock inclusive; no extrapolation")


def audit_witness_sources(spec, sources, witness):
    symbol = witness["symbol"]
    for market, field in (("spot", "spot_bar"), ("futures", "future_bar")):
        bar = witness.get(field)
        current_open = (int(witness["time_ns"]) // MINUTE - 1) * MINUTE
        current_raw = source_bar(sources.get((symbol, market, current_open)))
        current = current_raw if market == "futures" else derived_bar(spec, current_raw,
            source_bar(sources.get((symbol, "futures", current_open))), symbol, current_open)
        if current is not None and bar != current:
            raise ValueError("H3 witness hides or changes the current available source bar")
        if bar is None:
            continue
        opening = int(bar["open_time"])
        raw = source_bar(sources.get((symbol, market, opening)))
        expected = raw if market == "futures" else derived_bar(spec, raw,
            source_bar(sources.get((symbol, "futures", opening))), symbol, opening)
        if expected is None or bar != expected or int(bar["available_at"]) > int(witness["time_ns"]):
            raise ValueError("H3 witness bar differs from scenario source transformation")
    return True


def audit_window_price_sources(spec, sources, snapshot):
    time = int(snapshot["time_ns"])
    for symbol, asset in snapshot["assets"].items():
        raw_available = asset.get("original_spot_available_at")
        if raw_available is not None:
            original = source_bar(sources.get((symbol, "spot", int(raw_available) - MINUTE)))
            if (original is None or int(raw_available) > time
                    or number(asset["original_spot_price"]) != number(original["close"])
                    or asset["original_spot_source"] != original["source_file"]
                    or asset["original_spot_record_sha256"] != record_digest(original)):
                raise ValueError("Window original valuation source differs from extracted observation")
        if asset.get("spot_source_available_at") is None:
            if asset.get("spot_price") is not None:
                raise ValueError("Window valuation lacks source availability")
            continue
        opening = int(asset["spot_source_available_at"]) - MINUTE
        if opening + MINUTE > time:
            raise ValueError("Window valuation anticipates source availability")
        if spec["kind"] == "shock":
            factor = factor_for_open(spec, symbol, (time // MINUTE - 1) * MINUTE)
            if raw_available is None or opening + MINUTE != int(raw_available):
                raise ValueError("Stale shock valuation refreshed its original source timestamp")
            expected = number(original["close"]) * factor
            if number(asset["factor"]) != factor:
                raise ValueError("Window valuation factor differs from approved pulse clock")
        else:
            raw = source_bar(sources.get((symbol, "spot", opening)))
            bar = derived_bar(spec, raw, source_bar(sources.get((symbol, "futures", opening))), symbol, opening)
            if bar is None:
                raise ValueError("Window valuation lacks source bar")
            expected = number(bar["close"])
        if abs(number(asset["spot_price"]) - expected) > TOLERANCE:
            raise ValueError("Window valuation differs from the original source and approved equation")
    return True


def number(value):
    result = D(str(value))
    if not result.is_finite():
        raise ValueError("Nonfinite financial observation")
    return result


def price_attribution(before, after):
    """Exact two-term product difference on pre-event spot, including dust.

This is a valuation diagnostic along one scenario's actual inventory, not a
causal difference versus the BASE portfolio (whose inventory may differ).
"""
    quantity = number(before["spot"])
    fields = ("factor_valuation_usdt", "imposed_recovery_usdt", "imposed_drop_usdt",
              "underlying_price_usdt", "total_preinventory_price_effect_usdt",
              "decomposition_residual_usdt")
    result = dict(inventory_scope="pre_event_spot_quantity", ledger_movement_created=False,
                  pre_event_spot_quantity=quantity)
    if not quantity:
        return dict(result, **dict.fromkeys(fields, D(0)), evaluable=True, reason="no_spot")
    if any(row.get(key) is None for row in (before, after)
           for key in ("original_spot_price", "spot_price", "factor")):
        return dict(result, **dict.fromkeys(fields), evaluable=False, reason="missing_reference")
    s0, s1 = number(before["original_spot_price"]), number(after["original_spot_price"])
    f0, f1 = number(before["factor"]), number(after["factor"])
    factor = quantity * s0 * (f1 - f0)
    underlying = quantity * f1 * (s1 - s0)
    total = quantity * (number(after["spot_price"]) - number(before["spot_price"]))
    residual = total - factor - underlying
    if abs(residual) > TOLERANCE:
        raise ValueError("Spot factor/reference decomposition does not reconcile")
    return dict(result, factor_valuation_usdt=factor, imposed_recovery_usdt=max(D(0), factor),
                imposed_drop_usdt=min(D(0), factor), underlying_price_usdt=underlying,
                total_preinventory_price_effect_usdt=total,
                decomposition_residual_usdt=residual, evaluable=True, reason="")


def preventive_requirement(asset, rule, config):
    """Hypothetical top-up infimum, preserving both BASE preventive constraints."""
    q = number(asset["short"])
    empty = dict(no_open_short=q == 0, margin_balance_usdt=None, maintenance_usdt=None,
                 headroom_usdt=None, maintenance_shortfall_usdt=None, margin_ratio=None,
                 liquidation_price=None, liquidation_distance=None,
                 preventive_topup_infimum_usdt=None, strict_infimum=None,
                 ratio_need_usdt=None, distance_need_usdt=None, evaluable=False, reason="")
    if q == 0:
        return dict(empty, maintenance_usdt=D(0), maintenance_shortfall_usdt=D(0),
                    preventive_topup_infimum_usdt=D(0), ratio_need_usdt=D(0),
                    distance_need_usdt=D(0), strict_infimum=False, evaluable=True,
                    reason="no_open_short")
    if rule is None or any(asset.get(k) is None for k in ("average", "collateral", "mark")):
        return dict(empty, reason="missing_margin_input")
    average, collateral, mark = (number(asset[k]) for k in ("average", "collateral", "mark"))
    if q < 0 or mark <= 0:
        raise ValueError("Invalid short margin state")
    try:
        requirement = maintenance(q, mark, rule)
        target_mark = mark * (1 + config.liquidation_distance)
        target_maintenance = maintenance(q, target_mark, rule)
        liquidation = liquidation_price(q, average, collateral, rule)
    except ValueError:
        return dict(empty, reason="margin_tier_not_covered")
    balance = collateral + q * (average - mark)
    ratio_need = requirement / config.margin_exit_ratio - balance
    distance_need = q * (target_mark - mark) + target_maintenance - balance
    infimum = max(D(0), ratio_need, distance_need)
    return dict(empty, margin_balance_usdt=balance, maintenance_usdt=requirement,
                headroom_usdt=balance - requirement,
                maintenance_shortfall_usdt=max(D(0), requirement - balance),
                margin_ratio=requirement / balance if balance > 0 else None,
                liquidation_price=liquidation,
                liquidation_distance=(liquidation - mark) / mark if liquidation is not None else None,
                preventive_topup_infimum_usdt=infimum,
                strict_infimum=ratio_need >= 0 and ratio_need >= distance_need,
                ratio_need_usdt=max(D(0), ratio_need), distance_need_usdt=max(D(0), distance_need),
                evaluable=True, reason="nonpositive_margin_balance" if balance <= 0 else "")


def joint_requirement(assets, free_cash, reserved_cash, debt):
    """Compare simultaneous needs once with cash; no reuse of isolated collateral."""
    values = [r["preventive_topup_infimum_usdt"] for r in assets]
    total = sum(values, D(0)) if all(v is not None for v in values) else None
    committed_known = free_cash is not None and reserved_cash is not None and debt is not None
    available = max(D(0), number(free_cash) - number(reserved_cash)) if committed_known else None
    reason = "unknown_cash_commitment" if not committed_known else (
        "unknown_margin_need" if total is None else "")
    return dict(preventive_topup_infimum_usdt=total, uncommitted_cash_usdt=available,
                free_cash_usdt=free_cash, reserved_cash_usdt=reserved_cash, existing_debt_usdt=debt,
                external_shortfall_infimum_usdt=max(D(0), total + number(debt) - available)
                    if not reason else None,
                strict_infimum=any(r.get("strict_infimum") is True for r in assets),
                external_need_reason=reason, collateral_reused=False, money_injected=False)


def audit_opportunity(row, config):
    """Recompute H3 from a minute witness, without portfolio quantities or funds."""
    t, fc = int(row["time_ns"]), row.get("forecast")
    spot, future = row.get("spot_bar"), row.get("future_bar")
    if fc and int(fc["available_at"]) > t:
        raise ValueError("Forecast availability exceeds opportunity time")
    for bar in (spot, future):
        if bar and int(bar["available_at"]) > t:
            raise ValueError("Bar availability exceeds opportunity time")
    complete = bool(not row["bad_symbol"] and row["mark_present"] and fc
                    and fc["valid"] and row["rules_present"])
    fresh = bool(spot and future and spot["open_time"] == future["open_time"]
                 and spot["end_time"] == future["end_time"]
                 and 0 <= t - int(spot["available_at"]) <= config.freshness_seconds * SECOND
                 and number(spot["base_volume"]) > 0 and number(future["base_volume"]) > 0)
    basis = number(future["close"]) / number(spot["close"]) - 1 if spot and future else None
    eligible = bool(complete and fresh and row["operational"]
                    and config.basis_min <= basis <= config.basis_max
                    and number(fc["value"]) > D(".0034"))
    value = number(fc["value"]) if eligible else D(0)
    if (bool(row["complete"]) != complete or bool(row["eligible"]) != eligible
            or bool(row["fresh"]) != fresh or number(row["value"]) != value
            or row["selection_cost"] is not None and number(row["selection_cost"]) != D(".0034")):
        raise ValueError("Persisted opportunity witness differs from market filters")
    return dict(time_ns=t, symbol=row["symbol"], complete=complete, eligible=eligible,
                basis=basis, opportunity=value if complete else None,
                unit="fraction/168h", position_independent=True)


def audit_funding_amounts(ledger, consumed):
    """Observed rates/settlement marks times quantities strictly before simultaneous fills."""
    histories, payments = defaultdict(list), {}
    for row in ledger:
        symbol = row.get("symbol")
        if not symbol or row.get("short") is None:
            continue
        time = int(row["time_ns"])
        histories[symbol].append((time, number(row["short"])))
        if row["kind"] == "funding":
            key = symbol, time
            if key in payments:
                raise ValueError("Duplicate funding payment")
            payments[key] = row
    for values in histories.values():
        if [r[0] for r in values] != sorted(r[0] for r in values):
            raise ValueError("Ledger funding history is not ordered")
    times = {s: [r[0] for r in values] for s, values in histories.items()}
    expected, output = set(), []
    for source in consumed:
        if not source["economic_window"]:
            continue
        symbol, time = source["symbol"], int(source["funding_time"])
        i = bisect_left(times.get(symbol, []), time) - 1
        quantity = histories[symbol][i][1] if i >= 0 else D(0)
        if not quantity:
            continue
        key = symbol, time
        if key in expected:
            raise ValueError("Duplicate consumed funding settlement")
        expected.add(key)
        row = payments.get(key)
        if row is None:
            raise ValueError("Funding payment missing for an open pre-fill short")
        mark, rate = number(source["settlement_mark_price"]), number(source["funding_rate"])
        amount = quantity * mark * rate
        if number(row["short"]) != quantity or abs(number(row["amount_usdt"]) - amount) > TOLERANCE:
            raise ValueError("Funding amount differs from pre-fill quantity times settlement mark and rate")
        output.append(dict(symbol=symbol, time_ns=time, quantity_before_fills=quantity,
            settlement_mark_price=mark, funding_rate=rate, amount_usdt=row["amount_usdt"],
            recomputed_amount_usdt=amount, residual_usdt=number(row["amount_usdt"]) - amount,
            settlement_mark_method=source.get("settlement_mark_method")))
    if set(payments) != expected:
        raise ValueError("Funding payment population differs from consumed settlements")
    return output

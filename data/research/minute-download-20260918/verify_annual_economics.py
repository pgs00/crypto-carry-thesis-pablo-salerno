"""Independent financial audit of the two immutable annual minute baselines.

This script intentionally does not import the engine Ledger or cost helpers. It
replays persisted fills and observed funding records with Decimal arithmetic,
then reconciles the result to persisted terminal positions and summaries.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, getcontext
from pathlib import Path

import pyarrow.parquet as pq

getcontext().prec = 60
D = Decimal
TOLERANCE = D("1e-8")
EXCEPTIONAL_EVENT_DATE = "2023-03-24"
DEFAULT_RUNS = {
    "early_2022_2023": Path("D:/Backtesting/outputs/run_8fb22fa8b377466cff981b99"),
    "late_2025_2026": Path("D:/Backtesting/outputs/run_0cb21afbec7cdba1e5848df6"),
}


def _decimal(value: object) -> Decimal:
    return D(str(value))


def _text(value: Decimal) -> str:
    return str(value)


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _rows(path: Path) -> list[dict]:
    return pq.read_table(path).to_pylist()


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _state() -> dict[str, Decimal]:
    return {
        "spot": D(0),
        "spot_cost": D(0),
        "realized_spot": D(0),
        "short": D(0),
        "average": D(0),
        "realized_futures": D(0),
        "funding": D(0),
        "fees": D(0),
    }


def _expected_fill_price(
    reference: Decimal, side: str, tick: Decimal, slippage: Decimal
) -> Decimal:
    adverse = reference * (D(1) + slippage if side == "BUY" else D(1) - slippage)
    rounding = ROUND_CEILING if side == "BUY" else ROUND_FLOOR
    return (adverse / tick).to_integral_value(rounding=rounding) * tick


def _rules(run: Path) -> tuple[dict[tuple[str, str], dict], Decimal]:
    assumptions = json.loads((run / "research_assumptions.json").read_text(encoding="utf-8"))
    rules = {(row["symbol"], row["market"]): row["values"] for row in assumptions["rules"]}
    parameters = {row["parameter"]: row["value"] for row in _csv(run / "parameters.csv")}
    return rules, _decimal(parameters["slippage"])


def _source_open_checks(run: Path, repo: Path, fills: list[dict], issues: list[str]) -> dict:
    processed = json.loads(
        (run / "source_manifests" / "processed.json").read_text(encoding="utf-8")
    )
    entries = [row for row in processed["entries"] if row["dataset"] == "minute_prices"]
    requests: dict[Path, dict] = {}
    for fill in fills:
        time_ns = int(fill["time_ns"])
        matches = [
            row
            for row in entries
            if row["symbol"] == fill["symbol"]
            and row["market"] == fill["market"]
            and int(row["start"]) <= time_ns <= int(row["end"])
        ]
        if len(matches) != 1:
            issues.append(
                f"{run.name}: {fill['fill_id']} maps to {len(matches)} minute-price partitions"
            )
            continue
        entry = matches[0]
        path = repo / entry["path"]
        if not path.exists():
            path = run.parents[1] / entry["path"]
        request = requests.setdefault(path, {"entry": entry, "fills": []})
        request["fills"].append(fill)

    checked = 0
    hash_matches = 0
    for path, request in requests.items():
        entry = request["entry"]
        if _hash(path) == entry["sha256"]:
            hash_matches += 1
        else:
            issues.append(f"{run.name}: source hash mismatch for {entry['path']}")
        wanted: defaultdict[int, list[dict]] = defaultdict(list)
        for fill in request["fills"]:
            wanted[int(fill["time_ns"])].append(fill)
        found: dict[int, dict] = {}
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(columns=["event_time", "price", "reference_id"]):
            for row in batch.to_pylist():
                event_time = int(row["event_time"])
                if event_time in wanted:
                    found[event_time] = row
        for time_ns, same_open_fills in wanted.items():
            row = found.get(time_ns)
            if row is None:
                issues.extend(
                    f"{run.name}: source open missing for {fill['fill_id']}"
                    for fill in same_open_fills
                )
                continue
            for fill in same_open_fills:
                checked += 1
                if _decimal(row["price"]) != _decimal(fill["reference_price"]):
                    issues.append(f"{run.name}: source open differs for {fill['fill_id']}")
                if row["reference_id"] != fill["trade_id"]:
                    issues.append(f"{run.name}: source reference differs for {fill['fill_id']}")
                expected_reference = f"bar:{fill['symbol']}:{fill['market']}:{time_ns}"
                if fill["trade_id"] != expected_reference:
                    issues.append(f"{run.name}: malformed source reference for {fill['fill_id']}")
    return {
        "source_fill_rows_checked": checked,
        "source_files_checked": len(requests),
        "source_file_hashes_matched": hash_matches,
    }


def _completion_risk_checks(
    run: Path, positions: list[dict], rules: dict[tuple[str, str], dict], issues: list[str]
) -> dict:
    """Explain artifact-recorded pair completions that immediately forced an unwind."""
    risk_rows = _rows(run / "risk_events.parquet")
    failures = [
        row
        for row in risk_rows
        if row["kind"] == "close_requested"
        and row["cause"] == "completion_hedge_or_freshness_failure"
    ]
    parameters = {row["parameter"]: row["value"] for row in _csv(run / "parameters.csv")}
    tolerance = _decimal(parameters["hedge_tolerance"])
    checks = []
    for failure in failures:
        candidates = [
            row
            for row in positions
            if row["strategy"] == failure["strategy"]
            and row["symbol"] == failure["symbol"]
            and int(row["time_ns"]) == int(failure["time_ns"])
        ]
        if not candidates:
            issues.append(f"{run.name}: no position snapshot for completion failure")
            continue
        position = candidates[-1]
        spot = _decimal(position["spot"])
        short = _decimal(position["short"])
        error = abs(spot - short) / spot if spot else (D(0) if not short else D("Infinity"))
        step = _decimal(rules[(failure["symbol"], "futures")]["step"])
        floor_to_step = (spot / step).to_integral_value(rounding=ROUND_FLOOR) * step
        explained = error > tolerance and short == floor_to_step
        if not explained:
            issues.append(f"{run.name}: completion failure is not explained by hedge quantization")
        checks.append(
            {
                "strategy": failure["strategy"],
                "symbol": failure["symbol"],
                "time_ns": int(failure["time_ns"]),
                "spot_after_base_fee": position["spot"],
                "short_after_futures_fill": position["short"],
                "prescribed_futures_step": _text(step),
                "floor_spot_to_futures_step": _text(floor_to_step),
                "hedge_error": _text(error),
                "hedge_tolerance": _text(tolerance),
                "quantization_exceeds_tolerance": explained,
            }
        )
    return {
        "completion_failure_count": len(failures),
        "explanation": (
            "Persisted risk events forced an unwind after the completed opening hedge. "
            "Each listed short equals spot floored to the prescribed futures step, while "
            "the remaining base-fee/step mismatch exceeds hedge_tolerance."
            if checks
            else "No completion hedge or freshness failures were recorded."
        ),
        "checks": checks,
    }


def _daily_components(row: dict[str, str]) -> dict[str, Decimal]:
    symbols = sorted(
        key.removesuffix("_realized_spot") for key in row if key.endswith("_realized_spot")
    )
    components = {
        "spot_pnl": D(0),
        "futures_pnl": D(0),
        "funding": D(0),
        "fees": D(0),
        "liquidation_fees": D(0),
    }
    for symbol in symbols:
        components["spot_pnl"] += (
            _decimal(row[f"{symbol}_realized_spot"])
            + _decimal(row[f"{symbol}_spot"]) * _decimal(row[f"{symbol}_spot_price"])
            - _decimal(row[f"{symbol}_spot_cost"])
        )
        components["futures_pnl"] += _decimal(row[f"{symbol}_realized_futures"]) + (
            _decimal(row[f"{symbol}_short"])
            * (_decimal(row[f"{symbol}_average"]) - _decimal(row[f"{symbol}_mark"]))
        )
        components["funding"] += _decimal(row[f"{symbol}_funding"])
        components["fees"] -= _decimal(row[f"{symbol}_fees"])
        components["liquidation_fees"] -= _decimal(row[f"{symbol}_liquidation_fees"])
    return components


def _exceptional_event_checks(
    run: Path,
    fills: list[dict],
    orders: list[dict],
    positions: list[dict],
    summaries: dict[str, dict[str, str]],
    rules: dict[tuple[str, str], dict],
    issues: list[str],
) -> dict:
    """Reproduce the documented 2023-03-24 spot-halt equity event."""
    daily_rows = _csv(run / "equity_daily.csv")
    risk_rows = _rows(run / "risk_events.parquet")
    final_orders = [row for row in orders if row["record_type"] == "final"]
    strategy_checks = {}
    for strategy, summary in summaries.items():
        strategy_daily = sorted(
            (row for row in daily_rows if row["strategy"] == strategy),
            key=lambda row: int(row["time_ns"]),
        )
        selected = [
            (index, row)
            for index, row in enumerate(strategy_daily)
            if row["timestamp_utc"].startswith(EXCEPTIONAL_EVENT_DATE)
        ]
        if len(selected) != 1 or selected[0][0] == 0:
            issues.append(f"{run.name}: {strategy} exceptional daily row missing or ambiguous")
            continue
        index, event_day = selected[0]
        prior_day = strategy_daily[index - 1]
        before = _daily_components(prior_day)
        after = _daily_components(event_day)
        component_changes = {name: after[name] - before[name] for name in before}
        equity_change = _decimal(event_day["equity"]) - _decimal(prior_day["equity"])
        component_sum = sum(component_changes.values(), D(0))
        if abs(component_sum - equity_change) > TOLERANCE:
            issues.append(f"{run.name}: {strategy} exceptional daily components do not reconcile")

        close_fills = sorted(
            (
                row
                for row in fills
                if row["strategy"] == strategy
                and row["timestamp_utc"].startswith(EXCEPTIONAL_EVENT_DATE)
                and row["purpose"] in {"close_perp", "close_spot"}
            ),
            key=lambda row: int(row["time_ns"]),
        )
        if [row["purpose"] for row in close_fills] != ["close_perp", "close_spot"]:
            issues.append(f"{run.name}: {strategy} exceptional close fills differ")
            continue
        futures_fill, spot_fill = close_fills
        if futures_fill["symbol"] != spot_fill["symbol"]:
            issues.append(f"{run.name}: {strategy} exceptional close symbols differ")
            continue
        symbol = futures_fill["symbol"]
        inactivity = [
            row
            for row in risk_rows
            if row["strategy"] == strategy
            and row["symbol"] == symbol
            and row["kind"] == "close_requested"
            and row["cause"] == "real_market_inactivity"
            and row["timestamp_utc"].startswith(EXCEPTIONAL_EVENT_DATE)
        ]
        if len(inactivity) != 1:
            issues.append(f"{run.name}: {strategy} exceptional inactivity trigger mismatch")
            continue
        risk = inactivity[0]
        unhedged_seconds = D(int(spot_fill["time_ns"]) - int(futures_fill["time_ns"])) / D(
            1_000_000_000
        )
        if unhedged_seconds != D(121 * 60):
            issues.append(f"{run.name}: {strategy} exceptional unhedged duration differs")
        if not int(risk["time_ns"]) < int(futures_fill["time_ns"]) < int(spot_fill["time_ns"]):
            issues.append(f"{run.name}: {strategy} exceptional event ordering differs")

        close_spot_orders = [
            row
            for row in final_orders
            if row["strategy"] == strategy
            and row["symbol"] == symbol
            and row["purpose"] == "close_spot"
            and int(futures_fill["time_ns"]) < int(row["submitted_at"]) < int(spot_fill["time_ns"])
        ]
        expired_orders = [row for row in close_spot_orders if row["status"] == "expired"]
        filled_orders = [row for row in close_spot_orders if row["status"] == "filled"]
        timeout_events = [
            row
            for row in risk_rows
            if row["strategy"] == strategy
            and row["symbol"] == symbol
            and row["kind"] == "attempt_failed"
            and row["cause"] == "timeout"
            and int(futures_fill["time_ns"]) < int(row["time_ns"]) < int(spot_fill["time_ns"])
        ]
        if len(expired_orders) != 60 or len(timeout_events) != len(expired_orders):
            issues.append(f"{run.name}: {strategy} exceptional expired-order count differs")
        if len(filled_orders) != 1 or filled_orders[0]["order_id"] != spot_fill["order_id"]:
            issues.append(f"{run.name}: {strategy} exceptional final spot order differs")
        elif not (
            int(filled_orders[0]["submitted_at"])
            < int(spot_fill["time_ns"])
            < int(filled_orders[0]["deadline"])
        ):
            issues.append(f"{run.name}: {strategy} exceptional final spot timing is not strict")

        event_positions = [
            row
            for row in positions
            if row["strategy"] == strategy
            and row["symbol"] == symbol
            and int(row["time_ns"]) == int(spot_fill["time_ns"])
        ]
        if not event_positions:
            issues.append(f"{run.name}: {strategy} exceptional closing position missing")
            continue
        closed = event_positions[-1]
        spot_step = _decimal(rules[(symbol, "spot")]["step"])
        closed_to_dust = _decimal(closed["short"]) == 0 and _decimal(closed["spot"]) < spot_step
        daily_closed = (
            _decimal(event_day[f"{symbol}_short"]) == 0
            and _decimal(event_day[f"{symbol}_spot"]) < spot_step
        )
        if not closed_to_dust or not daily_closed:
            issues.append(f"{run.name}: {strategy} exceptional position was not closed to dust")

        final_profit = _decimal(summary["final_equity_usdt"]) - _decimal(summary["capital_usdt"])
        strategy_checks[strategy] = {
            "daily_equity_change_usdt": _text(equity_change),
            "component_changes_usdt": {
                name: _text(value) for name, value in component_changes.items()
            },
            "component_sum_usdt": _text(component_sum),
            "final_profit_usdt": _text(final_profit),
            "fraction_of_final_profit": _text(equity_change / final_profit),
            "forced_inactivity": {
                "symbol": symbol,
                "cause": risk["cause"],
                "time_ns": int(risk["time_ns"]),
                "timestamp_utc": risk["timestamp_utc"],
            },
            "futures_close": {
                key: futures_fill[key]
                for key in (
                    "fill_id",
                    "order_id",
                    "timestamp_utc",
                    "time_ns",
                    "quantity",
                    "price",
                    "reference_price",
                    "trade_id",
                )
            },
            "spot_close": {
                key: spot_fill[key]
                for key in (
                    "fill_id",
                    "order_id",
                    "timestamp_utc",
                    "time_ns",
                    "quantity",
                    "price",
                    "reference_price",
                    "trade_id",
                )
            },
            "unhedged_seconds": _text(unhedged_seconds),
            "unhedged_minutes": _text(unhedged_seconds / D(60)),
            "expired_spot_close_orders": len(expired_orders),
            "timeout_risk_events": len(timeout_events),
            "post_close_position": {
                "state": closed["state"],
                "spot": closed["spot"],
                "short": closed["short"],
                "spot_step": _text(spot_step),
                "closed_to_dust": closed_to_dust and daily_closed,
            },
        }
    return {
        "date": EXCEPTIONAL_EVENT_DATE,
        "classification": "documented spot-halt forced unwind with sequential leg execution",
        "interpretation": (
            "Source-backed and arithmetically reconciled, but exceptional outage/legging P&L; "
            "not ordinary carry, live-profit evidence, or investment fitness."
        ),
        "strategies": strategy_checks,
    }


def _audit_run(label: str, run: Path, repo: Path) -> tuple[dict, list[str]]:
    issues: list[str] = []
    fills = _rows(run / "fills.parquet")
    orders = _rows(run / "orders.parquet")
    ledger = _rows(run / "ledger.parquet")
    payments = _rows(run / "funding_payments.parquet")
    all_positions = _rows(run / "positions.parquet")
    positions = [row for row in all_positions if row["snapshot_kind"] == "final"]
    funding_audit = json.loads((run / "funding_mark_audit.json").read_text(encoding="utf-8"))
    summaries = {row["strategy"]: row for row in _csv(run / "run_summary.csv")}
    execution = {
        row["strategy"]: row
        for row in _csv(run / "execution_summary.csv")
        if row["symbol"] == "PORTFOLIO"
    }
    pnl = {
        (row["strategy"], row["component"]): _decimal(row["amount_usdt"])
        for row in _csv(run / "pnl_components.csv")
    }
    rules, slippage = _rules(run)
    completion_risk = _completion_risk_checks(run, all_positions, rules, issues)
    order_final = {row["order_id"]: row for row in orders if row["record_type"] == "final"}

    fill_price_mismatches = 0
    fill_timing_mismatches = 0
    fee_rate_mismatches = 0
    adverse_bps: list[Decimal] = []
    for fill in fills:
        rule = rules[(fill["symbol"], fill["market"])]
        price = _decimal(fill["price"])
        reference = _decimal(fill["reference_price"])
        expected = _expected_fill_price(reference, fill["side"], _decimal(rule["tick"]), slippage)
        if price != expected:
            fill_price_mismatches += 1
            issues.append(f"{run.name}: adverse tick rounding differs for {fill['fill_id']}")
        if _decimal(fill["fee_rate"]) != _decimal(rule["taker_fee"]):
            fee_rate_mismatches += 1
            issues.append(f"{run.name}: prescribed fee differs for {fill['fill_id']}")
        order = order_final.get(fill["order_id"])
        if order is None or not int(order["submitted_at"]) < int(fill["time_ns"]) < int(
            order["deadline"]
        ):
            fill_timing_mismatches += 1
            issues.append(f"{run.name}: non-strict fill timing for {fill['fill_id']}")
        adverse_bps.append(
            (price / reference - D(1)) * D(10000)
            if fill["side"] == "BUY"
            else (D(1) - price / reference) * D(10000)
        )

    source_checks = _source_open_checks(run, repo, fills, issues)
    payment_by_key = {
        (row["strategy"], row["symbol"], int(row["time_ns"])): row for row in payments
    }
    terminal_by_key = {(row["strategy"], row["symbol"]): row for row in positions}
    consumed = funding_audit["consumed"]
    strategy_results = {}
    expected_payment_keys: set[tuple[str, str, int]] = set()

    for strategy, summary in summaries.items():
        if summary["status"] != "complete":
            issues.append(f"{run.name}: {strategy} run status is {summary['status']}")
        capital = _decimal(summary["capital_usdt"])
        cash = capital
        state: defaultdict[str, dict[str, Decimal]] = defaultdict(_state)
        events: list[tuple[int, int, str, dict]] = []
        for row in consumed:
            if row["strategy"] == strategy and row["economic_window"]:
                events.append((int(row["funding_time"]), 0, row["symbol"], row))
        strategy_fills = [row for row in fills if row["strategy"] == strategy]
        for row in strategy_fills:
            events.append((int(row["time_ns"]), 1, row["symbol"], row))
        same_time_funding_and_fill = len(
            {time for time, kind, _, _ in events if kind == 0}
            & {time for time, kind, _, _ in events if kind == 1}
        )
        funding_checks: list[dict] = []
        fill_payoffs: list[dict] = []

        for time_ns, kind, symbol, row in sorted(
            events, key=lambda item: (item[0], item[1], item[2])
        ):
            current = state[symbol]
            if kind == 0:
                amount = (
                    current["short"]
                    * _decimal(row["settlement_mark_price"])
                    * _decimal(row["funding_rate"])
                )
                if amount:
                    key = (strategy, symbol, time_ns)
                    expected_payment_keys.add(key)
                    actual = payment_by_key.get(key)
                    actual_amount = _decimal(actual["amount_usdt"]) if actual else None
                    if actual_amount is None or abs(actual_amount - amount) > TOLERANCE:
                        issues.append(f"{run.name}: funding payment mismatch for {key}")
                    funding_checks.append(
                        {
                            "time_ns": time_ns,
                            "symbol": symbol,
                            "short_before_settlement": _text(current["short"]),
                            "settlement_mark": row["settlement_mark_price"],
                            "funding_rate": row["funding_rate"],
                            "recomputed_amount_usdt": _text(amount),
                            "reported_amount_usdt": actual["amount_usdt"] if actual else None,
                        }
                    )
                    current["funding"] += amount
                    cash += amount
                continue

            quantity = _decimal(row["quantity"])
            price = _decimal(row["price"])
            fee = quantity * price * _decimal(row["fee_rate"])
            current["fees"] += fee
            cash_effect = D(0)
            if row["market"] == "spot":
                if row["side"] == "BUY":
                    received = quantity * (D(1) - _decimal(row["fee_rate"]))
                    current["spot"] += received
                    current["spot_cost"] += received * price
                    cash_effect = -(quantity * price)
                else:
                    if quantity > current["spot"]:
                        issues.append(f"{run.name}: spot oversell at {row['fill_id']}")
                    basis = current["spot_cost"] * quantity / current["spot"]
                    current["spot"] -= quantity
                    current["spot_cost"] -= basis
                    current["realized_spot"] += quantity * price - basis
                    cash_effect = quantity * price - fee
            elif row["side"] == "SELL":
                new_short = current["short"] + quantity
                current["average"] = (
                    current["average"] * current["short"] + price * quantity
                ) / new_short
                current["short"] = new_short
                cash_effect = -fee
            else:
                if quantity > current["short"]:
                    issues.append(f"{run.name}: futures over-close at {row['fill_id']}")
                realized = (current["average"] - price) * quantity
                current["realized_futures"] += realized
                current["short"] -= quantity
                if current["short"] == 0:
                    current["average"] = D(0)
                cash_effect = realized - fee
            cash += cash_effect
            fill_payoffs.append(
                {
                    "fill_id": row["fill_id"],
                    "time_ns": time_ns,
                    "symbol": symbol,
                    "market": row["market"],
                    "side": row["side"],
                    "quantity": row["quantity"],
                    "price": row["price"],
                    "fee_usdt": _text(fee),
                    "cash_effect_usdt": _text(cash_effect),
                }
            )

        position_differences: dict[str, dict[str, str]] = {}
        terminal_spot_value = D(0)
        terminal_futures_unrealized = D(0)
        reported_collateral = D(0)
        for symbol in sorted({row["symbol"] for row in positions if row["strategy"] == strategy}):
            reported = terminal_by_key[(strategy, symbol)]
            current = state[symbol]
            terminal_spot_value += current["spot"] * _decimal(reported["spot_price"])
            terminal_futures_unrealized += (
                current["average"] - _decimal(reported["mark_price"])
            ) * current["short"]
            reported_collateral += _decimal(reported["collateral"])
            compared = {
                "spot": "spot",
                "spot_cost": "spot_cost",
                "realized_spot": "realized_spot",
                "short": "short",
                "average": "average",
                "realized_futures": "realized_futures",
                "funding": "funding",
                "fees": "fees",
            }
            differences = {
                field: _text(current[field] - _decimal(reported[reported_field]))
                for field, reported_field in compared.items()
            }
            position_differences[symbol] = differences
            for field, difference in differences.items():
                if abs(_decimal(difference)) > TOLERANCE:
                    issues.append(f"{run.name}: {strategy}/{symbol} terminal {field} mismatch")

        equity = cash + terminal_spot_value + terminal_futures_unrealized
        reported_equity = _decimal(summary["final_equity_usdt"])
        reported_cash = (
            _decimal(summary["free_spot"])
            + _decimal(summary["free_futures"])
            + reported_collateral
            - _decimal(summary["debt_usdt"])
        )
        aggregate_funding = sum((row["funding"] for row in state.values()), D(0))
        aggregate_fees = sum((row["fees"] for row in state.values()), D(0))
        spot_pnl = sum(
            (
                current["realized_spot"]
                + current["spot"] * _decimal(terminal_by_key[(strategy, symbol)]["spot_price"])
                - current["spot_cost"]
            )
            for symbol, current in state.items()
        )
        futures_pnl = sum(
            (
                current["realized_futures"]
                + (current["average"] - _decimal(terminal_by_key[(strategy, symbol)]["mark_price"]))
                * current["short"]
            )
            for symbol, current in state.items()
        )
        component_differences = {
            "spot_pnl": spot_pnl - pnl[(strategy, "spot_pnl")],
            "futures_pnl": futures_pnl - pnl[(strategy, "futures_pnl")],
            "funding": aggregate_funding - pnl[(strategy, "funding")],
            "fees": -aggregate_fees - pnl[(strategy, "fees")],
        }
        for component, difference in component_differences.items():
            if abs(difference) > TOLERANCE:
                issues.append(f"{run.name}: {strategy} {component} mismatch")

        final_orders = sum(1 for row in order_final.values() if row["strategy"] == strategy)
        fill_ledger_rows = sum(
            1 for row in ledger if row["strategy"] == strategy and row["kind"] != "funding"
        )
        funding_ledger_rows = sum(
            1 for row in ledger if row["strategy"] == strategy and row["kind"] == "funding"
        )
        strategy_payments = sum(1 for row in payments if row["strategy"] == strategy)
        expected_counts = {
            "fills": len(strategy_fills),
            "reported_fills": int(execution[strategy]["fills"]),
            "native_fill_count": int(execution[strategy]["native_fill_count"]),
            "native_reconciliation_count": int(execution[strategy]["native_reconciliation_count"]),
            "fill_ledger_rows": fill_ledger_rows,
            "orders": final_orders,
            "reported_orders": int(execution[strategy]["orders"]),
            "funding_payments": strategy_payments,
            "funding_ledger_rows": funding_ledger_rows,
            "recomputed_nonzero_funding_payments": len(funding_checks),
        }
        if (
            len(
                set(
                    expected_counts[name]
                    for name in (
                        "fills",
                        "reported_fills",
                        "native_fill_count",
                        "native_reconciliation_count",
                        "fill_ledger_rows",
                    )
                )
            )
            != 1
        ):
            issues.append(f"{run.name}: {strategy} native fill counts differ")
        if final_orders != int(execution[strategy]["orders"]):
            issues.append(f"{run.name}: {strategy} native order counts differ")
        if len({strategy_payments, funding_ledger_rows, len(funding_checks)}) != 1:
            issues.append(f"{run.name}: {strategy} funding counts differ")
        if abs(equity - reported_equity) > TOLERANCE:
            issues.append(f"{run.name}: {strategy} terminal equity mismatch")
        if abs(cash - reported_cash) > TOLERANCE:
            issues.append(f"{run.name}: {strategy} terminal cash mismatch")

        strategy_results[strategy] = {
            "counts": expected_counts,
            "same_time_funding_and_fill_events": same_time_funding_and_fill,
            "first_funding_payment": funding_checks[0] if funding_checks else None,
            "last_funding_payment": funding_checks[-1] if funding_checks else None,
            "first_fill_payoff": fill_payoffs[0] if fill_payoffs else None,
            "last_fill_payoff": fill_payoffs[-1] if fill_payoffs else None,
            "recomputed": {
                "cash_after_realized_flows_usdt": _text(cash),
                "terminal_spot_value_usdt": _text(terminal_spot_value),
                "terminal_futures_unrealized_usdt": _text(terminal_futures_unrealized),
                "terminal_equity_usdt": _text(equity),
                "spot_pnl_usdt": _text(spot_pnl),
                "futures_pnl_usdt": _text(futures_pnl),
                "funding_usdt": _text(aggregate_funding),
                "fees_usdt": _text(aggregate_fees),
            },
            "reported": {
                "status": summary["status"],
                "cash_plus_collateral_less_debt_usdt": _text(reported_cash),
                "terminal_equity_usdt": summary["final_equity_usdt"],
            },
            "differences": {
                "cash_usdt": _text(cash - reported_cash),
                "terminal_equity_usdt": _text(equity - reported_equity),
                "pnl_components_usdt": {
                    key: _text(value) for key, value in component_differences.items()
                },
                "terminal_positions": position_differences,
            },
        }

    unexpected_payments = set(payment_by_key) - expected_payment_keys
    if unexpected_payments:
        issues.append(f"{run.name}: {len(unexpected_payments)} unexpected funding payment rows")
    exceptional_event = (
        _exceptional_event_checks(run, fills, orders, all_positions, summaries, rules, issues)
        if label == "early_2022_2023"
        else None
    )

    return (
        {
            "label": label,
            "run_id": run.name,
            "path": run.as_posix(),
            "status": "passed" if not issues else "failed",
            "fill_checks": {
                "fills_checked": len(fills),
                "adverse_tick_rounding_mismatches": fill_price_mismatches,
                "prescribed_fee_rate_mismatches": fee_rate_mismatches,
                "strict_order_timing_mismatches": fill_timing_mismatches,
                "minimum_realized_adverse_bps": _text(min(adverse_bps)) if adverse_bps else None,
                "maximum_realized_adverse_bps": _text(max(adverse_bps)) if adverse_bps else None,
                **source_checks,
            },
            "funding_audit_native_counts": {
                "engine_consumed_count": funding_audit["engine_consumed_count"],
                "consumed_rows": len(consumed),
                "exact_consumed_count": funding_audit["exact_consumed_count"],
                "proxy_consumed_count": funding_audit["proxy_consumed_count"],
                "warmup_not_required_count": funding_audit["warmup_not_required_count"],
                "validated_count": funding_audit["validated_count"],
                "counts_by_strategy": funding_audit["counts_by_strategy"],
            },
            "completion_risk_checks": completion_risk,
            **({"exceptional_event": exceptional_event} if exceptional_event else {}),
            "strategies": strategy_results,
            "issues": issues,
        },
        issues,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--early", type=Path, default=DEFAULT_RUNS["early_2022_2023"])
    parser.add_argument("--late", type=Path, default=DEFAULT_RUNS["late_2025_2026"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    output = args.output or Path(__file__).with_name("annual-economic-audit.json")
    runs = {"early_2022_2023": args.early, "late_2025_2026": args.late}
    audited = {}
    all_issues: list[str] = []
    for label, path in runs.items():
        audited[label], issues = _audit_run(label, path.resolve(), repo)
        all_issues.extend(issues)
    result = {
        "audit": "independent annual minute financial reconstruction",
        "status": "passed" if not all_issues else "failed",
        "tolerance": _text(TOLERANCE),
        "method": {
            "arithmetic": "Decimal replay of persisted artifacts; no engine Ledger or cost helper imports",
            "spot_buy": "cash -= quantity * fill price; inventory += quantity * (1 - fee rate)",
            "spot_sell": "cash += quantity * fill price * (1 - fee rate)",
            "futures": "weighted short entry; reductions realize quantity * (average - fill price); taker fee on every fill",
            "funding": "short before observed funding_time * settlement mark * rate; funding precedes fills at equal time",
            "terminal_equity": "cash + spot inventory at terminal spot price + short * (average - terminal mark)",
            "fill_price": "reference open moved adversely by configured 1 bp and rounded adversely to prescribed tick",
        },
        "runs": audited,
        "issues": all_issues,
        "interpretation_limit": (
            "A pass establishes artifact-level arithmetic, timing, source-open, and reporting consistency "
            "within the declared tolerance. It does not establish live profitability or fitness for investment."
        ),
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps({"status": result["status"], "issues": len(all_issues), "output": str(output)})
    )
    return 0 if not all_issues else 1


if __name__ == "__main__":
    raise SystemExit(main())

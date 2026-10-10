"""Three separate views of persisted evaluations and executed actions."""

import json
from collections import Counter, defaultdict

from .common import number, truth

STATES = {"pass", "fail", "not_evaluable"}


def classify(row, *, validate_recorded=True, basis_max="0.005"):
    order = json.loads(row["filter_order"])
    if len(order) != len(set(order)):
        raise ValueError("Duplicate filter order")
    values = {name: row["filter_" + name] for name in order}
    if any(v not in STATES for v in values.values()):
        raise ValueError("Unknown filter state")
    enabled = truth(row["funding_filter_enabled"])
    applied = {
        name: not (name in {"funding", "funding_positive"} and not enabled)
        and not (name == "price_alignment" and not truth(row["price_alignment_enforced"]))
        for name in order
    }
    failed = [name for name in order if values[name] == "fail"]
    unknown = [name for name in order if values[name] == "not_evaluable"]
    first = next(
        (
            ("not_evaluable:" if values[n] == "not_evaluable" else "") + n
            for n in order
            if applied[n] and values[n] != "pass"
        ),
        "all_pass",
    )
    if validate_recorded:
        if (row.get("sequential_rejection") or "all_pass") != first:
            raise ValueError("Recorded sequential rejection disagrees with recorded order")
        if json.loads(row["simultaneous_rejections"]) != failed:
            raise ValueError("Recorded simultaneous failures disagree")
        if json.loads(row["simultaneous_not_evaluable"]) != unknown:
            raise ValueError("Recorded simultaneous unknowns disagree")
    funding = row["filter_funding"]
    negative, high = row["filter_basis_negative"], row["filter_basis_above_max"]
    basis = (
        "not_evaluable"
        if "not_evaluable" in (negative, high)
        else "fail"
        if "fail" in (negative, high)
        else "pass"
    )
    reason = (
        "negative"
        if negative == "fail"
        else "above_max"
        if high == "fail"
        else "unknown"
        if basis == "not_evaluable"
        else "within_inclusive_range"
    )
    if row["decision_kind"] == "renewal":
        cell = "not_applicable_renewal"
    elif "not_evaluable" in (funding, basis):
        cell = "not_evaluable"
    else:
        cell = {
            ("pass", "pass"): "both_pass",
            ("fail", "pass"): "funding_only_fail",
            ("pass", "fail"): "basis_only_fail",
            ("fail", "fail"): "both_fail",
        }[funding, basis]
    if validate_recorded and row["decision_kind"] == "entry":
        if basis != "not_evaluable":
            value = number(row["basis"])
            if (value < 0) != (negative == "fail") or (value > number(basis_max)) != (
                high == "fail"
            ):
                raise ValueError("Basis classifications disagree with inclusive bounds")
        if funding != "not_evaluable":
            expected = number(row["forecast"]) > number(row["estimated_cycle_cost"])
            if expected != (funding == "pass"):
                raise ValueError("Funding classification disagrees with forecast/cost")
    if validate_recorded and row["decision_kind"] == "renewal":
        state = row["filter_funding_positive"]
        if state != "not_evaluable" and ((number(row["forecast"]) > 0) != (state == "pass")):
            raise ValueError("Renewal must use zero funding threshold")
    return dict(
        market_cell=cell,
        basis_state=basis,
        basis_reason=reason,
        unknown_market_reasons=json.dumps(
            [
                n
                for n in ("funding", "basis_negative", "basis_above_max")
                if row["filter_" + n] == "not_evaluable"
            ]
        ),
        first_block=first,
        simultaneous_failures=json.dumps(failed),
        simultaneous_unknowns=json.dumps(unknown),
        applied_failures=json.dumps([n for n in failed if applied[n]]),
        budget_interpretation="prospective_with_prior_state"
        if row.get("filter_state_active") == "fail"
        else "prospective_no_prior_active_state",
    )


def identify(rows, source_file):
    multiplicity = Counter((r["symbol"], int(r["decision_time"]), r["decision_kind"]) for r in rows)
    seen, output = set(), []
    for ordinal, row in enumerate(rows):
        fingerprint = json.dumps(
            {k: v for k, v in row.items() if k not in {"units", "source_row", "evaluation_id"}},
            sort_keys=True,
        )
        if fingerprint in seen:
            raise ValueError("Duplicate identical evaluation")
        seen.add(fingerprint)
        if int(row["time_ns"]) != int(row["decision_time"]):
            raise ValueError("Evaluation timestamp disagrees")
        output.append(
            dict(
                row,
                source_file=source_file,
                source_row=ordinal,
                evaluation_id=f"{row['run_id']}:{source_file}:{ordinal}",
                timestamp_multiplicity=multiplicity[
                    row["symbol"], int(row["decision_time"]), row["decision_kind"]
                ],
            )
        )
    return output


def link_actions(evaluations, events, orders, fills):
    lookup = defaultdict(list)
    for row in evaluations:
        lookup[row["symbol"], int(row["decision_time"])].append(row)
    submissions = {r["order_id"]: r for r in orders if r.get("action") == "submitted"}
    result = []
    for source, rows in (
        ("risk_events.parquet", events),
        ("orders.parquet", orders),
        ("fills.parquet", fills),
    ):
        for ordinal, row in enumerate(rows):
            if source == "orders.parquet" and row.get("action") != "submitted":
                continue
            candidates = lookup[row["symbol"], int(row["time_ns"])]
            kind = (
                "renewal"
                if row.get("kind") in {"renewal", "rebalance_skipped"}
                or row.get("cause") in {"holding_expiry", "renewal_rebalance"}
                else "entry"
                if row.get("cause") == "entry"
                or row.get("purpose") == "open_spot"
                and row.get("action") == "submitted"
                else None
            )
            if kind:
                candidates = [c for c in candidates if c["decision_kind"] == kind]
            linked = candidates[0] if len(candidates) == 1 else None
            order_id = row.get("order_id") or ""
            submitted = submissions.get(order_id)
            roots = (
                lookup[row["symbol"], int(submitted["submitted_at"])]
                if submitted and submitted.get("purpose") == "open_spot"
                else []
            )
            roots = [
                c
                for c in roots
                if c["decision_kind"] == "entry" and c.get("decision") == "accepted"
            ]
            result.append(
                dict(
                    run_id=row.get("run_id", evaluations[0]["run_id"]),
                    strategy=row.get("strategy", ""),
                    symbol=row["symbol"],
                    source_file=source,
                    source_row=ordinal,
                    time_ns=int(row["time_ns"]),
                    kind=row.get("kind") or row.get("action") or "fill",
                    cause=row.get("cause") or "",
                    purpose=row.get("purpose") or "",
                    order_id=order_id,
                    fill_id=row.get("fill_id") or "",
                    cycle_id=row.get("cycle_id") or "",
                    evaluation_id=linked["evaluation_id"] if linked else "",
                    link_status="exact_time_unique"
                    if linked
                    else "unreconciled_ambiguous_time"
                    if candidates
                    else "unreconciled_no_exact_evaluation",
                    link_scope="temporal_concordance_only; causal_for_entry_transition_or_root_order",
                    accepted_entry_order_evaluation_id=roots[0]["evaluation_id"]
                    if len(roots) == 1
                    else "",
                    actual_decision=linked.get("decision") or "" if linked else "",
                )
            )
    return result


def analyze_decisions(signals, renewals, events, orders, fills, periods, basis_max):
    rows = identify(signals, "signals.parquet") + identify(renewals, "renewal_diagnostics.parquet")
    retained = {
        "run_id",
        "strategy",
        "symbol",
        "time_ns",
        "timestamp_utc",
        "decision_time",
        "decision_kind",
        "anchor",
        "forecast_anchor",
        "funding_filter_enabled",
        "price_alignment_enforced",
        "forecast",
        "estimated_cycle_cost",
        "basis",
        "basis_raw",
        "portfolio_state",
        "current_spot",
        "current_short",
        "available_cash",
        "equity_snapshot",
        "target_usdt",
        "budget_required_cash",
        "budget_reason",
        "sizing_reason",
        "prospective_sizing_reason",
        "sizing_enforcement",
        "decision",
        "actual_outcome",
        "state_after",
        "expiry_after",
        "renewal_status_kind",
        "renewal_funding_threshold",
        "source_file",
        "source_row",
        "evaluation_id",
        "timestamp_multiplicity",
        "sequential_rejection",
        "simultaneous_rejections",
        "simultaneous_not_evaluable",
    }
    classified = [
        dict(
            {k: v for k, v in row.items() if k in retained or k.startswith("filter_")},
            **classify(row, basis_max=basis_max),
        )
        for row in rows
    ]
    groups, reasons, decision_cross = summarize_decisions(
        classified, periods, rows[0]["run_id"], rows[0]["strategy"]
    )
    return dict(
        classified=classified,
        groups=groups,
        reasons=reasons,
        decision_cross=decision_cross,
        actions=link_actions(rows, events, orders, fills),
    )


def summarize_decisions(classified, periods, run_id, strategy):
    """Derive every aggregate from the declared evaluation population."""
    groups, reasons, decision_cross = [], [], []
    for period, lower, upper in periods:
        for symbol in ("BTCUSDT", "ETHUSDT", "PORTFOLIO"):
            for kind in ("entry", "renewal"):
                selected = [
                    r
                    for r in classified
                    if lower <= int(r["time_ns"]) < upper
                    and (symbol == "PORTFOLIO" or r["symbol"] == symbol)
                    and r["decision_kind"] == kind
                ]
                common = dict(
                    run_id=run_id,
                    strategy=strategy,
                    period=period,
                    start_ns=lower,
                    end_exclusive_ns=upper,
                    symbol=symbol,
                    decision_kind=kind,
                    denominator=len(selected),
                )
                for view, field in (
                    ("market", "market_cell"),
                    ("sequential", "first_block"),
                    ("actual_decision", "decision"),
                    ("basis_reason", "basis_reason"),
                ):
                    if view in {"market", "basis_reason"} and kind != "entry":
                        continue
                    counts = Counter((r.get(field) or "not_recorded") for r in selected)
                    if view == "market":
                        for name in (
                            "both_pass",
                            "funding_only_fail",
                            "basis_only_fail",
                            "both_fail",
                            "not_evaluable",
                        ):
                            counts.setdefault(name, 0)
                    for label, count in sorted(counts.items()):
                        groups.append(
                            dict(
                                **common,
                                view=view,
                                group=label,
                                count=count,
                                fraction=count / len(selected) if selected else None,
                            )
                        )
                counts = Counter()
                for row in selected:
                    for rank, name in enumerate(json.loads(row["filter_order"])):
                        applied = not (
                            name in {"funding", "funding_positive"}
                            and not truth(row["funding_filter_enabled"])
                        ) and not (
                            name == "price_alignment" and not truth(row["price_alignment_enforced"])
                        )
                        counts[rank, name, row["filter_" + name], applied] += 1
                for (rank, name, state, applied), count in sorted(counts.items()):
                    reasons.append(
                        dict(
                            **common,
                            order_position=rank,
                            filter=name,
                            state=state,
                            applied=applied,
                            count=count,
                            overlaps=True,
                            fraction=count / len(selected),
                        )
                    )
                for (first, actual), count in sorted(
                    Counter(
                        (r["first_block"], r.get("decision") or "not_recorded") for r in selected
                    ).items()
                ):
                    decision_cross.append(
                        dict(**common, first_block=first, actual_decision=actual, count=count)
                    )
    return groups, reasons, decision_cross


def paired_coverage(classified, periods):
    result = []
    for period, lower, upper in periods:
        for symbol in ("BTCUSDT", "ETHUSDT"):
            for kind in ("entry", "renewal"):
                sides = {}
                for strategy in ("conditional", "permanent"):
                    sides[strategy] = Counter(
                        int(r["decision_time"])
                        for r in classified
                        if r["strategy"] == strategy
                        and r["symbol"] == symbol
                        and r["decision_kind"] == kind
                        and lower <= int(r["decision_time"]) < upper
                    )
                a, b = sides["conditional"], sides["permanent"]
                paired = sum(1 for t in a.keys() & b.keys() if a[t] == b[t] == 1)
                result.append(
                    dict(
                        period=period,
                        symbol=symbol,
                        decision_kind=kind,
                        conditional_rows=sum(a.values()),
                        permanent_rows=sum(b.values()),
                        paired_unique=paired,
                        conditional_unpaired=sum(a.values()) - paired,
                        permanent_unpaired=sum(b.values()) - paired,
                        conditional_pair_fraction=paired / sum(a.values()) if a else None,
                        permanent_pair_fraction=paired / sum(b.values()) if b else None,
                    )
                )
    return result

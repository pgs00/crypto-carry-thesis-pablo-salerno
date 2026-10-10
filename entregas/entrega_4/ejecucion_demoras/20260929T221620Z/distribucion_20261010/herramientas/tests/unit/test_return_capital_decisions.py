"""Persisted diagnostics are not counterfactual trades or elapsed market time."""

import json
from collections import Counter

import pytest

from scripts.return_capital.decisions import classify, identify, link_actions


def entry(funding="pass", negative="pass", high="pass", **extra):
    order = ["state_active", "funding", "basis_negative", "basis_above_max", "budget"]
    row = dict(
        run_id="r",
        symbol="BTCUSDT",
        decision_time=1,
        time_ns=1,
        decision_kind="entry",
        anchor=0,
        funding_filter_enabled=True,
        price_alignment_enforced=True,
        filter_order=json.dumps(order),
        filter_state_active="pass",
        filter_funding=funding,
        filter_basis_negative=negative,
        filter_basis_above_max=high,
        filter_budget="pass",
        portfolio_state="FLAT",
        decision="test",
    )
    row.update(extra)
    return row


def test_four_cells_and_unknown_partition():
    rows = [
        entry(),
        entry("fail"),
        entry(negative="fail"),
        entry("fail", negative="fail"),
        entry("not_evaluable"),
    ]
    assert Counter(classify(r, validate_recorded=False)["market_cell"] for r in rows) == {
        "both_pass": 1,
        "funding_only_fail": 1,
        "basis_only_fail": 1,
        "both_fail": 1,
        "not_evaluable": 1,
    }


def test_funding_not_applied_for_permanent_and_renewal_uses_zero():
    result = classify(entry("fail", funding_filter_enabled=False), validate_recorded=False)
    assert result["market_cell"] == "funding_only_fail"
    assert result["first_block"] == "all_pass"
    renewal = entry(
        "fail",
        decision_kind="renewal",
        forecast="0.001",
        estimated_cycle_cost="0.0034",
        filter_order='["state_holding","funding_positive"]',
        filter_state_holding="pass",
        filter_funding_positive="pass",
    )
    result = classify(renewal, validate_recorded=False)
    assert result["first_block"] == "all_pass"
    assert result["market_cell"] == "not_applicable_renewal"


@pytest.mark.parametrize(
    "basis,negative,high",
    [
        ("-0.0001", "fail", "pass"),
        ("0", "pass", "pass"),
        ("0.005", "pass", "pass"),
        ("0.00501", "pass", "fail"),
        (None, "not_evaluable", "not_evaluable"),
    ],
)
def test_basis_boundaries_and_unknown(basis, negative, high):
    result = classify(entry(basis=basis, negative=negative, high=high), validate_recorded=False)
    assert result["basis_state"] == (
        "not_evaluable" if basis is None else "fail" if "fail" in (negative, high) else "pass"
    )


def test_simultaneous_does_not_change_recorded_sequential_order():
    row = entry(
        "fail",
        negative="fail",
        filter_state_active="fail",
        filter_budget="fail",
        basis="-0.001",
        forecast="0.001",
        estimated_cycle_cost="0.0034",
        sequential_rejection="state_active",
        simultaneous_rejections='["state_active","funding","basis_negative","budget"]',
        simultaneous_not_evaluable="[]",
    )
    result = classify(row)
    assert result["first_block"] == "state_active"
    assert len(json.loads(result["simultaneous_failures"])) == 4
    assert result["budget_interpretation"] == "prospective_with_prior_state"
    with pytest.raises(ValueError, match="sequential"):
        classify(dict(row, sequential_rejection="funding"))


def test_legitimate_ties_and_illegitimate_duplicates():
    rows = identify([entry(), entry(anchor=2)], "signals.parquet")
    assert len({r["evaluation_id"] for r in rows}) == 2
    assert all(r["timestamp_multiplicity"] == 2 for r in rows)
    with pytest.raises(ValueError, match="Duplicate"):
        identify([entry(), entry()], "signals.parquet")


def test_unlinked_actions_remain_unreconciled():
    rows = identify([entry()], "signals.parquet")
    actions = [
        dict(symbol="BTCUSDT", time_ns=1, kind="transition", cause="entry"),
        dict(symbol="BTCUSDT", time_ns=2, kind="attempt_failed", order_id="o"),
    ]
    result = link_actions(rows, actions, [], [])
    assert result[0]["link_status"] == "exact_time_unique"
    assert result[1]["link_status"] == "unreconciled_no_exact_evaluation"


def test_action_source_ordinal_survives_submission_filter():
    rows = identify([entry()], "signals.parquet")
    orders = [
        dict(symbol="BTCUSDT", time_ns=1, action="snapshot", order_id="o"),
        dict(
            symbol="BTCUSDT",
            time_ns=1,
            submitted_at=1,
            action="submitted",
            order_id="o",
            purpose="open_spot",
        ),
    ]
    result = link_actions(rows, [], orders, [])
    assert result[0]["source_row"] == 1

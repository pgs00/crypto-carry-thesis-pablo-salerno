"""Literal H2 expectations independent of the report and its verifier."""

import ast
import csv
import inspect
import io
from decimal import Decimal as D

import pytest

from scripts import rules_sensitivity_h2 as h2


def metrics(cagr=-0.01, conditional_sharpe=-0.5, permanent_sharpe=-1):
    common = dict(
        scenario="BASE_E3",
        period="full",
        start_utc="2022-01-01T00:00:00Z",
        end_exclusive_utc="2024-01-01T00:00:00Z",
        coverage_complete=True,
    )
    return [
        dict(common, strategy="conditional", run_id="cond", cagr=cagr, sharpe=conditional_sharpe),
        dict(common, strategy="permanent", run_id="perm", cagr=0.5, sharpe=permanent_sharpe),
    ]


def test_negative_cagr_cannot_support_h2_despite_superior_negative_sharpe():
    assert h2.h2_comparison(metrics())[0]["verdict"] == "no_favorable"


@pytest.mark.parametrize(
    "cagr,sc,sp,difference,positive,superior,verdict,reason",
    [
        (0.01, 2, 1, "1", True, True, "favorable", "cagr_positive_and_sharpe_superior"),
        (-0.01, -0.5, -1, "0.5", False, True, "no_favorable", "cagr_not_positive"),
        (0, 2, 1, "1", False, True, "no_favorable", "cagr_not_positive"),
        (0.01, 1, 1, "0", True, False, "no_favorable", "sharpe_not_superior"),
        (0.01, 1, 2, "-1", True, False, "no_favorable", "sharpe_not_superior"),
        (None, 2, 1, "1", None, True, "no_concluyente", "undefined_or_nonfinite_conditional_cagr"),
        (
            0.01,
            None,
            1,
            None,
            True,
            None,
            "no_concluyente",
            "undefined_or_nonfinite_conditional_sharpe",
        ),
        (0.01, -0.5, -1, "0.5", True, True, "favorable", "cagr_positive_and_sharpe_superior"),
    ],
)
def test_literal_complete_h2_contract(
    cagr, sc, sp, difference, positive, superior, verdict, reason
):
    rows = metrics(cagr, sc, sp)
    expected = dict(
        scenario="BASE_E3",
        period="full",
        start_utc="2022-01-01T00:00:00Z",
        end_exclusive_utc="2024-01-01T00:00:00Z",
        conditional_start_utc="2022-01-01T00:00:00Z",
        conditional_end_exclusive_utc="2024-01-01T00:00:00Z",
        permanent_start_utc="2022-01-01T00:00:00Z",
        permanent_end_exclusive_utc="2024-01-01T00:00:00Z",
        conditional_run_id="cond",
        permanent_run_id="perm",
        conditional_cagr=None if cagr is None else D(str(cagr)),
        conditional_sharpe=None if sc is None else D(str(sc)),
        permanent_sharpe=D(str(sp)),
        sharpe_difference=None if difference is None else D(difference),
        cagr_positive=positive,
        sharpe_superior=superior,
        verdict=verdict,
        reason=reason,
    )
    assert h2.h2_comparison(rows) == [expected]
    assert h2.validate_h2_rows([expected], rows) is None


@pytest.mark.parametrize(
    "field,strategy", [("cagr", "conditional"), ("sharpe", "conditional"), ("sharpe", "permanent")]
)
@pytest.mark.parametrize("value", [None, "", "ND", "NaN", "Infinity", "-Infinity"])
def test_unknown_and_nonfinite_values_remain_unknown(field, strategy, value):
    rows = metrics(0.01, 2, 1)
    rows[0 if strategy == "conditional" else 1][field] = value
    result = h2.h2_comparison(rows)[0]
    assert result["verdict"] == "no_concluyente"
    assert result[f"{strategy}_{field}"] is None
    assert result["cagr_positive"] is (None if field == "cagr" else True)
    assert result["sharpe_superior"] is (True if field == "cagr" else None)
    assert result["reason"] == f"undefined_or_nonfinite_{strategy}_{field}"
    h2.validate_h2_rows([result], rows)


@pytest.mark.parametrize("missing", [0, 1])
def test_missing_portfolio_preserves_evaluable_components(missing):
    rows = metrics(0.01, 2, 1)
    del rows[missing]
    result = h2.h2_comparison(rows)[0]
    assert result["verdict"] == "no_concluyente"
    assert result["cagr_positive"] is (None if missing == 0 else True)
    assert result["sharpe_superior"] is None
    assert result["start_utc"] is None
    assert f"missing_{'conditional' if missing == 0 else 'permanent'}_portfolio" in result["reason"]
    h2.validate_h2_rows([result], rows)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("start_utc", "2022-01-02T00:00:00Z", "noncomparable_window"),
        ("end_exclusive_utc", "2023-01-01T00:00:00Z", "noncomparable_window"),
        ("start_utc", "invalid", "noncomparable_window"),
        ("coverage_complete", False, "incomplete_permanent_coverage"),
        ("coverage_complete", "False", "incomplete_permanent_coverage"),
        ("coverage_complete", "", "incomplete_permanent_coverage"),
    ],
)
def test_noncomparable_or_incomplete_retains_numeric_components(field, value, reason):
    rows = metrics(0.01, 2, 1)
    rows[1][field] = value
    result = h2.h2_comparison(rows)[0]
    assert result["verdict"] == "no_concluyente"
    assert result["cagr_positive"] is True
    assert result["sharpe_superior"] is True
    assert reason in result["reason"]
    h2.validate_h2_rows([result], rows)


def test_duplicate_source_key_is_rejected_by_both_paths():
    rows = metrics()
    rows.append(dict(rows[0], run_id="conflicting"))
    with pytest.raises(ValueError, match="duplicate"):
        h2.h2_comparison(rows)
    with pytest.raises(ValueError, match="duplicate"):
        h2.validate_h2_rows([], rows)


def test_strict_comparisons_do_not_round_and_do_not_compare_permanent_cagr():
    rows = metrics("0.000000000000000000001", "1.000000000000000000001", "1")
    result = h2.h2_comparison(rows)[0]
    assert result["verdict"] == "favorable"
    assert result["sharpe_difference"] == D("0.000000000000000000001")
    h2.validate_h2_rows([result], rows)


def test_verifier_accepts_csv_roundtrip_including_unknown_booleans():
    rows = metrics(None, 2, 1)
    result = h2.h2_comparison(rows)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=result[0])
    writer.writeheader()
    writer.writerows(result)
    buffer.seek(0)
    h2.validate_h2_rows(list(csv.DictReader(buffer)), rows)


@pytest.mark.parametrize(
    "field,value",
    [
        ("verdict", "favorable"),
        ("cagr_positive", True),
        ("sharpe_superior", False),
        ("conditional_cagr", 0.01),
        ("conditional_sharpe", 2),
        ("permanent_sharpe", 2),
        ("sharpe_difference", 100),
        ("conditional_run_id", "other"),
        ("permanent_run_id", "other"),
        ("start_utc", "2023-01-01T00:00:00Z"),
        ("reason", "false_reason"),
    ],
)
def test_independent_verifier_rejects_corruption(field, value):
    rows = metrics()
    result = h2.h2_comparison(rows)
    result[0][field] = value
    with pytest.raises(ValueError):
        h2.validate_h2_rows(result, rows)


def test_verifier_rejects_missing_duplicate_and_extra_results():
    rows = metrics()
    result = h2.h2_comparison(rows)
    for invalid in ([], result * 2, result + [dict(result[0], scenario="invented")]):
        with pytest.raises(ValueError):
            h2.validate_h2_rows(invalid, rows)


def test_literal_contract_catches_joint_constructor_and_verifier_mutation():
    # Mutate both independent CAGR-positive comparisons to allow negative CAGR.
    class AllowNegative(ast.NodeTransformer):
        def visit_Compare(self, node):
            self.generic_visit(node)
            if (
                len(node.ops) == 1
                and isinstance(node.ops[0], ast.Gt)
                and isinstance(node.comparators[0], ast.Constant)
                and node.comparators[0].value == 0
            ):
                node.comparators[0] = ast.Constant(value=-1)
            return node

    mutant = ast.fix_missing_locations(AllowNegative().visit(ast.parse(inspect.getsource(h2))))
    namespace = {"__name__": "mutated_h2"}
    exec(compile(mutant, "<joint_h2_mutation>", "exec"), namespace)
    result = namespace["h2_comparison"](metrics())
    namespace["validate_h2_rows"](result, metrics())
    # A mutually consistent pair still fails the explicit independent contract.
    assert result[0]["verdict"] == "favorable"
    with pytest.raises(AssertionError):
        assert result[0]["verdict"] == "no_favorable"

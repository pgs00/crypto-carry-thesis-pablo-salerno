from dataclasses import replace
from decimal import Decimal as D

import pytest
from conftest import warmup

from crypto_carry.config import SECOND, Config, iso, timestamp
from crypto_carry.data.rules import synthetic_rules
from crypto_carry.events import event_key
from crypto_carry.models import Mark, MinuteBar
from crypto_carry.strategy import Backtest

MINUTE = 60 * SECOND
T = timestamp("2024-08-12T10:02:00Z")


def scenario(method):
    start = T - 10 * MINUTE
    config = Config(
        start=iso(start),
        end=iso(T + 5 * MINUTE),
        analysis_mode="prescribed_research",
        fee_profile="prescribed_fixed_no_discounts",
        execution_model="next_minute_vwap",
        signal_price_model="closed_minute",
        sizing_model="joint_quantity",
        mark_gap_method=method,
    )
    rows = warmup(start)
    for end in range(start, T + 5 * MINUTE, MINUTE):
        for symbol in config.symbols:
            for market, price in (("spot", D(100)), ("futures", D("100.3"))):
                rows.append(
                    MinuteBar(
                        symbol,
                        market,
                        end - MINUTE,
                        end,
                        end,
                        price,
                        price,
                        price,
                        price,
                        D(100000),
                        D(100000) * price,
                        100,
                        "fixture",
                    )
                )
            estimated = end - MINUTE in (T, T + MINUTE)
            rows.append(
                Mark(
                    symbol,
                    end - MINUTE,
                    end - 1_000_000,
                    end,
                    D("100.3"),
                    D("100.3"),
                    D("100.3"),
                    D("100.3"),
                    "estimated:fixture" if estimated else "fixture",
                    method if estimated else "official",
                    T - MINUTE if estimated else None,
                )
            )
    return config, sorted(rows, key=event_key)


@pytest.mark.parametrize("method", ["futures_scaled", "last_official"])
def test_audit_observes_real_margin_checks_without_changing_economics(method):
    from crypto_carry.mark_gap_study import GapAuditedBacktest

    config, rows = scenario(method)
    rules = synthetic_rules(config)
    baseline = Backtest(config, rules, "permanent", False).run(rows)
    observed = GapAuditedBacktest(config, rules, "permanent", False).run(rows)
    assert observed.status == "complete"
    assert observed.fills == baseline.fills
    assert observed.risk_events == baseline.risk_events
    assert observed.ledger.rows == baseline.ledger.rows
    checks = [r for r in observed.mark_gap_checks if r["mark_open_time"] in (T, T + MINUTE)]
    assert len(checks) == 4
    assert all(D(r["short"]) > 0 for r in checks)
    assert all(r["balance"] > r["maintenance"] > 0 for r in checks)
    assert all(not r["liquidate"] and not r["preventive"] for r in checks)
    assert {r["stage"] for r in observed.mark_gap_checks} == {"anchor", "estimated", "recovery"}
    assert all(r["time_ns"] >= r["mark_open_time"] + MINUTE for r in checks)


def test_estimated_mark_can_trigger_real_liquidation_and_audit_records_it():
    from crypto_carry.mark_gap_study import GapAuditedBacktest

    config, rows = scenario("futures_scaled")
    rows = [
        replace(r, open=D(200), high=D(200), low=D(200), close=D(200))
        if isinstance(r, Mark) and r.open_time == T and r.symbol == "BTCUSDT"
        else r
        for r in rows
    ]
    b = GapAuditedBacktest(config, synthetic_rules(config), "permanent", False).run(rows)
    check = next(
        r for r in b.mark_gap_checks if r["symbol"] == "BTCUSDT" and r["mark_open_time"] == T
    )
    assert check["liquidate"] is True
    assert check["state_after"] == "LIQUIDATING"
    assert any(e.get("cause") == "liquidation" for e in check["risk_events"])


def test_runtime_rejects_estimate_without_explicit_policy():
    config, rows = scenario("futures_scaled")
    strict = config.changed(mark_gap_method="strict")
    b = Backtest(strict, synthetic_rules(strict), "permanent", False).run(rows)
    assert b.status == "incomplete_data"
    assert any("estimated mark" in reason for reason in b.reasons)


def test_run_persists_risk_evidence_and_labels_approximate_coverage(tmp_path):
    import json

    import pyarrow.parquet as pq

    from crypto_carry.mark_gap_study import GapAuditedBacktest
    from crypto_carry.reporting import verify_run, write_run

    config, rows = scenario("last_official")
    b = GapAuditedBacktest(config, synthetic_rules(config), "permanent", False).run(rows)
    quality = dict(
        status="complete",
        issues=[],
        coverage=[],
        historical_certified=False,
        coverage_kind="completed_with_approximations",
        mark_gap_audit=[],
    )
    run = write_run(tmp_path, config, [b], quality, "historical_assumptions")
    assert verify_run(run)["valid"]
    assert pq.ParquetFile(run / "mark_gap_checks.parquet").metadata.num_rows == len(
        b.mark_gap_checks
    )
    saved = pq.ParquetFile(run / "mark_gap_checks.parquet").read().to_pylist()[0]
    units = json.loads(saved["units"])
    assert units["mark_close"] == "USDT per base asset unit"
    assert units["maintenance"] == "USDT"
    manifest = json.loads((run / "run_manifest.json").read_text())
    assert manifest["conventions"]["mark_gap_coverage"] == "completed_with_approximations"
    assert "completed_with_approximations" in (run / "report.md").read_text(encoding="utf-8")


def test_comparison_ignores_run_identity_but_detects_changed_risk_decision():
    from crypto_carry.mark_gap_study import compare_records

    left = [dict(run_id="a", strategy="conditional", time_ns=10, cause="margin")]
    right = [dict(run_id="b", strategy="conditional", time_ns=10, cause="margin")]
    assert compare_records(left, right)["identical"]
    right[0]["cause"] = "liquidation"
    diff = compare_records(left, right)
    assert not diff["identical"]
    assert diff["changed_rows"] == 1


def test_audit_keeps_parent_incomplete_data_halt_when_margin_tier_is_unavailable():
    from crypto_carry.ledger import Position
    from crypto_carry.mark_gap_study import GapAuditedBacktest

    config, _ = scenario("futures_scaled")
    results = []
    for cls in (Backtest, GapAuditedBacktest):
        b = cls(config, synthetic_rules(config), "permanent", False)
        b.now = T + MINUTE
        b.ledger.positions["BTCUSDT"] = Position(short=D(1), average=D(100), collateral=D(50))
        b.marks["BTCUSDT"] = Mark(
            "BTCUSDT",
            T,
            T + MINUTE - 1_000_000,
            T + MINUTE,
            D(100000001),
            D(100000001),
            D(100000001),
            D(100000001),
        )
        b._risk("BTCUSDT", True)
        results.append(b)
    assert results[1].status == results[0].status == "incomplete_data"
    assert results[1].reasons == results[0].reasons
    assert results[1].mark_gap_checks[0]["margin_error"]


def test_incomplete_run_does_not_claim_completed_approximate_coverage(tmp_path):
    import json

    from crypto_carry.mark_gap_study import GapAuditedBacktest
    from crypto_carry.reporting import write_run

    config, rows = scenario("last_official")
    rows = [
        r
        for r in rows
        if not (isinstance(r, Mark) and r.symbol == "BTCUSDT" and r.open_time == T + 2 * MINUTE)
    ]
    b = GapAuditedBacktest(config, synthetic_rules(config), "permanent", False).run(rows)
    assert b.status == "incomplete_data"
    quality = dict(
        status="incomplete_data",
        issues=["additional gap"],
        coverage=[],
        coverage_kind="incomplete_data",
    )
    run = write_run(tmp_path, config, [b], quality, "historical_assumptions")
    manifest = json.loads((run / "run_manifest.json").read_text())
    assert manifest["conventions"]["mark_gap_coverage"] == "incomplete_data"
    report = (run / "report.md").read_text(encoding="utf-8")
    assert "completed_with_approximations" not in report
    assert "Cobertura incomplete_data" in report

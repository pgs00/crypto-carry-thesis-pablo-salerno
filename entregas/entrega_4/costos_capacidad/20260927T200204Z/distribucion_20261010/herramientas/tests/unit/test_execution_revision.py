import hashlib
import json
from decimal import Decimal

import pytest

from crypto_carry.config import Config
from crypto_carry.execution_revision import (
    _cross_window_h3,
    _cycle_counts,
    _hypotheses,
    _position_durations,
    _revision_input_hashes,
    execution_revision_scenarios,
    verify_execution_revision,
)


def _base():
    return Config(
        analysis_mode="prescribed_research",
        fee_profile="prescribed_fixed_no_discounts",
        execution_model="minute_open",
        order_timeout_seconds=120,
        data_dir="data/minutes/window",
        start="2022-09-01T00:00:00Z",
        end="2023-09-01T00:00:00Z",
    )


def test_disabled_funding_is_a_diagnostic_and_never_a_permanent_rejection(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    from crypto_carry.execution_revision import _diagnostics

    common = {
        "symbol": "BTCUSDT",
        "forecast": "0.001",
        "estimated_cycle_cost": "0.0034",
        "filter_funding": "fail",
        "price_alignment_enforced": "True",
    }
    rows = [
        dict(
            common,
            strategy="permanent",
            funding_filter_enabled=False,
            basis="0",
            filter_basis_negative="pass",
            sequential_rejection=None,
        ),
        dict(
            common,
            strategy="permanent",
            funding_filter_enabled=False,
            basis="-0.0005",
            filter_basis_negative="fail",
            sequential_rejection="basis_negative",
        ),
        dict(
            common,
            strategy="conditional",
            funding_filter_enabled=True,
            basis="0",
            filter_basis_negative="pass",
            sequential_rejection="funding",
        ),
    ]
    pq.write_table(pa.Table.from_pylist(rows), tmp_path / "signals.parquet")
    counts, _ = _diagnostics("late", "vwap_joint", tmp_path)
    actual = {(r["strategy"], r["diagnostic"]): r["count"] for r in counts}
    assert actual.get(("permanent", "filter_funding:reject"), 0) == 0
    assert actual[("permanent", "filter_funding:diagnostic_fail_not_applied")] == 2
    assert actual[("permanent", "simultaneous_reject")] == 1
    assert actual[("permanent", "ordered_reject:basis_negative")] == 1
    assert actual[("conditional", "filter_funding:reject")] == 1
    assert actual[("conditional", "ordered_reject:funding")] == 1


def test_execution_revision_scenarios_isolate_each_methodological_change():
    scenarios = execution_revision_scenarios(_base())

    assert list(scenarios) == [
        "legacy_reference",
        "joint_sizing_only",
        "alignment_only",
        "vwap_only",
        "vwap_joint",
    ]
    assert {
        name: (c.execution_model, c.sizing_model, c.signal_price_model)
        for name, c in scenarios.items()
    } == {
        "legacy_reference": ("minute_open", "legacy", "execution_default"),
        "joint_sizing_only": ("minute_open", "joint_quantity", "execution_default"),
        "alignment_only": ("minute_open", "legacy", "closed_minute"),
        "vwap_only": ("next_minute_vwap", "legacy", "closed_minute"),
        "vwap_joint": ("next_minute_vwap", "joint_quantity", "closed_minute"),
    }
    assert all(c.max_volume_participation == Decimal("0.01") for c in scenarios.values())
    assert all(c.start == _base().start and c.end == _base().end for c in scenarios.values())


def test_execution_revision_requires_a_legacy_minute_profile():
    with pytest.raises(ValueError, match="minute_open"):
        execution_revision_scenarios(_base().changed(execution_model="next_minute_vwap"))


def test_next_minute_input_identity_excludes_legacy_price_partitions(tmp_path):
    bars = tmp_path / "data/minutes/window/processed/bars.parquet"
    prior = tmp_path / "data/minutes/window/processed/prior-bars.parquet"
    prices = tmp_path / "data/minutes/window/processed/prices.parquet"
    bars.parent.mkdir(parents=True)
    bars.write_bytes(b"closed bars")
    prior.write_bytes(b"antecedent closed bar")
    prices.write_bytes(b"legacy minute opens")

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    entries = [
        {
            "dataset": "minute_bars",
            "path": prior.relative_to(tmp_path).as_posix(),
            "sha256": digest(prior),
            "start": 1661980000000000000,
            "end": 1661990000000000000,
        },
        {
            "dataset": "minute_bars",
            "path": bars.relative_to(tmp_path).as_posix(),
            "sha256": digest(bars),
            "start": 1661990400000000000,
            "end": 1693526400000000000,
        },
        {
            "dataset": "minute_prices",
            "path": prices.relative_to(tmp_path).as_posix(),
            "sha256": digest(prices),
            "start": 1661990400000000000,
            "end": 1693526400000000000,
        },
    ]
    manifest = bars.parents[1] / "manifests/processed.json"
    manifest.parent.mkdir()
    manifest.write_text(json.dumps({"kind": "processed", "version": 1, "entries": entries}))

    hashes = _revision_input_hashes(
        tmp_path,
        _base().changed(execution_model="next_minute_vwap", signal_price_model="closed_minute"),
    )

    assert bars.relative_to(tmp_path).as_posix() in hashes
    assert prior.relative_to(tmp_path).as_posix() in hashes
    assert prices.relative_to(tmp_path).as_posix() not in hashes


def test_position_duration_extends_final_persisted_state_to_window_end():
    durations = _position_durations(
        [
            {
                "strategy": "conditional",
                "symbol": "BTCUSDT",
                "time_ns": 10_000_000_000,
                "spot": "1",
                "short": "1",
                "dust_spot": "0",
                "tradable_spot": "1",
            }
        ],
        70_000_000_000,
        Decimal("0.005"),
    )

    assert durations[("conditional", "BTCUSDT")]["covered_asset_seconds"] == Decimal("60")


def test_position_duration_does_not_invent_dust_when_legacy_metadata_is_absent():
    durations = _position_durations(
        [
            {
                "strategy": "conditional",
                "symbol": "BTCUSDT",
                "time_ns": 10_000_000_000,
                "state": "OPENING_PERP",
                "spot": "1",
                "short": "0",
            }
        ],
        70_000_000_000,
        Decimal("0.005"),
    )[("conditional", "BTCUSDT")]

    assert durations["unhedged_asset_seconds"] == Decimal("60")
    assert durations["dust_asset_seconds"] == 0


def test_position_duration_keeps_active_covered_position_out_of_dust():
    durations = _position_durations(
        [
            {
                "strategy": "conditional",
                "symbol": "BTCUSDT",
                "time_ns": 0,
                "state": "HOLDING",
                "spot": "1",
                "short": "1",
                "dust_spot": "0.01",
                "tradable_spot": "0.99",
            }
        ],
        60_000_000_000,
        Decimal("0.005"),
    )[("conditional", "BTCUSDT")]

    assert durations["covered_asset_seconds"] == Decimal("60")
    assert durations["dust_asset_seconds"] == 0


def test_position_duration_keeps_tradable_naked_spot_as_unhedged():
    durations = _position_durations(
        [
            {
                "strategy": "conditional",
                "symbol": "BTCUSDT",
                "time_ns": 0,
                "state": "OPENING_PERP",
                "spot": "1",
                "short": "0",
                "dust_spot": "0.01",
                "tradable_spot": "0.99",
            }
        ],
        60_000_000_000,
        Decimal("0.005"),
    )[("conditional", "BTCUSDT")]

    assert durations["unhedged_asset_seconds"] == Decimal("60")
    assert durations["dust_asset_seconds"] == 0


def test_pending_reentry_does_not_turn_unchanged_residual_dust_into_active_exposure():
    rows = [
        {
            "strategy": "conditional",
            "symbol": "ETHUSDT",
            "time_ns": 0,
            "state": "FLAT",
            "spot": "0.00001",
            "short": "0",
        },
        {
            "strategy": "conditional",
            "symbol": "ETHUSDT",
            "time_ns": 60_000_000_000,
            "state": "OPENING_SPOT",
            "spot": "0.00001",
            "short": "0",
        },
        {
            "strategy": "conditional",
            "symbol": "ETHUSDT",
            "time_ns": 120_000_000_000,
            "state": "OPENING_PERP",
            "spot": "1.00001",
            "short": "0",
        },
    ]
    durations = _position_durations(rows, 180_000_000_000, Decimal("0.005"))[
        ("conditional", "ETHUSDT")
    ]

    assert durations["dust_asset_seconds"] == 120
    assert durations["unhedged_asset_seconds"] == 60


def test_cycle_counts_do_not_treat_repeated_timeouts_as_failed_cycles():
    events = [
        {"symbol": "BTC", "cycle_id": "one", "kind": "transition", "cause": "opening_complete"},
        {"symbol": "BTC", "cycle_id": "one", "kind": "attempt_failed", "cause": "timeout"},
        {
            "symbol": "BTC",
            "cycle_id": "one",
            "kind": "transition",
            "cause": "unwind_complete",
            "state": "COOLDOWN",
        },
        {"symbol": "ETH", "cycle_id": "two", "kind": "attempt_failed", "cause": "timeout"},
        {"symbol": "ETH", "cycle_id": "two", "kind": "attempt_failed", "cause": "timeout"},
        {
            "symbol": "ETH",
            "cycle_id": "two",
            "kind": "transition",
            "cause": "unwind_complete",
            "state": "COOLDOWN",
        },
    ]

    assert _cycle_counts(events) == (1, 1)


def test_cycle_counts_accept_ordinary_close_as_successful_terminal_transition():
    events = [
        {"symbol": "BTC", "cycle_id": "one", "kind": "transition", "cause": "opening_complete"},
        {
            "symbol": "BTC",
            "cycle_id": "one",
            "kind": "transition",
            "cause": "ordinary_close_complete",
            "state": "FLAT",
        },
    ]

    assert _cycle_counts(events) == (1, 0)


@pytest.mark.parametrize(
    "late_cagr,late_days,expected",
    [("0.01", 365, "favorable"), ("0.03", 365, "mixta"), ("0.01", 364, "no_concluyente")],
)
def test_h3_compares_opportunity_and_cagr_with_complete_independent_windows(
    tmp_path, late_cagr, late_days, expected
):
    runs = {}
    for window, period, opportunity, cagr, days in (
        ("early", "2022-2023", "0.004", "0.02", 365),
        ("late", "2024+", "0.002", late_cagr, late_days),
    ):
        run = tmp_path / window
        run.mkdir()
        (run / "regime_comparison.csv").write_text(
            "symbol,period,valid_days,opportunity_mean,conditional_cagr,coverage_complete\n"
            f"EQUAL_WEIGHT,{period},{days},{opportunity},{cagr},True\n",
            encoding="utf-8",
        )
        runs[(window, "vwap_joint")] = run

    result = _cross_window_h3("vwap_joint", runs)

    assert result["result"] == expected
    assert result["observations"] == f"365/{late_days}"


@pytest.mark.parametrize("sharpe,coverage", [(None, True), ("3", False)])
def test_h2_is_inconclusive_with_undefined_sharpe_or_incomplete_coverage(
    tmp_path, monkeypatch, sharpe, coverage
):
    rows = {
        "metrics.csv": [
            {
                "strategy": "conditional",
                "period": "full",
                "cagr": "0.01",
                "sharpe": sharpe,
                "coverage_complete": coverage,
                "funding_filter_enabled": True,
                "status": "complete",
            },
            {
                "strategy": "permanent",
                "period": "full",
                "cagr": "0.02",
                "sharpe": "2",
                "coverage_complete": True,
                "funding_filter_enabled": False,
                "status": "complete",
            },
        ],
        "equity_daily.csv": [
            {"strategy": strategy, "time_ns": 1} for strategy in ("conditional", "permanent")
        ],
    }
    monkeypatch.setattr(
        "crypto_carry.execution_revision._rows", lambda run, name: rows.get(name, [])
    )

    result = next(
        row for row in _hypotheses("late", "vwap_joint", tmp_path) if row["hypothesis"] == "H2"
    )

    assert result["result"] == "no_concluyente"


def test_verify_execution_revision_checks_manifest_outputs_and_input_run_hashes(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "crypto_carry.execution_revision.verify_run",
        lambda path: {"valid": True, "mismatches": []},
    )
    revision = tmp_path / "revision_abc"
    revision.mkdir()
    report = revision / "execution_revision_report.md"
    report.write_text("# revision\n", encoding="utf-8")
    run_manifest = tmp_path / "run_x" / "run_manifest.json"
    run_manifest.parent.mkdir()
    run_manifest.write_text('{"run_id":"run_x"}\n', encoding="utf-8")

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    manifest = {
        "revision_id": "revision_abc",
        "artifacts_complete": True,
        "status": "complete",
        "output_hashes": {report.name: sha(report)},
        "input_runs": [
            {
                "path": run_manifest.parent.as_posix(),
                "manifest_sha256": sha(run_manifest),
            }
        ],
    }
    manifest_path = revision / "revision_manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    (revision / "revision_manifest.sha256").write_text(sha(manifest_path) + "\n")

    assert verify_execution_revision(revision)["valid"] is True
    assert verify_execution_revision(revision)["status"] == "complete"
    report.write_text("changed\n", encoding="utf-8")
    result = verify_execution_revision(revision)
    assert result["valid"] is False
    assert {row["path"] for row in result["mismatches"]} == {report.name}


def test_outage_close_prices_keep_base_assets_separate_and_exclude_rebalances():
    from crypto_carry.execution_revision import _outage_close_prices

    common = {
        "scenario": "joint_sizing_only",
        "strategy": "permanent",
        "market": "futures",
        "side": "BUY",
        "purpose": "close_perp",
        "timestamp_utc": "2023-03-24T11:59:00Z",
    }
    rows = [
        dict(common, symbol="BTCUSDT", quantity="0.1", price="28000"),
        dict(common, symbol="ETHUSDT", quantity="1", price="1700"),
        dict(common, symbol="ETHUSDT", quantity="1", price="1800"),
        dict(common, symbol="ETHUSDT", quantity="9", price="1", purpose="decrease_perp"),
    ]

    prices = {row["symbol"]: row for row in _outage_close_prices(rows)}

    assert Decimal(prices["BTCUSDT"]["future_close_price_usdt"]) == 28000
    assert Decimal(prices["ETHUSDT"]["future_close_price_usdt"]) == 1750
    assert prices["ETHUSDT"]["spot_close_price_usdt"] is None


def test_rebuilding_revision_preserves_verified_economic_runs(tmp_path, monkeypatch):
    from crypto_carry import execution_revision as revision

    source = tmp_path / "outputs/revision_source"
    source.mkdir(parents=True)
    entries = [
        {"window": window, "scenario": scenario, "path": str(tmp_path / f"{window}-{scenario}")}
        for window in ("early", "late")
        for scenario in revision.SCENARIOS
    ]
    (source / "revision_manifest.json").write_text(json.dumps({"input_runs": entries}))
    monkeypatch.setattr(revision, "verify_execution_revision", lambda path: {"valid": True})
    captured = {}

    def build(root, runs):
        captured.update(runs)
        return tmp_path / "new_revision"

    monkeypatch.setattr(revision, "_build_revision", build)

    result = revision.rebuild_execution_revision(tmp_path, source)

    assert result.name == "new_revision"
    assert {(window, scenario) for window, scenario in captured} == {
        (r["window"], r["scenario"]) for r in entries
    }
    assert {str(path) for path in captured.values()} == {r["path"] for r in entries}

"""Reporting boundary tests: persisted truth, exact money, and immutable evidence."""

import hashlib
import json
from dataclasses import asdict
from decimal import Decimal as D

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from crypto_carry.config import DAY, HOUR, SECOND, Config, timestamp
from crypto_carry.models import Fill, Funding, Mark, Order, State, Trade
from crypto_carry.strategy import Backtest


def _backtest(rules):
    config = Config(start="2024-01-01T00:00:00Z", end="2024-01-04T00:00:00Z", horizon_hours=1)
    b = Backtest(config, rules)
    start = timestamp(config.start)
    for market, side, quantity, price, reference, offset in (
        ("spot", "BUY", "10", "100.01", "100", 1),
        ("futures", "SELL", "9.99", "100.3", "100.31", 2),
    ):
        rule = rules.get("BTCUSDT", market, start)
        fill = Fill(
            f"fill-{offset}",
            f"order-{offset}",
            "BTCUSDT",
            market,
            side,
            D(quantity),
            D(price),
            D(reference),
            start + offset * SECOND,
            f"trade-{offset}",
            rule.taker_fee,
        )
        assert b.ledger.apply_fill(fill, rule, D("100.3"))
        b.fills.append(
            dict(
                asdict(fill),
                strategy=b.strategy,
                participation="0.01",
                recent_volume_quantity="1000",
                purpose=f"open_{market}",
            )
        )
        order = Order(
            fill.order_id,
            fill.symbol,
            market,
            side,
            fill.quantity,
            start,
            start + 30 * SECOND,
            f"open_{market}",
            "filled",
        )
        b.orders[order.order_id] = order
        b.order_rows.append(
            dict(asdict(order), time_ns=fill.time_ns, strategy=b.strategy, action="filled")
        )
    funding = Funding(
        "BTCUSDT",
        start + HOUR,
        start + HOUR + 60 * SECOND,
        D(".001"),
        D(1),
        D("100.4"),
        "synthetic",
        True,
    )
    b.ledger.apply_funding(funding)
    b.all_funding = [
        Funding(
            symbol,
            start + h * HOUR,
            start + h * HOUR + 60 * SECOND,
            D(".001"),
            D(1),
            D("100.4"),
            "synthetic",
            True,
        )
        for symbol in config.symbols
        for h in range(5)
    ]
    b.signals = [
        {
            "time_ns": start + 60 * SECOND,
            "strategy": b.strategy,
            "symbol": symbol,
            "anchor": start,
            "history_start": start - 336 * HOUR,
            "forecast": D(".001"),
            "no_change": D(".002"),
            "valid": True,
            "decision": "fixture",
            "estimated_cycle_cost": D(".0034"),
            "basis": D(".003"),
        }
        for symbol in config.symbols
    ]
    b.pairs["BTCUSDT"].state = State.HOLDING
    for day, price in enumerate(("101", "103", "102"), 1):
        b.now = start + day * DAY - 1
        b.trades[("BTCUSDT", "spot")] = Trade(
            "BTCUSDT", "spot", str(day), b.now, b.now, D(price), D(1)
        )
        mark = D(price) + D(".3")
        b.marks["BTCUSDT"] = Mark(
            "BTCUSDT", b.now - 60 * SECOND, b.now, b.now, mark, mark, mark, mark
        )
        b._daily()
    b.durations.update(
        portfolio_invested_seconds=D(259199),
        cash_seconds=D(1),
        BTCUSDT_invested_seconds=D(259199),
        BTCUSDT_unhedged_seconds=D(1),
    )
    b.native_fill_count = 2
    b.native_reconciliation_count = 2
    b.risk_events = [
        {
            "time_ns": start + 2 * SECOND,
            "strategy": b.strategy,
            "symbol": "BTCUSDT",
            "kind": "transition",
            "state": "HOLDING",
            "previous": "OPENING_PERP",
            "cause": "entry_complete",
        }
    ]
    return b


def _quality(config):
    return {
        "status": "complete",
        "issues": [],
        "start": config.start,
        "end": config.end,
        "coverage": [
            {
                "dataset": "synthetic_fixture",
                "symbol": "BTCUSDT",
                "start": config.start,
                "end": config.end,
                "expected_start": timestamp(config.start),
                "expected_end": timestamp(config.end),
                "observed_start": timestamp(config.start),
                "observed_end": timestamp(config.end) - 1,
                "status": "complete",
                "rows": 3,
                "complete": True,
            }
        ],
    }


def test_empty_historical_run_has_schemas_and_no_fabricated_equity(tmp_path):
    from crypto_carry.reporting import verify_run, write_run

    config = Config()
    run = write_run(
        tmp_path,
        config,
        [],
        {"status": "incomplete_data", "issues": ["missing historical rules"], "coverage": []},
        "historical",
    )
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "incomplete_data"
    assert manifest["data_kind"] == "historical"
    assert pd.read_csv(run / "equity_daily.csv").empty
    assert pd.read_csv(run / "metrics.csv").empty
    for name in (
        "signals",
        "orders",
        "fills",
        "ledger",
        "funding_payments",
        "positions",
        "risk_events",
    ):
        table = pq.read_table(run / f"{name}.parquet")
        assert table.num_rows == 0
        assert {"run_id", "symbol", "strategy", "timestamp_utc", "units"} <= set(table.column_names)
    assert pa.types.is_string(pq.read_schema(run / "fills.parquet").field("price").type)
    report = (run / "report.md").read_text(encoding="utf-8")
    assert "missing historical rules" in report
    assert "Sin observaciones verificadas" in report
    assert "H2: no concluyente" in report
    assert verify_run(run)["valid"] is True


def test_saved_outputs_preserve_exact_money_and_reconcile_without_slippage_twice(tmp_path, rules):
    from crypto_carry.reporting import verify_run, write_run

    b = _backtest(rules)
    run = write_run(tmp_path, b.config, [b], _quality(b.config), "synthetic")
    required = {
        "run_manifest.json",
        "effective_config.toml",
        "data_quality_report.md",
        "data_coverage.csv",
        "equity_daily.csv",
        "metrics.csv",
        "forecast_evaluation.csv",
        "opportunity_daily.csv",
        "regime_comparison.csv",
        "robustness_summary.csv",
        "h1_summary.csv",
        "pnl_components.csv",
        "execution_summary.csv",
        "attribution_by_asset.csv",
        "report.md",
    }
    assert required <= {path.name for path in run.iterdir()}
    for name in (
        "equity",
        "drawdown",
        "pnl_components",
        "forecast",
        "opportunity",
        "cost_sensitivity",
    ):
        for extension in ("png", "svg"):
            assert (run / "figures" / f"{name}.{extension}").stat().st_size > 1000
        svg = (run / "figures" / f"{name}.svg").read_text(encoding="utf-8")
        assert "SINTÉTICO" in svg
    rows = pq.read_table(run / "ledger.parquet").to_pylist()
    assert rows[0]["fee"] == str(b.ledger.rows[0]["fee"])
    assert rows[0]["amount_usdt"] == str(b.ledger.rows[0]["amount_usdt"])
    assert rows[0]["timestamp_utc"] == "2024-01-01T00:00:01.000000000Z"
    daily = pd.read_csv(run / "equity_daily.csv", dtype=str, keep_default_na=False)
    units = json.loads(daily.iloc[0].units)
    assert units["BTCUSDT_spot"] == "base asset units"
    assert units["BTCUSDT_fees"] == "USDT"
    coverage = pd.read_csv(run / "data_coverage.csv", dtype=str, keep_default_na=False)
    assert coverage.iloc[0].expected_start_utc == "2024-01-01T00:00:00.000000000Z"
    components = pd.read_csv(run / "pnl_components.csv", dtype=str, keep_default_na=False)
    included = components[components.included_in_total == "True"]
    assert sum(map(D, included.amount_usdt)) == D("-0.5980025")
    assert b.equity() - b.config.capital == D("-0.5980025")
    assert components[
        components.component == "slippage_informational"
    ].included_in_total.tolist() == ["False"]
    attribution = pd.read_csv(run / "attribution_by_asset.csv", dtype=str, keep_default_na=False)
    assert sum(map(D, attribution.total_pnl_usdt)) == D("-0.5980025")
    report = (run / "report.md").read_text(encoding="utf-8")
    assert "SINTÉTICO" in report and "validan el pipeline" in report
    assert "H2: no concluyente" in report  # Only one economic strategy was supplied.
    assert "horizontes se solapan" in report
    assert "Sin escenarios de costos evaluados" in report
    assert verify_run(run)["valid"]


def test_stable_run_id_reuses_verified_artifacts_and_detects_corruption(tmp_path, rules):
    from crypto_carry.reporting import verify_run, write_run

    b = _backtest(rules)
    inputs = {"fixture_sha256": "b" * 64}
    source = tmp_path / b.config.data_dir / "manifests" / "download.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(b'{"created_at":"first","sha256":"fixed"}\n')
    first = write_run(tmp_path, b.config, [b], _quality(b.config), "synthetic", inputs=inputs)
    assert not (
        first / "source_manifests"
    ).exists()  # Demo inputs cannot borrow historical provenance.
    source.write_bytes(b'{"created_at":"later","sha256":"fixed"}\n')
    before = {
        p.relative_to(first).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in first.rglob("*")
        if p.is_file()
    }
    assert (
        write_run(tmp_path, b.config, [b], _quality(b.config), "synthetic", inputs=inputs) == first
    )
    after = {
        p.relative_to(first).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in first.rglob("*")
        if p.is_file()
    }
    assert before == after
    b.native_reconciliation_count += 1
    with pytest.raises(ValueError, match="(?i)(immutable|different results)"):
        write_run(tmp_path, b.config, [b], _quality(b.config), "synthetic", inputs=inputs)
    b.native_reconciliation_count -= 1
    (first / "equity_daily.csv").write_text("tampered\n", encoding="utf-8")
    verification = verify_run(first)
    assert verification["valid"] is False
    assert "equity_daily.csv" in json.dumps(verification["mismatches"])
    with pytest.raises(
        (ValueError, FileExistsError), match="(?i)(immutable|checksum|hash|corrupt)"
    ):
        write_run(tmp_path, b.config, [b], _quality(b.config), "synthetic", inputs=inputs)


def test_regeneration_uses_saved_tables_and_is_byte_identical(tmp_path, rules):
    from crypto_carry.reporting import regenerate_report, verify_run, write_run

    b = _backtest(rules)
    run = write_run(tmp_path, b.config, [b], _quality(b.config), "synthetic")
    hashes = {
        p.relative_to(run).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in run.rglob("*")
        if p.is_file()
    }
    b.daily.clear()
    b.signals.clear()
    b.ledger.free_spot = D(-999999)
    assert regenerate_report(run) == run / "report.md"
    assert hashes == {
        p.relative_to(run).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in run.rglob("*")
        if p.is_file()
    }
    assert verify_run(run)["valid"]
    (run / "report.md").write_text("changed report", encoding="utf-8")
    with pytest.raises(
        (ValueError, FileExistsError), match="(?i)(immutable|checksum|hash|corrupt)"
    ):
        regenerate_report(run)
    assert (run / "report.md").read_text(encoding="utf-8") == "changed report"


def test_inputs_and_filter_are_identity_and_manifest_has_reproducibility(tmp_path, rules):
    from crypto_carry.reporting import write_run

    b = _backtest(rules)
    run = write_run(
        tmp_path, b.config, [b], _quality(b.config), "synthetic", inputs={"dataset": "a" * 64}
    )
    other = write_run(
        tmp_path, b.config, [b], _quality(b.config), "synthetic", inputs={"dataset": "b" * 64}
    )
    b.funding_filter_enabled = False
    third = write_run(
        tmp_path, b.config, [b], _quality(b.config), "synthetic", inputs={"dataset": "b" * 64}
    )
    assert len({run.name, other.name, third.name}) == 3
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    for key in (
        "config",
        "python",
        "dependencies",
        "code_hash",
        "input_hashes",
        "requested_range",
        "observed_range",
        "conventions",
        "output_hashes",
        "created_at",
    ):
        assert key in manifest
    assert manifest["input_hashes"] == {"dataset": "a" * 64}
    assert len(manifest["code_hash"]) == 64
    assert manifest["observed_range"]["end"] == "2024-01-03T23:59:59.999999999Z"


def test_failed_build_leaves_failed_manifest_and_no_complete_reuse(tmp_path, rules, monkeypatch):
    from crypto_carry import reporting

    b = _backtest(rules)

    def broken(*args, **kwargs):
        raise RuntimeError("renderer unavailable")

    monkeypatch.setattr(reporting, "_render_figures", broken)
    with pytest.raises(RuntimeError, match="renderer unavailable"):
        reporting.write_run(tmp_path, b.config, [b], _quality(b.config), "synthetic")
    manifests = list((tmp_path / "outputs").glob("*/run_manifest.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["artifacts_complete"] is False
    assert reporting.verify_run(manifests[0].parent)["valid"] is False


def test_execution_counts_accepted_signals_and_participation_of_unfilled_orders(rules):
    from crypto_carry.reporting import _execution

    b = Backtest(Config(), rules)
    for index, quantity, status in ((1, "10", "filled"), (2, "30", "expired")):
        order = Order(
            str(index),
            "BTCUSDT",
            "spot",
            "BUY",
            D(quantity),
            0,
            SECOND,
            "open_spot",
            status,
            recent_volume_quantity=D(100),
        )
        b.orders[order.order_id] = order
    b.signals = [
        {"symbol": "BTCUSDT", "decision": "accepted"},
        {"symbol": "BTCUSDT", "decision": "funding_not_above_cost"},
    ]
    portfolio = _execution(b)[0]
    assert portfolio["rejected_signals"] == 1
    assert portfolio["participation_observations"] == 2
    assert portfolio["participation_missing"] == 0
    assert portfolio["participation_p50"] == pytest.approx(0.2)
    assert portfolio["participation_p90"] == pytest.approx(0.28)
    assert portfolio["failed_attempts"] == 1


@pytest.mark.parametrize("invalid_manifest", [[], None, "not a manifest"])
def test_verifier_reports_malformed_manifest_as_invalid(tmp_path, invalid_manifest):
    from crypto_carry.reporting import verify_run

    (tmp_path / "run_manifest.json").write_text(json.dumps(invalid_manifest), encoding="utf-8")
    result = verify_run(tmp_path)
    assert result["valid"] is False
    assert result["status"] == "failed"
    assert result["mismatches"]

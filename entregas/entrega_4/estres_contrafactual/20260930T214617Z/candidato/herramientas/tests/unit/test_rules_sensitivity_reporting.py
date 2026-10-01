"""Independent arithmetic and negative cases for the preliminary rules report."""

import csv
import hashlib
import json
import subprocess
import sys
from decimal import Decimal as D
from pathlib import Path

import pytest


def modules():
    from scripts import report_historical_rules_sensitivity as report
    from scripts import verify_rules_sensitivity_package as verify

    return report, verify


def daily_row(time_ns, equity, *, funding="0", spot="0", short="0", fees="0"):
    row = dict(
        time_ns=time_ns,
        equity=equity,
        partial_day=False,
        free_spot=equity,
        free_futures="0",
        debt="0",
    )
    for symbol in ("BTCUSDT", "ETHUSDT"):
        row.update(
            {
                f"{symbol}_{key}": "0"
                for key in (
                    "spot",
                    "short",
                    "spot_cost",
                    "realized_spot",
                    "realized_futures",
                    "average",
                    "mark",
                    "spot_price",
                    "funding",
                    "fees",
                    "liquidation_fees",
                    "slippage",
                    "collateral",
                )
            }
        )
    row.update(BTCUSDT_spot=spot, BTCUSDT_short=short, BTCUSDT_funding=funding, BTCUSDT_fees=fees)
    return row


def test_daily_accounting_values_open_inventory_and_does_not_subtract_slippage_twice():
    _, verify = modules()
    row = daily_row(86_400_000_000_000 - 1, "105", funding="7", spot="2", short="2", fees="3")
    row.update(
        free_spot="84",
        BTCUSDT_spot_price="12",
        BTCUSDT_spot_cost="20",
        BTCUSDT_mark="11.5",
        BTCUSDT_average="10",
        BTCUSDT_slippage="99",
    )
    daily, assets = verify.financial_daily([row], D("100"))
    assert daily[0]["spot_pnl_usdt"] == D("4")
    assert daily[0]["futures_pnl_usdt"] == D("-3")
    assert daily[0]["net_pnl_usdt"] == D("5")
    assert daily[0]["reconciliation_residual_usdt"] == 0
    assert assets[0]["slippage_informational_usdt"] == D("99")


def test_accounting_rejects_missing_component_and_inconsistent_equity():
    _, verify = modules()
    row = daily_row(86_400_000_000_000 - 1, "101")
    with pytest.raises(ValueError, match="reconcil"):
        verify.financial_daily([row], D("100"))
    row["equity"] = "100"
    del row["BTCUSDT_fees"]
    with pytest.raises(ValueError, match="BTCUSDT_fees"):
        verify.financial_daily([row], D("100"))


def test_daily_equity_reconciles_cash_inventory_collateral_and_debt():
    _, verify = modules()
    row = daily_row(86_400_000_000_000 - 1, "100")
    row["free_spot"] = "101"
    with pytest.raises(ValueError, match="balance|valuation"):
        verify.financial_daily([row], D("100"))


def test_subperiod_uses_previous_equity_and_zero_volatility_is_undefined():
    report, verify = modules()
    start = verify.timestamp("2023-12-31T00:00:00Z")
    day = verify.DAY
    rows = [
        daily_row(start + day - 1, "110", funding="10"),
        daily_row(start + 2 * day - 1, "121", funding="21"),
    ]
    daily, _ = verify.financial_daily(rows, D("100"))
    sub = report.period_financials(daily, [("2024", start + day, start + 2 * day)])[0]
    assert sub["starting_equity_usdt"] == D("110")
    assert sub["net_pnl_usdt"] == D("11")
    assert sub["net_return"] == D("0.1")
    assert sub["funding_usdt"] == D("11")
    assert sub["sharpe"] is None
    constant = report.period_financials(daily, [("full", start, start + 2 * day)])[0]
    assert constant["sharpe"] is None
    assert constant["sharpe_reason"] == "zero sample volatility"


def test_missing_day_is_rejected_instead_of_reported_as_idle_day():
    report, verify = modules()
    daily, _ = verify.financial_daily([daily_row(verify.DAY - 1, "100")], D("100"))
    with pytest.raises(ValueError, match="coverage"):
        report.period_financials(daily, [("full", 0, 2 * verify.DAY)])


def test_deltas_use_realized_comparator_for_decision_and_keep_run_ids():
    report, _ = modules()
    rows = [
        dict(
            scenario=scenario,
            strategy="conditional",
            period="full",
            run_id=run_id,
            final_equity_usdt=D(equity),
        )
        for scenario, run_id, equity in (
            ("BASE_E3", "base", "100"),
            ("FUT4_REALIZADA", "real", "105"),
            ("FUT4_DECISION", "decision", "102"),
        )
    ]
    delta = next(
        r
        for r in report.compare_deltas(rows)
        if r["scenario"] == "FUT4_DECISION" and r["metric"] == "final_equity_usdt"
    )
    assert delta["delta"] == D("-3")
    assert delta["comparator_run_id"] == "real"
    assert delta["run_id"] == "decision"


def test_h2_never_pairs_with_another_scenario_and_keeps_undefined_sharpe():
    report, _ = modules()
    rows = [
        dict(scenario="BASE_E3", strategy="permanent", period="full", run_id="base", sharpe=9),
        dict(
            scenario="FUT4_DECISION", strategy="conditional", period="full", run_id="cond", sharpe=2
        ),
        dict(
            scenario="FUT4_DECISION",
            strategy="permanent",
            period="full",
            run_id="perm",
            sharpe=None,
            sharpe_reason="zero sample volatility",
        ),
    ]
    row = next(r for r in report.h2_comparison(rows) if r["scenario"] == "FUT4_DECISION")
    assert row["permanent_run_id"] == "perm"
    assert row["verdict"] == "no_concluyente"
    assert row["sharpe_difference"] is None


def test_exposure_counts_union_and_uses_complete_persisted_position_states():
    report, _ = modules()
    second = 1_000_000_000
    ledger = [
        dict(time_ns=2 * second, symbol="BTCUSDT", spot="2", short="0", state="OPENING_SPOT"),
        dict(time_ns=3 * second, symbol="BTCUSDT", spot="2", short="2", state="HOLDING"),
        dict(time_ns=4 * second, symbol="ETHUSDT", spot="1", short="1", state="HOLDING"),
        dict(time_ns=7 * second, symbol="BTCUSDT", spot="0", short="0", state="FLAT"),
    ]
    rows = report.exposure_summary(ledger, [("full", 0, 10 * second)], D("0.005"))
    portfolio = next(r for r in rows if r["symbol"] == "PORTFOLIO")
    assert portfolio["invested_seconds"] == D("8")
    assert portfolio["unhedged_seconds"] == D("1")
    assert portfolio["both_covered_seconds"] == D("3")


def test_h3_averages_assets_equally_and_unknown_is_not_zero():
    report, _ = modules()
    rows = [
        dict(
            date="2024-01-01",
            symbol=symbol,
            minutos_totales="1440",
            minutos_conocidos="1440",
            minutos_desconocidos="0",
            minutos_elegibles=eligible,
            suma_forecast_elegible=value,
        )
        for symbol, eligible, value in (("BTCUSDT", "144", "14.4"), ("ETHUSDT", "0", "0"))
    ]
    day = report.h3_from_assets(rows)[0]
    assert day["opportunity"] == D("0.005")
    assert day["eligible_fraction"] == D("0.05")
    rows[1].update(minutos_conocidos="1439", minutos_desconocidos="1")
    day = report.h3_from_assets(rows)[0]
    assert day["opportunity"] is None
    assert not day["complete"]


def test_h1_digest_ignores_identity_but_detects_target_or_exclusion_changes():
    _, verify = modules()
    a = [
        dict(
            run_id="a",
            symbol="BTCUSDT",
            time_ns="1",
            forecast="0.01",
            realized="0.02",
            horizon_valid="True",
            reason="",
        )
    ]
    b = [dict(a[0], run_id="b")]
    assert verify.economic_digest(a) == verify.economic_digest(b)
    b[0]["realized"] = "0.03"
    assert verify.economic_digest(a) != verify.economic_digest(b)
    b = [dict(a[0], horizon_valid="False", reason="horizon_outside_sample")]
    assert verify.economic_digest(a) != verify.economic_digest(b)


@pytest.mark.parametrize(
    "relative", ["../outside", "C:/outside", "/outside", "a/../../outside", "a\\..\\x"]
)
def test_manifest_paths_cannot_escape_package(tmp_path, relative):
    _, verify = modules()
    with pytest.raises(ValueError, match="[Pp]ath"):
        verify.safe_path(tmp_path, relative)


def test_seal_is_explicit_and_verification_detects_changed_missing_and_extra_members(tmp_path):
    report, verify = modules()
    (tmp_path / "data.txt").write_text("original", encoding="utf-8")
    report.seal_package(tmp_path)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert verify.check_manifest(tmp_path)["members_checked"] == 1
    assert before == {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(FileExistsError):
        report.seal_package(tmp_path)
    (tmp_path / "data.txt").write_text("altered", encoding="utf-8")
    with pytest.raises(ValueError, match="hash|size"):
        verify.check_manifest(tmp_path)
    (tmp_path / "data.txt").unlink()
    with pytest.raises(ValueError, match="missing"):
        verify.check_manifest(tmp_path)
    (tmp_path / "data.txt").write_bytes(before[str(tmp_path / "data.txt")])
    (tmp_path / "extra.txt").write_text("new", encoding="utf-8")
    with pytest.raises(ValueError, match="unlisted"):
        verify.check_manifest(tmp_path)


def write_csv(path, rows, fields=None):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fixture_package(tmp_path):
    """Tiny synthetic artifacts are only fixtures, never historical results."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    report, verify = modules()
    start = verify.timestamp("2023-12-31T00:00:00Z")
    index = dict(schema="rules_sensitivity_batch_v1", runs=[])
    for scenario in report.COMPARATORS:
        for strategy in ("conditional", "permanent"):
            run_id = f"run_{scenario.lower()}_{strategy}"
            run = tmp_path / "corridas" / run_id
            run.mkdir(parents=True)
            config = dict(
                start="2023-12-31T00:00:00Z",
                end="2024-01-02T00:00:00Z",
                capital="100",
                hedge_tolerance="0.005",
                research_maintenance_multiplier="1",
                symbols=["BTCUSDT", "ETHUSDT"],
                leverage="2",
            )
            common = dict(run_id=run_id, strategy=strategy, symbol="PORTFOLIO")
            daily = [
                dict(common, **daily_row(start + verify.DAY - 1, "110", funding="10")),
                dict(common, **daily_row(start + 2 * verify.DAY - 1, "121", funding="21")),
            ]
            write_csv(run / "equity_daily.csv", daily)
            write_csv(
                run / "run_summary.csv",
                [
                    dict(
                        common,
                        status="complete",
                        capital_usdt="100",
                        final_equity_usdt="121",
                        net_pnl_usdt="21",
                    )
                ],
            )
            write_csv(
                run / "pnl_components.csv",
                [
                    dict(
                        common,
                        component=key.removesuffix("_usdt"),
                        amount_usdt="21" if key == "funding_usdt" else "0",
                        included_in_total=key != "slippage_informational_usdt",
                    )
                    for key in verify.COMPONENTS
                ],
            )
            write_csv(run / "metrics.csv", [dict(common, period="full", net_return="0.21")])
            forecast = [
                dict(
                    run_id=run_id,
                    symbol=symbol,
                    strategy="COMMON",
                    time_ns=str(start + 1),
                    anchor=str(start),
                    history_start=str(start - 1),
                    horizon_end=str(start + 2),
                    forecast="0.01",
                    no_change="0.03",
                    realized="0.02",
                    horizon_valid="True",
                    reason="",
                    absolute_error_ewma="0.01",
                    absolute_error_no_change="0.01",
                )
                for symbol in ("BTCUSDT", "ETHUSDT")
            ]
            write_csv(run / "forecast_evaluation.csv", forecast)
            write_csv(
                run / "h1_summary.csv",
                [
                    dict(
                        run_id=run_id,
                        symbol=symbol,
                        period=period,
                        observations="2" if symbol == "EQUAL_WEIGHT" else "1",
                        excluded="0",
                        mae_ewma="0.01",
                        mae_no_change="0.01",
                    )
                    for period in ("full",)
                    for symbol in ("BTCUSDT", "ETHUSDT", "EQUAL_WEIGHT")
                ],
            )
            opportunity = [
                dict(
                    run_id=run_id,
                    date=date,
                    time_ns=str(start + (i + 1) * verify.DAY - 1),
                    complete="True",
                    opportunity="0",
                    eligible_fraction="0",
                    reason="",
                )
                for i, date in enumerate(("2023-12-31", "2024-01-01"))
            ]
            write_csv(run / "opportunity_daily.csv", opportunity)
            write_csv(run / "execution_summary.csv", [dict(common, invested_seconds="0")])
            (run / "effective_config.toml").write_text('capital = "100"\n', encoding="utf-8")
            signals = [dict(r, strategy=strategy, valid=True, forecast_reason="") for r in forecast]
            for name in (
                "signals",
                "ledger",
                "fills",
                "orders",
                "risk_events",
                "positions",
                "funding_payments",
            ):
                rows = signals if name == "signals" else []
                pq.write_table(pa.Table.from_pylist(rows), run / (name + ".parquet"))
            manifest = dict(
                run_id=run_id,
                status="complete",
                artifacts_complete=True,
                config=config,
                strategies=[dict(strategy=strategy)],
                output_hashes={
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in run.iterdir()
                },
            )
            (run / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            manifest_sha = hashlib.sha256((run / "run_manifest.json").read_bytes()).hexdigest()
            (run / "run_manifest.sha256").write_text(manifest_sha + "\n", encoding="ascii")
            index["runs"].append(
                dict(
                    scenario=scenario,
                    strategy=strategy,
                    status="ejecutado",
                    engine_status="complete",
                    run_id=run_id,
                    path=f"corridas/{run_id}",
                    manifest_sha256=manifest_sha,
                )
            )
            h3 = tmp_path / "h3_minutos"
            h3.mkdir(exist_ok=True)
            write_csv(
                h3 / (run_id + ".csv"),
                [
                    dict(
                        scenario=scenario,
                        strategy=strategy,
                        run_id=run_id,
                        date=date,
                        symbol=symbol,
                        minutos_totales="1440",
                        minutos_conocidos="1440",
                        minutos_desconocidos="0",
                        minutos_elegibles="0",
                        suma_forecast_elegible="0",
                    )
                    for date in ("2023-12-31", "2024-01-01")
                    for symbol in ("BTCUSDT", "ETHUSDT")
                ],
            )
    (tmp_path / "indice_corridas.json").write_text(json.dumps(index), encoding="utf-8")
    return tmp_path


def test_build_and_portable_verifier_work_without_engine_or_writes(tmp_path):
    report, verify = modules()
    package = fixture_package(tmp_path / "exported package")
    report.build_report(package, figures=False)
    assert not (package / verify.MANIFEST).exists()
    metrics = verify.read_csv(package / "comparacion" / "metricas_cartera_periodo.csv")
    row = next(
        r
        for r in metrics
        if r["scenario"] == "BASE_E3" and r["strategy"] == "conditional" and r["period"] == "2024+"
    )
    assert row["starting_equity_usdt"] == "110"
    assert row["sharpe"] == ""
    assert row["sharpe_reason"] == "fewer than two daily returns"
    report.seal_package(package)
    before = {p.relative_to(package): p.read_bytes() for p in package.rglob("*") if p.is_file()}
    command = [
        sys.executable,
        "-I",
        "-S",
        "-B",
        str(Path(verify.__file__).resolve()),
        "--package",
        str(package),
    ]
    result = subprocess.run(command, capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["status"] == "passed"
    assert before == {
        p.relative_to(package): p.read_bytes() for p in package.rglob("*") if p.is_file()
    }


def test_verifier_rejects_bad_report_arithmetic_even_after_resealing_fixture(tmp_path):
    report, verify = modules()
    package = fixture_package(tmp_path)
    report.build_report(package, figures=False)
    path = package / "comparacion" / "metricas_cartera_periodo.csv"
    rows = verify.read_csv(path)
    rows[0]["net_pnl_usdt"] = "22"
    write_csv(path, rows)
    report.seal_package(package)
    with pytest.raises(ValueError, match="net_pnl_usdt|reconcil"):
        verify.verify_package(package)


def test_verifier_rejects_duplicated_scenario(tmp_path):
    report, verify = modules()
    package = fixture_package(tmp_path)
    index_path = package / "indice_corridas.json"
    index = json.loads(index_path.read_text())
    index["runs"].append(index["runs"][0])
    index_path.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        report.build_report(package, figures=False)


def test_failed_run_is_preserved_in_registry_and_never_reported_as_zero(tmp_path):
    report, verify = modules()
    package = fixture_package(tmp_path)
    path = package / "indice_corridas.json"
    index = json.loads(path.read_text())
    for entry in index["runs"]:
        if entry["scenario"] == "FUT4_DECISION":
            entry.update(status="fallido", engine_status="failed", reason="fixture failure")
    path.write_text(json.dumps(index), encoding="utf-8")
    report.build_report(package, figures=False)
    registry = verify.read_csv(package / "comparacion" / "registro_corridas.csv")
    assert sum(r["status"] == "fallido" for r in registry) == 2
    metrics = verify.read_csv(package / "comparacion" / "metricas_cartera_periodo.csv")
    assert not any(r["scenario"] == "FUT4_DECISION" for r in metrics)


@pytest.mark.parametrize(
    "table,column,value",
    [
        ("metricas_cartera_periodo", "sharpe", "0"),
        ("metricas_cartera_periodo", "cagr", "0"),
        ("metricas_cartera_periodo", "max_drawdown", "-0.9"),
        ("h3_diario", "opportunity", "0.1"),
        ("h3_regimen", "opportunity_mean", "0.1"),
        ("h1_invariancia", "btc_weight", "1"),
    ],
)
def test_verifier_recomputes_metrics_hypotheses_and_weights(tmp_path, table, column, value):
    report, verify = modules()
    package = fixture_package(tmp_path)
    report.build_report(package, figures=False)
    path = package / "comparacion" / (table + ".csv")
    rows = verify.read_csv(path)
    rows[0][column] = value
    write_csv(path, rows)
    report.seal_package(package)
    with pytest.raises(ValueError, match="mismatch|weight|H3"):
        verify.verify_package(package)


def test_verifier_does_not_accept_unknown_h3_minutes_as_zero_opportunity(tmp_path):
    report, verify = modules()
    package = fixture_package(tmp_path)
    report.build_report(package, figures=False)
    path = package / "h3_minutos" / "run_base_e3_conditional.csv"
    rows = verify.read_csv(path)
    rows[0].update(minutos_conocidos="1439", minutos_desconocidos="1")
    write_csv(path, rows)
    report.seal_package(package)
    with pytest.raises(ValueError, match="H3"):
        verify.verify_package(package)


def test_h3_alias_requires_same_strategy_and_verified_nondecision_source(tmp_path):
    _, verify = modules()
    package = fixture_package(tmp_path)
    items = verify.load_index(package)
    base = items[0]
    (package / "h3_procedencia.json").write_text(
        json.dumps(
            {
                "aliases": {
                    base["run_id"]: {
                        "source_run_id": "run_fut4_decision_conditional",
                        "status": "derivado_invariancia_verificada",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="alias"):
        verify.h3_source(package, base, items)


def test_margin_reporting_reads_persisted_tier_rates_and_deductions():
    report, verify = modules()
    row = daily_row(verify.timestamp("2024-01-01T00:00:00Z"), "100", short="600")
    row.update(BTCUSDT_mark="100", BTCUSDT_average="100", BTCUSDT_collateral="2000")
    assumptions = {
        "rules": [
            {
                "symbol": "BTCUSDT",
                "market": "futures",
                "valid_from": "2024-01-01T00:00:00Z",
                "valid_to": "2024-01-02T00:00:00Z",
                "values": {
                    "tiers": [
                        {"floor": "0", "cap": "50000", "rate": "0.008", "deduction": "0"},
                        {"floor": "50000", "cap": "100000000", "rate": "0.02", "deduction": "600"},
                    ]
                },
            }
        ]
    }
    observed = report.margin_daily([row], assumptions)[0]
    assert observed["maintenance_usdt"] == D("600")
    assert observed["maintenance_to_balance_max"] == D("0.3")


def test_run_provenance_checks_snapshot_bytes_and_aggregate_code_hash(tmp_path):
    _, verify = modules()
    package = fixture_package(tmp_path)
    item = verify.load_index(package)[0]
    run = package / item["path"]
    snapshot = package / "codigo_base" / "src" / "example.py"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(b"# original bytes\r\n")
    manifest_path = run / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["code_files"] = {"src/example.py": hashlib.sha256(snapshot.read_bytes()).hexdigest()}
    manifest["code_hash"] = hashlib.sha256(
        json.dumps(
            manifest["code_files"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    item["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    (run / "run_manifest.sha256").write_text(item["manifest_sha256"] + "\n", encoding="ascii")
    verify.check_run(package, item)
    snapshot.write_bytes(b"# normalized bytes\n")
    with pytest.raises(ValueError, match="code|snapshot"):
        verify.check_run(package, item)


@pytest.mark.parametrize("table", ["registro_corridas", "metricas_cartera_periodo"])
def test_report_cannot_invent_status_or_an_unregistered_scenario(tmp_path, table):
    report, verify = modules()
    package = fixture_package(tmp_path)
    report.build_report(package, figures=False)
    path = package / "comparacion" / (table+".csv")
    rows = verify.read_csv(path)
    if table == "registro_corridas":
        rows[0]["status"] = "reutilizado_verificado"
    else:
        rows.append(dict(rows[0], scenario="UNREGISTERED"))
    write_csv(path, rows)
    report.seal_package(package)
    with pytest.raises(ValueError, match="[Rr]egistr|[Ii]dentity"):
        verify.verify_package(package)

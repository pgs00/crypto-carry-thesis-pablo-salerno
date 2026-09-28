"""Literal preservation and destination controls for the derived report builder."""

from decimal import Decimal as D

import pytest


def builder():
    from scripts import correct_rules_sensitivity_report

    return correct_rules_sensitivity_report


def test_destination_cannot_replace_or_enter_source(tmp_path):
    source = tmp_path / "sealed"
    source.mkdir()
    protected = source / "evidence.txt"
    protected.write_bytes(b"sealed bytes")
    with pytest.raises(ValueError, match="source|parent|sealed"):
        builder().validate_destination(source, source / "correction")
    with pytest.raises((ValueError, FileExistsError)):
        builder().validate_destination(source, source)
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(FileExistsError):
        builder().validate_destination(source, existing)
    builder().validate_destination(source, tmp_path / "new")
    assert protected.read_bytes() == b"sealed bytes"
    assert not (tmp_path / "new").exists()


def test_destination_cannot_enter_another_sealed_package(tmp_path):
    source = tmp_path / "parent"
    source.mkdir()
    e3 = tmp_path / "other sealed evidence"
    e3.mkdir()
    (e3 / "manifest.json").write_text("{}", encoding="utf-8")
    (e3 / "manifest.sha256").write_text("preserved", encoding="ascii")
    with pytest.raises(ValueError, match="sealed"):
        builder().validate_destination(source, e3 / "new child")


def test_only_exposure_changes_financial_precision_is_preserved():
    original = dict(
        scenario="BASE_E3",
        strategy="conditional",
        run_id="same",
        period="full",
        cagr="-0.01000000000000000003",
        sharpe="-0.5",
        final_equity_usdt="99.0000000000000000001",
        coverage_complete="True",
        capital_utilization_daily_mean="0.01234567890123456789",
        invested_seconds="9",
        unhedged_seconds="8",
        invested_fraction="0.9",
    )
    summary = dict(
        scenario="BASE_E3",
        strategy="conditional",
        run_id="same",
        period="full",
        symbol="PORTFOLIO",
        invested_seconds=D(2),
        unhedged_seconds=D(1),
        invested_fraction=D("0.2"),
        raw_invested_seconds=D(9),
        dust_only_seconds=D(7),
    )
    corrected = builder().correct_metrics([original], [summary])[0]
    assert corrected["invested_seconds"] == D(2)
    assert corrected["unhedged_seconds"] == D(1)
    assert corrected["cagr"] == "-0.01000000000000000003"
    assert corrected["sharpe"] == "-0.5"
    assert corrected["final_equity_usdt"] == "99.0000000000000000001"
    assert corrected["capital_utilization_daily_mean"] == "0.01234567890123456789"
    assert corrected["run_id"] == "same"
    assert original["invested_seconds"] == "9"


def test_metrics_reject_duplicate_and_missing_exposure_rows():
    row = dict(scenario="BASE_E3", strategy="conditional", run_id="a", period="full")
    exposure = dict(row, symbol="PORTFOLIO", invested_seconds=D(1))
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        builder().correct_metrics([row], [exposure, exposure])
    with pytest.raises(ValueError, match="[Mm]issing"):
        builder().correct_metrics([row], [])
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        builder().correct_metrics([row, row], [exposure])


def test_deltas_preserve_economic_values_and_correct_operational_values():
    rows = [
        dict(
            scenario=s,
            strategy="conditional",
            run_id=r,
            period="full",
            invested_seconds=D(seconds),
            net_pnl_usdt=pnl,
        )
        for s, r, seconds, pnl in (
            ("BASE_E3", "b", 4, "10.1234567890123456789"),
            ("FUT4_REALIZADA", "f", 6, "11.1234567890123456789"),
        )
    ]
    common = dict(
        scenario="FUT4_REALIZADA",
        comparator="BASE_E3",
        strategy="conditional",
        period="full",
        run_id="f",
        comparator_run_id="b",
        reason="",
    )
    old = [
        dict(
            common,
            metric="net_pnl_usdt",
            value="11.1234567890123456789",
            comparator_value="10.1234567890123456789",
            delta="1.0000000000000000000",
        ),
        dict(common, metric="invested_seconds", value="10", comparator_value="10", delta="0"),
    ]
    actual = builder().correct_deltas(old, rows)
    assert actual[0] == old[0]
    assert actual[1]["value"] == D(6)
    assert actual[1]["comparator_value"] == D(4)
    assert actual[1]["delta"] == D(2)


def test_active_report_entrypoint_applies_both_corrected_contracts():
    from scripts import report_historical_rules_sensitivity as active

    context = dict(
        scenario="BASE_E3",
        period="full",
        coverage_complete=True,
        start_utc="2024-01-01T00:00:00Z",
        end_exclusive_utc="2024-01-02T00:00:00Z",
    )
    h2 = active.h2_comparison(
        [
            dict(context, strategy="conditional", run_id="c", cagr="-0.01", sharpe="-0.5"),
            dict(context, strategy="permanent", run_id="p", cagr="0.01", sharpe="-1"),
        ]
    )[0]
    assert h2["verdict"] == "no_favorable"
    assert h2["cagr_positive"] is False
    assert h2["sharpe_superior"] is True
    rows = active.exposure_summary(
        [dict(time_ns=0, symbol="BTCUSDT", spot="0.00001", short="0", state="FLAT")],
        [("full", 0, 10_000_000_000)],
        D("0.005"),
    )
    row = next(r for r in rows if r["symbol"] == "PORTFOLIO")
    assert row["invested_seconds"] == 0
    assert row["unhedged_seconds"] == 0
    assert row["raw_invested_seconds"] == 10


def test_v2_cannot_fall_back_to_legacy_verifier_without_parent(tmp_path):
    from scripts.verify_rules_sensitivity_package import verify_package

    (tmp_path / "manifiesto_paquete.json").write_text(
        '{"schema": "rules_sensitivity_correction_v2"}', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="explicit --parent"):
        verify_package(tmp_path)


def test_generic_v2_entrypoint_is_readonly_even_without_python_B(tmp_path):
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    package = tmp_path / "invalid sealed fixture"
    tools = package / "herramientas"
    tools.mkdir(parents=True)
    source = Path(__file__).resolve().parents[2] / "scripts"
    for name in (
        "verify_rules_sensitivity_package.py",
        "verify_rules_sensitivity_correction.py",
        "rules_sensitivity_h2.py",
    ):
        shutil.copyfile(source / name, tools / name)
    (package / "manifiesto_paquete.json").write_text(
        '{"schema": "rules_sensitivity_correction_v2"}', encoding="utf-8"
    )
    before = {p.relative_to(package): p.read_bytes() for p in package.rglob("*") if p.is_file()}
    result = subprocess.run(
        [
            sys.executable,
            str(tools / "verify_rules_sensitivity_package.py"),
            "--package",
            str(package),
            "--parent",
            str(tmp_path / "missing parent"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=tmp_path,
    )
    assert result.returncode == 1  # Invalid fixture must fail without modifying evidence.
    assert before == {
        p.relative_to(package): p.read_bytes() for p in package.rglob("*") if p.is_file()
    }

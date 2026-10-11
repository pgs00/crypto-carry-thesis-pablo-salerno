"""B6 contracts use invented accounts, never alternative historical results."""

from dataclasses import replace
from decimal import Decimal as D

import pytest

from crypto_carry.config import DAY, Config, timestamp
from scripts import stability_uncertainty_report as report


def snapshot(day, funding="0", *, partial=False):
    total = D(funding)
    row = dict(time_ns=timestamp(day + "T00:00:00Z") + DAY - 1,
               equity=str(D(10000) + total), free_spot="10000", free_futures=str(total),
               debt="0", partial_day=partial)
    for symbol in ("BTCUSDT", "ETHUSDT"):
        for field in ("spot", "short", "average", "spot_cost", "realized_spot",
                      "realized_futures", "funding", "fees", "liquidation_fees",
                      "collateral", "slippage"):
            row[symbol + "_" + field] = "0"
        row[symbol + "_spot_price"] = row[symbol + "_mark"] = "100"
    row["BTCUSDT_funding"] = str(total)
    return row


def config(start="2023-01-01T00:00:00Z", end="2023-01-04T00:00:00Z"):
    return replace(Config(), start=start, end=end)


def full(rows):
    return next(row for row in rows if row["period"] == "full")


def test_fresh_start_and_inherited_segment_keep_different_denominators():
    original = config("2022-12-31T00:00:00Z", "2023-01-03T00:00:00Z")
    continuous = report.financial_view(
        [snapshot("2022-12-31", "2000"), snapshot("2023-01-01", "2120"),
         snapshot("2023-01-02", "2000")], original, timestamp("2023-01-01T00:00:00Z"))
    fresh = report.financial_view(
        [snapshot("2023-01-01", "120"), snapshot("2023-01-02", "0")],
        config(end="2023-01-03T00:00:00Z"))
    assert continuous["diario"][0]["starting_equity_usdt"] == D(12000)
    assert continuous["diario"][0]["daily_return"] == D(".01")
    assert fresh["diario"][0]["starting_equity_usdt"] == D(10000)
    assert fresh["diario"][0]["daily_return"] == D(".012")
    assert full(continuous["metricas"])["net_pnl_usdt"] == 0
    assert continuous["saldos_iniciales"][0]["free_futures_usdt"] == D(2000)
    assert fresh["saldos_iniciales"][0]["free_futures_usdt"] == 0


def test_original_cut_is_explicitly_partial_and_has_no_prestart_zero_year():
    rows = [snapshot("2023-01-01"), snapshot("2023-01-02"), snapshot("2023-01-03")]
    result = report.financial_view(rows, config())
    periods = {r["period"]: r for r in result["metricas"]}
    assert "2022" not in periods
    assert "2022-2023" not in periods
    assert periods["2022-2023_disponible"]["original_period_complete"] is False
    assert periods["2022-2023_disponible"]["start_utc"].startswith("2023-01-01")
    assert len(result["diario"]) == 3


def test_inherited_inventory_carries_cost_and_unrealized_pnl_through_the_cut():
    before = snapshot("2022-12-31")
    after = snapshot("2023-01-01")
    for row, price, equity in ((before, "110", "10020"), (after, "120", "10040")):
        row.update(free_spot="9700", equity=equity, BTCUSDT_spot="2", BTCUSDT_short="2",
                   BTCUSDT_spot_cost="200", BTCUSDT_average="100", BTCUSDT_collateral="100",
                   BTCUSDT_spot_price=price)
    result = report.financial_view(
        [before, after], config("2022-12-31T00:00:00Z", "2023-01-02T00:00:00Z"),
        timestamp("2023-01-01T00:00:00Z"))
    assert full(result["metricas"])["starting_equity_usdt"] == 10020
    assert full(result["metricas"])["spot_pnl_usdt"] == 20
    assert result["saldos_iniciales"][0]["spot"] == 2
    assert result["saldos_iniciales"][0]["spot_cost"] == 200


def test_missing_day_does_not_become_a_one_day_return_or_zero_cash():
    result = report.financial_view(
        [snapshot("2023-01-01", "100"), snapshot("2023-01-03", "200")], config())
    row = full(result["metricas"])
    assert row["coverage_complete"] is False
    assert row["missing_days"] == 1
    assert row["cagr"] is None and row["sharpe"] is None
    assert result["diario"][1]["daily_return"] is None
    assert result["diario"][1]["return_reason"] == "nonconsecutive_daily_observations"
    assert len(result["diario"]) == 2


def test_end_is_exclusive_and_prestart_economic_rows_are_rejected():
    with pytest.raises(ValueError, match="outside economic sample"):
        report.financial_view([snapshot("2022-12-31")], config())
    with pytest.raises(ValueError, match="outside economic sample"):
        report.financial_view([snapshot("2023-01-04")], config())


def test_full_day_truncation_preserves_actual_dates_without_extrapolating_cash():
    result = report.financial_view([snapshot("2023-01-01", "100")], config())
    row = full(result["metricas"])
    assert row["end_exclusive_utc"].startswith("2023-01-02")
    assert row["requested_end_exclusive_utc"].startswith("2023-01-04")
    assert row["coverage_complete"] is False
    assert row["days"] == 1
    assert row["sharpe"] is None
    assert row["sharpe_reason"] == "fewer than two daily returns"


def test_sharpe_uses_sample_variance_rf_zero_and_cagr_uses_compounding():
    result = report.financial_view(
        [snapshot("2023-01-01", "100"), snapshot("2023-01-02", "302")],
        config(end="2023-01-03T00:00:00Z"))
    row = full(result["metricas"])
    assert float(row["net_return"]) == pytest.approx(.0302, abs=1e-15)
    assert row["cagr"] == pytest.approx(1.0302 ** (365 / 2) - 1, rel=1e-13)
    assert row["sharpe"] == pytest.approx(40.52776825831888, rel=1e-13)
    assert row["max_drawdown"] == 0


def test_cash_only_pair_has_nd_h2_and_alternative_h3_never_passes():
    view = report.financial_view([snapshot("2023-01-01"), snapshot("2023-01-02")],
                                 config(end="2023-01-03T00:00:00Z"))
    metrics = [dict(row, scenario="I2023", strategy=strategy, run_id="run_" + strategy)
               for strategy in ("conditional", "permanent") for row in view["metricas"]]
    rows = report.h2_comparison(metrics)
    assert all(r["verdict"] == "no_concluyente" for r in rows)
    coverage = report.h3_coverage(metrics)
    assert all(r["verdict"] == "ND" for r in coverage)
    assert all("2022" in r["reason"] for r in coverage)


@pytest.mark.parametrize("field,value", [("equity", "10001"),
                                         ("BTCUSDT_funding", True),
                                         ("partial_day", "unknown")])
def test_accounting_and_types_are_actually_adulterated(field, value):
    row = snapshot("2023-01-01")
    row[field] = value
    with pytest.raises(ValueError):
        report.financial_view([row], config())


def test_portable_table_verifier_recomputes_instead_of_trusting_saved_metric(tmp_path):
    rows = [dict(period="full", net_return=D(".01"), coverage_complete=True)]
    report.write_table(tmp_path / "metricas.csv", rows)
    report.verify_table(tmp_path / "metricas.csv", rows)
    altered = [dict(rows[0], net_return=D(".02"))]
    report.write_table(tmp_path / "metricas.csv", altered)
    with pytest.raises(ValueError, match="metricas"):
        report.verify_table(tmp_path / "metricas.csv", rows)


def test_portable_table_verifier_rejects_invalid_boolean_type(tmp_path):
    path = tmp_path / "metricas.csv"
    rows = [dict(period="full", net_return=D(".01"), coverage_complete=True)]
    report.write_table(path, rows)
    path.write_text(path.read_text().replace("True", "definitely"), encoding="utf-8")
    with pytest.raises(ValueError, match="coverage_complete"):
        report.verify_table(path, rows)


def test_render_only_uses_reconciled_tables_without_reopening_sources(tmp_path):
    view = report.financial_view([snapshot("2023-01-01"), snapshot("2023-01-02")],
                                 config(end="2023-01-03T00:00:00Z"))
    metrics, daily = [], []
    for scenario in ("BASE_E3", "I2023", "I2024", "BASE_CONTINUA_I2023", "BASE_CONTINUA_I2024"):
        for strategy in report.BASES:
            identity = dict(scenario=scenario, strategy=strategy, run_id=scenario + strategy)
            metrics.extend(dict(row, **identity, invested_fraction=D(0)) for row in view["metricas"])
            daily.extend(dict(row, **identity) for row in view["diario"])
    report.write_table(tmp_path / "tablas/metricas.csv", metrics)
    report.write_table(tmp_path / "tablas/diario.csv", daily)
    report.write_table(tmp_path / "tablas/h2.csv", report.h2_comparison(metrics))
    report.write_json(tmp_path / "resultados/financiero.json", dict(passed=True))
    report.render_report(tmp_path)
    assert len(list((tmp_path / "figuras").glob("*.png"))) == 3
    assert (tmp_path / "reporte.html").is_file()
    assert not (tmp_path / "evidencia").exists()

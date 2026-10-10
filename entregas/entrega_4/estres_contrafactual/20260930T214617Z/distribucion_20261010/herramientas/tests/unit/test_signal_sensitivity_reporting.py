import importlib.util
from decimal import Decimal as D

import pytest

from crypto_carry.config import Config, timestamp


def test_hypothesis_units_and_unknown_h3_days_remain_unknown():
    assert importlib.util.find_spec("scripts.signal_sensitivity_hypotheses") is not None
    from scripts.signal_sensitivity_hypotheses import summarize_h1, summarize_h3

    config = Config(start="2023-12-31T00:00:00Z", end="2024-01-02T00:00:00Z",
                    horizon_hours=72)
    h1 = [dict(symbol=s, time_ns=timestamp(config.start), horizon_valid=True, reason="",
               absolute_error_ewma=D(e), absolute_error_no_change=D(n))
          for s, e, n in [("BTCUSDT", ".001", ".004"), ("ETHUSDT", ".003", ".006")]]
    rows = summarize_h1(h1, config)
    full = next(r for r in rows if r["period"] == "full" and r["symbol"] == "EQUAL_WEIGHT")
    assert full["unit"] == "pb/72 h"
    assert full["mae_ewma_bps"] == D(20)
    assert full["mae_no_change_bps"] == D(50)
    assert full["skill_vs_no_change"] == D(".6")
    financials = [dict(period=p, strategy="conditional", cagr=c, coverage_complete=True)
                  for p, c in [("full", ".02"), ("2022-2023", ".03"), ("2024+", ".01"),
                               ("2023", ".03"), ("2024", ".01")]]
    daily = [dict(time_ns=timestamp(day)+86400000000000-1, complete=known,
                  opportunity=value, eligible_fraction=D(".1") if known else None)
             for day, known, value in [("2023-12-31T00:00:00Z", True, D(".005")),
                                       ("2024-01-01T00:00:00Z", False, None)]]
    h3 = summarize_h3(daily, config, financials)
    after = next(r for r in h3 if r["period"] == "2024+")
    assert after["valid_days"] == 0
    assert after["opportunity_mean"] is None
    assert after["h3_descriptive"] == "no_concluyente"
    daily[1].update(complete=True, opportunity=D(".002"), eligible_fraction=D(".1"))
    h3 = summarize_h3(daily, config, financials)
    assert all(r["h3_descriptive"] == "favorable" for r in h3)


def test_portfolio_builder_retains_inherited_yearly_balance_and_daily_capital():
    assert importlib.util.find_spec("scripts.signal_sensitivity_report") is not None
    from scripts.signal_sensitivity_report import financial_tables

    config = Config(start="2023-12-31T00:00:00Z", end="2024-01-02T00:00:00Z")
    rows = []
    for date, equity, funding in [("2023-12-31", "10010", "10"), ("2024-01-01", "10030", "30")]:
        row = dict(time_ns=timestamp(date+"T00:00:00Z")+86400000000000-1,
                   equity=equity, free_spot="9900", free_futures=funding, debt="0", partial_day=False)
        for symbol in config.symbols:
            row.update({f"{symbol}_{field}": "0" for field in
                        ("spot", "short", "spot_cost", "average", "realized_spot", "realized_futures",
                         "funding", "fees", "liquidation_fees", "slippage", "collateral")})
            row.update({f"{symbol}_spot_price": "100", f"{symbol}_mark": "100"})
        row.update(BTCUSDT_spot="1", BTCUSDT_spot_cost="100", BTCUSDT_funding=funding)
        rows.append(row)
    daily, assets, periods = financial_tables(rows, config)
    after = next(r for r in periods if r["period"] == "2024")
    assert after["starting_equity_usdt"] == D("10010")
    assert after["net_pnl_usdt"] == D(20)
    assert daily[1]["capital_deployed_usdt"] == D(100)
    assert after["reconciliation_residual_usdt"] == 0
    assert len(assets) == 4


def test_period_reconciliation_rejects_accumulated_daily_residuals():
    from scripts.signal_sensitivity_report import financial_tables

    config = Config(start="2023-12-30T00:00:00Z", end="2024-01-03T00:00:00Z")
    rows = []
    for date, drift in [("2023-12-30", "6E-9"), ("2023-12-31", "12E-9"),
                        ("2024-01-01", "6E-9"), ("2024-01-02", "0")]:
        equity = str(D(10000)+D(drift))
        row = dict(time_ns=timestamp(date+"T00:00:00Z")+86400000000000-1,
                   equity=equity, free_spot=equity, free_futures="0", debt="0", partial_day=False)
        for symbol in config.symbols:
            row.update({f"{symbol}_{field}": "0" for field in
                        ("spot", "short", "spot_cost", "average", "realized_spot", "realized_futures",
                         "funding", "fees", "liquidation_fees", "slippage", "collateral")})
            row.update({f"{symbol}_spot_price": "100", f"{symbol}_mark": "100"})
        rows.append(row)
    with pytest.raises(ValueError, match="Period accounting"):
        financial_tables(rows, config)


def test_large_decision_table_roundtrip_keeps_exact_decimal_and_nanosecond_cells(tmp_path):
    from scripts.build_signal_sensitivity import read_table, write_table

    rows = [dict(time_ns=1705276980000000001, rate=D("0.0012300000000000000001"),
                 valid=False, reason="información no disponible", optional=None)]
    write_table(tmp_path, "decisiones", rows)
    assert (tmp_path/"tablas/decisiones.parquet").is_file()
    assert not (tmp_path/"tablas/decisiones.csv").exists()
    assert read_table(tmp_path, "decisiones") == [dict(time_ns="1705276980000000001",
        rate="0.0012300000000000000001", valid="False", reason="información no disponible", optional="")]


def test_conclusion_separates_economic_and_market_invariance():
    from scripts.signal_sensitivity_docs import conclusion_lines

    scenarios = ("BASE_E3", "H072", "H336", "V012", "V048", "B025", "B100")
    tables = dict(metricas=[], h1_resumen=[], h2=[], h3_resumen=[], invariancias=[])
    for scenario in scenarios:
        for strategy in ("conditional", "permanent"):
            tables["metricas"].append(dict(scenario=scenario, strategy=strategy, period="full",
                net_pnl_usdt=D(100), invested_fraction=D(".2"),
                capital_utilization_daily_mean=D(".1")))
            tables["invariancias"].append(dict(scenario=scenario, strategy=strategy,
                economic_invariant=True, h3_daily_equal_base=scenario != "B025"))
        tables["h1_resumen"].append(dict(scenario=scenario, period="full", symbol="EQUAL_WEIGHT",
            mae_ewma_bps=D(6)))
        tables["h2"].append(dict(scenario=scenario, period="full", verdict="no_favorable"))
        tables["h3_resumen"].append(dict(scenario=scenario, period="full", h3_descriptive="contraria",
            opportunity_mean_bps=D(3 if scenario == "B025" else 4)))
    text = "\n".join(conclusion_lines(tables))
    assert "B025: economía igual" in text
    assert "H3 diario igual=False" in text
    assert "-1.000000 pb/168 h" in text
    assert "H2 completo conserva" in text
    next(r for r in tables["h3_resumen"] if r["scenario"] == "B025")["opportunity_mean_bps"] = None
    assert "delta de oportunidad media completa ND pb/168 h" in "\n".join(conclusion_lines(tables))

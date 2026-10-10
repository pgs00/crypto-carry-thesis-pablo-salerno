from decimal import Decimal as D
from pathlib import Path

import pytest

from scripts.stress_counterfactual_report import h3_daily, overlap_duration


def test_h3_equal_asset_weights_and_complete_forecast_not_net_of_cost():
    rows = [dict(date="2022-01-01", symbol=s, minutos_totales=1440, minutos_conocidos=1440,
                 minutos_desconocidos=0, minutos_elegibles=n, suma_forecast_elegible=v)
            for s, n, v in [("BTCUSDT", 720, "7.2"), ("ETHUSDT", 1440, "28.8")]]
    daily = h3_daily(rows, ("BTCUSDT", "ETHUSDT"))
    assert daily[0]["opportunity"] == D(".0125")
    assert daily[0]["eligible_fraction"] == D(".75")
    rows[0]["minutos_conocidos"], rows[0]["minutos_desconocidos"] = 1439, 1
    assert h3_daily(rows, ("BTCUSDT", "ETHUSDT"))[0]["opportunity"] is None


def test_h3_duplicate_asset_or_inconsistent_count_is_rejected():
    row = dict(date="2022-01-01", symbol="BTCUSDT", minutos_totales=1440,
               minutos_conocidos=1440, minutos_desconocidos=0, minutos_elegibles=1441,
               suma_forecast_elegible="1")
    with pytest.raises(ValueError):
        h3_daily([row, row], ("BTCUSDT", "ETHUSDT"))


def test_fixed_calendar_coverage_unites_overlaps_without_stressing_new_time():
    assert overlap_duration(5, 25, [(0, 10), (8, 20), (30, 40)]) == 15
    assert overlap_duration(25, 30, [(0, 10), (8, 20), (30, 40)]) == 0


def test_h1_report_does_not_depend_on_ephemeral_cohort_cache(monkeypatch):
    from scripts import stress_counterfactual_report as report

    monkeypatch.setattr(report, "parquet", lambda _: [])
    monkeypatch.setattr(report, "funding_rows_from_run", lambda _: [])
    monkeypatch.setattr(report, "forecast_rows", lambda _: [])
    monkeypatch.setattr(report, "evaluate_h1", lambda *args: ([], {}, {"checked": True}))
    monkeypatch.setattr(report, "summarize_h1", lambda *args: [])
    from crypto_carry.config import Config
    cache = {}
    first = report.hypothesis_h1(Path("run"), Path("base"), Config(), cache)
    assert cache
    second = report.hypothesis_h1(Path("run"), Path("base"), Config(), cache)
    assert first == second


def test_window_operations_use_ledger_realized_results_without_double_counting_valuation():
    from decimal import Decimal as D

    from scripts.stress_counterfactual_report import window_ledger_components
    windows = [dict(window_id=1, start_ns=10, end_ns=20)]
    ledger = [dict(time_ns=t, kind=k, pnl=pnl, fee=fee, liquidation_fee=liq, funding=fund,
                   amount_usdt="777") for t,k,pnl,fee,liq,fund in
              ((9,"spot_sell","99","0","0","0"),
               (10,"spot_sell","-4",".1","0","0"),
               (15,"futures_buy","2",".2",".3","0"),
               (20,"funding","0","0","0",".5"),
               (21,"spot_sell","99","0","0","0"))]
    row = window_ledger_components(windows, ledger)[0]
    assert row["ledger_records"] == 3
    assert row["spot_realized_pnl_usdt"] == -4
    assert row["futures_realized_pnl_usdt"] == 2
    assert row["realized_operations_net_usdt"] == D("-2.6")
    assert row["realized_plus_funding_usdt"] == D("-2.1")
    assert row["valuation_attribution_added"] is False


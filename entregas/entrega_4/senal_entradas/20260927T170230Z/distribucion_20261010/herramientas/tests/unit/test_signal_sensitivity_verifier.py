import importlib.util
from copy import deepcopy
from decimal import Decimal as D

import pytest

from crypto_carry.config import SECOND, Config, timestamp


def test_h3_verifier_enforces_exact_publication_grid_and_cycle_cost():
    assert importlib.util.find_spec("scripts.verify_signal_sensitivity") is not None
    from scripts.verify_signal_sensitivity import validate_h3_groups

    start = timestamp("2024-01-01T00:00:00Z")
    config = Config(start="2024-01-01T00:00:00Z", end="2024-01-02T00:00:00Z")
    schedules, groups = {}, []
    for symbol in config.symbols:
        times = [start-3600*SECOND, start+60*SECOND+6_000_000]
        schedules[symbol] = [dict(time_ns=t, anchor=t-60*SECOND, forecast=".004", valid=True)
                             for t in times]
        for t, minutes, eligible in zip(times, [2, 1438], [1, 2]):
            groups.append(dict(date="2024-01-01", symbol=symbol, forecast_available_at=t,
                               forecast_anchor=t-60*SECOND, forecast=".004", minutes=minutes,
                               valid_minutes=minutes, eligible_minutes=eligible,
                               opportunity_sum=str(D(".004")*eligible)))
    result = validate_h3_groups(groups, schedules, config)
    assert len(result) == 2
    assert result[0]["minutos_totales"] == 1440
    assert result[0]["minutos_elegibles"] == 3
    assert result[0]["suma_forecast_elegible"] == D(".012")
    broken = deepcopy(groups)
    broken[0]["minutes"] = 1
    broken[1]["minutes"] = 1439
    with pytest.raises(ValueError, match="publication"):
        validate_h3_groups(broken, schedules, config)
    broken = deepcopy(groups)
    broken[0]["opportunity_sum"] = ".003"
    with pytest.raises(ValueError, match="sum"):
        validate_h3_groups(broken, schedules, config)
    broken_schedules = deepcopy(schedules)
    broken_schedules["BTCUSDT"][0]["forecast"] = ".0034"
    broken = deepcopy(groups)
    broken[0].update(forecast=".0034", opportunity_sum=".0034")
    with pytest.raises(ValueError, match="cost"):
        validate_h3_groups(broken, broken_schedules, config)


def test_h3_asset_verifier_rejects_duplicate_day_and_timestamp():
    from scripts.verify_signal_sensitivity import validate_h3_asset_rows

    rows, assets = [], []
    for date in ("2024-01-01", "2024-01-02"):
        assets.append(dict(date=date, symbol="BTCUSDT", minutos_totales=1440,
                           minutos_conocidos=1440, minutos_elegibles=3,
                           suma_forecast_elegible=D(".012")))
        rows.append(dict(date=date, time_ns=timestamp(date+"T00:00:00Z"), symbol="BTCUSDT",
                         expected_minutes=1440, observed_minutes=1440, valid_minutes=1440,
                         eligible_minutes=3, opportunity_sum=D(".012"), opportunity=D(".012")/1440,
                         complete=True, eligible_fraction=D(3)/1440, reason=""))
    validate_h3_asset_rows(rows, assets)
    with pytest.raises(ValueError, match="population"):
        validate_h3_asset_rows([rows[0], rows[0]], assets)
    changed = deepcopy(rows)
    changed[0]["time_ns"] += 1
    with pytest.raises(ValueError, match="timestamp"):
        validate_h3_asset_rows(changed, assets)


def test_nonpositive_opening_retains_legacy_values_and_correct_nd():
    from scripts.signal_sensitivity_report import compare_archived_metrics

    archived = dict(net_return="0", cagr="", sharpe="", annual_volatility="", max_drawdown="0",
                    max_drawdown_days="0", cagr_reason="nonpositive equity or insolvency",
                    sharpe_reason="nonpositive equity or insolvency")
    row = dict(starting_equity_usdt=D(-1), net_return=None, cagr=None, sharpe=None,
               annual_volatility=None, max_drawdown=None, max_drawdown_days=None,
               net_return_reason="nonpositive starting equity", max_drawdown_reason="nonpositive starting equity",
               cagr_reason="nonpositive equity or insolvency", sharpe_reason="nonpositive equity or insolvency")
    differences = compare_archived_metrics(archived, row)
    assert {r["metric"] for r in differences} == {"net_return", "max_drawdown", "max_drawdown_days"}
    assert all(r["archived_value"] == "0" and r["reported_value"] is None for r in differences)
    with pytest.raises(ValueError):
        compare_archived_metrics(archived, dict(row, net_return=D(0)))

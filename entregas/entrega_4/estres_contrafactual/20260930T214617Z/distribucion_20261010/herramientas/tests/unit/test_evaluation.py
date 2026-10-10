import math
from decimal import Decimal as D

import pytest

from crypto_carry.config import DAY, HOUR, SECOND, Config, timestamp
from crypto_carry.evaluation import daily_opportunity, forecast_evaluation, portfolio_metrics
from crypto_carry.models import Funding


def test_h3_keeps_zero_minutes_and_equal_weights_and_rejects_incomplete_day():
    start = timestamp("2024-01-01T00:00:00Z")
    rows = [
        dict(
            time_ns=start + m * 60 * SECOND,
            symbol=s,
            complete=True,
            eligible=s == "BTCUSDT" and m < 720,
            value=".004" if s == "BTCUSDT" and m < 720 else "0",
        )
        for m in range(1440)
        for s in Config().symbols
    ]
    result = daily_opportunity(rows, Config())
    assert result.iloc[0]["opportunity"] == pytest.approx(0.001)
    assert result.iloc[0]["complete"]
    rows[0]["complete"] = False
    assert not daily_opportunity(rows, Config()).iloc[0]["complete"]
    assert math.isnan(daily_opportunity(rows, Config()).iloc[0]["opportunity"])


def test_metrics_include_initial_capital_sample_std_and_undefined_sharpe():
    start = timestamp("2024-01-01T00:00:00Z")
    rows = [
        dict(time_ns=start + DAY - 1, equity="9000"),
        dict(time_ns=start + 2 * DAY - 1, equity="9900"),
    ]
    result = portfolio_metrics(rows, D(10000), start, start + 2 * DAY)
    assert result["net_return"] == pytest.approx(-0.01)
    assert result["max_drawdown"] == pytest.approx(-0.1)
    assert result["annual_volatility"] == pytest.approx(math.sqrt(0.02) * math.sqrt(365))
    flat = portfolio_metrics(
        [dict(time_ns=start + DAY - 1, equity="10000")], D(10000), start, start + DAY
    )
    assert flat["sharpe"] is None and flat["sharpe_reason"]
    bankrupt = portfolio_metrics(
        [dict(time_ns=start + DAY - 1, equity="-100")], D(10000), start, start + DAY
    )
    assert bankrupt["net_return"] == pytest.approx(-1.01)
    assert bankrupt["cagr"] is None


def test_h1_target_excludes_funding_at_signal_and_incomplete_horizons():
    start = timestamp("2024-01-01T00:00:00Z")
    c = Config(start="2024-01-01T00:00:00Z", end="2024-01-02T00:00:00Z", horizon_hours=2)
    funding = [
        Funding(
            "BTCUSDT",
            start + h * HOUR,
            start + h * HOUR + 60 * SECOND,
            D(".001"),
            D(1),
            D(100),
            "synthetic",
            True,
        )
        for h in range(0, 6)
    ]
    signals = [
        dict(
            symbol="BTCUSDT",
            time_ns=start,
            anchor=start,
            history_start=start - 336 * HOUR,
            forecast=".002",
            no_change=".003",
            valid=True,
        ),
        dict(
            symbol="BTCUSDT",
            time_ns=start + 23 * HOUR,
            anchor=start + 23 * HOUR,
            history_start=start,
            forecast=".002",
            no_change=".003",
            valid=True,
        ),
    ]
    result = forecast_evaluation(signals, funding, c)
    assert result.iloc[0]["realized"] == pytest.approx(0.002)
    assert result.iloc[0]["absolute_error_ewma"] == 0
    assert not result.iloc[1]["horizon_valid"]

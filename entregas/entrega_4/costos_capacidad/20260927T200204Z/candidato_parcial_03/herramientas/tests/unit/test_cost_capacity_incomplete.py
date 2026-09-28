from decimal import Decimal as D

from crypto_carry.config import DAY, Config, timestamp
from scripts.verify_rules_sensitivity_package import COMPONENTS, SPLIT_COMPONENTS


def test_interrupted_period_preserves_observed_balance_and_nd_without_extra_days():
    from scripts.cost_capacity_incomplete import observed_financial_periods

    config = Config(start="2022-01-01T00:00:00Z", end="2022-01-04T00:00:00Z")
    start = timestamp(config.start)
    row = dict(time_ns=start+DAY//2, partial_day=True, equity_usdt=D(-1),
               starting_equity_usdt=D(10000), net_pnl_usdt=D(-10001),
               reconciliation_residual_usdt=D(0))
    row.update(dict.fromkeys((*COMPONENTS, *SPLIT_COMPONENTS), D(0)))
    row["spot_pnl_usdt"] = D(-10001)
    result = observed_financial_periods([row], [("full", start, start+3*DAY)])
    metric = result[0]
    assert not metric["coverage_complete"]
    assert metric["observed_end_exclusive_utc"] == "2022-01-01T12:00:00.000000001Z"
    assert metric["final_equity_usdt"] == -1
    assert metric["net_pnl_usdt"] == -10001
    assert metric["cagr"] is None and metric["sharpe"] is None
    assert metric["days"] == 0 and metric["observed_snapshots"] == 1


def test_missing_period_has_no_fabricated_balance_or_zero_return():
    from scripts.cost_capacity_incomplete import observed_financial_periods

    result = observed_financial_periods([], [("full", 0, DAY)])[0]
    assert result["starting_equity_usdt"] is None
    assert result["final_equity_usdt"] is None
    assert result["net_return"] is None

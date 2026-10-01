"""End-to-end postprocessing fixtures; none represent missing historical data."""

import numpy as np
import pytest

from scripts.build_intraday_risk import value_grid
from scripts.intraday_risk_sources import account_history, observation_grid


def test_complete_reconstruction_keeps_spot_risk_after_future_close():
    ledger = [dict(time_ns=10, event_id="open", kind="fill", symbol="BTCUSDT",
                   free_spot="50", free_futures="0", debt="0", spot="1", short="1",
                   average="100", collateral="50"),
              dict(time_ns=20, event_id="close", kind="fill", symbol="BTCUSDT",
                   free_spot="100", free_futures="0", debt="0", spot="1", short="0",
                   average="0", collateral="0")]
    history = account_history(ledger, 200)
    grid = observation_grid(0, 31, history, daily_times=[29], step_ns=10)
    prices = {}
    for symbol in ("BTCUSDT", "ETHUSDT"):
        for label in ("spot", "mark", "futures"):
            prices[symbol, label] = dict(available_at=np.array([0, 10, 20, 30]),
                open_time=np.array([-10, 0, 10, 20]), end_time=np.array([0, 10, 20, 30]),
                close_time=np.array([-1, 9, 19, 29]), close=np.array([100., 100., 100., 80.]),
                base_volume=np.ones(4), source_id=np.ones(4, int), estimated=np.zeros(4, int))
    tiers = {s: [dict(floor=0, cap=1e8, rate=.01, deduction=0)] for s in ("BTCUSDT", "ETHUSDT")}
    out = value_grid(history, grid, prices, tiers)
    assert out["equity_usdt"][-1] == pytest.approx(180)
    assert out["BTCUSDT_maintenance_usdt"][-1] == 0
    assert np.isnan(out["BTCUSDT_margin_ratio"][-1])
    assert out["BTCUSDT_net_exposure_usdt"][-1] == 80
    assert out["BTCUSDT_asset_pnl_usdt"][-1] == pytest.approx(-20)
    assert out["equity_usdt"][np.flatnonzero(out["time_ns"] == 29)[0]] == 200


def test_equity_does_not_double_count_funding_or_charge_slippage_again():
    ledger = [dict(time_ns=1, event_id="open", kind="fill", symbol="ETHUSDT",
                   free_spot="49", free_futures="0", debt="0", spot="1", short="1",
                   average="100", collateral="50", fee="1", slippage="0.5"),
              dict(time_ns=2, event_id="fund", kind="funding", symbol="ETHUSDT",
                   free_spot="49", free_futures="3", debt="0", spot="1", short="1",
                   average="100", collateral="50", amount_usdt="3")]
    h = account_history(ledger, 200)
    g = observation_grid(0, 3, h, daily_times=[], step_ns=1)
    source = dict(available_at=np.array([0]), open_time=np.array([-1]),
                  end_time=np.array([0]), close=np.array([100.]), base_volume=np.array([1.]))
    p = {(s, label): source for s in ("BTCUSDT", "ETHUSDT") for label in ("spot", "mark", "futures")}
    tiers = {s: [dict(floor=0, cap=1e8, rate=.01, deduction=0)] for s in ("BTCUSDT", "ETHUSDT")}
    out = value_grid(h, g, p, tiers)
    assert out["equity_usdt"][-1] == 202
    assert out["ETHUSDT_asset_pnl_usdt"][-1] == 2


def test_outstanding_debt_is_not_redistributable_collateral_cash(monkeypatch, tmp_path):
    from scripts import intraday_risk_reservations
    from scripts.build_intraday_risk import add_liquidity

    def reservation_source(path, times, phases):
        assert path == tmp_path
        return dict(reserved_cash=np.array([10.]), available_known=np.array([True]),
                    pending_orders_count=np.array([1]), reason=np.array(["verified"]))

    monkeypatch.setattr(intraday_risk_reservations, "reservation_grid", reservation_source)
    values = dict(time_ns=np.array([1]), phase=np.array([0]), free_cash_usdt=np.array([100.]),
                  debt_usdt=np.array([70.]), maintenance_need_joint_usdt=np.array([60.]),
                  preventive_need_joint_infimum_usdt=np.array([60.]))
    add_liquidity(values, dict(path=tmp_path))
    assert values["redistributable_cash_usdt"].tolist() == [20.]
    assert values["maintenance_external_deficit_usdt"].tolist() == [40.]

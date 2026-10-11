"""Persisted commitments must never become spendable cash by omission."""

from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest


def run_fixture(tmp_path, *, signals=(), renewals=(), orders=(), fills=(), risks=(), ledger=(), positions=()):
    (tmp_path / "effective_config.toml").write_text(
        'symbols = ["BTCUSDT", "ETHUSDT"]\ncapital = "100"\naccounting_tolerance = "1E-8"\n',
        encoding="utf-8",
    )
    for name, rows in (
        ("signals", signals), ("renewal_diagnostics", renewals), ("orders", orders),
        ("fills", fills), ("risk_events", risks), ("ledger", ledger), ("positions", positions),
    ):
        pq.write_table(pa.Table.from_pylist(list(rows)), tmp_path / f"{name}.parquet")
    return tmp_path


def signal(t, symbol="BTCUSDT", *, budget="60", available="100", decision="accepted"):
    return dict(time_ns=t, symbol=symbol, decision=decision, available_cash=available,
                budget_required_cash=budget, sizing_feasible="True")


def order(t, *, order_id="o1", symbol="BTCUSDT", status="pending", action="submitted",
          purpose="open_spot", cancel=None, record_type="event"):
    return dict(time_ns=t, symbol=symbol, order_id=order_id, status=status, action=action,
                purpose=purpose, cancel_requested_at=cancel, record_type=record_type,
                quantity="1", market="spot", side="BUY")


def fill(t, *, purpose="open_spot", partial=False, order_id="o1", symbol="BTCUSDT"):
    return dict(time_ns=t, symbol=symbol, purpose=purpose, partial=partial, order_id=order_id,
                quantity="1", remaining_quantity="1" if partial else "0")


def cash(t, value):
    return dict(time_ns=t, free_spot=str(value), free_futures="0", debt="0")


def load_module():
    # This assertion produces a deliberate RED before implementation exists.
    module_path = Path(__file__).parents[1] / "scripts" / "intraday_risk_reservations.py"
    assert module_path.exists(), "reservation_grid implementation does not exist yet"
    from scripts.intraday_risk_reservations import reservation_grid
    return reservation_grid


def test_shared_cash_deducts_both_commitments_and_inherits_pre_state(tmp_path):
    """Dropping one symbol's reservation would incorrectly expose 60 extra cash."""
    run = run_fixture(
        tmp_path,
        signals=[signal(10, budget="60"), signal(10, "ETHUSDT", budget="30", available="40")],
        orders=[order(10), order(10, order_id="o2", symbol="ETHUSDT")],
    )
    result = load_module()(run, np.array([9, 10, 10, 11]), phases=["post", "pre", "post", "post"])
    assert result["reserved_cash"].tolist() == [0, 0, 90, 90]
    assert result["cash_available_lower"].tolist() == [100, 100, 10, 10]
    assert result["pending_orders_count"].tolist() == [0, 0, 2, 2]
    assert result["available_known"].tolist() == [True, True, True, True]


def test_partial_fill_keeps_commitment_full_spot_without_close_makes_bounds(tmp_path):
    """Partial executions cannot release capital; unknown close cannot be a VWAP."""
    run = run_fixture(
        tmp_path,
        signals=[signal(10)],
        orders=[order(10), order(20, action="partial_fill"), order(30, status="filled", action="filled")],
        fills=[fill(20, partial=True), fill(30)], ledger=[cash(20, 90), cash(30, 80)],
    )
    result = load_module()(run, np.array([20, 30, 31]))
    assert result["reserved_cash"][0] == 60
    assert np.isnan(result["reserved_cash"][1:]).all()
    assert result["reserved_cash_lower"].tolist() == [60, 0, 0]
    assert result["reserved_cash_upper"].tolist() == [60, 60, 60]
    assert result["cash_available_lower"].tolist() == [30, 20, 20]
    assert result["cash_available_upper"].tolist() == [30, 80, 80]
    assert result["available_known"].tolist() == [True, False, False]


def test_verified_price_at_fill_reduces_reservation_and_completion_releases(tmp_path):
    """A corroborated close is usable; end-of-cycle evidence clears commitments."""
    run = run_fixture(
        tmp_path, signals=[signal(10)],
        orders=[order(10), order(20, status="filled", action="filled")],
        fills=[fill(20)], positions=[dict(time_ns=20, symbol="BTCUSDT", spot_price="25")],
        risks=[dict(time_ns=30, symbol="BTCUSDT", kind="transition", cause="opening_complete")],
    )
    result = load_module()(run, np.array([20, 29, 30]))
    assert result["reserved_cash"].tolist() == [35, 35, 0]


def test_deferred_cancellation_does_not_release_committed_interval(tmp_path):
    """A cancellation request can still lead to a fill, and does not run after_fill."""
    run = run_fixture(
        tmp_path, signals=[signal(10)],
        orders=[order(10), order(15, action="deferred_cancel:risk", cancel=15),
                order(20, status="filled", action="filled", cancel=15)],
        fills=[fill(20)],
        risks=[dict(time_ns=30, symbol="BTCUSDT", kind="transition", cause="unwind_complete")],
    )
    result = load_module()(run, np.array([15, 20, 30]))
    assert result["reserved_cash"].tolist() == [60, 60, 0]
    assert result["pending_orders_count"].tolist() == [1, 0, 0]


def test_available_cash_diagnostic_resolves_other_assets_unknown_commitment(tmp_path):
    """Stored cash for ETH identifies BTC's reservation without using future prices."""
    run = run_fixture(
        tmp_path, signals=[signal(10), signal(25, "ETHUSDT", decision="state_or_cooldown", available="55")],
        orders=[order(10), order(20, status="filled", action="filled")],
        fills=[fill(20)], ledger=[cash(20, 80)],
    )
    result = load_module()(run, np.array([24, 25, 26]))
    assert np.isnan(result["reserved_cash"][0])
    assert result["reserved_cash"][1:].tolist() == [25, 25]
    assert result["cash_available_lower"][1:].tolist() == [55, 55]


def test_inconsistent_available_cash_diagnostic_is_rejected(tmp_path):
    """A corrupted diagnostic must not silently rewrite an already known reserve."""
    run = run_fixture(tmp_path, signals=[signal(10), signal(11, "ETHUSDT", decision="blocked", available="70")],
                      orders=[order(10)])
    with pytest.raises(ValueError, match="available_cash"):
        load_module()(run, np.array([20]))


def test_intermediate_phase_does_not_invent_cross_table_event_order(tmp_path):
    """End-of-timestamp release is not proof that an earlier same-time state was free."""
    run = run_fixture(
        tmp_path, signals=[signal(10)], orders=[order(10)],
        risks=[dict(time_ns=20, symbol="BTCUSDT", kind="transition", cause="unwind_complete")],
    )
    result = load_module()(run, np.array([20, 20, 20]), phases=["pre", "intermediate", "post"])
    assert result["reserved_cash"][0] == 60
    assert np.isnan(result["reserved_cash"][1])
    assert result["reserved_cash_lower"][1] == 0
    assert result["reserved_cash_upper"][1] == 60
    assert result["reserved_cash"][2] == 0
    assert result["reason"][1] == "ambiguous_simultaneous_phase"


def test_rejected_signals_final_order_copies_and_orphan_orders_are_not_spendable(tmp_path):
    """Final order copies cannot create orders; unlinked opening orders are uncertain."""
    run = run_fixture(tmp_path, signals=[signal(5, decision="funding_not_above_cost")],
                      orders=[order(10), order(20, record_type="final", status="filled")])
    result = load_module()(run, np.array([9, 10, 20]))
    assert result["reserved_cash"][0] == 0
    assert result["available_known"].tolist() == [True, False, False]
    assert result["cash_available_lower"].tolist() == [100, 0, 0]
    assert result["pending_orders_count"].tolist() == [0, 1, 1]


@pytest.mark.parametrize("side,purpose", [("BUY", "close_perp"), ("SELL", "correct")])
def test_unpriced_futures_commitments_have_no_invented_finite_liability_cap(tmp_path, side, purpose):
    """Closing losses and corrective short opening can consume all free cash."""
    pending = order(10, purpose=purpose)
    pending.update(market="futures", side=side)
    run = run_fixture(tmp_path, orders=[pending])
    result = load_module()(run, np.array([9, 10]))
    assert result["available_known"].tolist() == [True, False]
    assert np.isinf(result["reserved_cash_upper"][1])
    assert result["cash_available_lower"].tolist() == [100, 0]
    assert result["cash_available_upper"].tolist() == [100, 100]


def test_renewal_assigns_only_when_event_confirms_adjustment_and_debt_is_not_free(tmp_path):
    """A stale REBALANCING diagnostic alone cannot create a second reservation."""
    renewal = dict(time_ns=10, symbol="BTCUSDT", state_after="REBALANCING",
                   available_cash="100", budget_required_cash="40", sizing_feasible="True")
    run = run_fixture(
        tmp_path, renewals=[renewal, dict(renewal, time_ns=15, budget_required_cash="70")],
        risks=[dict(time_ns=10, symbol="BTCUSDT", kind="transition", cause="renewal_rebalance")],
        orders=[order(10, purpose="increase_spot")],
        ledger=[dict(time_ns=20, free_spot="30", free_futures="0", debt="10")],
    )
    result = load_module()(run, np.array([10, 15, 20]))
    assert result["reserved_cash"].tolist() == [40, 40, 40]
    assert result["cash_available_upper"].tolist() == [60, 60, 0]

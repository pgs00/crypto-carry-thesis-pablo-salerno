"""Small synthetic contracts, never historical results."""

from decimal import Decimal as D

import pytest

from scripts.return_capital.accounting import Account, components, cycle_catalog, segment_changes
from scripts.return_capital.concentration import concentration


def test_attribution_rejects_ambiguous_same_asset_fill_at_entry(monkeypatch, tmp_path):
    from scripts.return_capital import attribution

    entry = dict(symbol="BTCUSDT", cycle_id="A", kind="transition", cause="entry", time_ns=1)
    fill = movement("spot_buy", time_ns=1, quantity="1", price="100", fee="1")
    sources = {"risk_events.parquet": [entry], "ledger.parquet": [fill]}
    monkeypatch.setattr(attribution, "parquet", lambda path: sources.get(path.name, []))
    monkeypatch.setattr(
        attribution, "read_csv", lambda _: [dict(run_id="test", strategy="conditional")]
    )
    monkeypatch.setattr(
        attribution, "account_history", lambda *_: pytest.fail("Ambiguous entry reached accounting")
    )
    with pytest.raises(ValueError, match="Simultaneous economic movement at cycle entry"):
        attribution.analyze_run(tmp_path, [], [("test", 0, 10)], [])


def test_entry_guard_allows_other_asset_and_zero_funding():
    from scripts.return_capital.accounting import validate_entry_timing

    cycles = [dict(symbol="BTCUSDT", cycle_id="A", entry_ns=1)]
    validate_entry_timing(
        cycles,
        [
            dict(symbol="ETHUSDT", kind="spot_buy", time_ns=1, fee="1"),
            movement("funding", time_ns=1, funding="0"),
            movement("transfer", time_ns=1, amount_usdt="100"),
        ],
    )


def movement(kind, **kwargs):
    return dict(kind=kind, symbol="BTCUSDT", **kwargs)


def test_positive_negative_denominators_are_not_clipped():
    rows = [dict(identity=str(n), net_pnl_usdt=D(v)) for n, v in enumerate((100, 50, -80))]
    result = concentration(rows, (1, 3, 5))
    top = next(r for r in result if r["sign"] == "positive" and r["requested_k"] == 1)
    assert top["G_usdt"] == 150 and top["L_usdt"] == 80 and top["net_usdt"] == 70
    assert top["share_sign"] == D(100) / 150
    assert top["share_net"] == D(100) / 70 > 1
    assert next(r for r in result if r["sign"] == "negative")["effective_k"] == 1
    assert concentration([], (1,))[0]["share_sign"] is None


def test_cross_year_changes_and_dust_are_not_assigned_to_closing_year():
    points = [
        dict(time_ns=0, category_after="cycle", cycle_after="A", values={"net_pnl_usdt": D(0)}),
        dict(time_ns=10, category_after="cycle", cycle_after="A", values={"net_pnl_usdt": D(80)}),
        dict(
            time_ns=20,
            category_after="outside_dust",
            cycle_after="",
            values={"net_pnl_usdt": D(200)},
        ),
        dict(time_ns=30, category_after="cycle", cycle_after="B", values={"net_pnl_usdt": D(205)}),
        dict(time_ns=40, category_after="cycle", cycle_after="B", values={"net_pnl_usdt": D(215)}),
    ]
    rows = segment_changes(points)
    assert [r["net_pnl_usdt"] for r in rows] == [80, 120, 5, 10]
    assert [r["cycle_id"] for r in rows] == ["A", "A", "", "B"]
    assert sum(r["net_pnl_usdt"] for r in rows) == 215


def test_net_spot_cost_fee_dust_and_transfer_accounting():
    a = Account()
    a.apply(
        movement("spot_buy", quantity="10", price="100", base_fee_quantity="1", fee="100", pnl="0")
    )
    assert a.spot == 9 and a.spot_cost == 900 and a.fees == 100
    a.apply(movement("spot_sell", quantity="8", price="110", fee="8.8", pnl="80"))
    before = components(a, D(120), D(100))
    assert a.spot == 1 and a.spot_cost == 100
    assert before["spot_realized_pnl_usdt"] == 80
    assert before["spot_unrealized_pnl_usdt"] == 20
    assert before["net_pnl_usdt"] == D("-8.8")
    a.apply(movement("transfer", amount_usdt="3000"))
    assert components(a, D(120), D(100)) == before
    # An inherited unit is not bought a second time.
    a.apply(
        movement("spot_buy", quantity="1", price="120", base_fee_quantity="0", fee="0", pnl="0")
    )
    assert a.spot == 2 and a.spot_cost == 220
    assert components(a, D(120), D(100))["net_pnl_usdt"] == before["net_pnl_usdt"]


def test_simultaneous_funding_precedes_fill_and_partial_short_keeps_average():
    a = Account()
    a.apply(movement("futures_sell", quantity="2", price="100", fee="1", pnl="0"))
    a.apply(movement("funding", funding="2", short="2", fee="0", pnl="0"))
    a.apply(movement("futures_buy", quantity="1", price="110", fee="0.5", pnl="-10"))
    assert a.short == 1 and a.average == 100 and a.funding == 2
    c = components(a, D(100), D(120))
    assert c["futures_realized_pnl_usdt"] == -10
    assert c["futures_unrealized_pnl_usdt"] == -20
    assert c["net_pnl_usdt"] == D("-29.5")
    with pytest.raises(ValueError, match="funding.*position"):
        a.apply(movement("funding", funding="1", short="2", fee="0", pnl="0"))


def test_renewal_failed_attempt_and_open_final_cycle():
    events = [
        dict(
            symbol="BTCUSDT",
            time_ns=1,
            cycle_id="A",
            kind="transition",
            cause="entry",
            state="OPENING_SPOT",
        ),
        dict(
            symbol="BTCUSDT",
            time_ns=2,
            cycle_id="A",
            kind="transition",
            cause="opening_complete",
            state="HOLDING",
        ),
        dict(symbol="BTCUSDT", time_ns=3, cycle_id=None, kind="renewal", cause=None, state=None),
        dict(
            symbol="ETHUSDT",
            time_ns=4,
            cycle_id="B",
            kind="transition",
            cause="entry",
            state="OPENING_SPOT",
        ),
        dict(
            symbol="ETHUSDT",
            time_ns=5,
            cycle_id="B",
            kind="transition",
            cause="unwind_complete",
            state="COOLDOWN",
        ),
    ]
    cycles = cycle_catalog(events, 10)
    assert len(cycles) == 2
    assert cycles[0]["closed_ns"] is None and cycles[0]["still_open_at_end"]
    assert cycles[1]["failed"] and not cycles[1]["complete"]
    a = Account()
    a.apply(
        movement("spot_buy", quantity="1", price="100", base_fee_quantity="0.01", fee="1", pnl="0")
    )
    assert components(a, D(100), D(100))["net_pnl_usdt"] == -1
    # Open terminal inventory has no invented liquidation or commission.
    assert a.spot == D("0.99") and a.fees == 1


def test_nonfinite_missing_and_inconsistent_values_fail():
    a = Account()
    with pytest.raises(ValueError):
        a.apply(movement("spot_buy", quantity="1", price=None, base_fee_quantity="0", fee="0"))
    with pytest.raises(ValueError):
        a.apply(movement("spot_buy", quantity="NaN", price="1", base_fee_quantity="0", fee="0"))

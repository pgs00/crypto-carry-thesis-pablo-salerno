from dataclasses import replace
from decimal import Decimal as D

from conftest import prices, warmup

from crypto_carry.config import HOUR, SECOND, Config, iso
from crypto_carry.events import DataGap, event_key
from crypto_carry.models import Fill, Funding, State
from crypto_carry.strategy import Backtest


def run(start, rules, rows, seconds=200, enabled=True, **overrides):
    c = Config(start=iso(start), end=iso(start + seconds * SECOND), **overrides)
    return Backtest(c, rules, "conditional", enabled).run(sorted(rows, key=event_key))


def test_two_legs_strict_trade_gate_net_hedge_and_no_terminal_close(start, rules):
    b = run(start, rules, warmup(start) + prices(start, [0, 60, 61, 62, 63, 100], mark="100.3"))
    fills = [f for f in b.fills if f["symbol"] == "BTCUSDT"]
    assert [(f["market"], f["time_ns"] - start) for f in fills] == [
        ("spot", 61 * SECOND),
        ("futures", 63 * SECOND),
    ]
    assert D(fills[1]["quantity"]) <= b.ledger.positions["BTCUSDT"].spot
    assert b.pairs["BTCUSDT"].state == State.HOLDING
    assert b.ledger.reconcile(b.spot_prices(), b.mark_prices())["difference"] == 0
    assert all(f["time_ns"] < start + 200 * SECOND for f in b.fills)
    assert D(fills[0]["recent_volume_quantity"]) == D(".001")
    assert D(fills[0]["participation"]) == D(fills[0]["quantity"]) / D(".001")


def test_second_leg_timeout_unwinds_with_costs_and_starts_cooldown_after_exit(start, rules):
    rows = warmup(start) + prices(start, [0, 60, 61], mark="100.3")
    rows += [r for r in prices(start, [93, 94], mark="100.3") if getattr(r, "market", "") == "spot"]
    b = run(start, rules, rows)
    assert b.ledger.positions["BTCUSDT"].short == 0
    assert b.pairs["BTCUSDT"].state == State.COOLDOWN
    assert b.ledger.positions["BTCUSDT"].fees > 0
    assert b.pairs["BTCUSDT"].cooldown_until == start + 93 * SECOND + 24 * HOUR


def test_funding_before_fill_and_duplicate_notice_charged_once(start, rules):
    fund = Funding(
        "BTCUSDT",
        start + 63 * SECOND,
        start + 123 * SECOND,
        D(".001"),
        D(".0175"),
        D("100"),
        "synthetic",
        True,
    )
    b = run(
        start,
        rules,
        warmup(start) + prices(start, [0, 60, 61, 62, 63, 64], mark="100.3") + [fund, fund],
    )
    assert b.ledger.positions["BTCUSDT"].funding == 0  # Short opens after funding at second 63.


def test_missing_data_stops_certification_without_erasing_open_exposure(start, rules):
    b = run(
        start,
        rules,
        warmup(start)
        + prices(start, [0, 60, 61, 62, 63], mark="100.3")
        + [DataGap("BTCUSDT", start + 90 * SECOND, "missing trade partition")],
    )
    assert b.status == "incomplete_data"
    assert b.stopped_at == start + 90 * SECOND
    assert b.ledger.positions["BTCUSDT"].short > 0


def test_equal_filter_disabled_instances_and_future_mutation_do_not_change_prefix(start, rules):
    rows = warmup(start, ".000001") + prices(start, [0, 60, 61, 62, 63, 100], mark="100.3")
    a = run(start, rules, rows, enabled=False)
    b = run(
        start,
        rules,
        rows + prices(start, [150], spot="500", future="600", mark="600"),
        enabled=False,
    )
    assert [r for r in a.fills if r["time_ns"] < start + 140 * SECOND] == [
        r for r in b.fills if r["time_ns"] < start + 140 * SECOND
    ]
    c = run(start, rules, rows, enabled=False)
    assert a.fills == c.fills and a.ledger.rows == c.ledger.rows
    assert a.ledger.positions is not c.ledger.positions


def test_renewal_uses_positive_forecast_below_entry_cost_and_has_no_fills(start, rules):
    rows = warmup(start, interval=1) + prices(
        start, [0, 60, 61, 62, 63, 3600, 3660, 3663], mark="100.3"
    )
    rows += prices(start, range(120, 3600, 60), mark="100.3")
    rows += [
        Funding(
            s,
            start + HOUR,
            start + HOUR + 60 * SECOND,
            D(".000001"),
            D(1),
            D("100.3"),
            "synthetic",
            True,
        )
        for s in Config().symbols
    ]
    b = run(start, rules, rows, seconds=3700, holding_hours=1, window_hours=1)
    assert len(b.fills) == 4
    assert b.forecasts["BTCUSDT"].value == D(".000168")
    assert b.pairs["BTCUSDT"].expiry == start + 63 * SECOND + 2 * HOUR
    assert b.pairs["BTCUSDT"].basis_reference == D(".003")


def test_rebalance_reduces_both_legs_and_updates_basis(start, rules):
    rows = warmup(start) + prices(start, [0, 60, 61, 62, 63], mark="100.3")
    rows += prices(start, range(120, 3600, 60), mark="100.3")
    rows += prices(start, [3600, 3663, 3664, 3665, 3666], spot="120", future="120.3", mark="120.3")
    b = run(start, rules, rows, seconds=3700, holding_hours=1)
    fills = [f for f in b.fills if f["symbol"] == "BTCUSDT"]
    assert [f["purpose"] for f in fills] == ["open_spot", "open_perp", "reduce_perp", "reduce_spot"]
    assert fills[-1]["time_ns"] == start + 3666 * SECOND
    assert b.ledger.positions["BTCUSDT"].spot < D(26)
    assert b.pairs["BTCUSDT"].basis_reference == D(".0025")


def test_risk_precedes_renewal_and_close_retry_keeps_funding_exposure(start, rules):
    rows = warmup(start) + prices(start, [0, 60, 61, 62, 63], mark="100.3")
    rows += prices(start, range(120, 3661, 60), mark="100.3")
    rows += prices(start, [3663], mark="140")
    rows += prices(start, [3694, 3695, 3696], mark="140")
    rows += [
        Funding(
            "BTCUSDT",
            start + 3680 * SECOND,
            start + 3740 * SECOND,
            D(".001"),
            D("1"),
            D("100"),
            "synthetic",
            True,
        )
    ]
    b = run(start, rules, rows, seconds=3710, holding_hours=1)
    assert not [e for e in b.risk_events if e["kind"] == "renewal"]
    assert b.ledger.positions["BTCUSDT"].funding > 0
    assert len([r for r in b.order_rows if r["action"] == "timeout"]) == 2
    assert b.ledger.positions["BTCUSDT"].short == 0


def test_chunk_boundaries_do_not_change_decisions_or_ledger(start, rules):
    rows = sorted(
        warmup(start) + prices(start, [0, 60, 61, 62, 63, 100], mark="100.3"), key=event_key
    )
    c = Config(start=iso(start), end=iso(start + 200 * SECOND))
    a = Backtest(c, rules).run(rows, chunk_size=3)
    b = Backtest(c, rules).run(rows, chunk_size=10000)
    assert a.fills == b.fills and a.ledger.rows == b.ledger.rows and a.daily == b.daily


def test_forecast_equal_to_cost_does_not_enter(start, rules):
    for symbol in Config().symbols:
        rules.items[(symbol, "futures")] = replace(
            rules.items[(symbol, "futures")], taker_fee=D(".00075")
        )
    rows = warmup(start, rate=".0005", interval=24) + prices(
        start, [0, 60, 61, 62, 63], mark="100.3"
    )
    b = run(start, rules, rows, slippage=D(0))
    assert b.forecasts["BTCUSDT"].value == D(".0035")
    assert b.signals[-1]["decision"] == "funding_not_above_cost"
    assert not b.fills


def test_actual_inactivity_keeps_pending_close_but_missing_file_halts(start, rules):
    rows = warmup(start) + prices(start, [0, 60, 61, 62, 63], mark="100.3")
    b = run(start, rules, rows, seconds=2000)
    assert b.status == "complete"
    assert b.pairs["BTCUSDT"].state == State.CLOSING_PERP
    assert b.ledger.positions["BTCUSDT"].short > 0
    assert any(r.get("cause") == "real_market_inactivity" for r in b.risk_events)


def test_liquidation_debt_insolvency_and_charges_survive_full_unwind(start, rules):
    rows = warmup(start) + prices(start, [0, 60, 61, 62, 63], mark="100.3")
    rows += prices(start, [120, 121, 122, 123], spot="100", future="500", mark="500")
    b = run(start, rules, rows)
    assert b.status == "insolvent"
    assert b.ledger.debt > 0 and b.equity() < 0
    assert all(p.short == 0 for p in b.ledger.positions.values())
    assert len([f for f in b.fills if f["liquidation"]]) == 2
    assert all(p.liquidation_fees > 0 for p in b.ledger.positions.values())


def seeded_hedge(start, rules, short):
    config = Config(start=iso(start), end=iso(start + 100 * SECOND), slippage=D(0))
    b = Backtest(config, rules)
    for market, side, q in (("spot", "BUY", D(30)), ("futures", "SELL", D(short))):
        fill = Fill(
            market, market, "BTCUSDT", market, side, q, D(100), D(100), start - SECOND, market, D(0)
        )
        assert b.ledger.apply_fill(fill, rules.get("BTCUSDT", market, start), D(100))
    for record in prices(start, [-1], mark="100.3"):
        if hasattr(record, "market"):
            b.trades[(record.symbol, record.market)] = record
        else:
            b.marks[record.symbol] = record
    b.pairs["BTCUSDT"].state = State.HOLDING
    b.pairs["BTCUSDT"].basis_reference = D(".003")
    b.pairs["BTCUSDT"].expiry = start + HOUR
    b.now = start - SECOND
    b.resuming = True
    return b


def test_hedge_trigger_strict_and_correction_changes_only_perpetual(start, rules):
    rows = sorted(prices(start, [0, 1, 2], mark="100.3"), key=event_key)
    exact = seeded_hedge(start, rules, "29.4").run(rows)
    assert not exact.fills
    corrected = seeded_hedge(start, rules, "29.399").run(rows)
    assert [(f["market"], f["purpose"], f["quantity"]) for f in corrected.fills] == [
        ("futures", "correct", "0.601")
    ]
    assert corrected.ledger.positions["BTCUSDT"].spot == 30
    assert corrected.ledger.positions["BTCUSDT"].short == 30
    assert corrected.pairs["BTCUSDT"].basis_reference == D(".003")


def test_correction_deadline_closes_if_no_hedge_trade_arrives(start, rules):
    rows = sorted(prices(start, [0], mark="100.3"), key=event_key)
    b = seeded_hedge(start, rules, "29.399").run(rows)
    assert any(e.get("cause") == "hedge_correction_deadline" for e in b.risk_events)
    assert b.pairs["BTCUSDT"].state == State.CLOSING_PERP
    assert b.ledger.positions["BTCUSDT"].short == D("29.399")


def test_opening_trade_must_recheck_other_market_freshness(start, rules):
    rows = warmup(start) + prices(start, [0], mark="100.3")
    rows += [
        r for r in prices(start, [60, 61, 62], mark="100.3") if getattr(r, "market", None) == "spot"
    ]
    rows += prices(start, [63], mark="100.3")
    b = run(start, rules, rows)
    assert not b.fills
    assert any(e.get("cause") == "stale_data_at_fill" for e in b.risk_events)


def test_suspension_retains_close_intent_and_retries_when_tradable(start, rules):
    class Suspended:
        def get(self, symbol, market, time_ns):
            rule = rules.get(symbol, market, time_ns)
            return (
                replace(rule, operational=False)
                if market == "futures" and start + 120 * SECOND <= time_ns < start + 180 * SECOND
                else rule
            )

    rows = warmup(start) + prices(start, [0, 60, 61, 62, 63, 120, 180, 181, 182, 183], mark="100.3")
    b = run(start, Suspended(), rows)
    assert all(p.short == 0 for p in b.ledger.positions.values())
    assert len([f for f in b.fills if f["purpose"] == "close_spot"]) == 2


def test_suspended_spot_inventory_is_not_mistaken_for_dust(start, rules):
    class Suspended:
        def get(self, symbol, market, time_ns):
            rule = rules.get(symbol, market, time_ns)
            return (
                replace(rule, operational=False)
                if market == "spot" and start + 120 * SECOND <= time_ns < start + 180 * SECOND
                else rule
            )

    rows = warmup(start) + prices(
        start, [0, 60, 61, 62, 63, 120, 121, 122, 123, 180, 181, 182, 183], mark="100.3"
    )
    b = run(start, Suspended(), rows)
    assert all(p.spot < D(".001") for p in b.ledger.positions.values())
    assert all(p.short == 0 for p in b.ledger.positions.values())
    assert all(p.cooldown_until >= start + 181 * SECOND + 24 * HOUR for p in b.pairs.values())


def test_failed_first_rebalance_leg_preserves_existing_pair(start, rules):
    rows = warmup(start) + prices(start, [0, 60, 61, 62, 63, *range(120, 3601, 60)], mark="100.3")
    rows += prices(start, [3603], spot="90", future="90.3", mark="90.3")
    rows += [
        r
        for r in prices(start, [3663, 3664], spot="90", future="90.3")
        if getattr(r, "market", None) == "spot"
    ]
    rows += prices(start, [3665, 3666, 3667, 3668], spot="90", future="90.3", mark="90.3")
    b = run(start, rules, rows, seconds=3700, holding_hours=1)
    assert len(b.fills) == 4
    assert all(p.state == State.HOLDING for p in b.pairs.values())
    assert all(p.cooldown_until == start + 3664 * SECOND + 24 * HOUR for p in b.pairs.values())


def test_debt_realizes_btc_first_and_preserves_eth_once_debt_is_paid(start, rules):
    rows = warmup(start) + prices(
        start, [0, 60, 61, 62, 63, 90, 91, 92, 93, 94, 95, 96], mark="100.3"
    )
    rows.append(
        Funding(
            "BTCUSDT",
            start + 90 * SECOND,
            start + 150 * SECOND,
            D(-1),
            D(".025"),
            D("100.3"),
            "synthetic",
            True,
        )
    )
    b = run(start, rules, rows)
    assert b.ledger.debt == 0
    assert b.ledger.positions["BTCUSDT"].short == 0
    assert b.ledger.positions["ETHUSDT"].short > 0
    assert not [f for f in b.fills if f["symbol"] == "ETHUSDT" and f["purpose"].startswith("close")]


def test_integral_native_replay_funding_renewal_close_retry_and_equity(start, rules):
    rows = warmup(start, interval=1) + prices(
        start, [0, 60, 61, 62, 63, *range(120, 7200, 60)], mark="100.3"
    )
    rows += prices(start, [7200, 7231, 7232, 7233], mark="140")
    rows += [
        Funding(
            s,
            start + HOUR,
            start + HOUR + 60 * SECOND,
            D(".000001"),
            D(1),
            D("100.3"),
            "synthetic",
            True,
        )
        for s in Config().symbols
    ]
    payment = Funding(
        "BTCUSDT",
        start + 7210 * SECOND,
        start + 7270 * SECOND,
        D(".001"),
        D("1"),
        D(100),
        "synthetic",
        True,
    )
    rows.extend([payment, replace(payment, source_file="duplicate-notice")])
    b = run(start, rules, rows, seconds=7280, holding_hours=1, window_hours=1)
    assert len([e for e in b.risk_events if e["kind"] == "renewal"]) == 2
    assert len([o for o in b.order_rows if o["action"] == "timeout"]) == 2
    assert b.native_fill_count == 8
    assert b.native_reconciliation_count == 8
    assert len(b.ledger.funding_rows) == 3
    assert all(p.short == 0 for p in b.ledger.positions.values())
    assert b.ledger.reconcile(b.spot_prices(), b.mark_prices())["difference"] == 0

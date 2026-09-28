"""Causal end-of-window fills, real inventories, and native/ledger agreement."""

from dataclasses import replace
from decimal import Decimal as D

from conftest import warmup

from crypto_carry import models
from crypto_carry.config import SECOND, Config, iso
from crypto_carry.events import event_key
from crypto_carry.models import Fill, Funding, Mark, State
from crypto_carry.strategy import Backtest


def config(start, seconds=600, **changes):
    return Config(
        start=iso(start),
        end=iso(start + seconds * SECOND),
        analysis_mode="prescribed_research",
        fee_profile="prescribed_fixed_no_discounts",
        execution_model="next_minute_vwap",
    ).changed(**changes)


def bars(start, ends=range(0, 601, 60), base="100000"):
    assert hasattr(models, "MinuteBar")
    rows = []
    for second in ends:
        end = start + second * SECOND
        for symbol in Config().symbols:
            for market, price in (("spot", D(100)), ("futures", D("100.3"))):
                rows.append(
                    models.MinuteBar(
                        symbol,
                        market,
                        end - 60 * SECOND,
                        end,
                        end,
                        price,
                        price,
                        price,
                        price,
                        D(base),
                        D(base) * price,
                        100 if D(base) else 0,
                        "synthetic:closed-minute",
                    )
                )
            rows.append(
                Mark(
                    symbol,
                    end - 60 * SECOND,
                    end - 1,
                    end,
                    D("100.3"),
                    D("100.3"),
                    D("100.3"),
                    D("100.3"),
                )
            )
    return rows


def run(start, rules, rows, **changes):
    return Backtest(config(start, **changes), rules).run(
        sorted(warmup(start) + rows, key=event_key)
    )


def test_vwap_legs_fill_at_successive_window_ends_and_reconcile(start, rules):
    result = run(start, rules, bars(start))
    fills = [f for f in result.fills if f["symbol"] == "BTCUSDT"]
    assert [(f["market"], f["time_ns"] - start) for f in fills] == [
        ("spot", 120 * SECOND),
        ("futures", 180 * SECOND),
    ]
    assert D(fills[0]["price"]) == D("100.01")
    assert D(fills[1]["price"]) == D("100.28")
    assert fills[0]["window_start"] == start + 60 * SECOND
    assert fills[0]["window_end"] == fills[0]["time_ns"]
    assert result.pairs["BTCUSDT"].opened_at == start + 180 * SECOND
    assert result.native_fill_count == len(result.fills)
    assert result.ledger.reconcile(result.spot_prices(), result.mark_prices())["difference"] == 0


def test_partial_first_leg_expires_then_unwinds_only_received_inventory(start, rules):
    rows = bars(start)
    rows = [
        replace(r, base_volume=D(10), quote_volume=D(1000))
        if isinstance(r, models.MinuteBar)
        and r.symbol == "BTCUSDT"
        and r.market == "spot"
        and r.end_time == start + 120 * SECOND
        else r
        for r in rows
    ]
    result = run(start, rules, rows)
    fills = [f for f in result.fills if f["symbol"] == "BTCUSDT"]
    assert fills[0]["purpose"] == "open_spot"
    assert D(fills[0]["quantity"]) == D(".10")
    assert fills[0]["partial"] is True
    assert all(f["market"] == "spot" for f in fills)
    assert sum(D(f["quantity"]) for f in fills if f["side"] == "SELL") <= D(".0999")
    assert any(
        o["status"] == "expired" and D(o["remaining_quantity"]) > 0
        for o in result.order_rows
        if o["purpose"] == "open_spot" and o["symbol"] == "BTCUSDT"
    )
    assert result.pairs["BTCUSDT"].state == State.COOLDOWN
    assert result.ledger.reconcile(result.spot_prices(), result.mark_prices())["difference"] == 0


def test_partial_second_leg_unwinds_actual_short_and_spot(start, rules):
    rows = [
        replace(r, base_volume=D(10), quote_volume=D(1003))
        if isinstance(r, models.MinuteBar)
        and r.symbol == "BTCUSDT"
        and r.market == "futures"
        and r.end_time == start + 180 * SECOND
        else r
        for r in bars(start)
    ]
    result = run(start, rules, rows)
    futures = [f for f in result.fills if f["symbol"] == "BTCUSDT" and f["market"] == "futures"]
    assert [(f["side"], D(f["quantity"])) for f in futures] == [
        ("SELL", D(".10")),
        ("BUY", D(".10")),
    ]
    assert result.ledger.positions["BTCUSDT"].short == 0
    assert result.pairs["BTCUSDT"].state == State.COOLDOWN
    assert result.native_fill_count == len(result.fills)


def test_zero_volume_consumes_window_without_fee_or_hedge(start, rules):
    rows = [
        replace(r, base_volume=D(0), quote_volume=D(0), trade_count=0)
        if isinstance(r, models.MinuteBar)
        and r.symbol == "BTCUSDT"
        and r.market == "spot"
        and r.end_time == start + 120 * SECOND
        else r
        for r in bars(start)
    ]
    result = run(start, rules, rows)
    assert not [f for f in result.fills if f["symbol"] == "BTCUSDT"]
    assert result.ledger.positions["BTCUSDT"].fees == 0


def test_missing_execution_bar_is_coverage_failure_not_zero_volume(start, rules):
    rows = [
        r
        for r in bars(start)
        if not (
            isinstance(r, models.MinuteBar)
            and r.symbol == "BTCUSDT"
            and r.market == "spot"
            and r.end_time == start + 120 * SECOND
        )
    ]
    result = run(start, rules, rows)
    assert result.status == "incomplete_data"
    assert any("Missing" in r and "minute" in r for r in result.reasons)


def test_missing_mark_at_execution_boundary_is_explicit_coverage_failure(start, rules):
    rows = [
        row
        for row in bars(start)
        if not (
            isinstance(row, Mark)
            and row.symbol == "BTCUSDT"
            and row.available_at == start + 120 * SECOND
        )
    ]

    result = run(start, rules, rows)

    assert result.status == "incomplete_data"
    assert any("Missing" in reason and "mark" in reason for reason in result.reasons)


def test_funding_precedes_fill_at_the_same_timestamp(start, rules):
    rows = bars(start)
    for second in (180, 240):
        rows.append(
            Funding(
                "BTCUSDT",
                start + second * SECOND,
                start + (second + 60) * SECOND,
                D(".001"),
                D(8),
                D("100.3"),
                "synthetic",
                True,
            )
        )
    result = run(start, rules, rows)
    payments = result.ledger.funding_rows
    assert len(payments) == 1
    assert payments[0]["time_ns"] == start + 240 * SECOND
    assert result.ledger.positions["BTCUSDT"].funding == D("29.970") * D("100.3") * D(".001")


def test_future_window_change_cannot_change_prior_orders_or_balances(start, rules):
    original = bars(start)
    changed = [
        replace(r, quote_volume=r.quote_volume * D("1.001"), high=r.high * D("1.001"))
        if isinstance(r, models.MinuteBar) and r.end_time >= start + 180 * SECOND
        else r
        for r in original
    ]
    before, after = run(start, rules, original), run(start, rules, changed)
    cutoff = start + 120 * SECOND
    for field in ("signals", "order_rows", "fills"):
        assert [r for r in getattr(before, field) if r["time_ns"] <= cutoff] == [
            r for r in getattr(after, field) if r["time_ns"] <= cutoff
        ]
    assert [r for r in before.ledger.rows if r["time_ns"] <= cutoff] == [
        r for r in after.ledger.rows if r["time_ns"] <= cutoff
    ]


def test_exclusive_end_does_not_fill_pending_window(start, rules):
    result = run(start, rules, bars(start), seconds=180)
    assert all(f["time_ns"] < start + 180 * SECOND for f in result.fills)
    assert result.ledger.positions["BTCUSDT"].short == 0
    assert any(o.status == "pending" for o in result.orders.values())


def test_partitioned_and_checkpoint_replay_match_continuous(start, rules, tmp_path):
    cfg = config(start)
    rows = sorted(warmup(start) + bars(start), key=event_key)
    whole = Backtest(cfg, rules).run(rows)
    partitioned = Backtest(cfg, rules).run(rows, chunk_size=2)
    partial = Backtest(cfg, rules).run(rows, stop_at=start + 120 * SECOND)
    checkpoint = tmp_path / "window.json"
    partial.checkpoint(checkpoint)
    restored = Backtest.load_checkpoint(checkpoint, cfg, rules).run(rows)
    for result in (partitioned, restored):
        assert result.fills == whole.fills
        assert result.orders == whole.orders
        assert result.ledger.rows == whole.ledger.rows
        assert result.daily == whole.daily


def test_joint_sizing_prevents_rounding_failure_before_spot_purchase(start, rules):
    # Synthetic steps reproduce the documented BTC failure independently of history.
    sr = rules.items[("BTCUSDT", "spot")]
    fr = rules.items[("BTCUSDT", "futures")]
    rules.items[("BTCUSDT", "spot")] = replace(sr, step=D(".00001"), min_qty=D(".00001"))
    rules.items[("BTCUSDT", "futures")] = replace(fr, step=D(".001"))
    price = D(3000) / D(".03929")
    rows = []
    for row in bars(start):
        if row.symbol == "BTCUSDT":
            p = price * (D("1.003") if getattr(row, "market", "futures") == "futures" else D(1))
            if isinstance(row, models.MinuteBar):
                row = replace(row, open=p, high=p, low=p, close=p, quote_volume=row.base_volume * p)
            else:
                row = replace(row, open=p, high=p, low=p, close=p)
        rows.append(row)
    result = run(start, rules, rows, sizing_model="joint_quantity")
    fills = [f for f in result.fills if f["symbol"] == "BTCUSDT"]
    assert len(fills) == 2
    assert D(fills[0]["quantity"]) == D(".03904")
    assert D(fills[1]["quantity"]) == D(".039")
    assert result.ledger.positions["BTCUSDT"].spot == D(".03900096")
    assert result.pairs["BTCUSDT"].state == State.HOLDING


def test_joint_sizing_rejects_impossible_minimum_before_any_cost(start, rules):
    rules.items[("BTCUSDT", "futures")] = replace(
        rules.items[("BTCUSDT", "futures")], min_notional=D("1000000")
    )
    result = run(start, rules, bars(start), sizing_model="joint_quantity")
    assert not [f for f in result.fills if f["symbol"] == "BTCUSDT"]
    assert result.ledger.positions["BTCUSDT"].fees == 0


def test_risk_observed_at_window_end_does_not_erase_committed_fill(start, rules):
    # The spot window is already over when the simultaneous mark shock is seen.
    rows = [
        replace(r, open=D(131), high=D(131), low=D(131), close=D(131))
        if isinstance(r, Mark) and r.symbol == "BTCUSDT" and r.available_at >= start + 240 * SECOND
        else r
        for r in bars(start)
    ]
    result = run(start, rules, rows)
    fills = [f for f in result.fills if f["symbol"] == "BTCUSDT"]
    assert [f["purpose"] for f in fills[:2]] == ["open_spot", "open_perp"]
    assert any(
        e["kind"] == "close_requested" for e in result.risk_events if e["symbol"] == "BTCUSDT"
    )
    assert all(
        f["time_ns"] >= start + 300 * SECOND for f in fills if f["purpose"].startswith("close")
    )


def test_cancellation_inside_committed_window_fills_then_unwinds_inventory(start, rules):
    cancel_at = start + 90 * SECOND

    class CancelInsideWindow(Backtest):
        def process(self, time_ns, records, native):
            super().process(time_ns, records, native)
            if time_ns == cancel_at:
                self._cancel("BTCUSDT", "risk_inside_committed_window")

    rows = bars(start)
    rows.append(
        Mark(
            "BTCUSDT",
            cancel_at - 60 * SECOND,
            cancel_at - 1,
            cancel_at,
            D("100.3"),
            D("100.3"),
            D("100.3"),
            D("100.3"),
        )
    )
    result = CancelInsideWindow(config(start), rules).run(
        sorted(warmup(start) + rows, key=event_key)
    )

    fills = [fill for fill in result.fills if fill["symbol"] == "BTCUSDT"]
    assert fills[0]["purpose"] == "open_spot"
    assert result.ledger.positions["BTCUSDT"].short == 0
    assert result.pairs["BTCUSDT"].state == State.COOLDOWN
    assert result._spot_is_dust("BTCUSDT")


def test_risk_close_inside_committed_window_fills_then_unwinds_inventory(start, rules):
    risk_at = start + 90 * SECOND

    class RiskInsideWindow(Backtest):
        def process(self, time_ns, records, native):
            super().process(time_ns, records, native)
            if time_ns == risk_at:
                self._close("BTCUSDT", "risk_inside_committed_window")

    rows = bars(start)
    rows.append(
        Mark(
            "BTCUSDT",
            risk_at - 60 * SECOND,
            risk_at - 1,
            risk_at,
            D("100.3"),
            D("100.3"),
            D("100.3"),
            D("100.3"),
        )
    )
    result = RiskInsideWindow(config(start), rules).run(sorted(warmup(start) + rows, key=event_key))

    fills = [fill for fill in result.fills if fill["symbol"] == "BTCUSDT"]
    assert [fill["purpose"] for fill in fills] == ["open_spot", "close_spot"]
    assert result.ledger.positions["BTCUSDT"].short == 0
    assert result.pairs["BTCUSDT"].state == State.COOLDOWN
    assert result._spot_is_dust("BTCUSDT")


def test_partial_closing_order_retries_only_the_actual_remainder(start, rules):
    rows = []
    for r in bars(start, range(0, 1201, 60)):
        if isinstance(r, Mark) and r.symbol == "BTCUSDT" and r.available_at >= start + 240 * SECOND:
            r = replace(r, open=D(131), high=D(131), low=D(131), close=D(131))
        if (
            isinstance(r, models.MinuteBar)
            and r.symbol == "BTCUSDT"
            and r.end_time >= start + 300 * SECOND
        ):
            r = replace(r, base_volume=D(1000), quote_volume=D(1000) * r.close)
        rows.append(r)
    result = run(start, rules, rows, seconds=1200)
    futures = [f for f in result.fills if f["symbol"] == "BTCUSDT" and f["market"] == "futures"]
    sold = sum(D(f["quantity"]) for f in futures if f["side"] == "SELL")
    bought = sum(D(f["quantity"]) for f in futures if f["side"] == "BUY")
    assert sold == bought == D("29.970")
    assert [D(f["quantity"]) for f in futures if f["side"] == "BUY"] == [D(10), D(10), D("9.970")]
    assert result.pairs["BTCUSDT"].state == State.COOLDOWN
    assert result.native_fill_count == len(result.fills)
    assert result.ledger.reconcile(result.spot_prices(), result.mark_prices())["difference"] == 0


def test_disabled_funding_filters_have_independent_identical_economics(start, rules):
    rows = sorted(warmup(start) + bars(start), key=event_key)
    first = Backtest(config(start, sizing_model="joint_quantity"), rules, "a", False).run(rows)
    second = Backtest(config(start, sizing_model="joint_quantity"), rules, "a", False).run(rows)
    assert first.fills and first.orders is not second.orders
    assert first.fills == second.fills
    assert first.ledger.rows == second.ledger.rows
    assert first.daily == second.daily
    first.pairs["BTCUSDT"].cooldown_until = 123
    assert second.pairs["BTCUSDT"].cooldown_until != 123


def test_partial_correction_that_reaches_tolerance_is_not_closed_at_expiry(start, rules):
    cfg = config(start, seconds=180)
    result = Backtest(cfg, rules)
    result.now = start - 1
    result.resuming = True
    result.pairs["BTCUSDT"].state = State.HOLDING
    for market, side, quantity in (("spot", "BUY", D(1)), ("futures", "SELL", D(".979"))):
        result.ledger.apply_fill(
            Fill(
                f"seed-{market}",
                f"seed-{market}",
                "BTCUSDT",
                market,
                side,
                quantity,
                D("100.3"),
                D("100.3"),
                start - 1,
                "synthetic",
                D(0),
            ),
            rules.items[("BTCUSDT", market)],
            D("100.3"),
        )
    # The pending correction requests .021; .017 is enough to meet 0.5%.
    rows = [
        replace(r, base_volume=D("1.7"), quote_volume=D("1.7") * r.close)
        if isinstance(r, models.MinuteBar)
        and r.market == "futures"
        and r.end_time == start + 60 * SECOND
        else r
        for r in bars(start, [0, 60, 120])
    ]
    result.run(sorted(rows, key=event_key))
    assert result.ledger.positions["BTCUSDT"].short == D(".996")
    assert result.pairs["BTCUSDT"].state == State.HOLDING
    assert not [e for e in result.risk_events if e["kind"] == "close_requested"]


def test_committed_close_fills_before_simultaneous_liquidation_observation(start, rules):
    rows = bars(start, range(0, 4201, 60))
    rows.append(
        Funding(
            "BTCUSDT",
            start + 3600 * SECOND,
            start + 3660 * SECOND,
            D("-.1"),
            D(1),
            D("100.3"),
            "synthetic",
            True,
        )
    )
    rows = [
        replace(r, open=D(300), high=D(300), low=D(300), close=D(300))
        if isinstance(r, Mark) and r.symbol == "BTCUSDT" and r.available_at >= start + 3840 * SECOND
        else r
        for r in rows
    ]
    result = run(start, rules, rows, seconds=4200, holding_hours=1)
    futures = [f for f in result.fills if f["symbol"] == "BTCUSDT" and f["market"] == "futures"]
    assert [(f["purpose"], f["time_ns"] - start) for f in futures] == [
        ("open_perp", 180 * SECOND),
        ("close_perp", 3840 * SECOND),
    ]
    assert result.ledger.positions["BTCUSDT"].short == 0
    assert result.ledger.positions["BTCUSDT"].liquidation_fees == 0

import json
from dataclasses import asdict
from decimal import Decimal as D

import pandas as pd
import pyarrow.parquet as pq
import pytest

from crypto_carry.config import DAY, HOUR, SECOND, Config, timestamp
from crypto_carry.models import Fill, Funding, Mark, Order, State, Trade
from crypto_carry.strategy import Backtest


def _backtest(rules):
    config = Config(start="2024-01-01T00:00:00Z", end="2024-01-04T00:00:00Z", horizon_hours=1)
    b = Backtest(config, rules)
    start = timestamp(config.start)
    for market, side, quantity, price, reference, offset in (
        ("spot", "BUY", "10", "100.01", "100", 1),
        ("futures", "SELL", "9.99", "100.3", "100.31", 2),
    ):
        rule = rules.get("BTCUSDT", market, start)
        fill = Fill(
            f"fill-{offset}",
            f"order-{offset}",
            "BTCUSDT",
            market,
            side,
            D(quantity),
            D(price),
            D(reference),
            start + offset * SECOND,
            f"trade-{offset}",
            rule.taker_fee,
        )
        assert b.ledger.apply_fill(fill, rule, D("100.3"))
        b.fills.append(
            dict(
                asdict(fill),
                strategy=b.strategy,
                participation="0.01",
                recent_volume_quantity="1000",
                purpose=f"open_{market}",
            )
        )
        order = Order(
            fill.order_id,
            fill.symbol,
            market,
            side,
            fill.quantity,
            start,
            start + 30 * SECOND,
            f"open_{market}",
            "filled",
        )
        b.orders[order.order_id] = order
        b.order_rows.append(
            dict(asdict(order), time_ns=fill.time_ns, strategy=b.strategy, action="filled")
        )
    funding = Funding(
        "BTCUSDT",
        start + HOUR,
        start + HOUR + 60 * SECOND,
        D(".001"),
        D(1),
        D("100.4"),
        "synthetic",
        True,
    )
    b.ledger.apply_funding(funding)
    b.all_funding = [
        Funding(
            symbol,
            start + h * HOUR,
            start + h * HOUR + 60 * SECOND,
            D(".001"),
            D(1),
            D("100.4"),
            "synthetic",
            True,
        )
        for symbol in config.symbols
        for h in range(5)
    ]
    b.signals = [
        {
            "time_ns": start + 60 * SECOND,
            "strategy": b.strategy,
            "symbol": symbol,
            "anchor": start,
            "history_start": start - 336 * HOUR,
            "forecast": D(".001"),
            "no_change": D(".002"),
            "valid": True,
            "decision": "fixture",
            "estimated_cycle_cost": D(".0034"),
            "basis": D(".003"),
        }
        for symbol in config.symbols
    ]
    b.pairs["BTCUSDT"].state = State.HOLDING
    for day, price in enumerate(("101", "103", "102"), 1):
        b.now = start + day * DAY - 1
        b.trades[("BTCUSDT", "spot")] = Trade(
            "BTCUSDT", "spot", str(day), b.now, b.now, D(price), D(1)
        )
        mark = D(price) + D(".3")
        b.marks["BTCUSDT"] = Mark(
            "BTCUSDT", b.now - 60 * SECOND, b.now, b.now, mark, mark, mark, mark
        )
        b._daily()
    b.durations.update(
        portfolio_invested_seconds=D(259199),
        cash_seconds=D(1),
        BTCUSDT_invested_seconds=D(259199),
        BTCUSDT_unhedged_seconds=D(1),
    )
    b.native_fill_count = 2
    b.native_reconciliation_count = 2
    b.risk_events = [
        {
            "time_ns": start + 2 * SECOND,
            "strategy": b.strategy,
            "symbol": "BTCUSDT",
            "kind": "transition",
            "state": "HOLDING",
            "previous": "OPENING_PERP",
            "cause": "entry_complete",
        }
    ]
    return b


def _quality(config):
    return {
        "status": "complete",
        "issues": [],
        "start": config.start,
        "end": config.end,
        "coverage": [
            {
                "dataset": "synthetic_fixture",
                "symbol": "BTCUSDT",
                "start": config.start,
                "end": config.end,
                "expected_start": timestamp(config.start),
                "expected_end": timestamp(config.end),
                "observed_start": timestamp(config.start),
                "observed_end": timestamp(config.end) - 1,
                "status": "complete",
                "rows": 3,
                "complete": True,
            }
        ],
    }


def test_saved_outputs_preserve_exact_money_and_reconcile_without_slippage_twice(tmp_path, rules):
    from crypto_carry.reporting import verify_run, write_run

    b = _backtest(rules)
    run = write_run(tmp_path, b.config, [b], _quality(b.config), "synthetic")
    required = {
        "run_manifest.json",
        "effective_config.toml",
        "data_quality_report.md",
        "data_coverage.csv",
        "equity_daily.csv",
        "metrics.csv",
        "forecast_evaluation.csv",
        "opportunity_daily.csv",
        "regime_comparison.csv",
        "robustness_summary.csv",
        "h1_summary.csv",
        "pnl_components.csv",
        "execution_summary.csv",
        "attribution_by_asset.csv",
        "report.md",
    }
    assert required <= {path.name for path in run.iterdir()}
    rows = pq.read_table(run / "ledger.parquet").to_pylist()
    assert rows[0]["fee"] == str(b.ledger.rows[0]["fee"])
    assert rows[0]["amount_usdt"] == str(b.ledger.rows[0]["amount_usdt"])
    assert rows[0]["timestamp_utc"] == "2024-01-01T00:00:01.000000000Z"
    daily = pd.read_csv(run / "equity_daily.csv", dtype=str, keep_default_na=False)
    units = json.loads(daily.iloc[0].units)
    assert units["BTCUSDT_spot"] == "base asset units"
    assert units["BTCUSDT_fees"] == "USDT"
    coverage = pd.read_csv(run / "data_coverage.csv", dtype=str, keep_default_na=False)
    assert coverage.iloc[0].expected_start_utc == "2024-01-01T00:00:00.000000000Z"
    components = pd.read_csv(run / "pnl_components.csv", dtype=str, keep_default_na=False)
    included = components[components.included_in_total == "True"]
    assert sum(map(D, included.amount_usdt)) == D("-0.5980025")
    assert b.equity() - b.config.capital == D("-0.5980025")
    assert components[
        components.component == "slippage_informational"
    ].included_in_total.tolist() == ["False"]
    attribution = pd.read_csv(run / "attribution_by_asset.csv", dtype=str, keep_default_na=False)
    assert sum(map(D, attribution.total_pnl_usdt)) == D("-0.5980025")
    report = (run / "report.md").read_text(encoding="utf-8")
    assert "H2: no concluyente" in report  # Only one economic strategy was supplied.
    assert verify_run(run)["valid"]


def test_execution_counts_accepted_signals_and_participation_of_unfilled_orders(rules):
    from crypto_carry.reporting import _execution

    b = Backtest(Config(), rules)
    for index, quantity, status in ((1, "10", "filled"), (2, "30", "expired")):
        order = Order(
            str(index),
            "BTCUSDT",
            "spot",
            "BUY",
            D(quantity),
            0,
            SECOND,
            "open_spot",
            status,
            recent_volume_quantity=D(100),
        )
        b.orders[order.order_id] = order
    b.signals = [
        {"symbol": "BTCUSDT", "decision": "accepted"},
        {"symbol": "BTCUSDT", "decision": "funding_not_above_cost"},
    ]
    portfolio = _execution(b)[0]
    assert portfolio["rejected_signals"] == 1
    assert portfolio["participation_observations"] == 2
    assert portfolio["participation_missing"] == 0
    assert portfolio["participation_p50"] == pytest.approx(0.2)
    assert portfolio["participation_p90"] == pytest.approx(0.28)
    assert portfolio["failed_attempts"] == 1

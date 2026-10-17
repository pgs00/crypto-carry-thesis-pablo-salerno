"""Immutable, exact-decimal research artifacts and reports from persisted tables.

Economic evaluation is delegated to evaluation.py.  Rendering never accesses a
live Backtest.  A manifest checksum detects accidental manifest changes; it is
an integrity check, not a digital signature or proof of source authenticity.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .config import SECOND, Config, iso, timestamp
from .costs import floor_step, valid_quantity
from .data.prescribed import research_assumptions
from .evaluation import (
    daily_opportunity,
    forecast_evaluation,
    h1_summary,
    metric_tables,
    regime_comparison,
)

if TYPE_CHECKING:
    from .strategy import Backtest

D = Decimal
COMMON = [
    "run_id",
    "symbol",
    "strategy",
    "funding_filter_enabled",
    "time_ns",
    "timestamp_utc",
    "units",
    "data_kind",
]
PARQUET_COLUMNS = {
    "signals": [
        "anchor",
        "history_start",
        "forecast",
        "no_change",
        "valid",
        "forecast_reason",
        "decision",
        "estimated_cycle_cost",
        "basis",
    ],
    "orders": [
        "order_id",
        "market",
        "side",
        "quantity",
        "submitted_at",
        "deadline",
        "purpose",
        "status",
        "action",
        "record_type",
    ],
    "fills": [
        "fill_id",
        "order_id",
        "market",
        "side",
        "quantity",
        "price",
        "reference_price",
        "trade_id",
        "fee_rate",
        "liquidation",
        "participation",
        "recent_volume_quantity",
        "partial",
        "remaining_quantity",
        "window_start",
        "window_end",
        "slippage_rate",
        "execution_model",
        "window_base_volume",
        "window_quote_volume",
        "max_volume_participation",
        "capacity_used",
        "fill_reason",
        "source_file",
    ],
    "ledger": [
        "event_id",
        "kind",
        "amount_usdt",
        "fee",
        "free_spot",
        "free_futures",
        "debt",
        "spot",
        "short",
        "average",
        "collateral",
    ],
    "funding_payments": ["event_id", "kind", "amount_usdt", "funding", "short", "debt"],
    "positions": [
        "state",
        "snapshot_kind",
        "spot",
        "short",
        "average",
        "collateral",
        "spot_cost",
        "realized_spot",
        "realized_futures",
        "funding",
        "fees",
        "liquidation_fees",
        "slippage",
        "spot_price",
        "mark_price",
        "dust_spot",
        "tradable_spot",
    ],
    "risk_events": ["kind", "cause", "previous", "state", "order_id", "cycle_id"],
}
OPTIONAL_PARQUET_COLUMNS = {
    "mark_gap_checks": [
        "method",
        "stage",
        "mark_open_time",
        "mark_available_at",
        "mark_close",
        "spot",
        "short",
        "average",
        "collateral",
        "balance",
        "maintenance",
        "ratio",
        "distance",
        "liquidation_price",
        "liquidate",
        "preventive",
        "state_before",
        "state_after",
        "risk_events",
    ],
    "renewal_diagnostics": [
        "decision_kind",
        "decision",
        "forecast",
        "estimated_cycle_cost",
        "basis",
        "renewal_funding_threshold",
        "actual_outcome",
        "renewal_status_kind",
        "state_after",
        "expiry_after",
    ],
}
CSV_COLUMNS = {
    "data_coverage": [
        "dataset",
        "market",
        "expected_start",
        "expected_end",
        "observed_start",
        "observed_end",
        "files",
        "rows",
        "status",
        "checks",
    ],
    "data_issues": ["issue"],
    "run_context": ["status", "label", "requested_start", "requested_end", "history_start"],
    "parameters": ["parameter", "value"],
    "run_summary": [
        "status",
        "reasons",
        "start",
        "end",
        "capital_usdt",
        "final_equity_usdt",
        "net_pnl_usdt",
        "debt_usdt",
        "free_spot",
        "free_futures",
        "stopped_at",
    ],
    "equity_daily": ["equity", "free_spot", "free_futures", "debt", "status", "partial_day"],
    "metrics": [
        "period",
        "start",
        "end",
        "status",
        "observations",
        "coverage_complete",
        "net_return",
        "cagr",
        "sharpe",
        "annual_volatility",
        "max_drawdown",
        "max_drawdown_days",
        "cagr_reason",
        "sharpe_reason",
    ],
    "forecast_evaluation": [
        "anchor",
        "history_start",
        "horizon_end",
        "forecast",
        "no_change",
        "realized",
        "horizon_valid",
        "reason",
        "error_ewma",
        "error_no_change",
        "absolute_error_ewma",
        "absolute_error_no_change",
    ],
    "h1_summary": ["period", "observations", "excluded", "mae_ewma", "mae_no_change"],
    "opportunity_daily": ["date", "complete", "opportunity", "eligible_fraction", "reason"],
    "regime_comparison": [
        "period",
        "observed_days",
        "valid_days",
        "opportunity_mean",
        "eligible_fraction",
        "conditional_cagr",
        "coverage_complete",
        "h3_descriptive",
    ],
    "robustness_summary": [
        "label",
        "dimension",
        "value",
        "status",
        "period",
        "cagr",
        "sharpe",
        "net_return",
        "coverage_complete",
        "scenario_evaluated",
    ],
    "pnl_components": ["component", "amount_usdt", "included_in_total"],
    "attribution_by_asset": [
        "spot_pnl_usdt",
        "futures_pnl_usdt",
        "funding_usdt",
        "fees_usdt",
        "liquidation_fees_usdt",
        "slippage_informational_usdt",
        "total_pnl_usdt",
    ],
    "execution_summary": [
        "orders",
        "fills",
        "failed_attempts",
        "openings",
        "renewals",
        "rebalances",
        "corrections",
        "closes",
        "liquidations",
        "blocked_orders",
        "rejected_signals",
        "turnover_usdt",
        "turnover_over_initial_capital",
        "invested_seconds",
        "unhedged_seconds",
        "cash_seconds",
        "cooldown_seconds",
        "risk_events",
        "participation_observations",
        "participation_missing",
        "participation_p50",
        "participation_p90",
        "participation_p95",
        "participation_max",
        "native_fill_count",
        "native_reconciliation_count",
    ],
}
BOOL_FIELDS = {
    "liquidate",
    "preventive",
    "periodic",
    "risk_applicable",
    "funding_filter_enabled",
    "valid",
    "liquidation",
    "partial",
    "complete",
    "horizon_valid",
    "partial_day",
    "coverage_complete",
    "included_in_total",
    "scenario_evaluated",
}
NS_FIELDS = {
    "eligible_at",
    "generated_at",
    "fill_at",
    "expired_at",
    "cancel_effective_at",
    "window_available_at",
    "mark_open_time",
    "gap_anchor",
    "gap_last",
    "time_ns",
    "anchor",
    "history_start",
    "horizon_end",
    "submitted_at",
    "deadline",
    "window_start",
    "window_end",
    "spot_price_time_ns",
    "mark_close_time_ns",
    "mark_available_at",
}
REQUIRED = (
    {f"{name}.parquet" for name in PARQUET_COLUMNS}
    | {f"{name}.csv" for name in CSV_COLUMNS}
    | {"effective_config.toml", "data_quality_report.md", "data_quality.json", "report.md"}
)


def _plain(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return value.as_posix()
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _json(value) -> str:
    return json.dumps(
        _plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _code_identity() -> tuple[str, dict]:
    # Hash the executing checkout even when the output root is a pytest tempdir.
    project = Path(__file__).resolve().parents[2]
    paths = list((project / "src").rglob("*.py"))
    paths.extend(p for p in (project / "pyproject.toml", project / "uv.lock") if p.is_file())
    hashes = {p.relative_to(project).as_posix(): _hash(p) for p in sorted(paths)}
    return hashlib.sha256(_json(hashes).encode("utf-8")).hexdigest(), hashes


def _dependencies() -> dict:
    result = {}
    for name in ("nautilus_trader", "pandas", "numpy", "matplotlib", "pyarrow", "httpx"):
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = "not installed"
    return result


def _unit(name: str) -> str:
    if name == "reference_price_model":
        return "price convention identifier"
    if name in {"window_vwap", "window_ohlc4", "window_open", "window_high",
                "window_low", "window_close"}:
        return "USDT per base asset unit"
    for prefix in ("BTCUSDT_", "ETHUSDT_"):
        if name.startswith(prefix):
            return _unit(name.removeprefix(prefix))
    if name == "sharpe":
        return "dimensionless risk-adjusted ratio; not a percentage"
    if name in NS_FIELDS or name in {
        "expected_start",
        "expected_end",
        "observed_start",
        "observed_end",
    }:
        return "UTC nanoseconds when numeric; otherwise ISO 8601 UTC"
    if name == "timestamp_utc" or name.endswith("_utc"):
        return "ISO 8601 UTC"
    if name.endswith("seconds"):
        return "seconds"
    if name.endswith("days"):
        return "calendar days"
    if name in {
        "quantity",
        "spot",
        "short",
        "dust_spot",
        "tradable_spot",
        "base_fee_quantity",
        "recent_volume_quantity",
        "vwap_quantity",
    }:
        return "base asset units"
    if "price" in name or name in {"average", "mark", "mark_close"} or name.endswith("_mark"):
        return "USDT per base asset unit"
    if (
        name.endswith("usdt")
        or name
        in {
            "balance",
            "maintenance",
            "equity_before_risk",
            "equity_after_risk",
            "equity",
            "free_spot",
            "free_futures",
            "debt",
            "collateral",
            "spot_cost",
            "realized_spot",
            "realized_futures",
            "funding",
            "fees",
            "fee",
            "pnl",
            "liquidation_fees",
            "liquidation_fee",
            "collateral_change",
            "debt_change",
            "spot_proceeds",
            "transfer_futures_to_spot",
            "transfer",
            "open_loss",
            "slippage",
            "rounding_cost",
            "vwap_notional",
        }
        or name.startswith("cash_")
        and name.endswith("change")
    ):
        return "USDT"
    if name in BOOL_FIELDS:
        return "boolean"
    if name in {"ratio", "distance", "margin_exit_ratio", "liquidation_distance"}:
        return "dimensionless fraction"
    if (
        any(
            part in name
            for part in (
                "return",
                "cagr",
                "sharpe",
                "volatility",
                "drawdown",
                "forecast",
                "no_change",
                "realized",
                "error",
                "mae",
                "basis",
                "fee_rate",
                "participation_p",
                "participation_max",
                "eligible_fraction",
                "opportunity",
                "estimated_cycle_cost",
            )
        )
        or name == "participation"
    ):
        return "dimensionless ratio (1 = 100%)"
    return "identifier, label or count as column indicates"


def _write_table(run: Path, name: str, rows, manifest: dict, parquet: bool = False) -> None:
    rows = rows.to_dict("records") if isinstance(rows, pd.DataFrame) else list(rows)
    rows = [dict(row) for row in rows]
    defaults = list(
        (PARQUET_COLUMNS | OPTIONAL_PARQUET_COLUMNS)[name] if parquet else CSV_COLUMNS[name]
    )
    time_fields = (
        NS_FIELDS
        | {
            "start",
            "end",
            "expected_start",
            "expected_end",
            "observed_start",
            "observed_end",
            "next_expiry",
        }
    ) - {"time_ns"}
    source_keys = set(defaults) | {key for row in rows for key in row}
    for key in sorted(source_keys & time_fields):
        utc_key = f"{key}_utc"
        defaults.append(utc_key)
        for row in rows:
            value = _plain(row.get(key))
            if value is not None and value != "":
                row[utc_key] = iso(
                    timestamp(value) if isinstance(value, str) and "T" in value else int(value)
                )
    extra = sorted({key for row in rows for key in row} - set(COMMON) - set(defaults))
    columns = list(dict.fromkeys(COMMON + defaults + extra))
    unit_map = _json({key: _unit(key) for key in columns if key != "units"})
    normalized = []
    for original in rows:
        row = {key: _plain(original.get(key)) for key in columns}
        row.update(
            run_id=manifest["run_id"],
            data_kind=manifest["data_kind"],
            symbol=row.get("symbol") or "PORTFOLIO",
            strategy=row.get("strategy") or "COMMON",
            units=unit_map,
        )
        if row.get("time_ns") is not None:
            row["time_ns"] = int(row["time_ns"])
            row["timestamp_utc"] = iso(row["time_ns"])
        for key, value in row.items():
            if isinstance(value, (dict, list)):
                row[key] = _json(value)
        normalized.append(row)
    if parquet:
        fields = [
            pa.field(
                key,
                pa.int64()
                if key in NS_FIELDS
                else pa.bool_()
                if key in BOOL_FIELDS
                else pa.string(),
            )
            for key in columns
        ]
        schema = pa.schema(
            fields,
            metadata={
                b"decimal_contract": b"Exact monetary quantities are decimal strings",
                b"run_id": manifest["run_id"].encode(),
            },
        )
        for row in normalized:
            for field in fields:
                value = row[field.name]
                if value is not None and pa.types.is_string(field.type):
                    row[field.name] = str(value)
        pq.write_table(
            pa.Table.from_pylist(normalized, schema=schema),
            run / f"{name}.parquet",
            compression="zstd",
        )
    else:
        with (run / f"{name}.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(normalized)


def _stamp(rows, b) -> list[dict]:
    return [
        dict(row, strategy=b.strategy, funding_filter_enabled=b.funding_filter_enabled)
        for row in rows
    ]


def _final_positions(b) -> list[dict]:
    rows = []
    for symbol, position in b.ledger.positions.items():
        spot_price, mark_price = b.spot_prices().get(symbol), b.mark_prices().get(symbol)
        trade, mark = b.trades.get((symbol, "spot")), b.marks.get(symbol)
        rule = b.rules.get(symbol, "spot", b.now)
        tradable = None
        if position.spot == 0:
            tradable = D(0)
        elif rule is not None and spot_price is not None:
            rounded = floor_step(position.spot, rule.step)
            tradable = rounded if valid_quantity(rounded, spot_price, rule) else D(0)
        rows.append(
            dict(
                asdict(position),
                symbol=symbol,
                time_ns=b.now,
                state=b.pairs[symbol].state.value,
                snapshot_kind="final",
                spot_price=spot_price,
                mark_price=mark_price,
                tradable_spot=tradable,
                dust_spot=position.spot - tradable if tradable is not None else None,
                spot_price_time_ns=trade.event_time if trade else None,
                mark_close_time_ns=mark.close_time if mark else None,
                mark_available_at=mark.available_at if mark else None,
                spot_price_age_seconds=D(b.now - trade.event_time) / SECOND if trade else None,
                mark_age_seconds=D(b.now - mark.close_time) / SECOND if mark else None,
            )
        )
    return _stamp(rows, b)


def _attribution(b) -> tuple[list[dict], list[dict]]:
    assets, totals = [], Counter()
    for symbol, p in b.ledger.positions.items():
        spot_pnl = p.realized_spot + (
            p.spot * b.spot_prices()[symbol] - p.spot_cost if p.spot else D(0)
        )
        futures_pnl = p.realized_futures + (
            p.short * (p.average - b.mark_prices()[symbol]) if p.short else D(0)
        )
        values = {
            "spot_pnl_usdt": spot_pnl,
            "futures_pnl_usdt": futures_pnl,
            "funding_usdt": p.funding,
            "fees_usdt": -p.fees,
            "liquidation_fees_usdt": -p.liquidation_fees,
        }
        total = sum(values.values(), D(0))
        assets.append(
            dict(
                symbol=symbol,
                time_ns=b.now,
                **values,
                total_pnl_usdt=total,
                slippage_informational_usdt=p.slippage,
            )
        )
        for key, value in values.items():
            totals[key] += value
        totals["slippage_informational"] += p.slippage
    attributed = sum((r["total_pnl_usdt"] for r in assets), D(0))
    difference = b.equity() - b.config.capital - attributed
    if abs(difference) > b.config.accounting_tolerance:
        raise ValueError(f"Attribution does not reconcile for {b.strategy}: {difference}")
    components = [
        {
            "symbol": "PORTFOLIO",
            "time_ns": b.now,
            "component": key.removesuffix("_usdt"),
            "amount_usdt": value,
            "included_in_total": key != "slippage_informational",
        }
        for key, value in totals.items()
    ]
    return _stamp(assets, b), _stamp(components, b)


def _execution(b) -> list[dict]:
    output = []
    for symbol in ["PORTFOLIO", *b.config.symbols]:
        all_assets = symbol == "PORTFOLIO"
        fills = [r for r in b.fills if all_assets or r["symbol"] == symbol]
        orders = [o for o in b.orders.values() if all_assets or o.symbol == symbol]
        risks = [r for r in b.risk_events if all_assets or r.get("symbol") == symbol]
        signals = [r for r in b.signals if all_assets or r["symbol"] == symbol]
        kinds = Counter(r.get("kind", "") for r in risks)
        transitions = Counter(r.get("state", "") for r in risks if r.get("kind") == "transition")
        failed = sum(o.status in {"expired", "rejected", "timeout"} for o in orders)
        turnover = sum((D(str(r["quantity"])) * D(str(r["price"])) for r in fills), D(0))
        participation = [
            float(order.quantity / order.recent_volume_quantity)
            for order in orders
            if order.recent_volume_quantity > 0
        ]
        prefix = "portfolio" if all_assets else symbol
        row = {
            "symbol": symbol,
            "time_ns": b.now,
            "orders": len(orders),
            "fills": len(fills),
            "failed_attempts": max(failed, kinds["attempt_failed"]),
            "openings": transitions["OPENING_SPOT"],
            "renewals": kinds["renewal"],
            "rebalances": transitions["REBALANCING"],
            "corrections": transitions["CORRECTING_HEDGE"],
            "closes": kinds["close_requested"],
            "liquidations": sum(bool(r.get("liquidation")) for r in fills),
            "blocked_orders": kinds["order_blocked"],
            "rejected_signals": sum(r.get("decision") != "accepted" for r in signals),
            "turnover_usdt": turnover,
            "turnover_over_initial_capital": turnover / b.config.capital,
            "invested_seconds": b.durations.get(f"{prefix}_invested_seconds", D(0)),
            "unhedged_seconds": (
                None if all_assets else b.durations.get(f"{symbol}_unhedged_seconds", D(0))
            ),
            "cash_seconds": b.durations.get("cash_seconds", D(0)) if all_assets else None,
            "cooldown_seconds": None
            if all_assets
            else b.durations.get(f"{symbol}_cooldown_seconds", D(0)),
            "risk_events": len(risks),
            "participation_observations": len(participation),
            "participation_missing": len(orders) - len(participation),
            "native_fill_count": getattr(b, "native_fill_count", 0) if all_assets else None,
            "native_reconciliation_count": b.native_reconciliation_count if all_assets else None,
        }
        for label, quantile in (("p50", 0.5), ("p90", 0.9), ("p95", 0.95), ("max", 1)):
            row[f"participation_{label}"] = (
                float(np.quantile(participation, quantile)) if participation else None
            )
        output.append(row)
    return _stamp(output, b)


def _status(backtests, quality, config) -> str:
    statuses = {b.status for b in backtests}
    if "failed" in statuses or quality.get("status") == "failed":
        return "failed"
    if (
        not backtests
        or quality.get("status") != "complete"
        or "incomplete_data" in statuses
        or any(b.now < timestamp(config.end) - 1 for b in backtests)
    ):
        return "incomplete_data"
    return "insolvent" if "insolvent" in statuses else "complete"


def _result_digest(backtests, quality) -> str:
    digest = hashlib.sha256(_json(quality).encode("utf-8"))
    for b in sorted(backtests, key=lambda item: (item.strategy, item.funding_filter_enabled)):
        for value in (
            b.strategy,
            b.funding_filter_enabled,
            b.status,
            b.reasons,
            b.now,
            b.stopped_at,
            b.ledger.positions,
            b.ledger.free_spot,
            b.ledger.free_futures,
            b.ledger.debt,
            b.spot_prices(),
            b.mark_prices(),
            dict(b.durations),
            b.orders,
            b.pairs,
            _final_positions(b),
            getattr(b, "native_fill_count", 0),
            b.native_reconciliation_count,
        ):
            digest.update(_json(value).encode("utf-8"))
        for rows in (
            b.signals,
            getattr(b, "renewal_diagnostics", []),
            b.order_rows,
            b.fills,
            b.ledger.rows,
            b.ledger.funding_rows,
            b.positions,
            b.risk_events,
            getattr(b, "mark_gap_checks", []),
            b.daily,
            b.opportunities,
            b.all_funding,
        ):
            digest.update(b"\nTABLE\n")
            for row in rows:
                digest.update(_json(row).encode("utf-8") + b"\n")
    return digest.hexdigest()


def _persist_tables(run, config, backtests, quality, manifest):
    tables = {name: [] for name in (*PARQUET_COLUMNS, *OPTIONAL_PARQUET_COLUMNS, *CSV_COLUMNS)}
    tables["data_coverage"] = quality.get("coverage", [])
    tables["data_issues"] = [{"issue": item} for item in quality.get("issues", [])]
    tables["run_context"] = [
        {
            "status": manifest["status"],
            "label": manifest["label"],
            "requested_start": config.start,
            "requested_end": config.end,
            "history_start": config.history_start,
            "scope": quality.get(
                "scope", "synthetic" if manifest["data_kind"] == "synthetic" else "unspecified"
            ),
            "full_baseline_coverage": bool(quality.get("full_baseline_coverage", False)),
        }
    ]
    tables["parameters"] = [
        {"parameter": key, "value": value} for key, value in config.to_dict().items()
    ]
    for b in sorted(backtests, key=lambda item: (item.strategy, item.funding_filter_enabled)):
        for name, rows in (
            ("signals", b.signals),
            ("renewal_diagnostics", getattr(b, "renewal_diagnostics", [])),
            ("fills", b.fills),
            ("ledger", b.ledger.rows),
            ("funding_payments", b.ledger.funding_rows),
            ("risk_events", b.risk_events),
            ("mark_gap_checks", getattr(b, "mark_gap_checks", [])),
            ("equity_daily", b.daily),
        ):
            tables[name].extend(_stamp(rows, b))
        tables["orders"].extend(_stamp([dict(row, record_type="event") for row in b.order_rows], b))
        tables["orders"].extend(
            _stamp(
                [
                    dict(asdict(order), time_ns=b.now, record_type="final",
                         **b._execution_metadata(order))
                    for order in b.orders.values()
                ],
                b,
            )
        )
        tables["positions"].extend(
            _stamp([dict(row, snapshot_kind="event") for row in b.positions], b)
        )
        tables["positions"].extend(_final_positions(b))
        assets, components = _attribution(b)
        tables["attribution_by_asset"].extend(assets)
        tables["pnl_components"].extend(components)
        tables["execution_summary"].extend(_execution(b))
        tables["run_summary"].extend(
            _stamp(
                [
                    {
                        "time_ns": b.now,
                        "status": b.status,
                        "reasons": b.reasons,
                        "start": b.config.start,
                        "end": iso(b.now),
                        "capital_usdt": b.config.capital,
                        "final_equity_usdt": b.equity(),
                        "net_pnl_usdt": b.equity() - b.config.capital,
                        "debt_usdt": b.ledger.debt,
                        "free_spot": b.ledger.free_spot,
                        "free_futures": b.ledger.free_futures,
                        "stopped_at": iso(b.stopped_at) if b.stopped_at is not None else None,
                    }
                ],
                b,
            )
        )
    metrics = metric_tables(backtests, config)
    if not metrics.empty:
        # Preserve each strategy's identity even if a funding-off control is supplied.
        by_strategy = {b.strategy: b.funding_filter_enabled for b in backtests}
        metrics["funding_filter_enabled"] = metrics.strategy.map(by_strategy)
        if manifest["status"] not in {"complete", "insolvent"}:
            metrics["coverage_complete"] = False
    tables["metrics"] = metrics
    # H1 and market opportunity are common datasets, not pooled duplicated portfolios.
    common = next(
        (b for b in backtests if b.strategy == "conditional"), backtests[0] if backtests else None
    )
    forecast = forecast_evaluation(
        common.signals if common else [], common.all_funding if common else [], config
    )
    opportunities = daily_opportunity(common.opportunities if common else [], config)
    tables["forecast_evaluation"] = forecast
    tables["h1_summary"] = h1_summary(forecast, config)
    tables["opportunity_daily"] = opportunities
    tables["regime_comparison"] = regime_comparison(opportunities, metrics)
    if metrics.empty:
        tables["robustness_summary"] = [
            {
                "label": manifest["label"],
                "dimension": "baseline",
                "value": 1,
                "status": manifest["status"],
                "scenario_evaluated": False,
                "coverage_complete": False,
            }
        ]
    else:
        tables["robustness_summary"] = [
            dict(
                row,
                label=manifest["label"],
                dimension="baseline",
                value=1,
                scenario_evaluated=False,
            )
            for row in metrics[metrics.period == "full"].to_dict("records")
        ]
    for name, rows in tables.items():
        _write_table(
            run,
            name,
            rows,
            manifest,
            parquet=name in PARQUET_COLUMNS or name in OPTIONAL_PARQUET_COLUMNS,
        )


def _read(run: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(run / f"{name}.csv", dtype=str, keep_default_na=False)


def _yes(value) -> bool:
    return str(value).lower() == "true"


def _number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _judgments(run: Path) -> tuple[str, str, str]:
    context = _read(run, "run_context").iloc[0]
    if context.status != "complete":
        return ("no concluyente: cobertura incompleta o métricas no evaluables",) * 3
    if context.data_kind == "historical" and not _yes(context.full_baseline_coverage):
        return ("no concluyente para toda la muestra: intervalo preliminar",) * 3
    h1 = _read(run, "h1_summary")
    full = h1[(h1.period == "full") & (h1.symbol == "EQUAL_WEIGHT")]
    verdict1 = "no concluyente: sin comparación válida de MAE"
    if len(full):
        a, b = _number(full.iloc[0].mae_ewma), _number(full.iloc[0].mae_no_change)
        if a is not None and b is not None:
            verdict1 = "favorable" if a < b else "contraria" if a > b else "no concluyente: empate"
    metrics, daily = _read(run, "metrics"), _read(run, "equity_daily")
    conditional = metrics[(metrics.strategy == "conditional") & (metrics.period == "full")]
    permanent = metrics[(metrics.strategy == "permanent") & (metrics.period == "full")]
    verdict2 = "no concluyente: faltan dos carteras comparables o métricas válidas"
    if len(conditional) == len(permanent) == 1:
        a, b = conditional.iloc[0], permanent.iloc[0]
        cagr, sharpe_a, sharpe_b = _number(a.cagr), _number(a.sharpe), _number(b.sharpe)
        dates_a = daily[daily.strategy == "conditional"].time_ns.tolist()
        dates_b = daily[daily.strategy == "permanent"].time_ns.tolist()
        valid = (
            _yes(a.coverage_complete)
            and _yes(b.coverage_complete)
            and _yes(a.funding_filter_enabled)
            and not _yes(b.funding_filter_enabled)
            and dates_a == dates_b
            and all(v is not None for v in (cagr, sharpe_a, sharpe_b))
        )
        if valid:
            verdict2 = (
                "favorable"
                if cagr > 0 and sharpe_a > sharpe_b
                else "contraria al criterio definido"
            )
    regimes = _read(run, "regime_comparison")
    verdict3 = "no concluyente: cobertura insuficiente de ambos regímenes"
    if len(regimes) == 2 and all(_yes(v) for v in regimes.coverage_complete):
        verdict3 = regimes.iloc[0].h3_descriptive.replace("_", " ")
    return verdict1, verdict2, verdict3


def _safe_artifact(run: Path, name: str) -> Path:
    candidate = Path(name)
    if candidate.is_absolute() or ".." in candidate.parts or ":" in name or "\\" in name:
        raise ValueError(f"Unsafe manifest artifact path: {name}")
    resolved = (run / candidate).resolve()
    if not resolved.is_relative_to(run.resolve()):
        raise ValueError(f"Artifact escapes run directory: {name}")
    return resolved


def _finish_manifest(run: Path, manifest: dict) -> None:
    manifest["output_hashes"] = {
        p.relative_to(run).as_posix(): _hash(p)
        for p in sorted(run.rglob("*"))
        if p.is_file() and p.name not in {"run_manifest.json", "run_manifest.sha256"}
    }
    path = run / "run_manifest.json"
    path.write_text(
        json.dumps(_plain(manifest), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (run / "run_manifest.sha256").write_text(_hash(path) + "\n", encoding="ascii")


def verify_run(run_dir: Path) -> dict:
    """Rehash all declared artifacts and the manifest; report every detected issue."""
    run = Path(run_dir).resolve()
    mismatches = []
    try:
        manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("Manifest must be a JSON object")
    except (OSError, ValueError) as exc:
        return {
            "valid": False,
            "status": "failed",
            "run_id": run.name,
            "checked_files": 0,
            "mismatches": [{"path": "run_manifest.json", "reason": str(exc)}],
        }
    try:
        expected = (run / "run_manifest.sha256").read_text(encoding="ascii").strip()
        if _hash(run / "run_manifest.json") != expected:
            mismatches.append({"path": "run_manifest.json", "reason": "manifest checksum mismatch"})
    except (OSError, UnicodeError) as exc:
        mismatches.append(
            {"path": "run_manifest.sha256", "reason": f"missing or unreadable: {exc}"}
        )
    hashes = manifest.get("output_hashes", {})
    if not isinstance(hashes, dict):
        hashes = {}
        mismatches.append({"path": "run_manifest.json", "reason": "invalid output_hashes"})
    if manifest.get("run_id") != run.name:
        mismatches.append({"path": "run_manifest.json", "reason": "run_id differs from directory"})
    checked = 0
    for name, expected in hashes.items():
        try:
            path = _safe_artifact(run, name)
            if not path.is_file():
                mismatches.append({"path": name, "reason": "missing"})
                continue
            checked += 1
            actual = _hash(path)
            if actual != expected:
                mismatches.append(
                    {
                        "path": name,
                        "reason": "checksum mismatch",
                        "expected": expected,
                        "actual": actual,
                    }
                )
        except (OSError, ValueError) as exc:
            mismatches.append({"path": name, "reason": str(exc)})
    for name in sorted(REQUIRED - set(hashes)):
        mismatches.append({"path": name, "reason": "required artifact absent from manifest"})
    expected_paths = set(hashes) | {"run_manifest.json", "run_manifest.sha256"}
    actual_paths = {p.relative_to(run).as_posix() for p in run.rglob("*") if p.is_file()}
    for name in sorted(actual_paths - expected_paths):
        mismatches.append({"path": name, "reason": "untracked artifact"})
    if not manifest.get("artifacts_complete") or manifest.get("status") == "failed":
        mismatches.append(
            {"path": "run_manifest.json", "reason": "artifact build failed or incomplete"}
        )
    return {
        "valid": not mismatches,
        "status": manifest.get("status"),
        "run_id": manifest.get("run_id"),
        "checked_files": checked,
        "mismatches": mismatches,
    }


def write_run(
    root: Path,
    config: Config,
    backtests: list[Backtest],
    quality: dict,
    data_kind: str,
    label: str = "baseline",
    inputs: dict | None = None,
    output_root: Path | None = None,
) -> Path:
    """Create a run once, or reuse it only after checking identity and all hashes."""
    if data_kind not in {"synthetic", "historical", "historical_assumptions"}:
        raise ValueError("data_kind must be synthetic, historical or historical_assumptions")
    research = config.analysis_mode == "prescribed_research"
    if research != (data_kind == "historical_assumptions"):
        raise ValueError("analysis_mode and data_kind describe different research provenance")
    if len({b.strategy for b in backtests}) != len(backtests):
        raise ValueError("Each strategy must have a unique name within a run")
    if any(b.config.to_dict() != config.to_dict() for b in backtests):
        raise ValueError("Backtest configuration differs from the effective run configuration")
    code_hash, code_files = _code_identity()
    identity = {
        "config": config.to_dict(),
        "code_hash": code_hash,
        "input_hashes": _plain(inputs or {}),
        "strategies": sorted(
            [
                {"strategy": b.strategy, "funding_filter_enabled": b.funding_filter_enabled}
                for b in backtests
            ],
            key=lambda item: item["strategy"],
        ),
        "data_kind": data_kind,
        "label": label,
    }
    run_id = "run_" + hashlib.sha256(_json(identity).encode("utf-8")).hexdigest()[:24]
    destination = Path(root).resolve() / "outputs" if output_root is None else Path(output_root).resolve()
    run = destination / run_id
    result_digest = _result_digest(backtests, quality)
    if run.exists():
        verification = verify_run(run)
        if not verification["valid"]:
            raise ValueError(
                f"Immutable run has checksum corruption or incomplete artifacts: {verification['mismatches']}"
            )
        existing = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
        if existing.get("result_digest") != result_digest:
            raise ValueError(
                "Immutable run identity already exists with different results or quality evidence"
            )
        return run
    run.mkdir(parents=True, exist_ok=False)
    observed = [b for b in backtests if b.now >= timestamp(config.start)]
    conventions = {
        "time": "UTC integer nanoseconds",
        "money": "exact decimal strings in Parquet",
        "annualization": "365 calendar days; sample daily standard deviation; risk-free rate zero",
        "marks": "last available closed one-minute mark; trades for execution",
        "slippage": "included in fill; informational attribution never subtracted twice",
        "terminal_positions": "valued without forced close or hypothetical fees",
        "synthetic": "software validation only; never historical academic results",
        "hashes": "SHA-256; manifest excluded from output_hashes and checked by sidecar",
        "input_provenance": "caller supplied" if inputs else "not supplied",
    }
    if config.execution_model == "minute_open":
        conventions.update(
            marks="last available closed one-minute mark for risk and valuation",
            execution=(
                "one-minute bar open assigned to the opening boundary; exact first trade time unknown"
            ),
            fill_reference_ids=(
                "bar:<symbol>:<market>:<open_ns>; source-bar references, not individual trade IDs"
            ),
            order_timeout=f"{config.order_timeout_seconds} seconds from submission",
            leg_delay=(
                f"configured delay {config.leg_delay_seconds} second; fill at a strictly later "
                "available minute open, typically up to one additional minute per leg"
            ),
            participation=(
                "prior closed one-minute volume; approximation of rolling 60 seconds; "
                "unavailable before bar close"
            ),
            liquidation_path=(
                "no intrabar high/low path; risk uses the last available closed one-minute mark"
            ),
        )
    elif config.execution_model == "next_minute_vwap":
        conventions.update(
            marks="last available closed one-minute mark for signals, risk and valuation",
            execution=(
                "quote volume divided by base volume in the first full minute beginning at or "
                "after submission"
            ),
            fill_reference_ids=("minute-window source references; not individual trade IDs"),
            fill_time="eligible minute close, after price and volume are known",
            capacity=(
                f"{config.max_volume_participation * 100:f}".rstrip("0").rstrip(".")
                + "% of eligible-minute base volume; "
                "remainder expires"
            ),
            partial_fills="one native fill event records the executable quantity",
            liquidation_path=(
                "no intrabar high/low path; risk uses the last available closed one-minute mark"
            ),
        )
    if config.execution_research_active:
        conventions.update(
            reference_price_model=config.research_minute_price_model,
            execution="selected price from the full minute beginning at or after eligibility",
            eligibility="original submitted_at + purpose-classified additional client delay",
            research_execution_delay_seconds=config.research_execution_delay_seconds,
            research_execution_delay_scope=config.research_execution_delay_scope,
            liquidation_additional_delay_seconds=0,
            risk_deadlines="unchanged; no automatic extension to delayed execution windows",
        )
    manifest = dict(
        identity,
        run_id=run_id,
        code_files=code_files,
        python=platform.python_version(),
        dependencies=_dependencies(),
        platform=platform.platform(),
        status=_status(backtests, quality, config),
        artifacts_complete=False,
        result_digest=result_digest,
        created_at=datetime.now(UTC).isoformat(),
        requested_range={
            "start": config.start,
            "end": config.end,
            "end_inclusive": False,
            "history_start": config.history_start,
        },
        observed_range={
            "start": config.start if observed else None,
            "end": iso(max(b.now for b in observed)) if observed else None,
            "source": "backtest clock; market-data coverage is in data_coverage.csv",
        },
        conventions=conventions,
    )
    if config.mark_gap_method != "strict":
        conventions["mark_gap_method"] = config.mark_gap_method
        conventions["mark_gap_coverage"] = (
            "completed_with_approximations"
            if quality["status"] == "complete" and manifest["status"] in {"complete", "insolvent"}
            else "incomplete_data"
        )
        conventions["mark_gap_estimates"] = (
            "Only 15 documented missing minutes; fixed last official anchor; "
            "published at next minute; no additional basis; funding proxy unchanged"
        )
    try:
        for name in (
            "download.json",
            "processed.json",
            "coverage.json",
            "mark_gap_audit.json",
            "original_processed.json",
        ):
            source = Path(root).resolve() / config.data_dir / "manifests" / name
            if data_kind in {"historical", "historical_assumptions"} and source.is_file():
                destination = run / "source_manifests" / name
                destination.parent.mkdir(exist_ok=True)
                destination.write_bytes(source.read_bytes())
        (run / "effective_config.toml").write_text(config.to_toml(), encoding="utf-8")
        (run / "data_quality.json").write_text(_json(quality) + "\n", encoding="utf-8")
        if data_kind == "historical_assumptions":
            validated = list(quality.get("funding_mark_audit", []))
            consumed = [
                {
                    **asdict(item),
                    "strategy": b.strategy,
                    "funding_filter_enabled": b.funding_filter_enabled,
                    "economic_window": item.funding_time >= timestamp(config.start),
                }
                for b in backtests
                for item in b.all_funding
            ]
            methods = Counter(row.get("settlement_mark_method", "exact") for row in consumed)
            counts_by_strategy = {
                b.strategy: dict(
                    sorted(Counter(item.settlement_mark_method for item in b.all_funding).items())
                )
                for b in backtests
            }
            audit = {
                "validated_count": len(validated),
                "engine_consumed_count": len(consumed),
                "exact_consumed_count": methods["exact"],
                "proxy_consumed_count": methods["previous_closed_1m"],
                "warmup_not_required_count": methods["not_required_before_start"],
                "counts_by_strategy": counts_by_strategy,
                "validated": validated,
                "consumed": consumed,
                "limitations": [
                    "Validated records may cover the whole requested window even when a run stops early.",
                    "Consumed observations do not necessarily produce cash funding payments.",
                    "Warmup not_required_before_start observations are not mark substitutions.",
                    "Proxy marks are causal approximations and do not certify historical rules.",
                ],
            }
            (run / "research_assumptions.json").write_text(
                _json(research_assumptions(config)) + "\n", encoding="utf-8"
            )
            (run / "funding_mark_audit.json").write_text(_json(audit) + "\n", encoding="utf-8")
        _persist_tables(run, config, backtests, quality, manifest)
        (run / "data_quality_report.md").write_text(_quality_text(run), encoding="utf-8")
        (run / "report.md").write_text(_report_text(run), encoding="utf-8")
        manifest["artifacts_complete"] = True
        _finish_manifest(run, manifest)
        verification = verify_run(run)
        if not verification["valid"]:
            raise ValueError(f"New artifact verification failed: {verification['mismatches']}")
    except Exception as exc:
        manifest.update(
            status="failed", artifacts_complete=False, failure=f"{type(exc).__name__}: {exc}"
        )
        _finish_manifest(run, manifest)
        raise
    return run


def _quality_text(run: Path) -> str:
    quality = json.loads((run / "data_quality.json").read_text(encoding="utf-8"))
    lines = ["# Calidad y cobertura", "", f"Estado: {quality['status']}.", "",
             "La evidencia de cobertura se conserva en data_quality.json y data_coverage.csv.",
             "Esta salida usa datos preparados y no vuelve a certificar las fuentes.", ""]
    lines.extend(f"- {issue}" for issue in quality.get("issues", []))
    return "\n".join(lines) + "\n"


def _report_text(run: Path) -> str:
    context = _read(run, "run_context").iloc[0]
    config = Config.load(run / "effective_config.toml")
    quality = json.loads((run / "data_quality.json").read_text(encoding="utf-8"))
    coverage = ("completed_with_approximations" if quality["status"] == "complete"
                and context.status in {"complete", "insolvent"} else "incomplete_data")
    lines = ["# Resultados de la corrida", "", f"Estado: {context.status}.",
             f"Datos: {context.data_kind}.", ""]
    if config.mark_gap_method != "strict":
        lines.extend([f"Cobertura {coverage}; método {config.mark_gap_method}.", ""])
    lines.extend(f"- H{index}: {verdict}" for index, verdict in enumerate(_judgments(run), 1))
    lines.extend(["", "Las fórmulas y tablas económicas se conservan en los siguientes archivos:", ""])
    lines.extend(f"- [{name}.csv]({name}.csv)" for name in (
        "metrics", "equity_daily", "pnl_components", "h1_summary", "opportunity_daily",
        "regime_comparison", "execution_summary", "data_coverage"))
    return "\n".join(lines) + "\n"

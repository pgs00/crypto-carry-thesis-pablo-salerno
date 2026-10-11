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
import tempfile
from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
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
FIGURES = ("equity", "drawdown", "pnl_components", "forecast", "opportunity", "cost_sensitivity")
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
    | {f"figures/{name}.{ext}" for name in FIGURES for ext in ("png", "svg")}
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
                    dict(asdict(order), time_ns=b.now, record_type="final")
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
    except TypeError, ValueError:
        return None


def _markdown(frame: pd.DataFrame, columns: list[str], limit: int | None = None) -> str:
    if frame.empty:
        return "Sin observaciones verificadas.\n"
    columns = [column for column in columns if column in frame.columns]
    selected = frame[columns].head(limit) if limit else frame[columns]

    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ") if str(value) else "—"

    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    lines.extend(
        "| " + " | ".join(cell(value) for value in row) + " |"
        for row in selected.itertuples(index=False, name=None)
    )
    return "\n".join(lines) + "\n"


def _documented_closures_text(run: Path, heading: str) -> str:
    quality = json.loads((run / "data_quality.json").read_text(encoding="utf-8"))
    closures = quality.get("documented_closures", [])
    if not closures:
        return ""
    return (
        f"{heading} Cierres documentados de mercado\n\n"
        "Estos cierres publicados por la fuente son evidencia ex post de cobertura. "
        "No se clasifican como datos faltantes, no generan barras sintéticas y no se "
        "entregaron anticipadamente a la estrategia.\n\n"
        + _markdown(
            pd.DataFrame([{**row, "symbols": ", ".join(row["symbols"])} for row in closures]),
            [
                "symbols",
                "market",
                "start_utc",
                "end_utc",
                "minutes",
                "source_url",
                "description",
            ],
        )
    )


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


def _quality_text(run: Path) -> str:
    context, issues = _read(run, "run_context").iloc[0], _read(run, "data_issues")
    text = (
        f"# Calidad y cobertura\n\nTipo: {context.data_kind}. Estado: {context.status}.\n\n"
        "La cobertura observada se conserva sin rellenar huecos ni inferir reglas históricas.\n\n"
        + _markdown(
            _read(run, "data_coverage"),
            [
                "dataset",
                "symbol",
                "market",
                "expected_start_utc",
                "expected_end_utc",
                "observed_start_utc",
                "observed_end_utc",
                "files",
                "rows",
                "status",
            ],
        )
        + "\n## Bloqueos y observaciones\n\n"
        + (
            _markdown(issues, ["issue"])
            if not issues.empty
            else "No se registraron bloqueos adicionales.\n"
        )
    )
    closures = _documented_closures_text(run, "##")
    return text + ("\n" + closures if closures else "")


def _report_text(run: Path) -> str:
    context = _read(run, "run_context").iloc[0]
    synthetic = context.data_kind == "synthetic"
    research = context.data_kind == "historical_assumptions"
    label = (
        "SINTÉTICO — validación del pipeline" if synthetic else "HISTÓRICO — cobertura observada"
    )
    if research:
        label = "PRECIOS OBSERVADOS CON SUPUESTOS PRESCRIPTOS"
    summary, metrics = _read(run, "run_summary"), _read(run, "metrics")
    params = _read(run, "parameters")
    gap_parameter = params[params.parameter == "mark_gap_method"]
    gap_method = gap_parameter.iloc[0].value if len(gap_parameter) else "strict"
    execution = params[params.parameter == "execution_model"]
    execution_value = execution.iloc[0].value if len(execution) == 1 else None
    minute_execution = execution_value in {"minute_open", "next_minute_vwap"}
    timeout = params[params.parameter == "order_timeout_seconds"].iloc[0].value
    leg_delay = params[params.parameter == "leg_delay_seconds"].iloc[0].value
    capital = params[params.parameter == "capital"].iloc[0].value
    leg_delay_unit = "segundo" if leg_delay == "1" else "segundos"
    legacy_minute_text = (
        "Convención de ejecución por minuto: los fills usan el open de la barra de un minuto "
        "asignado al inicio de la barra; se desconoce la hora exacta de la primera operación. "
        "Las referencias de los fills usan `bar:<symbol>:<market>:<open_ns>` y remiten a barras "
        f"fuente; no son IDs de operaciones individuales. El timeout de la orden es de {timeout} "
        f"segundos. La demora configurada entre patas es de {leg_delay} {leg_delay_unit}; cada fill "
        "espera un open de minuto disponible estrictamente posterior, lo que suele agregar hasta "
        "un minuto por pata. Las señales siguen la disponibilidad del funding y el equity diario "
        "se observa al cierre UTC. Ambos activos comparten el capital de cada estrategia dentro "
        "de esta ventana de evaluación."
        if execution_value == "minute_open"
        else None
    )
    next_minute_text = (
        "Convencion de ejecucion por minuto cerrado: cada orden usa el VWAP, calculado como "
        "volumen cotizado dividido por volumen base, del primer minuto completo que comienza al "
        "momento de envio o despues. El fill se registra al cierre de ese minuto, cuando precio y "
        "volumen ya son conocidos. La capacidad maxima es 1% del volumen base observado; la "
        "cantidad restante vence al cierre. Una ejecucion parcial produce un solo evento nativo."
        if execution_value == "next_minute_vwap"
        else None
    )
    execution_text = legacy_minute_text or next_minute_text
    h1, h2, h3 = _judgments(run)
    window_scope = (
        " Alcance de la ventana de evaluación por minuto: este informe cubre una sola ventana "
        f"de evaluación independiente [{context.requested_start}, {context.requested_end}). "
        f"El capital se reinicia en {capital} USDT por estrategia al comienzo de esta ventana. "
        "Las demás ventanas por minuto son corridas separadas: no hay una trayectoria continua "
        "de cartera durante los años excluidos y este informe no compara por sí mismo ventanas "
        "por minuto reiniciadas independientemente."
        if minute_execution
        else ""
    )
    h3_text = f"H3: {h3}."
    if gap_method != "strict":
        gap_coverage = (
            "completed_with_approximations"
            if context.status in {"complete", "insolvent"}
            else "incomplete_data"
        )
        window_scope = (
            f" Cartera del intervalo solicitado con {capital} USDT iniciales por estrategia; "
            "no se reinician posiciones ni capital al cambiar de año o régimen. "
            f"Cobertura {gap_coverage}: método `{gap_method}`, opción limitada a los "
            "15 minutos documentados, con disponibilidad al minuto siguiente. "
            "Se conserva la aproximación de funding vigente."
        )
    if minute_execution:
        h3_text += (
            " En las ventanas de evaluación por minuto, la clasificación anterior/posterior a "
            "2024 es descriptiva dentro de esta corrida; un informe de una sola ventana no "
            "establece una comparación entre ventanas reiniciadas independientemente."
        )
    closures = _documented_closures_text(run, "###")
    report = [
        f"# Crypto carry: {label}",
        f"Corrida `{context.run_id}` · escenario `{context.label}` · estado `{context.status}`.",
        (
            "Estos datos sintéticos validan el pipeline únicamente. No son resultados académicos históricos. "
            "Las lecturas de H1–H3 son ilustrativas del funcionamiento del software."
            if synthetic
            else "Los resultados se limitan a la cobertura verificada. Un prefijo incompleto es diagnóstico; "
            "no evalúa toda la muestra solicitada."
        ),
        "## Entrega 3: implementación, muestra y método",
        (
            "Se implementó replay con Nautilus, la máquina de estados compartida por carry condicional y permanente, "
            "ledger decimal, funding, reglas históricas, gestión de margen y deuda, conciliación y evaluación descriptiva. "
            "Las cantidades, decisiones y saldos se conservan en Parquet; este informe y las figuras usan exclusivamente las tablas guardadas."
        ),
        (
            f"Rango solicitado UTC: [{context.requested_start}, {context.requested_end}); historia prevista en configuración desde {context.history_start}. "
            "El extremo final solicitado es exclusivo. Los extremos observados se muestran abajo."
            + window_scope
        ),
        _markdown(
            summary,
            [
                "strategy",
                "funding_filter_enabled",
                "start",
                "end",
                "status",
                "capital_usdt",
                "final_equity_usdt",
                "debt_usdt",
                "reasons",
            ],
        ),
        execution_text
        or (
            "Ejecución con trades y orden temporal de eventos; mark cerrado por minuto; señales después de la disponibilidad "
            "del funding y equity al cierre diario UTC. Ambos activos comparten el capital de cada cartera. "
            "No hay reinicio de posiciones al cambiar de régimen."
        ),
        _markdown(
            params[
                params.parameter.isin(
                    [
                        "capital",
                        "target_fraction",
                        "leverage",
                        "window_hours",
                        "half_life_hours",
                        "horizon_hours",
                        "holding_hours",
                        "signal_delay_seconds",
                        "leg_delay_seconds",
                        "execution_model",
                        "sizing_model",
                        "signal_price_model",
                        "max_volume_participation",
                        "order_timeout_seconds",
                        "slippage",
                        "cost_multiplier",
                        "participation_seconds",
                    ]
                )
            ],
            ["parameter", "value"],
        ),
        "### Cobertura, bloqueos y reglas",
        _markdown(
            _read(run, "data_coverage"),
            [
                "dataset",
                "symbol",
                "market",
                "expected_start_utc",
                "expected_end_utc",
                "observed_start_utc",
                "observed_end_utc",
                "rows",
                "status",
            ],
        ),
        (
            _markdown(_read(run, "data_issues"), ["issue"])
            if not _read(run, "data_issues").empty
            else "No se registraron bloqueos adicionales."
        ),
        *([closures] if closures else []),
        "### Resultados diarios, anuales y por régimen",
        (
            "Las métricas usan calendario real, anualización de 365 días, Sharpe con tasa libre de riesgo cero "
            "y desviación estándar muestral. El primer retorno parte del capital inicial. Las métricas indefinidas "
            "quedan vacías con motivo; se conservan días inactivos, pérdidas e insolvencia. Los días parciales "
            "permanecen en la curva y no se usan como retornos diarios completos."
        ),
        _markdown(
            metrics,
            [
                "strategy",
                "period",
                "start",
                "end",
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
        ),
        "![Equity en USDT](figures/equity.png)",
        "![Drawdown](figures/drawdown.png)",
        "### Hipótesis: lecturas descriptivas",
        f"H1: {h1}.",
        _markdown(
            _read(run, "h1_summary"),
            ["period", "symbol", "observations", "excluded", "mae_ewma", "mae_no_change"],
        ),
        (
            "Ambos pronósticos usan las mismas observaciones válidas; el MAE conjunto da igual peso a cada activo. "
            "El objetivo suma tasas liquidadas después de la señal y hasta el extremo inclusivo del horizonte. "
            "Los horizontes se solapan: estas comparaciones no establecen significancia estadística. "
            "Un menor error predictivo no demuestra rentabilidad."
        ),
        f"H2: {h2}.",
        h3_text,
        _markdown(
            _read(run, "regime_comparison"),
            [
                "period",
                "observed_days",
                "valid_days",
                "coverage_complete",
                "opportunity_mean",
                "eligible_fraction",
                "conditional_cagr",
                "h3_descriptive",
            ],
        ),
        (
            "La oportunidad promedia todos los minutos de días completos, incluyendo ceros, y pondera por igual los activos. "
            "No depende del saldo, posiciones o cooldown de una cartera. Un minuto desconocido excluye el día conjunto. "
            + (
                "La clasificación temporal de esta ventana no enlaza capital, posiciones ni equity "
                "con otra corrida de evaluación."
                if minute_execution
                else "Las diferencias entre regímenes no demuestran causalidad ni prueban la entrada de arbitrajistas."
            )
        ),
        "![Funding pronosticado y realizado](figures/forecast.png)",
        "![Oportunidad diaria](figures/opportunity.png)",
        "### Atribución, costos y cierre de la muestra",
        _markdown(
            _read(run, "attribution_by_asset"),
            [
                "strategy",
                "symbol",
                "spot_pnl_usdt",
                "futures_pnl_usdt",
                "funding_usdt",
                "fees_usdt",
                "liquidation_fees_usdt",
                "total_pnl_usdt",
                "slippage_informational_usdt",
            ],
        ),
        (
            "La suma de spot, perpetuos, funding y comisiones negativas reconcilia con equity menos capital inicial. "
            "El slippage es informativo: ya está en los precios de fill y no se resta otra vez. Spot usa el último "
            + ("open de barra de un minuto conocido" if minute_execution else "trade conocido")
            + " y perpetuos el último mark disponible; no se mezcla un basis de "
            + ("ejecución" if minute_execution else "trade")
            + " con una valuación mark "
            "para forzar la identidad. La comisión de compra spot reduce inventario; se valora al fill. "
            "La conciliación nativa ajusta las unidades base cobradas como comisión porque el ledger económico conserva ese descuento. "
            "Las posiciones finales se valúan sin cierre forzado ni comisiones hipotéticas."
        ),
        "![P&L por componente](figures/pnl_components.png)",
    ]
    positions = pq.read_table(run / "positions.parquet").to_pandas().fillna("")
    finals = positions[positions.snapshot_kind == "final"]
    report.extend(
        [
            _markdown(
                finals,
                [
                    "strategy",
                    "symbol",
                    "timestamp_utc",
                    "state",
                    "spot",
                    "short",
                    "collateral",
                    "dust_spot",
                    "spot_price",
                    "mark_price",
                    "spot_price_age_seconds",
                    "mark_age_seconds",
                ],
            ),
            (
                "El polvo forma parte del inventario y del patrimonio. Una valuación antigua conserva su antigüedad; "
                "no habilita ejecución ni señales frescas. La deuda y cualquier equity no positivo permanecen en las tablas."
            ),
            "## Entrega 4: ejecución, liquidez y análisis crítico",
            _markdown(
                _read(run, "execution_summary"),
                [
                    "strategy",
                    "symbol",
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
                    "risk_events",
                ],
            ),
            _markdown(
                _read(run, "execution_summary"),
                [
                    "strategy",
                    "symbol",
                    "invested_seconds",
                    "unhedged_seconds",
                    "cash_seconds",
                    "cooldown_seconds",
                    "participation_observations",
                    "participation_missing",
                    "participation_p50",
                    "participation_p90",
                    "participation_p95",
                    "participation_max",
                    "native_fill_count",
                    "native_reconciliation_count",
                ],
            ),
            (
                "Los tiempos se expresan en segundos. La exposición sin cobertura se muestra por activo, incluyendo intervalos entre patas. "
                "El tiempo invertido de cartera es la unión temporal de activos expuestos; no la suma. "
                "La participación es cantidad de cada orden frente al volumen reciente del mismo mercado conocido al enviarla, "
                "incluyendo órdenes sin fill; si no existe denominador verificable queda vacía. "
                "Sus cuantiles describen órdenes y no estiman impacto de mercado."
                + (
                    " Para la ejecución por minuto, el denominador es el volumen del minuto "
                    "cerrado anterior, una aproximación del volumen móvil de 60 segundos; el "
                    "volumen no está disponible antes del cierre de la barra."
                    if minute_execution
                    else ""
                )
            ),
            "### Robustez pendiente o ejecutada",
            _markdown(
                _read(run, "robustness_summary"),
                [
                    "label",
                    "strategy",
                    "dimension",
                    "value",
                    "status",
                    "cagr",
                    "sharpe",
                    "coverage_complete",
                    "scenario_evaluated",
                ],
            ),
            (
                "Sin escenarios de costos evaluados en esta corrida individual. Las comparaciones reales de sensibilidad "
                "se guardan por separado y no se reemplaza el baseline ni se elige retrospectivamente el mejor escenario."
            ),
            "![Sensibilidad a costos](figures/cost_sensitivity.png)",
            (
                "AUM: sensibilidad pendiente de ejecutar y validar con reglas aplicables al nocional. "
                "También deben compararse costos, slippage, latencia entre patas, disponibilidad del funding, "
                "ventana, vida media, horizonte, "
                + (
                    "e inicios alternativos"
                    if minute_execution
                    else "ejecución VWAP e inicios alternativos"
                )
                + " en sus propias corridas. "
                "Retornos similares bajo fills completos no demuestran escalabilidad."
            ),
            "### Supuestos y límites",
            (
                "USDT a la par; transferencias inmediatas y gratuitas; ejecución total de cada pata; "
                "mark por minuto; liquidación total; sin ADL, libro completo, impuestos ni insolvencia del exchange. "
                "El baseline no incorpora restricciones de liquidez dentro del fill ni impacto estimado sin datos. "
                "Los fallos artificiales son pruebas de software separadas de la historia observada."
                + (
                    " Las liquidaciones por minuto no modelan una trayectoria intraminuto de "
                    "máximos y mínimos; el riesgo usa el último mark de un minuto cerrado disponible."
                    if minute_execution
                    else ""
                )
            ),
            "### Reproducibilidad y próximos pasos",
            (
                "La configuración efectiva, hashes de código e inputs, versiones, estado y hashes de artefactos están en "
                "`run_manifest.json`; `run_manifest.sha256` controla cambios accidentales del manifiesto. "
                "`source_manifests/` conserva los manifiestos de descarga, procesamiento y cobertura disponibles "
                "al crear la corrida; `input_hashes` identifica los inputs efectivos. "
                "La verificación no certifica autenticidad externa. Los importes Parquet son cadenas decimales exactas; "
                "las figuras convierten copias a punto flotante para dibujar. La regeneración usa las tablas guardadas "
                "y rechaza cambios sobre resultados previos. Completar los bloqueos de cobertura y reglas precede "
                "a cualquier conclusión histórica de muestra completa."
            ),
        ]
    )
    if research:
        audit = json.loads((run / "funding_mark_audit.json").read_text(encoding="utf-8"))
        report.extend(
            [
                "### Declaración del escenario de investigación",
                "Los precios y tasas son observados; los marks sustituidos y las reglas de mercado "
                "son supuestos prescriptos declarados en 2026. Esta corrida no certifica una "
                "reconstrucción histórica. H2 y H3 se evalúan dentro de ese escenario, por separado "
                "de la cobertura histórica estricta. `research_assumptions.json` declara las reglas y "
                "`funding_mark_audit.json` separa los marks validados de los usados, con conteos exactos "
                "y sustituidos. El motor consumió "
                f"{audit['exact_consumed_count']} exactos, {audit['proxy_consumed_count']} proxies "
                f"causales y {audit['warmup_not_required_count']} observaciones de precalentamiento "
                "sin imputación. Son observaciones entregadas al motor y no implican, por sí solas, "
                "pagos de funding en efectivo.",
            ]
        )
    text = "\n\n".join(report) + "\n"
    if research:
        text = text.replace("reglas históricas", "reglas prescriptas declaradas")
    return text


def _render_figures(run: Path, destination: Path, manifest: dict) -> None:
    """Render only saved tables. Metadata and SVG IDs are reproducible."""
    destination.mkdir(parents=True, exist_ok=True)
    context = _read(run, "run_context").iloc[0]
    label = (
        "SINTÉTICO · validación del pipeline"
        if context.data_kind == "synthetic"
        else "HISTÓRICO · cobertura observada"
    )
    if context.data_kind == "historical_assumptions":
        label = "OBSERVADO + SUPUESTOS PRESCRIPTOS"
    daily, summary = _read(run, "equity_daily"), _read(run, "run_summary")
    palettes = ["#2563a6", "#dc741c", "#487b3a", "#884b8d"]
    strategy_labels = {"conditional": "Condicional", "permanent": "Permanente"}
    coverage_label = (
        f"Motor observado: {summary.start.min()} a {summary.end.max()}"
        if not summary.empty
        else f"Rango solicitado: {context.requested_start} a {context.requested_end}"
    )
    with plt.rc_context(
        {
            "svg.hashsalt": manifest["run_id"],
            "svg.fonttype": "none",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    ):

        def make(title, ylabel):
            fig, ax = plt.subplots(figsize=(11.2, 5.8), layout="constrained")
            fig.suptitle(f"{title}\n{label} · {context.status}", fontsize=13)
            ax.set_ylabel(ylabel)
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
            ax.grid(alpha=0.2)
            fig.supxlabel("UTC · " + coverage_label, fontsize=8)
            return fig, ax

        def empty(ax, text="Sin observaciones verificadas"):
            ax.text(0.5, 0.5, text, transform=ax.transAxes, ha="center", va="center", fontsize=13)
            ax.set_xticks([])
            ax.set_yticks([])

        def dates(ax):
            locator = mdates.AutoDateLocator(minticks=3, maxticks=8)
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

        def save(fig, name):
            fig.savefig(destination / f"{name}.png", dpi=160, metadata={"Software": "crypto_carry"})
            fig.savefig(
                destination / f"{name}.svg", metadata={"Date": None, "Creator": "crypto_carry"}
            )
            plt.close(fig)

        for name, title in (
            ("equity", "Patrimonio comparado"),
            ("drawdown", "Caída desde el máximo previo"),
        ):
            fig, ax = make(title, "Equity (USDT)" if name == "equity" else "Drawdown (%)")
            plotted = False
            for color, (strategy, group) in zip(palettes, daily.groupby("strategy", sort=True)):
                group = group.sort_values("time_ns")
                base = summary[summary.strategy == strategy]
                if not len(base) or group.empty:
                    continue
                capital = float(base.iloc[0].capital_usdt)
                x = [pd.Timestamp(base.iloc[0].start)] + list(
                    pd.to_datetime(group.timestamp_utc, utc=True)
                )
                y = np.array([capital] + list(map(float, group.equity)))
                if name == "drawdown":
                    peaks = np.maximum.accumulate(y)
                    y = (y / peaks - 1) * 100
                ax.plot(
                    x, y, label=strategy_labels.get(strategy, strategy), color=color, linewidth=1.8
                )
                plotted = True
            if plotted:
                ax.legend(loc="best")
                dates(ax)
            else:
                empty(ax)
            save(fig, name)

        fig, ax = make("Atribución reconciliada del P&L", "P&L (USDT)")
        components = _read(run, "pnl_components")
        included = components[components.included_in_total.map(_yes).astype(bool)]
        labels = {
            "spot_pnl": "Spot",
            "futures_pnl": "Perpetuos",
            "funding": "Funding",
            "fees": "Comisiones",
            "liquidation_fees": "Liquidación",
        }
        names = list(labels)
        groups = list(included.groupby("strategy", sort=True))
        width = 0.75 / max(1, len(groups))
        for i, (strategy, group) in enumerate(groups):
            amounts = dict(zip(group.component, map(float, group.amount_usdt)))
            ax.bar(
                np.arange(len(names)) + (i - (len(groups) - 1) / 2) * width,
                [amounts.get(name, 0) for name in names],
                width=width,
                label=strategy_labels.get(strategy, strategy),
                color=palettes[i % len(palettes)],
            )
        if groups:
            ax.set_xticks(np.arange(len(names)), [labels[name] for name in names])
            ax.axhline(0, color="#333333", linewidth=0.8)
            ax.legend()
        else:
            empty(ax)
        fig.supxlabel(
            "Slippage informativo excluido: ya está incorporado en los fills\nUTC · "
            + coverage_label,
            fontsize=8,
        )
        save(fig, "pnl_components")

        fig, ax = make("Funding pronosticado y realizado", "Tasa acumulada del horizonte (%)")
        forecast = _read(run, "forecast_evaluation")
        valid = forecast[forecast.horizon_valid.map(_yes).astype(bool)]
        for i, (symbol, group) in enumerate(valid.groupby("symbol", sort=True)):
            x = pd.to_datetime(group.timestamp_utc, utc=True)
            for column, style, description in (
                ("forecast", "-", "EWMA"),
                ("realized", "--", "realizado"),
                ("no_change", ":", "no-change"),
            ):
                ax.plot(
                    x,
                    pd.to_numeric(group[column]) * 100,
                    style,
                    marker=".",
                    color=palettes[i % len(palettes)],
                    label=f"{symbol} {description}",
                )
        if len(valid):
            ax.legend(fontsize=8, ncol=2)
            dates(ax)
            if valid.timestamp_utc.nunique() == 1:
                ax.set_xlim(
                    pd.Timestamp(context.requested_start), pd.Timestamp(context.requested_end)
                )
        else:
            empty(ax)
        save(fig, "forecast")

        fig, ax = make(
            "Oportunidad diaria con igual peso por activo", "Funding esperado elegible (%)"
        )
        opportunity = _read(run, "opportunity_daily")
        valid = opportunity[opportunity.complete.map(_yes).astype(bool)]
        if len(valid):
            x = pd.to_datetime(opportunity.timestamp_utc, utc=True)
            values = pd.to_numeric(opportunity.opportunity, errors="coerce").where(
                opportunity.complete.map(_yes).astype(bool)
            )
            ax.plot(x, values * 100, color=palettes[0], label="Oportunidad", marker=".")
            split = pd.Timestamp("2024-01-01", tz="UTC")
            if x.min() <= split <= x.max():
                ax.axvline(split, color="#555555", linestyle="--", label="Cambio de régimen")
            ax.legend()
            dates(ax)
            if opportunity.timestamp_utc.nunique() == 1:
                ax.set_xlim(
                    pd.Timestamp(context.requested_start), pd.Timestamp(context.requested_end)
                )
        else:
            empty(ax)
        save(fig, "opportunity")

        fig, ax = make("Sensibilidad a costos", "Métrica de cartera")
        empty(ax, "Sin escenarios de costos evaluados")
        save(fig, "cost_sensitivity")


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
        _render_figures(run, run / "figures", manifest)
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


def regenerate_report(run_dir: Path) -> Path:
    """Rebuild from saved tables; verify identical bytes or fail without overwriting.

    Missing derived files can be restored only when their rebuilt hashes equal
    the original manifest. Modified source tables or existing files are rejected.
    """
    run = Path(run_dir).resolve()
    derived = {"report.md"} | {
        f"figures/{name}.{ext}" for name in FIGURES for ext in ("png", "svg")
    }
    verification = verify_run(run)
    forbidden = [
        item
        for item in verification["mismatches"]
        if item["path"] not in derived or item["reason"] != "missing"
    ]
    if forbidden:
        raise ValueError(f"Immutable run checksum or artifact validation failed: {forbidden}")
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="crypto-carry-report-") as directory:
        staging = Path(directory)
        _render_figures(run, staging / "figures", manifest)
        (staging / "report.md").write_text(_report_text(run), encoding="utf-8")
        for name in sorted(derived):
            if _hash(staging / name) != manifest["output_hashes"].get(name):
                raise ValueError(
                    f"Immutable report would change {name}; use a new run or report version"
                )
        for name in sorted(derived):
            target = _safe_artifact(run, name)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write((staging / name).read_bytes())
    result = verify_run(run)
    if not result["valid"]:
        raise ValueError(f"Regenerated artifact checksum validation failed: {result['mismatches']}")
    return run / "report.md"

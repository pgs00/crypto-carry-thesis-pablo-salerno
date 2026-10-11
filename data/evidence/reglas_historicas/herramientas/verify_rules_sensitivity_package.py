"""Portable, offline, read-only checks for the preliminary rules-sensitivity package.

Only the Python standard library is imported. No trading engine, Git state,
market-data drive, or saved Python session is needed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path, PurePosixPath, PureWindowsPath

D = Decimal
SECOND = 1_000_000_000
DAY = 86_400 * SECOND
SYMBOLS = ("BTCUSDT", "ETHUSDT")
TOLERANCE = D("1E-8")
MANIFEST = "manifiesto_paquete.json"
MANIFEST_SIDECAR = "manifiesto_paquete.sha256"
COMPARATORS = {
    "BASE_E3": None,
    "BTC_PROMO_REALIZADA": "BASE_E3",
    "BTC_PROMO_DECISION": "BTC_PROMO_REALIZADA",
    "FUT4_REALIZADA": "BASE_E3",
    "FUT4_DECISION": "FUT4_REALIZADA",
    "MARGEN_2X": "BASE_E3",
}
COMPONENTS = (
    "spot_pnl_usdt",
    "futures_pnl_usdt",
    "funding_usdt",
    "fees_usdt",
    "liquidation_fees_usdt",
    "slippage_informational_usdt",
)
SPLIT_COMPONENTS = (
    "spot_realized_pnl_usdt",
    "spot_unrealized_pnl_usdt",
    "futures_realized_pnl_usdt",
    "futures_unrealized_pnl_usdt",
)


def decimal(value, field="number"):
    if value is None or value == "" or isinstance(value, bool):
        raise ValueError(f"Missing or invalid decimal: {field}")
    try:
        number = D(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal: {field}={value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"Nonfinite decimal: {field}={value!r}")
    return number


def yes(value):
    if value in (True, "True", "true", "1", 1):
        return True
    if value in (False, "False", "false", "0", 0):
        return False
    raise ValueError(f"Invalid boolean: {value!r}")


def timestamp(value):
    match = re.fullmatch(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?Z", value)
    if not match:
        raise ValueError(f"Expected exact UTC timestamp: {value!r}")
    date = datetime.fromisoformat(match[1]).replace(tzinfo=UTC)
    seconds = int((date - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds())
    return seconds * SECOND + int((match[2] or "").ljust(9, "0"))


def iso(value):
    seconds, fraction = divmod(int(value), SECOND)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S") + f".{fraction:09d}Z"


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"Missing or duplicate CSV columns: {path}")
        rows = list(reader)
        if any(None in row for row in rows):
            raise ValueError(f"Malformed CSV row: {path}")
        return rows


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key {key}: {path}")
            result[key] = value
        return result

    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def safe_path(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError(f"Path must be a relative POSIX member: {relative!r}")
    member = PurePosixPath(relative)
    if (
        member.is_absolute()
        or PureWindowsPath(relative).drive
        or ".." in member.parts
        or ":" in relative
        or member.as_posix() != relative
    ):
        raise ValueError(f"Path escapes or is noncanonical: {relative!r}")
    root = Path(root).resolve()
    resolved = (root / member).resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise ValueError(f"Path escapes root: {relative!r}")
    return resolved


def economic_digest(rows, ignored=("run_id",)):
    normalized = [{k: v for k, v in row.items() if k not in ignored} for row in rows]
    records = [
        json.dumps(row, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
        for row in normalized
    ]
    return hashlib.sha256("\n".join(sorted(records)).encode("utf-8")).hexdigest()


def financial_daily(rows, capital):
    """Difference cumulative Decimal attribution, preserving carried inventory."""
    previous = {symbol: dict.fromkeys((*COMPONENTS, *SPLIT_COMPONENTS), D(0)) for symbol in SYMBOLS}
    previous_equity = decimal(capital)
    times = [int(row["time_ns"]) for row in rows]
    if len(times) != len(set(times)):
        raise ValueError("Duplicate daily equity timestamp")
    daily, assets = [], []
    with localcontext() as context:
        context.prec = 50
        for row in sorted(rows, key=lambda item: int(item["time_ns"])):
            common = dict(time_ns=int(row["time_ns"]), date=iso(int(row["time_ns"]))[:10])
            totals = dict.fromkeys((*COMPONENTS, *SPLIT_COMPONENTS), D(0))
            deployed = gross = collateral = position_value = D(0)
            for symbol in SYMBOLS:

                def value(field):
                    key = f"{symbol}_{field}"
                    return decimal(row.get(key), key)

                spot, short = value("spot"), value("short")
                spot_value = spot * value("spot_price")
                unrealized_spot = spot_value - value("spot_cost") if spot else D(0)
                unrealized_future = short * (value("average") - value("mark"))
                realized_spot, realized_future = value("realized_spot"), value("realized_futures")
                cumulative = dict(
                    zip(
                        (*COMPONENTS, *SPLIT_COMPONENTS),
                        (
                            realized_spot + unrealized_spot,
                            realized_future + unrealized_future,
                            value("funding"),
                            -value("fees"),
                            -value("liquidation_fees"),
                            value("slippage"),
                            realized_spot,
                            unrealized_spot,
                            realized_future,
                            unrealized_future,
                        ),
                    )
                )
                changes = {key: cumulative[key] - previous[symbol][key] for key in cumulative}
                assets.append(
                    dict(
                        common,
                        symbol=symbol,
                        **changes,
                        net_pnl_usdt=sum((changes[k] for k in COMPONENTS[:-1]), D(0)),
                    )
                )
                previous[symbol] = cumulative
                for key, value_change in changes.items():
                    totals[key] += value_change
                collateral += value("collateral")
                deployed += spot_value + value("collateral")
                gross += spot_value + short * value("mark")
                position_value += spot_value + value("collateral") + unrealized_future
            equity = decimal(row.get("equity"), "equity")
            pnl = equity - previous_equity
            residual = pnl - sum((totals[key] for key in COMPONENTS[:-1]), D(0))
            if abs(residual) > TOLERANCE:
                raise ValueError(
                    f"Daily accounting does not reconcile {common['date']}: {residual}"
                )
            cash = decimal(row.get("free_spot"), "free_spot") + decimal(
                row.get("free_futures"), "free_futures"
            )
            debt = decimal(row.get("debt"), "debt")
            balance_residual = equity - (cash - debt + position_value)
            if abs(balance_residual) > TOLERANCE:
                raise ValueError(
                    f"Daily cash/inventory valuation balance mismatch {common['date']}: {balance_residual}"
                )
            daily.append(
                dict(
                    common,
                    equity_usdt=equity,
                    starting_equity_usdt=previous_equity,
                    net_pnl_usdt=pnl,
                    **totals,
                    reconciliation_residual_usdt=residual,
                    daily_return=equity / previous_equity - 1 if previous_equity > 0 else None,
                    capital_deployed_usdt=deployed,
                    capital_utilization=deployed / equity if equity > 0 else None,
                    gross_exposure_usdt=gross,
                    collateral_usdt=collateral,
                    free_cash_usdt=cash,
                    debt_usdt=debt,
                    balance_residual_usdt=balance_residual,
                    partial_day=yes(row.get("partial_day", False)),
                )
            )
            previous_equity = equity
    return daily, assets


def check_manifest(package):
    package = Path(package).resolve()
    manifest_path = package / MANIFEST
    if not manifest_path.is_file():
        raise ValueError(f"missing package manifest: {manifest_path}")
    sidecar = package / MANIFEST_SIDECAR
    if not sidecar.is_file() or sidecar.read_text(encoding="ascii").strip() != sha256(
        manifest_path
    ):
        raise ValueError("Package manifest hash mismatch or missing sidecar")
    manifest = read_json(manifest_path)
    if manifest.get("schema") != "rules_sensitivity_package_v1":
        raise ValueError("Unexpected package manifest schema")
    seen = set()
    for member in manifest.get("members", []):
        name = member["path"]
        if name in seen or name in {MANIFEST, MANIFEST_SIDECAR}:
            raise ValueError(f"Duplicate or self-referential manifest member: {name}")
        seen.add(name)
        path = safe_path(package, name)
        if not path.is_file():
            raise ValueError(f"missing manifest member: {name}")
        if path.stat().st_size != member["size"]:
            raise ValueError(f"Manifest size mismatch: {name}")
        if sha256(path) != member["sha256"]:
            raise ValueError(f"Manifest hash mismatch: {name}")
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    extra = actual - seen - {MANIFEST, MANIFEST_SIDECAR}
    if extra:
        raise ValueError(f"unlisted package members: {sorted(extra)}")
    return dict(members_checked=len(seen), manifest_sha256=sha256(manifest_path))


RUN_REQUIRED = {
    "effective_config.toml",
    "equity_daily.csv",
    "run_summary.csv",
    "pnl_components.csv",
    "metrics.csv",
    "forecast_evaluation.csv",
    "h1_summary.csv",
    "opportunity_daily.csv",
    "execution_summary.csv",
    "signals.parquet",
    "ledger.parquet",
    "positions.parquet",
    "fills.parquet",
    "orders.parquet",
    "risk_events.parquet",
    "funding_payments.parquet",
}
REPORT_REQUIRED = {
    "registro_corridas.csv",
    "metricas_cartera_periodo.csv",
    "diario_carteras.csv",
    "componentes_por_activo_periodo.csv",
    "deltas.csv",
    "h1_invariancia.csv",
    "h1_resumen.csv",
    "h2.csv",
    "h3_diario.csv",
    "h3_regimen.csv",
    "h3_invariancia.csv",
    "exposicion_periodo.csv",
    "eventos_periodo.csv",
    "conciliaciones.csv",
    "reporte.md",
}
SUCCESS = {"ejecutado", "reutilizado_verificado"}


def load_index(package):
    index = read_json(Path(package) / "indice_corridas.json")
    if index.get("schema") != "rules_sensitivity_batch_v1" or not isinstance(
        index.get("runs"), list
    ):
        raise ValueError("Invalid run index schema")
    seen, ids = set(), set()
    for item in index["runs"]:
        key = (item.get("scenario"), item.get("strategy"))
        if key in seen:
            raise ValueError(f"Duplicate scenario/strategy: {key}")
        if key[0] not in COMPARATORS or key[1] not in {"conditional", "permanent"}:
            raise ValueError(f"Unknown scenario/strategy: {key}")
        seen.add(key)
        if item.get("status") not in SUCCESS | {"fallido", "bloqueado"}:
            raise ValueError(f"Invalid run status: {key}")
        if item["status"] in SUCCESS:
            if not item.get("run_id") or item["run_id"] in ids:
                raise ValueError(f"Missing or duplicate run_id: {key}")
            ids.add(item["run_id"])
            if item.get("path") != f"corridas/{item['run_id']}":
                raise ValueError(f"Path must identify the packaged run: {key}")
            safe_path(package, item["path"])
        elif not (item.get("reason") or item.get("motivo")):
            raise ValueError(f"Failed/blocked run requires a reason: {key}")
    expected = {
        (scenario, strategy)
        for scenario in COMPARATORS
        for strategy in ("conditional", "permanent")
    }
    if seen != expected:
        raise ValueError(
            f"Run index must retain all 12 statuses; missing {sorted(expected - seen)}"
        )
    return index["runs"]


def check_run(package, item):
    run = safe_path(package, item["path"])
    manifest_path = run / "run_manifest.json"
    expected = item.get("manifest_sha256")
    if not manifest_path.is_file() or sha256(manifest_path) != expected:
        raise ValueError(f"Run manifest hash mismatch or missing: {item['run_id']}")
    sidecar = run / "run_manifest.sha256"
    if not sidecar.is_file() or sidecar.read_text(encoding="ascii").strip() != expected:
        raise ValueError(f"Run manifest sidecar mismatch: {item['run_id']}")
    manifest = read_json(manifest_path)
    if manifest.get("run_id") != item["run_id"] or not manifest.get("artifacts_complete"):
        raise ValueError(f"Run identity/artifacts incomplete: {item['run_id']}")
    if manifest.get("status") not in {"complete", "insolvent"}:
        raise ValueError(
            f"Run marked successful but engine is {manifest.get('status')}: {item['run_id']}"
        )
    if item.get("engine_status") != manifest.get("status"):
        raise ValueError(f"Run engine_status mismatch: {item['run_id']}")
    strategies = [r["strategy"] for r in manifest.get("strategies", [])]
    if strategies != [item["strategy"]]:
        raise ValueError(f"Run must hold one independent portfolio: {item['run_id']}")
    hashes = manifest.get("output_hashes", {})
    if not RUN_REQUIRED <= set(hashes):
        raise ValueError(
            f"Missing required run artifacts {item['run_id']}: {sorted(RUN_REQUIRED - set(hashes))}"
        )
    for name, digest in hashes.items():
        member = safe_path(run, name)
        if not member.is_file() or sha256(member) != digest:
            raise ValueError(f"Missing or changed run artifact: {item['run_id']}/{name}")
    actual = {p.relative_to(run).as_posix() for p in run.rglob("*") if p.is_file()}
    if actual != set(hashes) | {"run_manifest.json", "run_manifest.sha256"}:
        raise ValueError(f"Run has unlisted members: {item['run_id']}")
    code_files = manifest.get("code_files", {})
    if not code_files and (
        (Path(package) / "codigo_base").is_dir() or (Path(package) / "codigo_ejecutado").is_dir()
    ):
        raise ValueError(f"Missing code_files in a package with source snapshots: {item['run_id']}")
    if code_files:
        aggregate = hashlib.sha256(
            json.dumps(
                code_files,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        if aggregate != manifest.get("code_hash"):
            raise ValueError(f"Aggregate code_hash mismatch: {item['run_id']}")
        snapshot = Path(package) / (
            "codigo_base" if item["scenario"] == "BASE_E3" else "codigo_ejecutado"
        )
        for name, digest in code_files.items():
            path = safe_path(snapshot, name)
            if not path.is_file() or sha256(path) != digest:
                raise ValueError(
                    f"Missing or changed code snapshot: {snapshot.name}/{name} for {item['run_id']}"
                )
    return manifest


def periods(config):
    start, end = timestamp(config["start"]), timestamp(config["end"])
    if start >= end or start % DAY or end % DAY:
        raise ValueError("Report requires a positive interval bounded by UTC midnights")
    split = timestamp("2024-01-01T00:00:00Z")
    candidates = [
        ("full", start, end),
        ("2022-2023", start, min(end, split)),
        ("2024+", max(start, split), end),
    ]
    for year in range(int(config["start"][:4]), int(config["end"][:4]) + 1):
        candidates.append(
            (
                str(year),
                max(start, timestamp(f"{year}-01-01T00:00:00Z")),
                min(end, timestamp(f"{year + 1}-01-01T00:00:00Z")),
            )
        )
    return [(name, lower, upper) for name, lower, upper in candidates if lower < upper]


def assert_close(actual, expected, field, tolerance=TOLERANCE):
    if actual in (None, "") or expected in (None, ""):
        if actual not in (None, "") or expected not in (None, ""):
            raise ValueError(f"Undefined value mismatch: {field}")
    elif abs(decimal(actual, field) - decimal(expected, field)) > tolerance:
        raise ValueError(f"Arithmetic/reconciliation mismatch: {field}: {actual} != {expected}")


def h3_source(package, item, items):
    source_id, status, reason = item["run_id"], "observado_en_corrida", ""
    aliases_path = Path(package) / "h3_procedencia.json"
    aliases = read_json(aliases_path).get("aliases", {}) if aliases_path.is_file() else {}
    if item["run_id"] in aliases:
        alias = aliases[item["run_id"]]
        source_id = alias["source_run_id"]
        source = next(
            (x for x in items if x.get("run_id") == source_id and x["status"] in SUCCESS), None
        )
        if (
            item["scenario"] != "BASE_E3"
            or not source
            or source["scenario"] not in {"FUT4_REALIZADA", "BTC_PROMO_REALIZADA", "MARGEN_2X"}
            or source["strategy"] != item["strategy"]
            or alias.get("status") != "derivado_invariancia_verificada"
        ):
            raise ValueError(f"Invalid H3 reconstruction alias: {item['run_id']}")
        for name in ("forecast_evaluation.csv", "opportunity_daily.csv"):
            first = read_csv(safe_path(package, item["path"]) / name)
            other = read_csv(safe_path(package, source["path"]) / name)
            if economic_digest(first) != economic_digest(other):
                raise ValueError(f"H3 alias lacks exact invariance: {item['run_id']}/{name}")
        status, reason = alias["status"], alias.get("reason", "")
    path = safe_path(package, f"h3_minutos/{source_id}.csv")
    return path, source_id, status, reason


def period_financials(daily, periods):
    output = []
    for label, start, end in periods:
        selected = [r for r in daily if start <= r["time_ns"] < end]
        expected = list(range(start + DAY - 1, end, DAY))
        if (
            [r["time_ns"] for r in selected] != expected
            or any(r["partial_day"] for r in selected)
            or not selected
        ):
            raise ValueError(f"Incomplete daily coverage: {label}")
        opening, final = selected[0]["starting_equity_usdt"], selected[-1]["equity_usdt"]
        equities = [opening] + [r["equity_usdt"] for r in selected]
        returns = [r["daily_return"] for r in selected]
        positive = all(equity > 0 for equity in equities)
        reason = "" if positive else "nonpositive equity or insolvency"
        cagr = (
            math.expm1(math.log(float(final / opening)) * 365 * DAY / (end - start))
            if positive
            else None
        )
        sharpe = volatility = None
        if positive:
            if len(returns) < 2:
                reason = "fewer than two daily returns"
            else:
                mean = sum(returns, D(0)) / len(returns)
                variance = sum(((x - mean) ** 2 for x in returns), D(0)) / (len(returns) - 1)
                volatility = math.sqrt(float(variance) * 365)
                if variance == 0:
                    reason = "zero sample volatility"
                else:
                    sharpe = float(mean) / math.sqrt(float(variance)) * math.sqrt(365)
        peak, peak_time, drawdown, duration = opening, start - 1, D(0), D(0)
        for row in selected:
            value, moment = row["equity_usdt"], row["time_ns"]
            if value >= peak:
                peak, peak_time = value, moment
            elif peak > 0:
                drawdown = min(drawdown, value / peak - 1)
                duration = max(duration, D(moment - peak_time) / DAY)
        row = dict(
            period=label,
            start_utc=iso(start),
            end_exclusive_utc=iso(end),
            days=len(selected),
            coverage_complete=True,
            starting_equity_usdt=opening,
            final_equity_usdt=final,
            net_pnl_usdt=final - opening,
            net_return=final / opening - 1 if opening > 0 else None,
            cagr=cagr,
            cagr_reason="" if positive else "nonpositive equity or insolvency",
            sharpe=sharpe,
            sharpe_reason=reason,
            annual_volatility=volatility,
            max_drawdown=drawdown if opening > 0 else None,
            max_drawdown_days=duration,
        )
        for key in (*COMPONENTS, *SPLIT_COMPONENTS):
            row[key] = sum((r[key] for r in selected), D(0))
        row["reconciliation_residual_usdt"] = row["net_pnl_usdt"] - sum(
            (row[key] for key in COMPONENTS[:-1]), D(0)
        )
        for key in (
            "capital_deployed_usdt",
            "capital_utilization",
            "gross_exposure_usdt",
            "collateral_usdt",
            "debt_usdt",
        ):
            values = [r[key] for r in selected]
            row[f"{key}_daily_mean"] = (
                sum(values, D(0)) / len(values) if None not in values else None
            )
            row[f"{key}_daily_max"] = max(values) if None not in values else None
        output.append(row)
    return output


def h3_from_assets(rows):
    groups = defaultdict(dict)
    for row in rows:
        day, symbol = row["date"], row["symbol"]
        if symbol not in SYMBOLS or symbol in groups[day]:
            raise ValueError(f"Unknown or duplicate H3 asset: {day} {symbol}")
        total, known, unknown, eligible = (
            int(row[key])
            for key in (
                "minutos_totales",
                "minutos_conocidos",
                "minutos_desconocidos",
                "minutos_elegibles",
            )
        )
        if (
            min(total, known, unknown, eligible) < 0
            or known + unknown != total
            or eligible > known
            or total > 1440
        ):
            raise ValueError(f"Invalid H3 minute counts: {day} {symbol}")
        groups[day][symbol] = dict(
            total=total,
            known=known,
            unknown=unknown,
            eligible=eligible,
            value=decimal(row["suma_forecast_elegible"]),
        )
    output = []
    for day, assets in sorted(groups.items()):
        complete = set(assets) == set(SYMBOLS) and all(r["known"] == 1440 for r in assets.values())
        output.append(
            dict(
                date=day,
                time_ns=timestamp(day + "T00:00:00Z") + DAY - 1,
                complete=complete,
                opportunity=sum((r["value"] / 1440 for r in assets.values()), D(0)) / 2
                if complete
                else None,
                eligible_fraction=sum((D(r["eligible"]) / 1440 for r in assets.values()), D(0)) / 2
                if complete
                else None,
                observed_asset_minutes=sum(r["total"] for r in assets.values()),
                unknown_asset_minutes=sum(r["unknown"] for r in assets.values()),
                reason="" if complete else "missing minute, asset, or required data",
            )
        )
    return output


def h1_summaries(rows, periods):
    result = []
    for period, lower, upper in periods:
        asset_rows = []
        for symbol in SYMBOLS:
            selected = [
                r for r in rows if r["symbol"] == symbol and lower <= int(r["time_ns"]) < upper
            ]
            valid = [r for r in selected if yes(r["horizon_valid"])]
            exclusions = defaultdict(int)
            for row in selected:
                if not yes(row["horizon_valid"]):
                    exclusions[row["reason"]] += 1
            asset_rows.append(
                dict(
                    period=period,
                    symbol=symbol,
                    observations=len(valid),
                    excluded=len(selected) - len(valid),
                    exclusion_reasons=json.dumps(exclusions, sort_keys=True),
                    weight=D("0.5"),
                    mae_ewma=sum((decimal(r["absolute_error_ewma"]) for r in valid), D(0))
                    / len(valid)
                    if valid
                    else None,
                    mae_no_change=sum((decimal(r["absolute_error_no_change"]) for r in valid), D(0))
                    / len(valid)
                    if valid
                    else None,
                )
            )
        result.extend(asset_rows)
        result.append(
            dict(
                period=period,
                symbol="EQUAL_WEIGHT",
                observations=sum(r["observations"] for r in asset_rows),
                excluded=sum(r["excluded"] for r in asset_rows),
                exclusion_reasons="see asset rows",
                weight=D(1),
                **{
                    key: sum((r[key] for r in asset_rows), D(0)) / 2
                    if all(r[key] is not None for r in asset_rows)
                    else None
                    for key in ("mae_ewma", "mae_no_change")
                },
            )
        )
    return result


def verify_package(package):
    package = Path(package).resolve()
    result = check_manifest(package)
    items = load_index(package)
    comparison = package / "comparacion"
    for name in REPORT_REQUIRED:
        if not (comparison / name).is_file():
            raise ValueError(f"missing required report file: comparacion/{name}")
    registry = read_csv(comparison / "registro_corridas.csv")
    registered = {(item["scenario"], item["strategy"]): item for item in items}
    registry_keys = [(row["scenario"], row["strategy"]) for row in registry]
    if len(registry_keys) != len(set(registry_keys)) or set(registry_keys) != set(registered):
        raise ValueError("Registry scenario/portfolio mismatch")
    for row in registry:
        item = registered[(row["scenario"], row["strategy"])]
        for key in ("status", "engine_status", "run_id", "path", "manifest_sha256"):
            if row[key] != item.get(key, ""):
                raise ValueError(f"Registry {key} mismatch: {item['scenario']}/{item['strategy']}")
    metrics = read_csv(comparison / "metricas_cartera_periodo.csv")
    for row in metrics:
        item = registered.get((row["scenario"], row["strategy"]))
        if not item or item["status"] not in SUCCESS or row["run_id"] != item["run_id"]:
            raise ValueError("Unregistered financial result or run identity mismatch")
    metric_keys = [(r["scenario"], r["strategy"], r["period"]) for r in metrics]
    if len(metric_keys) != len(set(metric_keys)):
        raise ValueError("Duplicate report metric period")
    daily_export = read_csv(comparison / "diario_carteras.csv")
    h3_export = read_csv(comparison / "h3_diario.csv")
    h3_regimes = read_csv(comparison / "h3_regimen.csv")
    h3_checks = read_csv(comparison / "h3_invariancia.csv")
    h1_export = read_csv(comparison / "h1_resumen.csv")
    run_data = {}
    h3_data = {}
    checked_days = checked_periods = checked_outputs = checked_code = 0
    for item in items:
        selected_metrics = [
            r
            for r in metrics
            if r["scenario"] == item["scenario"] and r["strategy"] == item["strategy"]
        ]
        if item["status"] not in SUCCESS:
            if selected_metrics:
                raise ValueError(
                    f"Failed/blocked run reported as financial results: {item['scenario']}"
                )
            continue
        manifest = check_run(package, item)
        checked_outputs += len(manifest["output_hashes"])
        checked_code += len(manifest.get("code_files", {}))
        run = safe_path(package, item["path"])
        raw = read_csv(run / "equity_daily.csv")
        if any(
            r.get("run_id") != item["run_id"] or r.get("strategy") != item["strategy"] for r in raw
        ):
            raise ValueError(f"Daily identity mismatch: {item['run_id']}")
        daily, _ = financial_daily(raw, decimal(manifest["config"]["capital"]))
        run_data[item["run_id"]] = (item, manifest, daily)
        checked_days += len(daily)
        export = [r for r in daily_export if r["run_id"] == item["run_id"]]
        if len(export) != len(daily):
            raise ValueError(f"Daily export length mismatch: {item['run_id']}")
        for stored, expected in zip(export, daily):
            if int(stored["time_ns"]) != expected["time_ns"]:
                raise ValueError(f"Daily export timestamp mismatch: {item['run_id']}")
            for key in (
                "equity_usdt",
                "starting_equity_usdt",
                "net_pnl_usdt",
                *COMPONENTS,
                *SPLIT_COMPONENTS,
            ):
                assert_close(stored.get(key), expected[key], f"{item['run_id']} daily {key}")
        expected_periods = periods(manifest["config"])
        recomputed_metrics = {r["period"]: r for r in period_financials(daily, expected_periods)}
        if {r["period"] for r in selected_metrics} != {p[0] for p in expected_periods}:
            raise ValueError(f"Missing report periods: {item['run_id']}")
        for label, lower, upper in expected_periods:
            row = next(r for r in selected_metrics if r["period"] == label)
            if row["run_id"] != item["run_id"]:
                raise ValueError(f"Metric run identity mismatch: {item['run_id']}")
            subset = [r for r in daily if lower <= r["time_ns"] < upper]
            expected_times = list(range(lower + DAY - 1, upper, DAY))
            if [r["time_ns"] for r in subset] != expected_times or any(
                r["partial_day"] for r in subset
            ):
                raise ValueError(f"Incomplete daily coverage: {item['run_id']}/{label}")
            opening, closing = subset[0]["starting_equity_usdt"], subset[-1]["equity_usdt"]
            assert_close(row["starting_equity_usdt"], opening, "starting_equity_usdt")
            assert_close(row["final_equity_usdt"], closing, "final_equity_usdt")
            assert_close(row["net_pnl_usdt"], closing - opening, "net_pnl_usdt")
            assert_close(
                row["net_return"], closing / opening - 1 if opening > 0 else None, "net_return"
            )
            for key in (*COMPONENTS, *SPLIT_COMPONENTS):
                assert_close(row[key], sum((r[key] for r in subset), D(0)), key)
            assert_close(
                row["net_pnl_usdt"],
                sum((decimal(row[k]) for k in COMPONENTS[:-1]), D(0)),
                "period reconciliation",
            )
            expected_metric = recomputed_metrics[label]
            for key, expected in expected_metric.items():
                if (
                    isinstance(expected, (D, float, int))
                    and not isinstance(expected, bool)
                    or expected is None
                ):
                    assert_close(row.get(key), expected, f"metric {item['run_id']}/{label}/{key}")
            for key in ("cagr_reason", "sharpe_reason"):
                if row[key] != expected_metric[key]:
                    raise ValueError(f"Metric reason mismatch: {item['run_id']}/{label}/{key}")
            checked_periods += 1
        summary = read_csv(run / "run_summary.csv")
        if len(summary) != 1:
            raise ValueError(f"Expected one run_summary portfolio: {item['run_id']}")
        assert_close(
            summary[0]["final_equity_usdt"], daily[-1]["equity_usdt"], "run_summary equity"
        )
        components = read_csv(run / "pnl_components.csv")
        included = sum(
            (decimal(r["amount_usdt"]) for r in components if yes(r["included_in_total"])), D(0)
        )
        assert_close(
            included,
            daily[-1]["equity_usdt"] - decimal(manifest["config"]["capital"]),
            "archived components",
        )
        h3_path, source_id, provenance, _ = h3_source(package, item, items)
        if not h3_path.is_file():
            raise ValueError(f"Missing H3 per-asset minute evidence: {h3_path}")
        source_rows = read_csv(h3_path)
        if any(r.get("run_id") != source_id for r in source_rows):
            raise ValueError(f"H3 source identity mismatch: {h3_path}")
        rebuilt = {r["date"]: r for r in h3_from_assets(source_rows)}
        native_rows = read_csv(run / "opportunity_daily.csv")
        native = {r["date"]: r for r in native_rows}
        exported = [r for r in h3_export if r["run_id"] == item["run_id"]]
        if (
            len(exported) != len(rebuilt)
            or len(native) != len(native_rows)
            or len({r["date"] for r in exported}) != len(exported)
            or {r["date"] for r in exported} != set(rebuilt)
            or set(native) != set(rebuilt)
        ):
            raise ValueError(f"H3 duplicate/missing day: {item['run_id']}")
        for row in exported:
            expected = rebuilt[row["date"]]
            archived = native[row["date"]]
            if row["source_run_id"] != source_id or row["provenance"] != provenance:
                raise ValueError(f"H3 provenance mismatch: {item['run_id']}")
            if not yes(row["per_asset_minutes_verified"]):
                raise ValueError(f"H3 per-asset check omitted: {item['run_id']}")
            if (
                yes(row["complete"]) != expected["complete"]
                or yes(archived["complete"]) != expected["complete"]
            ):
                raise ValueError(
                    f"H3 unknown minute/completeness mismatch: {item['run_id']}/{row['date']}"
                )
            for key in ("opportunity", "eligible_fraction"):
                assert_close(row[key], expected[key], f"H3 exported {key}", D("1E-14"))
                assert_close(archived[key], expected[key], f"H3 original {key}", D("1E-14"))
            for key in ("observed_asset_minutes", "unknown_asset_minutes", "time_ns"):
                assert_close(row[key], expected[key], f"H3 {key}", D(0))
        h3_data[item["run_id"]] = economic_digest(native_rows)
        regime_rows = [r for r in h3_regimes if r["run_id"] == item["run_id"]]
        if len(regime_rows) != len(expected_periods):
            raise ValueError(f"H3 missing regime: {item['run_id']}")
        for label, lower, upper in expected_periods:
            matching = [r for r in regime_rows if r["period"] == label]
            if len(matching) != 1:
                raise ValueError(f"H3 missing/duplicate regime: {item['run_id']}/{label}")
            row = matching[0]
            valid = [r for r in rebuilt.values() if lower <= r["time_ns"] < upper and r["complete"]]
            for column, key in (
                ("opportunity_mean", "opportunity"),
                ("eligible_fraction", "eligible_fraction"),
            ):
                expected = sum((r[key] for r in valid), D(0)) / len(valid) if valid else None
                assert_close(row[column], expected, f"H3 regime {column}", D("1E-14"))
            assert_close(row["valid_days"], len(valid), "H3 valid days", D(0))
            if yes(row["coverage_complete"]) != (len(valid) == (upper - lower) // DAY):
                raise ValueError("H3 regime completeness mismatch")
            assert_close(
                row["portfolio_cagr"], recomputed_metrics[label]["cagr"], "H3 portfolio CAGR"
            )
    by_key = {(r["scenario"], r["strategy"], r["period"]): r for r in metrics}
    for row in read_csv(comparison / "deltas.csv"):
        scenario, strategy, period = (row[k] for k in ("scenario", "strategy", "period"))
        if row["comparator"] != COMPARATORS[scenario]:
            raise ValueError(f"Wrong delta comparator: {scenario}")
        current = by_key[(scenario, strategy, period)]
        other = by_key.get((row["comparator"], strategy, period), {})
        if row["run_id"] != current["run_id"] or row["comparator_run_id"] != other.get(
            "run_id", ""
        ):
            raise ValueError("Delta run identity mismatch")
        a, b = current.get(row["metric"]), other.get(row["metric"])
        expected = decimal(a) - decimal(b) if a not in (None, "") and b not in (None, "") else None
        assert_close(row["delta"], expected, f"delta {scenario}/{row['metric']}")
    for row in read_csv(comparison / "h2.csv"):
        cond = by_key.get((row["scenario"], "conditional", row["period"]), {})
        perm = by_key.get((row["scenario"], "permanent", row["period"]), {})
        if row["conditional_run_id"] != cond.get("run_id", "") or row[
            "permanent_run_id"
        ] != perm.get("run_id", ""):
            raise ValueError("H2 must compare portfolios within the same scenario")
        a, b = cond.get("sharpe"), perm.get("sharpe")
        expected = decimal(a) - decimal(b) if a not in (None, "") and b not in (None, "") else None
        assert_close(row["sharpe_difference"], expected, "H2 Sharpe difference")
        if expected is None and row["verdict"] != "no_concluyente":
            raise ValueError("Undefined H2 Sharpe must stay inconclusive")
    h1 = read_csv(comparison / "h1_invariancia.csv")
    if len(h1) != len(run_data):
        raise ValueError("Missing H1 invariance runs")
    for row in h1:
        item, manifest, _ = run_data[row["run_id"]]
        if decimal(row["btc_weight"]) != D("0.5") or decimal(row["eth_weight"]) != D("0.5"):
            raise ValueError(f"H1 weight mismatch: {item['run_id']}")
        base = next(
            x for x in items if x["scenario"] == "BASE_E3" and x["strategy"] == item["strategy"]
        )
        for artifact, field in (
            ("forecast_evaluation.csv", "forecast_evaluation_sha256"),
            ("h1_summary.csv", "h1_summary_sha256"),
        ):
            digest = economic_digest(read_csv(safe_path(package, item["path"]) / artifact))
            base_digest = economic_digest(read_csv(safe_path(package, base["path"]) / artifact))
            if digest != base_digest or row[field] != digest:
                raise ValueError(
                    f"H1 forecasts/targets/exclusions changed: {item['run_id']}/{artifact}"
                )
        summaries = h1_summaries(
            read_csv(safe_path(package, item["path"]) / "forecast_evaluation.csv"),
            periods(manifest["config"]),
        )
        exported = [r for r in h1_export if r["run_id"] == item["run_id"]]
        if len(exported) != len(summaries):
            raise ValueError("H1 report summary length mismatch")
        for expected in summaries:
            matching = [
                r
                for r in exported
                if r["period"] == expected["period"] and r["symbol"] == expected["symbol"]
            ]
            if len(matching) != 1:
                raise ValueError("H1 missing/duplicate asset summary")
            for key in ("observations", "excluded", "mae_ewma", "mae_no_change", "weight"):
                assert_close(matching[0][key], expected[key], f"H1 {key}", D("1E-15"))
    if len(h3_checks) != len(run_data):
        raise ValueError("H3 missing invariance rows")
    for row in h3_checks:
        item, _, _ = run_data[row["run_id"]]
        base = next(
            x for x in items if x["scenario"] == "BASE_E3" and x["strategy"] == item["strategy"]
        )
        invariant = h3_data[item["run_id"]] == h3_data[base["run_id"]]
        required = not item["scenario"].endswith("_DECISION")
        if required and not invariant:
            raise ValueError(f"H3 invariance failed: {item['run_id']}")
        if (
            yes(row["exact_base_invariance"]) != invariant
            or yes(row["expected_base_invariance"]) != required
        ):
            raise ValueError("H3 invariance result mismatch")
        if row["opportunity_daily_sha256"] != h3_data[item["run_id"]]:
            raise ValueError("H3 native daily digest mismatch")
        peer = next(
            (
                x
                for x in items
                if x["scenario"] == item["scenario"]
                and x["strategy"] != item["strategy"]
                and x["status"] in SUCCESS
            ),
            None,
        )
        if peer and h3_data[peer["run_id"]] != h3_data[item["run_id"]]:
            raise ValueError("H3 must not depend on portfolio")
    result.update(
        status="passed",
        runs_checked=len(run_data),
        run_artifacts_checked=checked_outputs,
        daily_reconciliations=checked_days,
        period_reconciliations=checked_periods,
        run_code_snapshot_hashes_checked=checked_code,
        code_provenance="verified_against_packaged_snapshots" if checked_code else "not_provided",
        git_provenance="not_checked_not_required",
        market_inputs="recorded_hashes_not_rehashed_offline",
        engine_reexecution=False,
        package_read_only=True,
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Optional NEW result file outside the package")
    args = parser.parse_args(argv)
    try:
        if args.output and (
            args.output.resolve().is_relative_to(args.package.resolve()) or args.output.exists()
        ):
            raise ValueError("Verification output must be a NEW path outside the package")
        result = verify_package(args.package)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result = dict(status="failed", error=str(exc), package_read_only=True)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output and result["status"] == "passed":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(text)
    sys.stdout.write(text)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

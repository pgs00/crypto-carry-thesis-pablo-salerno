"""Read-only verification of published thesis numbers against retained evidence.

Uses only the Python standard library. Never executes the backtest, downloads data,
or trusts a previously generated verification result as an observation.
"""

import argparse
import bisect
import csv
import hashlib
import io
import json
import math
import re
import statistics
import sys
import tomllib
import zipfile
from collections import defaultdict
from decimal import ROUND_HALF_UP, localcontext
from decimal import Decimal as D
from functools import lru_cache
from pathlib import Path

COMPACT = "data/evidence/carteras_continuas.zip"
SOFR = "results/benchmark_sofr/evidencia/tablas/cartera_sofr_diaria.csv"
BOUNDS = {
    "full": ("2022-01-01", "2026-09-01"),
    "2022-2023": ("2022-01-01", "2024-01-01"),
    "2024-2026-08": ("2024-01-01", "2026-09-01"),
    "2024+": ("2024-01-01", "2026-09-01"),
}
for y in range(2022, 2027):
    BOUNDS[str(y)] = (f"{y}-01-01", f"{y + 1}-01-01" if y < 2026 else "2026-09-01")


def rounded(value, decimals):
    return format(
        D(str(value)).quantize(D(1).scaleb(-decimals), rounding=ROUND_HALF_UP), f".{decimals}f"
    )


def matches(row, selector):
    return all(str(row.get(k, "")) == str(v) for k, v in selector.items())


class Evidence:
    def __init__(self, root):
        self.root = Path(root)

    @lru_cache(None)
    def content(self, path, member=None):
        if member:
            with zipfile.ZipFile(self.root / path) as z:
                return z.read(member)
        return (self.root / path).read_bytes()

    @lru_cache(None)
    def rows(self, path, member=None):
        return list(csv.DictReader(io.StringIO(self.content(path, member).decode("utf-8-sig"))))

    def compact(self, member):
        return self.rows(COMPACT, member)

    def direct(self, c):
        selector = c.get("selector", c.get("filter", {}))
        if c.get("source_format") == "toml":
            return D(str(tomllib.loads(self.content(c["source"]).decode())[c["field"]]))
        rows = [r for r in self.rows(c["source"], c.get("member")) if matches(r, selector)]
        if c["field"] == "__count__":
            return D(len(rows))
        if c.get("aggregation") == "unique":
            values = {r[c["field"]] for r in rows}
            if len(values) != 1:
                raise ValueError("Expected one unique value")
            value = D(values.pop())
        else:
            if len(rows) != 1:
                raise ValueError(f"Expected one row, found {len(rows)}: {selector}")
            value = D(rows[0][c["field"]])
        if c.get("divide_by"):
            value /= D(rows[0][c["divide_by"]])
        return value

    def period(self, rows, period, date_field="date"):
        lo, hi = BOUNDS[period]
        return [r for r in rows if lo <= r[date_field][:10] < hi]

    @lru_cache(None)
    def portfolio(self, strategy, period):
        rows = sorted(
            self.period(
                [
                    r
                    for r in self.compact("tablas/equity_pnl_diario.csv")
                    if r["strategy"] == strategy
                ],
                period,
            ),
            key=lambda r: r["date"],
        )
        opening = D(rows[0]["starting_equity_usdt"])
        equity = [opening] + [D(r["equity_usdt"]) for r in rows]
        # Reconstruct returns from balances, not the provided daily_return column.
        returns = [float(b / a - 1) for a, b in zip(equity, equity[1:])]
        final = equity[-1]
        peak = opening
        maxdd = D(0)
        for value in equity:
            peak = max(peak, value)
            maxdd = min(maxdd, value / peak - 1)
        out = {
            "final_equity_usdt": final,
            "net_pnl_usdt": final - opening,
            "net_return": final / opening - 1,
            "cagr": math.expm1(math.log(float(final / opening)) * 365 / len(rows)),
            "sharpe": statistics.mean(returns) / statistics.stdev(returns) * math.sqrt(365)
            if statistics.stdev(returns)
            else 0,
            "max_drawdown": maxdd,
            "days": len(rows),
        }
        for field in [
            "spot_pnl_usdt",
            "futures_pnl_usdt",
            "funding_usdt",
            "fees_usdt",
            "liquidation_fees_usdt",
        ]:
            out[field] = sum((D(r[field]) for r in rows), D(0))
        out["capital_deployed_daily_mean_usdt"] = sum(
            (D(r["capital_deployed_usdt"]) for r in rows), D(0)
        ) / len(rows)
        out["capital_utilization_daily_mean"] = sum(
            (D(r["capital_deployed_usdt"]) / D(r["equity_usdt"]) for r in rows), D(0)
        ) / len(rows)
        # Accounting is checked day by day, independently of the aggregate table.
        for r in rows:
            pnl = sum(
                (
                    D(r[f])
                    for f in [
                        "spot_pnl_usdt",
                        "futures_pnl_usdt",
                        "funding_usdt",
                        "fees_usdt",
                        "liquidation_fees_usdt",
                    ]
                ),
                D(0),
            )
            if abs(D(r["equity_usdt"]) - D(r["starting_equity_usdt"]) - pnl) > D("1e-8"):
                raise ValueError("Daily accounting mismatch " + r["date"])
        return out

    @lru_cache(None)
    def h1(self, period):
        rows = self.period(self.compact("tablas/h1_observaciones.csv"), period, "signal_utc")
        valid = [r for r in rows if r["horizon_valid"] == "True"]
        out = {"valid_observations": len(valid), "excluded_observations": len(rows) - len(valid)}
        for field, forecast in [("mae_ewma", "forecast"), ("mae_no_change", "no_change")]:
            means = []
            for symbol in ["BTCUSDT", "ETHUSDT"]:
                selected = [r for r in valid if r["symbol"] == symbol]
                means.append(
                    sum((abs(D(r[forecast]) - D(r["realized"])) for r in selected), D(0))
                    / len(selected)
                )
            out[field] = sum(means, D(0)) / 2
        return out

    @lru_cache(None)
    def h3(self, period):
        # Rebuild equal-asset daily means from active-minute aggregates.
        rows = self.period(self.compact("tablas/h3_diario_activo.csv"), period)
        by_date = defaultdict(list)
        for r in rows:
            by_date[r["date"]].append(r)
        valid = [
            rs
            for rs in by_date.values()
            if len(rs) == 2 and all(r["complete"] == "True" for r in rs)
        ]
        out = {"valid_days": len(valid), "excluded_days": len(by_date) - len(valid)}
        out["opportunity_mean"] = sum(
            (
                sum((D(r["opportunity_sum"]) / D(r["expected_minutes"]) for r in rs), D(0)) / 2
                for rs in valid
            ),
            D(0),
        ) / len(valid)
        out["eligible_fraction"] = sum(
            (
                sum((D(r["eligible_minutes"]) / D(r["expected_minutes"]) for r in rs), D(0)) / 2
                for rs in valid
            ),
            D(0),
        ) / len(valid)
        out["conditional_cagr"] = self.portfolio("conditional", period)["cagr"]
        return out

    @lru_cache(None)
    def activity(self, strategy):
        rows = [r for r in self.compact("tablas/ciclos.csv") if r["strategy"] == strategy]
        fills = [r for r in self.compact("evidencia/fills.csv") if r["strategy"] == strategy]
        return {
            "opening_attempts": len(rows),
            "completed_openings": sum(bool(r["opened_ns"]) for r in rows),
            "completed_cycles": sum(r["complete"] == "True" for r in rows),
            "failed_cycles": sum(r["failed"] == "True" for r in rows),
            "fills": len(fills),
            "partial_fills": sum(r["partial"] == "True" for r in fills),
        }

    @lru_cache(None)
    def exposure(self, strategy):
        rows = [
            r
            for r in self.compact("tablas/exposicion_intervalos.csv")
            if r["strategy"] == strategy and r["exposure"] in {"covered", "unhedged"}
        ]
        intervals = sorted((int(r["start_ns"]), int(r["end_ns"])) for r in rows)
        total = 0
        lo, hi = intervals[0]
        for a, b in intervals[1:]:
            if a <= hi:
                hi = max(hi, b)
            else:
                total += hi - lo
                lo, hi = a, b
        total += hi - lo
        return {"invested_fraction": D(total) / D(1704 * 86400 * 10**9)}

    @lru_cache(None)
    def entry(self, period, symbol):
        rows = self.period(
            [
                r
                for r in self.compact("evidencia/signals.csv")
                if r["strategy"] == "conditional" and r["symbol"] == symbol
            ],
            period,
            "timestamp_utc",
        )
        return {
            "evaluaciones": len(rows),
            "basis entre 0 y 0.50%": sum(
                r["filter_basis_negative"] == "pass" and r["filter_basis_above_max"] == "pass"
                for r in rows
            ),
            "funding supera costo": sum(r["filter_funding"] == "pass" for r in rows),
        }

    @lru_cache(None)
    def sofr(self):
        rows = self.rows(SOFR)
        principal = D(10000)
        pending = D(0)
        for r in rows:
            pending += principal * D(r["annual_decimal_rate"]) / D(360)
            if r["capitalized_at_close"] == "True":
                principal += pending
                pending = D(0)
        final = principal + pending
        return {
            "final_equity_usdt": final,
            "net_return": final / D(10000) - 1,
            "cagr": math.expm1(math.log(float(final / D(10000))) * 365 / len(rows)),
        }

    @lru_cache(None)
    def supplemental_h1(self, period):
        rows = [
            r
            for r in self.period(self.compact("tablas/h1_observaciones.csv"), period, "signal_utc")
            if r["horizon_valid"] == "True"
        ]
        funding = self.rows(
            "results/complementaria/Evidencia_complementaria_Pablo_Salerno.zip",
            "quant_h1/inputs/funding_consumido.csv",
        )
        grouped = {
            symbol: sorted(
                [r for r in funding if r["symbol"] == symbol], key=lambda r: int(r["funding_time"])
            )
            for symbol in ["BTCUSDT", "ETHUSDT"]
        }
        indexes = {
            symbol: [int(r["funding_time"]) for r in values] for symbol, values in grouped.items()
        }
        errors = defaultdict(list)
        for r in rows:
            symbol = r["symbol"]
            anchor = int(r["anchor"])
            target = D(r["realized"])
            forecasts = {
                "ewma": D(r["forecast"]),
                "no_change": D(r["no_change"]),
                "constant_001pct_8h": D("0.0021"),
            }
            for name, hours in [("rolling_7d", 168), ("rolling_14d", 336)]:
                a = bisect.bisect_right(indexes[symbol], anchor - hours * 3600 * 10**9)
                b = bisect.bisect_right(indexes[symbol], anchor)
                selected = grouped[symbol][a:b]
                forecasts[name] = (
                    D(168)
                    * sum((D(x["funding_rate"]) for x in selected), D(0))
                    / sum((D(x["interval_hours"]) for x in selected), D(0))
                )
            for name, value in forecasts.items():
                errors[(symbol, name)].append(abs(value - target))
        return {
            "mae_" + name + "_bps": sum(
                (
                    sum(errors[(symbol, name)], D(0)) / len(errors[(symbol, name)])
                    for symbol in grouped
                ),
                D(0),
            )
            / 2
            * 10000
            for name in forecasts
        }

    @lru_cache(None)
    def basis(self, period, symbol):
        rows = self.period(
            [
                r
                for r in self.compact("evidencia/signals.csv")
                if r["strategy"] == "conditional"
                and r["symbol"] == symbol
                and r["filter_data_valid"] == "pass"
            ],
            period,
            "timestamp_utc",
        )
        values = [(D(r["futures_price"]) / D(r["spot_price"]) - 1) * 10000 for r in rows]
        return {
            "mean_basis_bps": sum(values, D(0)) / len(values),
            "median_basis_bps": statistics.median(values),
            "negative_pct": D(sum(v < 0 for v in values)) * 100 / len(values),
        }

    @lru_cache(None)
    def cash(self, fraction):
        rates = {r["date"]: r for r in self.rows(SOFR)}
        out = {"cash_fraction": D(fraction)}
        for strategy in ["conditional", "permanent"]:
            rows = sorted(
                [
                    r
                    for r in self.compact("tablas/equity_pnl_diario.csv")
                    if r["strategy"] == strategy
                ],
                key=lambda r: r["date"],
            )
            with localcontext() as context:
                context.prec = 50
                capitalized = D(0)
                pending = D(0)
                lagged_cash = D(10000)
                prior_equity = D(10000)
                returns = []
                for row in rows:
                    rate = rates[row["date"]]
                    pending += (
                        (D(fraction) * lagged_cash + capitalized)
                        * D(rate["annual_decimal_rate"])
                        / 360
                    )
                    adjusted = D(row["equity_usdt"]) + capitalized + pending
                    returns.append(float(adjusted / prior_equity - 1))
                    prior_equity = adjusted
                    if rate["capitalized_at_close"] == "True":
                        capitalized += pending
                        pending = D(0)
                    lagged_cash = max(D(row["free_cash_usdt"]) - D(row["debt_usdt"]), D(0))
                out[strategy + "_CAGR365_percent"] = (
                    (adjusted / 10000) ** (D(365) / len(rows)) - 1
                ) * 100
                out[strategy + "_Sharpe_rf0"] = (
                    statistics.mean(returns) / statistics.stdev(returns) * math.sqrt(365)
                )
        return out

    def recompute(self, c):
        r = c["recompute"]
        kind = r["kind"]
        if kind == "portfolio":
            v = self.portfolio(r["strategy"], r["period"])
        elif kind == "h1":
            v = self.h1(r["period"])
        elif kind == "h3":
            v = self.h3(r["period"])
        elif kind == "activity":
            v = self.activity(r["strategy"])
        elif kind == "exposure":
            v = self.exposure(r["strategy"])
        elif kind == "entry":
            v = self.entry(r["period"], r["symbol"])
        elif kind == "sofr":
            v = self.sofr()
        elif kind == "supplemental_h1":
            v = self.supplemental_h1(r["period"])
        elif kind == "basis":
            v = self.basis(r["period"], r["symbol"])
        elif kind == "cash":
            v = self.cash(r["fraction"])
        elif kind == "annual_h3":
            raw = self.h3(r["period"])
            v = {
                "valid_days": raw["valid_days"],
                "opportunity_bps_per_168h": raw["opportunity_mean"] * 10000,
                "eligible_minutes_percent": raw["eligible_fraction"] * 100,
            }
        else:
            raise ValueError("Unsupported computation " + kind)
        return D(str(v[r["field"]]))


def verify(root, baseline):
    evidence = Evidence(root)
    checks = []
    integrity = []
    for source in baseline.get("source_files", []) + (
        [baseline["pdf"]] if baseline.get("pdf") else []
    ):
        try:
            actual = hashlib.sha256((Path(root) / source["path"]).read_bytes()).hexdigest()
            if actual != source["sha256"]:
                integrity.append({"path": source["path"], "error": "SHA256 mismatch"})
        except Exception as exc:
            integrity.append({"path": source["path"], "error": str(exc)})
    for name in baseline.get("required_paths", []):
        if not (Path(root) / name).is_file():
            integrity.append({"path": name, "error": "Required thesis source missing"})
    if (
        baseline.get("ai_disclosure")
        and baseline["ai_disclosure"] not in (Path(root) / "README.md").read_text()
    ):
        integrity.append({"path": "README.md", "error": "AI disclosure changed"})
    for c in baseline["cells"]:
        result = {k: c[k] for k in ["table", "row", "column", "expected_published"]}
        try:
            value = evidence.direct(c)
            result["source_value"] = str(value)
            result["actual_published"] = rounded(value * D(str(c["multiplier"])), c["decimals"])
            result["matches_published"] = D(result["actual_published"]) == D(
                c["expected_published"]
            )
            if c.get("recompute"):
                independent = evidence.recompute(c)
                result["recomputed_value"] = str(independent)
                result["recomputed_published"] = rounded(
                    independent * D(str(c["multiplier"])), c["decimals"]
                )
                result["recomputed_matches_published"] = D(result["recomputed_published"]) == D(
                    c["expected_published"]
                )
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        checks.append(result)
    failures = [
        r
        for r in checks
        if r.get("error")
        or not r.get("matches_published", False)
        or not r.get("recomputed_matches_published", True)
    ]
    return {
        "tables": len(set(c["table"] for c in baseline["cells"])),
        "numeric_cells": len(checks),
        "independently_recomputed_cells": sum("recomputed_value" in r for r in checks),
        "integrity_failures": integrity,
        "failure_count": len(failures) + len(integrity),
        "failures": failures,
        "checks": checks,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--baseline", type=Path)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    baseline = a.baseline or a.repo / "data/evidence/thesis_baseline.json"
    result = verify(a.repo, json.loads(baseline.read_text()))
    if a.output:
        a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps({k: v for k, v in result.items() if k != "checks"}, ensure_ascii=False, indent=2)
    )
    return bool(result["failure_count"])


if __name__ == "__main__":
    sys.exit(main())

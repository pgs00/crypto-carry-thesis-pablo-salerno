"""Verify the compact package using only Python's standard library."""

import argparse
import csv
import hashlib
import json
import re
import runpy
from bisect import bisect_right
from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path

DAY = 86_400_000_000_000
SECOND = 1_000_000_000
SYMBOLS = ("BTCUSDT", "ETHUSDT")
PERIODS = (
    ("full", 1640995200000000000, 1788220800000000000),
    ("2022-2023", 1640995200000000000, 1704067200000000000),
    ("2024-2026-08", 1704067200000000000, 1788220800000000000),
)


def number(value):
    return D(0) if value in (None, "") else D(value)


def yes(value):
    return str(value).lower() in {"true", "1"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def equal(actual, expected, message, tolerance=D("1e-18")):
    require(abs(number(actual) - number(expected)) <= tolerance, message)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def rows(root, name):
    with (root / name).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def verify_h1(root):
    observations = rows(root, "tablas/h1_observaciones.csv")
    rates = rows(root, "evidencia/funding_mercado_y_marks.csv")
    histories = {}
    for symbol in SYMBOLS:
        selected = sorted(
            (r for r in rates if r["symbol"] == symbol), key=lambda r: int(r["funding_time"])
        )
        times, prefix = [], [D(0)]
        for row in selected:
            times.append(int(row["funding_time"]))
            prefix.append(prefix[-1] + number(row["funding_rate"]))
        histories[symbol] = times, prefix
    require(
        len({(r["symbol"], r["time_ns"]) for r in observations}) == len(observations),
        "Duplicate H1 cohort",
    )
    for row in observations:
        if not yes(row["horizon_valid"]):
            require(
                bool(row["reason"]) and row["realized"] == "",
                "Invalid H1 observation has an invented target",
            )
            continue
        times, prefix = histories[row["symbol"]]
        left = bisect_right(times, int(row["time_ns"]))
        right = bisect_right(times, int(row["horizon_end"]))
        target = prefix[right] - prefix[left]
        equal(row["realized"], target, "H1 target differs from future funding sum")
        require(
            int(row["horizon_end"]) - int(row["time_ns"]) == 168 * 3600 * SECOND, "Wrong H1 horizon"
        )
        for prediction, field in (
            ("forecast", "absolute_error_ewma"),
            ("no_change", "absolute_error_no_change"),
        ):
            equal(row[field], abs(number(row[prediction]) - target), "H1 absolute error differs")
    summaries = rows(root, "tablas/h1_resumen.csv")
    for period, start, end in PERIODS:
        asset_means = []
        total_valid = total_excluded = 0
        for symbol in SYMBOLS:
            all_rows = [
                r
                for r in observations
                if r["symbol"] == symbol and start <= int(r["time_ns"]) < end
            ]
            valid = [r for r in all_rows if yes(r["horizon_valid"])]
            summary = next(r for r in summaries if r["period"] == period and r["symbol"] == symbol)
            require(int(summary["valid_observations"]) == len(valid), "H1 valid count differs")
            require(
                int(summary["excluded_observations"]) == len(all_rows) - len(valid),
                "H1 exclusion count differs",
            )
            means = [
                sum((number(r[field]) for r in valid), D(0)) / len(valid)
                for field in ("absolute_error_ewma", "absolute_error_no_change")
            ]
            equal(summary["mae_ewma"], means[0], "H1 asset MAE differs")
            equal(summary["mae_no_change"], means[1], "H1 asset MAE differs")
            asset_means.append(means)
            total_valid += len(valid)
            total_excluded += len(all_rows) - len(valid)
        summary = next(
            r for r in summaries if r["period"] == period and r["symbol"] == "EQUAL_WEIGHT"
        )
        equal(
            summary["mae_ewma"],
            (asset_means[0][0] + asset_means[1][0]) / 2,
            "H1 asset weights differ",
        )
        equal(
            summary["mae_no_change"],
            (asset_means[0][1] + asset_means[1][1]) / 2,
            "H1 asset weights differ",
        )
        require(
            int(summary["valid_observations"]) == total_valid
            and int(summary["excluded_observations"]) == total_excluded,
            "H1 aggregate sample counts differ",
        )
    return len(observations)


def verify_h3(root):
    days = rows(root, "tablas/h3_diario_activo.csv")
    joint = rows(root, "tablas/h3_diario_conjunto.csv")
    groups = rows(root, "tablas/h3_grupos_forecast.csv")
    totals = defaultdict(lambda: dict(minutes=0, valid=0, eligible=0, total=D(0)))
    for row in groups:
        item = totals[row["date"], row["symbol"]]
        item["minutes"] += int(row["minutes"])
        item["valid"] += int(row["valid_minutes"])
        item["eligible"] += int(row["eligible_minutes"])
        contribution = number(row["forecast"]) * int(row["eligible_minutes"])
        equal(
            row["opportunity_sum"],
            contribution,
            "H3 contribution is not the full forecast times eligible minutes",
        )
        item["total"] += contribution
    by_date = defaultdict(list)
    for row in days:
        total = totals[row["date"], row["symbol"]]
        require(total["minutes"] == 1440, "H3 does not include all daily minutes")
        require(yes(row["complete"]) == (total["valid"] == 1440), "H3 coverage flag differs")
        require(int(row["eligible_minutes"]) == total["eligible"], "H3 eligibility count differs")
        equal(row["opportunity_sum"], total["total"], "H3 daily sum differs")
        if yes(row["complete"]):
            equal(row["opportunity"], total["total"] / 1440, "H3 denominator excludes zero minutes")
        else:
            require(row["opportunity"] == "", "Incomplete H3 day must be excluded")
        by_date[row["date"]].append(row)
    for row in joint:
        pair = by_date[row["date"]]
        require({r["symbol"] for r in pair} == set(SYMBOLS) and len(pair) == 2, "H3 assets differ")
        complete = all(yes(r["complete"]) for r in pair)
        require(yes(row["complete"]) == complete, "Joint H3 coverage differs")
        if complete:
            equal(
                row["opportunity"],
                sum((number(r["opportunity"]) for r in pair), D(0)) / 2,
                "H3 assets are not equally weighted",
            )
        else:
            require(row["opportunity"] == "", "Joint H3 must exclude incomplete asset days")
    summaries = rows(root, "tablas/h3_resumen.csv")
    for period, start, end in PERIODS:
        for symbol in (*SYMBOLS, "EQUAL_WEIGHT"):
            selected = [
                r
                for r in (joint if symbol == "EQUAL_WEIGHT" else days)
                if start <= int(r["time_ns"]) < end
                and (symbol == "EQUAL_WEIGHT" or r["symbol"] == symbol)
            ]
            good = [r for r in selected if yes(r["complete"])]
            summary = next(r for r in summaries if r["period"] == period and r["symbol"] == symbol)
            require(
                int(summary["valid_days"]) == len(good)
                and int(summary["excluded_days"]) == len(selected) - len(good),
                "H3 summary coverage differs",
            )
            equal(
                summary["opportunity_mean"],
                sum((number(r["opportunity"]) for r in good), D(0)) / len(good),
                "H3 regime mean differs",
            )
    for row in rows(root, "evidencia/h3_muestra_minutos.csv"):
        require(
            int(row["forecast_available_at"]) <= int(row["time_ns"]),
            "H3 sample uses a future forecast",
        )
        require(
            yes(row["eligible"])
            == all(yes(row[k]) for k in ("complete", "funding_pass", "basis_pass", "operational")),
            "H3 sample eligibility differs",
        )
    return len(days), len(joint)


def verify_financials(root):
    daily = rows(root, "tablas/equity_pnl_diario.csv")
    summaries = rows(root, "tablas/resultados_periodos.csv")
    fields = (
        "spot_pnl_usdt",
        "futures_pnl_usdt",
        "funding_usdt",
        "fees_usdt",
        "liquidation_fees_usdt",
    )
    for strategy in ("conditional", "permanent"):
        selected = sorted(
            (r for r in daily if r["strategy"] == strategy), key=lambda r: int(r["time_ns"])
        )
        require(
            [int(r["time_ns"]) for r in selected]
            == list(range(PERIODS[0][1] + DAY - 1, PERIODS[0][2], DAY)),
            "Missing continuous daily equity",
        )
        previous = D(10000)
        for row in selected:
            equal(
                row["starting_equity_usdt"],
                previous,
                "Portfolio equity restarted at a cut",
                D("1e-8"),
            )
            change = number(row["equity_usdt"]) - previous
            equal(row["net_pnl_usdt"], change, "Daily P&L differs from equity", D("1e-8"))
            equal(
                sum((number(row[k]) for k in fields), D(0)),
                change,
                "Daily P&L components do not reconcile",
                D("1e-8"),
            )
            previous = number(row["equity_usdt"])
        for period, start, end in PERIODS:
            block = [r for r in selected if start <= int(r["time_ns"]) < end]
            summary = next(
                r for r in summaries if r["strategy"] == strategy and r["period"] == period
            )
            equal(
                summary["starting_equity_usdt"],
                block[0]["starting_equity_usdt"],
                "Regime starts from the wrong equity",
            )
            equal(
                summary["final_equity_usdt"],
                block[-1]["equity_usdt"],
                "Regime ends at the wrong equity",
            )
            for field in (*fields, "net_pnl_usdt"):
                equal(
                    summary[field],
                    sum((number(r[field]) for r in block), D(0)),
                    "Regime P&L does not reconcile",
                    D("1e-8"),
                )
            equal(
                summary["net_return"],
                number(block[-1]["equity_usdt"]) / number(block[0]["starting_equity_usdt"]) - 1,
                "Regime return differs",
                D("1e-12"),
            )
    return len(daily)


def verify_package(root):
    root = Path(root).resolve()
    require(
        sha(root / "manifest.json") == (root / "manifest.sha256").read_text().strip(),
        "Manifest hash differs",
    )
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["file_hashes"].items():
        path = (root / name).resolve()
        require(path.is_relative_to(root), "Package path escapes its directory")
        require(sha(path) == expected, f"File hash differs: {name}")
    for path in (root / "fuentes").glob("*/run_manifest.json"):
        require(
            sha(path) == path.with_suffix(".sha256").read_text().strip(),
            "Original run manifest bytes changed",
        )
    h1 = verify_h1(root)
    h3_assets, h3_joint = verify_h3(root)
    financial_days = verify_financials(root)
    sensitivity = root / "data/research/continuous-marks-20260919"
    helper = runpy.run_path(str(sensitivity / "summarize_sensitivity.py"))
    helper["verify"](sensitivity, helper["summarize"](sensitivity))
    links = 0
    for document in (
        root / "README.md",
        sensitivity / "README.md",
        root / "docs/continuous_mark_gaps.md",
    ):
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            if target.startswith(("https://", "http://", "#")):
                continue
            require(
                (document.parent / target.split("#")[0]).exists(), f"Broken document link: {target}"
            )
            links += 1
    return dict(
        status="verified",
        files=len(manifest["file_hashes"]),
        valid_local_links=links,
        daily_financial_rows=financial_days,
        h1_observations=h1,
        h3_asset_days=h3_assets,
        h3_joint_days=h3_joint,
        scope="ZIP contents, paired H1 labels and MAE, H3 aggregates, daily/regime accounting; original market files verified separately",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(verify_package(args.directory), indent=2))


if __name__ == "__main__":
    main()

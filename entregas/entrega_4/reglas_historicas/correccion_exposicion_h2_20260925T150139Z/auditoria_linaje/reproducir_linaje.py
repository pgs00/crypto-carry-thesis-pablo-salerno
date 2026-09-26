"""Read persisted evidence and archived pure E3 functions; never simulate a strategy.

Run from repository root: .venv/Scripts/python.exe -B -X utf8 <this file>
Only writes linaje_resultados.json alongside this new diagnostic script.
"""

import ast
import hashlib
import json
import sys
import zipfile
from collections import Counter, defaultdict
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normal(value):
    return "" if value is None else str(value)


def main():
    from crypto_carry.config import SECOND, iso, timestamp
    from scripts.continuous_delivery.common import PERIODS, SYMBOLS, decimal, read_rows

    parent = ROOT / "entregas/entrega_4/reglas_historicas/20260925T005436Z"
    evidence = ROOT / "Paquete de evidencia"
    archived = evidence / "codigo/scripts/continuous_delivery/portfolio.py"
    tree = ast.parse(archived.read_text(encoding="utf-8"))
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"exposure_intervals", "exposure_summary"}
    ]
    namespace = dict(
        defaultdict=defaultdict, D=D, iso=iso, SECOND=SECOND, decimal=decimal, SYMBOLS=SYMBOLS
    )
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(archived), "exec"), namespace)
    originals = read_rows(evidence / "tablas/exposicion_intervalos.csv")
    original_summaries = read_rows(evidence / "tablas/tiempo_invertido.csv")
    e3_positions = read_rows(evidence / "evidencia/positions.csv")
    report = {
        "method": "archived E3 pure functions, saved positions; no simulation",
        "inputs": {},
        "archive_checks": [],
        "runs": [],
    }
    sources = [
        archived,
        evidence / "codigo/scripts/continuous_delivery/build.py",
        evidence / "codigo/scripts/continuous_delivery/common.py",
        evidence / "codigo/src/crypto_carry/strategy.py",
        evidence / "codigo/src/crypto_carry/reporting.py",
        evidence / "tablas/exposicion_intervalos.csv",
        evidence / "tablas/tiempo_invertido.csv",
        evidence / "evidencia/positions.csv",
        evidence / "evidencia/ledger.csv",
        evidence / "evidencia/risk_events.csv",
        ROOT / "entregas/entrega_3/continua/tablas/tiempo_invertido.csv",
        parent / "indice_corridas.json",
    ]
    archive = ROOT / "entregas/entrega_3/paquete_actualizacion_entrega_3_continua.zip"
    report["archive_sha256"] = sha(archive)
    with zipfile.ZipFile(archive) as stream:
        for source in sources:
            if source.is_relative_to(evidence):
                name = source.relative_to(evidence).as_posix()
                report["archive_checks"].append(
                    dict(member=name, bytes_equal=source.read_bytes() == stream.read(name))
                )
    assert all(row["bytes_equal"] for row in report["archive_checks"])
    report["published_time_table_bytes_equal"] = sources[6].read_bytes() == sources[10].read_bytes()
    for run in json.loads((parent / "indice_corridas.json").read_text(encoding="utf-8"))["runs"]:
        folder = parent / run["path"]
        sources += [
            folder / name
            for name in (
                "positions.parquet",
                "ledger.parquet",
                "risk_events.parquet",
                "run_manifest.json",
                "run_summary.csv",
                "run_context.csv",
            )
        ]
        manifest = json.loads((folder / "run_manifest.json").read_text(encoding="utf-8"))
        config = manifest["config"]
        start, end = timestamp(config["start"]), timestamp(config["end"])
        rows = read_rows(folder / "positions.parquet")
        ledger = read_rows(folder / "ledger.parquet")
        risks = read_rows(folder / "risk_events.parquet")
        intervals = namespace["exposure_intervals"](rows, start, end, D(config["hedge_tolerance"]))
        summaries = namespace["exposure_summary"](intervals, PERIODS)
        quantity_mismatches, transition_mismatches, missing_quantity_times = [], [], []
        for symbol in SYMBOLS:
            position_at = {int(row["time_ns"]): row for row in rows if row["symbol"] == symbol}
            quantities = {start: (D(0), D(0))}
            for row in ledger:
                if row["symbol"] == symbol:
                    quantities[int(row["time_ns"])] = (decimal(row["spot"]), decimal(row["short"]))
            times = sorted(quantities)
            pointer = 0
            for moment, row in sorted(position_at.items()):
                while pointer + 1 < len(times) and times[pointer + 1] <= moment:
                    pointer += 1
                if quantities[times[pointer]] != (decimal(row["spot"]), decimal(row["short"])):
                    quantity_mismatches.append(dict(symbol=symbol, time_ns=moment))
            previous = (D(0), D(0))
            for moment, quantity in sorted(quantities.items()):
                if quantity != previous and moment not in position_at:
                    missing_quantity_times.append(dict(symbol=symbol, time_ns=moment))
                previous = quantity
            transitions = {
                int(row["time_ns"]): row
                for row in risks
                if row["symbol"] == symbol and row["kind"] == "transition"
            }
            for moment, row in transitions.items():
                if moment not in position_at or position_at[moment]["state"] != row["state"]:
                    transition_mismatches.append(dict(symbol=symbol, time_ns=moment))
        item = dict(
            scenario=run["scenario"],
            strategy=run["strategy"],
            run_id=run["run_id"],
            status=manifest["status"],
            start_ns=start,
            end_exclusive_ns=end,
            hedge_tolerance=config["hedge_tolerance"],
            positions_rows=len(rows),
            snapshot_counts=dict(Counter(r["snapshot_kind"] for r in rows)),
            missing_state_rows=sum(not row.get("state") for row in rows),
            missing_quantity_rows=sum(
                row.get("spot") in (None, "") or row.get("short") in (None, "") for row in rows
            ),
            duplicate_symbol_timestamp_rows=len(rows)
            - len({(r["symbol"], r["time_ns"]) for r in rows}),
            intervals=len(intervals),
            summaries=summaries,
            last_positions=[r for r in rows if r["snapshot_kind"] == "final"],
            run_summary=read_rows(folder / "run_summary.csv"),
            run_context=read_rows(folder / "run_context.csv"),
            position_ledger_quantity_mismatches=quantity_mismatches,
            quantity_change_times_without_position=missing_quantity_times,
            position_transition_mismatches=transition_mismatches,
        )
        assert not quantity_mismatches and not missing_quantity_times and not transition_mismatches
        if run["scenario"] == "BASE_E3":
            old = [r for r in originals if r["strategy"] == run["strategy"]]
            old_sums = [r for r in original_summaries if r["strategy"] == run["strategy"]]
            item["original_interval_field_differences"] = [
                [i, k, str(r[k]), o[k]]
                for i, (r, o) in enumerate(zip(intervals, old, strict=True))
                for k in r
                if str(r[k]) != o[k]
            ]
            item["original_summary_field_differences"] = [
                [i, k, str(r[k]), o[k]]
                for i, (r, o) in enumerate(zip(summaries, old_sums, strict=True))
                for k in r
                if str(r[k]) != o[k]
            ]
            old_positions = [r for r in e3_positions if r["strategy"] == run["strategy"]]
            item["e3_position_input_field_differences"] = [
                [i, k, normal(r[k]), normal(o[k])]
                for i, (r, o) in enumerate(zip(rows, old_positions, strict=True))
                for k in r
                if normal(r[k]) != normal(o[k])
            ]
            assert not item["original_interval_field_differences"]
            assert not item["original_summary_field_differences"]
            assert not item["e3_position_input_field_differences"]
            full = next(
                r for r in summaries if r["period"] == "full" and r["symbol"] == "PORTFOLIO"
            )
            item["full_invested_percent"] = (
                full["invested_seconds"] / full["calendar_seconds"] * 100
            )
            day = timestamp("2023-03-24T00:00:00Z")
            item["episode"] = namespace["exposure_summary"](
                intervals, [("2023-03-24", day, day + 86400 * SECOND)]
            )
            shorter = namespace["exposure_intervals"](
                rows, start, end - 1, D(config["hedge_tolerance"])
            )
            shorter_sums = namespace["exposure_summary"](shorter, [("full", start, end - 1)])
            item["terminal_nanosecond_if_wrong_end_used"] = [
                dict(
                    symbol=r["symbol"],
                    differences_seconds={k: r[k] - s[k] for k in r if k.endswith("_seconds")},
                )
                for r, s in zip(summaries[:3], shorter_sums, strict=True)
            ]
        report["runs"].append(item)
    report["inputs"] = {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in sources}
    Path(__file__).with_name("linaje_resultados.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "runs": len(report["runs"]),
                "archive_checks": len(report["archive_checks"]),
                "source_hashes": len(report["inputs"]),
                "all_position_ledger_transition_checks": True,
                "BASE_exact_original_intervals_and_summaries": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

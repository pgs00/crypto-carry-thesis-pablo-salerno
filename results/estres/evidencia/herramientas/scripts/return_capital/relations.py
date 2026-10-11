"""Population, period and foreign-key contracts for compact verification."""

from collections import Counter
from decimal import Decimal as D

from .common import COMPONENTS, DAY, RUNS, SYMBOLS, close, iso, number, periods, truth
from .decisions import paired_coverage, summarize_decisions


def unique(rows, fields, label):
    result = {tuple(r[k] for k in fields): r for r in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate " + label)
    return result


def check_relations(tables, compare):
    metrics = unique(tables["metricas_reutilizadas"], ("run_id", "period"), "financial period")
    windows = periods(tables["metricas_reutilizadas"])
    bounds = {p: (a, b) for p, a, b in windows}
    if len(bounds) != len(windows) or set(metrics) != {
        (run, p) for run in RUNS.values() for p in bounds
    }:
        raise ValueError("Financial period population differs")
    for name, rows in tables.items():
        for r in rows:
            if r.get("period") in bounds and "start_ns" in r:
                if (int(r["start_ns"]), int(r["end_exclusive_ns"])) != bounds[r["period"]]:
                    raise ValueError("Noncanonical period interval: " + name)
            if r.get("run_id") in RUNS.values() and r.get("strategy"):
                if RUNS.get(r["strategy"]) != r["run_id"]:
                    raise ValueError("Strategy/run identity differs: " + name)
    lower, upper = min(a for _, a, _ in windows), max(b for _, _, b in windows)
    daily = unique(tables["diario_reutilizado"], ("run_id", "date"), "financial day")
    expected_days = {(run, iso(t)[:10]) for run in RUNS.values() for t in range(lower, upper, DAY)}
    if set(daily) != expected_days:
        raise ValueError("Financial day population differs")
    for r in daily.values():
        t = int(r["time_ns"])
        if iso(t)[:10] != r["date"] or (t + 1) % DAY:
            raise ValueError("Daily close timestamp differs")

    cycles = unique(tables["ciclos_vida"], ("run_id", "cycle_id"), "cycle identity")
    credited = unique(tables["entradas_acreditadas"], ("run_id", "cycle_id"), "credited entry")
    segment_cycles = {
        (r["run_id"], r["cycle_id"]) for r in tables["atribuciones_segmentos"] if r["cycle_id"]
    }
    if set(cycles) != set(credited) or not segment_cycles <= set(cycles):
        raise ValueError("Inconsistent cycle population across tables")
    for name in ("movimientos_ciclo", "contribuciones_ciclo_periodo", "atribuciones_segmentos"):
        for r in tables[name]:
            if r["cycle_id"]:
                cycle = cycles.get((r["run_id"], r["cycle_id"]))
                if cycle is None or cycle["symbol"] != r["symbol"]:
                    raise ValueError("Invalid cycle population reference: " + name)
    for key, cycle in cycles.items():
        own = [r for r in tables["atribuciones_segmentos"] if (r["run_id"], r["cycle_id"]) == key]
        for f in (*COMPONENTS, "net_pnl_usdt"):
            close(cycle[f], sum((number(r[f]) for r in own), D(0)), "cycle component " + f)
        closed = cycle["closed_ns"] not in (None, "")
        opened = cycle["opened_ns"] not in (None, "")
        if (
            truth(cycle["complete"]) != (closed and opened)
            or truth(cycle["still_open_at_end"]) == closed
        ):
            raise ValueError("Cycle terminal state differs")
        if int(cycle["end_ns"]) != (int(cycle["closed_ns"]) if closed else upper - 1):
            raise ValueError("Cycle terminal boundary differs")
        fills = [
            r
            for r in tables["movimientos_ciclo"]
            if (r["run_id"], r["cycle_id"]) == key and r["fill_id"]
        ]
        status = (
            "open_at_end"
            if not closed
            else "closed"
            if opened
            else "incomplete_opening"
            if fills
            else "attempt_without_fill"
        )
        if cycle["status"] != status or int(cycle["fills"]) != len(fills):
            raise ValueError("Cycle status/fill count differs")

    expected_contributions = set()
    for run in RUNS.values():
        for period, a, b in windows:
            expected_contributions.update(
                (run, period, r["symbol"], r["category"], r["cycle_id"])
                for r in tables["atribuciones_segmentos"]
                if r["run_id"] == run and a <= int(r["time_ns"]) < b
            )
    actual_contributions = unique(
        tables["contribuciones_ciclo_periodo"],
        ("run_id", "period", "symbol", "category", "cycle_id"),
        "contribution",
    )
    if set(actual_contributions) != expected_contributions:
        raise ValueError("Contribution population differs")

    counts = unique(tables["conteo_ciclos_periodo"], ("run_id", "period", "symbol"), "cycle count")
    expected_count_keys = {(run, p, s) for run, p in metrics for s in (*SYMBOLS, "PORTFOLIO")}
    if set(counts) != expected_count_keys:
        raise ValueError("Cycle count population differs")
    for (run, period, symbol), actual in counts.items():
        a, b = bounds[period]
        own = [
            r
            for r in cycles.values()
            if r["run_id"] == run and (symbol == "PORTFOLIO" or r["symbol"] == symbol)
        ]
        overlap = [r for r in own if int(r["entry_ns"]) < b and int(r["end_ns"]) >= a]
        states = Counter(
            r["status"]
            if r["closed_ns"] not in (None, "") and int(r["closed_ns"]) < b
            else "open_at_period_end"
            for r in overlap
        )
        expected = dict(
            cycles_participating=len(overlap),
            entries_in_period=sum(a <= int(r["entry_ns"]) < b for r in own),
            closes_in_period=sum(
                r["closed_ns"] not in (None, "") and a <= int(r["closed_ns"]) < b for r in own
            ),
            **{
                k: states[k]
                for k in (
                    "closed",
                    "incomplete_opening",
                    "attempt_without_fill",
                    "open_at_period_end",
                )
            },
        )
        compare([{k: actual[k] for k in expected}], [expected], "cycle period count")

    for name, ranks, symbols in (
        ("concentracion_ciclos", (1, 3, 5), (*SYMBOLS, "PORTFOLIO")),
        ("concentracion_dias", (1, 5, 10), ("PORTFOLIO",)),
    ):
        actual = [
            (
                r["run_id"],
                r["period"],
                r.get("symbol", "PORTFOLIO"),
                r["sign"],
                int(r["requested_k"]),
            )
            for r in tables[name]
        ]
        expected = {
            (run, p, s, sign, k)
            for run, p in metrics
            for s in symbols
            for sign in ("positive", "negative")
            for k in ranks
        }
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError("Concentration population differs")

    evaluations = unique(tables["decisiones_clasificadas"], ("evaluation_id",), "evaluation")
    for strategy, run in RUNS.items():
        rows = [r for r in evaluations.values() if r["run_id"] == run]
        expected = summarize_decisions(rows, windows, run, strategy)
        for name, values in zip(
            ("grupos_excluyentes", "motivos_simultaneos", "diagnostico_vs_decision"),
            expected,
            strict=True,
        ):
            compare(
                [r for r in tables[name] if r["run_id"] == run],
                values,
                "evaluation aggregate " + name,
            )
    compare(
        tables["emparejamiento"],
        paired_coverage(list(evaluations.values()), windows),
        "paired coverage",
    )
    accepted = {
        r["evaluation_id"]
        for r in evaluations.values()
        if r["decision_kind"] == "entry" and r["decision"] == "accepted"
    }
    if {r["evaluation_id"] for r in credited.values()} != accepted:
        raise ValueError("Accepted evaluation/entry population differs")
    for key, entry in credited.items():
        cycle, ev = cycles[key], evaluations[entry["evaluation_id"],]
        if any(entry[k] != cycle[k] for k in ("run_id", "symbol")) or int(entry["time_ns"]) != int(
            cycle["entry_ns"]
        ):
            raise ValueError("Credited entry/cycle link differs")
        if (
            ev["run_id"] != entry["run_id"]
            or ev["symbol"] != entry["symbol"]
            or int(ev["time_ns"]) != int(entry["time_ns"])
        ):
            raise ValueError("Credited entry/evaluation link differs")
    unique(
        tables["acciones_y_enlaces"], ("run_id", "source_file", "source_row"), "action source row"
    )
    for action in tables["acciones_y_enlaces"]:
        for field in ("evaluation_id", "accepted_entry_order_evaluation_id"):
            identity = action[field]
            if not identity:
                continue
            ev = evaluations.get((identity,))
            if ev is None or any(ev[k] != action[k] for k in ("run_id", "symbol")):
                raise ValueError("Invalid action evaluation reference")
            if field == "evaluation_id" and (
                int(ev["time_ns"]) != int(action["time_ns"])
                or action["link_status"] != "exact_time_unique"
            ):
                raise ValueError("Invalid temporal action link")
            if field != "evaluation_id" and identity not in accepted:
                raise ValueError("Order root is not an accepted entry")
    integrated = unique(tables["resumen_integrado"], ("run_id", "period"), "integrated period")
    if set(integrated) != set(metrics):
        raise ValueError("Integrated population differs")
    for key, row in integrated.items():
        expected = {
            k: v
            for k, v in counts[*key, "PORTFOLIO"].items()
            if k not in metrics[key] and k != "symbol"
        }
        compare([{k: row[k] for k in expected}], [expected], "integrated cycle counts")
        outside = sum(
            (
                number(r["net_pnl_usdt"])
                for r in tables["contribuciones_ciclo_periodo"]
                if (r["run_id"], r["period"]) == key and r["category"] != "cycle"
            ),
            D(0),
        )
        close(row["outside_cycle_pnl_usdt"], outside, "integrated outside P&L")
        a, b = bounds[key[1]]
        n = sum(
            r["run_id"] == key[0] and r["decision_kind"] == "entry" and a <= int(r["time_ns"]) < b
            for r in evaluations.values()
        )
        if int(row["entry_evaluations"]) != n:
            raise ValueError("Integrated entry count differs")

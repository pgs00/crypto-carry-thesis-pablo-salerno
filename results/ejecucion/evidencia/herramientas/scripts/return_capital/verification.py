"""Hash, arithmetic and population checks, plus source-based recomputation."""

import json
from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path

from .common import COMPONENTS, close, number, read_csv, read_json, sha256, truth
from .concentration import concentration
from .decisions import classify
from .relations import check_relations


def new_destination(destination, protected):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Destination already exists; choose a new version")
    for root in protected:
        root = Path(root).resolve()
        if destination.is_relative_to(root) or root.is_relative_to(destination):
            raise ValueError("Destination overlaps a protected input")
    return destination


def cell(value):
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def same_rows(actual, expected, label):
    if len(actual) != len(expected):
        raise ValueError(f"{label}: row count changed")
    for ordinal, (a, b) in enumerate(zip(actual, expected)):
        for key in a.keys() | b.keys():
            if cell(a.get(key)) != cell(b.get(key)):
                raise ValueError(f"{label}/{ordinal}/{key}: value changed")


def check_tables(tables):
    check_relations(tables, same_rows)
    boundaries = defaultdict(list)
    for row in tables["fronteras_contables"]:
        boundaries[row["run_id"], row["symbol"]].append(row)
        spot = number(row["spot"]) * number(row["spot_price"], optional=True) - number(
            row["spot_cost"]
        )
        future = number(row["short"]) * (
            number(row["average"]) - number(row["mark_price"], optional=True)
        )
        close(spot, row["spot_unrealized_pnl_usdt"], "boundary spot")
        close(future, row["futures_unrealized_pnl_usdt"], "boundary futures")
        close(
            sum((number(row[k]) for k in COMPONENTS), D(0)),
            row["net_pnl_usdt"],
            "boundary components",
        )
        close(
            number(row["asset_cash"])
            + number(row["collateral"])
            + number(row["spot_cost"])
            + spot
            + future,
            row["net_pnl_usdt"],
            "boundary cash identity",
        )
    expected_segments = {}
    for key, rows in boundaries.items():
        rows.sort(key=lambda r: int(r["time_ns"]))
        for before, after in zip(rows, rows[1:]):
            t, start = int(after["time_ns"]), int(before["time_ns"])
            if t <= start:
                raise ValueError("Duplicate boundary timestamp")
            expected_segments[*key, t] = (before, after)
    if len(expected_segments) != len(tables["atribuciones_segmentos"]):
        raise ValueError("Segment population differs from boundaries")
    daily, cycles, contributions = (
        defaultdict(D),
        defaultdict(D),
        defaultdict(lambda: defaultdict(D)),
    )
    for row in tables["atribuciones_segmentos"]:
        before, after = expected_segments.pop((row["run_id"], row["symbol"], int(row["time_ns"])))
        if (
            int(row["start_ns"]) != int(before["time_ns"])
            or row["cycle_id"] != before["cycle_after"]
            or row["category"] != before["category_after"]
        ):
            raise ValueError("Segment interval or ownership changed")
        for field in (*COMPONENTS, "net_pnl_usdt"):
            close(row[field], number(after[field]) - number(before[field]), "segment " + field)
        daily[row["run_id"], row["date"]] += number(row["net_pnl_usdt"])
        if row["cycle_id"]:
            cycles[row["run_id"], row["cycle_id"]] += number(row["net_pnl_usdt"])
    for row in tables["diario_reutilizado"]:
        close(daily[row["run_id"], row["date"]], row["net_pnl_usdt"], "daily reconciliation")
    for row in tables["ciclos_vida"]:
        close(cycles[row["run_id"], row["cycle_id"]], row["net_pnl_usdt"], "lifetime cycle")
    by_run = defaultdict(list)
    for row in tables["atribuciones_segmentos"]:
        by_run[row["run_id"]].append(row)
    for row in tables["contribuciones_ciclo_periodo"]:
        selected = [
            s
            for s in by_run[row["run_id"]]
            if int(row["start_ns"]) <= int(s["time_ns"]) < int(row["end_exclusive_ns"])
            and s["symbol"] == row["symbol"]
            and s["cycle_id"] == row["cycle_id"]
            and s["category"] == row["category"]
        ]
        if int(row["segments"]) != len(selected):
            raise ValueError("Period segment count changed")
        for field in (*COMPONENTS, "net_pnl_usdt"):
            close(row[field], sum((number(s[field]) for s in selected), D(0)), "period " + field)
            contributions[row["run_id"], row["period"]][field] += number(row[field])
    for row in tables["metricas_reutilizadas"]:
        for field in (*COMPONENTS, "net_pnl_usdt"):
            close(
                contributions[row["run_id"], row["period"]][field], row[field], "financial period"
            )
    for name, ranks in (("concentracion_ciclos", (1, 3, 5)), ("concentracion_dias", (1, 5, 10))):
        grouped = defaultdict(list)
        for row in tables[name]:
            grouped[row["run_id"], row["period"], row.get("symbol", "PORTFOLIO")].append(row)
        for (run, period, symbol), actual in grouped.items():
            first = actual[0]
            if name == "concentracion_ciclos":
                selected = [
                    dict(identity=r["cycle_id"], net_pnl_usdt=r["net_pnl_usdt"])
                    for r in tables["contribuciones_ciclo_periodo"]
                    if r["run_id"] == run
                    and r["period"] == period
                    and r["category"] == "cycle"
                    and (symbol == "PORTFOLIO" or r["symbol"] == symbol)
                ]
            else:
                selected = [
                    dict(identity=r["date"], net_pnl_usdt=r["net_pnl_usdt"])
                    for r in tables["diario_reutilizado"]
                    if r["run_id"] == run
                    and int(first["start_ns"]) <= int(r["time_ns"]) < int(first["end_exclusive_ns"])
                ]
            for a, b in zip(actual, concentration(selected, ranks), strict=True):
                same_rows([{k: a[k] for k in b}], [b], name)
    classified = tables["decisiones_clasificadas"]
    if len({r["evaluation_id"] for r in classified}) != len(classified):
        raise ValueError("Duplicate evaluation identity")
    for row in classified:
        expected = classify(row)
        same_rows([{k: row[k] for k in expected}], [expected], "classification")
    populations = {}
    for row in tables["grupos_excluyentes"]:
        key = row["run_id"], row["period"], row["symbol"], row["decision_kind"]
        if key not in populations:
            populations[key] = [
                r
                for r in classified
                if r["run_id"] == row["run_id"]
                and r["decision_kind"] == row["decision_kind"]
                and (row["symbol"] == "PORTFOLIO" or r["symbol"] == row["symbol"])
                and int(row["start_ns"]) <= int(r["time_ns"]) < int(row["end_exclusive_ns"])
            ]
        selected = populations[key]
        field = {
            "market": "market_cell",
            "sequential": "first_block",
            "actual_decision": "decision",
            "basis_reason": "basis_reason",
        }[row["view"]]
        count = sum((r.get(field) or "not_recorded") == row["group"] for r in selected)
        if int(row["denominator"]) != len(selected) or int(row["count"]) != count:
            raise ValueError("Population denominator or exclusive count changed")
    partitions = defaultdict(int)
    for row in tables["grupos_excluyentes"]:
        key = row["run_id"], row["period"], row["symbol"], row["decision_kind"]
        partitions[*key, row["view"]] += int(row["count"])
    for key, count in partitions.items():
        if count != len(populations[key[:-1]]):
            raise ValueError("Nonexhaustive exclusive partition")
    for row in tables["motivos_simultaneos"]:
        key = row["run_id"], row["period"], row["symbol"], row["decision_kind"]
        selected = populations[key]
        expected = sum(r["filter_" + row["filter"]] == row["state"] for r in selected)
        if int(row["count"]) != expected or int(row["denominator"]) != len(selected):
            raise ValueError("Simultaneous count or denominator changed")
        if (
            row["filter"] in {"funding", "funding_positive"}
            and row["strategy"] == "permanent"
            and truth(row["applied"])
        ):
            raise ValueError("Permanent funding must not be applied")
    original = {(r["run_id"], r["period"]): r for r in tables["metricas_reutilizadas"]}
    for row in tables["resumen_integrado"]:
        source = original[row["run_id"], row["period"]]
        same_rows([{k: row[k] for k in source}], [source], "unchanged financial metrics")
        close(
            number(row["cycle_pnl_usdt"]) + number(row["outside_cycle_pnl_usdt"]),
            row["net_pnl_usdt"],
            "integrated attribution",
        )
        if row["benchmark_status"] != "pendiente_aprobacion_benchmark":
            raise ValueError("Benchmark calculation has not been authorized")
    return dict(
        portfolio_days=len(tables["diario_reutilizado"]),
        cycles=len(tables["ciclos_vida"]),
        evaluations=len(classified),
        segments=len(tables["atribuciones_segmentos"]),
        monetary_tolerance_usdt="1E-8",
        status="passed",
    )


def check_manifest(package):
    manifest = read_json(package / "manifiesto_paquete.json")
    actual = sha256(package / "manifiesto_paquete.json")
    if (package / "manifiesto_paquete.sha256").read_text().split()[0] != actual:
        raise ValueError("Manifest hash mismatch")
    expected_files = {"manifiesto_paquete.json", "manifiesto_paquete.sha256"}
    for row in manifest["members"]:
        path = (package / row["path"]).resolve()
        if not path.is_relative_to(package.resolve()):
            raise ValueError("Unsafe member path")
        if path.stat().st_size != row["bytes"] or sha256(path) != row["sha256"]:
            raise ValueError("Member hash mismatch: " + row["path"])
        expected_files.add(row["path"])
    found = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    if found != expected_files:
        raise ValueError("Manifest membership differs")
    return manifest


def verify(package, dependencies=None):
    package = Path(package).resolve()
    manifest = check_manifest(package)
    tables = {p.stem: read_csv(p) for p in (package / "tablas").glob("*.csv")}
    result = check_tables(tables)
    from .report import verify_report

    verify_report(package, tables, same_rows)
    if dependencies:
        for source in read_json(package / "fuentes.json"):
            path = dependencies[source["dependency"]] / source["path"]
            if sha256(path) != source["sha256"]:
                raise ValueError("Dependency hash mismatch: " + str(path))
        from .tables import derive

        expected = derive(
            dependencies["parent"], dependencies["correction"], dependencies["intraday"]
        )
        if set(expected) != set(tables):
            raise ValueError("Table inventory changed")
        for name in expected:
            same_rows(tables[name], expected[name], "source recomputation " + name)
    result.update(
        scope="complete" if dependencies else "compact",
        source_recomputed=bool(dependencies),
        manifest_sha256=sha256(package / "manifiesto_paquete.json"),
        members=len(manifest["members"]),
        engine_executed=False,
        benchmark="pendiente_aprobacion_benchmark",
        sources_read_only=True,
        limits="Compact checks arithmetic/populations; complete also authenticates and recomputes from explicit source dependencies. Shared postprocessing code, no independent engine validation.",
    )
    return result

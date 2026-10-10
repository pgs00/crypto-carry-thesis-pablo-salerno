"""Selective historical synthesis and saved-state B2/B3 diagnostic. No engine replay."""

from __future__ import annotations

import argparse
import ast
import csv
import gzip
import hashlib
import io
import json
import os
import shutil
from collections import Counter
from decimal import Decimal
from pathlib import Path

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["MPLBACKEND"] = "Agg"

SCHEMA = "stability_synthesis_v3"
BLOCKS = ("BASE", "RIESGO", "B1_CAPITAL", "B1_SOFR", "B2", "B3", "B4", "B5")
QUESTIONS = ("h1", "h2", "h3", "retorno_capital", "riesgo")
LIMITS = {
    "BASE": "reglas prescritas; no historia certificada del exchange",
    "B1_CAPITAL": "descriptivo sobre BASE; sin eliminar ciclos para estimar retornos contrafácticos",
    "B1_SOFR": "hipotética bruta USD; ACT/360 y paridad nominal; riesgo y acceso no equiparables",
    "RIESGO": "intradía previo con cobertura de precios y valoraciones explícitas; no extendido a variantes",
    "B2": "seis variantes aisladas; MAE sólo comparable dentro del mismo horizonte",
    "B3": "ocho variantes aisladas; participación con velas 1m no estima impacto ni colas",
    "B4": "seis variantes aisladas; drawdown diario y ventanas intradía locales",
    "B5": "trayectorias hipotéticas aprobadas; no identifica causalidad ni agrega observaciones históricas",
}
READ_COLUMNS = {
    "risk_events": ("run_id", "symbol", "strategy", "time_ns", "kind", "cause", "previous",
                    "state", "order_id", "cycle_id", "liquidation", "purpose"),
    "orders": ("run_id", "symbol", "strategy", "time_ns", "order_id", "market", "side",
               "purpose", "status", "action", "record_type", "quantity", "remaining_quantity"),
    "positions": ("run_id", "symbol", "strategy", "time_ns", "state", "snapshot_kind", "short"),
}
HISTORY_SPECS = {
    "BASE": ("comparacion/h1_resumen.csv", "comparacion/h2.csv", "comparacion/h3_regimen.csv"),
    "B1_CAPITAL": ("tablas/resumen_integrado.csv", "tablas/concentracion_ciclos.csv",
                   "tablas/h1_resumen_reutilizado.csv", "tablas/h2_reutilizado.csv",
                   "tablas/h3_regimen_reutilizado.csv"),
    "B1_SOFR": ("tablas/comparacion_periodos.csv",),
    "RIESGO": ("tablas/drawdown_comparativo.csv", "tablas/garantias_periodo.csv"),
    "B2": ("tablas/h1_resumen.csv", "tablas/h2.csv", "tablas/h3_resumen.csv", "tablas/metricas.csv", "tablas/invariancias.csv"),
    "B3": ("hipotesis_base/h1_resumen.csv", "tablas/h2.csv", "tablas/h3_resumen.csv", "tablas/metricas.csv", "tablas/invariancias.csv"),
    "B4": ("hipotesis_base/h1_resumen.csv", "tablas/h2.csv", "tablas/h3_resumen.csv", "tablas/metricas.csv", "tablas/invariancias.csv", "tablas/incidentes_resumen.csv"),
    "B5": ("resultados/h1_resumen.csv", "resultados/h2.csv", "resultados/h3_resumen.csv", "resultados/metricas.csv", "resultados/ventanas_resumen.csv"),
}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def write_json_gz(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    path.write_bytes(gzip.compress(raw, mtime=0))


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def csv_text(rows: list[dict], empty_fields=()) -> str:
    fields = list(dict.fromkeys(k for row in rows for k in row)) or list(empty_fields)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list))
                         else v for k, v in row.items()})
    return stream.getvalue()


def write_csv(path: Path, rows: list[dict], empty_fields=()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(csv_text(rows, empty_fields).encode("utf-8"))


def authenticate_member(package: Path, manifest: dict, relative: str) -> str:
    entries = {x["path"].replace("\\", "/"): x
               for x in manifest.get("members", manifest.get("files", []))}
    entry = entries.get(relative)
    if entry is None:
        raise ValueError(f"Member not authenticated by package: {relative}")
    digest = sha256(package / relative)
    if digest != entry["sha256"]:
        raise ValueError(f"SHA256 mismatch: {package / relative}")
    expected_size = entry.get("bytes", entry.get("size"))
    if expected_size is not None and (package / relative).stat().st_size != expected_size:
        raise ValueError(f"Size mismatch: {package / relative}")
    return digest


class Sources:
    """Read only selected members, copying small published sources for audit."""

    def __init__(self, candidate: Path, project: Path, packages: dict[str, str]):
        self.candidate, self.project, self.packages = candidate, project, packages
        self.manifests, self.inventory = {}, []

    def record(self, path: Path, digest: str, *, local: str = "", **metadata) -> None:
        stat = path.stat()
        self.inventory.append(dict(path=str(path.resolve()), sha256=digest, bytes=stat.st_size,
                                   mtime_ns=stat.st_mtime_ns, local=local, **metadata))

    def package(self, block: str) -> tuple[Path, dict]:
        root = self.project / self.packages[block]
        if block not in self.manifests:
            path = root / "manifiesto_paquete.json"
            digest = sha256(path)
            sidecar = root / "manifiesto_paquete.sha256"
            if digest != sidecar.read_text(encoding="utf-8-sig").split()[0]:
                raise ValueError(f"Package sidecar mismatch: {root}")
            self.manifests[block] = read_json(path)
            for file in (path, sidecar):
                local = f"fuentes/sintesis_referencias/{block}/{file.name}"
                target = self.candidate / local
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, target)
                self.record(file, sha256(file), local=local, block=block, role="seal")
        return root, self.manifests[block]

    def member(self, block: str, relative: str, copy=True) -> tuple[Path, dict]:
        root, manifest = self.package(block)
        digest = authenticate_member(root, manifest, relative)
        local = f"fuentes/sintesis_referencias/{block}/{relative}" if copy else ""
        if copy:
            target = self.candidate / local
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / relative, target)
        self.record(root / relative, digest, local=local, block=block, role="selected_member")
        return root / relative, dict(block=block, source_package=self.packages[block],
                                    source_path=relative, source_sha256=digest,
                                    source_local=local, verification_state="autenticado_selectivamente")

    def table(self, block: str, relative: str) -> list[dict]:
        path, meta = self.member(block, relative)
        return [dict(row, **meta) for row in read_csv(path)]


def instrumentation_contract(strategy: str, models: str, reporting: str, observer: str) -> bool:
    """Conservative structural check of the reviewed logging/pending-flag contract."""
    tree = ast.parse(strategy)
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    close = funcs.get("_close")
    if close is None or "_event" not in funcs:
        return False
    writes = []
    for name, func in funcs.items():
        for n in ast.walk(func):
            if isinstance(n, ast.Attribute) and n.attr == "liquidation_pending" \
                    and isinstance(n.ctx, ast.Store):
                writes.append(name)
    if sorted(writes) != ["_close", "_finish_close"]:
        return False
    assignment = next((i for i, n in enumerate(close.body) if isinstance(n, ast.AugAssign)
                       and isinstance(n.target, ast.Attribute)
                       and n.target.attr == "liquidation_pending"
                       and isinstance(n.op, ast.BitOr)
                       and isinstance(n.value, ast.Name) and n.value.id == "liquidate"), None)
    event = next((i for i, n in enumerate(close.body) if isinstance(n, ast.Expr)
                  and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute)
                  and n.value.func.attr == "_event"
                  and any(isinstance(a, ast.Constant) and a.value == "close_requested"
                          for a in n.value.args)
                  and any(k.arg == "liquidation" and isinstance(k.value, ast.Name)
                          and k.value.id == "liquidate" for k in n.value.keywords)), None)
    initializes_false = any(isinstance(n, ast.AnnAssign)
                            and isinstance(n.target, ast.Name)
                            and n.target.id == "liquidation_pending"
                            and isinstance(n.value, ast.Constant) and n.value.value is False
                            for n in ast.walk(ast.parse(models)))
    appends = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr == "append" and isinstance(n.func.value, ast.Attribute)
                  and n.func.value.attr == "risk_events" for n in ast.walk(funcs["_event"]))
    observer_tree = ast.parse(observer)
    observer_class = next((n for n in observer_tree.body if isinstance(n, ast.ClassDef)
                           and n.name == "GapAuditedBacktest"), None)
    observer_safe = (observer_class is not None and not any(
        isinstance(n, ast.FunctionDef) and n.name in ("_event", "_close", "_timeout")
        or isinstance(n, ast.Attribute) and n.attr == "liquidation_pending" and isinstance(n.ctx, ast.Store)
        for n in ast.walk(observer_class)))
    return bool(assignment is not None and event is not None and event == assignment + 2
                and initializes_false and appends and len(funcs["_event"].body) == 1 and observer_safe
                and '("risk_events", b.risk_events)' in reporting
                and 'tables[name].extend(_stamp(rows, b))' in reporting)


def diagnose_records(risks: list[dict], orders: list[dict], positions: list[dict], *,
                     complete: bool, code_instrumented: bool,
                     expected_risk_count: int | None,
                     expected_order_count: int | None) -> dict:
    """Follow escalations to a timeout, ordinary retry or HOLDING with a short.

    Missing evidence cannot exclude the branch. Zero liquidation fills are not
    an input to the exclusion criterion. State joins are within symbol only.
    """
    for row in risks:
        if row.get("liquidation") is not None and not isinstance(row["liquidation"], bool):
            raise ValueError("liquidation must be boolean or null")
    escalations = [r for r in risks if r.get("liquidation") is True
                   or r.get("cause") == "liquidation" or r.get("state") == "LIQUIDATING"]
    orders_event = [r for r in orders if r.get("record_type", "event") == "event"]
    liquidation_orders = [r for r in orders_event if r.get("purpose") == "liquidate"]
    liquidation_states = [r for r in positions if r.get("state") == "LIQUIDATING"]
    coverage = (complete and code_instrumented and expected_risk_count == len(risks)
                and expected_order_count == len({r.get("order_id") for r in orders}))
    events = []
    for escalation in escalations:
        t, symbol = int(escalation["time_ns"]), escalation["symbol"]
        stops = [int(r["time_ns"]) for r in risks if r.get("symbol") == symbol
                 and int(r["time_ns"]) > t and r.get("state") in ("FLAT", "COOLDOWN")]
        stop = min(stops, default=2**63 - 1)
        active = [r for r in positions if r.get("symbol") == symbol
                  and t <= int(r["time_ns"]) < stop
                  and r.get("snapshot_kind", "event") == "event"]
        timeline = [("risk", r) for r in risks if r.get("symbol") == symbol
                    and t < int(r["time_ns"]) < stop]
        timeline += [("order", r) for r in orders_event if r.get("symbol") == symbol
                     and t < int(r["time_ns"]) < stop]
        for kind, row in sorted(timeline, key=lambda pair: int(pair[1]["time_ns"])):
            at = int(row["time_ns"])
            states = [r for r in active if int(r["time_ns"]) <= at]
            state = max(states, key=lambda r: int(r["time_ns"]), default={})
            short = Decimal(str(state["short"])) if state.get("short") is not None else None
            finding = ""
            if kind == "order" and row.get("action") == "timeout":
                finding = "timeout_tras_escalada"
            elif kind == "order" and row.get("action") == "submitted" \
                    and row.get("purpose") in ("close_perp", "correct", "reduce_perp") \
                    and short is not None and short > 0:
                finding = "reintento_ordinario_con_corto"
            elif kind == "risk" and row.get("state") == "HOLDING" \
                    and short is not None and short > 0 \
                    and int(state["time_ns"]) == at and state.get("state") == "HOLDING":
                finding = "holding_con_corto_tras_escalada"
            if finding:
                events.append(dict(symbol=symbol, escalation_time_ns=t, time_ns=at,
                                   finding=finding, short=None if short is None else str(short),
                                   state_time_ns=state.get("time_ns"), order_id=row.get("order_id"),
                                   purpose=row.get("purpose"), cause=row.get("cause")))
    affected = any(r["finding"] in ("reintento_ordinario_con_corto",
                                   "holding_con_corto_tras_escalada") for r in events)
    status = "afectada" if affected else "indeterminada" if not coverage else (
        "pendiente_escalada" if escalations or liquidation_orders or liquidation_states
        else "rama_no_activada")
    return dict(status=status, risk_rows=len(risks), order_rows=len(orders),
                distinct_orders=len({r.get("order_id") for r in orders}),
                position_rows=len(positions), liquidation_event_rows=len(escalations),
                liquidation_order_rows=len(liquidation_orders),
                liquidation_state_rows=len(liquidation_states), coverage_complete=coverage,
                events=events,
                criterion="flag starts false; only activation logs close_requested(liquidation=true); "
                          "full risk log and native counters; orders and positions cross-checked; "
                          "absence of liquidation fills is not the criterion")


def verify_diagnostics(candidate: Path) -> dict:
    cases = json.loads(gzip.decompress((candidate / "fuentes/sintesis_diagnostico.json.gz").read_bytes()))
    results, events = [], []
    for case in cases:
        args = {k: case[k] for k in ("risks", "orders", "positions", "complete", "code_instrumented",
                                    "expected_risk_count", "expected_order_count")}
        result = diagnose_records(**args)
        identity = {k: case[k] for k in ("block", "scenario", "strategy", "run_id")}
        events.extend(dict(**identity, **event) for event in result.pop("events"))
        results.append(dict(**identity, **result))
    return dict(schema=SCHEMA, runs=results, events=events,
                statuses=dict(Counter(x["status"] for x in results)))


def collect_diagnostics(sources: Sources, data_root: Path) -> tuple[list[dict], list[dict]]:
    import pyarrow as pa
    import pyarrow.parquet as pq

    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    code = {}
    for name in ("strategy.py", "models.py", "reporting.py", "mark_gap_study.py"):
        path, _ = sources.member("B3", f"codigo_ejecutado/src/crypto_carry/{name}")
        code[name] = (sha256(path), path.read_text(encoding="utf-8"))
    instrumented = instrumentation_contract(*(code[x][1] for x in
                                               ("strategy.py", "models.py", "reporting.py", "mark_gap_study.py")))
    cases, coverage = [], []
    for block in ("B2", "B3"):
        path, _ = sources.member(block, "indice_corridas.json")
        for run in read_json(path)["runs"]:
            if run["scenario"] == "BASE_E3":
                continue
            prefix = run["path"].replace("\\", "/")
            mp, _ = sources.member(block, f"{prefix}/run_manifest.json")
            manifest = read_json(mp)
            if sha256(mp) != run["manifest_sha256"]:
                raise ValueError(f"Indexed run manifest differs: {run['run_id']}")
            sm, _ = sources.member(block, f"{prefix}/run_summary.csv")
            summary = read_csv(sm)
            saved = {}
            for name, columns in READ_COLUMNS.items():
                file, meta = sources.member(block, f"{prefix}/{name}.parquet")
                if meta["source_sha256"] != manifest["output_hashes"][f"{name}.parquet"]:
                    raise ValueError(f"Run output differs: {file}")
                parquet = pq.ParquetFile(file)
                saved[name] = parquet.read(columns=[c for c in columns if c in parquet.schema_arrow.names],
                                           use_threads=False).to_pylist()
                if any(x.get("run_id") != run["run_id"] for x in saved[name]):
                    raise ValueError(f"Mixed run identity: {file}")
            original = Path(run.get("original_path_hint", data_root / "outputs" / run["run_id"]))
            execution = original / "execution_summary.csv"
            expected_risks = expected_orders = None
            if execution.exists():
                digest = sha256(execution)
                if digest != manifest["output_hashes"].get(execution.name):
                    raise ValueError(f"Native execution counter hash mismatch: {execution}")
                local = f"fuentes/sintesis_referencias/{block}/{run['run_id']}_execution_summary.csv"
                shutil.copyfile(execution, sources.candidate / local)
                sources.record(execution, digest, local=local, block=block, role="native_counter")
                native = next(x for x in read_csv(execution) if x["symbol"] == "PORTFOLIO"
                              and x["strategy"] == run["strategy"])
                expected_risks, expected_orders = int(native["risk_events"]), int(native["orders"])
            log_name = str(run.get("log", "")).replace("\\", "/").split("/")[-1]
            log_rel = f"ejecucion/logs_corridas/{log_name}"
            root, sealed = sources.package(block)
            if not log_name:
                log_prefix = f"ejecucion/logs_corridas/{run['scenario']}__{run['strategy']}__"
                for member in sealed["members"]:
                    if member["path"].startswith(log_prefix):
                        trial_log = root / member["path"]
                        if run["run_id"] in trial_log.read_text(encoding="utf-8-sig"):
                            log_rel, log_name = member["path"], trial_log.name
                            break
            log_complete = False
            if log_name and (root / log_rel).exists():
                log, _ = sources.member(block, log_rel)
                text = log.read_text(encoding="utf-8-sig")
                log_complete = "REPLAY_COMPLETE" in text and run["run_id"] in text
            matched_code = all(manifest["code_files"].get(f"src/crypto_carry/{name}") == digest
                               for name, (digest, _) in code.items())
            complete = (manifest.get("artifacts_complete") is True and manifest.get("status") == "complete"
                        and len(summary) == 1 and summary[0]["status"] == "complete"
                        and not summary[0].get("stopped_at") and log_complete)
            identity = dict(block=block, scenario=run["scenario"], strategy=run["strategy"], run_id=run["run_id"])
            cases.append(dict(**identity, risks=saved["risk_events"], orders=saved["orders"],
                              positions=saved["positions"], complete=complete,
                              code_instrumented=instrumented and matched_code,
                              expected_risk_count=expected_risks, expected_order_count=expected_orders))
            coverage.append(dict(**identity, manifest_sha256=run["manifest_sha256"],
                                 start_utc=manifest["requested_range"]["start"],
                                 end_exclusive_utc=manifest["requested_range"]["end"],
                                 observed_end=manifest["observed_range"]["end"],
                                 run_complete=complete, saved_execution_log_complete=log_complete,
                                 code_matches_run=matched_code, activation_logging_proven=instrumented,
                                 native_risk_count=expected_risks, native_order_count=expected_orders,
                                 risk_rows=len(saved["risk_events"]), order_rows=len(saved["orders"]),
                                 position_rows=len(saved["positions"]),
                                 scope="28 variants only; two BASE references excluded from this audit; no replay"))
    return cases, coverage


def historical_sources(sources: Sources) -> dict:
    result = {}
    for block, files in HISTORY_SPECS.items():
        result[block] = {name: sources.table(block, name) for name in files}
        if block in ("B2", "B3", "B4", "B5"):
            p, _ = sources.member(block, "indice_corridas.json")
            result[block]["runs"] = read_json(p)["runs"]
    # B5's scoped compatibility records are reused; no package-wide rescans.
    for name in ("controles/sellos_entrada.json", "controles/compatibilidad_recalculada.json",
                 "controles/identidades_corridas.json", "entradas_compatibilidad.md",
                 "fuentes/consigna_academica_extraida.txt"):
        sources.member("B5", name)
    sources.member("RIESGO", "documentos/feedback_e3.md")
    return result


def cached_history(candidate: Path, project: Path, data_root: Path) -> tuple[dict, bool]:
    matrix = read_csv(project / "docs/entrega_4/matriz_avance.csv")
    packages = {r["id"]: r["paquete_vigente"] for r in matrix if r["id"] in BLOCKS}
    cache = candidate / "fuentes/sintesis_historico.json"
    inventory_path = candidate / "fuentes/sintesis_inventario.json"
    if cache.exists() and inventory_path.exists():
        inventory = read_json(inventory_path)
        valid = inventory.get("schema") == SCHEMA and inventory.get("packages") == packages
        for entry in inventory.get("sources", []) if valid else []:
            path = Path(entry["path"])
            if not path.exists():
                valid = False
                break
            stat = path.stat()
            if (stat.st_size != entry["bytes"] or stat.st_mtime_ns != entry["mtime_ns"]) \
                    and sha256(path) != entry["sha256"]:
                valid = False
                break
        for name, digest in inventory.get("compact_outputs", {}).items() if valid else []:
            if not (candidate / name).exists() or sha256(candidate / name) != digest:
                valid = False
                break
        if valid:
            return read_json(cache), True
    sources = Sources(candidate, project, packages)
    history = historical_sources(sources)
    cases, coverage = collect_diagnostics(sources, data_root)
    write_json(cache, history)
    write_json_gz(candidate / "fuentes/sintesis_diagnostico.json.gz", cases)
    write_csv(candidate / "tablas/diagnostico_b2_b3_cobertura.csv", coverage)
    compact = ("fuentes/sintesis_historico.json", "fuentes/sintesis_diagnostico.json.gz",
               "tablas/diagnostico_b2_b3_cobertura.csv")
    write_json(inventory_path, dict(schema=SCHEMA, packages=packages, sources=sources.inventory,
                                   compact_outputs={name: sha256(candidate / name) for name in compact},
                                   massive_inputs_reread=False, historical_replays=0,
                                   verification_scope="selected sealed summaries, run event/state logs and native counters; B5 compatibility reused"))
    return history, False


def attach_run_ids(rows: list[dict], runs: list[dict]) -> list[dict]:
    for row in rows:
        match = [r for r in runs if r["scenario"] == row.get("scenario")
                 and (not row.get("strategy") or r["strategy"] == row["strategy"])]
        if not row.get("run_id"):
            row["run_ids"] = ";".join(r["run_id"] for r in match)
    return rows


def make_tables(history: dict, candidate: Path, diagnostic: dict) -> dict[str, list[dict]]:
    tables = {q: [] for q in QUESTIONS}
    scenario_rows = []
    statuses = {r["run_id"]: r["status"] for r in diagnostic["runs"]}
    for block, values in history.items():
        for name, original in values.items():
            if name == "runs":
                continue
            rows = [dict(r) for r in original if block != "BASE" or r.get("scenario") == "BASE_E3"]
            attach_run_ids(rows, values.get("runs", []))
            for row in rows:
                row["limitation"] = LIMITS[block]
                if block in ("B2", "B3"):
                    ids = [row.get("run_id", ""), row.get("conditional_run_id", ""), row.get("permanent_run_id", "")]
                    ids += row.get("run_ids", "").split(";")
                    relevant = [statuses[x] for x in ids if x in statuses]
                    row["liquidation_diagnostic"] = ";".join(sorted(set(relevant))) or "no_aplica_o_BASE"
                    row["conclusion_condition"] = ("pendiente_alcance_defecto" if any(x != "rama_no_activada" for x in relevant)
                                                   else "rama_defectuosa_excluida_en_logs_autenticados" if relevant
                                                   else "no_aplica_o_BASE_reutilizada")
            if "h1_resumen" in name:
                if block in ("B3", "B4"):
                    for row in rows:
                        row["scope"] = "H1 BASE reutilizada; invariancia por variante en tabla fuente invariancias"
                tables["h1"].extend(rows)
            elif name.endswith(("h2.csv", "h2_reutilizado.csv")):
                tables["h2"].extend(rows)
            elif "h3_" in name:
                tables["h3"].extend(rows)
            elif name.endswith(("metricas.csv", "resumen_integrado.csv", "comparacion_periodos.csv")):
                for row in rows:
                    row["risk_comparability"] = ("SOFR hipotética bruta USD, ACT/360, paridad nominal; riesgo/acceso no equiparables"
                                                  if block == "B1_SOFR" else "neto de costos modelados; capital medio diario")
                    if row.get("period") == "full" and row.get("scenario") != "BASE_E3":
                        scenario_rows.append(row)
                tables["retorno_capital"].extend(rows)
            elif name.endswith("drawdown_comparativo.csv"):
                for row in rows:
                    row["risk_scope"] = "intradía global previo; valoración y cobertura originales/proxy separadas"
                tables["riesgo"].extend(rows)
            elif name.endswith("garantias_periodo.csv"):
                for row in rows:
                    row["risk_scope"] = "garantías intradía previas; transferencias no son P&L"
                tables["riesgo"].extend(rows)
            elif name.endswith(("incidentes_resumen.csv", "ventanas_resumen.csv")):
                for row in rows:
                    row["risk_scope"] = "ventanas locales examinadas; no máximo intradía global"
                tables["riesgo"].extend(rows)
            elif name.endswith("invariancias.csv"):
                for row in rows:
                    row["evidence_type"] = "controles_invariancia_pronostico_y_cobertura"
                tables["h1"].extend(rows)
    for filename, question in (("metricas.csv", "retorno_capital"), ("h2.csv", "h2"), ("h3_cobertura.csv", "h3")):
        file = candidate / "tablas" / filename
        if file.exists():
            tables[question].extend(dict(r, block="B6", source_package="candidato_B6",
                                         source_path=f"tablas/{filename}", source_sha256=sha256(file),
                                         verification_state="derivado_B6_verificacion_financiera_separada",
                                         limitation="reinicio nuevo versus saldos heredados; historia ya examinada; H3 original no validable con inicios parciales") for r in read_csv(file))
    intervals = candidate / "tablas/bootstrap_intervalos.csv"
    if intervals.exists():
        for row in read_csv(intervals):
            question = row["hypothesis"].lower()
            if question in tables:
                tables[question].append(dict(row, block="B6_BOOTSTRAP", source_package="candidato_B6",
                                             source_path="tablas/bootstrap_intervalos.csv", source_sha256=sha256(intervals),
                                             verification_state="posprocesamiento_BASE; verificacion_estadistica_separada",
                                             limitation="intervalos marginales nominales; estabilidad aproximada intraestrato; sin probabilidades de verdad/ganancia futura"))
    tables["escenarios_previos"] = scenario_rows
    return tables


def fmt(value, percent=False) -> str:
    if value in (None, ""):
        return "ND"
    try:
        n = Decimal(str(value))
        return f"{n * 100:.3f}%" if percent else f"{n:.4f}"
    except Exception:
        return str(value)


def render(candidate: Path, tables: dict, diagnostic: dict, cache_reused: bool, *, write=True) -> dict:
    h2 = [r for r in tables["h2"] if r.get("verdict")]
    historical_h2 = [r for r in h2 if r["block"] in ("BASE", "B2", "B3", "B4", "B5")]
    favorable = [r for r in historical_h2 if r["verdict"] == "favorable"]
    table = ["| Bloque / escenario | Períodos favorables H2 | Fuente |", "|---|---|---|"]
    groups = {}
    for r in favorable:
        key = (r["block"], r["scenario"])
        groups.setdefault(key, []).append(r)
    for (block, scenario), rows in groups.items():
        table.append(f"| {block} / {scenario} | {', '.join(r['period'] for r in rows)} | "
                     f"[tabla autenticada]({rows[0]['source_local']}) |")
    base_h2 = next(r for r in historical_h2 if r["block"] == "BASE" and r["period"] == "full")
    base_metrics = [r for r in tables["retorno_capital"] if r["block"] == "B1_CAPITAL" and r["period"] == "full"]
    base_cap = "; ".join(f"{r['strategy']}: retorno {fmt(r['net_return'], True)}, CAGR365 {fmt(r['cagr'], True)}, "
                         f"capital medio utilizado {fmt(r['capital_utilization_daily_mean'], True)}, "
                         f"actividad sin polvo {fmt(r['invested_fraction'], True)}" for r in base_metrics)
    sofr = next(r for r in tables["retorno_capital"] if r["block"] == "B1_SOFR"
                and r["period"] == "full" and r.get("portfolio") not in ("conditional", "permanent"))
    no_branch = diagnostic["statuses"].get("rama_no_activada", 0)
    pending = [r["run_id"] for r in diagnostic["runs"] if r["status"] != "rama_no_activada"]
    b6_ready = all((candidate / "tablas" / f).exists() for f in
                   ("metricas.csv", "h2.csv", "h3_cobertura.csv", "bootstrap_intervalos.csv"))
    interval_table = ["| Efecto BASE, bloques 28 días | Punto | IC marginal nominal 95% | Evaluables |",
                      "|---|---:|---:|---:|"]
    labels = {"h1_mae_delta_bps": "H1: delta MAE BTC/ETH 50/50 (pb/168 h)",
              "h2_conditional_cagr": "H2: CAGR condicional",
              "h2_sharpe_delta": "H2: diferencia Sharpe RF=0",
              "h3_opportunity_delta_bps": "H3: diferencia oportunidad (pb/168 h)",
              "h3_conditional_cagr_delta": "H3: diferencia CAGR (puntos porcentuales)"}
    for question in ("h1", "h2", "h3"):
        for row in tables[question]:
            if row.get("block") != "B6_BOOTSTRAP" or str(row.get("block_length_days")) != "28":
                continue
            if row.get("period") not in ("full", "2024+ minus 2022-2023"):
                continue
            if question == "h1" and row.get("symbol") != "EQUAL_WEIGHT":
                continue
            percent = "cagr" in row["metric"]
            label = labels.get(row["metric"], row["metric"])
            point, low, high = (fmt(row.get(key), percent) for key in
                                ("point_estimate", "interval_low", "interval_high"))
            if row["metric"] == "h3_conditional_cagr_delta":
                point, low, high = (x.replace("%", " pp") for x in (point, low, high))
            interval_table.append(f"| {label} | {point} | [{low}, {high}] | "
                                  f"{row['valid_replicates']}/{row['n_replicates']} |")
    if len(interval_table) == 2:
        interval_table = ["Intervalos aún pendientes de cálculo/incorporación."]
    lines = ["# Síntesis integrable: estabilidad, incertidumbre y bloques previos", "",
             "Esta síntesis reutiliza cifras identificadas por paquete, ruta, SHA-256 y run_id. "
             "La autenticación es selectiva: se releen los resúmenes y registros utilizados; "
             "la integridad histórica integral y compatibilidad BASE se reutilizan del bloque 5. "
             "No se repiten los bloques 1–5 ni se simula dentro del bootstrap.", "",
             "## H1: capacidad descriptiva del pronóstico", "",
             "[Tabla por pregunta: H1](tablas/sintesis_h1.csv). Se conservan MAE por activo y el promedio "
             "BTC/ETH 50/50; el bootstrap pondera sumas/conteos originales, con exclusiones del borde final. "
             "Un delta MAE EWMA menos no-cambio negativo favorece descriptivamente EWMA. "
             "H072 y H336 tienen horizontes distintos: sus MAE sólo se comparan dentro de cada horizonte. "
             "B1 interpreta BASE; B3/B4 preservan el pronóstico y sus controles de invariancia. "
             "B5 no añade observaciones históricas al remuestreo.", "",
             "## H2: retorno positivo y Sharpe superior al permanente", "",
             f"[Tabla por pregunta: H2](tablas/sintesis_h2.csv). BASE total: {base_h2['verdict']}; "
             f"CAGR condicional {fmt(base_h2['conditional_cagr'], True)} y diferencia Sharpe "
             f"{fmt(base_h2['sharpe_difference'])}. En 2022 el Sharpe condicional es ND por volatilidad "
             "nula: no se reemplaza por cero. Los días inactivos siguen incluidos.", "",
             "Las excepciones favorables acreditadas son las siguientes; se conservan todos sus períodos, "
             "sin generalizar el resultado total a los años ni seleccionar un ganador.", "", *table, "",
             "Los inicios B6 comparan las dos estrategias del mismo inicio y período. Sus cuentas nuevas "
             "desde 10.000 USDT se distinguen de los tramos BASE con saldos heredados. Los intervalos "
             "marginales de CAGR y diferencia Sharpe complementan el veredicto histórico; dos intervalos "
             "al 95% no constituyen un contraste conjunto al 95%.", "",
             "## H3: contraste original de regímenes", "",
             "[Tabla por pregunta: H3](tablas/sintesis_h3.csv). El contraste original conserva "
             "2022–2023 frente a 2024–agosto de 2026, oportunidad media en pb/168 h y CAGR condicional. "
             "BASE y las sensibilidades examinadas mantienen la dirección contraria documentada; "
             "los años son un desglose descriptivo. I2023/I2024 no validan H3 original por faltar parte "
             "o todo el primer régimen. El bootstrap conserva regímenes, años y pesos históricos.", "",
             "## Retorno, capital, costos y comparador remunerado", "",
             f"[Tabla por pregunta](tablas/sintesis_retorno_capital.csv). BASE, 1.704 días: {base_cap}. "
             "Son retornos netos de los costos modelados; el P&L monetario de cuentas con denominadores "
             "distintos no es directamente comparable. Pocos ciclos, inactividad y concentración "
             "siguen limitando la extrapolación; B1 no elimina ciclos para fabricar un CAGR contrafáctico.", "",
             f"SOFR: retorno {fmt(sofr['net_return'], True)} y CAGR365 {fmt(sofr['cagr365'], True)} en "
             "la cuenta hipotética bruta USD aprobada, ACT/360 y paridad nominal 1 USDT = 1 USD. "
             "No equivale a una cuenta accesible ni a rentabilidad libre de riesgo realizada; no se "
             "remunera caja ni garantías del carry. Acceso, costos y riesgo no son equiparables.", "",
             "[Escenarios previos con sus IDs](tablas/sintesis_escenarios_previos.csv): B2 cambia señal/entrada; "
             "B3 mantiene selección a 34 pb y distingue costos, participación y capital; B4 altera "
             "convención/demora; B5 usa trayectorias hipotéticas aprobadas, recuperación impuesta y "
             "anclas fijas. Sus diferencias no identifican causalidad histórica ni probabilidades.", "",
             "## Riesgo, garantías y definiciones de drawdown", "",
             "[Tabla por pregunta](tablas/sintesis_riesgo.csv). El drawdown diario de las sensibilidades "
             "usa cierres diarios. El intradía global previo reconstruye la trayectoria BASE/MARGEN_2X "
             "con cobertura y valoración identificadas; la suspensión de marzo de 2023 conserva "
             "el precio antiguo/proxy hipotético separado. Las ventanas locales B4/B5 no son máximos "
             "intradía globales ni sustituyen esa reconstrucción. Garantías, reservas y transferencias "
             "no se agregan como P&L.", "",
             "## Diagnóstico dirigido del defecto de prioridad de liquidación en B2/B3", "",
             f"Resultado: {no_branch}/{len(diagnostic['runs'])} variantes con precondición excluida "
             f"por evidencia; {len(pending)} afectadas o indeterminadas. "
             "[Corridas](tablas/diagnostico_b2_b3_corridas.csv), "
             "[cobertura](tablas/diagnostico_b2_b3_cobertura.csv), "
             "[secuencias](tablas/diagnostico_b2_b3_eventos.csv).", "",
             "El código autenticado de cada corrida inicia liquidation_pending=False; su única "
             "activación ocurre en _close e inmediatamente registra close_requested con liquidation=True. "
             "_event persiste todos los eventos; se contrastan contadores nativos, manifiesto de corrida "
             "completa, log de finalización, órdenes y posiciones. Se busca escalada seguida por timeout, "
             "reintento ordinario o HOLDING con corto remanente, por activo y sin inferir el estado "
             "desde un fill ausente. La exclusión se refiere sólo a esa rama y esas corridas; no demuestra "
             "equivalencia universal entre motores ni certifica reglas históricas del exchange.", "",
             ("Pendientes que condicionan conclusiones B2/B3: " + ", ".join(pending)) if pending else
             "No quedan run_id indeterminados para esta rama dentro de las 28 variantes examinadas. "
             "El resultado permite cerrar este pendiente dirigido, manteniendo la revisión transversal separada.", "",
             "## Incertidumbre, cobertura y estado", "",
             "El remuestreo BASE utiliza bloques circulares emparejados dentro de año/segmento contiguo: "
             "28 días principal y 14/56 como sensibilidad, 5.000 réplicas por longitud, raíz 20261001, "
             "PCG64/SeedSequence e intervalos percentiles marginales nominales 95%. Circularidad no "
             "es contigüidad real; estratificar corta dependencia entre años y supone estabilidad "
             "aproximada dentro del estrato. No garantiza cobertura exacta ni elimina no estacionariedad. "
             "Las frecuencias no son probabilidades de verdad de hipótesis o ganancia futura. "
             "Menos de 95% evaluables deja el intervalo principal ND; cuantiles finitos quedan "
             "condicionados a evaluabilidad. No se selecciona longitud por conveniencia.", "", *interval_table, "",
             "Los inicios alternativos usan historia ya examinada y no son validación fuera de muestra. "
             "2026 es parcial, no se crean ceros previos al inicio y cada corte muestra sus fechas reales.", "",
             ("Las tablas B6 de inicios e intervalos ya se incorporaron; su validación corresponde a "
              "los verificadores financiero y estadístico del paquete." if b6_ready else
              "Candidato parcial: faltan tablas finales de los inicios B6; "
              + ("los intervalos BASE ya están incorporados; " if len(interval_table) > 1 else "los intervalos siguen pendientes; ") +
              "este estado no declara B6 terminado."), "",
             "La síntesis incorpora la extracción autenticada de la consigna académica B5 y el feedback E3. "
             "La revisión transversal y Word/PDF permanecen pendientes.", ""]
    state = dict(schema=SCHEMA, historical_cache_reused=cache_reused, b6_tables_incorporated=b6_ready,
                 diagnostic_statuses=diagnostic["statuses"], diagnostic_pending_run_ids=pending,
                 historical_replays=0, branch_scope="only liquidation_pending timeout regression, B2/B3 variants",
                 academic_revision="pendiente", word_pdf="pendiente", published=False)
    if not write:
        return dict(state=state, markdown="\n".join(lines))
    (candidate / "sintesis.md").write_text("\n".join(lines), encoding="utf-8")
    write_json(candidate / "fuentes/sintesis_estado.json", state)
    return state


def build(candidate: Path, project: Path, data_root: Path) -> dict:
    candidate, project, data_root = Path(candidate), Path(project), Path(data_root)
    history, reused = cached_history(candidate, project, data_root)
    diagnostic = verify_diagnostics(candidate)
    write_csv(candidate / "tablas/diagnostico_b2_b3_corridas.csv", diagnostic["runs"])
    write_csv(candidate / "tablas/diagnostico_b2_b3_eventos.csv", diagnostic["events"],
              ("block", "scenario", "strategy", "run_id", "symbol", "escalation_time_ns", "time_ns", "finding", "short"))
    tables = make_tables(history, candidate, diagnostic)
    for question, rows in tables.items():
        write_csv(candidate / f"tablas/sintesis_{question}.csv", rows)
    return render(candidate, tables, diagnostic, reused)


def verify(candidate: Path) -> dict:
    """Read-only offline reproduction using the included selective source copies.

    Historical economic summaries are authenticated, not rerun. The branch
    diagnostic is recomputed from full saved events, orders and states whose
    bytes match both historical package and run manifests. Financial B6 and
    bootstrap inputs are independently recomputed by their respective helpers.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    candidate = Path(candidate)
    inventory = read_json(candidate / "fuentes/sintesis_inventario.json")
    if inventory.get("schema") != SCHEMA:
        raise ValueError("Unsupported synthesis source schema")
    manifests = {}
    for block in BLOCKS:
        folder = candidate / "fuentes/sintesis_referencias" / block
        manifest = folder / "manifiesto_paquete.json"
        if sha256(manifest) != (folder / "manifiesto_paquete.sha256").read_text(encoding="utf-8-sig").split()[0]:
            raise ValueError(f"Copied historical seal mismatch: {block}")
        manifests[block] = read_json(manifest)
    copied = {}
    for entry in inventory["sources"]:
        local = entry.get("local")
        if not local or local in copied:
            continue
        file = candidate / local
        if sha256(file) != entry["sha256"]:
            raise ValueError(f"Copied source SHA256 mismatch: {local}")
        copied[local] = entry
    for local, digest in inventory["compact_outputs"].items():
        if sha256(candidate / local) != digest:
            raise ValueError(f"Compact source SHA256 mismatch: {local}")

    def member(block, relative):
        folder = candidate / "fuentes/sintesis_referencias" / block
        authenticate_member(folder, manifests[block], relative)
        return folder / relative

    historical = {}
    for block, files in HISTORY_SPECS.items():
        historical[block] = {}
        for relative in files:
            file = member(block, relative)
            metadata = dict(block=block, source_package=inventory["packages"][block],
                            source_path=relative, source_sha256=sha256(file),
                            source_local=f"fuentes/sintesis_referencias/{block}/{relative}",
                            verification_state="autenticado_selectivamente")
            historical[block][relative] = [dict(row, **metadata) for row in read_csv(file)]
        if block in ("B2", "B3", "B4", "B5"):
            historical[block]["runs"] = read_json(member(block, "indice_corridas.json"))["runs"]
    if historical != read_json(candidate / "fuentes/sintesis_historico.json"):
        raise ValueError("Historical cache differs from authenticated copied summaries")
    code = {}
    for name in ("strategy.py", "models.py", "reporting.py", "mark_gap_study.py"):
        file = member("B3", f"codigo_ejecutado/src/crypto_carry/{name}")
        code[name] = (sha256(file), file.read_text(encoding="utf-8"))
    instrumented = instrumentation_contract(*(code[x][1] for x in
                                               ("strategy.py", "models.py", "reporting.py", "mark_gap_study.py")))
    cases = json.loads(gzip.decompress((candidate / "fuentes/sintesis_diagnostico.json.gz").read_bytes()))
    by_id = {case["run_id"]: case for case in cases}
    expected_ids = set()
    total_raw = Counter()
    for block in ("B2", "B3"):
        for run in historical[block]["runs"]:
            if run["scenario"] == "BASE_E3":
                continue
            expected_ids.add(run["run_id"])
            case = by_id[run["run_id"]]
            if any(case[k] != run[k] for k in ("run_id", "scenario", "strategy")) or case["block"] != block:
                raise ValueError("Diagnostic identity mismatch")
            prefix = run["path"].replace("\\", "/")
            manifest_file = member(block, f"{prefix}/run_manifest.json")
            if sha256(manifest_file) != run["manifest_sha256"]:
                raise ValueError("Indexed original manifest mismatch")
            manifest = read_json(manifest_file)
            for name, columns in READ_COLUMNS.items():
                file = member(block, f"{prefix}/{name}.parquet")
                if sha256(file) != manifest["output_hashes"][file.name]:
                    raise ValueError("Original run output hash mismatch")
                parquet = pq.ParquetFile(file)
                rows = parquet.read(columns=[c for c in columns if c in parquet.schema_arrow.names],
                                    use_threads=False).to_pylist()
                key = "risks" if name == "risk_events" else name
                if rows != case[key]:
                    raise ValueError(f"Diagnostic projection differs from source: {run['run_id']}/{name}")
                total_raw[name] += len(rows)
            counter_name = f"fuentes/sintesis_referencias/{block}/{run['run_id']}_execution_summary.csv"
            counter_file = candidate / counter_name
            if counter_file.exists():
                if sha256(counter_file) != manifest["output_hashes"]["execution_summary.csv"]:
                    raise ValueError("Native counter source mismatch")
                counts = next(x for x in read_csv(counter_file) if x["symbol"] == "PORTFOLIO"
                              and x["strategy"] == run["strategy"])
                if case["expected_risk_count"] != int(counts["risk_events"]) \
                        or case["expected_order_count"] != int(counts["orders"]):
                    raise ValueError("Diagnostic native counters differ")
            elif case["expected_risk_count"] is not None or case["expected_order_count"] is not None:
                raise ValueError("Missing native execution counters")
            summary = read_csv(member(block, f"{prefix}/run_summary.csv"))
            log_complete = False
            folder = candidate / "fuentes/sintesis_referencias" / block
            for log in (folder / "ejecucion/logs_corridas").glob(f"{run['scenario']}__{run['strategy']}__*"):
                member(block, log.relative_to(folder).as_posix())
                text = log.read_text(encoding="utf-8-sig")
                log_complete |= "REPLAY_COMPLETE" in text and run["run_id"] in text
            complete = (manifest.get("artifacts_complete") is True and manifest.get("status") == "complete"
                        and len(summary) == 1 and summary[0]["status"] == "complete"
                        and not summary[0].get("stopped_at") and log_complete)
            matched = all(manifest["code_files"].get(f"src/crypto_carry/{n}") == digest
                          for n, (digest, _) in code.items())
            if case["complete"] != complete or case["code_instrumented"] != (matched and instrumented):
                raise ValueError("Claimed event coverage differs from original evidence")
    if set(by_id) != expected_ids or len(cases) != len(expected_ids):
        raise ValueError("Diagnostic scope must contain exactly the 28 original variants")
    diagnostic = verify_diagnostics(candidate)
    checks = {"diagnostico_b2_b3_corridas.csv": csv_text(diagnostic["runs"]),
              "diagnostico_b2_b3_eventos.csv": csv_text(diagnostic["events"],
                 ("block", "scenario", "strategy", "run_id", "symbol", "escalation_time_ns", "time_ns", "finding", "short"))}
    tables = make_tables(historical, candidate, diagnostic)
    checks.update({f"sintesis_{q}.csv": csv_text(rows) for q, rows in tables.items()})
    for name, expected in checks.items():
        if (candidate / "tablas" / name).read_bytes() != expected.encode("utf-8"):
            raise ValueError(f"Synthesis table reproduction mismatch: {name}")
    state = read_json(candidate / "fuentes/sintesis_estado.json")
    expected = render(candidate, tables, diagnostic, state["historical_cache_reused"], write=False)
    if state != expected["state"] or (candidate / "sintesis.md").read_text(encoding="utf-8") != expected["markdown"]:
        raise ValueError("Synthesis narrative or state differs from reproduced claims")
    return dict(status="passed", schema=SCHEMA, offline=True, read_only=True,
                source_copies_verified=len(copied), diagnostic_runs=len(cases),
                diagnostic_statuses=diagnostic["statuses"], raw_rows_rechecked=dict(total_raw),
                tables_reproduced=len(checks), historical_economics="authenticated summaries reused, no replay",
                b6_economics="financial verifier", bootstrap="statistical verifier",
                massive_market_data_reread=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--data-root", type=Path, default=Path("D:/Backtesting"))
    parser.add_argument("--verify-diagnostics", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = verify(args.candidate) if args.verify else (
        verify_diagnostics(args.candidate) if args.verify_diagnostics else build(
            args.candidate, args.project, args.data_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

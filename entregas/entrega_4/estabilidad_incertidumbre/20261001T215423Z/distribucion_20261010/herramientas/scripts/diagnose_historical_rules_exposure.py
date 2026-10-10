"""Offline candidate exposure on persisted BASE_E3 records; never a rulebook/backtest.

Reads immutable evidence and runs, using Decimal values. All source observations are
screened atemporally, with no forward fill, implied validity, or historical knowledge.
Output must be a new directory. No trading engine is imported.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pandas as pd

D = Decimal
PACKAGE = "data/research/historical-rules-followup-20260924T234206Z"
RUN_IDS = ("run_ad71d751b20623006c195ff3", "run_dfea4b7ac1475668d5968c97")
SYMBOLS = ("BTCUSDT", "ETHUSDT")
INVENTORY: dict[str, dict] = {}


def inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes root: {relative}")
    return path


def read_bytes(path: Path, purpose: str, expected: str | None = None) -> bytes:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError(f"SHA-256 mismatch: {path}")
    key = str(path.resolve())
    previous = INVENTORY.get(key, {}).get("read_purpose", "")
    INVENTORY[key] = {"path": key, "bytes": len(raw), "sha256": digest,
                      "read_purpose": "; ".join(dict.fromkeys([previous, purpose])).strip("; ")}
    return raw


def read_json(path: Path, purpose: str) -> dict | list:
    return json.loads(read_bytes(path, purpose).decode("utf-8-sig"))


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
                    encoding="utf-8", newline="\n")


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    columns = fields or list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def quantity_candidate(q: Decimal, component: str, limit: Decimal) -> tuple[bool | None, str]:
    if limit == 0:
        return None, "published_zero_semantics_unresolved"
    if limit < 0:
        raise ValueError("negative filter limit")
    if component == "stepSize":
        return q % limit != 0, "quantity_modulo_positive_step"
    if component == "minQty":
        return q < limit, "quantity_below_minimum"
    if component == "maxQty":
        return q > limit, "quantity_above_order_maximum"
    raise ValueError(component)


def notional_applies(fact: dict) -> bool | None:
    flags = fact.get("applicability", {}).get("flags", {})
    parameter = fact["parameter"]
    flag = ("applyMaxToMarket" if parameter == "NOTIONAL.maxNotional" else
            "applyMinToMarket" if parameter == "NOTIONAL.minNotional" else "applyToMarket")
    return flags.get(flag)


def derive_tiers(rows: list[dict]) -> list[dict]:
    tiers = []
    deduction, previous_rate, previous_cap = D(0), D(0), D(0)
    for row in rows:
        floor, cap, rate = (D(row[k]) for k in
                            ("floor_usdt", "cap_usdt", "maintenance_rate"))
        if floor != previous_cap or cap <= floor:
            raise ValueError("tier intervals must be contiguous from zero")
        if rate < previous_rate:
            raise ValueError("maintenance rates must not decrease")
        if tiers:
            deduction += floor * (rate - previous_rate)
        tiers.append({"floor": floor, "cap": cap, "rate": rate, "deduction": deduction,
                      "maximum_initial_leverage": row.get("maximum_initial_leverage")})
        previous_rate, previous_cap = rate, cap
    return tiers


def maintenance_candidate(notional: Decimal, tiers: list[dict]) -> tuple[Decimal, int | None]:
    if notional == 0:
        return D(0), None
    for index, tier in enumerate(tiers):
        if tier["floor"] < notional <= tier["cap"]:
            return notional * tier["rate"] - tier["deduction"], index
    raise ValueError(f"notional outside published brackets: {notional}")


def integration_row(fact: dict, sources: dict[str, dict]) -> dict:
    parameter, status = fact["parameter"], fact["status"]
    semantic = "Vigencia, captura, publicación y conocimiento son dimensiones separadas."
    compatibility = "No cargar: RuleBook exige snapshot completo y cobertura temporal acreditada."
    change = "Conservar evidencia; diagnóstico atemporal, sin interpolar ni forward-fill."
    assumption = "Cualquier persistencia fuera del punto/evento sería un supuesto nuevo no aprobado."
    if parameter.startswith(("LOT_SIZE.", "MARKET_LOT_SIZE.")):
        semantic = "LOT_SIZE y MARKET_LOT_SIZE son filtros distintos; maxQty limita cada orden."
        compatibility = "El motor usa un único step/min_qty/max_qty y exige valores positivos."
        if fact.get("value_normalized") == "0":
            semantic += " El cero está publicado; semántica histórica pendiente; nunca módulo por cero."
    elif "NOTIONAL" in parameter or parameter == "minimum_order_notional":
        semantic = "Banderas MARKET, promedio de precio y exenciones/reducciones requieren tratamiento propio."
        compatibility = "min_notional/max_notional únicos; sin banderas MARKET ni precio medio del filtro."
        assumption = "Usar quantity*primer reference_price del fill es proxy diagnóstico; no validación de la orden."
        if parameter == "NOTIONAL.maxNotional":
            semantic += " applyMaxToMarket=false impide imponer ese máximo a MARKET. No es límite de posición."
    elif parameter == "PRICE_FILTER.tickSize":
        semantic = "Órdenes anteriores pueden conservar condiciones; tick no define liquidez ni fills subminuto."
        compatibility = "Compatible con redondeo adverso por tick; evento no prueba continuidad."
    elif parameter in {"maintenance_tiers", "maintenance_deduction_derived"}:
        semantic = "Piso exclusivo/techo inclusivo; cohortes y aumentos; 2x no elige un tramo por sí solo."
        compatibility = "Tier conserva floor/cap/rate/deduction; no cohorte, despliegue ni límite inicial de apalancamiento."
        change = "Evaluar las 16 tablas por separado sobre nocionales diarios BASE_E3; no cronología."
        assumption = "D0=0 y continuidad para deducciones derivadas; no son cum publicados."
    elif parameter.startswith("taker_fee"):
        semantic = "Tarifa realizada separada del costo ex ante; VIP0, sin descuentos y mercado coincidente."
        compatibility = "Extensión opt-in de costos; no transformar este registro en RuleBook."
        change = "FUT4 constante sólo como supuesto experimental; no fechar el cambio 4 a 5 pb."
        assumption = "4 pb todo el período y 10 pb spot fuera de promoción son supuestos del experimento."
        if fact["id"] == "BTC_SPOT_ZERO":
            change = "BTC_PROMO_REALIZADA y BTC_PROMO_DECISION exclusivamente BTCUSDT spot en intervalo respaldado."
            assumption = "known_from histórico desconocido; conocer tarifa al entrar en vigencia es hipótesis experimental."
        elif status == "pendiente":
            change = "Mantener fecha efectiva desconocida. FAQ y pista de octubre de 2023 no la acreditan."
    elif parameter.startswith("liquidation"):
        semantic = "Tasa, base execution_notional y cobro regular simultáneo no comparten cobertura histórica completa."
        compatibility = "Motor admite tasa/base/cargo regular, pero cobertura y excepciones faltan."
        change = "Conservar costos de liquidación BASE_E3; no escalar con FUT4 ni margen."
    else:
        semantic += " El campo no tiene representación separada o no se usa en órdenes MARKET del motor."
    if status in {"fuera_de_alcance", "contradictorio"}:
        change = "Excluir de parámetros activos; conservar identidad y motivo documental."
    return {
        "parametro": parameter, "activo": fact["symbol"], "mercado": fact["market"],
        "hecho": json_text({"original": fact.get("value_original"),
                              "normalizado": fact.get("value_normalized"), "unidad": fact["unit"]}),
        "fuente_respaldo": " | ".join(sources[s]["original_url"] for s in fact["source_ids"]),
        "precision_temporal": json_text(fact["temporal"]), "estado_documental": status,
        "semantica_pendiente": semantic, "compatibilidad_motor": compatibility,
        "cambio_propuesto": change, "supuesto_adicional_necesario": assumption,
        "fact_id": fact["id"], "source_id": "|".join(fact["source_ids"]),
        "known_from_utc": fact.get("knowledge", {}).get("known_from_utc"),
        "conocimiento_documental": json_text(fact.get("knowledge", {})),
        "aplicabilidad_documental": json_text(fact.get("applicability", {})),
        "loadable_by_rulebook": False,
    }


def load_evidence(root: Path, evidence: Path) -> tuple[list[dict], dict, list]:
    manifest = read_json(evidence / "manifest.json", "manifiesto sellado")
    for member in manifest["files"]:
        raw = read_bytes(inside(evidence, member["path"]), "miembro sellado íntegro",
                         member["sha256"])
        if len(raw) != member["bytes"]:
            raise ValueError(f"Size mismatch: {member['path']}")
    registry = read_json(evidence / "reglas_historicas.json", "345 hechos y estados íntegros")
    if registry["loadable_by_rulebook"] is not False:
        raise ValueError("documentary registry unexpectedly loadable")
    sources = {s["id"]: s for s in read_json(evidence / "fuentes.json", "52 fuentes íntegras")["sources"]}
    for source in sources.values():
        base = root if source["local_base"] == "repository" else evidence
        raw = read_bytes(inside(base, source["local_file"]), f"fuente {source['id']}",
                         source["sha256"])
        if len(raw) != source["bytes"]:
            raise ValueError(f"Source size mismatch: {source['id']}")
    for name in ("README.md", "reporte_fuentes_historicas.md", "verificar_fuentes.py",
                 "estado_inicial.json", "verificacion_resultados.json", "revision_segunda.json"):
        raw = read_bytes(evidence / name, "lectura íntegra de antecedentes sellados")
        if name.endswith(".json"):
            json.loads(raw)
        else:
            raw.decode("utf-8-sig")
    coverage = list(csv.DictReader(read_bytes(evidence / "cobertura.csv", "479 filas cobertura")
                                  .decode("utf-8-sig").splitlines()))
    if len(coverage) != 479:
        raise ValueError("unexpected source coverage count")
    # Corroborate the exact interval against the preserved source texts, not a recollection.
    facts = registry["facts"]
    promo = next(f for f in facts if f["id"] == "BTC_SPOT_ZERO")
    assert promo["temporal"]["valid_from_utc"] == "2022-07-08T14:00:00Z"
    assert promo["temporal"]["valid_to_exclusive_utc"] == "2023-03-22T00:00:00Z"
    for source_id, token in (("PROMO_START", "2022-07-08 14:00 (UTC)"),
                             ("PROMO_END", "2023-03-22 00:00 (UTC)")):
        body = read_bytes(evidence / sources[source_id]["local_file"], "corroboración promoción")
        if token not in body.decode("utf-8") or b"BTC/USDT" not in body:
            raise ValueError(f"promotion source token missing: {source_id}")
    api_copies = {}
    for fact in facts:
        proof = fact.get("proof") or {}
        if proof.get("kind") != "json_path":
            continue
        source_id = fact["source_ids"][0]
        if source_id not in api_copies:
            api_copies[source_id] = json.loads(read_bytes(
                evidence / sources[source_id]["local_file"], "288 campos API contra copia original"))
        value = api_copies[source_id]
        for key in proof["path"]:
            value = value[key]
        if value != fact["value_original"]:
            raise ValueError(f"API original value mismatch: {fact['id']}")
    tables = read_json(evidence / "extraidos/tablas_margen.json", "16 tablas íntegras")
    for path in (root / "docs/research").glob("*"):
        if path.suffix in {".json", ".md"}:
            raw = read_bytes(path, "antecedente metodológico íntegro")
            if path.suffix == ".json":
                json.loads(raw)
    for rel in ("docs/methodology.md", "docs/progress.md", "src/crypto_carry/data/rules.py",
                "src/crypto_carry/data/prescribed.py", "src/crypto_carry/margin.py",
                "src/crypto_carry/allocation.py", "src/crypto_carry/execution.py",
                "src/crypto_carry/portfolio.py", "src/crypto_carry/reporting.py"):
        path = root / rel
        if path.exists():
            read_bytes(path, "interfaz y metodología; no importada por diagnóstico").decode("utf-8-sig")
    return facts, sources, tables


def load_run(path: Path) -> dict:
    manifest_raw = read_bytes(path / "run_manifest.json", "manifiesto corrida original")
    expected = read_bytes(path / "run_manifest.sha256", "sello corrida").decode().strip().split()[0]
    if hashlib.sha256(manifest_raw).hexdigest() != expected:
        raise ValueError(f"run manifest mismatch: {path}")
    manifest = json.loads(manifest_raw)
    if manifest["run_id"] != path.name or path.name not in RUN_IDS:
        raise ValueError(f"unexpected reference run: {path.name}")
    # Every original output is conserved; configuration and input identity come from the manifest.
    for relative, digest in manifest["output_hashes"].items():
        read_bytes(inside(path, relative), "salida original contrastada con manifiesto", digest)
    for relative in ("effective_config.toml", "research_assumptions.json"):
        read_bytes(path / relative, "configuración efectiva original")
    data = {"manifest": manifest, "run_id": path.name}
    for name in ("orders", "fills", "positions", "ledger"):
        frame = pd.read_parquet(path / f"{name}.parquet")
        if not frame.empty and set(frame.run_id) != {path.name}:
            raise ValueError(f"mixed run IDs in {path / name}")
        data[name] = frame.to_dict("records")
    data["daily"] = list(csv.DictReader((path / "equity_daily.csv").open(encoding="utf-8-sig", newline="")))
    data["assumptions"] = json.loads((path / "research_assumptions.json").read_text(encoding="utf-8-sig"))
    return data


def baseline_orders(run: dict) -> list[dict]:
    fills = {}
    for fill in run["fills"]:
        fills.setdefault(fill["order_id"], []).append(fill)
    final = {r["order_id"]: r for r in run["orders"] if r["record_type"] == "final"}
    submitted = [r for r in run["orders"] if r["action"] == "submitted"]
    if len(submitted) != len(final) or len({r["order_id"] for r in submitted}) != len(submitted):
        raise ValueError("order event/final population does not reconcile")
    result = []
    for row in submitted:
        fs = sorted(fills.get(row["order_id"], []), key=lambda f: f["time_ns"])
        reference = D(fs[0]["reference_price"]) if fs else None
        result.append({
            "run_id": run["run_id"], "strategy": row["strategy"], "order_id": row["order_id"],
            "symbol": row["symbol"], "market": row["market"], "side": row["side"],
            "purpose": row["purpose"], "submitted_at_ns": int(row["submitted_at"]),
            "submitted_at_utc": row["submitted_at_utc"], "quantity": D(row["quantity"]),
            "final_status": final[row["order_id"]]["status"], "fill_count": len(fs),
            "filled_quantity": sum((D(f["quantity"]) for f in fs), D(0)),
            "fill_notional_usdt": sum((D(f["quantity"]) * D(f["price"]) for f in fs), D(0)),
            "reference_price_first_fill": reference,
            "order_notional_proxy_usdt": D(row["quantity"]) * reference if reference else None,
            "notional_definition": "requested_quantity * first_fill.reference_price; unavailable if no fill",
            "first_fill_id": fs[0]["fill_id"] if fs else None,
        })
    return result


def baseline_daily(run: dict) -> list[dict]:
    baseline_rules = {r["symbol"]: r["values"]["tiers"] for r in run["assumptions"]["rules"]
                      if r["market"] == "futures"}
    result = []
    for row in run["daily"]:
        for symbol in SYMBOLS:
            q, mark, average, collateral = (D(row[f"{symbol}_{field}"])
                                            for field in ("short", "mark", "average", "collateral"))
            n = q * mark
            tiers = [{k: D(v) for k, v in t.items()} for t in baseline_rules[symbol]]
            maintenance, tier = maintenance_candidate(n, tiers)
            result.append({"run_id": run["run_id"], "strategy": row["strategy"],
                           "symbol": symbol, "time_ns": int(row["time_ns"]),
                           "timestamp_utc": row["timestamp_utc"], "short_quantity": q,
                           "mark_price": mark, "position_notional_usdt": n,
                           "average_entry": average, "collateral_usdt": collateral,
                           "margin_balance_usdt": collateral + q * (average - mark),
                           "base_maintenance_usdt": maintenance, "base_tier_index": tier})
    return result


def filter_diagnostics(facts: list[dict], orders: list[dict]) -> tuple[list, list]:
    summaries, affected = [], []
    for fact in facts:
        parameter = fact["parameter"]
        is_quantity = parameter.startswith(("LOT_SIZE.", "MARKET_LOT_SIZE."))
        is_notional = parameter in {"MIN_NOTIONAL.minNotional", "MIN_NOTIONAL.notional",
                                    "NOTIONAL.minNotional", "NOTIONAL.maxNotional"}
        if fact["status"] != "observacion_puntual" or not (is_quantity or is_notional):
            continue
        market = "spot" if fact["market"] == "spot" else "futures"
        limit = D(fact["value_normalized"])
        for run_id in RUN_IDS:
            candidates = [o for o in orders if o["run_id"] == run_id and
                          o["symbol"] == fact["symbol"] and o["market"] == market]
            tested = unknown = failed = 0
            applicability = notional_applies(fact) if is_notional else None
            reason = "not_applied_market_flag_false" if applicability is False else ""
            for order in candidates:
                if applicability is False:
                    continue
                if is_quantity:
                    violation, reason = quantity_candidate(order["quantity"], parameter.split(".")[1], limit)
                elif order["order_notional_proxy_usdt"] is None:
                    violation, reason = None, "no_fill_price_notional_unavailable"
                else:
                    value = order["order_notional_proxy_usdt"]
                    violation = value > limit if parameter == "NOTIONAL.maxNotional" else value < limit
                    reason = "requested_quantity_times_first_fill_reference_proxy"
                if violation is None:
                    unknown += 1
                else:
                    tested += 1
                    if violation:
                        failed += 1
                        affected.append({**order, "fact_id": fact["id"],
                                         "source_id": "|".join(fact["source_ids"]),
                                         "parameter": parameter, "observed_value": limit,
                                         "observed_at_utc": fact["temporal"].get("observed_at_utc"),
                                         "candidate_reason": reason,
                                         "market_applicability": applicability,
                                         "scope": "atemporal_candidate_not_historical_rejection"})
            summaries.append({"run_id": run_id, "fact_id": fact["id"],
                              "source_id": "|".join(fact["source_ids"]), "symbol": fact["symbol"],
                              "market": market, "parameter": parameter, "observed_value": limit,
                              "observed_at_utc": fact["temporal"].get("observed_at_utc"),
                              "orders_population": len(candidates), "orders_tested": tested,
                              "candidate_orders": failed, "orders_unknown": unknown,
                              "market_applicability": applicability, "note": reason,
                              "scope": "atemporal_candidate_no_interpolation"})
    return summaries, affected


def margin_diagnostics(tables: list[dict], facts: dict, daily: list[dict]) -> tuple[list, list, list]:
    summaries, details, boundaries = [], [], []
    for table in tables:
        fact_id, symbol = table["fact_id"], table["symbol"]
        tiers = derive_tiers(table["rows"])
        documented = facts[fact_id + "_DERIVED"]["value_normalized"]
        if [str(t["deduction"].normalize()) for t in tiers] != [str(D(v).normalize()) for v in documented]:
            raise ValueError(f"deduction mismatch: {fact_id}")
        for index, tier in enumerate(tiers):
            cap_value, selected = maintenance_candidate(tier["cap"], tiers)
            right = (tier["cap"] * tiers[index + 1]["rate"] - tiers[index + 1]["deduction"]
                     if index + 1 < len(tiers) else None)
            if selected != index or (right is not None and cap_value != right):
                raise ValueError(f"boundary/continuity mismatch: {fact_id}")
            boundaries.append({"fact_id": fact_id, "source_id": table["source_id"],
                               "derived_fact_id": fact_id + "_DERIVED", "tier_index": index,
                               "floor_exclusive_usdt": tier["floor"], "cap_inclusive_usdt": tier["cap"],
                               "published_rate": tier["rate"], "derived_deduction_usdt": tier["deduction"],
                               "maintenance_at_cap": cap_value, "next_formula_at_cap": right,
                               "continuity_checked": right is not None, "boundary_selection_passed": True})
        for run_id in RUN_IDS:
            sample = [r for r in daily if r["run_id"] == run_id and r["symbol"] == symbol and r["short_quantity"] > 0]
            rows = []
            for row in sample:
                value, index = maintenance_candidate(row["position_notional_usdt"], tiers)
                delta = value - row["base_maintenance_usdt"]
                detail = {**row, "fact_id": fact_id, "derived_fact_id": fact_id + "_DERIVED",
                          "source_id": table["source_id"], "relative_table": table["side"],
                          "candidate_tier_index": index, "candidate_maintenance_usdt": value,
                          "delta_maintenance_usdt": delta,
                          "candidate_margin_ratio": value / row["margin_balance_usdt"]
                          if row["margin_balance_usdt"] > 0 else None,
                          "candidate_balance_below_maintenance": row["margin_balance_usdt"] <= value,
                          "scope": "atemporal_daily_candidate_not_a_simulation"}
                rows.append(detail)
            details.extend(rows)
            summaries.append({"run_id": run_id, "symbol": symbol, "fact_id": fact_id,
                              "derived_fact_id": fact_id + "_DERIVED", "source_id": table["source_id"],
                              "relative_table": table["side"], "positive_position_days": len(rows),
                              "max_daily_notional_usdt": max((r["position_notional_usdt"] for r in rows), default=D(0)),
                              "first_tier_cap_usdt": tiers[0]["cap"],
                              "days_above_first_tier": sum(r["candidate_tier_index"] > 0 for r in rows),
                              "days_higher_maintenance": sum(r["delta_maintenance_usdt"] > 0 for r in rows),
                              "days_lower_maintenance": sum(r["delta_maintenance_usdt"] < 0 for r in rows),
                              "min_delta_maintenance_usdt": min((r["delta_maintenance_usdt"] for r in rows), default=None),
                              "max_delta_maintenance_usdt": max((r["delta_maintenance_usdt"] for r in rows), default=None),
                              "days_balance_below_candidate": sum(r["candidate_balance_below_maintenance"] for r in rows),
                              "scope": "atemporal_daily_candidate_not_historical_applicability"})
    return summaries, details, boundaries


def event_diagnostics(facts: list[dict], orders: list[dict], runs: list[dict]) -> tuple[list, list]:
    order_rows, cohort_rows = [], []
    for fact in facts:
        if fact["status"] != "evento_respaldado" or fact.get("preperiod"):
            continue
        t = fact["temporal"]
        anchor = t.get("effective_at_utc") or t.get("earliest_utc") or t.get("latest_utc")
        if not anchor:
            continue
        ns = pd.Timestamp(anchor).value
        if fact["parameter"] in {"minimum_order_notional", "PRICE_FILTER.tickSize"}:
            market = "spot" if fact["market"] == "spot" else "futures"
            for order in orders:
                if order["symbol"] != fact["symbol"] or order["market"] != market:
                    continue
                values = fact["value_normalized"]
                proxy = order["order_notional_proxy_usdt"]
                changed = (proxy is not None and (proxy >= D(values["before"])) !=
                           (proxy >= D(values["after"]))) if fact["parameter"] == "minimum_order_notional" else None
                near = abs(order["submitted_at_ns"] - ns) <= 86400 * 10**9
                if near or changed:
                    order_rows.append({**order, "fact_id": fact["id"],
                                       "source_id": "|".join(fact["source_ids"]),
                                       "temporal_kind": t["kind"], "diagnostic_anchor_utc": anchor,
                                       "within_24h_anchor": near, "threshold_result_differs": changed,
                                       "submitted_before_anchor": order["submitted_at_ns"] < ns,
                                       "scope": "candidate_only_anchor_is_not_assumed_effective_time"})
        if fact["parameter"] != "maintenance_tiers":
            continue
        for run in runs:
            symbol = fact["symbol"]
            ledger = [r for r in run["ledger"] if r["symbol"] == symbol]
            prior = [r for r in ledger if int(r["time_ns"]) <= ns]
            last = max(enumerate(prior), key=lambda pair: (int(pair[1]["time_ns"]), pair[0]),
                       default=(None, None))[1]
            q = D(last["short"]) if last else D(0)
            later = sorted([r for r in ledger if int(r["time_ns"]) > ns], key=lambda r: int(r["time_ns"]))
            cohort_end = next((int(r["time_ns"]) for r in later if D(r["short"]) == 0), None) if q else None
            increases = [f for f in run["fills"] if q and f["symbol"] == symbol and
                         f["market"] == "futures" and f["side"] == "SELL" and
                         int(f["time_ns"]) > ns and (cohort_end is None or int(f["time_ns"]) < cohort_end)]
            cohort_rows.append({"run_id": run["run_id"], "symbol": symbol, "fact_id": fact["id"],
                                "source_id": "|".join(fact["source_ids"]), "temporal_kind": t["kind"],
                                "diagnostic_anchor_utc": anchor, "existing_short_quantity": q,
                                "last_ledger_event_id": last["event_id"] if last else None,
                                "last_ledger_timestamp_utc": last["timestamp_utc"] if last else None,
                                "existing_positions_affected": fact["applicability"].get("existing_positions_affected"),
                                "known_from_utc": fact["knowledge"]["known_from_utc"],
                                "subsequent_increase_fills_before_flat": len(increases),
                                "increase_fill_ids": "|".join(f["fill_id"] for f in increases),
                                "cohort_closed_at_ns": cohort_end,
                                "scope": "quantity_reconstructed_from_recorded_ledger_no_policy_applied"})
    return order_rows, cohort_rows


def promo_boundaries(runs: list[dict]) -> list[dict]:
    rows = []
    start = pd.Timestamp("2022-07-08T14:00:00Z").value
    end = pd.Timestamp("2023-03-22T00:00:00Z").value
    for run in runs:
        fills = [f for f in run["fills"] if f["market"] == "spot" and f["symbol"] == "BTCUSDT"]
        for label, boundary in (("start_inclusive", start), ("end_exclusive", end)):
            crossing = [f for f in fills if int(f["window_start"]) < boundary < int(f["window_end"])]
            at_fill = [f for f in fills if int(f["time_ns"]) == boundary]
            rows.append({"run_id": run["run_id"], "fact_id": "BTC_SPOT_ZERO",
                         "source_id": "PROMO_START|PROMO_END", "boundary": label,
                         "boundary_ns": boundary, "btc_spot_fills_all": len(fills),
                         "fills_inside_interval_by_recorded_timestamp": sum(start <= int(f["time_ns"]) < end for f in fills),
                         "fills_at_boundary": len(at_fill), "windows_straddling_boundary": len(crossing),
                         "boundary_fill_ids": "|".join(f["fill_id"] for f in at_fill),
                         "straddling_fill_ids": "|".join(f["fill_id"] for f in crossing)})
    return rows


def documentation(output: Path, result: dict, products: dict[str, list[dict]]) -> None:
    definitions = {
        "run_id": "Identificador de la corrida original BASE_E3; no identifica una simulación nueva.",
        "strategy": "conditional o permanent, según la corrida original.",
        "symbol": "BTCUSDT o ETHUSDT.", "market": "spot o futures (USDT-M perpetuo).",
        "fact_id": "Clave exacta del hecho en reglas_historicas.json sellado.",
        "derived_fact_id": "Clave del cálculo separado de deducciones derivadas.",
        "source_id": "Clave del catálogo fuentes.json; | separa varias fuentes.",
        "order_id": "ID original único de orden submitted; eventos y finales no se duplican.",
        "side": "BUY o SELL de la orden original.", "purpose": "Propósito original de la orden.",
        "submitted_at_ns": "Timestamp de envío UTC, nanosegundos enteros.",
        "submitted_at_utc": "Timestamp original de envío en ISO 8601 UTC.",
        "quantity": "Cantidad bruta solicitada por orden, en unidades del activo base.",
        "final_status": "Estado final de la orden original.", "fill_count": "Número de fills de la orden.",
        "filled_quantity": "Suma de cantidades ejecutadas, en unidades base.",
        "fill_notional_usdt": "Suma Decimal de cantidad*precio efectivo de cada fill; USDT.",
        "reference_price_first_fill": "reference_price del primer fill (USDT/unidad), vacío si no hay fill.",
        "order_notional_proxy_usdt": "Cantidad solicitada*reference_price del primer fill; no precio de aceptación.",
        "notional_definition": "Definición explícita del proxy; no una observación adicional.",
        "first_fill_id": "ID que traza el precio usado por el proxy; vacío sin fill.",
        "time_ns": "Cierre diario UTC, nanosegundos enteros.",
        "timestamp_utc": "Cierre diario en ISO 8601 UTC.",
        "short_quantity": "Cantidad corta al cierre, en unidades base positivas.",
        "mark_price": "Mark observado/conservado por BASE_E3 al cierre, USDT/unidad.",
        "position_notional_usdt": "short_quantity*mark_price; saldo de posición diario, no por orden.",
        "average_entry": "Precio promedio original del short, USDT/unidad.",
        "collateral_usdt": "Garantía aislada original al cierre; USDT.",
        "margin_balance_usdt": "collateral+short*(average_entry-mark_price); USDT.",
        "base_maintenance_usdt": "MM de reglas prescritas guardadas con la corrida, al nocional diario.",
        "base_tier_index": "Índice de tramo BASE_E3, desde cero; vacío si no hay short.",
        "parameter": "Nombre exacto del componente de filtro en el registro documental.",
        "observed_value": "Valor puntual normalizado del hecho, sin intervalo imputado.",
        "observed_at_utc": "Captura documental, no fecha de vigencia.",
        "orders_population": "Órdenes únicas del símbolo/mercado/cartera durante toda la muestra.",
        "orders_tested": "Órdenes evaluables con la comparación aritmética de ese componente.",
        "candidate_orders": "Comparaciones fuera del límite puntual; no rechazos históricos.",
        "orders_unknown": "No evaluables por cero sin semántica o por ausencia de precio de fill.",
        "market_applicability": "Bandera explícita: True/False; vacío cuando no consta. False no se impone a MARKET.",
        "note": "Convención/limitación de la comparación, no decisión del motor.",
        "scope": "Etiqueta que impide interpretar el candidato como historia continua o simulación.",
        "candidate_reason": "Motivo aritmético de la diferencia potencial.",
        "relative_table": "before o after del aviso; no fecha de inicio/duración.",
        "positive_position_days": "Cierres diarios con short>0, por símbolo y cartera.",
        "max_daily_notional_usdt": "Máximo de short*mark entre cierres observados; no máximo intradiario.",
        "first_tier_cap_usdt": "Techo inclusivo del primer tramo publicado; USDT de posición.",
        "days_above_first_tier": "Cierres cuyo nocional seleccionaría un tramo superior.",
        "days_higher_maintenance": "Cierres con MM candidato mayor que MM base; no días históricamente afectados.",
        "days_lower_maintenance": "Cierres con MM candidato menor que MM base; no días históricamente afectados.",
        "min_delta_maintenance_usdt": "Mínima diferencia MM candidato-MM base en USDT; stock, no P&L.",
        "max_delta_maintenance_usdt": "Máxima diferencia MM candidato-MM base en USDT; stock, no P&L.",
        "days_balance_below_candidate": "Cierres con margin_balance<=MM candidato; no liquidaciones simuladas.",
        "candidate_tier_index": "Tramo seleccionado con floor<N<=cap, índice desde cero.",
        "candidate_maintenance_usdt": "N*tasa-deducción derivada de la tabla; USDT, sólo candidato atemporal.",
        "delta_maintenance_usdt": "MM candidato-MM base; stock de garantía requerida, nunca flujo de costo.",
        "candidate_margin_ratio": "MM candidato/margin_balance original positivo; vacío si denominador<=0.",
        "candidate_balance_below_maintenance": "True si saldo original no cubre MM candidato al cierre.",
        "tier_index": "Índice del tramo publicado, desde cero.",
        "floor_exclusive_usdt": "Piso exclusivo del tramo, USDT de posición.",
        "cap_inclusive_usdt": "Techo inclusivo del tramo, USDT de posición.",
        "published_rate": "Tasa de mantenimiento publicada en fracción decimal.",
        "derived_deduction_usdt": "Deducción analítica D0=0 y continuidad; no cum publicado.",
        "maintenance_at_cap": "MM en el techo, calculado por el tramo inferior; USDT.",
        "next_formula_at_cap": "Límite de fórmula del tramo siguiente en la frontera; vacío en último tramo.",
        "continuity_checked": "True cuando existe siguiente tramo y se comprobó continuidad exacta Decimal.",
        "boundary_selection_passed": "True si el techo selecciona el tramo inferior publicado.",
        "temporal_kind": "exact_event/deadline/approximate_rollout original; nunca homogeneizado.",
        "diagnostic_anchor_utc": "Instante exacto o inicio/deadline usado para localizar exposición, no vigencia supuesta.",
        "within_24h_anchor": "Orden dentro de +/-24 horas del ancla para inspección local, ventana arbitraria explícita.",
        "threshold_result_differs": "El proxy cumple uno y no otro mínimo before/after, sin aplicar cronología.",
        "submitted_before_anchor": "Relación cronológica de envío con el ancla de inspección, no con vigencia certificada.",
        "existing_short_quantity": "Short del último ledger a/o antes del ancla; cero inicial si no hubo evento.",
        "last_ledger_event_id": "Evento original que respalda cantidad existente.",
        "last_ledger_timestamp_utc": "Timestamp del evento original usado; no mark interpolado.",
        "existing_positions_affected": "Política publicada sobre existentes, separada de aumentos.",
        "known_from_utc": "Conocimiento históricamente acreditado; vacío conserva null, no lo imputa.",
        "subsequent_increase_fills_before_flat": "Fills futures SELL posteriores al ancla y previos al primer short=0.",
        "increase_fill_ids": "IDs de aumentos que requieren resolver política de cohortes; | separa IDs.",
        "cohort_closed_at_ns": "Primer evento posterior con short=0; vacío si no cerró o no había posición.",
        "boundary": "start_inclusive o end_exclusive de BTC_SPOT_ZERO.",
        "boundary_ns": "Frontera exacta UTC en nanosegundos.",
        "btc_spot_fills_all": "Fills BTC spot originales de toda la muestra.",
        "fills_inside_interval_by_recorded_timestamp": "Fills cuyo timestamp cumple inicio<=t<fin; diagnóstico BASE_E3.",
        "fills_at_boundary": "Fills cuyo timestamp coincide exactamente con la frontera.",
        "windows_straddling_boundary": "Ventanas con window_start<frontera<window_end; no se inventan subfills.",
        "boundary_fill_ids": "IDs de fills en la frontera.", "straddling_fill_ids": "IDs de ventanas que cruzan la frontera.",
    }
    schemas = {}
    for name in products:
        with (output / name).open(encoding="utf-8", newline="") as handle:
            fields = next(csv.reader(handle))
        missing = set(fields) - definitions.keys()
        if missing:
            raise ValueError(f"missing column definitions: {missing}")
        schemas[name] = {column: definitions[column] for column in fields}
    schemas["input_inventory.csv"] = {
        "path": "Ruta local leída (el inventario cambiará al reproducir en otra raíz).",
        "bytes": "Tamaño exacto de bytes leídos.", "sha256": "SHA-256 de esos bytes.",
        "read_purpose": "Tipo de lectura; un escaneo de bytes no certifica interpretación de todo el documento."}
    write_json(output / "esquema_columnas.json", schemas)
    daily = products["daily_positions_baseline.csv"]
    order_rows = products["orders_baseline.csv"]
    table_rows = []
    for population in result["populations"]:
        run_id = population["run_id"]
        unknown = sum(o["order_notional_proxy_usdt"] is None for o in order_rows if o["run_id"] == run_id)
        table_rows.append(f"| `{run_id}` | {population['submitted_orders']} | {population['fills']} | {unknown} | {population['daily_observations']} |")
    max_rows = []
    for run_id in RUN_IDS:
        for symbol in SYMBOLS:
            rows = [r for r in daily if r["run_id"] == run_id and r["symbol"] == symbol]
            max_rows.append(f"| `{run_id}` | {symbol} | {max(r['position_notional_usdt'] for r in rows)} | {sum(r['short_quantity'] > 0 for r in rows)} |")
    readme = """# Diagnóstico histórico de exposición — versión técnica preliminar

Resultado ejecutado sobre registros originales BASE_E3; no es un backtest nuevo
ni una decisión de cargar tablas históricas. [Resultados](diagnostico_resultados.json),
[definición de cada columna](esquema_columnas.json) e [inventario leído](input_inventory.csv).

| run_id | Órdenes únicas | Fills | Órdenes sin proxy nocional | Cierres diarios |
|---|---:|---:|---:|---:|
""" + "\n".join(table_rows) + """

`orders_baseline.csv` deduplica eventos submitted por order_id y concilia con
filas finales. Las cantidades conservan Decimal. El proxy nocional usa cantidad
solicitada por reference_price del primer fill; sin fill no se inventa precio.
No es una comprobación del precio medio que Binance usaba al aceptar la orden.

En `filter_candidates_summary.csv` hay 204 comparaciones (102 hechos por cartera).
No se detectan órdenes registradas fuera de los límites puntuales comparables.
`candidate_orders.csv` y `event_order_candidates.csv` conservan encabezados aunque
tengan cero filas. No se deduce ausencia de entradas que podrían aparecer con
filtros más permisivos. 24 comparaciones de componentes cero MARKET spot quedan
sin semántica de evaluación; no se ejecuta módulo por cero. Las banderas máximas
MARKET falsas se respetan; banderas desconocidas siguen desconocidas. No se
interpolan las capturas ni se les atribuye duración.

Los fact_id/source_id exactos de cada prueba están en las tablas; siguen las
observaciones SPOTI22/SPOTI23/SPOTI25 y FUTI22/FUTI22B/FUTI26/FUTI26B.

| run_id | Activo | Máximo nocional diario USDT | Cierres con short positivo |
|---|---|---:|---:|
""" + "\n".join(max_rows) + """

`daily_positions_baseline.csv` deriva short*mark de los 1.704 cierres de cada
cartera y ambos activos (6.816 filas). No observa máximos de posición intradiarios.
`margin_candidates_daily.csv` tiene 32.160 comparaciones sobre cierres con short;
`margin_candidates_summary.csv` resume las 16 tablas relativas por cartera.
Todos esos nocionales seleccionan el primer tramo de cada tabla. Las tablas
BTC coinciden con el mantenimiento base en estas observaciones. Las tasas ETH
de 0,004 o 0,005 reducen mantenimiento frente al 0,0065 base; no producen P&L.
La reducción máxima candidata con 0,004 es 9,76380775 USDT (condicional) y
10,1998613 (permanente), fila `TIERS_MARG23_ETHUSDT_after` / fuente `MARG23`,
con deducción `TIERS_MARG23_ETHUSDT_after_DERIVED`. Ningún cierre observado tiene
saldo de margen menor o igual al candidato. No se infieren liquidaciones,
trayectorias nuevas ni ausencia de riesgo intradiario.

`tier_boundary_checks.csv` comprueba 177 techos de las 16 tablas: piso exclusivo,
techo inclusivo y continuidad analítica de la deducción. La deducción es derivada,
no publicada. No se suman stocks de mantenimiento a los costos ni al P&L.

`event_position_cohorts.csv` identifica 16 exposiciones de cartera/símbolo/evento
desde el ledger. Por ejemplo, en diciembre de 2023 hay short ETH de 1,306 en
condicional y 1,342 en permanente; después hay un fill de aumento en permanente
antes del cierre. Son filas `TIERS_MARG23_ETHUSDT_after` / `MARG23`, con los
run_id anteriores. El aviso preserva posiciones existentes, pero no resuelve
la política de ese aumento. Mayo de 2024 también tiene aumentos posteriores
en ambas carteras (`TIERS_MARG24_*_after` / `MARG24`). Las anclas de despliegues
aproximados sólo localizan exposición y no se transforman en vigencias exactas.

`promo_fill_boundaries.csv`, hecho `BTC_SPOT_ZERO`, fuentes `PROMO_START/PROMO_END`,
encuentra cero fills BTC spot condicionales y diez permanentes dentro del intervalo
según su timestamp registrado. Ningún fill BASE_E3 coincide con los extremos ni
ninguna ventana los cruza. Esto no comprueba las ventanas de las variantes nuevas.

Se contrastaron los miembros y fuentes del manifiesto sellado (incluidas A1–A3),
los 288 valores API contra sus rutas JSON originales y las deducciones contra
el registro. Se verificaron todos los output_hashes de cada corrida y su sello
de manifiesto. `input_inventory.csv` registra los bytes leídos y el chequeo de
conservación al finalizar. Este inventario no sustituye al verificador de publicación
ni certifica el motor o la continuidad de fuentes. No hubo cambios de índice,
commit, publicación externa ni modificación de evidencia original por este comando.

La segunda tanda sólo está propuesta en `docs/entrega_4/reglas_historicas/decisiones_integracion.md`.
No se ejecutó ninguna de sus políticas ni interpolaciones.

Reproducir requiere el paquete sellado, sus dependencias A1–A3, docs/research y
las dos carpetas de corridas originales bajo --runs-root. Usar una salida nueva:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/diagnose_historical_rules_exposure.py --root . --runs-root D:/Backtesting/outputs --output entregas/entrega_4/reglas_historicas/diagnostico_reproducido_nuevo
```

`--root`, `--evidence` y `--runs-root` permiten otra ubicación sin depender de HEAD.
El manifiesto local `manifest.json` protege los productos relativos a esta carpeta;
su hash esperado debe conservarse fuera del paquete al publicarlo. Verificación
de productos, offline y de sólo lectura:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/diagnose_historical_rules_exposure.py --verify-output RUTA_DIAGNOSTICO
```
"""
    (output / "README.md").write_text(readme, encoding="utf-8", newline="\n")


def verify_output(path: Path) -> dict:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    names = [row["path"] for row in manifest["files"]]
    if len(names) != len(set(names)):
        raise ValueError("duplicate output manifest path")
    for member in manifest["files"]:
        raw = inside(path, member["path"]).read_bytes()
        if len(raw) != member["bytes"] or hashlib.sha256(raw).hexdigest() != member["sha256"]:
            raise ValueError(f"output differs from manifest: {member['path']}")
    return {"passed": True, "files_checked": len(names),
            "scope": "diagnostic_output_integrity_only_no_historical_continuity_claim"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--runs-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--matrix", type=Path)
    parser.add_argument("--verify-output", type=Path)
    args = parser.parse_args(argv)
    if args.verify_output:
        print(json_text(verify_output(args.verify_output.resolve())))
        return 0
    root = args.root.resolve()
    evidence = (args.evidence or root / PACKAGE).resolve()
    facts, sources, tables = load_evidence(root, evidence)
    if args.matrix:
        if args.matrix.exists():
            raise FileExistsError(f"matrix already exists: {args.matrix}")
        args.matrix.parent.mkdir(parents=True, exist_ok=True)
        write_csv(args.matrix, [integration_row(f, sources) for f in facts])
    if args.output is None:
        if not args.matrix:
            parser.error("--matrix or --output required")
        print(json_text({"matrix_rows": len(facts), "loadable_by_rulebook": False}))
        return 0
    if args.runs_root is None:
        parser.error("--runs-root required with --output")
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"diagnostic output must be new: {output}")
    if output.is_relative_to(evidence) or evidence.is_relative_to(output):
        raise ValueError("output must be separate from sealed evidence")
    runs = [load_run(args.runs_root / run_id) for run_id in RUN_IDS]
    read_bytes(Path(__file__), "código del diagnóstico ejecutado")
    orders = [row for run in runs for row in baseline_orders(run)]
    daily = [row for run in runs for row in baseline_daily(run)]
    filter_summary, affected = filter_diagnostics(facts, orders)
    margin_summary, margin_details, boundaries = margin_diagnostics(
        tables, {f["id"]: f for f in facts}, daily)
    events, cohorts = event_diagnostics(facts, orders, runs)
    output.mkdir(parents=True)
    products = {"orders_baseline.csv": orders, "daily_positions_baseline.csv": daily,
                "filter_candidates_summary.csv": filter_summary, "candidate_orders.csv": affected,
                "margin_candidates_summary.csv": margin_summary, "margin_candidates_daily.csv": margin_details,
                "tier_boundary_checks.csv": boundaries, "event_order_candidates.csv": events,
                "event_position_cohorts.csv": cohorts, "promo_fill_boundaries.csv": promo_boundaries(runs)}
    empty_schemas = {
        "candidate_orders.csv": list(orders[0]) + ["fact_id", "source_id", "parameter",
            "observed_value", "observed_at_utc", "candidate_reason", "market_applicability", "scope"],
        "event_order_candidates.csv": list(orders[0]) + ["fact_id", "source_id", "temporal_kind",
            "diagnostic_anchor_utc", "within_24h_anchor", "threshold_result_differs",
            "submitted_before_anchor", "scope"],
    }
    for name, rows in products.items():
        write_csv(output / name, rows, empty_schemas.get(name) if not rows else None)
    source_inventory = list(INVENTORY.values())
    # Final content check: fail if any input changed during the diagnostic.
    changed = [r["path"] for r in source_inventory if hashlib.sha256(Path(r["path"]).read_bytes()).hexdigest() != r["sha256"]]
    if changed:
        raise ValueError(f"inputs changed during diagnostic: {changed}")
    write_csv(output / "input_inventory.csv", source_inventory)
    result = {
        "status": "ejecutado_diagnostico_no_simulacion", "technical_preliminary": True,
        "scenario": "BASE_E3", "run_ids": list(RUN_IDS), "documentary_facts": len(facts),
        "documentary_states": dict(Counter(f["status"] for f in facts)),
        "input_files_read_and_hash_checked": len(source_inventory), "input_bytes_unchanged": True,
        "matrix_loadable_by_rulebook": False,
        "output_rows": {name: len(rows) for name, rows in products.items()},
        "populations": [{"run_id": run["run_id"], "submitted_orders": sum(o["run_id"] == run["run_id"] for o in orders),
                         "fills": len(run["fills"]), "daily_observations": len(run["daily"])} for run in runs],
        "limitations": ["Candidate screens are atemporal; observations are not made continuous.",
                        "Order notional is a first-fill reference-price proxy; unfilled orders have no estimated notional.",
                        "MARKET applicability without a documented flag remains unknown; published zero semantics unresolved.",
                        "Daily marks do not observe intraday maximum notionals or intraday margin risk.",
                        "Cohort quantities use the ledger; no grandfathering or increase policy is simulated.",
                        "No historical transition date, interpolation, backtest, or second scenario batch is executed."]}
    write_json(output / "diagnostico_resultados.json", result)
    documentation(output, result, products)
    write_json(output / "manifest.json", {"schema": "diagnostic_output_manifest_v1",
        "files": [{"path": p.name, "bytes": p.stat().st_size,
                   "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                  for p in sorted(output.iterdir()) if p.is_file()]})
    print(json_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

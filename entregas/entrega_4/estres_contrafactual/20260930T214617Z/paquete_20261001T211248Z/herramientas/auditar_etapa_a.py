"""Auditoría descriptiva de etapa A. No importa ni ejecuta un backtest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.dont_write_bytecode = True


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
                    encoding="utf-8")


def table(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def git(root, *args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    return subprocess.check_output(["git", "-C", str(root), *args], env=env).decode("utf-8")


def regular_files(folder):
    """No atravesar reparse points, symlinks o junctions, ni siquiera al medir."""
    folder_stat = Path(folder).lstat()
    if getattr(folder_stat, "st_file_attributes", 0) & 0x400:
        raise ValueError("La raíz solicitada es un reparse point")
    with os.scandir(folder) as entries:
        for entry in sorted(entries, key=lambda e: e.name):
            stat = entry.stat(follow_symlinks=False)
            if entry.is_symlink() or getattr(stat, "st_file_attributes", 0) & 0x400:
                continue
            if entry.is_dir(follow_symlinks=False):
                yield from regular_files(Path(entry.path))
            elif entry.is_file(follow_symlinks=False):
                yield Path(entry.path)


def inputs(root, data, out):
    b4 = root / "entregas/entrega_4/ejecucion_demoras/20260929T221620Z"
    matrix = rows(root / "docs/entrega_4/matriz_avance.csv")
    folders = {r["paquete_vigente"] for r in matrix
               if r["paquete_vigente"] and r["estado"] == "ejecutado"}
    folders.add("entregas/entrega_4/reglas_historicas/20260925T005436Z")
    folders.add(str((b4 / "paquete_20260930T012056Z").relative_to(root)).replace("\\", "/"))
    sealed = []
    for name in sorted(folders):
        path = root / name / "manifiesto_paquete.json"
        manifest = read(path)
        members = manifest.get("members", manifest.get("files"))
        bad = []
        for member in members:
            target = path.parent / member["path"]
            if not target.is_file() or sha(target) != member["sha256"]:
                bad.append(member["path"])
        sealed.append(dict(path=name, manifest_sha256=sha(path), members=len(members),
                           mismatches=bad, passed=not bad))
        print("sello", name, len(members), "diferencias", len(bad), flush=True)
    assert all(r["passed"] for r in sealed), "Fuente sellada alterada"
    save(out / "controles/sellos_entrada.json", sealed)
    sys.path[:0] = [str(root), str(root / "src")]
    from crypto_carry.config import Config
    from scripts.check_execution_delays_base import compare
    from scripts.cost_capacity_ledger import audit_ledger
    from scripts.return_capital.common import parquet

    comparisons, ledger, identities = [], [], []
    original_ids = {"conditional": "run_ad71d751b20623006c195ff3",
                    "permanent": "run_dfea4b7ac1475668d5968c97"}
    for strategy, rid in original_ids.items():
        state = read(b4 / f"controles_base/CONTROL_BASE__{strategy}.json")
        old, new = data / "outputs" / rid, Path(state["path"])
        result = compare(old, new)
        result["strategy"] = strategy
        comparisons.append(result)
        assert result["passed"]
        for folder in (old, new):
            manifest = read(folder / "run_manifest.json")
            current = {}
            for name, digest in manifest["code_files"].items():
                current[name] = sha(root / name) == digest
            identity = dict(path=str(folder), run_id=folder.name,
                            manifest_sha256=sha(folder / "run_manifest.json"),
                            code_hash=manifest["code_hash"], code_current_equal=current,
                            bytes=sum(p.stat().st_size for p in regular_files(folder)))
            identities.append(identity)
            config = Config.load(folder / "effective_config.toml")
            audit = audit_ledger(config, parquet(folder / "ledger.parquet"),
                                 rows(folder / "equity_daily.csv"),
                                 parquet(folder / "positions.parquet"))
            ledger.append(dict(run_id=folder.name, **audit))
        print("BASE", strategy, "11 artefactos iguales y ledger conciliado", flush=True)
    published = read(b4 / "control_compatibilidad_base_completa.json")
    assert json.loads(json.dumps(comparisons)) == published["comparisons"]
    assert all(all(i["code_current_equal"].values()) for i in identities if i["run_id"]
               not in original_ids.values())
    save(out / "controles/compatibilidad_recalculada.json", dict(passed=True, comparisons=comparisons))
    save(out / "controles/conciliacion_referencias.json", ledger)
    save(out / "controles/identidades_corridas.json", identities)
    massive_inputs(root, data, out)


def massive_inputs(root, data, out):
    manifest = read(data / "outputs/run_ad71d751b20623006c195ff3/run_manifest.json")
    source_checks = []
    for name, expected in manifest["input_hashes"].items():
        if name == "processed_manifest_semantics":
            path = data / manifest["config"]["data_dir"] / "manifests/processed.json"
            semantic = {k: v for k, v in read(path).items() if k != "source_manifest_sha256"}
            actual = hashlib.sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest()
            source_checks.append(dict(path=str(path), key=name, bytes=path.stat().st_size,
                                      sha256=actual, expected=expected, passed=actual == expected,
                                      kind="semantic projection, not file byte hash",
                                      file_sha256=sha(path)))
            continue
        choices = [data / name, root / name]
        path = next((p for p in choices if p.is_file()), None)
        assert path is not None, name
        actual = sha(path)
        source_checks.append(dict(path=str(path), key=name, bytes=path.stat().st_size,
                                  sha256=actual, expected=expected, passed=actual == expected))
    assert all(s["passed"] for s in source_checks), "Entrada masiva diferente"
    save(out / "controles/entradas_masivas.json", source_checks)
    print("inputs", len(source_checks), "autenticados", flush=True)


def calibration(root, out, temp):
    import numpy as np

    sys.path[:0] = [str(root), str(root / "src")]
    from scripts.intraday_risk_report import episode_price_descriptions

    risk = root / "entregas/entrega_4/riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z"
    temp.mkdir(parents=True, exist_ok=False)
    for name in ("evidencia/episodios.parquet", "tablas/catalogo_incidentes.csv"):
        dest = temp / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(risk / name, dest)
    for sub in ("figuras/fuentes",):
        (temp / sub).mkdir(parents=True)
    summaries = episode_price_descriptions(temp, rows(risk / "tablas/catalogo_incidentes.csv"))
    details = rows(temp / "figuras/fuentes/calibracion_episodios.csv")
    original_details = rows(risk / "figuras/fuentes/calibracion_episodios.csv")
    assert details == original_details, "Recalibracion de episodios diferente"
    expected = rows(risk / "figuras/fuentes/calibracion_escenarios_pendientes.csv")
    recomputed = rows(temp / "figuras/fuentes/calibracion_escenarios_pendientes.csv")
    assert recomputed == expected, "Cuantiles diferentes"
    # Conserva las fracciones textuales originales, no redondea para publicar.
    for name in ("calibracion_episodios.csv", "calibracion_escenarios_pendientes.csv"):
        dest = out / "tablas" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(risk / "figuras/fuentes" / name, dest)
    diffs = []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        a, b = [r for r in summaries if r["symbol"] == symbol]
        for key in ("p90_adverse_fraction", "maximum_adverse_fraction"):
            diffs.append(dict(symbol=symbol, level=key, original=str(a[key]), proxy=str(b[key]),
                              difference_fraction=str(Decimal(str(b[key])) - Decimal(str(a[key])))))
    table(out / "tablas/diferencias_proxy.csv", diffs)
    episodes = [r for r in rows(risk / "tablas/catalogo_incidentes.csv") if r["scenario"] == "BASE_E3"]
    minute = 60_000_000_000
    schedule = []
    for ep in episodes:
        start = ((int(ep["start_ns"]) + minute - 1) // minute) * minute
        end = max(start + minute, ((int(ep["end_ns"]) + minute - 1) // minute) * minute)
        schedule.append(dict(symbol=ep["symbol"], episode_id=ep["episode_id"], strategy=ep["strategy"],
                             base_start_ns=ep["start_ns"], base_end_ns=ep["end_ns"],
                             first_bar_open_ns=start, plateau_end_open_ns=end,
                             recovery_end_open_ns=end + 60 * minute))
    table(out / "tablas/calendario_shocks_propuesto.csv", schedule)
    summary = []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        selected = [r for r in schedule if r["symbol"] == symbol]
        unions = []
        for r in sorted(selected, key=lambda r: r["first_bar_open_ns"]):
            a, b = r["first_bar_open_ns"], r["recovery_end_open_ns"]
            if unions and a <= unions[-1][1]:
                unions[-1][1] = max(unions[-1][1], b)
            else:
                unions.append([a, b])
        summary.append(dict(symbol=symbol, episodes=len(selected), merged_windows=len(unions),
                            affected_bar_opens=sum((b-a)//minute for a,b in unions)))
    save(out / "controles/calibracion.json", dict(passed=True, source=str(risk),
         episode_rows_equal=len(details), summaries_equal=summaries, numpy=np.__version__,
         percentile_method="numpy.quantile(q=0.9, method=linear); default original",
         episode_formula="max(0,1-minimum_spot_price/initial_spot_price)",
         catalogue_mask="incident_exposure_mask: intervalo activo y pre-cierre; no POST cubierto",
         schedule_summary=summary, economic_simulations=0))
    print("calibracion", summaries, "calendario", summary, flush=True)


def market(root, data, out):
    import pyarrow.parquet as pq

    sys.path[:0] = [str(root), str(root / "src")]
    from crypto_carry.config import iso, timestamp

    manifest_path = data / "data/minutes/2022_2026_continuous/derived_marks/futures_scaled/manifests/processed.json"
    manifest = read(manifest_path)
    source_rows, source_ids = {}, []
    for e in manifest["entries"]:
        if e["dataset"] == "minute_bars" and e["date"] in {"2023-02", "2023-03"}:
            p = data / e["path"]
            assert sha(p) == e["sha256"]
            source_ids.append(dict(path=e["path"], sha256=e["sha256"], bytes=p.stat().st_size))
            key = e["symbol"], e["market"]
            source_rows.setdefault(key, {}).update({r["open_time"]: r for r in pq.ParquetFile(p).read().to_pylist()})
    a, start, stop = [timestamp(t) for t in ("2023-03-24T11:26:00Z", "2023-03-24T11:27:00Z", "2023-03-24T14:00:00Z")]
    first = timestamp("2023-03-22T00:00:00Z")
    last = timestamp("2023-03-24T00:00:00Z")
    minute, day = 60_000_000_000, 86400_000_000_000
    coverage, anchors, liquidity, chronology, prevolume = [], [], [], [], []

    def median(values):
        v = sorted(values)
        n = len(v)
        return v[n//2] if n % 2 else (v[n//2-1]+v[n//2])/2

    for symbol in ("BTCUSDT", "ETHUSDT"):
        spot, future = source_rows[symbol, "spot"], source_rows[symbol, "futures"]
        for t in range(first, last, minute):
            assert t in spot, (symbol, iso(t), "missing pre-halt spot")
        coverage.append(dict(symbol=symbol, calibration_minutes=(last-first)//minute,
            calibration_missing=0, full_closed_minutes=(stop-start-minute)//minute,
            zero_volume=sum(t in spot and Decimal(spot[t]["base_volume"]) == 0 for t in range(start+minute,stop,minute)),
            absent=sum(t not in spot for t in range(start+minute,stop,minute)),
            future_minutes=sum(t in future for t in range(start,stop,minute))))
        k = Decimal(spot[a]["close"]) / Decimal(future[a]["close"])
        anchors.append(dict(symbol=symbol, anchor_open=iso(a), available=iso(a+minute),
            spot_close=spot[a]["close"], futures_close=future[a]["close"], ratio=str(k),
            ratio_definition="Decimal division precision 28; exact numerator/denominator retained; no reopen fit",
            first_observed_reopen_open=spot[stop]["open"], first_observed_reopen_close=spot[stop]["close"],
            futures_reopen_open=future[stop]["open"], futures_reopen_close=future[stop]["close"],
            opening_basis_residual=str(Decimal(spot[stop]["open"])/(k*Decimal(future[stop]["open"]))-1),
            closing_basis_residual=str(Decimal(spot[stop]["close"])/(k*Decimal(future[stop]["close"]))-1)))
        for hour in range(11, 14):
            for d in range(first, last, day):
                for offset in range(60):
                    prior_time = d + (hour * 60 + offset) * minute
                    r = spot[prior_time]
                    assert r["available_at"] <= start
                    prevolume.append(dict(symbol=symbol, hour_utc=hour,
                        open_time=r["open_time"], utc=iso(prior_time),
                        base_volume=r["base_volume"], trade_count=r["trade_count"]))
        for t in range(start,stop,minute):
            assert t in future and Decimal(future[t]["base_volume"]) > 0
            minute_of_day = t % day
            hour = minute_of_day // (60 * minute)
            observations = [r for r in prevolume if r["symbol"] == symbol
                            and r["hour_utc"] == hour]
            volumes = [Decimal(r["base_volume"]) for r in observations]
            trades = [Decimal(r["trade_count"]) for r in observations]
            v = median(volumes)
            liquidity.append(dict(symbol=symbol, open_utc=iso(t), minute_of_day=minute_of_day//minute,
                hour_utc=hour, observations=len(volumes),
                zero_observations=sum(v==0 for v in volumes),
                median_base_volume=str(v), synthetic_trade_count=int(median(trades)) if v>0 else 0,
                gross_cap_base=str(v*Decimal("0.01")), volume_unit=symbol.removesuffix("USDT")+"/minute"))
        for t in [a,start,start+minute,timestamp("2023-03-24T12:39:00Z"),timestamp("2023-03-24T12:40:00Z"),stop-minute,stop,stop+minute]:
            for market, source in [("spot",spot),("futures",future)]:
                r = source.get(t)
                chronology.append(dict(symbol=symbol,market=market,open_utc=iso(t),present=r is not None,
                    available_at=iso(r["available_at"]) if r else None,
                    open=r["open"] if r else None,high=r["high"] if r else None,
                    low=r["low"] if r else None,close=r["close"] if r else None,
                    base_volume=r["base_volume"] if r else None,quote_volume=r["quote_volume"] if r else None,
                    trade_count=r["trade_count"] if r else None))
    table(out / "tablas/anclas_cf.csv", anchors)
    table(out / "tablas/volumen_cf_propuesto.csv", liquidity)
    table(out / "tablas/muestra_volumen_previa.csv", prevolume)
    table(out / "tablas/cronologia_spot_futuros.csv", chronology)
    save(out / "controles/cobertura_cf.json", dict(passed=True, coverage=coverage, sources=source_ids,
         window_start=iso(first), window_end=iso(last), intervention_start=iso(start),intervention_end=iso(stop),
         source_manifest_sha256=sha(manifest_path), economic_simulations=0))
    print("cobertura",coverage,"anclas",anchors,flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["inputs", "massive_inputs", "calibration", "market"])
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--data-root", type=Path, default=Path("D:/Backtesting"))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--temp", type=Path)
    args = p.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    if any((parent / "manifiesto_paquete.json").exists() for parent in (out, *out.parents)):
        raise ValueError("El destino no puede estar dentro de un sello previo")
    if args.temp is not None and args.temp.resolve().is_relative_to(root):
        raise ValueError("La copia temporal debe estar fuera del árbol del repositorio")
    if args.action == "inputs":
        inputs(root, args.data_root, out)
    elif args.action == "massive_inputs":
        massive_inputs(root, args.data_root, out)
    elif args.action == "calibration":
        if args.temp is None:
            p.error("--temp requerido para copia real exclusiva")
        calibration(root, out, args.temp)
    else:
        market(root, args.data_root, out)
    save(out / f"controles/{args.action}_terminado.json", dict(passed=True,
         utc=datetime.now(timezone.utc).isoformat(), engine_replay=False))


if __name__ == "__main__":
    main()

"""Authenticate original inputs, check transformed source candles, freeze stage B."""

import argparse
import json
import shutil
import sys
from collections import Counter
from dataclasses import fields
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from crypto_carry.config import Config  # noqa: E402
from crypto_carry.data.market_calendar import closure_for_minute  # noqa: E402
from crypto_carry.data.replay import input_hashes  # noqa: E402
from crypto_carry.data.stress_counterfactual import (  # noqa: E402
    MINUTE,
    compile_shock,
    counterfactual_bar,
    shock_bar,
)
from crypto_carry.models import MinuteBar  # noqa: E402
from crypto_carry.reporting import _code_identity, verify_run  # noqa: E402
from crypto_carry.serialization import encode  # noqa: E402
from scripts.execution_delays_sources import extract_windows  # noqa: E402
from scripts.stress_counterfactual_contract import (  # noqa: E402
    BASES,
    CONTROLS,
    SCENARIOS,
    STRATEGIES,
    authenticate_approval,
    digest,
    load_spec,
    read,
)


def immutable_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")


def bar_from_row(row):
    decimals = {"open", "high", "low", "close", "base_volume", "quote_volume"}
    return MinuteBar(**{f.name: D(row[f.name]) if f.name in decimals else row[f.name]
                       for f in fields(MinuteBar)})


def check_sources(candidate, data, config, inputs):
    specs = {s: load_spec(candidate, s) for s in SCENARIOS}
    keys = set()
    factors = compile_shock(specs["SH_MAX"]["episodes"], specs["SH_MAX"]["magnitudes"])
    keys.update((s, "spot", u) for (s, u) in factors)
    cf = specs["CF_SIN_INTERRUPCION"]
    for symbol in cf["anchors"]:
        keys.update((symbol, market, u) for market in ("spot", "futures")
                    for u in range(cf["start"] - MINUTE, cf["end"], MINUTE))
    requested = [dict(symbol=s, market=m, open_time=u) for s, m, u in sorted(keys)]
    sources = extract_windows(data, config, requested, inputs)
    indexed = {(r["symbol"], r["market"], r["open_time"]): r for r in sources}
    checks = []
    for scenario in ("SH_P90", "SH_MAX"):
        spec = specs[scenario]
        counts = Counter()
        for (symbol, opening), factor in compile_shock(spec["episodes"], spec["magnitudes"]).items():
            row = indexed[symbol, "spot", opening]
            counts[symbol + "_calendar_minutes"] += 1
            if row["present"]:
                bar = bar_from_row(row)
                changed = shock_bar(bar, factor, scenario)
                assert changed.base_volume == bar.base_volume
                counts[symbol + "_observed_transformed"] += 1
            elif closure_for_minute(symbol, "spot", opening) is not None:
                counts[symbol + "_absent_documented_closure"] += 1
            else:
                raise ValueError("Unexplained source gap in shock schedule")
        checks.append(dict(scenario=scenario, passed=True, counts=dict(counts)))
    bases = {}
    for (symbol, opening), (volume, count) in cf["volumes"].items():
        anchor = cf["anchors"][symbol]
        for market in ("spot", "futures"):
            original = indexed[symbol, market, cf["start"] - MINUTE]
            if not original["present"] or D(original["close"]) != anchor[market]:
                raise ValueError("Counterfactual anchor mismatch")
        future = indexed[symbol, "futures", opening]
        if not future["present"]:
            raise ValueError("Counterfactual future is missing")
        bar = counterfactual_bar(bar_from_row(future), anchor["spot"], anchor["futures"],
                                volume, count, "CF_SIN_INTERRUPCION")
        basis = D(future["close"]) / bar.close - 1
        if basis >= 0:
            raise ValueError("The approved counterfactual must have negative basis")
        bases.setdefault(symbol, []).append(basis)
    checks.append(dict(scenario="CF_SIN_INTERRUPCION", passed=True, synthetic_bars=306,
        basis_by_symbol={s: dict(min=min(v), max=max(v), basis_nonnegative_minutes=0)
                         for s, v in bases.items()}))
    evidence = candidate / "evidencia_mercado"
    evidence.mkdir(exist_ok=True)
    target = evidence / "fuentes_intervencion.parquet"
    if target.exists():
        raise FileExistsError(target)
    pq.write_table(pa.Table.from_pylist(sources), target, compression="zstd")
    result = dict(passed=True, source_rows=len(sources), checks=checks,
                  source_extract_sha256=digest(target), economic_replay=False,
                  scope="Exact approved minutes and anchors; unchanged full inputs authenticated separately")
    immutable_json(candidate / "controles/fuentes_intervencion_etapa_b.json", result)
    return result


def prepare(candidate, data):
    authenticate_approval(candidate)
    references = read(candidate / "indice_referencias.json")["references"]
    records, configs = [], {}
    for ref in references:
        strategy = ref["strategy"]
        base = data / "outputs" / BASES[strategy]
        corrected = Path(ref["original_control_path"])
        for path, expected in ((base, ref["original_manifest_sha256"]),
                               (corrected, ref["control_manifest_sha256"])):
            if digest(path / "run_manifest.json") != expected or not verify_run(path)["valid"]:
                raise ValueError("A preserved reference changed: " + str(path))
        manifest = read(corrected / "run_manifest.json")
        for name, expected in manifest["code_files"].items():
            if digest(ROOT / name) != expected:
                raise ValueError("Common corrected engine code changed before optional adapter: " + name)
        config = Config.load(base / "effective_config.toml")
        if config.to_dict() != Config.load(corrected / "effective_config.toml").to_dict():
            raise ValueError("Corrected reference configuration differs")
        configs[strategy] = config
        records.append(dict(strategy=strategy, original=str(base), corrected=str(corrected),
                            original_manifest_sha256=ref["original_manifest_sha256"],
                            corrected_manifest_sha256=ref["control_manifest_sha256"],
                            original_code_files_unchanged=True))
    config = configs["conditional"]
    if config.to_dict() != configs["permanent"].to_dict():
        raise ValueError("Strategies do not share the same BASE configuration")
    print("Authenticating all original input bytes...", flush=True)
    inputs = input_hashes(data, config)
    expected = read(data / "outputs" / BASES["conditional"] / "run_manifest.json")["input_hashes"]
    if inputs != expected:
        raise ValueError("Full original input hashes changed")
    immutable_json(candidate / "input_hashes_etapa_b.json", inputs)
    immutable_json(candidate / "controles/referencias_etapa_b.json", records)
    immutable_json(candidate / "controles/entradas_etapa_b.json", dict(
        passed=True, utc=datetime.now(UTC).isoformat(), identities=len(inputs), data_root=str(data),
        base_manifest_sha256=digest(data / "outputs" / BASES["conditional"] / "run_manifest.json")))
    specs = {s: encode(load_spec(candidate, s)) for s in CONTROLS + SCENARIOS}
    immutable_json(candidate / "especificaciones_ejecutables.json", specs)
    config_dir = ROOT / "configs/entrega_4/estres_contrafactual" / candidate.parent.name
    config_dir.mkdir(parents=True, exist_ok=True)
    for strategy in STRATEGIES:
        target = config_dir / f"BASE__{strategy}.toml"
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(configs[strategy].to_toml())
    check_sources(candidate, data, config, inputs)
    print("APPROVED SOURCES PASS; no portfolios executed", flush=True)


def freeze(candidate):
    authenticate_approval(candidate)
    if not read(candidate / "controles/fuentes_intervencion_etapa_b.json")["passed"]:
        raise ValueError("Source transformation gate failed")
    gate = read(candidate / "controles/puerta_pruebas_etapa_b.json")
    if not gate["passed"]:
        raise ValueError("Pre-execution test gate failed")
    code, files = _code_identity()
    names = ["scripts/run_stress_counterfactual.py", "scripts/stress_counterfactual_contract.py",
             "scripts/prepare_stress_counterfactual.py", "scripts/run_historical_rules_sensitivity.py",
             "scripts/run_execution_delays.py", "scripts/execution_delays.py",
             "scripts/execution_delays_guards.py", "scripts/signal_sensitivity.py",
             "scripts/execution_delays_sources.py", "scripts/execution_delays_audit.py",
             "scripts/continuous_delivery/portfolio.py", "scripts/continuous_delivery/common.py",
             "scripts/continuous_delivery/__init__.py", "scripts/return_capital/__init__.py",
             "scripts/check_execution_delays_base.py", "scripts/return_capital/common.py",
             "scripts/cost_capacity_ledger.py", "scripts/cost_capacity_audit.py",
             "scripts/return_capital/accounting.py"]
    package_names = ["aprobacion_recibida.json", "identidad_propuesta.json",
                     "input_hashes_etapa_b.json", "especificaciones_ejecutables.json",
                     "indice_referencias.json", "controles/puerta_pruebas_etapa_b.json",
                     "controles/fuentes_intervencion_etapa_b.json",
                     "evidencia_mercado/fuentes_intervencion.parquet"]
    package_names += list(read(candidate / "aprobacion_recibida.json")["approved_files_sha256"])
    for name in (*files, *names):
        target = candidate / "codigo_ejecutado" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(target)
        shutil.copyfile(ROOT / name, target)
    immutable_json(candidate / "protocolo_ejecucion.json", dict(
        utc=datetime.now(UTC).isoformat(), approved_scenarios=list(SCENARIOS),
        technical_controls=list(CONTROLS), engine_code_hash=code, code_files=files,
        project_files={n: digest(ROOT / n) for n in names},
        candidate_files={n: digest(candidate / n) for n in package_names},
        economic_assumptions_unchanged=True, execution_order=list(CONTROLS + SCENARIOS)))
    print("FROZEN", code, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--data-root", default=Path("D:/Backtesting"), type=Path)
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        freeze(args.candidate.resolve())
    else:
        prepare(args.candidate.resolve(), args.data_root.resolve())


if __name__ == "__main__":
    main()

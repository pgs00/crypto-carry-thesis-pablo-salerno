"""Fixed B6 starts and shared, authenticated inputs; economic engine unchanged."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from crypto_carry.config import Config, timestamp
from crypto_carry.data.prescribed import prescribed_rules
from crypto_carry.data.replay import input_hashes, iter_records
from crypto_carry.mark_gap_study import GapAuditedBacktest
from crypto_carry.reporting import _code_identity, verify_run

ROOT = Path(__file__).resolve().parents[1]
B5 = ROOT / "entregas/entrega_4/estres_contrafactual/20260930T214617Z/paquete_20261001T211248Z"
BASES = {"conditional": "run_ad71d751b20623006c195ff3", "permanent": "run_dfea4b7ac1475668d5968c97"}
STARTS = {"I2023": "2023-01-01T00:00:00Z", "I2024": "2024-01-01T00:00:00Z"}
TASKS = [(s, strategy) for s in STARTS for strategy in BASES]
THREAD_ENV = {
    key: "1"
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
}
THREAD_ENV.update(PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg", PYTHONIOENCODING="utf-8")


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    """One writer per target, atomic replacement; preserve immutable files separately."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def immutable(path, value):
    path = Path(path)
    if path.exists():
        if read(path) != value:
            raise ValueError(f"Immutable contract changed: {path}")
        return
    save(path, value)


def scenario_configs(base):
    return {name: base.changed(start=start) for name, start in STARTS.items()}


def validate_variant(base, scenario, config):
    if scenario not in STARTS or config.to_dict() != base.changed(start=STARTS[scenario]).to_dict():
        raise ValueError(f"Unauthorized B6 configuration diff: {scenario}")
    before, after = base.to_dict(), config.to_dict()
    return {k: {"before": before[k], "after": after[k]} for k in before if before[k] != after[k]}


def simulate(config, data_root, strategy, inputs):
    if strategy not in BASES:
        raise ValueError("Unknown B6 strategy")
    backtest = GapAuditedBacktest(
        config, prescribed_rules(config), strategy, strategy == "conditional", inputs
    )
    backtest.run(
        iter_records(
            data_root,
            timestamp(config.start),
            timestamp(config.end),
            config.window_hours + 24,
            data_dir=config.data_dir,
            execution_model=config.execution_model,
            include_closed_bars=True,
            mark_gap_method=config.mark_gap_method,
        )
    )
    return backtest


def file_record(path, digest=None):
    path = Path(path).resolve()
    before = path.stat()
    digest = digest or sha(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"Input changed during authentication: {path}")
    return dict(path=str(path), size=after.st_size, mtime_ns=after.st_mtime_ns, sha256=digest)


def check_inventory(records):
    """Cheap guard against drift of the shared byte-authenticated snapshot."""
    for row in records:
        path = Path(row["path"])
        if not path.is_file():
            raise ValueError(f"Input changed or missing: {path}")
        stat = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != (row["size"], row["mtime_ns"]):
            # Revalidate changed metadata, but do not silently replace the frozen inventory.
            actual = sha(path)
            raise ValueError(f"Input changed since authentication: {path}; sha256={actual}")


def launch_capacity(
    *, available_gib, resident_gib, physical, cpu, disk_free_gib, paging_mbps, ramped
):
    active = len(resident_gib)
    if cpu >= 90 or disk_free_gib < 15 or paging_mbps > 8:
        return active
    growth = sum(max(0, 4 - size) for size in resident_gib)
    additional = max(0, int((available_gib - 6 - growth) // 4))
    target = min(4 if ramped else 2, max(1, physical))
    return max(active, min(target, active + additional))


def authenticate_b5_file(name):
    manifest = read(B5 / "manifiesto_paquete.json")
    if (
        sha(B5 / "manifiesto_paquete.json")
        != (B5 / "manifiesto_paquete.sha256").read_text().strip().split()[0]
    ):
        raise ValueError("B5 seal changed")
    member = next(r for r in manifest["members"] if r["path"] == name)
    path = B5 / name
    if sha(path) != member["sha256"] or path.stat().st_size != member["bytes"]:
        raise ValueError("B5 reference changed: " + name)
    return path


def prepare(candidate, data_root):
    candidate, data_root = Path(candidate).resolve(), Path(data_root).resolve()
    protocol_path = candidate / "protocolo_ejecucion.json"
    if protocol_path.exists():
        return verify_contract(candidate)
    candidate.mkdir(parents=True, exist_ok=True)
    code, files = _code_identity()
    b5_protocol = read(authenticate_b5_file("protocolo_ejecucion.json"))
    if b5_protocol["engine_code_hash"] != code:
        raise ValueError("Economic engine differs from compatible B5 protocol")
    selected = [
        "indice_referencias.json",
        "protocolo_ejecucion.json",
        "controles/compatibilidad_CONTROL_APAGADO_ac1a148ac22e.json",
        "controles/compatibilidad_CONTROL_CERO_ac1a148ac22e.json",
    ]
    for name in selected:
        source = authenticate_b5_file(name)
        target = candidate / "fuentes/b5" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(
        candidate / "fuentes/b5/indice_referencias.json", candidate / "indice_referencias.json"
    )
    audit = read(B5.parent / "controles_finales_20261001T211248Z/verificacion_sello.json")
    if not audit["passed"]:
        raise ValueError("Final B5 offline verification has not passed")
    immutable(candidate / "fuentes/b5/verificacion_sello_externa.json", audit)
    references = read(candidate / "indice_referencias.json")["references"]
    configs, verified = {}, []
    for ref in references:
        base = data_root / "outputs" / ref["original_run_id"]
        corrected = Path(ref["original_control_path"])
        for path, expected in (
            (base, ref["original_manifest_sha256"]),
            (corrected, ref["control_manifest_sha256"]),
        ):
            if sha(path / "run_manifest.json") != expected or not verify_run(path)["valid"]:
                raise ValueError(f"Unauthenticated preserved reference: {path}")
            verified.append(dict(path=str(path), manifest_sha256=expected, verified=True))
        configs[ref["strategy"]] = Config.load(base / "effective_config.toml")
        if (
            configs[ref["strategy"]].to_dict()
            != Config.load(corrected / "effective_config.toml").to_dict()
        ):
            raise ValueError("BASE/control configurations differ")
        for name, expected in read(corrected / "run_manifest.json")["code_files"].items():
            if sha(ROOT / name) != expected:
                raise ValueError("Corrected economic source changed: " + name)
    base = configs["conditional"]
    if base.to_dict() != configs["permanent"].to_dict():
        raise ValueError("BASE strategies must share configuration")
    expected = read(data_root / "outputs" / BASES["conditional"] / "run_manifest.json")[
        "input_hashes"
    ]
    # Exactly once for the full identity required by the existing writer, including source archives.
    before = {
        n: file_record(data_root / n, digest=h)
        for n, h in expected.items()
        if n != "processed_manifest_semantics"
    }
    print("Authenticating existing runner input identity once", flush=True)
    inputs = input_hashes(data_root, base)
    if inputs != expected:
        raise ValueError("Original market input identity differs")
    inventory = list(before.values())
    for name in (
        base.data_dir + "/manifests/processed.json",
        base.data_dir + "/manifests/download.json",
    ):
        if (data_root / name).exists():
            inventory.append(file_record(data_root / name))
    check_inventory(inventory)
    immutable(candidate / "inventario_entradas.json", inventory)
    immutable(candidate / "input_hashes.json", inputs)
    immutable(candidate / "controles/referencias.json", verified)
    cfgdir = candidate / "configuraciones"
    cfgdir.mkdir(exist_ok=True)
    for scenario, cfg in scenario_configs(base).items():
        validate_variant(base, scenario, cfg)
        target = cfgdir / (scenario + ".toml")
        target.write_text(cfg.to_toml(), encoding="utf-8", newline="\n")
        external = (
            ROOT
            / "configs/entrega_4/estabilidad_incertidumbre"
            / candidate.parent.name
            / target.name
        )
        external.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(target, external)
    helpers = [
        "scripts/stability_uncertainty_contract.py",
        "scripts/run_stability_uncertainty.py",
        "scripts/signal_sensitivity.py",
        "scripts/run_signal_sensitivity.py",
        "scripts/continuous_delivery/portfolio.py",
        "scripts/continuous_delivery/common.py",
    ]
    package_names = [
        "inventario_entradas.json",
        "input_hashes.json",
        "indice_referencias.json",
        "fuentes/encargo_b6.md",
        "controles/puerta_pruebas.json",
    ]
    package_names += ["configuraciones/" + s + ".toml" for s in STARTS]
    if not read(candidate / "controles/puerta_pruebas.json")["passed"]:
        raise ValueError("Start/warmup fixtures have not passed")
    protocol = dict(
        schema="b6-v1",
        fixed_before_calculation_utc=datetime.now(UTC).isoformat(),
        engine_code_hash=code,
        code_files=files,
        project_files={n: sha(ROOT / n) for n in helpers},
        package_files={n: sha(candidate / n) for n in package_names},
        tasks=TASKS,
        initial_cash="10000",
        warmup_hours=360,
        original_history_start=base.history_start,
        bootstrap=dict(
            method="paired_circular_calendar_year_contiguous_segments",
            main_block_days=28,
            sensitivity_block_days=[14, 56],
            replicas_per_length=5000,
            seed_root=20261001,
            bit_generator="PCG64",
            seed_sequence=True,
            quantile_method="linear",
            quantiles=[0.025, 0.975],
            batch_size=128,
            min_valid_fraction=0.95,
        ),
        index_sha256=sha(ROOT / ".git/index"),
        head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        thread_environment=THREAD_ENV,
        engine_replays=4,
        base_replays=0,
        authentication_scope="Full existing runner input identity once; worker stat guards before/after; no market rehash per replica",
    )
    immutable(protocol_path, protocol)
    for name in (*files, *helpers):
        target = candidate / "codigo_ejecutado" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return verify_contract(candidate)


def verify_contract(candidate):
    candidate = Path(candidate)
    protocol = read(candidate / "protocolo_ejecucion.json")
    if protocol["engine_code_hash"] != _code_identity()[0]:
        raise ValueError("Economic code changed")
    for name, expected in protocol["project_files"].items():
        if sha(ROOT / name) != expected:
            raise ValueError("Executing helper changed: " + name)
    for name, expected in protocol["package_files"].items():
        if sha(candidate / name) != expected:
            raise ValueError("Predeclared contract file changed: " + name)
    check_inventory(read(candidate / "inventario_entradas.json"))
    return protocol

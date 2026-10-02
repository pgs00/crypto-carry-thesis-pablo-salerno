"""Offline B6 verification: seal, fixed contracts, accounting and bootstrap recomputation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"
os.environ.update(PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def seal(package):
    package = Path(package)
    if (package / "manifiesto_paquete.json").exists() or (
        package / "manifiesto_paquete.sha256"
    ).exists():
        raise FileExistsError("Never overwrite an existing seal")
    members = [
        dict(path=p.relative_to(package).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(package.rglob("*"))
        if p.is_file()
    ]
    result = dict(
        schema="b6-package-v1",
        created_utc=datetime.now(UTC).isoformat(),
        members=members,
        economic_replays=4,
        base_replays=0,
        bootstrap_engine_replays=0,
    )
    path = package / "manifiesto_paquete.json"
    path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    (package / "manifiesto_paquete.sha256").write_text(sha(path) + "\n", encoding="ascii")
    return result


def verify_seal(package):
    package = Path(package).resolve()
    path = package / "manifiesto_paquete.json"
    if sha(path) != (package / "manifiesto_paquete.sha256").read_text().strip():
        raise ValueError("Package manifest sidecar differs")
    manifest = read(path)
    if manifest.get("schema") != "b6-package-v1" or not isinstance(manifest.get("members"), list):
        raise ValueError("Invalid B6 manifest schema")
    expected = {"manifiesto_paquete.json", "manifiesto_paquete.sha256"}
    for member in manifest["members"]:
        name = member.get("path")
        if not isinstance(name, str) or "\\" in name or ":" in name:
            raise ValueError("Invalid member path")
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts or name in expected:
            raise ValueError("Duplicate or unsafe member path")
        if type(member.get("bytes")) is not int or member["bytes"] < 0:
            raise ValueError("Invalid member bytes type")
        digest = member.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("Invalid digest type")
        target = package / name
        if not target.resolve().is_relative_to(package) or not target.is_file():
            raise ValueError("Missing or escaping member")
        if target.stat().st_size != member["bytes"] or sha(target) != digest:
            raise ValueError("Changed package member: " + name)
        expected.add(name)
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    if expected != actual:
        raise ValueError("Unexpected or missing package members: " + str(expected ^ actual))
    return dict(passed=True, members=len(manifest["members"]), manifest_sha256=sha(path))


def check_statistical_protocol(value):
    expected = dict(
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
    )
    if value != expected or any(
        type(value[k]) is not int
        for k in ("main_block_days", "replicas_per_length", "seed_root", "batch_size")
    ):
        raise ValueError("Statistical protocol differs from authorized fixed values/types")


def verify_contract(package):
    from crypto_carry.config import Config
    from crypto_carry.reporting import _code_identity

    protocol = read(package / "protocolo_ejecucion.json")
    check_statistical_protocol(protocol["bootstrap"])
    if protocol["engine_replays"] != 4 or protocol["base_replays"] != 0:
        raise ValueError("Unapproved replay scope")
    if _code_identity()[0] != protocol["engine_code_hash"]:
        raise ValueError("Included economic code differs from execution")
    for name, expected in protocol["code_files"].items():
        if sha(ROOT / name) != expected:
            raise ValueError("Included economic source changed: " + name)
    for name, expected in protocol["project_files"].items():
        if sha(ROOT / name) != expected:
            raise ValueError("Frozen runner/helper changed: " + name)
    for name, expected in protocol["package_files"].items():
        if sha(package / name) != expected:
            raise ValueError("Predeclared input changed: " + name)
    refs = read(package / "indice_referencias.json")["references"]
    base = Config.load(package / "fuentes/base_config.toml")
    for ref in refs:
        manifest_path = package / "fuentes" / f"BASE_manifest_{ref['strategy']}.json"
        if sha(manifest_path) != ref["original_manifest_sha256"]:
            raise ValueError("BASE anchor changed")
        if read(manifest_path)["config"] != base.to_dict():
            raise ValueError("BASE configuration mismatch")
    tasks = [(s, k) for s in ("I2023", "I2024") for k in ("conditional", "permanent")]
    if protocol["tasks"] != [list(t) for t in tasks]:
        raise ValueError("Task matrix changed")
    states = read(package / "indice_corridas.json")
    if {(s["scenario"], s["strategy"]) for s in states} != set(tasks) or len(states) != 4:
        raise ValueError("Portfolio index differs from four authorized portfolios")
    inputs = dict(
        read(package / "input_hashes.json"),
        b6_protocol_sha256=sha(package / "protocolo_ejecucion.json"),
    )
    for state in states:
        scenario, strategy = state["scenario"], state["strategy"]
        config = Config.load(package / "configuraciones" / f"{scenario}.toml")
        if config.to_dict() != base.changed(start=f"{scenario[1:]}-01-01T00:00:00Z").to_dict():
            raise ValueError("Economic field other than start differs")
        manifest_path = (
            package / "fuentes/corridas" / f"{scenario}__{strategy}" / "run_manifest.json"
        )
        manifest = read(manifest_path)
        if (
            sha(manifest_path) != state["manifest_sha256"]
            or state["status"] != "ejecutado"
            or manifest["run_id"] != state["run_id"]
            or manifest["config"] != config.to_dict()
            or manifest["input_hashes"] != inputs
            or manifest["code_hash"] != protocol["engine_code_hash"]
            or manifest["label"] != f"E4-estabilidad-{scenario}"
            or manifest["strategies"]
            != [dict(strategy=strategy, funding_filter_enabled=strategy == "conditional")]
            or manifest["status"] not in {"complete", "insolvent"}
        ):
            raise ValueError("New run identity/configuration mismatch")
    return dict(
        passed=True,
        portfolios=4,
        baseline_replays=0,
        economic_code_hash=protocol["engine_code_hash"],
    )


def verify(package):
    package = Path(package).resolve()
    sealed = verify_seal(package)
    contract = verify_contract(package)
    from scripts import stability_uncertainty_bootstrap as bootstrap
    from scripts import stability_uncertainty_report as financial
    from scripts import stability_uncertainty_synthesis as synthesis

    result = dict(
        passed=True,
        sealed=sealed,
        contract=contract,
        financial=financial.verify(package),
        bootstrap=bootstrap.verify(package),
        synthesis=synthesis.verify(package),
        economic_engine_replayed=False,
        original_data_root_required=False,
        scope="All sealed bytes; financial/accounting and fixed bootstrap recalculated from included compact inputs",
        massive_sources_not_reread="Original full minute partitions and source archives; shared authenticated inventory and extracted execution witnesses",
        shared_logic="Existing accounting/exposure/H2/execution helpers and B6 compact-input analytical reducers",
        verified_utc=datetime.now(UTC).isoformat(),
    )
    # A verifier must be read-only, including imports and native library caches.
    verify_seal(package)
    return result


def block_original_sources(roots):
    forbidden = [os.path.normcase(os.path.abspath(p)) for p in roots]
    allowed_runtime = os.path.normcase(os.path.abspath(sys.prefix))

    def audit(event, args):
        if event != "open" or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = os.path.normcase(os.path.abspath(os.fsdecode(args[0])))
        if path == allowed_runtime or path.startswith(allowed_runtime + os.sep):
            return
        if any(path == root or path.startswith(root + os.sep) for root in forbidden):
            raise PermissionError("Offline verification attempted original-source access: " + path)

    sys.addaudithook(audit)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--forbid-root", action="append", default=[])
    args = parser.parse_args()
    block_original_sources(args.forbid_root)
    result = verify(args.candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, default=str, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            dict(
                passed=True,
                manifest_sha256=result["sealed"]["manifest_sha256"],
                members=result["sealed"]["members"],
            )
        )
    )

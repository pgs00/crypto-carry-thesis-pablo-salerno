"""Snapshot small tools, or seal exactly one final block-5 delivery after its gate."""

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.return_capital.common import read_json, sha256, write_json  # noqa: E402


def no_links(folder):
    for path in (folder, *folder.rglob("*")):
        if path.is_symlink() or path.is_junction():
            raise ValueError("Evidence tree contains a filesystem link: " + str(path))


def snapshot_tools(candidate):
    if (candidate / "manifiesto_paquete.json").exists():
        raise ValueError("Cannot edit sealed tools")
    names = [p.relative_to(ROOT) for directory in ("src", "scripts")
             for p in sorted((ROOT / directory).rglob("*.py")) if "__pycache__" not in p.parts]
    names += [Path("pyproject.toml"), Path("uv.lock")]
    names += [p.relative_to(ROOT) for p in sorted((ROOT / "tests").rglob("*.py"))
              if "__pycache__" not in p.parts]
    names += [p.relative_to(ROOT) for p in sorted((ROOT / "tests").rglob("*"))
              if p.is_file() and p.suffix in (".json", ".csv", ".toml", ".yaml", ".yml")]
    members = []
    for name in names:
        target = candidate / "herramientas" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        members.append(dict(path=name.as_posix(), sha256=sha256(target), bytes=target.stat().st_size))
    write_json(candidate / "herramientas/indice_codigo.json", dict(members=members,
        purpose="Portable postprocessing/verifier and test dependencies; no old evidence packages or market partitions",
        frozen_economic_snapshot_separate="../" + read_json(candidate / "protocolo_ejecucion.json").get(
            "code_snapshot", "codigo_ejecutado")))
    print("TOOLS SNAPSHOT", len(members), flush=True)


def seal(candidate, destination, approval_gate):
    from scripts.verify_stress_counterfactual import verify

    if destination.exists() or destination.resolve().is_relative_to(candidate.resolve()):
        raise ValueError("Final destination must be new and outside the editable candidate")
    if (candidate / "manifiesto_paquete.json").exists():
        raise ValueError("The editable candidate is already sealed")
    gate = read_json(approval_gate)
    if not gate["passed"] or not all(gate[k] for k in (
            "full_regression", "ruff", "portable_copy_verified", "negative_tests", "final_review",
            "preserved_originals", "index_unchanged", "all_six_economic_and_four_technical")):
        raise ValueError("Final sealing gate is incomplete")
    no_links(candidate)
    result = verify(candidate, unsealed=True)
    if not result["passed"] or result["partial"]:
        raise ValueError("Final numerical verification did not pass")
    shutil.copytree(candidate, destination)
    members = [dict(path=p.relative_to(destination).as_posix(), bytes=p.stat().st_size, sha256=sha256(p))
               for p in sorted(destination.rglob("*")) if p.is_file()]
    write_json(destination / "manifiesto_paquete.json", dict(schema="stress_counterfactual_v1",
        created_utc=datetime.now(UTC).isoformat(), members=members,
        economic_portfolios=6, technical_control_portfolios=4, preserved_reference_portfolios=4,
        approval_gate_sha256=sha256(approval_gate), original_runs_preserved=True,
        scope="Approved hypothetical paths; compact offline postprocessing, not full economic replay"))
    (destination / "manifiesto_paquete.sha256").write_text(sha256(destination / "manifiesto_paquete.json") + "\n", encoding="ascii")
    print("SEALED", destination, sha256(destination / "manifiesto_paquete.json"), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--gate", type=Path)
    args = parser.parse_args()
    if args.snapshot:
        snapshot_tools(args.candidate.resolve())
    elif args.destination and args.gate:
        seal(args.candidate.resolve(), args.destination.resolve(), args.gate.resolve())
    else:
        parser.error("Choose --snapshot or both --destination and --gate")


if __name__ == "__main__":
    main()

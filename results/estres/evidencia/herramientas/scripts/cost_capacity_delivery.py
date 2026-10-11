"""Preservation and exact Git blob export using an isolated temporary index."""

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"src"))

from crypto_carry.config import Config  # noqa: E402
from crypto_carry.data.replay import input_hashes  # noqa: E402
from crypto_carry.reporting import _code_identity  # noqa: E402
from scripts.cost_capacity import BASES  # noqa: E402
from scripts.return_capital.common import read_json, sha256, write_json  # noqa: E402
from scripts.signal_sensitivity_delivery import git, real_index  # noqa: E402
from scripts.verify_rules_sensitivity_package import safe_path  # noqa: E402

CHANGED = {"src/crypto_carry/config.py", "src/crypto_carry/costs.py",
           "src/crypto_carry/diagnostics.py", "src/crypto_carry/data/prescribed.py"}


def preserve(project, work, data):
    initial = read_json(work/"preservacion_previa.json")
    for name, wanted in initial["tracked_files"].items():
        if name in CHANGED:
            if sha256(work/"codigo_previo"/name) != wanted:
                raise ValueError("Original economic source snapshot changed")
        elif name == ".gitattributes" and (work/"gitattributes_adicion.txt").exists():
            original = (work/"gitattributes_original.bin").read_bytes()
            addition = (work/"gitattributes_adicion.txt").read_bytes()
            if hashlib.sha256(original).hexdigest() != wanted or (project/name).read_bytes() != original+addition:
                raise ValueError("Attributes changed beyond scoped new-evidence addition")
        elif sha256(project/name) != wanted:
            raise ValueError("Unrelated tracked file changed: "+name)
    if sha256(real_index(project)) != initial["index_sha256"]:
        raise ValueError("User index changed")
    if git(project, ["rev-parse", "HEAD"]).decode().strip() != initial["head"]:
        raise ValueError("HEAD changed")
    protocol = read_json(work/"protocolo_previo.json")
    if _code_identity()[0] != protocol["engine_code_hash"]:
        raise ValueError("Frozen economic source changed")
    for name, wanted in protocol["project_files"].items():
        if sha256(project/name) != wanted:
            raise ValueError("Frozen executor changed")
    bases = []
    from crypto_carry.reporting import verify_run
    for item in read_json(work/"verificacion_base_previa.json")["runs"]:
        folder = Path(item["path"])
        if sha256(folder/"run_manifest.json") != item["manifest_sha256"] or not verify_run(folder)["valid"]:
            raise ValueError("Original BASE changed")
        bases.append(item["run_id"])
    previous = []
    for item in read_json(work/"autenticacion_referencias.json"):
        folder = Path(item["path"])
        if sha256(folder/"manifiesto_paquete.json") != item["manifest_sha256"]:
            raise ValueError("Previous sealed manifest changed")
        manifest = read_json(folder/"manifiesto_paquete.json")
        members = manifest.get("members", manifest.get("files"))
        for member in members:
            target = safe_path(folder, member["path"])
            if sha256(target) != member["sha256"] or target.stat().st_size != member.get("bytes", member.get("size")):
                raise ValueError("Previous sealed member changed")
        previous.append(dict(dependency=item["dependency"], members=len(members), sha256=item["manifest_sha256"]))
    base = Config.load(data/"outputs"/BASES["conditional"]/"effective_config.toml")
    inputs = input_hashes(data, base)
    if inputs != read_json(work/"input_hashes.json"):
        raise ValueError("Authenticated market inputs changed")
    return dict(passed=True, previous_tracked_files=len(initial["tracked_files"]),
        authorized_economic_paths=sorted(CHANGED), previous_packages=previous,
        original_base_ids=bases, input_identities=len(inputs),
        user_index_sha256=sha256(real_index(project)), head=initial["head"],
        engine_code_hash=protocol["engine_code_hash"])


def export_bytes(project, package):
    package = package.resolve()
    if not package.is_relative_to(project/"entregas/entrega_4/costos_capacidad"):
        raise ValueError("Export restricted to new block-3 evidence")
    before = sha256(real_index(project))
    temporary = Path(tempfile.mkdtemp(prefix="cost_capacity_git_export_"))
    index, output = temporary/"index", temporary/"checkout"
    names = sorted(p.relative_to(project).as_posix() for p in package.rglob("*") if p.is_file())
    rows = []
    try:
        git(project, ["read-tree", "--empty"], index=index)
        git(project, ["add", "--", ".gitattributes"], index=index)
        for offset in range(0, len(names), 60):
            git(project, ["add", "--", *names[offset:offset+60]], index=index)
        entries = git(project, ["ls-files", "-s", "-z"], index=index).decode().split("\0")
        entries = [(row.split("\t",1)[1],row.split("\t",1)[0].split()[1]) for row in entries if row]
        blobs = git(project, ["cat-file", "--batch"], index=index,
                    payload=("\n".join(oid for _,oid in entries)+"\n").encode())
        cursor = 0
        for name, oid in entries:
            end = blobs.index(b"\n",cursor)
            size = int(blobs[cursor:end].split()[2])
            value = blobs[end+1:end+1+size]
            cursor = end+size+2
            original = (project/name).read_bytes()
            if name == ".gitattributes":
                if value.replace(b"\r\n",b"\n") != original.replace(b"\r\n",b"\n"):
                    raise ValueError("Exported attributes differ beyond EOL")
            elif value != original:
                raise ValueError("Git alters evidence bytes: "+name)
            target = safe_path(output,name)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(value)
            rows.append(dict(path=name,oid=oid,bytes=size,sha256=hashlib.sha256(value).hexdigest(),exact_bytes=value==original))
        if cursor != len(blobs):
            raise ValueError("Trailing Git batch bytes")
        git(project,["diff","--cached","--check","--",package.relative_to(project).as_posix()],index=index)
    finally:
        if sha256(real_index(project)) != before:
            raise ValueError("User index changed during isolated export")
    return dict(passed=True, rows=rows, temporary_index=str(index),
        exported_package=str(output/package.relative_to(project)),
        user_index_unchanged=True,user_index_sha256=before,
        scope="exact package blobs reconstructed from isolated index; no commit/push")


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work",type=Path,required=True)
    p.add_argument("--data-root",type=Path,default=Path("D:/Backtesting"))
    p.add_argument("--package",type=Path)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if a.output.exists() or (a.package and a.output.resolve().is_relative_to(a.package.resolve())):
        raise ValueError("Audit output must be new and outside the package")
    root=Path(__file__).resolve().parents[1]
    result=dict(preservation=preserve(root,a.work.resolve(),a.data_root.resolve()))
    if a.package:
        result["export"]=export_bytes(root,a.package.resolve())
    write_json(a.output,result)
    print("Preservation and requested isolated export passed")

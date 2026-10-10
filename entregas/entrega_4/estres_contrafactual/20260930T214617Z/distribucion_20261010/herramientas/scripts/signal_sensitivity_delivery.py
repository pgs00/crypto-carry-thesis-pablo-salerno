"""Preservation and isolated Git-byte export checks for the new evidence only."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))
sys.path.insert(0, str(TOOLS_ROOT/"src"))

from crypto_carry.config import Config  # noqa: E402
from crypto_carry.data.replay import input_hashes  # noqa: E402
from scripts.return_capital.common import read_json, write_json  # noqa: E402
from scripts.signal_sensitivity import BASES  # noqa: E402
from scripts.signal_sensitivity_integrity import (  # noqa: E402
    reject_sealed_ancestor,
    validate_protocol,
)
from scripts.verify_rules_sensitivity_package import safe_path, sha256  # noqa: E402


def git(project, args, *, index=None, payload=None):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    if index is not None:
        env["GIT_INDEX_FILE"] = str(index)
    if args[0] in {"add", "read-tree"} and index is None:
        raise ValueError("Index mutation requires an explicit isolated index")
    result = subprocess.run(["git", *args], cwd=project, env=env, input=payload, capture_output=True)
    if result.returncode:
        raise ValueError("Git command failed: "+" ".join(args[:4])+"\n"+
                         (result.stdout+result.stderr).decode("utf-8", errors="replace"))
    return result.stdout


def real_index(project):
    path = Path(git(project, ["rev-parse", "--git-path", "index"]).decode().strip())
    return path if path.is_absolute() else project/path


def preserve(project, work, data_root):
    prior = read_json(work/"preservacion_previa.json")
    checked = []
    for name, expected in prior["tracked_files"].items():
        path = project/name
        if name == ".gitattributes":
            original = (work/"gitattributes_original.bin").read_bytes()
            addition = (work/"gitattributes_adicion.txt").read_bytes()
            if hashlib.sha256(original).hexdigest() != expected or path.read_bytes() != original+addition:
                raise ValueError("Attributes changed beyond the scoped evidence addition")
        elif sha256(path) != expected:
            raise ValueError("Previously tracked source changed: "+name)
        checked.append(name)
    if sha256(real_index(project)) != prior["index_sha256"]:
        raise ValueError("User index changed")
    if git(project, ["rev-parse", "HEAD"]).decode().strip() != prior["head"]:
        raise ValueError("HEAD changed")
    base_files = 0
    for item in read_json(work/"verificacion_base_previa.json")["runs"]:
        for name, expected in item["protected_files"].items():
            if sha256(Path(item["path"])/name) != expected:
                raise ValueError("Original BASE artifact changed: "+name)
            base_files += 1
    references = []
    for source in read_json(work/"autenticacion_referencias.json"):
        folder = Path(source["path"])
        manifest = folder/"manifiesto_paquete.json"
        digest = sha256(manifest)
        if digest != source["manifest_sha256"] or (folder/"manifiesto_paquete.sha256").read_text().split()[0] != digest:
            raise ValueError("Prior package manifest changed")
        archived = read_json(manifest)
        members = archived.get("members", archived.get("files"))
        if not isinstance(members, list):
            raise ValueError("Unrecognized prior package inventory schema")
        for row in members:
            path = safe_path(folder, row["path"])
            if sha256(path) != row["sha256"] or path.stat().st_size != row.get("bytes", row.get("size")):
                raise ValueError("Prior package member changed: "+str(path))
        references.append(dict(dependency=source["dependency"], manifest_sha256=digest, checked_files=len(members)))
    config = Config.load(data_root/"outputs"/BASES["conditional"]/"effective_config.toml")
    inputs = input_hashes(data_root, config)
    if inputs != read_json(work/"input_hashes.json"):
        raise ValueError("Original market inputs changed")
    validate_protocol(read_json(work/"protocolo_previo.json"), project, work)
    return dict(passed=True, tracked_files_checked=len(checked), scoped_attributes_only=True,
                original_base_files_checked=base_files, previous_packages=references,
                market_inputs_checked=len(inputs), user_index_sha256=sha256(real_index(project)),
                head=prior["head"], engine_and_frozen_runner_preserved=True)


def export_bytes(project, package):
    """Git mutations are confined to a fresh index; exported blobs remain inspectable."""
    package = package.resolve()
    if not package.is_relative_to(project/"entregas/entrega_4/senal_entradas") or not (package/"indice_corridas.json").is_file():
        raise ValueError("Export requires a new block-2 candidate inside the workspace")
    before = sha256(real_index(project))
    temporary = Path(tempfile.mkdtemp(prefix="senal_git_export_"))
    index, exported = temporary/"index", temporary/"checkout"
    exported.mkdir()
    files = [p for p in package.rglob("*") if p.is_file()]
    files += list((project/"scripts").glob("*signal_sensitivity*.py"))
    files += list((project/"tests/unit").glob("test_signal_sensitivity*.py"))
    files += list((project/"tests/integration").glob("test_signal_sensitivity*.py"))
    files += list((project/"configs/entrega_4/senal_entradas").rglob("*.toml"))
    names = sorted({p.relative_to(project).as_posix() for p in files})
    rows = []
    try:
        git(project, ["read-tree", "--empty"], index=index)
        git(project, ["add", "--", ".gitattributes"], index=index)
        for offset in range(0, len(names), 70):
            git(project, ["add", "--", *names[offset:offset+70]], index=index)
        entries = git(project, ["ls-files", "-s", "-z"], index=index).decode().split("\0")
        records = []
        for entry in filter(None, entries):
            metadata, name = entry.split("\t", 1)
            records.append((name, metadata.split()[1]))
        blobs = git(project, ["cat-file", "--batch"], index=index,
                    payload=("\n".join(oid for _, oid in records)+"\n").encode())
        cursor = 0
        for name, oid in records:
            end = blobs.index(b"\n", cursor)
            header = blobs[cursor:end].decode().split()
            size = int(header[2])
            value = blobs[end+1:end+1+size]
            cursor = end+size+2
            local = (project/name).read_bytes()
            if name == ".gitattributes":
                if value.replace(b"\r\n", b"\n") != local.replace(b"\r\n", b"\n"):
                    raise ValueError("Isolated attributes blob differs beyond EOL")
            elif value != local:
                raise ValueError("Git would alter evidence bytes: "+name)
            target = safe_path(exported, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value)
            rows.append(dict(path=name, oid=oid, bytes=size, sha256=hashlib.sha256(value).hexdigest(),
                             exact_bytes=value == local, attributes_eol_only=name == ".gitattributes"))
        if cursor != len(blobs):
            raise ValueError("Unexpected trailing batch output")
        attrs = git(project, ["check-attr", "--cached", "-z", "--stdin", "text"], index=index,
                    payload=("\0".join(names)+"\0").encode()).decode().split("\0")
        if any(attrs[i+2] != "unset" for i in range(0, len(attrs)-1, 3)):
            raise ValueError("Some evidence lacks -text protection")
        git(project, ["diff", "--cached", "--check", "--", package.relative_to(project).as_posix(),
                      "scripts", "tests", "configs/entrega_4/senal_entradas", ".gitattributes"], index=index)
    finally:
        if sha256(real_index(project)) != before:
            raise ValueError("User index changed during isolated export")
    return dict(passed=True, user_index_unchanged=True, user_index_sha256=before,
                temporary_index=str(index), exported_root=str(exported),
                exported_package=str(exported/package.relative_to(project)),
                new_files_with_exact_bytes=len(names), rows=rows,
                scope="Selected new package, new scripts/tests/configs; attributes authenticated allowing EOL only",
                publication="local isolated export only; no commit or push")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reject_sealed_ancestor(args.output)
    if args.output.exists() or args.output.resolve().is_relative_to(args.data_root.resolve()):
        raise ValueError("Delivery audit must be new and outside source data")
    if args.package and args.output.resolve().is_relative_to(args.package.resolve()):
        raise ValueError("Delivery audit must be outside the candidate")
    project = Path(__file__).resolve().parents[1]
    result = dict(preservation=preserve(project, args.work.resolve(), args.data_root.resolve()))
    if args.package:
        result["git_export"] = export_bytes(project, args.package.resolve())
    result["passed"] = True
    write_json(args.output, result)
    print("Preservation and requested export checks passed.")


if __name__ == "__main__":
    main()

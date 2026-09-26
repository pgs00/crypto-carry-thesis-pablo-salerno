"""Compare the original byte inventory and physical Git index without writing either."""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ALLOWED = {
    "scripts/report_historical_rules_sensitivity.py",
    "scripts/verify_rules_sensitivity_package.py",
    "tests/unit/test_rules_sensitivity_reporting.py",
    "docs/entrega_4/reglas_historicas/lectura_resultados.md",
}


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package", type=Path)
    args = parser.parse_args()
    audit = Path(__file__).resolve().parent
    initial = json.loads((audit / "estado_inicial.json").read_text(encoding="utf-8"))
    root = Path(initial["root"])
    if args.output.exists():
        raise FileExistsError("Preservation records are append-only")
    if args.package and args.output.resolve().is_relative_to(args.package.resolve()):
        raise ValueError("Output must be external to the sealed correction")
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")

    def git(*command):
        return subprocess.check_output(["git", "--no-optional-locks", *command], cwd=root,
                                       env=env).decode("utf-8").strip()

    changes, forbidden, missing = [], [], []
    groups = {"engine": 0, "configurations": 0, "e3": 0, "sealed_parent": 0}
    checked = []
    for record in initial["tracked_files"]:
        path = root / record["path"]
        if not path.is_file():
            missing.append(record["path"])
            continue
        actual = digest(path)
        unchanged = actual == record["sha256"] and path.stat().st_size == record["size"]
        checked.append(dict(path=record["path"], before_sha256=record["sha256"],
                            after_sha256=actual, unchanged=unchanged))
        if not unchanged:
            changes.append(record["path"])
            if record["path"] not in ALLOWED:
                forbidden.append(record["path"])
        for key, prefixes in {
            "engine": ("src/crypto_carry/",),
            "configurations": ("configs/",),
            "e3": ("Paquete de evidencia/", "entregas/entrega_3/"),
            "sealed_parent": ("entregas/entrega_4/reglas_historicas/20260925T005436Z/",),
        }.items():
            if record["path"].startswith(prefixes) and unchanged:
                groups[key] += 1
    index = Path(git("rev-parse", "--git-path", "index"))
    if not index.is_absolute():
        index = root / index
    index_hash = digest(index)
    head, branch = git("rev-parse", "HEAD"), git("branch", "--show-current")
    staged = git("diff", "--cached", "--name-status")
    passed = (not forbidden and not missing and index_hash == initial["index_sha256"]
              and head == initial["head"] and branch == initial["branch"] and not staged)
    record = dict(status="passed" if passed else "failed", checked_at=datetime.now(UTC).isoformat(),
                  tracked_files_checked=len(checked), unchanged_files=len(checked)-len(changes),
                  allowed_active_changes=changes, forbidden_changes=forbidden, missing_files=missing,
                  preserved_groups=groups, head_before=initial["head"], head_after=head,
                  branch_before=initial["branch"], branch_after=branch,
                  index_before_sha256=initial["index_sha256"], index_after_sha256=index_hash,
                  index_identical=index_hash == initial["index_sha256"], staged_changes=staged,
                  git_status=git("status", "--short"), byte_checks=checked)
    if args.package:
        record["correction_manifest_sha256"] = digest(args.package / "manifiesto_paquete.json")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({k: v for k, v in record.items() if k not in {"byte_checks", "git_status"}},
                     ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

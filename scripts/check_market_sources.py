"""Compare downloaded market files with the immutable inputs of BASE_E3."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

REFERENCE_COMMIT = "634c88fcf985da742cfa55d83bc4c0f99e082610"
REFERENCE_PATH = (
    "data/evidence/reglas_historicas/corridas/"
    "run_ad71d751b20623006c195ff3/source_manifests/download.json"
)
PROJECT = Path(__file__).resolve().parents[1]


def verify_sources(root, reference):
    """Hash raw observations and their supplements; ignore mutable local manifests."""
    root = Path(root).resolve()
    expected = {}
    if not reference.get("entries"):
        raise ValueError("Reference manifest is empty")
    for entry in reference["entries"]:
        for item in (entry, *entry.get("supplements", [])):
            pairs = [(item["path"], item["sha256"])]
            if item.get("checksum_path"):
                pairs.append((item["checksum_path"], item["checksum_file_sha256"]))
            for name, wanted in pairs:
                relative = PurePosixPath(name)
                path = (root / name).resolve()
                if (relative.is_absolute() or ".." in relative.parts
                        or "\\" in name or ":" in name or name != relative.as_posix()
                        or path == root or not path.is_relative_to(root)):
                    raise ValueError(f"Unsafe source path: {name}")
                if not re.fullmatch(r"[0-9a-f]{64}", wanted):
                    raise ValueError(f"Invalid reference SHA-256: {name}")
                if name in expected and expected[name] != wanted:
                    raise ValueError(f"Conflicting reference hashes: {name}")
                expected[name] = wanted
    failures = []
    for name, wanted in sorted(expected.items()):
        path = root / name
        if not path.is_file():
            failures.append({"path": name, "reason": "missing"})
            continue
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != wanted:
            failures.append({"path": name, "reason": "sha256_mismatch"})
    return {"checked_files": len(expected), "failures": failures}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        source = subprocess.run(
            ["git", "-C", str(PROJECT), "show", f"{REFERENCE_COMMIT}:{REFERENCE_PATH}"],
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
        result = verify_sources(args.data_root, json.loads(source.stdout))
        result["reference_commit"] = REFERENCE_COMMIT
        result["status"] = "passed" if not result["failures"] else "failed"
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "passed" else 1
    except subprocess.CalledProcessError:
        print(json.dumps({"status": "failed", "error": "Historical manifest unavailable",
                          "required_command": f"git fetch origin {REFERENCE_COMMIT}"}))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

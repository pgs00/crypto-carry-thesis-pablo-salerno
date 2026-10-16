"""Run the historical validator and bind its coverage to the prepared manifest."""

import argparse
import hashlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path


def validate(root, config_path):
    """Use the original checkout's Python environment; never download or backtest."""
    root = Path(root).resolve()
    config_path = root / config_path
    config = tomllib.loads(config_path.read_text())
    directory = root / config["data_dir"] / "manifests"
    manifest = directory / "processed.json"
    before = hashlib.sha256(manifest.read_bytes()).hexdigest()
    subprocess.run([
        sys.executable, "-m", "crypto_carry", "--root", str(root), "validate-data",
        "--config", str(config_path), "--scope", "full", "--skip-normalize",
    ], cwd=root, check=True)
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != before:
        raise ValueError("Prepared manifest changed during validation")
    path = directory / "coverage.json"
    quality = json.loads(path.read_text())
    if quality.get("status") != "complete" or quality.get("issues"):
        raise ValueError("Historical validation did not produce complete coverage")
    quality["processed_manifest_sha256"] = before
    path.write_text(json.dumps(quality, indent=2, sort_keys=True), encoding="utf-8")
    return {"coverage": str(path), "processed_manifest_sha256": before}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--config", default="configs/reglas_historicas/BASE_E3.toml")
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.root, args.config), indent=2))
        return 0
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    except (OSError, ValueError, KeyError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

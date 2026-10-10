"""New tool snapshots contain every dependency needed by the verifier CLI."""

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.distribution_integrity import sha256

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("builder,snapshot,verifier", [
    ("build_signal_sensitivity", "snapshot_tools", "verify_signal_sensitivity.py"),
    ("build_cost_capacity", "snapshot", "verify_cost_capacity.py"),
    ("build_execution_delays", "snapshot", "verify_execution_delays.py"),
])
def test_snapshot_has_portable_documentary_verifier(tmp_path, builder, snapshot, verifier):
    package = tmp_path / "new_snapshot"
    getattr(importlib.import_module("scripts." + builder), snapshot)(package)
    helper = package / "herramientas/scripts/distribution_integrity.py"
    assert helper.is_file(), "Documentary verifier dependency is absent from the portable snapshot"
    assert sha256(helper) == sha256(ROOT / "scripts/distribution_integrity.py")
    command = [sys.executable, "-I", "-B", "-X", "utf8",
               str(package / "herramientas/scripts" / verifier), "--help"]
    result = subprocess.run(command, cwd=tmp_path, env=dict(os.environ, PYTHONPATH=""),
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "--package" in result.stdout

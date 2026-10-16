"""Authenticate compact BASE evidence before economic exposure tests."""
import hashlib
import json
from pathlib import Path
import zipfile
import pytest

@pytest.fixture(scope="session")
def authenticated_e3():
    root = Path(__file__).resolve().parents[2]
    path = "data/evidence/carteras_continuas.zip"
    sources = json.loads((root / "data/evidence/thesis_baseline.json").read_text())["source_files"]
    expected = next(row["sha256"] for row in sources if row["path"] == path)
    assert hashlib.sha256((root / path).read_bytes()).hexdigest() == expected
    with zipfile.ZipFile(root / path) as archive:
        assert archive.testzip() is None
        return {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}

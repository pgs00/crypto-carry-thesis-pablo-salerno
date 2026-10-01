"""Long replay gates reject changed references, even after a prior preflight."""

import hashlib
import json

import pytest

from scripts.stress_counterfactual_contract import authenticated_references


@pytest.mark.parametrize("changed", ["original", "corrected"])
def test_reference_manifest_must_still_match_frozen_identity(tmp_path, changed):
    data, candidate = tmp_path / "data", tmp_path / "candidate"
    candidate.mkdir()
    original = data / "outputs/run_ad71d751b20623006c195ff3"
    corrected = tmp_path / "corrected"
    for directory in (original, corrected):
        directory.mkdir(parents=True)
        (directory / "run_manifest.json").write_text('{"fixture":"original"}', encoding="utf-8")
    sha = hashlib.sha256((original / "run_manifest.json").read_bytes()).hexdigest()
    refs = [dict(strategy="conditional", original_run_id=original.name,
                 corrected_control_run_id=corrected.name, original_manifest_sha256=sha,
                 control_manifest_sha256=sha, original_control_path=str(corrected))]
    (candidate / "indice_referencias.json").write_text(json.dumps(dict(references=refs)), encoding="utf-8")
    target = original if changed == "original" else corrected
    (target / "run_manifest.json").write_text('{"fixture":"changed"}', encoding="utf-8")
    # The old declared identity is retained; no test updates it to forgive tampering.
    assert hashlib.sha256((target / "run_manifest.json").read_bytes()).hexdigest() != sha
    with pytest.raises(ValueError, match="reference identity"):
        authenticated_references(candidate, data)

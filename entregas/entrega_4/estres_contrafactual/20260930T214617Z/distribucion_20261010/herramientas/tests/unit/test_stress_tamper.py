from pathlib import Path

import pytest


def test_negative_test_distinguishes_validation_rejection_from_execution_failure(monkeypatch):
    from scripts import check_stress_verifier_case as wrapper

    def bad_evidence(*args, **kwargs):
        raise ValueError("changed evidence")

    monkeypatch.setattr(wrapper, "verify", bad_evidence)
    result = wrapper.checked_verification(Path("fixture"))
    assert result["verifier_invoked"] and result["rejected"] and not result["passed"]
    assert result["reason"] == "changed evidence"

    def broken_import(*args, **kwargs):
        raise ImportError("missing dependency")

    monkeypatch.setattr(wrapper, "verify", broken_import)
    with pytest.raises(ImportError, match="dependency"):
        wrapper.checked_verification(Path("fixture"))


def test_negative_test_cannot_call_a_valid_package_rejected(monkeypatch):
    from scripts import check_stress_verifier_case as wrapper

    monkeypatch.setattr(wrapper, "verify", lambda *args, **kwargs: dict(passed=True, partial=False))
    result = wrapper.checked_verification(Path("fixture"))
    assert result["passed"] and not result["rejected"]

from pathlib import Path

import pytest

from scripts.signal_sensitivity_delivery import export_bytes, git
from scripts.verify_rules_sensitivity_package import sha256


def test_mutation_requires_explicit_isolated_index(tmp_path):
    with pytest.raises(ValueError, match="explicit isolated index"):
        git(tmp_path, ["add", "--", "file"])
    with pytest.raises(ValueError, match="explicit isolated index"):
        git(tmp_path, ["read-tree", "--empty"])


def test_export_preserves_crlf_binary_evidence_and_existing_index(tmp_path):
    project = tmp_path/"synthetic_repository"
    project.mkdir()
    git(project, ["init", "--quiet"])
    git(project, ["config", "core.autocrlf", "true"])
    marker = project/"unrelated.txt"
    marker.write_bytes(b"previously staged synthetic work\n")
    user_index = project/".git/index"
    git(project, ["add", "--", "unrelated.txt"], index=user_index)
    before = sha256(user_index)
    (project/".gitattributes").write_bytes(b"/entregas/entrega_4/senal_entradas/** -text whitespace=cr-at-eol\n")
    package = project/"entregas/entrega_4/senal_entradas/synthetic/paquete"
    package.mkdir(parents=True)
    evidence = {"indice_corridas.json": b'{"synthetic_test_only":true}\r\n',
                "decimal.csv": b"value\r\n0.0012300000000000001\r\n",
                "binary.bin": b"\x00\x80\xff\r\n\x00"}
    for name, data in evidence.items():
        (package/name).write_bytes(data)
    result = export_bytes(project, package)
    assert result["passed"] and result["user_index_unchanged"]
    assert sha256(user_index) == before
    assert result["new_files_with_exact_bytes"] == len(evidence)
    for name, data in evidence.items():
        assert (Path(result["exported_package"])/name).read_bytes() == data


def test_delivery_rejects_new_audit_file_inside_old_seal(tmp_path, monkeypatch):
    from scripts import signal_sensitivity_delivery as delivery

    sealed = tmp_path/"old_package"
    sealed.mkdir()
    (sealed/"manifiesto_paquete.json").write_text("{}", encoding="utf-8")
    target = sealed/"accidental_audit.json"
    monkeypatch.setattr("sys.argv", ["delivery", "--work", str(tmp_path/"work"),
                                    "--data-root", str(tmp_path/"data"), "--output", str(target)])
    with pytest.raises(ValueError, match="protected sealed"):
        delivery.main()
    assert not target.exists()

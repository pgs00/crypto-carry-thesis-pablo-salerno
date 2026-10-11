"""Tampering reaches B6 validators; no historical package copies or replays."""

import importlib.util
import json
import os
from pathlib import Path

import pytest


def verifier():
    assert importlib.util.find_spec("scripts.verify_stability_uncertainty"), "B6 verifier missing"
    from scripts import verify_stability_uncertainty

    return verify_stability_uncertainty


def test_seal_rejects_actual_changed_payload_extra_file_and_typed_size(tmp_path):
    api = verifier()
    payload = tmp_path / "input.csv"
    payload.write_text("day,return\n2024-01-01,0.01\n", encoding="utf-8")
    api.seal(tmp_path)
    assert api.verify_seal(tmp_path)["passed"]
    original = payload.read_bytes()
    payload.write_bytes(original.replace(b"0.01", b"0.99"))
    with pytest.raises(ValueError):
        api.verify_seal(tmp_path)
    payload.write_bytes(original)
    extra = tmp_path / "unexpected.txt"
    extra.write_text("unsealed", encoding="utf-8")
    with pytest.raises(ValueError):
        api.verify_seal(tmp_path)


def test_member_schema_rejects_string_bytes_and_traversal(tmp_path):
    api = verifier()
    path = tmp_path / "x.txt"
    path.write_text("x", encoding="utf-8")
    api.seal(tmp_path)
    manifest_path = tmp_path / "manifiesto_paquete.json"
    manifest = json.loads(manifest_path.read_text())
    for field, value in [("bytes", "1"), ("path", "../escape.txt")]:
        changed = json.loads(json.dumps(manifest))
        changed["members"][0][field] = value
        manifest_path.write_text(json.dumps(changed), encoding="utf-8")
        (tmp_path / "manifiesto_paquete.sha256").write_text(api.sha(manifest_path) + "\n")
        with pytest.raises(ValueError):
            api.verify_seal(tmp_path)


def test_bootstrap_protocol_rejects_boolean_seed_and_extra_replicas():
    api = verifier()
    valid = dict(
        method="paired_circular_calendar_year_contiguous_segments",
        main_block_days=28,
        sensitivity_block_days=[14, 56],
        replicas_per_length=5000,
        seed_root=20261001,
        bit_generator="PCG64",
        seed_sequence=True,
        quantile_method="linear",
        quantiles=[0.025, 0.975],
        batch_size=128,
        min_valid_fraction=0.95,
    )
    api.check_statistical_protocol(valid)
    for key, value in [("seed_root", True), ("replicas_per_length", 5001), ("main_block_days", 14)]:
        with pytest.raises(ValueError):
            api.check_statistical_protocol(dict(valid, **{key: value}))


@pytest.mark.parametrize(
    "script",
    [
        "stability_uncertainty_bootstrap.py",
        "stability_uncertainty_report.py",
        "stability_uncertainty_synthesis.py",
        "package_stability_uncertainty.py",
        "verify_stability_uncertainty.py",
    ],
)
def test_orphan_postprocessing_is_detected_before_resume(script):
    from scripts.coordinate_stability_uncertainty import existing_jobs

    orphan = dict(
        ProcessId=os.getpid() + 100000,
        ParentProcessId=0,
        CreationDate="/Date(1790892316898)/",
        CommandLine=f"python.exe scripts/{script} --candidate task",
    )
    assert existing_jobs([orphan]) == [orphan]


def test_passed_audit_cannot_turn_a_blocked_closure_into_success(tmp_path):
    from scripts.package_stability_uncertainty import finalize

    candidate = tmp_path / "candidato"
    candidate.mkdir()
    final = tmp_path / "paquete_final"
    final.mkdir()
    (final / "x.txt").write_text("evidence")
    verifier().seal(final)
    audit = tmp_path / "controles_finales"
    audit.mkdir()
    (audit / "verificacion_offline.json").write_text(
        json.dumps(
            dict(
                passed=True,
                sealed=dict(manifest_sha256=verifier().sha(final / "manifiesto_paquete.json")),
            )
        )
    )
    (tmp_path / "cierre_actual.json").write_text(json.dumps(dict(status="bloqueado", passed=False)))
    with pytest.raises(ValueError, match="closure"):
        finalize(candidate, Path("unused"))


def test_resume_rejects_a_passed_audit_for_another_seal(tmp_path):
    from scripts.package_stability_uncertainty import finalize

    candidate = tmp_path / "candidato"
    candidate.mkdir()
    final = tmp_path / "paquete_final"
    final.mkdir()
    (final / "x.txt").write_text("evidence")
    verifier().seal(final)
    audit = tmp_path / "controles_finales"
    audit.mkdir()
    (audit / "verificacion_offline.json").write_text(
        json.dumps(dict(passed=True, sealed=dict(manifest_sha256="wrong")))
    )
    (tmp_path / "cierre_actual.json").write_text(json.dumps(dict(status="completado", passed=True)))
    with pytest.raises(ValueError, match="audit"):
        finalize(candidate, Path("unused"))


def test_completed_delivery_resumes_without_market_inputs_or_new_offline_run(tmp_path):
    from scripts.package_stability_uncertainty import finalize

    candidate = tmp_path / "candidato"
    candidate.mkdir()
    final = tmp_path / "paquete_final"
    final.mkdir()
    (final / "x.txt").write_text("evidence")
    verifier().seal(final)
    digest = verifier().sha(final / "manifiesto_paquete.json")
    audit = tmp_path / "controles_finales"
    audit.mkdir()
    (audit / "verificacion_offline.json").write_text(
        json.dumps(dict(passed=True, sealed=dict(manifest_sha256=digest)))
    )
    expected = dict(status="completado", passed=True, manifest_sha256=digest)
    (tmp_path / "cierre_actual.json").write_text(json.dumps(expected))
    assert finalize(candidate, Path("nonexistent_market_data")) == expected


def test_export_keeps_dependency_lockfiles_and_excludes_runtime_locks(tmp_path):
    from scripts.package_stability_uncertainty import copy_final

    candidate = tmp_path / "candidate"
    files = {
        "herramientas/uv.lock": b"version = 1\n",
        "codigo_ejecutado/uv.lock": b"version = 1\n",
        "ejecuciones/I2023__conditional.lock": b"0",
        "tablas/metrics.csv": b"value\n0.01\n",
    }
    for name, payload in files.items():
        target = candidate / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    (candidate / "protocolo_ejecucion.json").write_text(
        json.dumps(dict(code_files={"uv.lock": verifier().sha(candidate / "herramientas/uv.lock")}))
    )
    final = tmp_path / "export"
    copy_final(candidate, final)
    for name in ("herramientas/uv.lock", "codigo_ejecutado/uv.lock", "tablas/metrics.csv"):
        assert (final / name).is_file(), f"Required evidence omitted: {name}"
        assert (final / name).read_bytes() == files[name]
    assert not (final / "ejecuciones/I2023__conditional.lock").exists()


def test_export_rejects_code_snapshot_that_differs_before_sealing(tmp_path):
    from scripts.package_stability_uncertainty import copy_final

    candidate = tmp_path / "candidate"
    for folder in ("herramientas", "codigo_ejecutado"):
        path = candidate / folder / "engine.py"
        path.parent.mkdir(parents=True)
        path.write_text("changed", encoding="utf-8")
    (candidate / "protocolo_ejecucion.json").write_text(
        json.dumps(dict(code_files={"engine.py": "0" * 64}))
    )
    with pytest.raises(ValueError, match="Exported code"):
        copy_final(candidate, tmp_path / "export")
    assert not (tmp_path / "export/manifiesto_paquete.json").exists()


def test_resume_uses_verified_replacement_without_touching_failed_seal(tmp_path):
    from scripts.package_stability_uncertainty import finalize

    candidate = tmp_path / "candidato"
    candidate.mkdir()
    failed = tmp_path / "paquete_final"
    failed.mkdir()
    (failed / "x.txt").write_text("failed attempt")
    verifier().seal(failed)
    old_bytes = (failed / "manifiesto_paquete.json").read_bytes()
    final = tmp_path / "paquete_final_verificado"
    final.mkdir()
    (final / "x.txt").write_text("complete evidence")
    verifier().seal(final)
    digest = verifier().sha(final / "manifiesto_paquete.json")
    audit = tmp_path / "controles_finales_corregidos"
    audit.mkdir()
    (audit / "verificacion_offline.json").write_text(
        json.dumps(dict(passed=True, sealed=dict(manifest_sha256=digest)))
    )
    expected = dict(
        status="completado",
        passed=True,
        manifest_sha256=digest,
        final_package=str(final),
        audit=str(audit),
    )
    (tmp_path / "cierre_actual.json").write_text(json.dumps(expected))
    assert finalize(candidate, Path("nonexistent_market_data")) == expected
    assert (failed / "manifiesto_paquete.json").read_bytes() == old_bytes

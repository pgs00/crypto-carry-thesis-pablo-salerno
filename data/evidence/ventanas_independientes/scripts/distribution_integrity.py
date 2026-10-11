"""Strict documentary derivation of authenticated packages; no economic changes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

DERIVATION = "procedencia/derivacion.json"
ORIGINAL = "procedencia/manifiesto_original.json"
ORIGINAL_SIDECAR = "procedencia/manifiesto_original.sha256"
COMMON_ADDED = {ORIGINAL, ORIGINAL_SIDECAR, "protocolo_distribucion.md",
                "herramientas/scripts/distribution_integrity.py"}

# Exact authorization boundary: none of these dispositions changes scientific data,
# configuration, frozen economic code, run identity, or numerical tolerances.
POLICIES = {
    '78cb03572c5940567852d0255d05a9f8a923f01df01fc0aa8b6cccef70f3b3bb': {"omitted": {'documentos/encargo_original.md', 'documentos/plan_ejecucion.md'}, "adapted": {'herramientas/scripts/verify_intraday_risk.py', "documentos/protocolo.md", 'README.md'}, "added": {'protocolo_distribucion.md', 'procedencia/manifiesto_original.json', 'procedencia/manifiesto_original.sha256', 'herramientas/scripts/distribution_integrity.py'}},
    '0163cf7622d929c06773700f50d13b2e808afee85a6cf85e48d45dcac03af12b': {"omitted": {'documentos/encargo_usuario.md', 'documentos/plan.md', 'documentos/progreso.md'}, "adapted": {'herramientas/scripts/return_capital/verification.py', "herramientas/scripts/return_capital/package.py", 'README.md'}, "added": {'protocolo_distribucion.md', 'procedencia/manifiesto_original.json', 'procedencia/manifiesto_original.sha256', 'herramientas/scripts/distribution_integrity.py'}},
    'd579bf84663986c7673db89d5f354d892b8efb896aa3bdf8ce309b17c8bee162': {"omitted": {'evidencia/procedencia/Prompt_Codex_Backtesting.md.txt', 'evidencia/procedencia/Prompt_Codex_Ajuste_Backtesting_1m.md.txt', 'evidencia/instructivo.md'}, "adapted": {'scripts/verificar_paquete.py', 'LEEME.md', 'evidencia/procedencia/methodology.md.txt', 'evidencia/procedencia/escenario_investigacion.md.txt', 'evidencia/procedencia/methodology_two_days_20260918.md.txt', 'evidencia/procedencia/historical_market_rules.md.txt', 'evidencia/procedencia/fees_followup_20260918.md.txt'}, "added": {'protocolo_distribucion.md', 'procedencia/manifiesto_original.json', 'procedencia/manifiesto_original.sha256', 'scripts/distribution_integrity.py'}},
    "f03624b6bdb40a3c9dfb31705a9c5c3552308200a953f9f5e80cce2137140095": {
        "omitted": {"documentos/encargo_usuario.md", "documentos/plan.md", "documentos/progreso.md"},
        "adapted": {"README.md", "documentos/protocolo.md", "herramientas/scripts/verify_signal_sensitivity.py",
                    "herramientas/scripts/signal_sensitivity_integrity.py"},
        "added": COMMON_ADDED,
    },
    "db68d839aa5837db72314b4f3de5509ecff283cc34d13a36e3c4f9d30298e1fb": {
        "omitted": {"documentos/encargo_usuario.md", "documentos/plan.md", "documentos/progreso.md"},
        "adapted": {"README.md", "documentos/protocolo.md", "reporte.md", "reporte.html",
                    "herramientas/scripts/verify_cost_capacity.py"},
        "added": COMMON_ADDED,
    },
    "88af2936e2dc243080abdf3909cc578c184778527eb847d6b021ce76d357335b": {
        "omitted": {"documentos/encargo_usuario.md", "documentos/plan.md", "documentos/progreso.md",
                    "documentos/controles/aprobacion_reparacion.md",
                    "documentos/controles/aprobacion_reparacion_transcripcion_utf8.md",
                    "documentos/controles/propuesta_reparacion_liquidacion.md",
                    "controles/aprobacion_reparacion.md",
                    "controles/aprobacion_reparacion_transcripcion_utf8.md",
                    "controles/propuesta_reparacion_liquidacion.md"},
        "adapted": {"README.md", "documentos/protocolo.md", "reporte.md", "reporte.html", "matriz_cumplimiento.md",
                    "herramientas/scripts/verify_execution_delays.py"},
        "added": COMMON_ADDED,
    },
    "091fe38bba57ad5be62275cabb03579b1c47f2d96784ed7c5e2ce6377467a8de": {
        "omitted": {"fuentes/encargo_bloque5.md", "plan_ejecucion.md", "continuacion_local.md",
                    "seguimiento_etapa_b.md", "progreso_local.json"},
        "adapted": {"README.md", "reproducibilidad.md", "aprobacion_recibida.json",
                    "herramientas/scripts/verify_stress_counterfactual.py",
                    "herramientas/scripts/stress_counterfactual_contract.py"},
        "added": COMMON_ADDED,
    },
    "8cca7f25e8d83f0e9b879574b1f06c77b8ca2a9aa6ae07fdd94baf80e73c829d": {
        "omitted": {"fuentes/encargo_b6.md", "plan_ejecucion.md", "continuacion_local.md"},
        "adapted": {"README.md", "herramientas/scripts/verify_stability_uncertainty.py"},
        "added": COMMON_ADDED,
    },
}


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def safe_path(root, name):
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or "\\" in name or ":" in name:
        raise ValueError("Unsafe distribution member: " + name)
    path = Path(root) / pure
    path.resolve().relative_to(Path(root).resolve())
    return path


def _rows(manifest):
    members = manifest.get("members", manifest.get("files", manifest.get("archivos")))
    if not isinstance(members, list):
        raise ValueError("Unsupported original manifest member schema")
    result = {}
    for row in members:
        name = row.get("path", row.get("archivo"))
        if name in result:
            raise ValueError("Duplicate original manifest member")
        result[name] = {"sha256": row["sha256"], "bytes": row.get("bytes", row.get("size"))}
    return result


def _indexed(rows):
    result = {row["path"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate distribution disposition")
    return result


def _load(package):
    package = Path(package).resolve()
    descriptor = read_json(package / DERIVATION)
    if descriptor["schema"] != "documentary_distribution_v1" or descriptor["distribution_id"] != "distribucion_20261010":
        raise ValueError("Unknown documentary distribution identity")
    original_sha = descriptor["original_manifest_sha256"]
    if original_sha not in POLICIES or sha256(package / ORIGINAL) != original_sha:
        raise ValueError("Unauthenticated original package identity")
    if (package / ORIGINAL_SIDECAR).read_text(encoding="ascii").split()[0] != original_sha:
        raise ValueError("Original manifest sidecar changed")
    members = _rows(read_json(package / ORIGINAL))
    groups = {key: _indexed(descriptor[key]) for key in ("omitted", "adapted", "added")}
    policy = POLICIES[original_sha]
    for key, rows in groups.items():
        if set(rows) != set(policy[key]):
            raise ValueError("Unauthorized documentary disposition: " + key)
        for name in rows:
            safe_path(package, name)
    if set(groups["added"]) & set(members):
        raise ValueError("Added member overwrites original evidence")
    for key in ("omitted", "adapted"):
        for name, row in groups[key].items():
            original = members.get(name)
            expected = {"sha256": row["sha256"], "bytes": row["bytes"]} if key == "omitted" else {
                "sha256": row["original_sha256"], "bytes": row["original_bytes"]}
            if original != expected:
                raise ValueError("Documentary disposition differs from original manifest: " + name)
    if original_sha == "091fe38bba57ad5be62275cabb03579b1c47f2d96784ed7c5e2ce6377467a8de":
        # Pin every original approval field except the removed conversation text.
        # This projection comes from the original manifest-authenticated record.
        approval = read_json(package / "aprobacion_recibida.json")
        if "user_response" in approval:
            raise ValueError("Conversational approval text is not part of this distribution")
        description = approval.pop("alcance_tecnico", None)
        if not isinstance(description, str) or not description.strip():
            raise ValueError("Missing descriptive technical approval scope")
        projection = json.dumps(
            approval, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        if hashlib.sha256(projection).hexdigest() != (
            "1395fe49b39408fbeadeb25b2b5a6ab9e7556ef2f910abadf8cd2c5ec2b9914e"
        ):
            raise ValueError("Original approved scope changed in documentary record")
    return descriptor, members, groups


def _check(path, row):
    if not path.is_file() or path.stat().st_size != row["bytes"] or sha256(path) != row["sha256"]:
        raise ValueError("Distribution member changed: " + str(path))


def verify_distribution(package):
    """Authenticate the exact allowed derivation, or return None for a legacy package."""
    package = Path(package).resolve()
    if not (package / DERIVATION).is_file():
        return None
    current_manifest = package / "manifiesto_paquete.json"
    current_sha = sha256(current_manifest)
    sidecar = (package / "manifiesto_paquete.sha256").read_text(encoding="ascii").split()
    if not sidecar or sidecar[0] != current_sha:
        raise ValueError("Current distribution manifest sidecar mismatch")
    current_members = _rows(read_json(current_manifest))
    current_seals = {"manifiesto_paquete.json", "manifiesto_paquete.sha256"}
    if set(current_members) & current_seals:
        raise ValueError("Self-referential distribution manifest")
    for name, row in current_members.items():
        _check(safe_path(package, name), row)
    actual_members = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    if actual_members != set(current_members) | current_seals:
        raise ValueError("Current distribution manifest membership differs")
    descriptor, members, groups = _load(package)
    omitted, adapted, added = (groups[key] for key in ("omitted", "adapted", "added"))
    for name, original in members.items():
        path = safe_path(package, name)
        if name in omitted:
            if path.exists():
                raise ValueError("Omitted operational document is present: " + name)
            continue
        _check(path, adapted.get(name, original))
    for name, row in added.items():
        _check(safe_path(package, name), row)
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    expected = (set(members) - set(omitted)) | set(added) | {
        DERIVATION, "manifiesto_paquete.json", "manifiesto_paquete.sha256"}
    if actual != expected:
        raise ValueError("Unexpected distribution file population")
    return {"distribution_id": descriptor["distribution_id"],
            "manifest_sha256": current_sha,
            "original_manifest_sha256": descriptor["original_manifest_sha256"],
            "preserved_members": len(members) - len(omitted) - len(adapted),
            "omitted_documents": len(omitted), "adapted_packaging_members": len(adapted)}


def verify_frozen_document(package, name, expected_hash):
    """Accept only exact bytes or a pinned documentary omission/adaptation."""
    package = Path(package).resolve()
    path = safe_path(package, name)
    if not (package / DERIVATION).is_file():
        if sha256(path) != expected_hash:
            raise ValueError("Frozen protocol input changed: " + name)
        return True
    _, members, groups = _load(package)
    if name not in members or members[name]["sha256"] != expected_hash:
        raise ValueError("Frozen protocol differs from original authenticated member: " + name)
    if name in groups["omitted"]:
        if path.exists():
            raise ValueError("Omitted operational document is present: " + name)
    else:
        _check(path, groups["adapted"].get(name, members[name]))
    return True


def original_manifest_path(package):
    """Resolve the original scientific reference after authenticating its distribution."""
    package = Path(package).resolve()
    if verify_distribution(package) is not None:
        return package / ORIGINAL
    return package / "manifiesto_paquete.json"

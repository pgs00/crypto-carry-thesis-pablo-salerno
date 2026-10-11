"""Verify the new postprocessing, without repeating earlier carry diagnostics."""

import argparse
import json
from pathlib import Path

from scripts.return_capital.common import read_csv, read_json, sha256, write_json

from .calculation import COPY_TABLES, PREVIOUS_HASH, derive
from .integrity import check_manifest, new_destination, same_rows
from .report import verify_report


def verify(package, previous=None):
    package = Path(package).resolve()
    manifest = check_manifest(package)
    tables, audit = derive(
        package / "fuentes_publicas", package / "documentos", package / "reutilizado"
    )
    actual = {p.stem: read_csv(p) for p in (package / "tablas").glob("*.csv")}
    if set(actual) != set(tables):
        raise ValueError("Table inventory differs from calculation")
    for name, expected in tables.items():
        same_rows(actual[name], expected, "recomputed " + name)
    if read_json(package / "verificacion_construccion.json") != audit:
        raise ValueError("Construction audit differs from checks")
    dependency = read_json(package / "dependencia_previa.json")
    if dependency["manifest_sha256"] != PREVIOUS_HASH:
        raise ValueError("Wrong predecessor in dependency record")
    expected_copies = [
        dict(
            previous_path="tablas/" + name,
            package_path="reutilizado/" + name,
            bytes=(package / "reutilizado" / name).stat().st_size,
            sha256=sha256(package / "reutilizado" / name),
        )
        for name in COPY_TABLES
    ]
    same_rows(dependency["copies"], expected_copies, "dependency inventory")
    verify_report(package, tables, audit, same_rows)
    if previous is not None:
        previous = Path(previous).resolve()
        check_manifest(previous)
        from scripts.distribution_integrity import verify_distribution
        distribution = verify_distribution(previous)
        previous_identity = previous / ("procedencia/manifiesto_original.json" if distribution else "manifiesto_paquete.json")
        if sha256(previous_identity) != PREVIOUS_HASH:
            raise ValueError("Explicit predecessor is not the approved seal")
        for name in COPY_TABLES:
            if sha256(previous / "tablas" / name) != sha256(package / "reutilizado" / name):
                raise ValueError("Explicit predecessor copy mismatch")
    return dict(
        **audit,
        scope="with_previous" if previous else "compact",
        manifest_sha256=sha256(package / "manifiesto_paquete.json"),
        members=len(manifest["members"]),
        previous_manifest_sha256=PREVIOUS_HASH,
        previous_entire_seal_checked=previous is not None and not bool(distribution),
        previous_distribution_checked=bool(distribution) if previous is not None else False,
        previous_distribution_manifest_sha256=sha256(previous / "manifiesto_paquete.json") if previous is not None and distribution else None,
        sources_read_only=True,
        network_used=False,
        limits="Shared SOFR postprocessing plus external Index checks; prior engine and diagnostics not rerun",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = None
    if args.output:
        output = new_destination(
            args.output, [args.package] + ([args.previous] if args.previous else [])
        )
    result = verify(args.package, args.previous)
    if output:
        write_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))

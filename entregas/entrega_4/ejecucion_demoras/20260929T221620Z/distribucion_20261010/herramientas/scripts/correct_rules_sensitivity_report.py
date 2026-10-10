"""Build a new, sealed exposure/H2 correction from twelve preserved portfolios.

This module reads persisted artifacts only. It never imports the economic engine.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path

if __package__:
    from . import verify_rules_sensitivity_package as legacy
    from .rules_sensitivity_h2 import h2_comparison
else:
    import verify_rules_sensitivity_package as legacy
    from rules_sensitivity_h2 import h2_comparison

SCHEMA = "rules_sensitivity_correction_v2"
VERSION = "exposure_h2_v2"
IDENTITY = ("scenario", "strategy", "run_id", "period")
OLD_EXPOSURE = {
    "invested_seconds",
    "unhedged_seconds",
    "covered_seconds",
    "both_covered_seconds",
    "cash_seconds",
    "calendar_seconds",
    "invested_fraction",
}
PRESERVED_TABLES = (
    "diario_carteras",
    "componentes_por_activo_periodo",
    "conciliaciones",
    "h1_invariancia",
    "h1_resumen",
    "h3_diario",
    "h3_invariancia",
    "h3_regimen",
    "registro_corridas",
    "eventos_periodo",
    "fronteras_promocion",
)
TOOLS = (
    "correct_rules_sensitivity_report.py",
    "rules_sensitivity_correction_docs.py",
    "rules_sensitivity_exposure.py",
    "rules_sensitivity_h2.py",
    "verify_rules_sensitivity_package.py",
    "verify_rules_sensitivity_correction.py",
)


def validate_destination(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("Destination cannot be inside or contain the sealed source parent")
    if destination.exists():
        raise FileExistsError(f"Destination must be new: {destination}")
    for ancestor in destination.parents:
        if any(
            (ancestor / name).is_file() for name in ("manifiesto_paquete.json", "manifest.sha256")
        ):
            raise ValueError(f"Destination would write inside sealed evidence: {ancestor}")
    return source, destination


def indexed(rows, keys=IDENTITY):
    result = {}
    for row in rows:
        key = tuple(row[name] for name in keys)
        if key in result:
            raise ValueError(f"Duplicate row identity: {key}")
        result[key] = row
    return result


def exposure_field(name):
    return name in OLD_EXPOSURE or name.endswith("_seconds") or name.endswith("_fraction")


def correct_metrics(original, exposure):
    indexed(original)
    lookup = indexed([row for row in exposure if row["symbol"] == "PORTFOLIO"])
    output = []
    for row in original:
        key = tuple(row[name] for name in IDENTITY)
        if key not in lookup:
            raise ValueError(f"Missing portfolio exposure: {key}")
        changes = {name: value for name, value in lookup[key].items() if exposure_field(name)}
        output.append(dict(row, **changes))
    if set(lookup) != set(indexed(original)):
        raise ValueError("Unexpected portfolio exposure identity")
    return output


def correct_deltas(original, metrics):
    lookup = indexed(metrics, ("scenario", "strategy", "period"))
    output = []
    seen = set()
    for old in original:
        row = dict(old)
        scenario, strategy, period, metric = (
            row[k] for k in ("scenario", "strategy", "period", "metric")
        )
        key = scenario, strategy, period, metric
        if key in seen:
            raise ValueError(f"Duplicate delta: {key}")
        seen.add(key)
        if metric in OLD_EXPOSURE:
            current = lookup[(scenario, strategy, period)][metric]
            prior = lookup[(row["comparator"], strategy, period)][metric]
            row.update(
                value=current,
                comparator_value=prior,
                delta=D(str(current)) - D(str(prior)),
                reason="",
            )
        output.append(row)
    for row in metrics:
        comparator = legacy.COMPARATORS[row["scenario"]]
        if comparator is None:
            continue
        prior = lookup[(comparator, row["strategy"], row["period"])]
        for name in row:
            if exposure_field(name) and name not in OLD_EXPOSURE:
                output.append(
                    dict(
                        scenario=row["scenario"],
                        comparator=comparator,
                        strategy=row["strategy"],
                        period=row["period"],
                        run_id=row["run_id"],
                        comparator_run_id=prior["run_id"],
                        metric=name,
                        value=row[name],
                        comparator_value=prior[name],
                        delta=D(str(row[name])) - D(str(prior[name])),
                        reason="",
                    )
                )
    return output


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = fields or list(dict.fromkeys(key for row in rows for key in row))
    if not columns:
        raise ValueError(f"Cannot write a table without columns: {path}")
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        handle.write("\n")


def file_record(root, path):
    return dict(
        path=path.relative_to(root).as_posix(), size=path.stat().st_size, sha256=legacy.sha256(path)
    )


def before_after(original, corrected, old_h2, new_h2):
    old_lookup = indexed(original)
    h2_old = indexed(old_h2, ("scenario", "period"))
    h2_new = indexed(new_h2, ("scenario", "period"))
    rows = []
    for row in corrected:
        old = old_lookup[tuple(row[k] for k in IDENTITY)]
        hkey = row["scenario"], row["period"]
        result = {k: row[k] for k in (*IDENTITY, "start_utc", "end_exclusive_utc")}
        result.update(
            {
                "old_" + k: old[k]
                for k in ("invested_seconds", "unhedged_seconds", "invested_fraction")
            }
        )
        result.update(
            {
                k: row[k]
                for k in (
                    "raw_invested_seconds",
                    "raw_unhedged_seconds",
                    "raw_invested_fraction",
                    "invested_seconds",
                    "unhedged_seconds",
                    "covered_seconds",
                    "dust_seconds",
                    "dust_only_seconds",
                    "no_active_seconds",
                    "no_inventory_seconds",
                    "calendar_seconds",
                    "invested_fraction",
                )
            }
        )
        result.update(
            delta_invested_seconds=D(str(row["invested_seconds"])) - D(old["invested_seconds"]),
            delta_unhedged_seconds=D(str(row["unhedged_seconds"])) - D(old["unhedged_seconds"]),
            h2_before=h2_old[hkey]["verdict"],
            h2_after=h2_new[hkey]["verdict"],
            h2_changed=h2_old[hkey]["verdict"] != h2_new[hkey]["verdict"],
        )
        rows.append(result)
    return rows


def financial_preservation(original, corrected):
    lookup = indexed(corrected)
    output = []
    for row in original:
        new = lookup[tuple(row[k] for k in IDENTITY)]
        for name, value in row.items():
            if name not in OLD_EXPOSURE:
                if value != new[name]:
                    raise ValueError(f"Financial/identity value changed: {row['run_id']} {name}")
                output.append(
                    dict(
                        **{key: row[key] for key in IDENTITY},
                        metric=name,
                        value_before=value,
                        value_after=new[name],
                        unchanged=True,
                    )
                )
    return output


def copy_reference(reference, destination):
    """Copy only authenticated E3 editorial reference files, without modifying originals."""
    reference = Path(reference).resolve()
    manifest_path = reference / "manifest.json"
    if legacy.sha256(manifest_path) != (reference / "manifest.sha256").read_text().strip():
        raise ValueError("E3 manifest checksum differs")
    manifest = legacy.read_json(manifest_path)
    names = (
        "tablas/exposicion_intervalos.csv",
        "tablas/tiempo_invertido.csv",
        "tablas/episodio_2023_03_24_exposicion.csv",
        "codigo/scripts/continuous_delivery/portfolio.py",
        "codigo/scripts/continuous_delivery/common.py",
        "codigo/scripts/continuous_delivery/build.py",
        "codigo/src/crypto_carry/strategy.py",
        "codigo/src/crypto_carry/reporting.py",
    )
    records = []
    for name in (*names, "manifest.json", "manifest.sha256"):
        source = legacy.safe_path(reference, name)
        if name in names and legacy.sha256(source) != manifest["file_hashes"][name]:
            raise ValueError(f"E3 reference differs: {name}")
        target = destination / "referencia_e3" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        records.append(file_record(reference, source))
    return records


def compare_e3_reference(intervals, summaries, destination):
    old_intervals = legacy.read_csv(destination / "referencia_e3/tablas/exposicion_intervalos.csv")
    old_summary = legacy.read_csv(destination / "referencia_e3/tablas/tiempo_invertido.csv")
    checks = []
    for strategy in ("conditional", "permanent"):
        actual = [r for r in intervals if r["scenario"] == "BASE_E3" and r["strategy"] == strategy]
        expected = [r for r in old_intervals if r["strategy"] == strategy]
        if len(actual) != len(expected):
            raise ValueError("E3 interval count differs")
        for left, right in zip(actual, expected):
            if left["run_id"] != right["source_run_id"]:
                raise ValueError("E3 source run identity differs")
            for key, value in right.items():
                if key in {"scenario", "run_id", "source_run_id", "strategy"}:
                    continue
                if str(left[key]) != value:
                    raise ValueError(f"E3 exact interval differs: {strategy} {key}")
        checked = 0
        for old in [r for r in old_summary if r["strategy"] == strategy]:
            period = "2024+" if old["period"] == "2024-2026-08" else old["period"]
            new = next(
                r
                for r in summaries
                if r["scenario"] == "BASE_E3"
                and r["strategy"] == strategy
                and r["period"] == period
                and r["symbol"] == old["symbol"]
            )
            if new["run_id"] != old["source_run_id"]:
                raise ValueError("E3 summary source run identity differs")
            mapping = {
                "cash_or_dust_seconds": "no_active_seconds",
                "flat_seconds": "no_inventory_seconds",
                "any_covered_seconds": "covered_seconds",
                "any_unhedged_seconds": "unhedged_seconds",
            }
            for key, value in old.items():
                target = mapping.get(key, key)
                if (
                    key in {"scenario", "run_id", "source_run_id", "strategy", "period", "symbol"}
                    or value == ""
                ):
                    continue
                if target in new and D(str(new[target])) != D(value):
                    raise ValueError(f"E3 exact summary differs: {strategy} {period} {key}")
            checked += 1
        checks.append(
            dict(
                strategy=strategy,
                intervals_checked=len(actual),
                summaries_checked=checked,
                exact=True,
                terminal_difference_ns=0,
            )
        )
    return checks


def exposure_figure(rows, destination):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    full = [row for row in rows if row["period"] == "full"]
    labels = [
        row["scenario"] + " / " + ("C" if row["strategy"] == "conditional" else "P") for row in full
    ]
    fig, axes = plt.subplots(1, 3, figsize=(16, 7), layout="constrained", sharey=True)
    y = list(range(len(full)))
    axes[0].barh(
        [v + 0.19 for v in y],
        [float(r["raw_invested_fraction"]) * 100 for r in full],
        height=0.36,
        color="#96a6b5",
        label="Bruto, incluye polvo",
    )
    axes[0].barh(
        [v - 0.19 for v in y],
        [float(r["invested_fraction"]) * 100 for r in full],
        height=0.36,
        color="#167d8d",
        label="Posiciones activas, E3",
    )
    axes[0].set(title="Tiempo invertido", xlabel="% del calendario")
    for ax, field, title, scale, unit, color in (
        (
            axes[1],
            "raw_unhedged_seconds",
            "Sin cobertura · bruto",
            1 / 86400,
            "Días, incluye polvo",
            "#96a6b5",
        ),
        (
            axes[2],
            "unhedged_seconds",
            "Sin cobertura · activo",
            1 / 3600,
            "Horas, excluye polvo",
            "#167d8d",
        ),
    ):
        values = [float(r[field]) * scale for r in full]
        bars = ax.barh(y, values, height=0.56, color=color)
        ax.bar_label(bars, labels=[f"{v:.2f}" for v in values], padding=3, fontsize=8)
        ax.set(title=title, xlabel=unit, xlim=(0, max(values) * 1.16))
    for ax in axes:
        ax.grid(axis="x", alpha=0.15)
    axes[0].set_yticks(y, labels, fontsize=8)
    axes[0].invert_yaxis()
    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="outside lower center", ncol=2, fontsize=9)
    fig.suptitle(
        "Corrección editorial · mismas doce carteras · muestra completa\n"
        "C: condicional · P: permanente · las dos vistas sin cobertura usan distintas unidades",
        fontsize=12,
    )
    for extension in ("png", "svg"):
        fig.savefig(destination / ("comparacion/figuras/exposicion." + extension), dpi=180)
    plt.close(fig)


def build_correction(source_package, destination, e3_reference, *, figures=True):
    import pyarrow.parquet as pq

    if __package__:
        from .rules_sensitivity_correction_docs import write_documents
        from .rules_sensitivity_exposure import exposure_intervals, exposure_summary
    else:
        from rules_sensitivity_correction_docs import write_documents
        from rules_sensitivity_exposure import exposure_intervals, exposure_summary

    parent, target = validate_destination(source_package, destination)
    reference = Path(e3_reference).resolve()
    if target.is_relative_to(reference) or reference.is_relative_to(target):
        raise ValueError("Destination cannot replace or enter the E3 reference")
    if legacy.read_json(parent / legacy.MANIFEST)["schema"] != "rules_sensitivity_package_v1":
        raise ValueError("Expected the preserved original v1 source package")
    parent_check = legacy.verify_package(parent)
    items = legacy.load_index(parent)
    if len(items) != 12 or any(item["status"] not in legacy.SUCCESS for item in items):
        raise ValueError("This correction requires the twelve existing successful portfolios")
    parent_manifest_sha = legacy.sha256(parent / legacy.MANIFEST)
    original = legacy.read_csv(parent / "comparacion/metricas_cartera_periodo.csv")
    old_h2 = legacy.read_csv(parent / "comparacion/h2.csv")
    intervals, summaries, episode, run_provenance = [], [], [], []
    for item in items:
        run = legacy.safe_path(parent, item["path"])
        manifest = legacy.read_json(run / "run_manifest.json")
        config = manifest["config"]
        common = {key: item[key] for key in ("scenario", "strategy", "run_id")}
        positions = pq.ParquetFile(run / "positions.parquet").read().to_pylist()
        complete = exposure_intervals(
            positions,
            legacy.timestamp(config["start"]),
            legacy.timestamp(config["end"]),
            D(config["hedge_tolerance"]),
        )
        intervals.extend(dict(common, **row) for row in complete)
        summaries.extend(
            dict(common, **row) for row in exposure_summary(complete, legacy.periods(config))
        )
        if item["scenario"] == "BASE_E3":
            episode.extend(
                dict(common, **row)
                for row in exposure_summary(
                    complete,
                    [
                        (
                            "2023-03-24",
                            legacy.timestamp("2023-03-24T00:00:00Z"),
                            legacy.timestamp("2023-03-25T00:00:00Z"),
                        )
                    ],
                )
            )
        run_provenance.append(
            dict(
                common,
                status=item["status"],
                engine_status=item["engine_status"],
                engine_code_hash=manifest.get("code_hash"),
                run_manifest_sha256=item["manifest_sha256"],
                positions_rows=len(positions),
                postprocessor_version=VERSION,
            )
        )
    corrected = correct_metrics(original, summaries)
    h2 = h2_comparison(corrected)
    differences = before_after(original, corrected, old_h2, h2)
    preserved_values = financial_preservation(original, corrected)
    # The first write happens after source integrity and trajectory validation.
    target.mkdir(parents=True, exist_ok=False)
    reference_files = copy_reference(e3_reference, target)
    e3_checks = compare_e3_reference(intervals, summaries, target)
    shutil.copyfile(parent / "indice_corridas.json", target / "indice_corridas.json")
    preserved = [
        dict(
            path="indice_corridas.json",
            parent_sha256=legacy.sha256(parent / "indice_corridas.json"),
            corrected_sha256=legacy.sha256(target / "indice_corridas.json"),
            equal_bytes=True,
        )
    ]
    for name in PRESERVED_TABLES:
        relative = "comparacion/" + name + ".csv"
        new = target / relative
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(parent / relative, new)
        preserved.append(
            dict(
                path=relative,
                parent_sha256=legacy.sha256(parent / relative),
                corrected_sha256=legacy.sha256(new),
                equal_bytes=True,
            )
        )
    for source in sorted((parent / "comparacion/figuras").glob("*")):
        if source.is_file():
            new = target / "comparacion/figuras" / source.name
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, new)
    old_lookup = indexed(old_h2, ("scenario", "period"))
    h2_changes = [
        dict(
            **{
                key: row[key]
                for key in ("scenario", "period", "conditional_run_id", "permanent_run_id")
            },
            verdict_before=old_lookup[(row["scenario"], row["period"])]["verdict"],
            verdict_after=row["verdict"],
            changed=old_lookup[(row["scenario"], row["period"])]["verdict"] != row["verdict"],
        )
        for row in h2
    ]
    tables = dict(
        metricas_cartera_periodo=corrected,
        h2=h2,
        exposicion_intervalos=intervals,
        exposicion_periodo=summaries,
        antes_despues=differences,
        h2_cambios=h2_changes,
        preservacion_financiera=preserved_values,
        preservacion_tablas=preserved,
        episodio_2023_03_24=episode,
        procedencia_corridas=run_provenance,
        deltas=correct_deltas(legacy.read_csv(parent / "comparacion/deltas.csv"), corrected),
    )
    for name, rows in tables.items():
        write_csv(target / ("comparacion/" + name + ".csv"), rows)
    write_csv(
        target / "comparacion/figuras/exposicion_datos.csv",
        [row for row in differences if row["period"] == "full"],
    )
    if figures:
        exposure_figure(differences, target)
    write_json(
        target / "verificacion_construccion.json",
        dict(
            parent_original_scope=parent_check,
            base_e3_equivalence=e3_checks,
            financial_values_unchanged=len(preserved_values),
            preserved_tables=len(preserved),
            h2_counts=Counter(row["verdict"] for row in h2),
            h2_verdicts_changed=sum(r["changed"] for r in h2_changes),
            engine_reexecution=False,
            sources_read_only=True,
        ),
    )
    write_documents(target, tables, parent_manifest_sha, e3_checks, figures)
    tool_folder = Path(__file__).resolve().parent
    for name in TOOLS:
        output = target / "herramientas" / name
        output.parent.mkdir(exist_ok=True)
        shutil.copyfile(tool_folder / name, output)
    test_names = (
        "test_rules_sensitivity_h2.py",
        "test_rules_sensitivity_exposure.py",
        "test_rules_sensitivity_correction_builder.py",
        "test_rules_sensitivity_correction_verifier.py",
    )
    source_tests = tool_folder.parent / "tests/unit"
    if not source_tests.is_dir():
        source_tests = tool_folder.parent / "pruebas"
    for name in test_names:
        output = target / "pruebas" / name
        output.parent.mkdir(exist_ok=True)
        shutil.copyfile(source_tests / name, output)
    parent_manifest = legacy.read_json(parent / legacy.MANIFEST)
    sources = list(parent_manifest["members"])
    sources.extend(
        file_record(parent, parent / name) for name in (legacy.MANIFEST, legacy.MANIFEST_SIDECAR)
    )
    provenance = dict(
        schema=SCHEMA,
        created_at=datetime.now(UTC).isoformat(),
        parent_manifest_sha256=parent_manifest_sha,
        parent_schema="rules_sensitivity_package_v1",
        parent_argument_required=True,
        parent_paths="relative to the explicit --parent argument",
        source_files=sources,
        e3_reference_files=reference_files,
        postprocessor_version=VERSION,
        postprocessor_files=[file_record(target, target / "herramientas" / name) for name in TOOLS],
        runs=run_provenance,
        financial_inputs="unchanged persisted parent artifacts",
        original_economic_code="run_manifest.code_hash and preserved parent snapshots",
        engine_reexecution=False,
        current_git_publication="not asserted; new local correction",
    )
    write_json(target / "procedencia.json", provenance)
    seal_correction(target, parent_manifest_sha)
    return dict(
        status="built_and_sealed_not_yet_independently_verified",
        package=str(target),
        parent_manifest_sha256=parent_manifest_sha,
        runs=len(items),
        intervals=len(intervals),
        summaries=len(summaries),
        h2=len(h2),
        engine_reexecution=False,
    )


def seal_correction(target, parent_manifest_sha):
    if (target / legacy.MANIFEST).exists() or (target / legacy.MANIFEST_SIDECAR).exists():
        raise FileExistsError("Cannot reseal an existing correction")
    members = [file_record(target, path) for path in sorted(target.rglob("*")) if path.is_file()]
    write_json(
        target / legacy.MANIFEST,
        dict(
            schema=SCHEMA,
            created_at=datetime.now(UTC).isoformat(),
            postprocessor_version=VERSION,
            parent_manifest_sha256=parent_manifest_sha,
            members=members,
            excludes=[legacy.MANIFEST, legacy.MANIFEST_SIDECAR],
        ),
    )
    with (target / legacy.MANIFEST_SIDECAR).open("x", encoding="ascii") as handle:
        handle.write(legacy.sha256(target / legacy.MANIFEST) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-package", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--e3-reference", type=Path, required=True)
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args(argv)
    result = build_correction(
        args.source_package, args.destination, args.e3_reference, figures=not args.no_figures
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

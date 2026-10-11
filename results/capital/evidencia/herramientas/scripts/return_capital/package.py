"""Create a new portable, sealed derivative; no input may be overwritten."""

import argparse
import platform
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .common import RUNS, read_csv, read_json, sha256, write_csv, write_json
from .report import write_report
from .tables import derive
from .verification import check_tables, new_destination, same_rows

COMPARISON_FILES = (
    "metricas_cartera_periodo",
    "diario_carteras",
    "h1_resumen",
    "h1_invariancia",
    "h2",
    "h3_regimen",
    "h3_invariancia",
    "componentes_por_activo_periodo",
    "exposicion_periodo",
    "eventos_periodo",
)


def source_inventory(dependencies):
    files = {key: [] for key in dependencies}
    for key in ("parent", "correction", "intraday"):
        files[key] += ["manifiesto_paquete.json", "manifiesto_paquete.sha256"]
    files["parent"].append("indice_corridas.json")
    for run in RUNS.values():
        files["parent"] += [
            f"corridas/{run}/{name}"
            for name in (
                "run_manifest.json",
                "run_manifest.sha256",
                "effective_config.toml",
                "ledger.parquet",
                "fills.parquet",
                "risk_events.parquet",
                "orders.parquet",
                "signals.parquet",
                "renewal_diagnostics.parquet",
                "positions.parquet",
                "equity_daily.csv",
            )
        ]
    files["correction"] += ["comparacion/" + name + ".csv" for name in COMPARISON_FILES]
    files["intraday"].append("evidencia/eventos_financieros.parquet")
    files["e3"] += [
        "manifest.json",
        "manifest.sha256",
        "tablas/ciclos.csv",
        "codigo/scripts/continuous_delivery/portfolio.py",
        "codigo/src/crypto_carry/diagnostics.py",
        "codigo/src/crypto_carry/ledger.py",
        "codigo/src/crypto_carry/strategy.py",
    ]
    result, schemas = [], []
    for key, names in files.items():
        root = dependencies[key]
        manifest_name = "manifest.json" if key == "e3" else "manifiesto_paquete.json"
        manifest = read_json(root / manifest_name)
        sidecar = root / manifest_name.replace(".json", ".sha256")
        if sidecar.read_text().split()[0] != sha256(root / manifest_name):
            raise ValueError("Input manifest hash mismatch")
        known = manifest.get("file_hashes") or {
            r["path"]: r["sha256"] for r in manifest.get("members", manifest.get("files", []))
        }
        for name in names:
            path = root / name
            digest = sha256(path)
            if name not in {manifest_name, sidecar.name} and known.get(name) != digest:
                raise ValueError(f"Input does not match sealed manifest: {key}/{name}")
            result.append(dict(dependency=key, path=name, bytes=path.stat().st_size, sha256=digest))
            if path.suffix == ".parquet":
                import pyarrow.parquet as pq

                file = pq.ParquetFile(path)
                schemas.append(
                    dict(
                        dependency=key,
                        path=name,
                        rows=file.metadata.num_rows,
                        fields=[dict(name=f.name, type=str(f.type)) for f in file.schema_arrow],
                    )
                )
    return result, schemas


def check_e3_cycles(cycles, e3):
    original = read_csv(e3 / "tablas/ciclos.csv")
    fields = (
        "symbol",
        "cycle_id",
        "entry_ns",
        "opened_ns",
        "closed_ns",
        "complete",
        "failed",
        "still_open_at_end",
    )
    # Same cycle_id may occur in both independent strategies. Add strategy in sort
    # and comparison to prevent an accidental cross-portfolio match.
    a = sorted(
        (dict(strategy=r["strategy"], **{k: r[k] for k in fields}) for r in cycles),
        key=lambda r: (r["strategy"], r["cycle_id"]),
    )
    b = sorted(
        (dict(strategy=r["strategy"], **{k: r[k] for k in fields}) for r in original),
        key=lambda r: (r["strategy"], r["cycle_id"]),
    )
    same_rows(a, b, "original E3 cycle identities")


def build(output, dependencies, documents, research, tests_root):
    output = new_destination(output, [*dependencies.values(), documents, research])
    sources, schemas = source_inventory(dependencies)
    tables = derive(dependencies["parent"], dependencies["correction"], dependencies["intraday"])
    validation = check_tables(tables)
    check_e3_cycles(tables["ciclos_vida"], dependencies["e3"])
    output.mkdir(parents=True)
    for name, rows in tables.items():
        write_csv(output / "tablas" / (name + ".csv"), rows)
    shutil.copytree(documents, output / "documentos")
    shutil.copytree(research, output / "fuentes_publicas")
    write_json(output / "fuentes.json", sources)
    write_json(output / "documentos/esquemas_fuentes.json", schemas)
    write_csv(output / "documentos/inventario_fuentes.csv", sources)
    for strategy, run in RUNS.items():
        shutil.copyfile(
            dependencies["parent"] / "corridas" / run / "effective_config.toml",
            output / "documentos" / ("config_" + strategy + ".toml"),
        )
    code = Path(__file__).resolve().parent
    tool_scripts = output / "herramientas/scripts"
    shutil.copytree(
        code, tool_scripts / "return_capital", ignore=shutil.ignore_patterns("__pycache__")
    )
    for name in ("build_return_capital.py", "verify_return_capital.py"):
        shutil.copyfile(code.parent / name, tool_scripts / name)
    shutil.copyfile(code.parent / "distribution_integrity.py", tool_scripts / "distribution_integrity.py")
    test_output = output / "herramientas/tests/unit"
    test_output.mkdir(parents=True)
    for path in tests_root.glob("test_return_capital_*.py"):
        shutil.copyfile(path, test_output / path.name)
    write_report(output, tables)
    write_json(output / "verificacion_construccion.json", validation)
    write_json(
        output / "estado_bloques.json",
        dict(
            concentracion="ejecutado",
            restricciones="ejecutado",
            integracion_anual="ejecutado",
            investigacion_benchmark="ejecutado",
            comparacion_remunerada="pendiente_aprobacion_benchmark",
            pdf_final="fuera_de_esta_entrega",
        ),
    )
    write_json(
        output / "documentos/entorno.json",
        dict(
            python=platform.python_version(),
            platform=platform.platform(),
            dependencies={
                name: __import__(name).__version__ for name in ("pyarrow", "numpy", "matplotlib")
            },
        ),
    )
    (output / "README.md").write_text(README, encoding="utf-8")
    manifest = dict(
        schema="return_capital_v1",
        created_at=datetime.now(UTC).isoformat(),
        benchmark_status="pendiente_aprobacion_benchmark",
        members=[
            dict(path=p.relative_to(output).as_posix(), bytes=p.stat().st_size, sha256=sha256(p))
            for p in sorted(output.rglob("*"))
            if p.is_file()
        ],
    )
    write_json(output / "manifiesto_paquete.json", manifest)
    (output / "manifiesto_paquete.sha256").write_text(
        sha256(output / "manifiesto_paquete.json") + "\n", encoding="ascii"
    )
    return output


README = """# Retorno y capital: paquete local verificable

Leer [reporte HTML](reporte.html), [reporte Markdown](reporte.md),
[protocolo](documentos/protocolo.md) y [ficha del benchmark](documentos/ficha_benchmark.json).
Concentración, restricciones e integración: ejecutado. Benchmark remunerado:
pendiente_aprobacion_benchmark. No se calcularon sus retornos ni se generó PDF final.

## Verificación portable

Python 3.14, PyArrow, NumPy y Matplotlib del entorno del proyecto. Desde cualquier
directorio, sin Git, HEAD, índice, motor, red ni datos masivos de mercado:

```powershell
& <python> -B -X utf8 <paquete>/herramientas/scripts/verify_return_capital.py --package <paquete>
& <python> -B -X utf8 <paquete>/herramientas/scripts/verify_return_capital.py --package <paquete> --parent <padre> --correction <correccion> --intraday <intradia_compacto> --e3 <evidencia_E3> --output <resultado_nuevo_externo.json>
```

La modalidad compacta verifica miembros, identidades algebraicas, fronteras,
atribuciones, clasificaciones y denominadores internos. La completa exige las
cuatro dependencias y comprueba sus fuentes contra los hashes fijados, vuelve
a derivar las tablas y conserva la identidad de ciclos E3. Comparte módulos de
posprocesamiento; no constituye una implementación independiente del motor.
No recalcula extremos intradía ni valida toda la historia de precios masiva.

`fuentes.json` e `inventario_fuentes.csv` enumeran los archivos indispensables.
Padre: manifiestos y archivos de las dos BASE. Corrección: tablas financieras,
exposición y H1/H2/H3. Intradía: manifiesto y precios de eventos financieros
exportados. E3: manifiesto, ciclos y código archivado de referencia. No se
copian las carteras ni millones de observaciones. El paquete sí incluye CSV
nuevos y subconjuntos BASE intactos, código/pruebas y originales públicos.

## Pruebas y reproducción

Para los fixtures pequeños, desde `<paquete>/herramientas`:

```powershell
& <python> -B -m pytest -p no:cacheprovider tests/unit
```

Las pruebas históricas requieren `RETURN_CAPITAL_PARENT`,
`RETURN_CAPITAL_CORRECTION` y `RETURN_CAPITAL_INTRADAY` con rutas explícitas;
sin ellas se declaran omitidas si no existen las rutas predeterminadas del
checkout. Una prueba omitida no certifica los resultados históricos.

Constructor (siempre destino inexistente, fuera de todas las entradas):

```powershell
& <python> -B -X utf8 <paquete>/herramientas/scripts/build_return_capital.py --output <destino_nuevo> --parent <padre> --correction <correccion> --intraday <intradia_compacto> --e3 <evidencia_E3> --documents <paquete>/documentos --research <paquete>/fuentes_publicas --tests-root <paquete>/herramientas/tests/unit
```

Las auditorías finales son externas al paquete y nombran el SHA-256 verificado.
El constructor rechaza sobrescritura; el verificador rechaza salida existente
o dentro de fuentes. Ningún comando importa crypto_carry ni ejecuta backtests.
Las reglas Git acotadas preservan bytes; no hay commit, push ni cambios al índice.
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "output",
        "parent",
        "correction",
        "intraday",
        "e3",
        "documents",
        "research",
        "tests-root",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    dependencies = {
        key: getattr(args, key).resolve() for key in ("parent", "correction", "intraday", "e3")
    }
    output = build(args.output, dependencies, args.documents, args.research, args.tests_root)
    print(output)

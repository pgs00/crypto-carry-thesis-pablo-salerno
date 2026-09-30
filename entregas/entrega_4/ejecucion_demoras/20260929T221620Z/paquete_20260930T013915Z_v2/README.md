# Evidencia de ejecución y demoras

[Reporte](reporte.md) · [HTML](reporte.html) · [Síntesis](sintesis.md) · [Incidentes](incidentes.md)

Desde una copia limpia, offline y con Python y dependencias fijadas en
`herramientas/pyproject.toml` y `herramientas/uv.lock`:

```powershell
python -B -X utf8 herramientas/scripts/verify_execution_delays.py --package . --output ../auditoria_nueva.json
```

El destino es nuevo y externo. No necesita HEAD, índice Git ni la ruta del proyecto original.
Recalcula cierres/períodos, exposición, H2/H3, órdenes/fills/ledger, precios,
cronología, capacidad e incidentes desde los extractos incluidos. No hace replay.
H1 reutiliza una sola población BASE después de verificar proyecciones y targets.
Constructor y verificador comparten funciones; no constituyen motores independientes.

Para volver a autenticar y extraer las ventanas desde fuentes masivas locales,
agregar `--data-root D:/Backtesting`; ese control exige esos archivos.
El CSV forecast original está comprimido sin pérdida con tamaño y hash originales.
Las carteras completas permanecen en los destinos indicados por el índice.

Pruebas semánticas del paquete (copias descartables, hashes renovados):

```powershell
$env:EXECUTION_DELAYS_PACKAGE = (Resolve-Path .).Path
python -B -m pytest herramientas/tests/integration/test_execution_delays_package.py -q -p no:cacheprovider
```

Los registros posteriores al sello, incluida la exportación binaria mediante
índice temporal aislado y la comprobación desde otra ruta, permanecen fuera
del paquete. No hay commit, push ni modificación del índice del usuario.

[Revision tecnica de esta version](documentos/revision_tecnica_paquete.md).

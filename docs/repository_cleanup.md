# Limpieza para presentación — 20/09/2026

El alcance vigente es la comparación de carteras continuas del **01/01/2022
al 31/08/2026 UTC**, `futures_scaled`, sin reinicios anuales. Esta limpieza
reorganiza la presentación; no modifica motor, parámetros, corridas o resultados.

## Actualizado

- [README](../README.md), [metodología](methodology.md) y [estado](progress.md)
  describen consistentemente el período continuo y distinguen antecedentes.
- [Vista de Entrega 3](../entregas/entrega_3/continua/README.md): 11 tablas originales,
  una proyección de equity diario de 3.408 filas y tres figuras en PNG/SVG.
  Se generan desde el ZIP guardado. CSV originales sin cambios; sólo la
  presentación Markdown y los gráficos redondean o convierten a punto flotante.
- Índices de entrega, investigación y manifiestos; enlaces y herramientas
  afectados por el archivo. H3 conserva el forecast elegible completo.
- `.gitattributes` preserva los bytes de los paquetes reubicados y de las nuevas
  evidencias. `.gitignore` conserva exclusiones existentes y cubre ZIP, checksums
  y Parquet de investigación.

## Archivado y conservado

- Dos ZIP anteriores, sus SHA-256 y los 140 archivos del paquete v2 en
  [archivo de Entrega 3](../entregas/entrega_3/archivo/README.md). Los miembros
  del ZIP v2 y su copia consultable son idénticos; ésta se conserva porque sirve
  a la navegación y a los verificadores históricos.
- Herramientas puntuales de preparación preservadas como snapshots de texto;
  el helper de integridad conserva sus pruebas y usa la ruta archivada.
- [Informe original del piloto del 01/01/2024](../data/manifests/archive/pilot_20240101/data_quality_report.md),
  sin alterar sus bytes. Su ruta anterior ahora avisa que no es el diagnóstico
  continuo. Los cuatro manifiestos/tablas de entrada del piloto siguen en sus
  rutas por las dependencias de reproducción.
- Snapshots de [metodología anterior](archive/methodology_before_cleanup_20260920.md.txt)
  y [avance anterior](archive/progress_before_cleanup_20260920.md.txt).
- Se revisaron las 13 carpetas exploratorias preexistentes de `data/research`:
  se conserva su evidencia única, sus hashes y las rutas usadas por scripts y
  pruebas. El [catálogo](../data/research/README.md) explica su vigencia y función.
  Las evidencias de los 15 marks y de sensibilidad del funding permanecen intactas.

## Eliminado del árbol o del seguimiento

- Una copia redundante: `entregas/entrega_3/preparar_paquete.py` (6.858 bytes).
  Antes de retirarla se comprobó SHA-256 y bytes idénticos a
  `archivo/paquete_redaccion/scripts/preparar_paquete.py`; la copia canónica y
  ambas versiones ZIP preservan el código. Sus consumidores activos se actualizaron.
- Dos ZIP de velas del piloto y sus dos checksums se retiraron **sólo del
  seguimiento de Git**. Siguen en `data/research/trades-2024-01-01/`, con los
  mismos hashes. Las bajas están en el índice para que el próximo commit deje
  de versionarlos; no se borraron los archivos ni se reescribió el historial.
- Se retuvo el duplicado de `download.json` del piloto: es una entrada con ruta
  propia y hash, no una copia prescindible. Tampoco se deduplicaron miembros
  internos de paquetes sellados, para conservar sus manifiestos y su autonomía.

## Validación reproducible

Desde la raíz del repositorio:

```powershell
& '.\.venv\Scripts\python.exe' -m scripts.verify_repository_evidence
& '.\.venv\Scripts\python.exe' -m pytest -q
& '.\.venv\Scripts\python.exe' -m ruff check src tests scripts entregas/entrega_3/archivo/empaquetar.py
```

El verificador contrasta el [registro de conservación](repository_cleanup_manifest.json),
fuentes archivadas, los tres ZIP, ambos paquetes, las sensibilidades, tablas,
figuras, enlaces de documentación vigente y exclusiones. Usa una extracción
temporal del ZIP continuo dentro de `.superpowers/`; no requiere Binance ni D:.
Los archivos grandes originales no forman parte de esta publicación.

Los paquetes y snapshots se verifican con sus bytes exactos. Para archivos de
código y configuración que ya tenían CRLF en el checkout y LF en Git antes de
esta limpieza, el registro conserva ambos hashes originales y acredita que la
única diferencia era el salto de línea. No se normalizaron esas fuentes.

La regeneración de presentación se comprueba con un destino nuevo mediante
`python -m scripts.publish_thesis --output .superpowers/presentacion_repro`.
No se realizaron backtests, descargas, commits ni push durante esta limpieza.

## Resultados de la validación

| Control | Resultado del 20/09/2026 |
|---|---|
| pytest | **485 passed**: 480 pruebas existentes y 5 controles nuevos de pérdida de caracteres en documentación y fórmulas. |
| Ruff | `check` aprobado para `src`, `tests`, `scripts` y el helper archivado; los tres archivos nuevos de código/pruebas cumplen `format --check`. |
| Integridad | 458 archivos protegidos o archivados conservan sus hashes; los tres ZIP pasan las comprobaciones. El paquete continuo verifica 120 archivos y el v2 conserva sus 140 miembros idénticos. |
| Evidencia financiera | Conciliación del paquete continuo y de las 10.224 observaciones de sensibilidad del funding aprobadas, sin recalcular las carteras. |
| Navegación | 160 enlaces locales vigentes válidos; ninguno de sus 83 destinos está excluido por Git. |
| Reproducción de presentación | Los 21 archivos regenerados, incluidos manifiestos, coinciden byte por byte; 1.242.221 bytes en total. |
| Revisión | Tres PNG inspeccionados visualmente y revisión independiente de conservación, cifras, metodología y navegación. La pérdida de caracteres detectada durante la edición quedó corregida y cubierta por pruebas. |
| Alcance | Motor, configuraciones, resultados y evidencia de marks/funding sin cambios; los cuatro archivos de mercado retirados de Git siguen presentes con sus hashes originales. |

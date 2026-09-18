# Verificación del escenario aprobado

Implementación local del 18/09/2026, rama `codex/crypto-carry`, sobre `bad3376bee0c73fa3f24b7afb41b9dbcbb1e16f5`. No se modificó el descargador activo, ni se hizo commit o push.

## Evidencia

- Base previa a los cambios: 179 pruebas aprobadas.
- Batería completa tras integrar el escenario: `python -m pytest -q`, **235 passed in 39.90s**.
- Tras corregir la etiqueta del gráfico vacío: 13 pruebas específicas de reporting/CLI aprobadas; Ruff check y format, 53 archivos conformes. Se renderizó el gráfico corregido y se comprobaron texto SVG y legibilidad PNG.
- Revisiones independientes: reglas/configuración aprobadas tras corregir el rechazo de `known_from` desconocido; funding/validación aprobados; reporting e integración final aprobados sin observaciones pendientes.
- Resolver de producción: 10.224 eventos reales contrastados con páginas API y ZIP de marks con hashes comprobados; 6.214 exactos conservados, 4.010 proxies del cierre anterior. Evidencia: `data/research/research-scenario-20260918/funding-resolver-verification.json` y script de reproducción adjunto.
- Piloto observado: 00:00–00:10 UTC del 01/01/2024, seleccionado antes de ejecutar resultados. 61.393 trades por cartera, continuidad efectiva de IDs comprobada y 20 velas de mark entre ambos activos. Ambas carteras completas, seis fills nativos cada una, diferencia contable cero.
- Ocho escenarios del piloto: caso base, costos 2x/3x, proxy +10/-10 bps, taker futuros 4 bps, mantenimiento 2x y cargo de liquidación 3 %. Todos completos para ambas carteras; hashes del índice y subcorridas verificados. Informe base regenerado idéntico. Evidencia: `pilot-artifact-verification.json` y `pilot-results.json` en la misma carpeta.

El índice `robustness-95178f7896fa4926` y sus subcorridas son inmutables y preceden a la corrección cosmética de la etiqueta del gráfico de costos vacío. Sus resultados económicos siguen verificados. La figura corregida se comprobó por separado en `corrected-plot-preview`; no se reescribieron los artefactos anteriores.

## Decisiones de implementación

- Se mantuvo el trabajo en la rama existente y en el entorno con los datos locales; no se creó otro checkout ni se publicó. La decisión previa del usuario sobre GitHub ya estaba resuelta.
- Se usaron scripts PowerShell equivalentes para los artefactos de revisión porque el entorno es Windows.
- Se añadió una configuración de investigación para D: con el presupuesto de 800 GB previamente autorizado, manteniendo el archivo de investigación de 20 GB para la muestra.
- Se utilizó una muestra observada de diez minutos con continuidad comprobada. Las discontinuidades de IDs del día completo se conservan como bloqueos y no se convierten en operaciones inventadas.
- Las reglas prescritas exigen un perfil de costos explícito sin promociones; no pueden presentarse bajo la etiqueta de tarifas históricas VIP 0.

## Pendientes externos a la implementación aprobada

La muestra corta no sustituye la validación económica extensa. Faltan completar y normalizar la descarga, resolver discontinuidades de IDs y los 15 minutos de mark pendientes señalados por la auditoría, medir recursos con una muestra más amplia y ejecutar la ventana completa con sus sensibilidades. Los dos tipos de incidencia siguen bloqueando la certificación de cobertura. No hace falta una nueva confirmación del usuario para los supuestos ya implementados.

Comandos y parámetros: [escenario de investigación](../escenario_investigacion.md).

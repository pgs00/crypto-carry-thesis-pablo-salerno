# Investigación histórica de reglas Binance

Entrega documental parcial ejecutada el 24–25/09/2026 UTC. La carpeta lleva el timestamp real de inicio: `20260924T234206Z`. Período económico: `[2022-01-01T00:00:00Z, 2026-09-01T00:00:00Z)`; Binance.com, BTCUSDT/ETHUSDT spot y perpetuos USDT-M, Regular/VIP0 sin descuentos, taker, spot sin crédito, futuros aislados a 2x.

**La fecha efectiva del cambio taker de futuros 0,04%→0,05% sigue pendiente.** Hay nueva evidencia conservada: FAQ junio 2023, tabla spot agosto 2026, siete capturas históricas API y ocho tablas anteriores de margen. El registro contiene 345 hechos; su cantidad no mide días certificados. No se ejecutaron backtests ni se integraron reglas en el motor.

| Archivo | Contenido |
|---|---|
| [reporte_fuentes_historicas.md](reporte_fuentes_historicas.md) | Hallazgos, diferencias con antecedentes, incertidumbre, límites y prioridades |
| [inventario_inicial.md](inventario_inicial.md) | Revisión local antes de búsqueda nueva |
| [fuentes.json](fuentes.json) | 52 fuentes/recuperaciones: URL, fechas, HTTP, representación y hashes |
| [reglas_historicas.json](reglas_historicas.json) | Hechos por parámetro y tablas completas; `loadable_by_rulebook=false` |
| [cobertura.csv](cobertura.csv) | 479 filas: intervalos, eventos, puntos, escenarios y huecos |
| [busquedas.jsonl](busquedas.jsonl) | Consultas web y descargas, con resultado y decisión |
| [originales/](originales/) / [extraidos/](extraidos/) | Cuerpos recibidos, metadatos, resultados web originales, textos, tablas y selecciones JSON |
| [revision_segunda.json](revision_segunda.json) | Segunda revisión por el mismo agente |
| [manifest.json](manifest.json) | SHA-256 y tamaños de todos los archivos estáticos nuevos |
| [verificacion_resultados.json](verificacion_resultados.json) | Resultado de ejecución, comprobaciones, pruebas negativas y conservación del repositorio |
| [incidencias_ejecucion.json](incidencias_ejecucion.json) | Fallos técnicos y correcciones del auxiliar documental |

Verificación **offline**, desde la raíz del repositorio, sin dependencias ajenas a la biblioteca estándar de Python:

```powershell
python -X utf8 data/research/historical-rules-followup-20260924T234206Z/verificar_fuentes.py --self-test
```

El comando sólo actualiza los dos archivos `verificacion_resultados.*` y usa copias temporales dentro de esta carpeta. Comprueba todos los archivos versionados contra `estado_inicial.json`; si el usuario cambia el repositorio después de la entrega, esa comprobación puede fallar correctamente. No actualiza hashes para esconder cambios.

La extracción puede reconstruirse desde las copias guardadas con:

```powershell
python -X utf8 data/research/historical-rules-followup-20260924T234206Z/construir_registro.py
```

Ese auxiliar reescribe sólo los productos derivados de esta carpeta y actualiza timestamps de lectura/generación. Por ello no es una reproducción binaria del paquete sellado: después de una regeneración deliberada, hay que revisar las diferencias antes de crear un nuevo manifiesto. La verificación normal no requiere regenerar ni descargar.

`recuperar_fuentes.py` documenta el procedimiento de descarga pública con timeout de conexión/lectura y hasta tres intentos; el valor usado por defecto fue uno. Rechaza sobrescribir un ID existente. Los planes `descargas_01.json` a `descargas_05.json` conservan las URL seleccionadas; las solicitudes adicionales están en `descargas.jsonl`. Para una nueva investigación, copiar el auxiliar/plan a una carpeta nueva y usar IDs nuevos. No repetir un bloqueo HTTP 403/429/451 ni tratarlo como ausencia de fuentes. No se instaló ninguna dependencia durante esta tarea; el auxiliar online utiliza `requests` y `beautifulsoup4` ya disponibles.

Los `.body` son exactamente los bytes de `requests.Response.content`, con la posible descompresión automática indicada en cada `.meta.json`. Las fuentes `*_web.txt` son extracciones de la herramienta de navegación, no HTML original; las fuentes sólo consultables online están marcadas expresamente. A1–A3 se referencian en su carpeta anterior, sin duplicarlas ni cambiar su manifiesto.

El manifiesto excluye únicamente a sí mismo y `verificacion_resultados.json/.txt`, para evitar autorreferencia; el resultado registra el hash del manifiesto que verificó. No hay commit, push ni cambios de índice. La protección `* -text whitespace=cr-at-eol` se aplica sólo dentro de esta carpeta.

# Reproducción

Los comandos se ejecutan desde la raíz del repositorio. Los PDF, las tablas y
la evidencia incluida permiten revisar el estudio sin fuentes de mercado
externas. Las [limitaciones metodológicas](methodology.md#limitaciones) definen
el alcance financiero de esa revisión.

## Instalar y verificar

```bash
uv sync --frozen --python 3.14.3
uv run python -m scripts.verify
uv run pytest -q
```

El primer comando instala el entorno de [uv.lock](../uv.lock). `verify` lee la
evidencia retenida, recalcula los resultados y compara 304 cifras de las 22
tablas de la tesina al redondeo publicado. También comprueba los parámetros,
las rutas protegidas, los enlaces internos y los hashes SHA-256 de las fuentes. Los valores esperados
y el registro único de integridad están en
[thesis_baseline.json](../data/evidence/thesis_baseline.json).

La salida identifica las comprobaciones y cualquier divergencia; un fallo
produce un código de salida distinto de cero. Los cálculos utilizan las
observaciones, series diarias, ciclos, señales y tasas incluidas en la evidencia.
De las 304 cifras, 282 se recalculan desde las observaciones retenidas y cuatro
comprueban la aritmética de extremos intradiarios archivados. Las otras 18
corresponden a parámetros y recuentos contrastados con sus fuentes. El alcance
intradiario se describe en metodología. El comando funciona sin descargar
mercados ni ejecutar nuevamente las carteras.

Para guardar el resultado fuera de la evidencia:

```bash
uv run python -m scripts.verify --output /tmp/crypto-carry-verification.json
```

`pytest` cubre contabilidad, funding, margen y liquidación, cantidades, ventanas
de ejecución, EWMA, métricas, H1/H2/H3 y bootstrap. La tolerancia relativa de
CAGR es `1e-9` para diferencias de aritmética entre plataformas; las cifras
publicadas se comparan a su redondeo original.

## Organización del recálculo

[`scripts/verify.py`](../scripts/verify.py) es el punto de entrada.
[`scripts/analysis/`](../scripts/analysis/) concentra los cálculos por tema y
comparte las fórmulas de períodos y lectura de evidencia. Las tablas declarativas
de escenarios conservan los parámetros originales. Los resultados se consultan
en el [índice temático](../results/README.md), y sus unidades en el
[diccionario](data_dictionary.md).

Los archivos ZIP se leen directamente. Se conservan completos porque son
fuentes citadas y contienen observaciones necesarias para recalcular las tablas.
Sus herramientas históricas quedan dentro del archivo como parte de la fuente;
el comando vigente es `scripts.verify`.

## Descargar y preparar los datos desde cero

Los archivos de mercado ocupan varios GB y se mantienen fuera de Git. Esta
secuencia recupera el procedimiento original, incluidas sus reparaciones.
Requiere Git, uv, conexión a las fuentes públicas de Binance y espacio para
los datos, los Parquet y las corridas. El perfil limita a 20 GB las carpetas
de datos de minutos; ese límite no incluye el entorno ni los resultados.

| Insumo | Fuente y alcance |
|---|---|
| Spot y perpetuos USD-M | BTCUSDT y ETHUSDT, velas de un minuto de [Binance Public Data](https://github.com/binance/binance-public-data). |
| Mark y calendarios de funding | Archivos mensuales de `data.binance.vision`, con sus `.CHECKSUM`. |
| Tasas y marks de cobro | API pública `https://fapi.binance.com/fapi/v1/fundingRate`, paginada y con fechas acotadas. |
| Período económico | Desde 2022-01-01 00:00 UTC hasta 2026-09-01 00:00 UTC, fin excluido. |
| Calentamiento | Diciembre de 2021; la selección efectiva de antecedentes queda registrada al normalizar. |

El plan continuo contiene 456 ZIP mensuales y dos respuestas paginadas de
funding. No requiere claves ni acceso a una cuenta. El
[manifiesto original](https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/blob/634c88fcf985da742cfa55d83bc4c0f99e082610/data/evidence/reglas_historicas/corridas/run_ad71d751b20623006c195ff3/source_manifests/download.json)
conserva URLs, intervalos y hashes de cada archivo y suplemento.

### 1. Recuperar las herramientas originales

Los siguientes comandos parten de una clonación Git de `simplify` llamada
`crypto-carry-thesis-pablo-salerno`. Si la carpeta tiene otro nombre, adaptar
el comando de regreso del paso 4. Una descarga ZIP de GitHub no contiene el
historial necesario; en ese caso, clonar primero:

```bash
git clone --branch simplify https://github.com/pgs00/crypto-carry-thesis-pablo-salerno.git crypto-carry-thesis-pablo-salerno
cd crypto-carry-thesis-pablo-salerno
```

Crear una copia de trabajo separada del commit original. La selección de
carpetas evita desplegar los paquetes de resultados y sus copias de código:

```bash
git fetch origin 634c88fcf985da742cfa55d83bc4c0f99e082610
git worktree add --detach --no-checkout ../crypto-carry-replay 634c88fcf985da742cfa55d83bc4c0f99e082610
git -C ../crypto-carry-replay sparse-checkout set src scripts configs data/research/minute-download-20260918 data/research/continuous-preparation-20260919
git -C ../crypto-carry-replay checkout
cd ../crypto-carry-replay
uv sync --frozen --python 3.14.3
```

Los comandos siguientes funcionan desde esa carpeta, con `--root .`. Los
datos quedan dentro de `crypto-carry-replay/data/minutes`, sin depender de una
unidad `D:`. Esta copia usa el `uv.lock` original, que incluye las dependencias
de descarga y preparación. El motor económico sigue siendo NautilusTrader.

### 2. Descargar las fuentes y los siete suplementos diarios

La secuencia original comenzó con dos ventanas de adquisición. Sus ZIP
verificados se reutilizan después para el historial continuo. Se preparan como
caché de datos, sin ejecutar carteras ni reiniciar capital en el estudio BASE:

```bash
uv run python -m crypto_carry.data.minute_download --root . --config configs/download_minutes_2022_2023_d.toml configs/download_minutes_2025_2026_d.toml --plan-only
uv run python -m crypto_carry.data.minute_download --root . --config configs/download_minutes_2022_2023_d.toml configs/download_minutes_2025_2026_d.toml
uv run python data/research/minute-download-20260918/repair_sources.py --root .
uv run python scripts/download_continuous.py --root . --plan-only
uv run python scripts/download_continuous.py --root .
uv run python data/research/continuous-preparation-20260919/repair_sources.py --root .
```

Ejecutar una línea por vez. Las opciones `--plan-only` muestran el inventario
sin descargar mercados. La primera reparación incorpora seis diarios de mark;
la descarga continua copia los ZIP y esos suplementos tras verificar SHA-256
y CRC. La última investigación agrega el séptimo diario y registra los huecos
que siguen ausentes de las fuentes oficiales:

| Día UTC del suplemento | Activos |
|---|---|
| 2022-07-31 | BTCUSDT |
| 2022-10-02 | BTCUSDT y ETHUSDT |
| 2023-02-24 | BTCUSDT y ETHUSDT |
| 2026-06-29 | BTCUSDT y ETHUSDT |

La descarga continua debe indicar `458/458`. Ante una interrupción, repetir
el mismo comando; reutiliza archivos verificados. La última investigación
puede terminar con código 2 por los 15 minutos documentados: revisar el
informe antes de continuar. Cualquier otro error detiene el procedimiento.
La reparación anual escribe su auditoría en esta copia de trabajo separada;
los commits históricos y la evidencia de `simplify` permanecen intactos.

### 3. Normalizar y validar la cobertura

```bash
uv run python -m crypto_carry validate-data --config configs/download_minutes_2022_2026_d.toml --scope full --clip-price-warmup
```

Este paso genera los Parquet bajo
`data/minutes/2022_2026_continuous/processed` y los informes en la carpeta
hermana `manifests`. Puede pasar varios minutos sin
imprimir progreso. La opción de calentamiento conserva los precios desde el
antecedente requerido, 2021-12-31 23:59 UTC, y mantiene el calentamiento de
funding y marks. El manifiesto original tiene 800 particiones.

En las fuentes originales, la validación estricta termina con código 2 por
15 marks faltantes. Compararlos con el
[inventario conservado](../data/research/continuous-preparation-20260919/unresolved_mark_minutes.csv):
ETH, 2022-07-12 y 2022-07-13; BTC y ETH, 2024-08-12. Si aparecen otras
omisiones, conflictos o errores, detenerse. La suspensión spot de marzo de
2023 se trata según el calendario del modelo, sin inventar velas.

Preparar la convención `futures_scaled` de BASE y validar la capa derivada:

```bash
uv run python -m crypto_carry prepare-mark-gaps --config configs/download_minutes_2022_2026_d.toml --method futures_scaled
uv run python -m crypto_carry validate-data --config configs/reglas_historicas/BASE_E3.toml --scope full --skip-normalize
```

La validación derivada debe devolver código 0 y `status: complete`. El archivo
`data/minutes/2022_2026_continuous/derived_marks/futures_scaled/manifests/coverage.json`
debe indicar `coverage_kind: completed_with_approximations`. La lista de 15 minutos está
fijada en código; el preparador contrasta las anclas y las observaciones
originales. El archivo `mark_gap_audit.json` documenta las estimaciones. Las
reglas económicas de esta convención están en [metodología](methodology.md).

### 4. Contrastar la descarga con los insumos de la tesina

Regresar a `simplify` y ejecutar:

```bash
cd ../crypto-carry-thesis-pablo-salerno
uv sync --frozen --python 3.14.3
uv run python -m scripts.check_market_sources --data-root ../crypto-carry-replay
```

El control lee el manifiesto del commit histórico, calcula los hashes reales
y contrasta 928 archivos: los ZIP, los dos snapshots de funding, los siete
suplementos y los archivos de checksum. Devuelve código 0 solamente si todos
coinciden. Un manifiesto local que declare la descarga completa no alcanza
para superar este control.

Si Binance modifica un archivo o cambia la respuesta histórica de la API,
aparecerá `sha256_mismatch`. Conservar ambas versiones e investigar la
diferencia antes de ejecutar una reproducción exacta. Si una fuente deja de
estar disponible, será necesario recuperar la copia original del autor.
Los hashes identifican esa copia, pero no reemplazan su contenido.

## Repetir el motor con datos preparados

Desde `simplify`, usar los datos preparados y una salida nueva:

```bash
uv run python -m crypto_carry --root ../crypto-carry-replay backtest --config configs/reglas_historicas/BASE_E3.toml --strategy both --output ../crypto-carry-runs
```

Se ejecutan las carteras condicional e incondicional del período completo.
La consola informa la ruta `run_<id>`. El identificador depende del código,
entorno y fuentes; la comparación relevante es la de las cifras. En esa
carpeta, `run_summary.csv` contiene patrimonio final y P&L; `metrics.csv`,
CAGR, Sharpe y drawdown por período. Seleccionar `period = full` y distinguir
`strategy = conditional` de `strategy = permanent`, identificador interno de
la cartera incondicional.

| Métrica BASE, muestra completa | Condicional | Incondicional |
|---|---:|---:|
| Patrimonio final, USDT | 10.785,7630496472 | 11.680,0692167574 |
| P&L neto, USDT | 785,7630496472 | 1.680,0692167574 |
| CAGR, porcentaje anual | 1,6334619266% | 3,3824773315% |
| Sharpe, tasa libre de riesgo cero | 4,9623712777 | 6,5336323815 |

La fuente de precisión completa es
[`metricas_cartera_periodo.csv`](../results/base/evidencia/comparacion/metricas_cartera_periodo.csv).
Comparar al redondeo de la tesina; para CAGR calculado entre plataformas,
la tolerancia relativa documentada es `1e-9`. Una diferencia se investiga
sin ajustar parámetros ni modificar los valores de referencia.

Para verificar la integridad de la nueva corrida, sustituir `<id>` por el
identificador que devolvió el motor:

```bash
uv run python -m crypto_carry verify-run ../crypto-carry-runs/run_<id>
```

`verify-run` verifica esa corrida; `scripts.verify` recalcula las 22 tablas
desde la evidencia publicada. Son comprobaciones con insumos distintos.
Los pasos anteriores regeneran BASE. Los análisis adicionales requieren
sus escenarios y preparaciones; el [índice de resultados](../results/README.md)
identifica la evidencia y configuraciones de cada tema.

Se comprobaron la instalación, los argumentos de los comandos, los planes
de descarga sin red y el rechazo de fuentes faltantes o alteradas. Esta guía
recupera el procedimiento original; la descarga completa y el replay desde
cero deben ejecutarse para confirmar su reproducción con las fuentes que
Binance sirva en ese momento. No se presentan esas ejecuciones como ya realizadas.

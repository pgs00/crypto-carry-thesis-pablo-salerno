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
las rutas protegidas y los hashes SHA-256 de las fuentes. Los valores esperados
y el registro único de integridad están en
[thesis_baseline.json](../data/evidence/thesis_baseline.json).

La salida identifica las comprobaciones y cualquier divergencia; un fallo
produce un código de salida distinto de cero. Los cálculos utilizan las
observaciones, series diarias, ciclos, señales y tasas incluidas en la evidencia.
Los parámetros declarados se contrastan con sus fuentes, y el alcance
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

## Repetir el motor con datos preparados

El motor y NautilusTrader siguen disponibles. Un replay completo necesita los
Parquet de mercado ya preparados y validados, las reglas, la configuración y
su informe de cobertura. Esos datos masivos no están incluidos. La CLI acepta
solamente fuentes locales y exige que la cobertura coincida con el período,
el modo de análisis y el tratamiento de marks de la configuración.

Con esas fuentes disponibles, consultar las opciones:

```bash
uv run python -m crypto_carry backtest --help
uv run python -m crypto_carry verify-run --help
```

BASE se define en
[`configs/reglas_historicas/BASE_E3.toml`](../configs/reglas_historicas/BASE_E3.toml).
Una corrida nueva debe guardar su salida fuera de la evidencia retenida.
Los informes y rutas anteriores se recuperan mediante los permalinks históricos
de la tesina; los commits citados permanecen intactos.

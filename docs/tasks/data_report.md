# Informe de implementación: pipeline de datos

## Alcance implementado

Se implementó exclusivamente el subsistema `src/crypto_carry/data/` y sus contratos documentales:

- `download.download(config, root, scope="sample")`: descarga oficial acotada, paginación de funding, reanudación HTTP Range validada, retries con backoff, límite agregado de 20 GB, caché, SHA-256 oficial, integridad ZIP y manifiesto por objeto.
- `normalize.normalize(config, root)`: lectura incremental de ZIP, timestamps UTC ns por fuente, decimales exactos, disponibilidad temporal sin look-ahead, Parquet particionado, deduplicación y manifiesto procesado.
- `validate.validate_data(config, root, scope="sample")`: hashes, cobertura, continuidad de IDs, cobertura de marks por minuto, calendario/mark de funding, reglas y salidas `coverage.json`, `data_coverage.csv` y `data_quality_report.md`.
- `rules.RuleBook`: selección conjunta por vigencia, conocimiento y evidencia; rechaza solapamientos. Los snapshots actuales no se retrotraen. `synthetic_rules` es explícito y sólo sirve para pruebas/demo.
- `replay.iter_records`: merge cronológico incremental de `Trade`, `Funding`, `Mark` y `DataGap`, con warmup y una observación antecedente por stream. `input_hashes` expone la trazabilidad utilizable.

`data/rules/history.json` se inicializó vacío. No se encontró ni se inventó evidencia oficial fechada suficiente para construir snapshots completos de fees, filtros, tramos, deducciones y cargos aplicables al pasado. Por eso el software funciona, pero una corrida histórica estricta permanece bloqueada.

## Evidencia de pruebas offline

El ciclo RED falló inicialmente durante collection con `ModuleNotFoundError: No module named 'crypto_carry.data'`, que era la ausencia esperada del subsistema. Después de implementar:

```text
.venv/Scripts/python.exe -m pytest tests/unit/test_data.py -q
11 passed in 0.79s

.venv/Scripts/python.exe -m ruff check src/crypto_carry/data tests/unit/test_data.py
All checks passed!
```

Las pruebas cubren la unidad microsegundo de spot desde 2025 sin alterar Futures, duplicados idénticos y conflictivos, rechazo por presupuesto antes de red, avance de paginación sin solapamiento, caché cruda con SHA/ZIP, límites `valid_from`/`valid_to`/`known_from`, snapshot actual no retroactivo, reglas sintéticas opt-in, gap de funding que no se reclasifica como cambio de intervalo, cobertura completa contra archivo desconocido y replay con observaciones previas.

## Muestra oficial descargada y normalizada

Se ejecutó el alcance `sample` de `configs/base.toml`: desde `2024-01-01T00:00:00Z` hasta antes de `2024-01-02T00:00:00Z`. Funding exigió warmup desde `2023-12-17T00:00:00Z` y la descarga comenzó el `2023-12-16T00:00:00Z` para conservar el antecedente.

La primera ejecución descargó 12 objetos sin error: trades individuales spot y USD-M de BTCUSDT/ETHUSDT, mark price klines 1m, archivos mensuales de funding Rate de Data Vision y respuestas de `/fapi/v1/fundingRate`. La segunda ejecución obtuvo `12 cached, 0 downloaded, 0 failed`, confirmando que no duplicó ni corrompió la entrada.

La API pública observada coincide con el contrato relevante: cada fila incluye `symbol`, `fundingTime`, `fundingRate` y `markPrice` (también apareció `rateType`). Cada símbolo devolvió 51 filas crudas; se descartó sólo la primera porque no tiene antecedente dentro de la respuesta para medir su intervalo. Se publicaron 50 filas por símbolo, todas corroboradas por el calendario de Data Vision y con settlement mark presente.

| Dataset | Archivos Parquet | Filas | Bytes Parquet | Resultado de controles |
|---|---:|---:|---:|---|
| Trades | 57 | 5.543.505 | 55.076.025 | Spot completo; discontinuidades de ID en ambos archivos Futures. |
| Mark 1m | 2 | 2.880 | 141.186 | 1.440 minutos consecutivos por símbolo. |
| Funding | 2 | 100 | 8.452 | 50 intervalos verificados por símbolo; marks presentes. |

Tamaño efectivo: 57.143.781 bytes crudos, 55.225.663 bytes procesados y 112.460.781 bytes totales bajo `data/`, muy por debajo del límite de 20 GB. La normalización terminó con 61 entradas, 5.546.485 filas y cero errores internos.

Hashes de control después de la ejecución:

```text
download.json  4964d6ed9c7e18150f65ce4e11c1dd94d6f6d5d38a23771ae056df1f03525091
processed.json 63f9624cb352b7ac3957d9d2fe20ca05294e59183d3d265bdaa0d3af547bf4b3
coverage.json  929094f1c914056fa28f5c4ef8c51c7c98f0e1f2372faaf6548208a0f131205b
```

## Estado real de cobertura

`validate_data(..., scope="sample")` devuelve `incomplete_data`, `historical=true` y `full_baseline_coverage=false`. Hay dos causas explícitas:

1. faltan reglas históricas verificadas para spot y Futures de BTCUSDT y ETHUSDT;
2. los archivos oficiales de Futures tienen saltos internos en `trade_id` pese a pasar el checksum publicado. Ejemplos BTC: `4426838728 → 4426838730`; ETH: `3478542319 → 3478542321`.

El validador no presenta esos saltos como inactividad real ni declara completa la muestra. La cobertura de spot, marks y funding sí pasó sus controles propios. Tampoco se infiere cobertura del baseline 2022–2026 a partir de este único día.

## Archivos resultantes

- `data/manifests/download.json`: URLs, paths, rangos, hashes, bytes, estados, errores y recuperación.
- `data/manifests/processed.json`: archivos Parquet, esquemas, filas, hashes y verificaciones.
- `data/manifests/coverage.json`, `data_coverage.csv`, `data_quality_report.md`: resultado verificable de cobertura.
- `docs/data_dictionary.md`: unidades, temporalidad, reglas, manifests y tratamiento de faltantes.

El siguiente paso válido para una corrida académica es resolver con evidencia oficial las reglas históricas completas y las discontinuidades de IDs de Futures. Hasta entonces la muestra sirve para verificar software y calidad de fuentes, no para certificar resultados económicos históricos.

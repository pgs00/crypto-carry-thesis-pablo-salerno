# H1 preliminar con funding observado — 18/09/2026

**Resultado descriptivo favorable a H1:** en 2022–2026, el MAE equiponderado de EWMA es **6,299 bps**, frente a **8,703 bps** del pronóstico no-change, una reducción del error de **27,63%**. La comparación usa las mismas observaciones válidas y los parámetros originales. No es un resultado de rentabilidad, ni completa H2 o H3.

Se pudo evaluar H1 sin imputar ningún mark de cobro: el objetivo es una suma de tasas de funding y las funciones existentes no necesitan ese precio. No se alteraron motor, configuración, reglas históricas ni datasets del pipeline. Los datos y resultados de esta investigación quedan separados en C:.

## Resultado

Los errores corresponden a la **tasa acumulada de funding de las 168 horas siguientes**; 1 bp equivale a 0,0001 en tasa decimal. No son errores anuales ni retornos de cartera.

| Período de la señal | Activo | Observaciones válidas | Excluidas | MAE EWMA, bps | MAE no-change, bps | Reducción relativa del MAE |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2022–2026 | BTCUSDT | 5.090 | 22 | 5,739 | 7,884 | 27,21% |
| 2022–2026 | ETHUSDT | 5.090 | 22 | 6,859 | 9,523 | 27,97% |
| 2022–2026 | Media equiponderada | 10.180 | 44 | **6,299** | **8,703** | **27,63%** |
| 2022–2023 | BTCUSDT | 2.190 | 0 | 6,290 | 8,782 | 28,38% |
| 2022–2023 | ETHUSDT | 2.190 | 0 | 8,479 | 11,771 | 27,97% |
| 2022–2023 | Media equiponderada | 4.380 | 0 | 7,384 | 10,276 | 28,14% |
| 2024–2026 | BTCUSDT | 2.900 | 22 | 5,323 | 7,205 | 26,13% |
| 2024–2026 | ETHUSDT | 2.900 | 22 | 5,636 | 7,825 | 27,98% |
| 2024–2026 | Media equiponderada | 5.800 | 44 | 5,479 | 7,515 | 27,09% |

La media equiponderada es `(MAE_BTC + MAE_ETH) / 2`; su conteo suma ambos activos y no implica observaciones independientes. Los regímenes se asignan por fecha de la señal, conforme a `h1_summary`: los horizontes de señales al final de 2023 pueden extenderse a enero de 2024. La fecha final de evaluación es exclusiva: 01/09/2026 00:00 UTC.

La mejora aparece en ambos activos y regímenes. Los horizontes se solapan y los activos pueden estar relacionados: esta comparación no establece significancia estadística ni causalidad. Un menor error de pronóstico tampoco demuestra que el filtro genere suficiente funding para cubrir costos o mejore el Sharpe de una cartera.

## Cobertura y procedencia

Se verificaron **114 calendarios mensuales oficiales** —57 por activo, de diciembre de 2021 a agosto de 2026— contra sus archivos `.CHECKSUM` SHA-256 y la integridad CRC de los ZIP. Se reutilizaron los cuatro ZIP válidos que ya estaban en C:. Se descargaron los otros 110 con un máximo de cuatro trabajadores; respuestas ZIP y CHECKSUM sumaron **110.050 bytes** nuevos. No se usaron credenciales ni soporte.

Los calendarios se cruzaron con las 14 páginas originales de la API guardadas en `funding-20260918T132612Z`, cuya integridad se verificó contra [el inventario anterior](funding_api_coverage.json). Las páginas contienen 6.684 observaciones por activo; para esta evaluación se usó diciembre de 2021 como preparación y la ventana económica original.

| Comprobación | BTCUSDT | ETHUSDT |
| --- | ---: | ---: |
| Eventos API en diciembre 2021–agosto 2026 | 5.205 | 5.205 |
| Eventos en calendarios oficiales | 5.205 | 5.205 |
| Timestamps presentes sólo en una fuente | 0 | 0 |
| Conflictos de tasa | 0 | 0 |
| Timestamps API duplicados | 0 | 0 |
| Cobros dentro de la evaluación 2022–2026 | 5.112 | 5.112 |
| Señales válidas de pronóstico | 5.112 | 5.112 |
| Marks de cobro ausentes en la ventana económica | 2.005 | 2.005 |

El primer intervalo del 01/12/2021 no tiene antecedente dentro de esta selección y permanece **no verificado**. Está fuera de todas las historias utilizadas por las señales de evaluación. Los otros intervalos se corroboraron mediante `normalize.funding_records`, con tiempos, tasas e intervalos publicados obtenidos por `_funding_calendar_times`. No se forzó `interval_verified=True`, no se redondearon timestamps y no se sustituyeron tasas faltantes por cero.

La concordancia de API y archivos oficiales, junto con los intervalos publicados, respalda esta cobertura. Ambas fuentes pertenecen a Binance: no excluye por sí sola una omisión compartida que tampoco se reflejara en su calendario.

Fuentes: [calendarios mensuales de Binance Data Vision](https://data.binance.vision/?prefix=data/futures/um/monthly/fundingRate/), [repositorio oficial de datos públicos](https://github.com/binance/binance-public-data), [historial de funding de la API oficial](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data). El manifiesto conserva las URL individuales de cada archivo.

## Método y exclusiones

Se reutilizaron sin modificaciones `forecast.forecast`, `evaluation.forecast_evaluation` y `evaluation.h1_summary` con `configs/base.toml`: ventana de 336 horas reales, vida media de 24 horas, horizonte de 168 horas y señal 60 segundos después de cada cobro efectivo.

Para cada pronóstico se pasó la ventana necesaria y su antecedente; el recorte sólo reduce trabajo de lectura y no altera los datos que consume la función. EWMA pondera tasas e intervalos reales. No-change extrapola la última tasa por su intervalo. El objetivo suma tasas observadas en `(señal, señal + 168 horas]`. Se evaluaron todas las señales, sin condicionar a posiciones, capital, basis, costos o elegibilidad económica.

Se excluyeron **22 señales por activo**:

- 21 con horizonte fuera de la muestra, desde el 25/08/2026.
- 1 del 24/08/2026 a las 16:01 UTC: su horizonte acaba después del último cobro del 31/08/2026 disponible en la selección. La función original no puede verificar la siguiente frontera de calendario y devuelve `funding_calendar_boundary_unverified`.

La última señal evaluable es del **24/08/2026 a las 08:01:00.002 UTC**, en ambos activos. La primera es del **01/01/2022 a las 00:01:00.006 UTC**. Se conservaron los 10.224 registros, incluidas las 44 exclusiones y sus motivos.

## Artefactos y reproducción

El [resultado JSON](funding_h1_preliminary_20260918.json) contiene configuración efectiva, cobertura, resumen, exclusiones, hashes del código y referencias de las páginas API. Los decimales de los pronósticos se conservan como strings en las señales; el evaluador original produce estadísticas en float.

- [Manifiesto de calendarios](../../data/research/funding-calendar-h1-20260918/manifest.json): 114 URL, hashes, checksums, tamaños y fecha de descarga/verificación.
- [Resumen H1](../../data/research/funding-calendar-h1-20260918/h1_summary.json): nueve filas, sin el redondeo de presentación de la tabla.
- [Señales JSON comprimidas](../../data/research/funding-calendar-h1-20260918/signals.json.gz): 10.224 pronósticos, tiempos, antecedentes y validez.
- [Evaluación JSON comprimida](../../data/research/funding-calendar-h1-20260918/forecast_evaluation.json.gz): objetivos, errores y exclusiones por señal.
- [Script reproducible](../../data/research/funding-calendar-h1-20260918/run_h1.py): descarga acotada, verificación y llamada a las funciones originales.

Desde la raíz del proyecto:

```powershell
.venv/Scripts/python.exe data/research/funding-calendar-h1-20260918/run_h1.py
```

La primera ejecución tardó **69,154 segundos** en este equipo. La carpeta de investigación ocupó **1.292.298 bytes** al terminar. ZIP, CHECKSUM y archivos comprimidos tienen exclusión local de Git; los artefactos conservan sus hashes para reproducción. Estos tiempos no estiman el costo del replay de trades.

Como control posterior, se verificaron **138 hashes** —fuentes API, calendarios, código, script y artefactos— y los **114 checksums** de calendarios. Se recontaron las 10.224 señales y 10.180 objetivos válidos, y se recalcularon directamente desde las páginas originales seis objetivos: primer evento, inicio de 2024 y último evento válido, para cada activo. Coincidieron con la evaluación guardada.

Una [verificación independiente adicional](../../data/research/funding-calendar-h1-20260918/independent-verification.json) recalculó los **10.224 pronósticos** con una fórmula vectorial y los **10.180 horizontes válidos**, y verificó **253 hashes** contando archivos de checksum. Las diferencias máximas fueron `6,94e-18` en pronósticos y `3,47e-18` en objetivos, compatibles con la representación numérica de las estadísticas. Los tres resúmenes agregados coincidieron. Este control no modificó el script ni el JSON original de resultados.

Este entregable aporta evidencia real para H1 y puede incorporarse a resultados preliminares. Los faltantes de marks, reglas y costos siguen siendo relevantes para la simulación económica; no impiden este cálculo de capacidad predictiva.

> Copia de consulta: enlace al informe corregido adaptado al paquete. El original íntegro está en `originales/basis_audit_report.txt`.

# Auditoría independiente del basis

**Conclusión: el basis predominantemente negativo queda confirmado contra las velas originales.**

Se contrastaron 4,380 observaciones únicas de mercado y 8,760 decisiones, con 96 ZIP originales locales y sus CHECKSUM de Binance. Las dos estrategias comparten la observación, pero conservan sus estados y decisiones separados. No se descargaron datos ni se usaron trades, aggTrades o datos subminuto.

Discrepancias de observación: 0. Discrepancias en decisiones: 0. Máximo error absoluto del basis persistido: `4.9706457925636007827788649706458E-28`, frente a tolerancia fija `1e-12`. Las diferencias no nulas provienen de la división Decimal del motor con 28 cifras significativas frente a las 60 del auditor. No se compara usando el Markdown redondeado a seis decimales; los límites operativos permanecen exactamente en cero y 0,005.

## Artefactos y versiones auditados

Informe de partida: `revision_dcf7d66e69aaf51cea4590ff`, creado 2026-09-19T16:38:08.216573+00:00. Era el informe más reciente al iniciar. Código de presentación: `26199980b9b1550d783e9b14d41fe18be93b35134d2460ebea0f354d621f7447`.

| Ventana UTC [inicio, fin) | Corrida principal | Código de simulación |
|---|---|---|
| 2022-09-01T00:00:00Z — 2023-09-01T00:00:00Z | run_f4151cc97937f3704d77fb14 | 4e78e13aa1618137f790a0253c43355b31fe184eaa9bfdac12b61ad6d2a129ac |
| 2025-09-01T00:00:00Z — 2026-09-01T00:00:00Z | run_519a165818e2cadce24bc873 | 4e78e13aa1618137f790a0253c43355b31fe184eaa9bfdac12b61ad6d2a129ac |

Los SHA-256 del parser, replay, modelos, estrategia, riesgo, configuración y diagnóstico actuales coinciden con los registrados por estas corridas. Los manifiestos originales, sus configuraciones efectivas y el código del auditor están preservados en `evidence_snapshot.zip`. `basis_audit_manifest.json` registra hashes de entradas, salidas y comando ejecutado.

## Cadena revisada

1. **Fuente original:** ZIP mensuales de `data.binance.vision/data/spot/monthly/klines/` y `data.binance.vision/data/futures/um/monthly/klines/`, exclusivamente `BTCUSDT` y `ETHUSDT`, intervalo `1m`. Se cotejó cada URL exacta, símbolo, mercado, archivo, checksum oficial guardado y hash del manifiesto. `um` identifica USD-M y los nombres sin sufijo de vencimiento identifican los perpetuos; no se utilizó COIN-M, markPriceKlines ni índices como precios de basis.
2. **Parser:** `src/crypto_carry/data/normalize.py::_kline_records`. Esquema original de 12 columnas, con apertura en columna 0, OHLC en 1–4, volumen base 5, cierre reportado 6 y volumen quote 7. El auditor usa `csv` y `zipfile` propios y la columna 4; no importa el parser ni `risk.basis`.
3. **Normalización:** `minute_bars` conserva OHLC y volúmenes como texto decimal exacto, `open_time` en ns UTC, `end_time=open_time+60s` y `available_at=end_time`. Se compararon precios, OHLC, actividad y tiempos originales contra los Parquet efectivamente incluidos en cada corrida, identificados por su hash.
4. **Selección:** `data/replay.py::_records` produce `MinuteBar`; `events.event_time` ordena por disponibilidad. `strategy.py::Backtest.process` actualiza `closed_bars`; `_signal_prices` elige el mismo símbolo y los mercados spot/futures. `models.MinuteBar.price` es el cierre, no el VWAP. `_fresh` exige intervalo alineado y actividad.
5. **Basis y filtros:** `risk.py::basis` calcula `F/S-1`; `entry_basis` acepta `0 <= basis <= 0.005`. `strategy.py::_entry` aplica funding sólo si está habilitado, y después basis. `diagnostics.signal_diagnostics` registra todas las condiciones y el primer bloqueo. El auditor recalcula el cociente directamente con Decimal de 60 cifras, sin fees, slippage, ajustes de cantidad ni anualización.
6. **Persistencia y reporte:** `signals.parquet` conserva `spot_price`, `futures_price`, intervalos, disponibilidad, `basis_raw`, `basis`, `filter_*`, `sequential_rejection` y `decision`. `execution_revision.py::_diagnostics` genera `diagnostics_summary.csv` y `diagnostic_quantiles.csv`; `_revision_report_lines` los presenta. La conciliación por campo queda en `basis_report_reconciliation.csv`.

El esquema y el cambio de unidad se contrastaron con la [documentación oficial de Binance Public Data](https://github.com/binance/binance-public-data). El CSV original no contiene el símbolo en cada fila: la identidad se demuestra con la ruta oficial, miembro del ZIP y manifiestos, no por la magnitud del precio.

## Tiempos, selección y cobertura

Spot temprano y USD-M usan milisegundos; spot desde enero de 2025 usa microsegundos. Se comprobó la unidad declarada contra magnitud, período y calendario. En fuentes ms, `close_time=end_time-1ms`; en spot us, `close_time=end_time-1us`. El motor adopta disponibilidad en el fin exclusivo común, sin confundirlo con el cierre reportado.

En cada decisión `t=tau+60s`, la vela esperada se obtuvo independientemente como `[floor(t/60s)*60s-60s, floor(t/60s)*60s)`. Si `tau=08:00:00.011`, se decide a `08:01:00.011` usando la vela `08:00–08:01` de ambos mercados. Su cierre ya estaba disponible a `08:01:00`, y no se usa la vela de ejecución posterior. La edad observada de las velas al decidir va de 0 a 29 ms. La señal no pierde los milisegundos originales del funding.

La grilla de evaluaciones se cotejó además contra los eventos de funding de entrada: no faltan ni se duplican decisiones de ninguna estrategia. Los joins son por símbolo, mercado y apertura UTC; nunca por número de fila. Se revisó orden estricto y ausencia de duplicados en las particiones leídas. Los huecos de marzo de 2023 constan en el inventario de fuentes; ninguno coincide con una observación de esta muestra de decisiones. No se rellenaron huecos.

| Ventana | Activo | Originales/N | Discrepancias | Mínimo | Mediana | Máximo | Error máx. |
|---|---|---|---|---|---|---|---|
| early | BTCUSDT | 1095/1095 | 0 | -0.001669121133 | -0.000429700029 | 0.001320379494 | 4.969E-28 |
| early | ETHUSDT | 1095/1095 | 0 | -0.003106294075 | -0.000440326899 | 0.001709181007 | 4.971E-28 |
| late | BTCUSDT | 1095/1095 | 0 | -0.000905579176 | -0.000469142477 | 0.000216821792 | 4.936E-28 |
| late | ETHUSDT | 1095/1095 | 0 | -0.002181301414 | -0.000476949766 | -0.000023865874 | 4.996E-29 |

| Ventana | Activo | Negativo | Cero | Positivo ≤0,005 | Elegible [0;0,005] | >0,005 |
|---|---|---|---|---|---|---|
| early | BTCUSDT | 1044 | 0 | 51 | 51 | 0 |
| early | ETHUSDT | 1006 | 3 | 86 | 89 | 0 |
| late | BTCUSDT | 1090 | 0 | 5 | 5 | 0 |
| late | ETHUSDT | 1095 | 0 | 0 | 0 | 0 |

**Cero también pertenece al intervalo elegible.** Para sumar categorías excluyentes se usan negativo, cero, positivo ≤0,005 y superior a 0,005; no se suma elegible otra vez. Estas frecuencias describen los 1.095 instantes de evaluación por activo y ventana, no todos los minutos del año. El signo del funding no se usó como prueba del signo del basis.

## Rechazos y defecto demostrado de presentación

| Ventana | Estrategia | Activo | N | Primer bloqueo o aceptación |
|---|---|---|---|---|
| early | conditional | BTCUSDT | 1095 | funding: 1095 |
| early | conditional | ETHUSDT | 1095 | accepted: 2; cooldown: 6; funding: 884; state_active: 203 |
| early | permanent | BTCUSDT | 1095 | accepted: 3; basis_negative: 373; cooldown: 6; state_active: 713 |
| early | permanent | ETHUSDT | 1095 | accepted: 3; basis_negative: 102; cooldown: 6; state_active: 984 |
| late | conditional | BTCUSDT | 1095 | funding: 1095 |
| late | conditional | ETHUSDT | 1095 | funding: 1095 |
| late | permanent | BTCUSDT | 1095 | accepted: 1; basis_negative: 1063; state_active: 31 |
| late | permanent | ETHUSDT | 1095 | basis_negative: 1095 |

En BTC tardío hay 1.090 basis negativos, pero sólo 1.063 bloqueos efectivos por basis en la permanente: 27 negativos ocurren cuando la posición ya está activa. De las cinco observaciones elegibles, una abre la posición y cuatro encuentran el estado activo. La condicional se bloquea antes por funding en sus 2.190 decisiones tardías. Un incumplimiento teórico no equivale necesariamente a una orden rechazada.

**Defecto confirmado:** el agregador del reporte incorporaba `filter_funding=fail` de la permanente en `filter_funding:reject` y en la unión `simultaneous_reject`, aun con `funding_filter_enabled=False`. El motor y su primer rechazo secuencial estaban correctos. La reproducción mínima contiene una entrada permanente con basis cero, funding bajo costos y ninguna otra condición incumplida: el reporte anterior la contaba como rechazo simultáneo. La prueba `test_disabled_funding_is_a_diagnostic_and_never_a_permanent_rejection` falló antes de la corrección y pasó después.

| Ventana | Activo | Campo del reporte | Antes | Auditado/después |
|---|---|---|---|---|
| early | BTCUSDT | filter_funding:reject | 1095 | 0 |
| early | BTCUSDT | simultaneous_reject | 1095 | 1092 |
| early | ETHUSDT | filter_funding:reject | 1087 | 0 |
| early | ETHUSDT | simultaneous_reject | 1094 | 1092 |
| late | BTCUSDT | filter_funding:reject | 1095 | 0 |
| late | BTCUSDT | simultaneous_reject | 1095 | 1094 |
| late | ETHUSDT | filter_funding:reject | 1095 | 0 |

Se corrigió únicamente la agregación y sus rótulos: funding omitido queda como `diagnostic_fail_not_applied`, fuera del conteo de rechazos; los rechazos secuenciales tienen su propio scope. No se modificaron velas, señales, precios, estrategia ni resultados económicos.

Informe corregido: [revision_eb5ed744b30836a39fd694fa](execution_revision_report.md). Discrepancias de conciliación del nuevo reporte: 0. Se regeneró el reporte desde las mismas diez corridas; **no se volvió a simular**. `report_preservation_comparison.csv` demuestra que los artefactos económicos y las identidades de las corridas permanecen iguales.

## Muestra y reproducción

`basis_audit_all.csv`: todas las observaciones de mercado, con registros originales, líneas físicas (base 1, incluyendo la cabecera cuando existe), fuente, checksum, campos normalizados y seleccionados por ambas estrategias. `basis_audit_decisions.csv`: decisiones separadas. Los identificadores de señal son referencias derivadas `run:signals.parquet:row=N`, ya que el archivo original no tiene una columna de ID individual de señal.

`basis_audit_sample.csv` contiene exactamente 20 observaciones por activo y ventana (80 total). Selección determinista: mínimo, máximo, cuatro más próximas a cero (empates por tiempo), y los lugares restantes repartidos uniformemente entre la primera y última evaluación. Los solapamientos se completan maximizando la distancia temporal a lo ya elegido. Cada fila conserva el motivo de selección. Ejemplos legibles:

| Ventana | Activo | Criterio | Decisión UTC | S original | F original | Basis |
|---|---|---|---|---|---|---|
| early | BTCUSDT | mínimo | 2022-11-10T00:01:00.006000000Z | 15882.61000000 | 15856.10 | -0.001669121133 |
| early | BTCUSDT | más próximo a cero | 2023-02-02T00:01:00.004000000Z | 23737.43000000 | 23737.30 | -0.000005476583 |
| early | ETHUSDT | mínimo | 2022-09-15T00:01:00.019000000Z | 1632.17000000 | 1627.10 | -0.003106294075 |
| early | ETHUSDT | más próximo a cero | 2023-02-09T08:01:00.006000000Z | 1631.61000000 | 1631.61 | 0.000000000000 |
| late | BTCUSDT | mínimo | 2026-03-04T16:01:00.000000000Z | 73444.71000000 | 73378.20 | -0.000905579176 |
| late | BTCUSDT | más próximo a cero | 2026-08-20T08:01:00.000000000Z | 69790.00000000 | 69788.80 | -0.000017194440 |
| late | ETHUSDT | mínimo | 2025-10-11T00:01:00.000000000Z | 3827.99000000 | 3819.64 | -0.002181301414 |
| late | ETHUSDT | más próximo a cero | 2026-08-22T00:01:00.000000000Z | 2514.05000000 | 2513.99 | -0.000023865874 |

Comando efectivamente ejecutado desde la raíz del proyecto:

```powershell
& 'C:\Users\pablo\Documentos\UCEMA\Tesina\Backtesting\.venv\Scripts\python.exe' 'data/research/basis-audit-20260919/verify_basis.py' '--root' 'D:\Backtesting' '--revision' 'revision_dcf7d66e69aaf51cea4590ff' '--corrected-revision' 'revision_eb5ed744b30836a39fd694fa'
```

Pruebas reproducibles:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/unit/test_basis_audit.py tests/unit/test_execution_revision.py -q --tb=short
```

Las pruebas cubren los cuatro cocientes calculables a mano del instructivo, límites inclusivos, unidades ms/us, disponibilidad, vela futura, desalineación, fuente faltante, duplicados, cambios de signo inferiores a la tolerancia y clasificación de funding no aplicado. El auditor no amplía su tolerancia para conseguir coincidencias.

## Límites

Esta auditoría verifica basis de entrada y su clasificación en los instantes persistidos; no vuelve a certificar EWMA, márgenes, sizing, rentabilidad, liquidaciones intraminuto ni cada renovación. Para el orden de otros filtros utiliza el estado persistido; no reconstruye toda la cartera. Los cierres spot y perpetuo pertenecen al mismo minuto, pero no prueban precios simultáneamente ejecutables ni bid/ask. La disponibilidad al fin del minuto es la convención explícita del proyecto, no una medición de latencia de publicación del exchange. La evidencia original es la versión descargada localmente, autenticada contra sus CHECKSUM guardados; no se volvió a descargar una versión posterior del archivo de Binance. Validar el basis no demuestra por sí solo la rentabilidad ni la corrección completa del backtest.

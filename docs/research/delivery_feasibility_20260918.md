# Factibilidad de entrega con un plazo de dos días

Auditoría del 18/09/2026. Inventario local observado a las 15:24 UTC; consultas HEAD a las 15:27 UTC. Alcance: lectura de configuración, código, manifiestos de C:, metadatos de seis carpetas conocidas de D: y cuatro consultas HEAD públicas. No se leyó ningún ZIP activo de D:, no se inició/interrumpió su descarga, no se normalizaron datos ni se ejecutó un backtest o una suite de pruebas. El único archivo escrito por esta auditoría es este informe.

**No hay evidencia que permita prometer el replay completo 2022–2026 en 48 horas.** Hay un entregable inmediato de investigación de funding y una muestra de precios preparada para ensayos; una simulación económica con supuestos necesita una ruta explícita distinta del baseline estricto. Las alternativas de menor tamaño existen, pero aún requieren adaptación y medición.

## Qué está disponible ahora

### C: muestra preparada y funding de investigación

Se leyeron los manifiestos actuales, sin regenerarlos:

| Insumo | Disponibilidad local | Alcance y limitación |
| --- | --- | --- |
| Trades BTC spot | 1.114.623 filas, 12 particiones | 01/01/2024 UTC. |
| Trades BTC USD-M | 2.197.331 filas, 22 particiones | Mismo día; discontinuidades de IDs pendientes. |
| Trades ETH spot | 536.670 filas, 6 particiones | Mismo día. |
| Trades ETH USD-M | 1.694.881 filas, 17 particiones | Mismo día; discontinuidades de IDs pendientes. |
| Marks de un minuto | 2.880 filas por activo, cuatro particiones en total | 31/12/2023 y 01/01/2024; incluye el cierre antecedente. |
| Funding normalizado de la muestra | 50 filas por activo | Ventana de preparación y muestra; es el conjunto de ejecución, no todo el histórico consultado. |
| Calendarios de funding en el manifiesto de descarga | Cuatro ZIP | Diciembre de 2023 y enero de 2024, ambos activos. |
| Respuestas amplias de investigación | 14 JSON; 6.684 eventos únicos por activo | Desde 26/07/2020 hasta 31/08/2026 16:00:00.001 UTC; 5.112 eventos económicos por activo y 2.005 sin settlement mark por activo. |
| Reglas ejecutables | Cero registros en `data/rules/history.json` | No hay ningún intervalo económico estricto habilitado. |

Los trades suman 5.543.505 filas. Los metadatos de tamaño suman 55.076.025 bytes de Parquet de trades activos. Estos son conteos de manifiesto, no una nueva lectura íntegra de todas las particiones. `data/manifests/coverage.json` conserva `incomplete_data`, con reglas faltantes para los cuatro mercados y discontinuidades de IDs en ambos Futures.

Las páginas amplias están en `data/research/funding-20260918T132612Z/page-000.json` a `page-013.json`. Esta auditoría volvió a contar filas, timestamps únicos y marks vacíos. Sus hashes y procedencia están en [funding_api_coverage.json](funding_api_coverage.json). **Consultar todas las tasas no verifica por sí solo los calendarios independientes**: el manifiesto de ejecución sólo contiene los cuatro calendarios mensuales indicados. El análisis amplio debe obtener/verificar los meses necesarios o declarar su menor nivel de evidencia.

### D: descarga parcial, todavía sin manifiesto final

La carpeta `D:\Backtesting\data` sólo contenía `raw`. No había `manifests/download.json`, `processed.json` ni reglas. La inspección de nombres y tamaños de ZIP completos dio:

| Carpeta | ZIP | Primer nombre fechado | Último nombre fechado | Bytes de ZIP |
| --- | ---: | --- | --- | ---: |
| spot/trades/BTCUSDT | 210 | 2020-08-11 | 2021-03-08 | 5.252.970.216 |
| futures/trades/BTCUSDT | 209 | 2020-08-11 | 2021-03-07 | 3.822.108.353 |
| futures/markPriceKlines/BTCUSDT | 176 | 2020-08-10 | 2021-03-07 | 6.725.220 |
| Las mismas tres series ETHUSDT | 0 | — | — | 0 |

No son rangos de cobertura certificados: primero/último nombre no descarta fechas ausentes y no se verificaron hashes ni CRC en esta auditoría. Es una fotografía que queda desactualizada mientras avanza la descarga. No había marks 2023-11…2026-08 disponibles para la auditoría de proxies. El descargador recorre un símbolo completo, por día y en orden spot/Futures/marks; luego sigue con el otro símbolo. No usa ZIP mensuales.

`preflight` tardó aproximadamente 1,65 segundos de pared y devolvió `blocked`: 13.424 objetos previstos, ausencia de manifiesto final y ausencia de reglas. Es una comprobación de metadatos, no una medición del motor. D: tenía 948.834.643.968 bytes libres; la consulta del sistema mostró aproximadamente 27,86 GiB de RAM física visible y 17,61 GiB libres. Ambos valores son instantáneos y no acreditan recursos suficientes para una corrida completa.

## Alternativas ordenadas por dependencia de trabajo adicional

1. **H1 sobre tasas y descripción de funding por períodos.** `forecast.forecast`, `evaluation.forecast_evaluation` y `h1_summary` trabajan con tasas, timestamps, intervalos y disponibilidad; no necesitan settlement marks, fills ni reglas de mercado. Se pueden reutilizar fuera del backtest, verificando calendario, antecedentes, retardo de 60 segundos y horizonte futuro completo. Esto permite avanzar sin esperar trades. Un resumen de tasas por régimen es descriptivo: no equivale a la H3 actual, que combina oportunidad elegible, basis, costos, frescura y resultados de carteras.
2. **Ensayo económico acotado con los trades existentes.** El 01/01/2024 ya tiene ambos activos y mercados; sirve para medir tiempo, RAM y diferencias bajo supuestos explícitos una vez implementada la ruta de investigación. Un día no alcanza para evaluar una tenencia/horizonte de 168 horas ni para sostener conclusiones anuales. Hoy no existe un comando válido que ejecute esa mezcla conservando la distinción histórica.
3. **Trades individuales del período económico, sin descargar preparación de precios desde 2020.** Para un escenario separado, los trades previos a 2022 no alimentan la ventana EWMA: sólo el funding requiere la preparación de 336+24 horas y antecedente. El replay de precios empieza en `start`, reteniendo un antecedente por flujo; marks exige el cierre anterior. Entre 11/08/2020 y 01/01/2022 hay 508 días de precios adicionales. Eliminar esa preparación de una descarga nueva puede reducir trabajo, pero no resuelve reglas ni marks de cobro. No se cambió la descarga original, expresamente solicitada completa.
4. **AggTrades en archivos mensuales.** Mantiene observaciones de precio/volumen mucho más finas que velas; puede reducir bytes y eventos. No es un formato soportado actualmente y no reconstruye todos los tiempos individuales. Debe ser otro escenario de ejecución, contrastado con trades individuales en una ventana común.
5. **Barras de un minuto más funding.** Reduce radicalmente el número de observaciones, pero cambia la resolución del modelo y exige definir fills, riesgo intraminuto, disponibilidad, timeouts y exposición entre patas. No puede conservar una afirmación de ejecución individual con un segundo entre patas.

Acortar el inicio económico a una fecha con settlement marks tampoco completa las reglas. Además, el validador estricto exige marks en el funding de preparación y su antecedente: comenzar el 01/11/2023 todavía incluye eventos sin mark de octubre. Diciembre de 2023 o enero de 2024 evitan ese problema particular con margen temporal, sujeto a verificar el resto de los datos; no corrigen los demás bloqueos.

## AggTrades y mensuales: medición y trabajo pendiente

Cuatro HEAD oficiales para enero de 2024, todos con HTTP 200; no se descargó el contenido:

| Par examinado | Trades individuales | AggTrades | Reducción observada |
| --- | ---: | ---: | ---: |
| BTCUSDT USD-M | 1.021.286.908 bytes | 522.743.749 bytes | 48,82 % |
| ETHUSDT spot | 383.895.949 bytes | 301.466.173 bytes | 21,47 % |

Objetos consultados: [BTC trades](https://data.binance.vision/data/futures/um/monthly/trades/BTCUSDT/BTCUSDT-trades-2024-01.zip), [BTC aggTrades](https://data.binance.vision/data/futures/um/monthly/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2024-01.zip), [ETH trades](https://data.binance.vision/data/spot/monthly/trades/ETHUSDT/ETHUSDT-trades-2024-01.zip) y [ETH aggTrades](https://data.binance.vision/data/spot/monthly/aggTrades/ETHUSDT/ETHUSDT-aggTrades-2024-01.zip). Son dos pares/mercados de un mes; no se extrapola ese ahorro al período completo ni se infiere proporcionalidad entre bytes y tiempo de CPU.

Binance publica ambos formatos diarios y mensuales, con esquemas diferentes y checksums. Los aggTrades incluyen identificador agregado y extremos de IDs individuales; spot cambia a microsegundos desde enero de 2025. El repositorio también registra una revisión histórica de aggTrades spot en 2022, por lo que no debe suponerse una convención idéntica para todos los años. [Documentación oficial](https://github.com/binance/binance-public-data).

La documentación USD-M actual describe agregación en 100 ms para mismo precio y lado tomador. Eso conserva más detalle que una vela, pero no acredita equivalencia con el primer trade posterior a una orden cuando el agregado cruza el instante de envío, la segunda pata o el vencimiento. Tampoco documenta por sí solo la política histórica de cada archivo. [Referencia USD-M](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data#compressedaggregate-trades-list).

Cambios concretos necesarios:

- `data/download.py:_archive_descriptors` sólo genera trades/marks diarios y funding mensual; no tiene selector mensual ni aggTrades.
- `data/normalize.py:_trade_rows` presupone columnas de trades individuales. Renombrar un ZIP aggTrades como trades interpretaría mal las columnas. Hace falta lector explícito, procedencia del agregado y controles propios, sin inventar IDs individuales.
- `data/normalize.py:_archive_date` usa los últimos diez caracteres del nombre; no admite correctamente un archivo `YYYY-MM`. Además asigna una única fecha a cada fuente. Importar trades mensuales exige particionar por fecha real, conservar unidades temporales y generar los mismos límites/fechas que espera el validador diario. Cambiar sólo la URL no basta.
- `data/validate.py` valida continuidad de IDs individuales. Un agregado necesita criterios de integridad propios; no corresponde desactivar esa comprobación para la ruta estricta.
- Los ZIP mensuales de trades conservan eventos individuales, pero reducen cantidad de solicitudes, no el número de eventos económicos. La referencia anterior de 210,421 GB corresponde a 224 ZIP mensuales de trades 2022–agosto de 2026 y excluye preparación y otros datasets; no es el tamaño de la descarga D: actual.

## Por qué no basta reproducir trades sólo en los momentos de decisión

`strategy.Backtest.process` actualiza último trade y volumen de 60 segundos, evalúa riesgo, vencimientos y órdenes en cada timestamp. `execution.eligible_trade` exige `submitted_at < event_time < deadline`, con deadline de 30 segundos por defecto. Los fills y la trayectoria posterior dependen de estos eventos. `NautilusAdapter` usa datos personalizados y tiene `trade_execution=False` y `bar_execution=False`: los fills los ejecuta el modelo de dominio.

El lector Parquet recorta particiones al intervalo solicitado, pero no posee un índice que permita buscar únicamente el primer trade elegible de cada orden y simultáneamente conservar todos los cruces de riesgo, frescura, volumen, liquidación y retry. Omitir trades entre decisiones cambia el modelo. Desarrollar un índice exacto y demostrar equivalencia es trabajo adicional, no un flag de velocidad existente.

Para barras 1m, `[2022-01-01, 2026-09-01)` tiene 1.704 días: 2.453.760 minutos por serie, **9.815.040 barras** para spot/Futures de dos activos y **4.907.520 marcas** adicionales si se conserva mark price 1m. Son conteos deterministas, no una medición de MB ni una garantía de duración. No se encontró loader/modelo de barras ejecutables; `data/reconcile.py` sólo las lee como referencia de auditoría.

## Separación mínima de un escenario con supuestos

No implementar mediante `--allow-incomplete` ni cambiando a mano `status=complete`. Los controles de hashes, tasas, calendario, timestamps y coherencia contable siguen siendo requisitos. El mínimo diseño revisable sería:

| Área | Situación actual | Extensión necesaria |
| --- | --- | --- |
| Perfil de investigación | `Config` rechaza campos desconocidos y fija el universo BTC/ETH. | Objeto/archivo separado con supuestos, versión, fuentes, método, alcance temporal y hash; incluirlo en identidad de corrida. Mantener `base.toml` y su contrato estricto. |
| Entrada y reglas | CLI sólo distingue backtest histórico y demo totalmente sintética. `RuleBook` tiene `allow_synthetic` interno, usado en demo. | Comando/ruta explícita de investigación. Fuente de reglas asumidas distinguida de evidencia histórica; conservar fechas observadas/publicadas reales y rango al que el modelo decide aplicar un supuesto. No convertir una observación actual en conocimiento pasado. |
| Funding aproximado | `Funding` admite mark ausente; el ledger bloquea cobros sin precio. | Transformación derivada fuera de crudos/Parquet originales, con clave símbolo+timestamp, mark original, proxy, procedencia y diagnóstico de error; mantener timestamps de disponibilidad. |
| Calidad | `validate_data` produce un estado estricto y escribe cobertura. | Informe separado de integridad, completitud observada y supuestos aceptados por el escenario; preservar todos los bloqueos estrictos. No llamar al validador actual sobre D: mientras escribe la descarga. |
| Reproducibilidad | `input_hashes` y checkpoints identifican datos, reglas, código y configuración. | Agregar hashes de perfil, derivaciones y política de ejecución; invalidar reanudación cuando cambien. `Backtest._rules_hash` ya incluye registros y `allow_synthetic`, pero no existe política de investigación. |
| Reportes | `write_run` sólo acepta `historical` o `synthetic`; títulos y juicios dependen de esos dos tipos. | Tipo explícito de investigación con supuestos en manifiesto, contexto, tablas, figuras y juicios; diferenciar ejecución terminada de certificación histórica. `full_baseline_coverage` no debe acreditar el baseline original. |

Puntos principales: [cli.py](../../src/crypto_carry/cli.py), [rules.py](../../src/crypto_carry/data/rules.py), [validate.py](../../src/crypto_carry/data/validate.py), [replay.py](../../src/crypto_carry/data/replay.py), [strategy.py](../../src/crypto_carry/strategy.py) y [reporting.py](../../src/crypto_carry/reporting.py). No hay actualmente un parámetro CLI de reglas simuladas que habilite precios históricos con las etiquetas correctas. Reutilizar `demo` cambiaría los propios precios a fixtures y no satisface ese objetivo.

## Bloqueos de escala y criterio para comprometer una entrega

- Normalización lee todos los objetos exitosos del manifiesto; `--scope sample` no limita esa primera fase. No hay reanudación rápida por archivo normalizado. Los originales se conservan y el presupuesto suma crudos, Parquet y temporales.
- El replay es incremental, pero convierte filas a diccionarios/Decimal y procesa todos los trades del intervalo. Ambas carteras se recorren por separado.
- `Backtest` conserva tablas en listas. Sólo `opportunities` puede acumular 4.907.520 filas por cartera para el período completo, 9.815.040 para ambas. Reportes convierten/copían filas y crean DataFrames; los checkpoints serializan el estado acumulado. No se midió RAM máxima a escala.
- `input_hashes` vuelve a leer todos los inputs de los manifiestos, incluso si el replay económico es una muestra. Cada sensibilidad revalida y vuelve a calcular hashes. No iniciar 30 escenarios antes de medir uno.
- Faltan tiempos separados de descarga restante, normalización, validación/hash, dos replays y reportes. Los HEAD miden tamaños; `preflight` mide metadatos; ninguno prueba rendimiento del motor. Los 5,54 millones de trades del día disponible no representan una tasa constante para todo el histórico.

El compromiso defendible en 48 horas es preparar primero las tablas de funding/H1 con cobertura declarada, concretar un perfil de supuestos y medir una corrida corta con datos existentes. Una ventana económica mayor queda condicionada al rendimiento observado y la cobertura que se termine verificando. La evaluación estricta completa y las 30 sensibilidades no tienen una estimación medida de finalización dentro del plazo.

Comprobación segura durante la descarga, desde la carpeta del proyecto:

```powershell
& '.\.venv\Scripts\python.exe' -B -m crypto_carry --root 'D:\Backtesting' preflight --config 'C:\Users\pablo\Documentos\UCEMA\Tesina\Backtesting\configs\download_full_d.toml'
Get-Content -LiteralPath '.\data\manifests\coverage.json'
Get-Content -LiteralPath '.\data\rules\history.json'
```

Estos comandos sólo inspeccionan; el primero informa bloqueos de preparación. `validate-data`, `backtest` y `report` sí escriben artefactos y no se ejecutaron para esta auditoría. Los pasos de normalización y corrida posteriores están documentados en [puesta_en_marcha.md](../puesta_en_marcha.md), sujetos a sus condiciones.

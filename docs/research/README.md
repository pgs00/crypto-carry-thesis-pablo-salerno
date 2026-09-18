# Investigación histórica y auditorías — 18/09/2026

Esta continuación se realizó mientras el usuario descargaba la historia completa en `D:\Backtesting`. Las consultas adicionales y auditorías usan una carpeta de investigación separada en C:. No se alteraron la descarga activa, los ZIP originales, la configuración económica ni el registro ejecutable de reglas históricas.

## Evidencia obtenida

| Tema | Resultado | Artefacto |
| --- | --- | --- |
| Comisiones | Intervalo exacto de la promoción BTCUSDT spot; tablas históricas VIP0; falta fechar el cambio taker Futures 0,04% → 0,05%. | [Comisiones](historical_fees.md), [hechos JSON](historical_fees.json) |
| Seguimiento de comisiones | Tabla archivada 31/05/2023 con taker Regular USDT 0,04 %; FAQ archivada 20/02/2024 con ejemplo BTCUSDT 0,05 %. Son observaciones de documentación, no fechas efectivas. | [Capturas y exclusiones](fees_followup_20260918.md), [evidencia JSON](fees_followup_20260918.json) |
| Filtros, margen y liquidación | Anuncios fechados, ocho tablas con 90 tramos, mínimos nocionales y una suspensión Spot. Persisten campos y vigencias sin evidencia suficiente. | [Reglas](historical_market_rules.md), [hechos JSON](historical_market_rules.json) |
| Seguimiento de reglas | Antecedentes oficiales 2020–2021 de filtros, margen y clearance; no completan nuevas reglas para 2022–2026. | [Hallazgos y límites](rules_followup_20260918.md), [hechos JSON](rules_followup_20260918.json) |
| Funding | 13.368 registros consultados; 2.005 cobros por activo sin mark dentro del período económico. | [Respuestas, hashes y cobertura](funding_api_coverage.json) |
| Seguimiento de funding | Inventario y nueva consulta completa de 4.010 eventos económicos: cero marks recuperados. En 12 cobros conocidos, dos aperturas de velas no coinciden con el mark de cobro. | [Investigación y alternativas](funding_followup_20260918.md), [evidencia JSON](funding_followup_20260918.json) |
| Trades de la muestra | Comparación exacta por minuto de conteos, cantidades, OHLC y suma de precio por cantidad; ambos activos concilian. Los saltos de IDs se conservan como diagnóstico. | [BTC](btcusdt_reconciliation.json), [ETH](ethusdt_reconciliation.json) |

Los JSON de reglas son inventarios parciales de evidencia. **No son snapshots ejecutables de RuleBook ni completan `data/rules/history.json`.** Una aprobación de un supuesto tampoco lo convertiría en evidencia histórica.

## Funding: faltante delimitado

Se consultó `/fapi/v1/fundingRate` para cada activo en `[2020-07-26T00:00:00Z, 2026-09-01T00:00:00Z)`, incluyendo preparación. Se guardaron las 14 respuestas HTTP originales, sus URL con parámetros, bytes y SHA-256. Total recibido: 1.583.680 bytes. Las páginas locales están referenciadas en `funding_api_coverage.json`.

Por activo:

- 6.684 tasas; 5.112 corresponden al período económico desde 2022.
- 3.577 marks vacíos en la historia consultada; 2.005 dentro del período económico.
- Último cobro sin mark: `2023-10-31T00:00:00.001Z`.
- Primer cobro con mark: `2023-10-31T08:00:00Z`.
- No aparecen marks ausentes después de ese primer valor en la consulta realizada.

El [changelog oficial USD-M](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/change-log) documenta la incorporación del campo `markPrice` en la entrada del 01/11/2023. La fecha del changelog y el primer evento disponible observado son hechos distintos. La [documentación del endpoint](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data#get-funding-rate-history) identifica el campo como precio asociado al cobro.

Las diferencias de hora nominal entre eventos son ocho horas en esta consulta; esto es un diagnóstico, no sustituye la comprobación independiente del calendario publicado ni modifica los timestamps efectivos. No se rellenaron los marks con cero, con el precio actual ni con velas. Una API key no añade un parámetro de reconstrucción de estos precios ausentes.

La evaluación estricta desde 2022 sigue necesitando otra fuente que acredite esos marks. Aceptar una aproximación o cambiar la ventana económica requeriría una decisión metodológica explícita del usuario. Tampoco basta resolver funding para certificar la muestra: siguen pendientes las reglas.

El [seguimiento posterior](funding_followup_20260918.md) deja cada faltante identificado para evaluar otras fuentes y demuestra con contraejemplos que las aperturas de velas de mark price no son un reemplazo exacto general. La investigación pública de funding y reglas no depende de finalizar la descarga de trades. Ningún mark faltante se rellenó en los inputs ejecutables.

## Trades: conciliación y anomalía identificada

Se contrastaron los ZIP originales del 01/01/2024 con los ZIP oficiales de `futures/um/daily/klines/<symbol>/1m/`, obtenidos con sus checksums. En los 1.440 minutos de cada activo coinciden exactamente los conteos, volumen base, volumen cotizado calculado como suma de `price × qty` y OHLC.

| Activo | Trades | Saltos / IDs ausentes | Filas con `quote_qty` diferente de `price × qty` |
| --- | ---: | ---: | ---: |
| BTCUSDT | 2.197.331 | 34 / 34 | 1 |
| ETHUSDT | 1.694.881 | 16 / 16 | 0 |

La fila BTC `4428495241`, a las `2024-01-01T20:44:23.751Z`, informa precio `43815.0`, cantidad `244.322` y `quote_qty=1.0704968`. El producto es `10704968.4300`. Al agregar los productos del minuto, el total es `113338551.55191` USDT, idéntico al ZIP de velas y a una consulta REST de ese minuto. La suma del campo `quote_qty` original es `102633584.1924068`. [Detalle y respuesta REST](btc_quote_discrepancy.json).

El normalizador del backtest utiliza precio y cantidad; no necesita sustituir esa fila ni modificar el ZIP. La primera auditoría exploratoria, que sumaba el campo original, se conserva en [trade_archive_reconciliation.json](trade_archive_reconciliation.json). La auditoría reproducible distingue ambos cálculos y enumera la anomalía.

La [documentación oficial de trades USD-M](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data#recent-trades-list) excluye del flujo público operaciones del fondo de seguro y ADL. Eso impide equiparar automáticamente cada salto numérico con una operación pública perdida; **no identifica la causa de cada uno de los 50 IDs de esta muestra**. Además, dos archivos de un mismo proveedor podrían compartir omisiones. Por esas razones, la auditoría no desactiva la validación estricta ni certifica cobertura histórica por sí sola.

## Reproducir la conciliación

Desde la raíz del proyecto, con los archivos de investigación ya descargados:

```powershell
& '.\.venv\Scripts\python.exe' -m crypto_carry.data.reconcile --trades 'data/raw/futures/trades/BTCUSDT/BTCUSDT-trades-2024-01-01.zip' --klines 'data/research/trades-2024-01-01/BTCUSDT-1m-2024-01-01.zip'
& '.\.venv\Scripts\python.exe' -m crypto_carry.data.reconcile --trades 'data/raw/futures/trades/ETHUSDT/ETHUSDT-trades-2024-01-01.zip' --klines 'data/research/trades-2024-01-01/ETHUSDT-1m-2024-01-01.zip'
```

El comando es offline y solo lee los ZIP. Emite JSON con hashes, intervalo comparado, diferencias y ejemplos acotados. Código de salida 0 indica conciliación de los agregados comparados; 2 indica diferencias. `historical_certified` siempre es `false`: este comando no ejecuta un backtest ni modifica sus controles. La memoria crece por minuto observado, no por cada trade leído.

La auditoría exige el esquema y ancho de columnas esperados, vuelve a comprobar la identidad de los archivos después de leerlos y falla si la aritmética Decimal pierde precisión. Sus 14 pruebas pasaron, junto con la suite completa de 107 pruebas. Los resultados de ambos archivos reales se reprodujeron sin diferencias después de la revisión independiente.

## Próximos pasos y decisiones

Se puede seguir sin credenciales ni nuevas confirmaciones con la búsqueda de capturas históricas, la fecha de transición de comisiones, conciliaciones adicionales y las pruebas del software. Antes de incorporar reglas parciales al motor falta resolver su vigencia, disponibilidad temporal y efecto sobre posiciones anteriores.

No se adoptaron tarifas constantes supuestas, ausencia de suspensiones por descarte, deducciones históricas ficticias ni sustitutos del mark de cobro. Si la evidencia sigue faltando, las opciones a evaluar con el usuario son conservar el requisito estricto, limitar un estudio adicional a una ventana verificable o definir un escenario de aproximaciones expresamente separado. Ninguna opción convierte esta descarga en una evaluación histórica completa automáticamente.

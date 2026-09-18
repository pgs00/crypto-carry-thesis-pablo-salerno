# Acceso a proveedores para recuperar los marks de funding

Investigación y pruebas públicas del 18/09/2026. Se descargaron muestras pequeñas en C:, sin credenciales. El backtest no incorpora estos precios como marks de cobro.

## Qué se consiguió

**Se obtuvieron marks difundidos cada segundo de enero de 2022, pero no se recuperó ningún mark de cobro certificado de los 4.010 faltantes.** La distinción se comprobó con datos, además de revisar documentación.

Tardis permite consultar gratuitamente el primer día de cada mes mediante su [API de replay](https://docs.tardis.dev/api/http-api-reference). Su [archivo de Binance Futures](https://docs.tardis.dev/historical-data-details/binance-futures) incluye el canal `markPrice@1s`. Se consultaron ocho ventanas de dos minutos, para BTCUSDT y ETHUSDT, alrededor de las 08:00 y 16:00 UTC de estos días:

- 2022-01-01: cuatro eventos cuyo mark de cobro falta en Binance.
- 2023-11-01, 2024-01-01 y 2024-02-01: doce eventos con mark de cobro publicado por Binance, usados como contraste.

Las ocho consultas respondieron HTTP 200. Se guardaron 427.200 bytes de respuestas descomprimidas, URL, fecha de consulta, cabeceras y SHA-256. El [resultado completo](../../data/research/funding-provider-access-20260918/sample-comparison.json) conserva cada candidato, timestamp de emisión y recepción, diferencia temporal y comparación decimal. El [índice de evidencia](funding_provider_access_20260918.json) también referencia las copias de documentación consultadas.

## Resultado del contraste

Se conservaron los milisegundos originales de `fundingTime`; no se redondeó la hora del cobro. La comparación de precios usa `Decimal`.

| Comprobación sobre los doce cobros conocidos | Coincidencias exactas |
|---|---:|
| Último mensaje emitido antes o en el instante del cobro | 9/12 |
| Primer mensaje emitido después o en el instante del cobro | 9/12 |
| Precio exacto presente en algún mensaje de los dos minutos | 11/12 |

El tercer criterio es solo diagnóstico: buscar retrospectivamente cualquier coincidencia no constituye una regla válida para imputar datos desconocidos.

Contraejemplo: **ETHUSDT, 2023-11-01 a las 16:00:00.000 UTC**.

| Dato | Precio |
|---|---:|
| `markPrice` del cobro en la respuesta oficial de funding | 1792.96543725 |
| `p` del mensaje `markPriceUpdate` con el mismo timestamp de emisión | 1792.96073137 |

El mark exacto no aparece en ningún mensaje de esa ventana. La diferencia es pequeña, pero basta para refutar la equivalencia exacta. Esta selección limitada no estima el error de todo el histórico ni su efecto sobre el resultado económico. La [FAQ de Binance consultada](https://www.binance.com/en-AE/support/faq/detail/360033525031) también distingue el precio calculado para funding del emitido periódicamente.

## Qué acceso adicional puede ayudar

Tardis es una fuente comprobada de **precios observados**, útil para contrastes y para investigar reglas mediante otros canales. Para aceptar sus datos como liquidaciones exactas faltaría una exportación distinta, cuya procedencia vincule cada precio al cobro. Comprar más mensajes del mismo canal no resuelve por sí solo esa diferencia. Los permisos y la vía de metadata se analizan en [el informe de proveedores de reglas](metadata_provider_access_20260918.md).

También se revisaron alternativas:

| Fuente | Qué documenta | Limitación para este faltante |
|---|---|---|
| [Amberdata: funding](https://docs.amberdata.io/http/market/futures-funding-rates) | Tasas aplicadas o previstas, hora, intervalo e indicador de tasa efectiva | El esquema publicado no incluye el precio usado en el cobro. |
| [Amberdata: funding acumulado](https://docs.amberdata.io/data-dictionary/analytics/derivatives/fundingrealized) | Métricas de funding realizado/acumulado | La descripción no acredita una cantidad nominal y unidades que permitan reconstruir el mark exacto. Requiere aclaración del proveedor. |
| [Coin Metrics: funding](https://gitbook-docs.coinmetrics.io/market-data/market-data-overview/market-funding-rates) | Tasa realizada y timestamps | El esquema no contiene un mark de liquidación de funding. |
| [Kaiko: métricas de derivados](https://docs.kaiko.com/rest-api/analytics/derivatives-risk-indicators/exchange-provided-metrics) | Funding y otras métricas según el contrato | Su campo `settlement_price` para futuros/opciones se describe como liquidación al final del día, no como precio del cobro de funding del perpetuo. |

Esto evalúa los endpoints documentados, no demuestra que los proveedores carezcan de archivos internos o exportaciones a medida. Antes de pedir una clave o contratar, deben confirmar ese campo, su origen y su cobertura.

## Condición de aceptación

La fuente candidata debe entregar `symbol`, timestamp efectivo con precisión original, tasa y **precio realmente utilizado para liquidar funding**, junto con procedencia, tratamiento de correcciones y cobertura. Se validará primero contra los cobros conocidos, incluido el contraejemplo anterior, y después contra el [inventario exacto de eventos ausentes](../../data/research/funding-followup-20260918/missing-economic-settlement-marks.json).

Los mensajes de 2022 descargados quedan como evidencia separada. No completan el requisito estricto y no se copian a los inputs operativos.

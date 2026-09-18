# Acceso a metadatos históricos: proveedores

Revisión: 2026-09-18. Objetivo: reglas BTCUSDT/ETHUSDT Spot y perpetuos USD-M para `[2022-01-01, 2026-09-01)`. Complementa `historical_market_rules.md` y `rules_followup_20260918.md`; no modifica reglas ejecutables, motor, configuración ni datasets. El JSON adjunto registra endpoints, pruebas y limitaciones.

**Acceso concreto para evaluar: Tardis Data API con RAW `!contractInfo` de Binance Futures y Instruments Metadata API.** Hay una vía documentada para recuperar cambios de tramos desde **2023-07-24**. Todavía no recuperamos un mensaje histórico BTC/ETH con tramos: las consultas gratuitas fueron vacías y la fecha del cambio conocido requiere autenticación. No comprar una suscripción suponiendo que entrega toda la historia de reglas.

## 1. Tardis RAW: la vía útil para tramos

[Tardis documenta](https://docs.tardis.dev/historical-data-details/binance-futures) el canal `!contractInfo` desde **2023-07-24**. La API reproduce mensajes nativos; el registro añade hora local de captura. [HTTP API](https://docs.tardis.dev/api/http-api-reference): cada GET devuelve un minuto, usa `Accept-Encoding: gzip`; sin clave permite el primer día de cada mes. Con licencia, autenticación `Authorization: Bearer <TARDIS_DATA_API_KEY>`.

Consulta de aceptación, anclada en el cambio de tramos ya localizado en el [anuncio Binance de diciembre de 2023](https://www.binance.com/en/support/announcement/detail/d75c5ca94f704e96a6a4e55ffddfd65d):

```text
GET https://api.tardis.dev/v1/data-feeds/binance-futures
from=2023-12-24T09:35:00.000Z
filters=[{"channel":"!contractInfo"}]
offset=0
```

El [esquema oficial Binance](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/ws-streams/market#contract-info-stream) publica:

| Campo | Significado |
| --- | --- |
| `E`, `s`, `ct`, `cs` | Hora del evento, símbolo, tipo y estado contractual. |
| `bks[].bs` | Número del tramo. |
| `bks[].bnf`, `bks[].bnc` | Piso y techo nocional del tramo. |
| `bks[].mmr` | Tasa de mantenimiento. |
| `bks[].cf` | Auxiliar de cálculo publicado; candidato a contrastar con el `cum` requerido. |
| `bks[].mi`, `bks[].ma` | Apalancamiento mínimo/máximo del tramo. |

Binance dice que el stream se emite con cambios de contrato y que `bks` sólo aparece cuando se actualizan tramos. **No es un snapshot inicial garantizado.** El esquema actual debe cotejarse con el payload histórico; no asumir retroactivamente campos añadidos después. `E` y la captura local ayudan a separar evento y observación, pero no resuelven por sí solos la vigencia jurídica, retrasos o cohortes de posiciones preservadas.

Lo que falta: baseline de cada contrato, integridad de la cadena, todo 2022 y el tramo hasta julio de 2023, filtros de órdenes, comisiones ordinarias, liquidation fee y su base/excepciones. Los caps de posición no sustituyen límites por orden.

## 2. Tardis Instruments Metadata: apoyo parcial

Endpoints objetivo:

```text
https://api.tardis.dev/v1/instruments/binance/BTCUSDT
https://api.tardis.dev/v1/instruments/binance/ETHUSDT
https://api.tardis.dev/v1/instruments/binance-futures/BTCUSDT
https://api.tardis.dev/v1/instruments/binance-futures/ETHUSDT
```

La [documentación actual](https://docs.tardis.dev/api/instruments-metadata-api) contiene `priceIncrement`, `amountIncrement`, `minTradeAmount`, `minNotional` y fees maker/taker. `changes[].until` marca cuándo dejaron de valer los valores anteriores. También admite cambios en mínimos y fees; el extracto antiguo del buscador omite estos campos.

**Sólo garantizan cambios completos para `contractMultiplier`**; los demás se registran sin garantía exhaustiva. Fees son orientativas, no una serie certificada VIP0. No hay campos documentados para maxQty, maxNotional, banderas MARKET, tramos o clearance. `availableSince` describe disponibilidad de metadatos Tardis; no prueba baseline completo ni continuidad de reglas.

Prueba sin clave: BTCUSDT Spot y Futures devolvieron **401** por requisito Pro/Business. La muestra gratuita **BitMEX XBTUSD** devolvió **200**, con cambios de cantidad/mínimo (2021), tick (2024) y fees (2024). Confirma funcionamiento y formato; **no aporta valores Binance**. Sin respuesta autenticada no está verificada la fecha inicial de cambios de los cuatro instrumentos objetivo.

## 3. Permisos, demo y criterio antes de pagar

[Planes y prueba Tardis](https://docs.tardis.dev/faq/billing-and-subscriptions): Academic/Solo sólo habilitan CSV; Pro/Business incluyen RAW y metadata. La prueba dura 30 días, sin tarjeta ni conversión automática, y asigna **7–14 días recientes aleatorios**: no garantiza acceso al cambio de diciembre de 2023. La documentación no demuestra aquí si una clave de prueba habilita metadata Binance.

Para RAW, la suscripción anual Pro ofrece cuatro años; Business anual toda la historia disponible. Una Pro iniciada el 2026-09-18 no abarcaría enero de 2022 por esa regla, aunque sí el inicio documentado de `!contractInfo`. La facturación mensual sólo incluye cuatro meses. Estas son condiciones de acceso, no prueba de cobertura de todos los campos. No se verificó una cotización numérica ni se creó cuenta/clave/suscripción.

**Qué pedir:** una clave de datos Tardis con acceso explícito a `binance-futures` RAW y fecha **2023-12-24**, más metadata de `binance` y `binance-futures`. Si ofrecen sólo la prueba reciente estándar, sirve para verificar formato pero no para aceptar cobertura histórica. No hace falta una API de trading de Binance para estas consultas.

Con esa clave, primero consultar `GET https://api.tardis.dev/v1/api-key-info` y comprobar permisos/rango; luego ejecutar cuatro GET de metadata y la ventana de aceptación `[2023-12-24 09:20, 09:51) UTC`, minuto a minuto. Conservar respuesta nativa, fecha de captura y hash. El filtro del canal es global; filtrar BTCUSDT/ETHUSDT dentro del payload.

Aceptar la vía para tiers sólo tras recibir `bks` histórico no vacío de BTC/ETH y contrastarlo con las tablas oficiales. Un minuto vacío no implica ausencia del canal ni ausencia de cambio; no usarlo para validar una serie constante. Separadamente, revisar si metadata devuelve cambios de los campos objetivo y baseline anterior a cada período. Este ensayo autoriza una evaluación técnica, no llenar automáticamente el RuleBook.

## 4. Otros proveedores examinados

| Proveedor / fuente oficial | Endpoint y campos pertinentes | Límite para este objetivo |
| --- | --- | --- |
| [CoinAPI símbolos activos](https://www.coinapi.io/products/market-data-api/docs/rest-api/metadata/symbols/exchange_id/active/get) y [símbolos históricos](https://www.coinapi.io/products/market-data-api/docs/rest-api/metadata/symbols/exchange_id/history/get) | `/v1/symbols/{exchange_id}/active`, `/history`; `price_precision`, `size_precision`, identidad y cobertura de market data. Header `X-CoinAPI-Key`. | Advertencia expresa: las precisiones de datos no siempre son precisiones de trading, con Binance como ejemplo. `/history` enumera símbolos retirados, no versiones temporales de reglas. No justifica pedir una clave para cerrar estos faltantes. Prueba sin clave: 401. |
| [Amberdata Spot Reference](https://docs.amberdata.io/http/market/spot-exchanges-reference) / [Futures Reference](https://docs.amberdata.io/http/market/futures-exchanges-reference) | `/markets/{spot,futures}/exchanges/reference`; `precisionPrice`, `precisionVolume`, `limitsVolumeMin/Max`, `limitsMarketMin/Max`, `limitsCostMin/Max`; `includeOriginalReference=true` solicita objeto nativo. Header `x-api-key`. | No se documenta selector de versión histórica. En Futures, `startDate/endDate` filtran **expiración**. `includeInactive` añade contratos retirados. No se verificó cadena histórica, fecha inicial ni cadencia de cambios; no pedir clave bajo la suposición de que lo actual es histórico. Prueba Futures sin clave: 403. |
| [Kaiko contract details](https://docs.kaiko.com/rest-api/reference-data/derivatives-contract-details) / [V3 beta](https://docs.kaiko.com/rest-api/misc-custom-and-legacy-endpoints/derivatives-contract-details-v3) | `/v2/data/derivatives.v2/reference`, V3 `/v3/data/derivatives/reference`; tamaño/unidad contractual, listado, funding interval; V3 agrega estado/última actualización. Header `X-Api-Key`. | Ningún campo documentado para tick, step, min/max orden, fees VIP0, tiers o clearance. Las fechas son filtros de vida del contrato, no historial de reglas de perpetuos Binance. No pedir clave para estos campos. |
| [CoinDesk Data / CCData Futures](https://developers.coindesk.com/documentation/data-api/futures) | `/futures/v1/latest/instrument/metadata`; endpoint de metadata **latest**. Consulta concreta BTCUSDT/ETHUSDT, grupos GENERAL/STATUS, sin clave: 401. | No se verificó endpoint histórico de reglas. Las series de funding, trades, precios o liquidaciones enumeradas no acreditan fees ni tiers. No pedir clave para este objetivo sin muestra histórica específica. |

No se afirma que los proveedores no puedan ofrecer contratos especiales; se delimita lo demostrado por endpoints públicos/documentados. No se les enviaron mensajes.

## 5. Pruebas de lectura realizadas

El [JSON](metadata_provider_access_20260918.json) conserva URLs y resultados. RAW `!contractInfo` sin clave devolvió 200 con gzip de 20 bytes y cuerpo descomprimido vacío para 2024-01-01 00:00 y tres minutos 2024-10-01 12:29–12:31. La fecha 2023-12-24 09:35 devolvió 401 con explicación de acceso gratuito restringido al día 1. No se obtuvo payload histórico objetivo ni se infirió un valor de regla de esas respuestas.

Las pruebas fueron GET acotados, sin credenciales; ningún cuerpo recibido excedió 400 KB. Sólo se crean estos dos archivos de investigación, por debajo de 5 MB. La lectura previa de los dos informes evitó repetir anuncios, Wayback y endpoints Binance ya agotados.

# Binance: acceso a historia faltante y utilidad de una API key

Consulta: 2026-09-18. BTCUSDT y ETHUSDT Spot y perpetuos USD-M; ventana económica `[2022-01-01, 2026-09-01)`. Investigación documental de acceso, sin solicitudes autenticadas ni cambios al método.

**Crear una API key ordinaria no tiene, en las fuentes oficiales revisadas, una vía documentada que complete los marks de funding faltantes o las reglas históricas.** Sí habilita registros privados y consultas actuales. Encontré dos vías concretas para escalar la búsqueda: soporte técnico de datos de mercado y el informe de funding del Report Center, este último condicionado a actividad histórica de la cuenta y a comprobar sus columnas. Ninguna fue presentada como recuperación confirmada.

El [seguimiento existente](funding_followup_20260918.md) ya identifica 2.005 eventos por activo, 4.010 en total, sin precio de cobro entre `2022-01-01T00:00:00.006Z` y `2023-10-31T00:00:00.001Z`. No se volvió a consultar ese historial vacío. Los faltantes de reglas siguen definidos en [historical_market_rules.md](historical_market_rules.md). Esta investigación recuperó **cero marks de cobro y cero snapshots históricos completos**. El [JSON adjunto](binance_historical_access_20260918.json) conserva fuentes, acceso, condiciones y conclusiones por vía.

## Qué permite cada vía

| Vía oficial | Acceso y contenido | Utilidad para el faltante |
| --- | --- | --- |
| Binance Data Collection | Archivo público diario/mensual; no requiere key para descargar los ZIP. [Repositorio oficial](https://github.com/binance/binance-public-data). | La key no agrega columnas a esos archivos. La comprobación previa de los ZIP de funding permanece válida para la muestra examinada. |
| `GET /fapi/v1/fundingRate` | Mercado público; su esquema incluye `fundingTime`, `fundingRate` y `markPrice` asociado al cobro. [Market Data](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data). | No se documenta una variante autenticada con mayor cobertura de ese campo. Esta es una conclusión sobre el contrato publicado, no una prueba de inexistencia de archivos internos. |
| `GET /fapi/v1/income` | Firmado; movimientos de la cuenta, incluido `FUNDING_FEE`; retención de tres meses. El esquema no contiene mark ni cantidad de posición. [Account](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/account). | No cubre 2022–2023 ni documenta el precio global de cobro. |
| `GET /fapi/v1/income/asyn`, luego `/income/asyn/id` | Exportación privada; intervalos de hasta un año, cinco solicitudes mensuales compartidas con la interfaz, enlace de siete días. [Account](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/account). | La documentación de estos endpoints entrega metadatos/enlace; no acredita columnas con el mark exacto ni fecha mínima conservada. No confundir un año por solicitud con un año de retención total. |
| `GET /fapi/v1/trade/asyn`, luego `/trade/asyn/id` | Trades propios anteriores a seis meses; hasta un año por solicitud y cinco solicitudes al mes, compartidas con la web. [Binance Academy](https://www.binance.com/en/academy/articles/how-to-get-account-trade-history-via-api). | Registros de ejecución/comisión de esa cuenta. El precio de ejecución no es el mark de funding ni una tabla general de tarifas. |
| `GET /fapi/v1/order/asyn`, luego `/order/asyn/id` | Órdenes propias; diez solicitudes mensuales y hasta un año por intervalo. [Account](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/account). El [anuncio de 2023](https://www.binance.com/en/support/announcement/detail/6811b3e0da104d77b6fb178e053b887c) habilitó historia antigua. | No reconstruye reglas universales ni eventos en los que la cuenta no operó. |
| `GET /sapi/v1/accountSnapshot` | Firmado; snapshots diarios propios, último mes, intervalo menor a 30 días. Incluye un `markPrice` de posición. [Wallet Account](https://developers.binance.com/en/docs/catalog/core-trading-wallet/api/rest-api/account). | Ese mark no está documentado como precio de cada cobro; tampoco cubre la ventana antigua. |
| `GET /fapi/v1/leverageBracket` y `/commissionRate` | Datos del usuario; sin selector histórico. `timestamp` firma la hora actual; brackets admite `notionalCoef` individual. [Account](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/account). | Una key permite observar hoy; no viajar a 2022 cambiando `timestamp`. |
| Spot `GET /api/v3/account/commission` y `/myTrades` | Tasas actuales de la cuenta y ejecuciones propias, respectivamente. [REST oficial](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#query-commission-rates-user_data). | Las comisiones efectivamente pagadas pueden documentar operaciones concretas, no toda la tarifa VIP0 histórica. |
| Spot `/api/v3/exchangeInfo`; USD-M `/fapi/v1/exchangeInfo` | Información actual; el segundo incluye `liquidationFee`. [Spot](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#exchange-information), [USD-M](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data). | No hay selector de fecha en estos contratos. Una key no acredita filtros, tasas de liquidación ni vigencias anteriores. |

Los antiguos trades públicos tampoco justifican crear una key: Binance [retiró de `/fapi/v1/historicalTrades` los datos anteriores al 2025-03-01](https://www.binance.com/en/support/announcement/detail/f04e986e02464015b3e85d5ef76cbb2a), con efecto el 2025-03-03, y remite al archivo público. Spot mantiene un [endpoint público de trades antiguos](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#old-trade-lookup). Esos precios siguen siendo de operaciones, no de liquidación de funding.

## Exportación útil que sí está documentada

El [Report Center de Binance VIP](https://www.binance.com/en/support/faq/detail/efe336a96f704afdb939905ad3adba21) permite CSV de **Funding Fee / USD-M Futures** de la cuenta principal o sus subcuentas; anuncia fecha mínima `2019-09-08`, sujeta a la existencia de actividad propia. Se accede en la web por `VIP Portal → Service and Solutions → Report Center → Report Generator`. Un usuario no VIP puede solicitar whitelist a Customer Service; la FAQ pide esperar dos días laborables para sincronizar datos.

La FAQ **no especifica todas las columnas del CSV**. Antes de atribuirle utilidad para los 4.010 eventos hay que verificar si exporta el mark utilizado por el motor en cada cobro y su precisión. Si la cuenta no tenía posiciones entonces, abrir una cuenta o crear una key hoy no genera esos registros. El informe podría aportar controles particulares si contiene los campos necesarios; no se ha demostrado cobertura global.

También existen exportaciones web de [órdenes Futures con período personalizado anterior a tres meses](https://www.binance.com/en/support/faq/detail/e21b95dc590e4c13b8f8bdcc9bbc4f82) y de [transacciones Spot con rango antiguo personalizado](https://www.binance.com/en/support/faq/detail/990afa0a0a9341f78e7a9298a9575163). No requieren entregar una key para obtener un archivo desde la propia cuenta.

## Programa histórico de order book: antecedente, vigencia sin confirmar

La [guía oficial de agosto de 2023](https://raw.githubusercontent.com/binance/binance-public-data/e8cdb38250d443e8b948f6cf7e37207614a7ad43/Futures_Order_Book_Download/README.md) describía cuenta Futures y key en whitelist para `T_DEPTH`, `S_DEPTH` y `T_DEPTH_BACKFILL`; intervalos menores a siete días. El esquema era profundidad L2. `S_DEPTH` se limitaba allí a BTCUSDT; `T_DEPTH_BACKFILL` llevaba detenido desde julio de 2021. Su [ejemplo oficial](https://raw.githubusercontent.com/binance/binance-public-data/e8cdb38250d443e8b948f6cf7e37207614a7ad43/Futures_Order_Book_Download/Futures-order-book-Level2-data-download.py) usaba `POST /sapi/v1/futuresHistDataId` y `GET /sapi/v1/downloadLink`.

Otro [esquema oficial, versión del 2024-10-08](https://github.com/binance/binance-api-swagger/blob/b6efbd19f529f1fbcdb9a4f5a042ce69a641cfb9/spot_api.yaml) documenta `GET /sapi/v1/futures/histDataLink`, firmado, con `symbol`, `dataType=T_DEPTH|S_DEPTH`, `startTime` y `endTime`, y devuelve enlaces por día. No documenta un tipo de archivo de marks internos, exchangeInfo, brackets ni tarifas.

La carpeta de la primera guía fue [eliminada del repositorio el 2024-07-25](https://github.com/binance/binance-public-data/commit/fdc72a94b481536dee32ed394585939326630fd4). En esta consulta las FAQ antiguas de descarga devolvieron artículo inexistente y la antigua landing no fue recuperable. Esto **no prueba que el servicio esté cancelado**; sí impide prometer sus requisitos o funcionamiento actuales con esas referencias. No se confirmó una condición vigente de “VIP1 basta”, una tarifa, ni un programa académico que entregue los campos requeridos. La autenticación sola no demuestra autorización de whitelist.

## Siguiente gestión concreta

Enviar, cuando el usuario lo autorice, el siguiente pedido a [Binance Chat](https://www.binance.com/en/chat), solicitando derivación al equipo de Futures Market Data/API. El repositorio oficial también [indica su sección Issues para preguntas de datos](https://github.com/binance/binance-public-data#issuequestion); esta ruta sería una publicación pública separada. **No se envió ningún mensaje.** El objetivo de la gestión es identificar una exportación exacta y su muestra antes de crear credenciales o contratar acceso.

### Borrador para soporte, sin enviar

Subject: Academic research — official historical funding settlement marks and market-rule versions, BTCUSDT / ETHUSDT

Hello Binance Futures Market Data / API team,

I am preparing an academic backtest for BTCUSDT and ETHUSDT USD-M perpetuals and Spot over 2022-01-01 00:00:00 UTC to 2026-09-01 00:00:00 UTC (end exclusive). Could you identify the official API, downloadable dataset or support export that supplies the following historical records?

1. Exact funding settlement marks for every BTCUSDT and ETHUSDT event from 2022-01-01 through the event at 2023-10-31 00:00:00.001 UTC. Our complete public `/fapi/v1/fundingRate` responses contain 2,005 empty `markPrice` values per symbol. The first missing event is `1640995200006`; the last is `1698710400001`. We can provide an event inventory with symbol, original millisecond `fundingTime` and decimal `fundingRate`.

   Required fields: symbol, original event timestamp, funding rate, and the exact mark used internally to calculate that funding charge, including decimal precision and provenance. Please confirm whether this value is the settlement-engine mark rather than a 1-second broadcast mark or OHLC candle value. As a control, the public endpoint gives BTCUSDT `42173.49474823` and ETHUSDT `2293.07001515` at 2023-12-31 00:00:00.000 UTC; the corresponding minute opens differ.

2. Versioned market rules covering the full research window: Spot/Futures exchangeInfo filters (including MARKET applicability flags), USD-M leverage/maintenance brackets with floor, cap, maintenance rate and cumulative maintenance amount, ordinary VIP0 maker/taker fees and symbol-wide exceptions, and liquidation-fee rates, assessment basis and whether normal trading commission additionally applies. Please include effective timestamps, publication/availability timestamps where retained, and how changes affected already open positions/orders. We need the baseline in force at the start and all subsequent revisions, including relevant trading suspensions.

Please provide the precise endpoint or export name, earliest retained date, schema and a small sample, account/VIP/whitelist requirements, and any price or licensing conditions. We are not requesting private records of other users. If only a custom market-data export can provide this, please route this request to the responsible team; if unavailable, please explicitly identify which fields are unavailable.

Separately, does the VIP Report Center USD-M Funding Fee CSV include the internal settlement mark and position quantity for each funding event? Please provide its column definitions and clarify whether it is limited to the requesting account's actual historical positions. We understand account income/trade history does not by itself provide a market-wide mark series.

Thank you.

## Alcance de la verificación

Se revisaron documentos oficiales, esquemas y versiones del repositorio; no se probaron endpoints privados, whitelist ni interfaces con sesión. Una documentación disponible hoy no prueba su publicación histórica. No se modificaron datasets, archivos en D:, código, configuración ni Git. Solo se crearon este informe y su JSON de evidencia.

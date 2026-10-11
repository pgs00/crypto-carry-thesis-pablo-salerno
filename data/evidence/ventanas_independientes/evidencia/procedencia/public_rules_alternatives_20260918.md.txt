# Alternativas públicas para reglas Binance — 18/09/2026

**Se recuperaron archivos públicos concretos con filtros de BTCUSDT y ETHUSDT, accesibles sin cuenta ni contacto con proveedores. Sirven como evidencia auxiliar y para diseñar escenarios explícitos; no completan una historia de reglas de producción entre 2022-01-01 y 2026-09-01.** La alternativa ejecutable para el plazo de dos días es un estudio de carry con reglas constantes declaradas y sensibilidad de costos/riesgo. Este informe no implementa ni certifica esa alternativa.

El [JSON](public_rules_alternatives_20260918.json) conserva URLs, hashes, resultados HTTP, contenido de dos fixtures y extractos de los demás archivos. Es evidencia de investigación, no una entrada de RuleBook. Se revisaron los cinco informes previos solicitados; no se repitieron consultas pagas de Tardis, pedidos de soporte ni búsquedas de Wayback ya realizadas.

## Archivos que sí se obtuvieron

| Fuente pública | Evidencia temporal real | Contenido y utilidad | Límite |
|---|---|---|---|
| [CCXT, archivo inmutable](https://github.com/ccxt/ccxt/blob/fbec4993ce0171b08691611281b9410397059333/ts/src/test/static/markets/binance.json) | Commit `fbec4993...`, 2023-10-31 16:59:26 UTC | Los cuatro instrumentos; filtros nativos dentro de `info`. GET 200, 64.554 bytes. | Es un fixture de software, sin manifiesto de captura ni entorno de adquisición. El commit no fecha la vigencia del exchange. |
| [Nautilus Spot](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/4dad2702599d35fd0d7a8d50b944f733d518b7dc/tests/integration_tests/adapters/binance/resources/http_responses/http_spot_market_exchange_info.json) | `serverTime` interno: 2021-10-22 22:41:05.856 UTC. Versión de repositorio: 2022-12-30. | Dos símbolos objetivo con filtros separados LOT_SIZE/MARKET_LOT_SIZE. GET 200, 4.190 bytes. | El timestamp está dentro de un dato de prueba; no se verificó captura original de producción. Es anterior a la muestra. |
| [Nautilus USD-M](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/4dad2702599d35fd0d7a8d50b944f733d518b7dc/tests/integration_tests/adapters/binance/resources/http_responses/http_futures_market_exchange_info.json) | `serverTime` interno: 2022-02-19 01:20:11.962 UTC. Versión de repositorio: 2022-12-30. | BTC/ETH perpetuos y un trimestral. GET 200, 6.641 bytes. | Entorno desconocido y parámetros distintos de otras evidencias. No adoptar como reglas históricas de producción. |
| [QuantConnect LEAN](https://raw.githubusercontent.com/QuantConnect/Lean/b8768ae27419073acdf1dfb17b3853d6e336f7d0/Data/symbol-properties/symbol-properties-database.csv) | Commit `b8768ae2...`, 2021-10-14 14:57:48 UTC | BTC/ETH Spot: tick 0,01; lot 0,00001 / 0,0001; minimum_order_size 10. GET 200, 210.615 bytes. | Base de propiedades de un simulador; no conserva aquí todas las reglas nativas ni su vigencia. No se recuperaron filas USD-M de esa versión. |

La fecha de un commit demuestra qué versión del archivo conserva el repositorio. No demuestra cuándo se consultó Binance, si se usó testnet, si se editaron valores para pruebas ni cuánto duró una regla. Un `serverTime` incrustado tampoco autentica por sí solo una captura.

Se comprobó que [las pruebas de Nautilus](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/4dad2702599d35fd0d7a8d50b944f733d518b7dc/tests/integration_tests/adapters/binance/test_providers.py) sustituyen el cliente HTTP por esos fixtures. Además, [un cambio del 19/02/2022](https://github.com/nautechsystems/nautilus_trader/commit/130f3cd850fa870d467aaa78ce57c5719cc52b14) agrega un contrato trimestral sin reconstruir el sobre completo: el archivo puede reunir partes editadas en momentos diferentes. No se ejecutó código de esos repositorios.

## Valores auxiliares de CCXT: útiles, pero sin fecha efectiva

El archivo de octubre de 2023 contiene estas magnitudes; se conserva su procedencia de fixture, sin ascenderlas a observaciones verificadas de Binance:

| Mercado | Tick | LOT_SIZE: mínimo / step / máximo | MARKET_LOT_SIZE: mínimo / step / máximo | Nocional |
|---|---|---|---|---|
| BTC Spot | 0,01 | 0,00001 / 0,00001 / 9.000 | 0 / 0 / 128,52621715 | NOTIONAL: mínimo 5, máximo 9.000.000; aplica mínimo a MARKET, máximo no. |
| ETH Spot | 0,01 | 0,0001 / 0,0001 / 9.000 | 0 / 0 / 3.277,54882761 | Igual al BTC Spot. |
| BTC USD-M | 0,1 | 0,001 / 0,001 / 1.000 | 0,001 / 0,001 / 120 | MIN_NOTIONAL 5. |
| ETH USD-M | 0,01 | 0,001 / 0,001 / 10.000 | 0,001 / 0,001 / 2.000 | MIN_NOTIONAL 5. |

Los filtros son más ricos que los seis escalares de orden del RuleBook actual. No se debe convertir el step cero de MARKET_LOT_SIZE en una precisión cero, ni copiar el máximo nocional Spot como restricción de MARKET cuando su bandera dice lo contrario. Esta observación sirve para revisar el modelo; no completa el historial.

El `liquidationFee` de CCXT es 0,012500 para ambos perpetuos. Nautilus muestra 0,012000 para BTC y 0,030000 para ETH, con mínimos nocionales 10. **No se recomienda usar ninguna de esas tasas como tasa histórica de producción**: no se validó el origen y son distintos de los antecedentes oficiales estudiados. Las comisiones normalizadas `maker/taker` de una biblioteca tampoco acreditan VIP0 o promociones en su fecha de commit.

## Otras vías probadas

- **Atlas:** el [repositorio](https://github.com/aperiodic-io/atlas) anuncia snapshots diarios. Se descargaron [Futures](https://raw.githubusercontent.com/aperiodic-io/atlas/main/atlas/data/binance-futures.json) y [Spot](https://raw.githubusercontent.com/aperiodic-io/atlas/main/atlas/data/binance-spot.json), ambos HTTP 200. Los registros BTC/ETH contienen identidad, disponibilidad y, para Futures, tamaño contractual; **no contienen filtros, fees, tiers ni clearance**. El repositorio se creó el 01/03/2026. Sus `first_capture` anteriores son disponibilidad del instrumento, no fechas de reglas.
- **Common Crawl:** dos consultas exactas al índice, Futures en CC-MAIN-2024-05 y Spot en CC-MAIN-2023-50, devolvieron 504 y 502. No se obtuvo ningún registro de índice ni WARC. Son fallos de acceso; no prueban que no existan capturas. Para el plazo actual, esta vía no entregó datos.
- **Kaggle / Zenodo:** las búsquedas acotadas llevaron a [OHLCV](https://www.kaggle.com/datasets/andreidiaconescu/binancepricedata/versions/3) y [VWAP](https://zenodo.org/records/7749449), sin un archivo de reglas demostrado. No se descargaron grandes datasets de precios para un faltante de metadatos.
- **Otros repositorios:** un fixture de binance-rs respondió 200, pero contiene ETHBTC/LTCBTC/BNBBTC; no los pares objetivo. Dos búsquedas GitHub devolvieron 403 y grep.app 429. No se interpreta un bloqueo de búsqueda como inexistencia de datos.
- **Stratmill:** su [blog](https://stratmill.com/blog/point-in-time-universe-crypto-perps/) menciona un archivo de snapshots, pero no se recuperó un payload público ni un endpoint histórico documentado de autoservicio. No constituye una fuente disponible demostrada.

Ninguna de estas vías resuelve la continuidad de tramos, la transición exacta de taker Futures 0,04% a 0,05%, la base/excepciones del cargo de liquidación o el calendario operativo completo.

## Propuesta metodológica disponible hoy

**Presentar el resultado como carry en precios y funding históricos bajo costos y restricciones constantes explícitos.** La pregunta cambia: estima el comportamiento bajo condiciones de ejecución declaradas; no reconstruye todas las condiciones históricas de Binance.

1. **Costos.** Corrida base: taker Spot 0,10% y Futures 0,05%; alternativa Futures 0,04%. Son tasas observadas en las [fuentes ya recuperadas](fees_followup_20260918.md), sostenidas deliberadamente durante toda la muestra. Un estrés adicional, por ejemplo Futures 0,10%, debe llamarse supuesto de estrés. La promoción BTC Spot de fechas oficiales puede agregarse como sensibilidad separada, sin inventar el corte de Futures. Para un round trip de cuatro legs y nocionales iguales, 10+5+5+10 = 30 bps del nocional emparejado; con Futures 4 bps son 28. Es sólo la aritmética de fees, antes de funding, variación de nocionales y ejecución.

2. **Filtros constantes.** Un escenario ilustrativo puede usar ticks Spot 0,01, Futures BTC 0,1 / ETH 0,01; steps Spot BTC 0,00001 / ETH 0,0001 y Futures 0,001. Mínimos nocionales declarados: Spot 10; BTC Futures 100; ETH Futures 20. Estos últimos son restricciones mantenidas por diseño, no fechas históricas reconstruidas. Comparar contra mínimos menores y medir órdenes rechazadas/polvo. El [cambio real de tick BTC en febrero de 2022](historical_market_rules.md) obliga a reconocer que el escenario constante difiere del mercado de ese comienzo. Más restricciones no garantizan menor P&L por la dependencia de la trayectoria.

3. **Mantenimiento y liquidación.** Comparar curvas completas de los anuncios ya transcritos como escenarios de toda la muestra, y una curva de estrés declarada. Preservar caps, tasas y deducciones por tramo; no extrapolar la primera tasa al nocional total. Reportar máximo nocional, tramos atravesados, menor excedente de margen y eventos de liquidación bajo cada curva. Sólo si ninguna corrida probada liquida, el importe del cargo de liquidación resulta inmaterial para esas corridas. El apalancamiento 2x no demuestra por sí mismo ese resultado. Si hay eventos, variar cargo, base y comisión ordinaria y mostrar su efecto.

4. **Verificación económica.** Además de repetir el backtest completo, recalcular fees sobre un mismo ledger para separar el efecto directo del cambio de trayectoria. Registrar holgura de filtros de cada orden, incluida la salida y el polvo; un nocional inicial de 3.000 USDT por activo no garantiza que todas las órdenes futuras estén lejos del mínimo. La propuesta complementa el análisis de datos de mercado y no sustituye los faltantes de mark/execution que se estudian por separado.

5. **Procedencia.** Guardar la parametrización asumida en un escenario separado y mantener sus fechas de consulta/publicación reales. No rotularla `verified` ni retrofechar una captura actual como conocida en 2022. Los archivos y etiquetas deben distinguir el intervalo simulado del intervalo histórico probado.

No se cambiaron código, configuración, RuleBook, datasets ni archivos de D:. Sólo se agregan los dos archivos de este informe. No se creó cuenta, clave ni compra, y no se enviaron mensajes a proveedores.


# Reglas históricas de Binance: evidencia parcial

Consulta: 2026-09-18. Alcance: BTCUSDT y ETHUSDT, Spot sin crédito y perpetuos USDⓈ-M con margen aislado y apalancamiento 2x; período [2022-01-01, 2026-09-01), prioridad 2024-01-01. Las comisiones VIP0 ordinarias se investigan por separado.

**Resultado:** se localizaron anuncios oficiales con cambios fechados y tablas anteriores/nuevas. La cobertura todavía no permite crear ningún snapshot completo de mercado verificable para toda la muestra. No se modificaron el motor, `data/rules/history.json`, los datasets ni la descarga.

[historical_market_rules.json](historical_market_rules.json) conserva 20 referencias, siete eventos parciales y ocho tablas de mantenimiento (90 tramos). Es un inventario de investigación; **no tiene el formato de entrada de RuleBook**. Las deducciones se distinguen de los valores publicados.

## Qué se pudo establecer

Las horas de vigencia indicadas abajo aparecen expresamente en UTC en el texto de los anuncios. Las horas de publicación se conservan como aparecen en la página: el encabezado renderizado no declara su zona horaria. No deben convertirse a UTC silenciosamente para una serie intradía estricta. “Por” una hora significa una fecha límite de implementación; una ventana aproximada no equivale a un cambio atómico.

| Campo / mercado | Publicación mostrada | Vigencia anunciada (UTC) | Hecho documentado |
| --- | --- | --- | --- |
| Step Spot, antecedente anterior a la muestra | 2021-08-12 15:57 | 2021-08-26 06:00 | BTCUSDT: 0.000001 → 0.00001 BTC; ETHUSDT: 0.00001 → 0.0001 ETH. Es la tabla de **step**, no la de tick. [Anuncio](https://www.binance.com/en/support/announcement/detail/6925d618ab6b47e2936cc4614eaad64b). |
| Tick BTCUSDT perpetuo | 2021-12-31 06:45 | 2022-02-15 03:30 | 0.01 → 0.1 USDT; preserva órdenes existentes. La ruta inglesa general redirigió; el mismo artículo en en-AU expuso el cuerpo inglés. [Anuncio](https://www.binance.com/en-AU/support/announcement/detail/81e6795b0bae49828cbd52479094a987). |
| Mínimo nocional Spot, pares cotizados en USDT | 2023-08-24 02:05 | Por 2023-08-31 03:00 | 10 → 5 USDT, aplicable al conjunto de pares USDT. No altera órdenes existentes. [Anuncio](https://www.binance.com/en-AE/support/announcement/detail/c4706c73b805423a8d36be948e297603). |
| Mínimo nocional perpetuos | 2023-10-27 12:40 | Por 2023-11-02 10:00 | BTCUSDT: 5 → 100 USDT; ETHUSDT: 5 → 20 USDT. El texto fue enmendado el 2023-10-30 sobre Grid. [Anuncio](https://www.binance.com/en/support/announcement/detail/e4384cba297a4bd2a154be644d5d76f9). |
| Mínimo nocional BTCUSDT perpetuo | 2026-04-09 06:14 | Inicio 2026-04-14 06:30; duración aproximada 4 h | 100 → 50 USDT; preserva órdenes existentes. El cuerpo inglés fue accesible en en-KZ. [Anuncio](https://www.binance.com/en-KZ/support/announcement/detail/10999fd17dc045de801c0c78ab29e6fc). |

Estos eventos no prueban continuidad entre cambios ni ausencia de otros cambios. La fila “Before” prueba un valor anterior al ajuste descrito, pero no establece desde qué fecha regía. Tampoco demuestra que `minQty=stepSize`.

## Mantenimiento y máximo de posición

Los artículos siguientes incluyen las tablas completas anteriores y nuevas. El JSON transcribe los tramos **nuevos** relevantes; los cinco valores de cada fila son `floor`, `cap`, tasa decimal, deducción derivada y máximo apalancamiento inicial.

| Fuente oficial | Publicación mostrada | Vigencia (UTC) | Tratamiento de posiciones anteriores |
| --- | --- | --- | --- |
| [ETH, 2022-09-13](https://www.binance.com/en/support/announcement/detail/56ba139dd19249acb4f9470c3d98020d) | 2022-09-13 03:05 | 2022-09-13 07:00 | Afectadas. El primer tramo nuevo abarca hasta 250,000 USDT, con tasa 0.0065. |
| [BTC y ETH, diciembre de 2023](https://www.binance.com/en/support/announcement/detail/d75c5ca94f704e96a6a4e55ffddfd65d) | 2024-01-02 13:50 | 2023-12-24 09:35 | No afectadas. Publicación posterior a la muestra prioritaria. |
| [BTC y ETH, mayo de 2024](https://www.binance.com/en/support/announcement/detail/aa735cd2d8bd4e7bb092179cf086e486) | 2024-05-27 06:00 | 2024-05-28 10:30, aproximadamente 30 min | No afectadas. |
| [BTC, junio de 2025](https://www.binance.com/en-PH/support/announcement/detail/e778988edec446038ad536bcb0c8d460) | 2025-06-14 14:08 | 2025-06-17 06:30, aproximadamente 1 h | Afectadas. Primer cap: 50,000 → 300,000 USDT; siguiente cap: 600,000 → 800,000. |
| [BTC y ETH, agosto de 2025](https://www.binance.com/en/support/announcement/detail/8e428625ebeb4cc7ae8678026846095c) | 2025-08-17 03:31; enmiendas 08-18 y 08-25 | 2025-08-19 06:30, aproximadamente 1 h | Afectadas. Aumenta el máximo del primer tramo de 125x a 150x; conserva caps y tasas de las tablas anteriores del propio anuncio. |

Para el cambio de diciembre de 2023, ambos primeros tramos nuevos terminan en 50,000 USDT y tienen tasa 0.004. A 2x, el máximo de posición publicado es 800,000,000 USDT para BTC y 500,000,000 para ETH. **Usar 2x no significa aplicar el mantenimiento del tramo rotulado 2x a una posición pequeña**: ese tramo describe el máximo apalancamiento permitido a posiciones de ese tamaño. Son límites de posición; no se pueden convertir automáticamente en un `max_notional` por orden.

La evidencia de diciembre permite una reconstrucción retrospectiva, pero no prueba que ese contenido estuviera publicado el 2024-01-01. La API pudo mostrar la nueva regla antes; no se recuperó una captura contemporánea. Por ello `known_from` queda sin resolver, separado de la vigencia, y no se fija arbitrariamente en el 2023-12-24.

La deducción no figura en estos anuncios. La documentación actual define `MM = nocional × tasa − Maintenance Amount` y explica los tramos. En el JSON se calcula `D[0]=0`, `D[i]=D[i-1]+floor[i]×(rate[i]−rate[i-1])`, **suponiendo mantenimiento continuo entre tramos**. Es una reconstrucción matemática, no un campo histórico publicado ni un `cum` histórico recuperado. [Margen, actualizado 2026-03-27](https://www.binance.com/en/support/faq/detail/360033162192); [cálculo de liquidación, actualizado 2025-12-31](https://www.binance.com/en/support/faq/detail/b3c689c1f50a44cabb3a84e663b81d93).

No se cerró la cadena completa de cambios desde 2022. Por ejemplo, el cap inicial de ETH era 50,000 en mayo de 2024 y aparece como 300,000 antes del ajuste de agosto de 2025; falta la fecha del cambio intermedio. La FAQ actual de margen también contempla ajustes pequeños sin anuncio. No se puede presentar una búsqueda de anuncios como registro exhaustivo.

## Liquidación

Un [anuncio fechado de 2020](https://www.binance.com/en/support/announcement/detail/41d8a353103c4fe18bf25c403bf7af3b), publicado el 2020-11-23 06:42 y efectivo a las 07:00 UTC, cambió la tasa de liquidación BTCUSDT de 0.003 a 0.005 y ETHUSDT de 0.005 a 0.0075. Es un antecedente; no certifica que esas tasas persistieran durante 2022–2026.

La [FAQ actual de cargos](https://www.binance.com/en/support/faq/detail/98488a516eb84e3eb34605683dffd554), publicada 2024-05-29 y actualizada 2026-01-05, calcula el cargo USDⓈ-M sobre cantidad de contratos por precio de ejecución. Esto apoya hoy la interpretación `execution_notional`, pero no demuestra su vigencia en enero de 2024. La lista de tipos de cargo no resuelve de forma histórica e inequívoca si además corresponde la comisión ordinaria en cada liquidación: `liquidation_regular_fee` sigue pendiente.

El [protocolo actual](https://www.binance.com/en/support/faq/detail/360033525271), actualizado 2026-01-04, distingue liquidación, órdenes IOC y posiciones en quiebra; contempla una excepción al cobro para estas últimas. Una única tasa y un booleano no representan por sí solos todos esos casos. No se adoptaron las versiones actuales como prueba del pasado ni se convirtió la fecha de creación 2019 de la FAQ en fecha de vigencia de su contenido actual.

## Operatividad

Binance documenta una suspensión Spot el **2023-03-24 desde 11:27 hasta 14:00 UTC**. El inicio consta en el [informe oficial del incidente](https://www.binance.com/en/blog/from-our-ceo/6789340645608890113); la reapertura en el [anuncio publicado a las 13:38](https://www.binance.com/en/support/announcement/detail/813a31506e9f478ea8c1058b425df87a). El anuncio fue aclarado el 2023-05-16 para especificar Spot. Esta es evidencia para `operational=false` en ese intervalo, no para un cierre general de Futures. No se recuperó el aviso contemporáneo del inicio con hora exacta de publicación.

No se elaboró un calendario exhaustivo de incidentes, restricciones regionales ni cambios de estado por símbolo. La presencia de trades no certifica disponibilidad de todas las operaciones; ausencia de trades tampoco demuestra suspensión. No se asigna `operational=true` al resto del período por descarte.

## Cobertura pendiente de la muestra 2024-01-01

| Campo | Estado de la evidencia |
| --- | --- |
| Tick BTC Futures | Cambio histórico localizado; continuidad hasta la muestra no demostrada. |
| Tick Spot BTC/ETH y tick ETH Futures | Sin captura histórica suficiente en esta investigación. |
| Step Spot | Antecedente de 2021; continuidad y aplicación a órdenes MARKET pendientes. |
| Step Futures; min/max qty de ambos mercados | Sin valores históricos completos verificados. |
| Min notional | Cambios 2023 documentados; faltan continuidad y banderas de aplicación a MARKET. |
| Max notional | Sin filtro histórico de orden; no usar caps de posición como sustituto. |
| Tiers | Tablas retrospectivas del cambio de diciembre; deducciones derivadas y conocimiento temporal pendiente. |
| Liquidation fee / basis / regular fee | Antecedente antiguo y explicaciones actuales; intervalo histórico incompleto. |
| Operational | Incidente puntual documentado; calendario completo pendiente. |

La [documentación actual de filtros Spot](https://developers.binance.com/en/docs/products/spot/filters) distingue `LOT_SIZE`, `MARKET_LOT_SIZE`, `MIN_NOTIONAL` y `NOTIONAL`, con banderas para su aplicación a órdenes MARKET. Sus ejemplos son ejemplos de esquema, no snapshots BTC/ETH. También hay restricciones de precio dinámicas; los campos estáticos seleccionados no representan todas las reglas de aceptación.

La [API de brackets](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/account) es USER_DATA y firmada, con ajustes posibles por usuario (`notionalCoef`). Su `timestamp` autentica la consulta; no selecciona una fecha histórica. [Exchange Information Futures](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information) se define como información actual. Una consulta de hoy no resuelve estas lagunas.

## Consecuencia para la integración

`src/crypto_carry/data/rules.py` admite únicamente snapshots completos, con todos los campos y vigencia/conocimiento independientes. No sería correcto completar las ausencias con parámetros sintéticos o actuales y etiquetar el conjunto como histórico verificado. Los eventos de órdenes o posiciones preservadas también requieren distinguir cohortes; una sustitución global de la regla por fecha puede alterar posiciones que el anuncio excluye.

No hace falta una confirmación del usuario para conservar estos hallazgos y continuar investigando. Para ejecutar la muestra con faltantes sí se necesita evidencia adicional, o una decisión metodológica explícita de aceptar supuestos y etiquetar el resultado como tal. La confirmación no convierte un dato faltante en evidencia.

Próxima evidencia útil: capturas de `exchangeInfo` y brackets guardadas durante la muestra, archivos de reglas fechados con procedencia y versiones archivadas de los anuncios/FAQ. No se pidieron credenciales: las APIs actuales, incluso autenticadas, no restituyen el pasado.


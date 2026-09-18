# Seguimiento de comisiones históricas — 18/09/2026

Ventana económica: `[2022-01-01T00:00:00Z, 2026-09-01T00:00:00Z)`. BTCUSDT y ETHUSDT spot y perpetuos USDT-M; VIP0 fijo, sin BNB, referidos ni programas especiales. Complementa [historical_fees.md](historical_fees.md); el [JSON contiguo](fees_followup_20260918.json) contiene metadatos, extractos y búsquedas fallidas.

**Resultado: nueva evidencia histórica recuperada, pero todavía no hay una fecha efectiva UTC verificable para el cambio Futures taker 0,04 % → 0,05 %.** No se generaron intervalos de reglas ejecutables ni se modificaron código, configuraciones, datos o `data/rules/history.json`.

## Evidencia nueva de las tarifas Futures

Se recuperó contenido real de capturas de páginas oficiales de Binance conservadas por Internet Archive. No se usó solamente el índice de capturas.

| ID | Captura UTC | Tipo de fuente y lectura | Alcance |
|---|---|---|---|
| A1 | 2023-05-31 22:47:44 | [Tabla oficial archivada](https://web.archive.org/web/20230531224744id_/https://www.binance.com/en/fee/futureFee): Regular, columna USDT, maker **0,0200 %**, taker **0,0400 %**. | Observación directa de la tarifa base publicada. |
| A2 | 2023-06-02 17:31:20 | [FAQ oficial archivada](https://web.archive.org/web/20230602173120id_/https://www.binance.com/en/support/faq/binance-futures-fee-structure-fee-calculations-360033544231): ejemplo BTCUSDT, maker **0,02 %**, taker **0,040 %**; calcula 4,0416 USDT sobre 10.104 USDT. | Ejemplo educativo, sin anuncio de vigencia. |
| A3 | 2024-02-20 06:41:15 | [Misma FAQ archivada](https://web.archive.org/web/20240220064115id_/https://www.binance.com/en/support/faq/binance-futures-fee-structure-fee-calculations-360033544231): ejemplo BTCUSDT, maker **0,02 %**, taker **0,05 %**; calcula 5,052 USDT sobre 10.104 USDT. | Prueba que la documentación ya mostraba 0,05 % en febrero de 2024, antes del blog de noviembre de 2025 hallado anteriormente. |

A1 también contiene datos de renderizado del servidor: `futureFee`, `level=0`, `makerCommission=0.0002`, `takerCommission=0.0004`. La fila visible distingue USDT de BUSD y las columnas con descuento BNB. En A2/A3 se leyó específicamente el apartado USD-M con BTCUSDT, separado del ejemplo COIN-M precedente.

**Estas observaciones acotan dónde buscar el cambio de documentación; no fijan el corte operativo de comisiones.** La FAQ podría haberse actualizado con demora y no se descartaron cambios intermedios. No corresponde rellenar automáticamente el período entre capturas ni adoptar el 20/02/2024 como comienzo del 0,05 %.

Los encabezados de la misma FAQ además varían: A2 muestra `2020-06-11 07:01` y A3 muestra `2019-09-09 13:39`. No explicitan zona horaria. Son evidencia de que una fecha de cabecera no debe interpretarse como vigencia de la tasa. Los timestamps UTC de la tabla anterior provienen de `Memento-Datetime`; las fechas HTTP del servidor original se preservan aparte.

## Comprobaciones adicionales de alcance

| ID / fuente oficial | Publicación mostrada | Vigencia anunciada UTC | Resultado para el perfil |
|---|---|---|---|
| X1 — [Promo taker altcoins spot/margin](https://www.binance.com/en/support/announcement/detail/8fbe902e90ec477780c18b98a5544acb) | 2024-05-14 07:00 | Desde 2024-05-21 00:00, hasta nuevo aviso | La lista inicial de 20 pares no contiene BTCUSDT ni ETHUSDT; sí ETCUSDT. No aplicar su taker Regular 0,0975 % a ETH. |
| X2 — [Promo BTC/U](https://www.binance.com/en-AE/support/announcement/detail/fe2b0d2853004943aba45f2e87a4081c) | 2026-04-10 09:00 | 2026-04-17 00:00 a 2026-07-16 23:59 | U significa United Stables. No es BTCUSDT. Se descartó una publicación de tercero en Square que confundía ambos pares. |
| X3 — [Actualización de elegibilidad VIP](https://www.binance.com/en/support/announcement/detail/4f379b9ab6314eff8fe02babfe255825) | 2026-03-18 08:00 | Cronograma general: 2026-03-19 23:59 | El cambio USDT taker 0,04 % → 0,05 % de esa tabla corresponde a **VIP1**, no VIP0. La página declara una edición de 2026-09-10 sobre otro umbral. |
| X4 — [Zero maker Futures VIP6–8](https://www.binance.com/en/support/announcement/detail/2c161ebe662a41edbd1233f76fcc7c08) | 2024-08-05 10:31 | 2024-08-07 10:30 a 2024-10-16 10:30 | Excluida por nivel VIP. |
| X5 — [Taker Program 2025](https://www.binance.com/en/support/announcement/detail/bec831262e4b4a49b021e6f4030921be) | 2025-07-31 07:00 | Aproximadamente desde 2025-08-12 07:00 | Requiere solicitud y elegibilidad; no es un descuento general VIP0. El 0,05 % que figura en sus criterios es cuota de volumen, no tasa de comisión. |

X1 remite a una [lista mutable de promociones](https://www.binance.com/en/fee/tradingPromote) y advierte que puede cambiarla. La exclusión inicial de BTC/ETH **no certifica todas sus revisiones posteriores**. La extracción pública actual de esa lista no devolvió una tabla de pares; queda un hueco concreto de cobertura.

X2 termina con precisión de minuto en el anuncio. No se inventó un extremo exclusivo con precisión de segundo. La URL inglesa normal redirigió al índice; la versión oficial `en-AE` sí devolvió el artículo en inglés.

## Fuentes rechazadas como anclas de fecha

- El [blog sobre apalancamiento](https://www.binance.com/en/blog/futures/421499824684902446), con cabecera 2021-07-29, hoy menciona taker 0,05 % pero computa 20 USDT sobre 50.000 USDT; a esa tasa serían 25 USDT. No sirve para fechar el 0,05 % en 2021.
- El [blog de costos maker/taker](https://www.binance.com/en/blog/futures/421499824684902239), con fecha 2025-04-09, mezcla tasas que parecen incorporar BNB, ejemplos USDC y montos USDT, y totales inconsistentes. No se utilizó para reconstruir la tarifa base.

## Vías exploradas y límites

Se probaron búsquedas nuevas en inglés y chino sobre cambio de comisiones USDT-M, tarifas Regular y promociones BTC/ETH; devolvieron principalmente programas especiales, otros márgenes y publicaciones de terceros. No apareció un anuncio primario del corte VIP0. Esto no demuestra que el anuncio no exista.

La vía de Internet Archive produjo estos resultados verificables:

- CDX de `/en/fee/futureFee` devolvió capturas 2021–2024. La consulta de prefijo de 2023 encontró enero–mayo y una variante de URL de marzo; no encontró una captura posterior en 2023 para esa consulta.
- El HTML de 2024-03-05 y 2024-05-29 respondió HTTP 200, pero mostraba **No records found**, sin tasas Regular. Recuperar una página no equivale a recuperar la tabla.
- CDX de la FAQ con su slug encontró las capturas A2/A3. La ruta corta devolvió un índice vacío. Otras consultas por idioma, blog y spot 2025–2026 terminaron por timeout o 503.
- El endpoint de disponibilidad de Archive respondió 429. Se cambió al índice CDX; no se esperó indefinidamente ni se hicieron descargas masivas.

Los hashes SHA-256 seleccionados corresponden al HTML **decodificado y vuelto a codificar como UTF-8**, no a bytes de transporte ni al digest CDX. En la validación posterior se recuperaron nuevamente A1, A2 y A3: coincidieron los tres hashes y sus fechas `Memento-Datetime`. Se conservaron las copias UTF-8 en `data/research/fee-archive-followup-20260918/`, con [manifiesto de procedencia](../../data/research/fee-archive-followup-20260918/manifest.json). Total: 1.701.226 bytes. Las copias permiten auditar exactamente el contenido revisado sin depender de una nueva descarga del archivo web.

## Pendientes y decisión necesaria

Sigue faltando una fuente primaria que determine el instante efectivo del cambio VIP0 USDT-M y la continuidad de las tarifas/promociones para los cuatro instrumentos hasta el corte. Esta revisión tampoco cierra las tarifas spot de 2025–2026 ni todas las revisiones de listas promocionales.

No hace falta ningún dato ni decisión del usuario para conservar estos hallazgos o continuar una investigación acotada. La próxima vía útil es recuperar un anuncio contemporáneo o una tabla/payload histórico alrededor del cambio observado de documentación. Usar una tasa constante o una fecha supuesta sería una decisión metodológica nueva y no certificaría la historia real. La evaluación histórica estricta debe seguir bloqueada mientras falte la vigencia necesaria.

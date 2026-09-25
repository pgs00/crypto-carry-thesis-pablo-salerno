# Fuentes históricas de Binance: investigación documental

Ejecución iniciada el **24/09/2026 23:42:06 UTC**, con consultas y verificaciones que continúan el 25/09 UTC. Alcance económico: **[2022-01-01 00:00 UTC, 2026-09-01 00:00 UTC)**. BTCUSDT y ETHUSDT spot sin crédito y perpetuos lineales USDT-M; Binance.com; Regular/VIP0 fijo; ejecución taker; sin BNB, referidos ni programas especiales; futuros aislados y apalancamiento elegido 2x.

**No se logró fechar la entrada en vigencia operativa del cambio taker de futuros de 0,04% a 0,05%.** Se recuperó evidencia primaria adicional y se amplió el registro, sin convertir fechas de FAQ o capturas en fechas operativas. El resultado es una investigación parcial trazable, no una cronología completa ni un archivo listo para cargar en el motor.

## Resultado respecto del inventario inicial

Se leyeron los nueve documentos/JSON de `docs/research/` indicados en el encargo, el manifiesto y las capturas A1–A3, y las interfaces del motor y metodología únicamente para identificar campos y límites. [Inventario inicial](inventario_inicial.md) y [verificación de antecedentes](verificacion_antecedentes.json).

Las tres copias anteriores coinciden en tamaño y SHA-256 con su manifiesto. Sus hashes representan **HTML decodificado y recodificado UTF-8**, no bytes originales de transporte. El informe JSON anterior que decía que no había copias persistidas precede a la recuperación que efectivamente dejó A1–A3; se conserva esa diferencia de estado sin editar antecedentes.

Esta entrega agrega:

- Una FAQ archivada el **21/06/2023**, con ejemplo USD-M de 0,040% (A4), y una tabla spot Regular del **06/08/2026**, con tarifa base 0,100% (SPOT26).
- **Siete respuestas históricas utilizables de `exchangeInfo`**, tres spot y cuatro futuros: **288 hechos** extraídos de rutas JSON concretas, incluidas banderas y cargos de liquidación. Se conserva cada respuesta completa, además de la selección BTC/ETH.
- **Ocho tablas anteriores de margen, 87 filas**, que no estaban transcritas en el registro anterior. Se reextrajeron y cotejaron también las ocho tablas nuevas, **90 filas**. Las 16 tablas conservan todos sus tramos, tasas, máximos de apalancamiento y límites.
- Índices CDX completos de las URL/rangos consultados, intentos fallidos, capturas sin tablas y exclusiones de promociones de otros pares/perfiles.

El registro contiene **345 hechos**: 305 observaciones documentales, 16 eventos, 16 deducciones derivadas, un intervalo respaldado, dos pendientes prioritarios, dos propuestas de sensibilidad y tres exclusiones. Un número alto de campos extraídos **no equivale a más días de historia certificada**. [Reglas](reglas_historicas.json), [fuentes](fuentes.json), [resumen](resumen_extraccion.json).

## Comisiones

### Cambio prioritario de futuros

| Evidencia | Momento documental UTC | Dato y alcance | Límite |
|---|---|---|---|
| A1, tabla oficial archivada, reutilizada | 2023-05-31 22:47:44 | Regular, USDT, taker 0,04%; maker 0,02%. SSR `futureFee`, `level=0` | No anuncia inicio de vigencia |
| A2, FAQ archivada, reutilizada | 2023-06-02 17:31:20 | Ejemplo BTCUSDT USD-M, taker 0,040% | Ejemplo educativo |
| **A4, FAQ archivada nueva** | **2023-06-21 19:20:25** | Mismo tipo de ejemplo, taker 0,040% | No garantiza que la FAQ estuviera sincronizada con la tarifa operativa |
| A3, FAQ archivada, reutilizada | 2024-02-20 06:41:15 | Ejemplo BTCUSDT USD-M, taker 0,05% | No informa la fecha del cambio |

[A1](https://web.archive.org/web/20230531224744id_/https://www.binance.com/en/fee/futureFee), [A2](https://web.archive.org/web/20230602173120id_/https://www.binance.com/en/support/faq/binance-futures-fee-structure-fee-calculations-360033544231), [A4](https://web.archive.org/web/20230621192025id_/http://www.binance.com/en/support/faq/binance-futures-fee-structure-fee-calculations-360033544231), [A3](https://web.archive.org/web/20240220064115id_/https://www.binance.com/en/support/faq/binance-futures-fee-structure-fee-calculations-360033544231).

Los cálculos se comprueban con Decimal: `10104 × 0.0004 = 4.0416`, `10104 × 0.0005 = 5.052` y `11104 × 0.0002 = 2.2208`. Se verifica la sección USD-M; la FAQ también contiene una sección COIN-M que no corresponde al objeto investigado. La fila de A1 distingue las columnas USDT y BUSD, y la tarifa base de la tarifa con BNB.

A4 desplaza la última observación documental recuperada de 0,04% desde el 2 al 21 de junio de 2023. **No establece un límite inferior operativo para el cambio.** Tampoco A3 establece por sí sola un límite superior operativo. El corredor junio de 2023–febrero de 2024 sirve para priorizar búsquedas, no como intervalo de implementación demostrado. Las etiquetas de publicación de las FAQ son distintas —2020-06-11 en A2/A4 y 2019-09-09 en A3—; ninguna fecha el cambio de tarifa.

Se encontró una [nota de Kripto Akadémia del 21/10/2023](https://kriptoakademia.com/2023/10/21/binance-futures-magasabb-jutalekot-kell-fizetni-a-hataridos-kereskedesert) que describe ese aumento sin anuncio previo. Se guardó como **pista secundaria**, con contenido comercial, y no se usó para fechar una regla. La búsqueda oficial en ese entorno recuperó el [Taker Program anunciado el 18/10/2023](https://www.binance.com/en/support/announcement/detail/143cee3a83944c4da2b1a53f302f45f0): requiere solicitud y volumen elevado; su fecha 31/10 y sus descuentos no son el cambio de tarifa general.

El [aviso de marzo de 2026](https://www.binance.com/en/support/announcement/detail/4f379b9ab6314eff8fe02babfe255825) contiene 0,04%→0,05% para **VIP1**, no VIP0. Su cuerpo tiene una actualización de septiembre de 2026. Se registra fuera de alcance, junto con el programa especial y BTC/U. No se tomó Square, una cuota de volumen ni una tarifa COIN-M como prueba del cambio buscado.

### Spot y promociones

La promoción general BTCUSDT spot de comisión cero queda respaldada en **[2022-07-08 14:00 UTC, 2023-03-22 00:00 UTC)** por el [anuncio de inicio](https://www.binance.com/en/support/announcement/detail/10435147c55d4a40b64fcbf43cb46329) y el [anuncio de modificación](https://www.binance.com/en/support/announcement/detail/be13a645cca643d28eab5b9b34f2dc36). Se conserva el alcance general y la exclusión del volumen de los cómputos VIP/LP durante la promoción. Los cuerpos consultados fueron enmendados; el segundo contiene cambios posteriores de FDUSD/TUSD que no deben trasladarse a marzo de 2023. La fila BTC/USDT y los extremos relevantes son explícitos.

La [tabla archivada SPOT26](https://web.archive.org/web/20260806031057id_/https://www.binance.com/en/fee/trading) muestra **Regular 0,100% maker / 0,100% taker**, aparte de 0,075% con BNB y de columnas USDC. Respalda la tarifa **base** de los pares USDT en ese documento. No acredita la pertenencia o exclusión de BTCUSDT/ETHUSDT de listas promocionales durante todo 2026.

Las capturas de tarifas de enero y julio de 2025 y las páginas `tradingPromote` de enero de 2025 y agosto de 2026 no recuperaron la tabla objetivo: unas muestran “No records found”; otra conserva notas generales sin lista de pares. Se guardaron los cuerpos y sus metadatos. **No se certifica ausencia de promociones en 2025 ni enero–agosto de 2026.** La promoción [BTC/U de abril–julio de 2026](https://www.binance.com/en/support/announcement/detail/fe2b0d2853004943aba45f2e87a4081c) usa United Stables, no USDT. Los antecedentes ETH/BUSD y BTC/USDC tampoco se trasladan a los pares investigados. Las anclas ordinarias de investigaciones anteriores siguen siendo antecedentes parciales, no cobertura continua adoptada por referencia.

## Filtros y restricciones de órdenes

Las siguientes son las **fechas reales recuperadas**, verificadas con URL final y `Memento-Datetime`. Todas las respuestas utilizables contienen BTCUSDT y ETHUSDT; las de futuros identifican `PERPETUAL`, `quoteAsset=USDT` y `marginAsset=USDT`.

| ID | Mercado | Captura UTC real | Información destacada |
|---|---|---|---|
| SPOTI22 | Spot | 2022-01-02 13:48:38 | `MIN_NOTIONAL=10`; `applyToMarket=true`; `avgPriceMins=5` |
| SPOTI23 | Spot | 2023-06-18 16:14:25 | `NOTIONAL` min=10, max=9.000.000; min aplica a MARKET, max no |
| SPOTI25 | Spot | 2025-12-09 11:16:42 | `NOTIONAL` min=5, max=9.000.000; mismas banderas |
| FUTI22 | USDT-M | 2022-01-02 13:48:38 | Mínimo nocional=5 en ambos; tick BTC=0,01 |
| FUTI22B | USDT-M | 2022-11-16 20:55:42 | Mínimo nocional=5; tick BTC=0,10 |
| FUTI26 | USDT-M | 2026-02-17 04:13:28 | Mínimo nocional BTC=100, ETH=20 |
| FUTI26B | USDT-M | 2026-05-10 10:30:16 | Mínimo nocional BTC=50, ETH=20 |

Las URL originales/finales, hashes y rutas JSON están en [fuentes](fuentes.json) y [selecciones extraídas](extraidos/). Estos JSON son respuestas archivadas del servicio original, no consultas actuales presentadas como históricas. El `serverTime` de FUTI22 corresponde al **31/12/2021 08:02:23.218 UTC**, anterior a la captura; los demás también tienen diferencias de segundos/minutos. Se conserva ese campo y no se lo interpreta como fecha de vigencia de filtros.

En los tres documentos spot, `LOT_SIZE` publica BTC min/step=0,00001 BTC y ETH min/step=0,0001 ETH, con max=9.000 unidades; son **campos leídos por separado**, no igualados por deducción. `PRICE_FILTER.tickSize=0,01 USDT`. `MARKET_LOT_SIZE` publica min=0 y step=0, pero máximos específicos variables: BTC 158,46776833 → 151,09725956 → 103,85345508; ETH 1293,19022111 → 2965,20223340 → 2554,65952958 en esas capturas. No se interpolan valores entre ellas.

Los ceros publicados se preservan. La [documentación oficial de filtros](https://raw.githubusercontent.com/binance/binance-spot-api-docs/master/filters.md), recuperada íntegramente del repositorio de Binance, explicita la desactivación por cero de componentes de `PRICE_FILTER`. No basta para trasladar automáticamente esa semántica a toda regla histórica de `MARKET_LOT_SIZE`: no se evalúa un módulo por cero ni se considera desconocido el cero publicado. Tampoco se borra `LOT_SIZE` por ver un step MARKET cero. Sus interacciones y la semántica histórica de órdenes ingresadas por cantidad de quote requieren documentación adicional.

En los cuatro documentos de futuros, `LOT_SIZE` min/step=0,001, máximos BTC=1000 y ETH=10000; `MARKET_LOT_SIZE` min/step=0,001, máximos BTC=120 y ETH=2000. Se retienen límites de precio, multiplicadores, `marketTakeBound`, conteos de órdenes y el valor categórico `POSITION_RISK_CONTROL.positionControlSide=NONE` cuando aparece. Los máximos de cantidad por orden, conteos y límites nocionales de posición son objetos distintos. No aparece un máximo nocional por orden de futuros que permita completar ese campo; ausencia del campo no equivale a ilimitado.

Eventos reabiertos y cotejados con estas nuevas observaciones:

| Cambio | Evidencia temporal | Precisión y condición |
|---|---|---|
| [Step spot BTC/ETH](https://www.binance.com/en-PH/support/announcement/detail/6925d618ab6b47e2936cc4614eaad64b) | 2021-08-26 06:00 UTC | Preperíodo; BTC 0,000001→0,00001 y ETH 0,00001→0,0001; órdenes anteriores conservan condiciones. No demuestra minQty |
| [Tick BTCUSDT perpetuo](https://www.binance.com/en-AU/support/announcement/detail/81e6795b0bae49828cbd52479094a987) | 2022-02-15 03:30 UTC | 0,01→0,1 USDT; órdenes anteriores no afectadas |
| [Mínimo spot con quote USDT](https://www.binance.com/en-AE/support/announcement/detail/c4706c73b805423a8d36be948e297603) | **A más tardar** 2023-08-31 03:00 UTC | 10→5 USDT; no se conoce el extremo inferior exacto; órdenes anteriores no afectadas |
| [Mínimo futuros BTC/ETH](https://www.binance.com/en/support/announcement/detail/e4384cba297a4bd2a154be644d5d76f9) | **A más tardar** 2023-11-02 10:00 UTC | BTC 5→100, ETH 5→20; órdenes anteriores no afectadas, con excepción explícita de Futures Grid que expira si no cumple el mínimo |
| [Mínimo futuros BTC](https://www.binance.com/en-KZ/support/announcement/detail/10999fd17dc045de801c0c78ab29e6fc) | Inicio 2026-04-14 06:30 UTC, duración **aproximada** cuatro horas | 100→50; no es un único instante ni un límite superior garantizado; órdenes anteriores no afectadas |

El máximo spot de `NOTIONAL=9.000.000` aparece con `applyMaxToMarket=false`; no se impone a una orden MARKET por analogía con el mínimo. En futuros, las banderas ausentes permanecen desconocidas. La documentación actual ayuda a interpretar nombres, pero no se retrotraen sus nuevas reglas de precio de referencia, ejemplos o precisiones a 2022.

## Margen y liquidación

Las [tablas extraídas](extraidos/tablas_margen.json) conservan el esquema antes/después y los encabezados. Se resolvieron las celdas `NA/N/A` como ausencia de tramo en esa mitad de la tabla, nunca como tasa cero. La semántica publicada es **piso exclusivo y techo inclusivo** (`floor < Position ≤ cap`); se conservan máximo de apalancamiento inicial y unidad USDT.

| Anuncio / contrato | Anteriores → nuevas | Momento operativo y posiciones existentes |
|---|---:|---|
| [Septiembre 2022, ETH](https://www.binance.com/en/support/announcement/detail/56ba139dd19249acb4f9470c3d98020d) | 10 → 9 | 2022-09-13 07:00 UTC; afecta existentes |
| [Diciembre 2023, BTC y ETH](https://www.binance.com/en/support/announcement/detail/d75c5ca94f704e96a6a4e55ffddfd65d) | BTC 10→10; ETH 10→11 | 2023-12-24 09:35 UTC; existentes no afectadas. Publicación visible **2024-01-02 13:50**, zona no acreditada |
| [Mayo 2024, BTC y ETH](https://www.binance.com/en-AU/support/announcement/detail/aa735cd2d8bd4e7bb092179cf086e486) | BTC 10→12; ETH 11→12 | 2024-05-28 10:30 UTC, aproximadamente 30 minutos; existentes no afectadas |
| [Junio 2025, BTC](https://www.binance.com/en-PH/support/announcement/detail/e778988edec446038ad536bcb0c8d460) | 12 → 12 | 2025-06-17 06:30 UTC, aproximadamente una hora; afecta existentes |
| [Agosto 2025, BTC y ETH](https://www.binance.com/en/support/announcement/detail/8e428625ebeb4cc7ae8678026846095c) | 12 → 12 cada uno | 2025-08-19 06:30 UTC, aproximadamente una hora; afecta existentes |

El evento de diciembre de 2023 tiene respaldo retrospectivo: **no se fija `known_from` en la fecha efectiva**. Las tablas anteriores no acreditan desde cuándo regían. Que una tabla nueva coincida con la anterior de otro aviso no prueba continuidad entre ambos. La política para aumentos de posiciones no se infiere cuando no está expresada.

En ETH persisten al menos dos discontinuidades documentales: la nueva tabla de septiembre de 2022 comienza hasta 250.000 USDT al 0,65%, mientras la tabla anterior de diciembre de 2023 comienza hasta 200.000 al 0,50%; y el primer techo pasa de 50.000 en mayo de 2024 a 300.000 en la tabla anterior de agosto de 2025, sin fecha intermedia recuperada. El cambio BTC de junio de 2025 no fecha el de ETH. La restricción de cuentas nuevas a más de 125x figura como aclaración agregada el 25/08/2025; no se convierte en conocimiento acreditado el 19/08. El apalancamiento elegido 2x no asigna por sí solo un tramo de mantenimiento.

No se recuperó `cum`/maintenance amount publicado en estas tablas. Se entregan 16 series separadas de deducciones **derivadas**, con `D0=0`, `Di=D(i-1)+floor_i×(rate_i-rate_(i-1))` y `MM=N×rate-D`. Requieren continuidad matemática y deducción inicial cero: no se presentan como importes históricos publicados.

| Captura API | `liquidationFee` BTC | `liquidationFee` ETH |
|---|---:|---:|
| 2022-01-02 | 0,015 = **1,50%** | 0,015 = **1,50%** |
| 2022-11-16 | 0,0175 = **1,75%** | 0,015 = **1,50%** |
| 2026-02-17 | 0,0125 = **1,25%** | 0,0125 = **1,25%** |
| 2026-05-10 | 0,0125 = **1,25%** | 0,0125 = **1,25%** |

La [documentación actual de `exchangeInfo`](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data) identifica el campo como tasa de liquidación. Se registran los valores originales y su conversión, con el límite de la interpretación semántica actual. No justifican extender ningún porcentaje a todo el período.

La [FAQ de cargos de futuros](https://www.binance.com/en/support/faq/detail/98488a516eb84e3eb34605683dffd554), publicada con etiqueta de 2024 y actualizada en enero de 2026, calcula insurance clearance sobre cantidad × precio de negociación y contempla una excepción para posiciones insolventes después de liquidar. Se conserva como **observación del cuerpo actual**, no prueba de que esa formulación rigiera en 2022. Siguen pendientes su cronología, condiciones de liquidación parcial, cargos regulares simultáneos y reconstrucción completa de tasas. Los antecedentes 2020/2021 no completan esas lagunas.

## Cobertura, contradicciones y recuperación

[Cobertura CSV](cobertura.csv) distingue parámetros, eventos, observaciones, ventanas inciertas, supuestos y huecos. El criterio para sumar tiempo exige un intervalo finito con ambos extremos explícitos y alcance coincidente. La unión se calcula por símbolo, mercado y parámetro; **sólo BTCUSDT spot `taker_fee` suma 22.154.400 segundos = 256,416666… días**, correspondientes a la promoción. El resto aporta cero días de continuidad certificada bajo este criterio, aunque tenga valores puntuales o eventos respaldados. No se informa un porcentaje global que mezcle campos ni un “porcentaje de historia” calculado por número de hechos.

Las filas `gap_continuity` pueden contener observaciones/eventos: indican falta de continuidad, no ausencia total de información. Las tablas antes/después son estados relativos diferentes, no contradicciones simultáneas. No se detectó un solapamiento contradictorio oculto de intervalos certificados. Las diferencias de tarifas entre fechas, las etiquetas de FAQ y las lagunas de ETH quedan visibles y sin reconciliación inventada.

La búsqueda, la apertura web y las descargas por terminal funcionaron por separado, con resultados distintos. Algunos avisos fueron legibles mediante navegación mientras la terminal recibió HTTP 202 y cero bytes. En esos casos se conserva **la extracción de la herramienta y su hash**, con `online_only_original=true`, `http_status=null` y sin afirmar que se recuperó el HTML original. Los `.body` descargados conservan exactamente `requests.Response.content`: puede haber descompresión HTTP automática, declarada en sus metadatos. No se equipara ese hash SHA-256 al digest de CDX ni a bytes de red/chunking.

Se consultó primero la documentación de CDX y después las URL exactas; se ampliaron sólo prefijos/variantes concretos. Los índices se guardaron sin `collapse`, con rango y campos explícitos y solicitud de clave de continuación. Los resultados recibidos no incluyeron una continuación pendiente; esto sólo completa esas consultas, no todo el archivo de Binance. Las variantes ES/CN/AU de `futureFee` sin resultados no prueban inexistencia de documentos en otros recursos.

Redirecciones relevantes:

- SPOTI23 solicitó junio 21 de 2023 y devolvió **junio 18**.
- FUTI22B solicitó noviembre 27 de 2022 y devolvió **noviembre 16**.
- FUTI23 solicitó noviembre 2 de 2023 y devolvió una captura de **enero 8 de 2024 con HTTP 451**. Se excluyó de los datos. La fila CDX 200 original no basta para validar el replay.
- Los avisos `en` que redirigieron al índice se reabrieron por versiones públicas del mismo ID, como `en-AU`, `en-PH`, `en-AE` o `en-KZ`. Se distinguió el cuerpo general del anuncio del pie regional actual. No se reconstruyen elegibilidad territorial ni términos de una cuenta individual a partir de estos pies; tampoco se trata cada idioma como una fuente independiente.

No se usaron claves, servicios pagos, consultas de cuenta ni técnicas para eludir bloqueos. Las consultas/URL y los resultados íntegros están en [busquedas.jsonl](busquedas.jsonl), [descargas.jsonl](descargas.jsonl) y `originales/W*_web.json`. Cuando una solicitud guardó una descripción abreviada en lugar del objeto exacto, los campos `Source:` del resultado preservan las aperturas efectivas; no se afirma reconstrucción literal perfecta de esos dos objetos de solicitud.

## Integración parcial futura y prioridades pendientes

Son candidatos a una integración posterior: los extremos explícitos de la promoción BTC, el cambio de tick BTC, los cambios de mínimos con su precisión temporal real y las tablas de margen con su política de posiciones existentes. Las capturas API permiten anclar filtros concretos, pero necesitan una política explícita para el tiempo entre capturas. Esa política sería un supuesto adicional, separado de la evidencia.

`RuleBook` exige snapshots que incluyen campos todavía incompletos y límites positivos; no representa directamente todas las banderas MARKET, ceros publicados, ventanas de despliegue, procedencia de conocimiento ni cohortes de posiciones. `Tier` conserva piso, techo, tasa y deducción pero no todo el máximo inicial de apalancamiento/documentación de frontera. `prescribed.py` contiene supuestos operativos, no fuentes históricas. Por eso este registro está marcado **`loadable_by_rulebook=false`** y no se escribió `data/rules/history.json`.

Prioridades concretas:

1. Conseguir un aviso operativo o una tabla histórica con fecha efectiva explícita del cambio Regular USDT-M 4→5 pb. La pista de octubre de 2023 orienta, pero no cierra el hueco. Si sigue sin aparecer: proponer sensibilidad posterior con 4 y 5 pb y fechas de transición alternativas, incluidas fuera del corredor documental. No interpretar esos escenarios como una fecha estimada.
2. Recuperar las listas efectivas de promociones 2025 y enero–agosto de 2026, con pares, perfil, fecha de entrada/salida y versiones. Separar tarifa base de tarifa aplicable.
3. Completar filtros entre capturas, semántica histórica de ceros MARKET, banderas/exenciones de mínimo en futuros y límites por orden ausentes. No confundir un `maxQty` variable con una regla constante.
4. Fechar los cambios intermedios ETH, obtener deducciones publicadas y reglas para aumentos/cohortes. En una sensibilidad posterior, comparar continuidad de tablas sólo como hipótesis y medir el efecto de preservar o actualizar posiciones donde falte evidencia.
5. Conseguir una cadena fechada de tasas y bases de liquidación. Los valores API nuevos permiten formular escenarios basados en observaciones, sin ejecutar sensibilidades ni adoptar 0,5%/1% como porcentajes certificados para todo el período.

## Verificaciones y preservación

El [verificador](verificar_fuentes.py) comprueba manifiesto, hashes de fuentes y textos, esquema, referencias, alcance por mercado/VIP/símbolo, rutas JSON, aritmética Decimal, filas antes/después, deducciones, temporalidad, cobertura por unión, archivos protegidos, índice/HEAD/rama y atributos Git efectivos. Las pruebas negativas usan copias temporales y deben ser rechazadas por el motivo esperado. El resultado ejecutado y su comando exacto están en [verificacion_resultados.json](verificacion_resultados.json).

La [segunda revisión](revision_segunda.json) fue realizada por el mismo agente, no es independiente. Se contrastaron otra vez anclas de comisiones, encabezados y aritmética; 177 filas de margen, con cotejo adicional de las 90 filas nuevas contra el registro anterior; identidades y filtros API; capturas reales y fechas operativas frente a publicación. Un hash acredita conservación, no exactitud de interpretación.

Todos los productos se encuentran en esta carpeta nueva. La protección `.gitattributes` es local a ella; conserva bytes y admite CRLF sin renormalizar el repositorio. La comprobación final compara **717 archivos ya versionados**, además del índice y HEAD, con el estado inicial. No se modificaron motor, configuraciones, resultados, paquetes anteriores ni conclusiones; no se ejecutaron backtests, commit ni push. Los detalles y límites verificables están en los registros de resultados, no en una afirmación de cronología completa.

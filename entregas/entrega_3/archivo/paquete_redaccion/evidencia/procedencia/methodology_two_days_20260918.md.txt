# Alternativa metodológica para una entrega en 48 horas

Fecha: 18/09/2026. Documento de decisión, sin ejecutar escenarios ni cambiar código, configuración, datos o descargas. Las recomendaciones siguientes son propuestas, no resultados. Se revisaron la consigna, la metodología, las configuraciones, el forecast y la evaluación existentes, y los informes de funding, tarifas y reglas.

Actualización posterior del mismo día: se completó por separado el [H1 con tasas observadas](funding_h1_preliminary_20260918.md), sin imputar marks ni modificar el motor. Su MAE equiponderado fue 6,299 bps para EWMA frente a 8,703 bps para no-change, con 10.180 observaciones válidas. Tiene [recalculo independiente de todos los pronósticos y objetivos válidos](../../data/research/funding-calendar-h1-20260918/independent-verification.json). El escenario económico propuesto aquí no fue ejecutado.

## Recomendación

Conservar **2022–2026 como escenario académico con supuestos explícitos**, producir primero **H1 con tasas observadas**, y presentar noviembre de 2023 en adelante como comprobación adicional. Es una salida científica defendible si se distinguen las observaciones de los supuestos, se cuantifica su sensibilidad y se conservan los resultados adversos. No equivale a certificar una reconstrucción exacta de Binance ni permite garantizar rentabilidad operable.

El plazo hace poco conveniente seguir buscando indefinidamente el precio interno exacto de los cobros de 2022–2023. Su ausencia no vuelve inútiles las tasas observadas ni demuestra que su aproximación tenga un efecto económico grande. Tampoco puede asegurarse que el efecto sea pequeño antes de medirlo. Las **comisiones y restricciones que cambian decisiones** pueden resultar más importantes que este error de precio; esa prioridad debe verificarse con las corridas.

La entrega mínima que no depende de autorizar nuevas hipótesis económicas es H1 completo, calendario/cobertura y análisis descriptivo de las tasas por régimen. El backtest económico con supuestos requiere una decisión metodológica expresa si todavía no fue autorizada. Preparar esa propuesta y medir el error de proxies sobre datos conocidos no requiere otra autorización.

## Qué falta y qué no falta

Los informes locales contabilizan 2.005 cobros por activo sin mark dentro de la ventana económica: desde el 01/01/2022 hasta el cobro de las 00:00 del 31/10/2023. Las tasas están presentes; todavía hay que validar calendario, intervalos y límites de los horizontes usados. El primer mark conocido está en el cobro del 31/10/2023 a las 08:00 UTC. [Seguimiento local](funding_followup_20260918.md).

No son datos intercambiables: Binance describe el campo de la API como el precio asociado al cobro y su FAQ distingue ese cálculo del mark difundido cada segundo. Su changelog incorporó ese campo el 01/11/2023. [API oficial](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data), [FAQ oficial](https://www.binance.com/en-AE/support/faq/detail/360033525031), [changelog](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/change-log). La FAQ es mutable: su texto consultado hoy no acredita que toda esa redacción estuviera vigente en 2022.

La apertura de una vela de mark de un minuto coincidió exactamente en 10/12 comparaciones locales. En otra muestra, el precio exacto apareció en algún mensaje de una ventana Tardis de dos minutos en 11/12 casos; buscar cualquier coincidencia retrospectiva no define un proxy utilizable. El contraejemplo ETH del 01/11/2023 a las 16:00 muestra 1792.96543725 para el cobro frente a 1792.96073137 para el mensaje contemporáneo. Ninguna muestra basta para estimar el error de todo el período. [Evidencia del proveedor](funding_provider_access_20260918.md).

También faltan series completas de reglas y comisiones. Empezar después de octubre de 2023 elimina el faltante identificado del mark de funding, **pero no completa esos otros requisitos**. [Tarifas](fees_followup_20260918.md), [reglas](historical_market_rules.md).

## Comparación de las tres rutas

| Ruta | Pregunta que sí permite estudiar | Limitación principal | Papel recomendado |
| --- | --- | --- | --- |
| Historia completa, tasas y precios observados, proxy de mark sólo donde falta, costos y reglas prescritos | H1; H2 bajo esos supuestos; H3 bajo esos supuestos si hay cobertura común completa | La rentabilidad y el riesgo dependen de decisiones de modelado expresamente declaradas | Principal escenario económico de investigación |
| Inicio 01/11/2023, mismo capital y calentamiento de tasas previo | H1 y comparación económica posterior; sensibilidad a quitar la imputación del mark | Quedan 61 días antes de 2024; no representa 2022–2023 ni resuelve reglas/comisiones. Cambia también el estado inicial de cartera | Comprobación adicional, no sustituto del H3 original |
| Estudio sólo de tasas y pronósticos, con ejercicio económico de exposición unitaria separado | H1 y evolución del funding bruto; sensibilidad de un umbral de costos prescrito | No contiene basis, ejecución de dos patas, margen, liquidación ni retornos de cartera. No prueba H2 ni el H3 compuesto original | Entrega mínima verificable y respaldo si no termina el replay |

Empezar el 01/01/2024 elimina por completo el régimen anterior: permite comparar estrategias desde esa fecha, pero no responder si la oportunidad se comprimió desde 2024 frente a 2022–2023. Una corrida nueva desde noviembre o enero tampoco se puede empalmar con una cartera iniciada en 2022. Cada una conserva su propio capital y estado.

## Escenario económico propuesto

El nombre sugerido es **“escenario de investigación con datos de mercado observados y reglas prescritas”**. Mantener la especificación estricta y sus bloqueos como referencia. La propuesta conserva BTC/ETH, long spot/short USD-M, 10.000 USDT por cartera, objetivo 30% por activo, 2x aislado, EWMA 336/24/168 horas, ejecución y controles de riesgo, y una misma implementación con el filtro de funding activado/desactivado. No reiniciar en 2024.

| Elemento | Propuesta concreta | Alcance de la afirmación |
| --- | --- | --- |
| Tasas y tiempos | Tasas finales y timestamps originales observados; demora de señal de 60 segundos; calendario validado | Observaciones históricas; no rellenar tasas con cero |
| Mark de funding observado | Usar el campo oficial cuando existe | Precio publicado para ese cobro |
| Mark de funding faltante | Cierre del último minuto de mark **ya disponible** en el timestamp efectivo del cobro; registrar fuente, antigüedad y condición de proxy | Aproximación causal; no modifica precios de fills, basis ni valuaciones |
| Costos | Spot taker 0,10%; Futures taker 0,05%; slippage 1 bp por orden; sin BNB, referidos ni promociones en este escenario fijo | Costos prescritos, no tarifas históricas certificadas. El costo estimado de ciclo es 0,34% |
| Tick, step y filtros de órdenes | Una tabla completa por instrumento y mercado, capturada y congelada antes de ver resultados. Publicar sus números y la fecha real de captura. Donde sólo hay evidencia parcial, identificar cada valor elegido como supuesto | Un contrato simulado explícito. Una respuesta actual no se convierte en regla histórica por copiarla hacia atrás |
| Margen | Conservar margen aislado y controles. Como referencia reproducible, usar la tabla nueva de diciembre de 2023 ya transcripta en `historical_market_rules.json`, congelada para todo el escenario; declarar la continuidad usada para derivar deducciones | Regla prescrita: no reconstruye cambios ni cohortes de posiciones históricas. No usar el tramo rotulado “2x” para posiciones pequeñas |
| Cargo de liquidación | Prescribir 1% del nocional ejecutado más comisión ordinaria y contrastar 3%, si se necesita completar el campo | Parámetro del estudio; 1% no se presenta como tasa histórica ni como extremo conservador garantizado |
| Operatividad | Incorporar incidentes documentados; disponibilidad del resto como supuesto explícito. Aplicar inactividad real, caducidad y timeouts; huecos desconocidos siguen siendo huecos | El supuesto de disponibilidad no autoriza inventar operaciones ni ocultar archivos faltantes |

Esta tabla define el cambio metodológico, pero **la ficha de filtros debe contener todos sus valores antes de ejecutar**: tick, step, min/max cantidad, min/max nocional y aplicación a las órdenes del modelo. No hace falta pedir al usuario que invente esos números: deben prepararse como una tabla revisable con origen y elección técnica. La recomendación no es reutilizar sin explicación las reglas ilustrativas de la demo.

No clasificar un supuesto como `verified`, no alterar la fecha real `retrieved_at` o `known_from`, ni hacer pasar estas corridas por la certificación estricta existente. El código actual no tiene un modo de investigación completo para esto: `RuleBook` y la validación previa requieren una adaptación explícita, no un cambio de etiquetas para eludir controles. Las observaciones deben permanecer separadas de la aplicación contrafactual de reglas.

### Por qué ese proxy y cómo contrastarlo

El último cierre ya disponible evita atribuir información posterior a la caja y al riesgo en el instante del cobro. La apertura del minuto es un segundo candidato valioso por proximidad temporal, pero el OHLC por sí solo no prueba la hora del primer update usado para construirla. Los timestamps de apertura/cierre pertenecen al esquema de la vela, no al registro interno de cobro. [Esquema oficial de mark klines](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data).

Comparar también la apertura sobre los cobros conocidos. Usarla como sensibilidad contable con cantidades congeladas es válido para medir diferencias directas; para usarla en un replay completo hay que especificar su disponibilidad. No usar el cierre del propio minuto ni escoger retrospectivamente el precio que mejor coincide. Si falta la vela causal, no encadenar otro reemplazo silencioso.

La regla debe guardar, por evento, `funding_time` original, tasa, mark observado o proxy, método, minuto de origen, disponibilidad supuesta y diferencia temporal. Las tasas y el pronóstico no cambian por elegir un mark de cobro.

## Medir el efecto económico, no sólo la diferencia de precios

Para un short de cantidad positiva `q`, tasa firmada `r` y mark de cobro `M`, el flujo es `F = q × r × M`. El error directo al usar `M_proxy`, manteniendo fija la posición, es:

```text
Delta F = q × r × (M_proxy - M_true)
```

No es `q × (M_proxy - M_true)`: esa segunda expresión confunde una modificación del precio de liquidación de funding con una repricing de toda la posición. Es una consecuencia algebraica de la fórmula del estudio y de la definición de funding de Binance. [FAQ oficial](https://www.binance.com/en-AE/support/faq/detail/360033525031).

Ejemplo puramente ilustrativo: con nocional 3.000 USDT, tasa 0,01% y error relativo de mark de 0,10%, el error directo del cobro es **0,0003 USDT**. No es una estimación de los eventos faltantes. El error cambia con el nocional y con el valor absoluto de la tasa; no se deben asumir tasas o exposición constantes durante 2022–2023.

Si se postula `abs(M_proxy - M_true) <= epsilon × M_proxy`, una cota condicional del error directo acumulado de una trayectoria fija es:

```text
B_strategy(epsilon) = sum(abs(q_i × r_i) × epsilon × M_proxy_i)
```

La suma abarca sólo cobros con proxy y exposición. Para la diferencia de funding entre estrategias, `B_conditional + B_permanent` es una cota simple con las dos trayectorias congeladas. Si la ventaja observada es menor que ese presupuesto, el orden de las estrategias no queda protegido por él. El presupuesto no es un intervalo de confianza ni una garantía sobre CAGR o Sharpe.

Las trayectorias reales pueden divergir: funding cambia caja, deuda, equity, sizing futuro y umbrales de riesgo. Por ello se necesitan **dos niveles de análisis**:

1. Diagnóstico directo con posiciones congeladas: error de precio en bps, sesgo, mediana, percentiles y máximo; `sum(abs(q*r*Delta M))`; error firmado y funding absoluto por activo/año. Informar exposición y eventos aproximados de cada cartera.
2. Repetición de ambas estrategias con el mismo método perturbado: cambios de órdenes, salidas, tamaños, riesgo, drawdown, costos, CAGR y Sharpe. El error de funding pequeño no excluye por sí solo un cambio de decisión cerca de un umbral.

Validar sobre todos los cobros conocidos que permita la cobertura, con desglose temporal y por activo. Reservar un tramo final para comprobar la regla elegida; no escogerla por rentabilidad ni por favorecer H2. Su error posterior a 2023 no prueba automáticamente el de 2022: complementar con perturbaciones predefinidas de **1, 10 y 100 bps** del proxy. Son escenarios de estrés, no probabilidades ni cotas históricas acreditadas. Para un estrés que disminuya cada cobro del short, aplicar `M_proxy × (1 - sign(r) × epsilon)`; el aumento usa el signo contrario. Ese par altera coherentemente ambas carteras y no garantiza encerrar todas las trayectorias posibles.

## Sensibilidades prioritarias dentro del plazo

Primero correr el escenario base y las dos carteras con la misma cobertura. Priorizar, en este orden, según el costo de replay medido:

1. Costos 2x y 3x, afectando comisiones/slippage realizados y umbral estimado de entrada. Un costo fijo mayor no garantiza menor rentabilidad porque puede evitar operaciones perdedoras; mostrar entradas y exposición además del resultado final.
2. Presupuesto directo de error de mark para 1/10/100 bps. Repetir trayectorias con el estrés adverso/favorable de 10 bps; ampliar si las conclusiones o decisiones son sensibles. La selección inicial de 10 bps es un protocolo, no un error estimado.
3. Reglas: tasas de mantenimiento prescritas más exigentes y límites de filtros más restrictivos en escenarios separados. Propuesta inicial: duplicar tasas de mantenimiento y recomputar deducciones para conservar continuidad; cargo de liquidación 3% separado; duplicar step, tick y mínimos por separado cuando el presupuesto lo permita. No llamar “histórico” a esos shocks.
4. Inicio 01/11/2023 y/o 01/01/2024. Para aislar mejor el proxy, agregar una comparación exacto/proxy **sobre la misma ventana posterior, mismo capital y reglas**. Comparar sólo una muestra larga contra otra corta confunde error de precio, régimen y estado inicial.

Registrar qué restricciones efectivamente se activan: redondeo por tamaño, órdenes rechazadas, mínimo nocional, aproximación a tramos, distancia mínima a liquidación y menor saldo de margen. Sólo si los datos lo muestran se puede afirmar que una regla fue poco influyente en esa corrida. El nocional objetivo inicial de 3.000 USDT no prueba que todos los futuros rebalanceos o cierres estén lejos de los mínimos.

La cartera debe conservar cierres por riesgo y liquidación; eliminarlos para sortear reglas faltantes cambia sustancialmente H2. Tampoco se puede sustituir trades por velas de un minuto y seguir afirmando una ejecución de primera operación posterior, demora de un segundo y timeout de 30 segundos. Si fuera indispensable un modelo por barras, necesita otro nombre, otro alcance y su propia limitación metodológica.

## Qué se puede entregar aun sin replay económico completo

H1 depende de tasas, tiempos, intervalos verificados y cobertura, no del mark de cobro, fills, tarifas ni tramos. El código de `forecast.py` y `forecast_evaluation` confirma que sus cálculos no usan `settlement_mark_price`; el contrato `Funding` permite ese campo nulo. Preparar una evaluación de tasas independiente del bloqueo global del backtest no exige imputarlo.

Usar los mismos instantes válidos para EWMA y no-change, horizonte de 168 horas y ventana de 336 horas con antecedente, excluyendo límites incompletos. Reportar MAE por activo, media equiponderada, resultados por régimen y cantidades excluidas. Los horizontes solapados no son observaciones independientes; no prometer significancia estadística.

Como análisis económico reducido, se puede mostrar una exposición normalizada de una unidad de nocional, tasas realizadas y umbrales de costo fijados de antemano. La suma de tasas es una medida de carry por unidad de nocional bajo esa normalización, no retorno sobre los 10.000 USDT de una cartera con cantidades mantenidas y margen aislado. Denominarlo **ejercicio de funding**, sin CAGR/Sharpe de cartera ni conclusión H2. La caída o aumento de tasas antes/después de 2024 es evidencia sobre funding bruto; no completa el H3 original, que requiere elegibilidad por basis/costos y CAGR condicional.

## Plan de 48 horas y condición de entrega

| Tiempo desde el comienzo | Trabajo y resultado comprobable |
| --- | --- |
| 0–4 h | Congelar el protocolo y la ficha de supuestos; validar tasas/calendario y ejecutar H1 independiente. Medir descarga/cobertura realmente disponible y velocidad de un replay representativo sin modificar la descarga activa. |
| 4–10 h | Contrastar proxy en el período conocido; completar tabla de filtros; preparar el modo de investigación separado y un piloto contable/temporal. Guardar parámetros antes de examinar rentabilidad. |
| 10–26 h | Correr la historia económica y las dos carteras si la integridad de datos y el tiempo proyectado lo permiten. Producir ledger, equity, atribución y cobertura. No iniciar una búsqueda abierta de proveedores. |
| 26–38 h | Ejecutar sensibilidades prioritarias que quepan en el tiempo medido; documentar las no realizadas. H3 sólo sobre días conjuntos completos y sin reiniciar capital. |
| 38–48 h | Conciliar resultados, revisar tablas/figuras, redactar supuestos y límites, reproducir el manifiesto y entregar. Reservar este tiempo aunque queden sensibilidades adicionales pendientes. |

No se midió aquí el tiempo del replay completo ni se verificó la descarga en D:. Las horas son un presupuesto de trabajo, no una promesa de que termine. El punto de decisión de las 10 h evita descubrir al final que el cálculo es inviable. Si no llega, entregar H1 y el análisis reducido, más resultados económicos sólo de intervalos expresamente terminados y comparables; no una curva de efectivo inventada ni una certificación de toda la muestra. No rellenar huecos de trades para forzar esa entrega.

El paquete mínimo contiene: protocolo fechado; inventario de datos observados/proxies/supuestos; tabla H1 y exclusiones; tasas/pronósticos por régimen; y, si finaliza la simulación, comparación económica, atribución, drawdown, cobertura y sensibilidades. H2/H3 deben figurar como **condicionados al escenario**, mixtos o no concluyentes según lo que resulte.

## Decisión metodológica mínima

La consigna aprobada exige marks de cobro y reglas históricos y prohíbe completar evidencia faltante con datos inventados. Para el escenario propuesto, la decisión concreta es autorizar **un estudio económico separado con tasas y precios observados, proxy causal de funding, costos fijos prescritos y reglas explícitas sujetas a sensibilidad**, conservando la evaluación estricta como no completada. No hace falta una autorización para cada parámetro técnico o cada tabla cuando el alcance del escenario ya está autorizado.

Redacción sugerida del acuerdo: “Usar la ventana 2022–2026 para un escenario de investigación con las aproximaciones y reglas prescritas de esta ficha, y reportar sensibilidad; mantener separado el resultado histórico estricto. No presentar el escenario como rendimiento real ejecutable ni como reconstrucción exacta de Binance”. La autorización cambia el alcance de las afirmaciones, no la calidad de la evidencia. Si el usuario ya dio esa autorización en la conversación, no volver a pedirla.

No se necesitan contactos con soporte, nuevas credenciales ni una compra de datos para adoptar esta ruta. La decisión esencial es el tipo de resultado académico que se va a entregar, acompañada por una tabla concreta de supuestos, no una promesa de recuperar en dos días toda la historia interna del exchange.

# Prompt para Codex: adaptar el backtesting existente a ejecución por minuto

Trabajá sobre el proyecto existente dentro de `Backtesting`. Implementá, ejecutá y verificá los cambios de este instructivo. No devuelvas solamente otro plan ni reconstruyas el proyecto desde cero.

## 1. Objetivo y restricciones

El motor ya ejecutó un backtest de crypto carry en Binance: long spot y short perpetuo lineal USD-M en BTCUSDT y ETHUSDT. Necesito una ejecución reproducible con datos de un minuto, corregir el dimensionamiento conjunto de las patas y explicar las restricciones que impiden operar.

Los trades individuales están descartados por volumen de datos. No descargues `trades`, `aggTrades`, ticks, order books ni datos subminuto, tampoco para ventanas pequeñas. No generes trades artificiales a partir de OHLC. Reutilizá velas de un minuto, funding, marks y reglas ya disponibles. Los archivos de investigación con trades que pudieran existir no serán una dependencia del nuevo modelo.

Todo archivo nuevo del proyecto debe quedar dentro de `Backtesting`. Si el directorio actual ya es esa carpeta, no crees otra anidada.

Código claro, modular y bien comentado, con identificadores, comentarios y docstrings en inglés. Documentación metodológica y análisis de resultados en español. Conservá las dependencias y convenciones del proyecto, salvo incompatibilidad demostrada. No envíes órdenes reales ni solicites credenciales privadas.

El objetivo es que la simulación sea coherente y evaluable. No ajustes parámetros para conseguir rentabilidad, operaciones o una conclusión favorable.

## 2. Inspección inicial y evidencia

Primero leé las instrucciones aplicables del repositorio, la configuración efectiva, la documentación, las pruebas y el último `report.md`. Localizá el adaptador del motor, ejecución, sizing, forecast, ledger y generación de reportes. Anotá los archivos reales que vas a modificar y sus responsabilidades antes de editar. Adaptá los módulos existentes y evitá una refactorización general.

Buscá las consignas, las Entregas 1 y 2 y el feedback si están disponibles. No finjas haber leído archivos inaccesibles. Este prompt reemplaza expresamente las reglas anteriores de ejecución con trades y tiempos subminuto para los nuevos escenarios. Conservá documentadas las diferencias metodológicas respecto de la Entrega 2.

El reporte que motivó esta adaptación informa:

- Dos ventanas independientes: `[2022-09-01T00:00:00Z, 2023-09-01T00:00:00Z)` y `[2025-09-01T00:00:00Z, 2026-09-01T00:00:00Z)`. Cada estrategia comienza cada ventana con 10.000 USDT y sin posiciones.
- En 2025-2026, la condicional rechazó 2.190 señales por funding insuficiente. La permanente rechazó 2.182 por basis y tuvo dos aperturas desarmadas por desbalance mayor que 0,5%.
- Una apertura compró 0,03929 BTC brutos; después de comisión quedaron 0,03925071 BTC, frente a 0,039 BTC en futuros. El desbalance fue aproximadamente 0,6387%.
- El 58,0045% del beneficio final de la condicional en 2022-2023 se concentró en el cierre excepcional del 24/03/2023, que dejó 121 minutos sin cobertura.
- La EWMA presentó menor MAE que el pronóstico sin cambio en ambas ventanas. Esto no demuestra rentabilidad ni justifica modificarla automáticamente.

Contrastá estos antecedentes con los artefactos disponibles. Son evidencia del escenario anterior, no resultados esperados de las nuevas corridas. Si encontrás discrepancias, documentalas.

## 3. Condiciones que debe preservar la comparación

Mantené las dos ventanas anuales anteriores y los 10.000 USDT iniciales por cartera. Cargá el historial previo necesario para el calentamiento, sin contabilizarlo como período invertido. Conservá las exclusiones de etiquetas que requieren funding posterior al final de muestra.

Usá la misma lógica, datos, sizing, costos, ejecución y riesgos para condicional y permanente. La única diferencia entre ambas debe continuar siendo la activación del filtro de funding para entrada y renovación. El profesor destacó expresamente esta comparabilidad.

No modifiques en esta intervención:

- EWMA con ventana de 336 horas, vida media de 24 horas y horizonte de 168 horas. Conservá su normalización por duración efectiva de los intervalos de funding. Verificá que no se haya confundido la frecuencia de barras con la frecuencia de funding.
- Entrada condicional con pronóstico estrictamente mayor que el costo estimado del ciclo completo de cuatro órdenes.
- Filtro de entrada `basis = precio_perpetuo / precio_spot - 1`, entre 0 y 0,005, inclusive.
- Tenencia inicial de 168 horas, contada desde que ambas patas quedan ejecutadas; renovación condicional con forecast positivo. La permanente omite solamente esas condiciones de funding.
- Asignaciones objetivo, apalancamiento, comisiones, slippage, reglas de margen, riesgos y cooldown de la configuración vigente, salvo las adaptaciones temporales expresas de este documento.

No incorpores ahora horizontes de 14 o 28 días, reducción de comisiones, ampliación del basis ni aumento del desbalance permitido. Quedan como posibles investigaciones posteriores. Si detectás un error de implementación comprobable en una regla preservada, corregilo con una prueba, identificá la corrección y separá su efecto en los resultados.

## 4. Datos agregados y validación

Para spot y perpetuos USD-M, normalizá las velas de un minuto con, al menos, símbolo, mercado, inicio y fin exclusivo del intervalo, OHLC, volumen base y volumen cotizado. Conservá también el número de operaciones cuando esté disponible.

En estos instrumentos, el volumen base está expresado en BTC o ETH y el volumen cotizado en USDT. Para volumen base positivo:

`vwap_1m = quote_asset_volume / base_asset_volume`

No uses OHLC4 ni precio típico como sustitutos del VWAP. No apliques esta interpretación a contratos inversos COIN-M. Si el parquet actual descartó alguno de los volúmenes, recuperalo de las velas originales; descargá solamente las particiones de klines indispensables si no están en caché.

Validá unidades, duplicados, orden temporal y coherencia con OHLC dentro de una tolerancia numérica explícita. Binance cambió a microsegundos los timestamps de archivos spot desde 2025; verificá cada fuente y normalizá a UTC sin asumir la misma unidad para todos los archivos.

Distinguí expresamente:

- Vela válida con volumen cero: no permite ejecución.
- Suspensión o ausencia real de actividad documentada: conserva la exposición y activa las reglas operativas correspondientes.
- Archivo, vela o mark indispensable faltante: problema de cobertura. No lo conviertas automáticamente en suspensión ni lo rellenes con volumen cero.

Una señal usa solo datos ya disponibles. Para el basis, utilizá spot y perpetuo del mismo intervalo cerrado, con su frescura comprobada. No mezcles mark, índice, VWAP futuro y precios de diferentes minutos. Si esto corrige una desalineación del motor anterior, registralo como corrección separada.

Reutilizá funding histórico en sus timestamps reales y el mark de liquidación de ese funding. No lo distribuyas uniformemente por minuto. Usá marks para garantías y riesgo, no como precio ejecutable del perpetuo.

Procesá datos por particiones, con caché, manifiestos y consumo acotado de memoria. No dupliques datasets por escenario. Informá bytes realmente disponibles o descargados; no inventes estimaciones de tamaño.

## 5. Modelo principal: `next_minute_vwap`

Implementá una política explícita de ejecución que pueda seleccionarse por configuración. Conservá el modo anterior para reproducir su referencia. Verificá las APIs de la versión instalada de NautilusTrader, si ese es el motor utilizado; no presupongas que su matching por barras implementa este contrato.

### Cronología sin anticipación

1. La decisión y la cantidad de la orden se fijan con información disponible en `t_decision`. Reservá los fondos necesarios según las reglas de presupuesto.
2. La ventana de ejecución comienza en el primer límite de minuto mayor o igual que el envío. Si la orden llega dentro de un minuto, espera al siguiente límite. Nunca utilices la parte de una vela anterior al envío.
3. Una orden enviada exactamente a las 12:01 puede usar la ventana `[12:01, 12:02)`, pero su fill se registra a las 12:02. Una orden enviada a las 12:01:15 solo puede usar `[12:02, 12:03)`.
4. Usá el VWAP de esa ventana, con slippage adverso: compra `VWAP * (1 + slippage)` y venta `VWAP * (1 - slippage)`. Aplicá las comisiones reales del escenario una sola vez. El slippage ya queda incluido en el precio, no se descuenta nuevamente del P&L.
5. El volumen y el VWAP de esa ventana sirven para simular su ejecución al finalizar, nunca para decidir retrospectivamente si convenía enviar la orden.
6. Para la apertura, completá primero spot y después enviá la cobertura de futuros. Si spot termina a las 12:02, el futuro puede usar `[12:02, 12:03)` y su fill se registra a las 12:03. Para cierres, conservá el orden de patas del proyecto.

Esta es una aproximación con fills contabilizados al final del intervalo. No representa un VWAP garantizado ni una trayectoria observable dentro del minuto. No asignes el fill al inicio después de haber leído toda la vela.

### Volumen, expiración y fallos

Usá `max_volume_participation = 0.01` como supuesto explícito del nuevo modelo, configurable y no calibrado contra retornos. Es una capacidad simulada del 1% del volumen de la ventana, no una garantía de liquidez accesible.

La cantidad máxima ejecutable será el menor valor entre la cantidad pendiente y esa capacidad, redondeada hacia abajo al paso de cantidad permitido, y sujeta a fondos, inventario y reglas de mercado. Compartí la capacidad entre órdenes del mismo instrumento y minuto, sin reutilizar el volumen para cada orden. Cada estrategia se evalúa como cartera contrafactual independiente.

Permití fills parciales y registrá cantidad ejecutada, remanente y motivo. Al terminar una única ventana elegible de un minuto, procesá el fill disponible y luego expirará el remanente. Una ventana válida sin volumen también consume ese plazo. No reutilices el timeout anterior de 30 segundos.

- Si la primera pata no llena completamente, cancelá el remanente, no abras la segunda y desarmá el inventario efectivamente adquirido. Si no hubo fill, no inventes comisiones ni inventario.
- Si la segunda pata no llena completamente, cancelá el remanente y cerrá las exposiciones efectivamente existentes conforme al estado de desarme y cooldown.
- Los cierres pendientes reintentan en el siguiente minuto con el remanente actualizado. Nunca asumas que una orden enviada ya cerró la posición.
- Reconciliá inventario antes de cada reintento y evitá cierres duplicados, sobreventas o recompras superiores al short.

El plazo de corrección de desbalance será una ventana elegible de un minuto. Procesá su fill antes de comprobar el vencimiento. Si no queda dentro de la tolerancia establecida, comenzá el cierre. Los reintentos no reinician indefinidamente ese plazo.

### Funding, riesgo y eventos simultáneos

Definí y probá una sola prioridad de eventos para el nuevo modelo: incorporar datos que pasan a estar disponibles; liquidar funding sobre la posición anterior a los fills de ese timestamp; registrar los fills de ventanas ya comprometidas; recalcular riesgo y estado; procesar vencimientos y reintentos; finalmente evaluar decisiones habilitadas. Las salidas por riesgo tienen prioridad sobre nuevas entradas o renovaciones.

Un control observado al cierre de una vela puede impedir la siguiente ventana de ejecución, pero no borrar retrospectivamente un fill de la ventana que acaba de concluir. Las órdenes canceladas antes del inicio de su ventana no pueden llenar. Documentá cualquier diferencia con la prioridad del motor anterior.

Mientras existan posiciones, incluso durante desarmes, siguen activos funding, valuación, margen, liquidación y deuda. Mantené el monitoreo de riesgo a un minuto. No afirmes que OHLC permite reconstruir una liquidación intraminuto ni uses un recorrido artificial del high y low como si fuera observado.

Conservá el corte de muestra exclusivo. No registres fills o funding en timestamps iguales o posteriores al final, ni un cierre terminal ficticio. Valuá el inventario remanente y reportá órdenes todavía pendientes.

## 6. Sizing conjunto: `joint_quantity`

Reemplazá la secuencia de comprar una cantidad spot objetivo y descubrir después que el redondeo de futuros impide cubrirla. Calculá una combinación ejecutable de ambas patas antes de enviar la primera.

Para una apertura sin inventario previo y comisión spot cobrada en el activo base:

1. Determiná el presupuesto y el objetivo con el snapshot de equity disponible al decidir.
2. Elegí una cantidad de futuros `q_futures` que respete su paso de cantidad.
3. Calculá `q_spot_gross = ceil_to_spot_step(q_futures / (1 - spot_fee_rate))`.
4. Calculá `q_spot_net = q_spot_gross * (1 - spot_fee_rate)` y el desbalance `abs(q_spot_net - q_futures) / q_spot_net`.
5. Verificá simultáneamente desbalance menor o igual a 0,005, presupuesto, comisión, margen, notional mínimo, cantidades mínimas/máximas y reglas vigentes de ambos mercados.
6. Si excede el presupuesto o no es viable, reducí el candidato de futuros al siguiente escalón permitido. Elegí la mayor combinación viable dentro del objetivo y documentá cualquier efectivo que quede sin asignar. Si ninguna sirve, rechazá antes de comprar.

Usá Decimal o aritmética entera escalada para pasos, comisiones y cantidades. Aplicá la moneda de comisión efectiva del escenario. No uses la fórmula de descuento en base si el fee se paga en otra moneda. Para rebalanceos y polvo residual, calculá sobre inventario neto total y cambios de posición, sin confundir una compra incremental con una apertura desde cero.

El plan de cantidades usa información conocida al enviarse. Después de fills parciales o cambios de precio, conciliá las cantidades y fondos reales. No aumentes retrospectivamente la compra original ni saltees controles para sostener el hedge.

Ejemplo de prueba, con supuestos sintéticos explícitos: `q_futures = 0.039`, paso spot `0.00001` y fee en base `0.001` producen compra bruta `0.03904`, spot neto `0.03900096` y desbalance aproximado `0.00246148%`, menor que 0,5%. No asumas que estos pasos sintéticos son las reglas históricas reales de todas las fechas.

## 7. Diagnóstico de oportunidades

Para cada instante de evaluación y activo, guardá los resultados de todos los filtros evaluables, aunque uno anterior ya haya rechazado la señal. Diferenciá `pass`, `fail` y `not_evaluable`, sin interpretar un dato faltante como un rechazo económico.

Persistí timestamp de decisión y disponibilidad de cada dato, forecast, costo esperado descompuesto, diferencia `forecast - cost`, precios y timestamps de spot/perpetuo, basis, estado de cartera y cooldown, cantidades propuestas, desbalance previsto y causas de rechazo.

Separá especialmente: funding insuficiente, basis negativo, basis mayor que 0,005, precios desalineados u obsoletos, sizing inviable, presupuesto/margen insuficiente, estado activo y cooldown. Informá tanto las causas simultáneas como una descomposición secuencial con orden explícito para evitar sumar conteos solapados como si fueran excluyentes.

Mostrá por activo y ventana la distribución del forecast frente al costo y del basis. Explicá por qué no se opera cuando corresponda, sin modificar los umbrales para generar actividad. El tamaño más cuidadoso no puede solucionar por sí mismo un filtro de funding o basis que rechaza todas las oportunidades.

## 8. Comparación controlada

Congelá y conservá los artefactos y configuraciones anteriores. Ejecutá la siguiente matriz en las dos ventanas y con ambas estrategias:

| Escenario | Ejecución | Sizing |
|---|---|---|
| `legacy_reference` | Modelo anterior por minuto | Modelo anterior |
| `joint_sizing_only` | Modelo anterior por minuto | Conjunto |
| `vwap_only` | Nuevo contrato `next_minute_vwap` completo | Modelo anterior |
| `vwap_joint` | Nuevo contrato `next_minute_vwap` completo | Conjunto |

Los escenarios con ejecución nueva incluyen explícitamente sus cambios de precio, capacidad, fills parciales y tiempos. No atribuyas toda su diferencia exclusivamente al VWAP. Si los artefactos guardados del escenario anterior tienen cobertura, configuración y trazabilidad suficientes, reutilizalos como referencia sin repetir inútilmente la corrida. Una corrección adicional de datos o lógica debe quedar identificada y no mezclarse silenciosamente con el experimento.

No agregues en esta intervención ejecución de cinco minutos ni nuevos horizontes de funding. Primero completá esta comparación acotada. Todos los escenarios usan los mismos datos de origen, tasas, presupuestos y reglas financieras, salvo las dos dimensiones indicadas.

Para el episodio del 24/03/2023, reconstruí la secuencia con las velas y registros disponibles. Compará el cierre, los precios modelados, funding, comisiones, P&L y duración sin cobertura entre escenarios. No elimines el episodio de la muestra ni presentes una resta manual del P&L local como un backtest anual nuevo.

## 9. Pruebas que deben acompañar la implementación

Usá fixtures pequeñas, sin red, con resultados verificables de forma independiente. Agregá pruebas para estos comportamientos concretos:

| Caso | Resultado requerido |
|---|---|
| Vela con volumen base 2 y cotizado 200 | VWAP 100; con slippage de 1 bp, compra 100,01 y venta 99,99. |
| Orden a las 12:01 y otra a las 12:01:15 | Sus primeros fills posibles son 12:02 y 12:03, respectivamente. |
| Se modifica una vela posterior a un corte | No cambian decisiones, órdenes ni saldos anteriores al corte. Los fills posteriores pueden cambiar. |
| Spot llena a las 12:02 | El futuro no llena a las 12:02; puede hacerlo desde las 12:03. |
| Volumen 10, participación 1%, orden 0,15, paso 0,01 | Capacidad 0,10, fill 0,10 y remanente 0,05 que expira al cerrar la ventana. |
| Dos órdenes para la misma ventana | La suma ejecutada respeta una única capacidad disponible. |
| Volumen cero frente a archivo ausente | El primero no llena; el segundo produce un fallo de cobertura explícito. |
| Sizing numérico de la sección 6 | Compra bruta 0,03904 y neta 0,03900096, respetando tolerancia y presupuesto. |
| Ninguna combinación cumple mínimo y presupuesto | Rechazo previo, sin compra ni comisión. |
| Primera o segunda pata parcial, o cierre reintentado | Inventario, remanentes y costos reales conservados, sin duplicación ni sobreventa. |
| Funding y fill al mismo timestamp | Funding sobre la cantidad previa al fill, exactamente una vez. |
| Fill y vencimiento de su ventana coinciden | Primero se contabiliza el fill válido y luego expira el remanente. |
| Riesgo aparece al terminar una ventana | No borra fills ya comprometidos; bloquea nuevos aumentos y prioriza salida. |
| Cambio de costos 1x, 2x y 3x en la fixture de sizing | Cantidades recalculadas antes de comprar; no queda fija la compra bruta por accidente. No exigir monotonicidad artificial del P&L. |
| Dos instancias con filtros de funding igualmente desactivados | Órdenes, ledger y equity iguales con estados independientes. |
| Corte final y replay por particiones | Sin ejecuciones fuera de muestra y con resultados iguales al replay continuo. |

Verificá además una secuencia integral con ambas patas, funding, margen, salida y conciliación contable. Conservá las pruebas relevantes del motor anterior bajo su política correspondiente. No marques pruebas como pasando sin ejecutarlas.

## 10. Plan de trabajo y salidas

Avanzá en este orden, registrando comandos reales y resultados:

- [ ] Inspeccionar proyecto y fijar referencia, configuraciones, archivos a modificar y diferencias metodológicas.
- [ ] Validar los campos y timestamps de velas existentes; completar únicamente klines indispensables.
- [ ] Implementar y probar sizing conjunto como cambio aislado.
- [ ] Implementar y probar el contrato de ejecución por minuto, integración con ledger y prioridades temporales.
- [ ] Agregar diagnóstico de filtros e informes de cobertura.
- [ ] Ejecutar una muestra real pequeña con calentamiento suficiente y conciliación.
- [ ] Ejecutar la matriz anual, reutilizando resultados verificados cuando corresponda.
- [ ] Generar comparación y documentación reproducibles, con los comandos efectivamente probados.

Cada corrida debe tener identificador propio, configuración efectiva, versión del código y manifiesto de datos. Conservá órdenes, fills, ledger, señales, eventos de riesgo y equity. Cada fill debe identificar su vela, ventana, precio de referencia, slippage, fee, cantidades y motivo.

Creá un informe `execution_revision_report.md` dentro del directorio de resultados que el proyecto ya utilice. Debe comparar retorno neto, Sharpe, drawdown diario, P&L por spot/futuros/funding/costos, número de ciclos completos y fallidos, fills parciales, capital utilizado y tiempos con carry cubierto y exposición sin cobertura. Separá el polvo residual del carry activo. Recalculá H1, H2 y H3 conforme a la metodología vigente, sin inventar Sharpe cuando es indefinido ni convertir dos ventanas en una serie continua.

Documentá la conciliación económica y los motivos de diferencias. Mostrá resultados negativos, cero operaciones y escenarios incompletos con su estado real. El escenario principal nuevo es `vwap_joint`, elegido por este diseño antes de observar su rendimiento, no por ser el mejor de la tabla.

Actualizá README y metodología con instalación, pruebas, preparación de datos, corrida y reporte. Las decisiones rutinarias quedan delegadas: resolvelas y avanzá. Si un bloqueo real de datos impide una corrida histórica, completá la implementación y las pruebas posibles e informá exactamente qué falta. No fabriques datos ni cambies de frecuencia para ocultarlo.

Al terminar, respondé brevemente con qué implementaste, qué verificaste, las ventanas efectivamente ejecutadas, dónde están los resultados, por qué opera o no opera cada estrategia y el comando concreto para reproducir la comparación.

## Referencias técnicas

- [Binance Public Data: campos de klines y unidades de timestamps](https://github.com/binance/binance-public-data).
- [Binance Spot API: filtros de cantidades y nocionales](https://github.com/binance/binance-spot-api-docs/blob/master/filters.md). Las reglas actuales no sustituyen sin advertencia las reglas históricas.
- [NautilusTrader: ejecución con barras](https://nautilustrader.io/docs/latest/concepts/backtesting/bar-execution/). Contrastá las APIs con la versión instalada y fijada por el proyecto.

Estas referencias respaldan fuentes y restricciones técnicas. El contrato de ejecución, la participación del 1% y el registro de fills al final del minuto son supuestos expresos del estudio, no garantías de Binance.

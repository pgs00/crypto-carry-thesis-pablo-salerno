# Encargo para Codex: riesgo intradía, incidentes y garantías

Trabajá en el proyecto Backtesting del repositorio `pgs00/crypto-carry-thesis-pablo-salerno`.

## 1. Objetivo y feedback recibido

Continuá desde la corrección de exposición y H2 ya publicada. Prepará un análisis ejecutado de pérdidas transitorias, drawdown intradía y necesidades de garantías que responda al feedback de la Entrega 3. No te limites a otro plan ni repitas las sensibilidades terminadas.

El profesor ya dio esta devolución. Conservala literalmente en un documento nuevo de feedback:

> La simulación contempla varios problemas de ejecución y los deja documentados, incluido el episodio en que la posición spot quedó sin cobertura. También reconocés que el filtro no supera a la alternativa que mantiene la operación sin esa condición de entrada.
> Para la cuarta entrega, revisaría qué pérdidas y necesidades de garantías pueden generar esos incidentes. El drawdown medido a cierres diarios puede ocultar parte del riesgo durante la jornada.
> Conservá la desagregación anual: el promedio desde 2024 no muestra una mejora sostenida, porque 2025 y 2026 son mucho más débiles. Conviene además leer el retorno junto con el capital utilizado. Como complemento, podés comparar con una alternativa remunerada para el capital disponible, dejando claros sus supuestos.

Este encargo desarrolla el bloque de riesgo observado y garantías, y reutiliza el desglose anual. La alternativa remunerada y las nuevas simulaciones hipotéticas quedan identificadas para el bloque siguiente. No declares que este trabajo completa toda la Entrega 4 o todo el feedback.

Las definiciones y experimentos adicionales de este prompt son decisiones metodológicas del encargo, no palabras ni exigencias numéricas del profesor. El informe sigue siendo técnico preliminar, pero ya no debe decir que estamos esperando la devolución de la Entrega 3. No edites las notas históricas de los paquetes sellados.

## 2. Punto de partida y preservación

Identificá instrucciones del proyecto, raíz real, rama, HEAD, entorno, datos locales y cambios existentes. La referencia revisada es el commit `6be02c00bfc6ebcdbd72b4ff9da386bb68084b5b`; no vuelvas a ese commit ni descartes correcciones posteriores.

Fuentes que debés leer y verificar:

- Paquete padre con las doce carteras: `entregas/entrega_4/reglas_historicas/20260925T005436Z/`.
- Corrección de exposición/H2: `entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/`.
- README, auditoría de linaje y verificaciones de la carpeta que contiene esa corrección.
- `docs/methodology.md`, `scripts/rules_sensitivity_exposure.py` y `scripts/rules_sensitivity_h2.py`.
- Configuraciones efectivas, manifiestos y esquemas reales de posiciones, ledger, eventos, órdenes, fills y patrimonio. Leé el código económico congelado que generó cada corrida, no sólo la versión activa.
- `Paquete de evidencia` y el PDF presentado, si están disponibles. No afirmes haber leído un PDF ausente.

Las carteras BASE_E3 son:

- Condicional: `run_ad71d751b20623006c195ff3`.
- Permanente: `run_dfea4b7ac1475668d5968c97`.

Ambas parten de 10.000 USDT, sobre `[2022-01-01T00:00:00Z, 2026-09-01T00:00:00Z)`, sin reinicios anuales. La permanente omite sólo el filtro de funding de entrada y renovación; conserva basis y controles operativos. No la conviertas en una cartera sin restricciones ni en otra estrategia.

Guardá huellas iniciales. Conservá intactos E3, fuentes históricas, paquetes padre/corrección, corridas, configuraciones económicas, manifiestos y snapshots originales. Generá productos con identidad propia y vinculados a sus entradas. No cambies hashes viejos ni copies otra vez los paquetes completos por defecto.

La corrección ya recuperó la clasificación de E3. No vuelvas a contar cualquier saldo positivo como posición activa. Usá la semántica verificada de `covered`, `unhedged`, `dust` y `flat`, con el orden persistido y la memoria de residuos. El polvo sigue incluido en patrimonio y riesgo de precio, aunque se informe por separado del riesgo de posiciones activas.

## 3. Alcance de ejecución y orden de trabajo

1. Verificar entradas y registrar el protocolo antes de calcular los nuevos resultados.
2. Reconstruir riesgo intradía de las dos BASE en toda la muestra, no sólo en fechas elegidas.
3. Catalogar los incidentes y analizar las garantías mientras existan cortos abiertos.
4. Elaborar el detalle del 24/03/2023 y de los episodios más relevantes según criterios explícitos.
5. Integrar el desglose anual existente y preparar el reporte y la evidencia.

Reutilizá las dos corridas MARGEN_2X ya existentes como comparación adicional de diagnóstico cuando puedan procesarse con la misma reconstrucción. No repitas sus backtests. No amplíes por defecto este trabajo a todas las variantes de costos ni lances la matriz general de E4.

Primero intentá reconstruir mediante posprocesamiento. Un archivo `positions.parquet` con estados en eventos y cierres diarios NO equivale a una serie de patrimonio por minuto. Comprobá qué otras tablas hacen falta para reconstruir efectivo, garantías, funding, deuda y precios.

Sólo si demostrás una carencia indispensable autorizo un replay instrumentado de la referencia afectada, con idénticos datos y reglas económicas. Documentá antes qué registro falta y por qué no puede derivarse. Agregá observación opt-in, sin alterar decisiones, tarifas, tamaños, riesgo ni orden de eventos. Probá equivalencia en una ventana corta y luego en fills, posiciones, funding, estados financieros y cierres diarios de la corrida completa. Conservá un identificador nuevo y `source_run_id` original. No llames posprocesamiento a una simulación nueva ni ejecutes variantes de estrategia para resolver una carencia de registro.

## 4. Reconstrucción temporal y contable

Construí una trayectoria de valoración con cierres de velas de un minuto y los instantes financieros necesarios para la conciliación. Conservá timestamps UTC exactos, disponibilidad de cada dato y secuencia de eventos; no redondees funding a una hora nominal ni cambies la asignación de día para facilitar coincidencias.

Especificá en el protocolo:

- El instante de la vela, cuándo su cierre se conoce y qué estado contable se valúa.
- Cómo se incluyen los cierres diarios originales y los eventos que ocurren entre puntos de la grilla.
- Si la serie utilizada para drawdown es una grilla de minuto o la unión de minutos y eventos. Rotulala exactamente; no la presentes como tick-by-tick.
- El tratamiento de estados pre/post funding y ejecución cuando compartan timestamp. Los cambios instantáneos no agregan duración, pero pueden cambiar la necesidad inmediata de fondos.

Respetá la secuencia de la corrida: datos disponibles, funding sobre el corto previo a fills simultáneos, fills comprometidos y controles posteriores. Usá el orden documentado y persistido para resolver empates. No construyas un orden nuevo por nombre de evento.

Reconstruí, por cartera:

`equity = caja_spot + caja_futures + garantías + valor_spot + P&L_no_realizado_futuros - deuda`.

Usá cantidades, precios medios y estados de caja/garantía originales. El spot se valúa con la referencia spot y los futuros con el mark de riesgo, no con un precio de ejecución arbitrario. Las transferencias y movimientos de garantía no son ganancias. No dupliques funding, comisiones o slippage.

Arrastrar el último estado de una cuenta sólo es válido si sus cambios están completos y ordenados. No interpoles equity entre cierres diarios ni supongas que las garantías permanecen iguales entre dos snapshots sin contrastar los movimientos del ledger.

Conciliá todos los cierres diarios con la evidencia original, con sus timestamps, convenciones y tolerancia monetaria existente. Guardá los residuos, causas y cobertura. Una diferencia no justificada impide interpretar las métricas nuevas de esa reconstrucción; no ajustes tolerancias ni parámetros para esconderla.

Separá incertidumbre de precios de integridad contable. Poder conciliar una valoración con precios antiguos no acredita que esos precios representaran el mercado durante una interrupción. Si quedan instantes no evaluables, informá cobertura y límites: no suprimas esos huecos para declarar un máximo observado y completo de toda la muestra.

## 5. Precios faltantes y suspensión spot

La valoración principal debe reproducir la convención de la corrida original. Marcá por observación: origen del precio, cierre/fecha de disponibilidad, antigüedad, valor oficial o aproximado y razón de cualquier arrastre. Conservá las excepciones documentadas de marks y funding; no confundas sus dos problemas distintos.

Durante una suspensión, el último spot conocido puede quedar constante. No presentes esa constancia como ausencia de pérdida intradía, ni rellenes con el precio futuro de reapertura. Un minuto sin negociación no ofrece necesariamente un precio spot nuevo.

Como diagnóstico adicional de valoración, no de ejecución, prepará para el intervalo spot suspendido del 24/03/2023:

`S_proxy(t) = S(s) * F(t) / F(s)`.

Aquí `s` es la última observación spot/perpetuo alineada y disponible anterior al hueco; `F(t)` es un cierre de perpetuo ya disponible al instante valorado. Mantené fija el ancla durante el hueco. La hipótesis es conservar la relación spot/perpetuo del ancla, no recuperar el precio spot real ni demostrar convergencia del basis.

Identificá esta serie como `valoracion_proxy_hipotetica`. Mantené las posiciones, caja, operaciones y decisiones originales. Cuando vuelve el spot válido, retomá su precio y explicá cualquier diferencia con el proxy. Si falta un ancla o un precio de futuros necesario, dejá la observación no evaluable: no inventes datos ni amplíes silenciosamente la excepción.

Compará la valoración original con este diagnóstico separado. No lo registres como un nuevo resultado histórico del backtest ni como una venta posible durante la suspensión. No uses precios actuales. No combines el mínimo spot y el máximo del mark de una vela como si necesariamente hubieran ocurrido al mismo tiempo.

## 6. Drawdown e incidentes

### Drawdown comparable

Usá `DD(t) = equity(t) / max(equity(u), u <= t) - 1`, incluyendo el capital inicial. Conservá el signo y las convenciones de métricas de E3. Si el patrimonio no es positivo, informá el evento y el tratamiento explícito, sin truncarlo para mejorar el resultado.

Calculá por cartera, muestra completa, años y cortes originales:

- Drawdown diario original y drawdown de la reconstrucción intradía, con instantes de máximo previo, mínimo y recuperación cuando exista.
- Peor caída desde el patrimonio al inicio de la jornada y peor caída desde un máximo intradía. Son métricas distintas; no las llames indistintamente drawdown máximo.
- Diferencia absoluta entre las medidas en puntos porcentuales y USDT cuando corresponda. No dividas por un drawdown diario cero.

En cada comparación, usá el mismo período, patrimonio inicial, política de máximo previo y valoración. Si los cierres diarios forman un subconjunto de la trayectoria intradía conciliada, el drawdown intradía no puede ser menor en magnitud que el diario. Investigá cualquier incumplimiento; no lo corrijas cambiando el máximo inicial.

Mantené dos convenciones claramente separadas para cortes: máximo acumulado de la trayectoria completa y drawdown del período con máximo reiniciado en su saldo inicial real. Compará diario/intradía bajo una misma convención. No reinicies efectivo ni posiciones.

### Catálogo sin selección favorable de episodios

Catalogá todos los intervalos de exposición activa sin cobertura de BASE. Agrupá intervalos contiguos de un mismo episodio sin fusionar silenciosamente incidentes separados. Conservá identificadores de cartera, activo, ciclo y órdenes relacionadas. Uní tiempos a nivel cartera, no los sumes entre activos simultáneos.

Distinguí aperturas secuenciales normales, parciales, desarmes, cierres demorados, correcciones de descalce e interrupciones documentadas. No llames incidente extraordinario a toda espera normal de una pata ni inventes una causa cuando el log no la acredita.

Para cada episodio informá duración, cantidades, exposición neta firmada y absoluta en USDT, valoración usada, cambio de patrimonio desde el inicio, peor pérdida transitoria y resultado al finalizar. Separá el resultado de la cartera de la contribución del activo afectado. Si cambian las cantidades durante el episodio, integrá los movimientos reales en lugar de mantener ficticiamente la cantidad inicial. El P&L ocurrido durante un incidente no es automáticamente P&L causado por el incidente.

El detalle del 24/03/2023 debe mostrar antes, durante y después de la interrupción, no sólo 12:00-14:01. Como controles a verificar, las BASE conservan 121 minutos de spot descubierto en ETH condicional y BTC/ETH permanente. La unión de cartera es 121 minutos para cada una. El total de exposición activa descubierta de la muestra base es 11.340 y 16.440 segundos, respectivamente; son controles provenientes de la corrección, no cifras a imponer.

Además de ese episodio, detallá el de peor caída de equity y el de menor holgura de margen de cada cartera, usando criterios fijados en el protocolo y manteniendo visible el catálogo completo. Pueden ser episodios diferentes o coincidir. No omitas un episodio porque haya terminado con ganancia.

## 7. Garantías y liquidez disponible

Mientras exista corto abierto, reconstruí por contrato: cantidad, nocional al mark, garantía aislada, precio medio, P&L no realizado, saldo de margen, mantenimiento, holgura, ratio de mantenimiento y distancia a liquidación. Usá las funciones y tramos efectivos de la corrida, no condiciones actuales ni una historia de reglas completada artificialmente.

Según la metodología base:

- `margin_balance = garantía + cantidad_corta * (precio_medio_venta - mark)`.
- `maintenance = nocional * tasa_del_tramo - deducción_del_tramo`.

Confirmá esas expresiones con el código aplicable, sus fronteras y redondeos. En MARGEN_2X, el estrés duplica el importe de mantenimiento, no el apalancamiento elegido ni únicamente una tasa aislada.

Separá tres preguntas:

1. Cuál era el mantenimiento exigido y cuánta holgura quedaba en cada instante.
2. Cuánto faltaría para llegar a la frontera de mantenimiento: `max(0, maintenance - margin_balance)`.
3. Cuánto capital adicional exigiría una política de conservar los umbrales preventivos de la estrategia, considerando tanto el ratio como la distancia a liquidación.

Las dos últimas son necesidades instantáneas hipotéticas sobre los estados originales, no aportes efectivamente ejecutados. Para la tercera, derivá las condiciones exactas del código: una igualdad en el límite puede activar una salida. No afirmes que alcanzar mantenimiento evita automáticamente toda liquidación, cargo o salida preventiva.

Si calculás una transferencia hipotética, contabilizala de caja libre a garantía, sin generar equity nueva. No alteres las carteras publicadas. Compará la necesidad conjunta simultánea con los fondos realmente libres, descontando compromisos verificables; no reutilices la garantía de otro contrato, no cuentes ganancias spot no vendidas como efectivo y no uses dos veces la misma caja.

Informá por separado fondos redistribuibles y faltante externo teórico. Si no puede acreditarse la disponibilidad exacta por órdenes pendientes, documentá esa limitación en vez de asumir disponibilidad total. No sumes déficits instantáneos de minutos consecutivos como si fueran una secuencia de aportes, ni sumes máximos por activo ocurridos en momentos distintos como necesidad simultánea de cartera.

Un saldo de margen no positivo es una señal de riesgo, no un ratio tranquilizador. Cuando no exista futuro abierto, mantenimiento de ese contrato será cero y ratio/distancia serán no aplicables. No calcules garantías para un corto inexistente.

En particular, durante los 121 minutos de spot descubierto del 24/03/2023 los futuros de los activos afectados ya estaban cerrados. Analizá sus garantías antes del cierre y el riesgo de precio del spot después. No agregues una necesidad de margen de futuros a ese tramo por el solo hecho de llamarse incidente operativo.

## 8. Resultados anuales y siguiente bloque

Reutilizá las tablas financieras verificadas para presentar 2022, 2023, 2024, 2025 y enero-agosto de 2026. Mostrá juntos P&L, retorno, CAGR con su período claro, drawdown diario/intradía, tiempo activo sin polvo, utilización diaria media y máxima, y medidas de margen. No compares el retorno parcial de 2026 como si cubriera doce meses.

Distinguí patrimonio, capital utilizado, garantía y caja libre. No calcules un supuesto retorno comparable dividiendo CAGR por utilización media. No alteres H1, el criterio corregido de H2 ni los cortes originales de H3. Las cifras anuales deben describir el debilitamiento o estabilidad que realmente muestren, sin forzarlas a una conclusión.

Al cerrar, proponé una tanda pequeña, todavía no ejecutada, para demoras de cierre y movimientos adversos mientras exista exposición. Definí comparadores, magnitudes justificadas y qué requeriría una nueva trayectoria. No uses retrospectivamente los resultados para elegir sólo escenarios favorables ni les asignes probabilidades no estimadas.

Dejá explícitamente pendiente la comparación remunerada sugerida como complemento: alternativa para todo el capital versus remuneración sólo del efectivo libre son experimentos diferentes. No selecciones una tasa, producto o reinversión sin especificar moneda, datos, disponibilidad, costos, riesgos y tratamiento de garantías. No modifiques ahora el Sharpe de H2 ni sumes intereses al P&L base.

El escenario hipotético sin interrupción comprometido anteriormente sigue siendo otro análisis. La valoración proxy con posiciones fijas de este encargo NO lo sustituye ni lo da por completado.

## 9. Implementación y pruebas

Usá módulos de posprocesamiento pequeños, reutilizá verificadores existentes y evitá una nueva infraestructura general. No rehagas la corrección de H2/exposición ni regeneres paquetes antiguos. Identificá rutas e interfaces nuevas en un plan breve y luego ejecutalo.

Procesá los precios por bloques, compartiendo lectura entre carteras. Medí primero una ventana corta. No cargues innecesariamente millones de objetos Decimal a la vez, no dupliques fuentes por escenario y no descargues trades ni agregues activos o fechas. Si faltan datos locales indispensables, terminá las tareas independientes, registrá el bloqueo exacto y dejá comandos de continuación; no fabriques una serie histórica con fixtures.

Antes de implementar, escribí pruebas pequeñas con expectativas explícitas. Como mínimo:

- Equity inicial 100, valor intradía 80 y cierre 101: drawdown intradía -20%, diario 0%, sin costos ni movimientos externos.
- Una posición spot y un corto de igual cantidad pueden compensar su cambio de precio total mientras empeora el saldo del margen aislado. Comprobá ambas cosas por separado.
- Transferir 10 de caja libre a garantía conserva equity y reduce caja libre en 10.
- Dos necesidades simultáneas de 60 con caja libre común de 100 dejan faltante teórico de 20, no cero; máximos en momentos distintos no se suman automáticamente.
- Futuro cerrado, spot aún abierto: no hay requerimiento de mantenimiento de ese futuro, pero sí exposición spot.
- Funding y fills simultáneos, comisiones únicas, estados pre/post, movimientos de garantía y deuda.
- Polvo versus exposición activa, posiciones simultáneas, herencia de estado en cortes y fronteras temporales exactas.
- Fuente ausente o antigua identificada; proxy causal sin usar la reapertura futura; ningún fill inventado con volumen cero.
- Tabla de mantenimiento y umbrales de seguridad en ambos lados de sus fronteras; ND y patrimonio/margen no positivos.
- Conciliación diaria, relación entre drawdowns con grillas anidadas, detección de corrupción y verificación de sólo lectura.

No obligues a que todos los indicadores den un valor favorable ni a que cada incidente tenga pérdida. Conservá resultados nulos, adversos y no evaluables con su motivo.

## 10. Productos y verificación final

Usá una carpeta nueva bajo `entregas/entrega_4/riesgo_intradia/`, con identificador real de ejecución. Documentación y scripts pueden quedar en las carpetas equivalentes del proyecto. No crees otra raíz Backtesting.

Entregá:

- Feedback literal, protocolo y matriz de cobertura que separe feedback, consigna, compromisos previos y decisiones del encargo.
- Reporte Markdown y HTML legibles, con síntesis de hallazgos y límites. No generes todavía el PDF final ni reescribas E3.
- Tablas de drawdown comparable, catálogo de episodios, detalle del 24/03/2023, garantías/liquidez y resumen anual.
- Figuras con UTC, unidades, fuente y distinción entre valoración original y proxy. Evitá tablas de números con decenas de decimales en el cuerpo; conservá precisión completa en archivos de evidencia.
- Fuente de cada cifra, `run_id`, entradas, política de valoración y estado: reutilizado, reconstruido, hipotético o replay instrumentado.
- Un verificador de sólo lectura, manifiesto nuevo, pruebas y registro de comandos/resultados reales.

Conservá la serie intradía completa en formato comprimido local, con su procedencia y hash. El paquete publicable debe incluir evidencia suficiente para revisar los episodios y las cifras que declara verificables. No subas por defecto todos los datos masivos ni dupliques el paquete padre. Declarar una dependencia es preferible a fingir que el producto es autocontenido.

Distinguí verificación completa con precios y estados locales de verificación compacta de aritmética y tablas. Si la exportación no incluye la serie completa, no afirmes que desde ella se recalculó independientemente el máximo drawdown de toda la muestra. Documentá entradas y comandos para cada alcance, con rutas proporcionadas por argumento.

Antes de cerrar, ejecutá las pruebas relevantes, Ruff, verificación de entradas preservadas, conciliación de todos los cierres y una prueba desde otra ruta. Comprobá que verificar no escriba dentro de fuentes o paquetes sellados. No exijas HEAD/índice iguales a una sesión pasada para aprobar integridad publicada. No actualices manifiestos históricos para hacer pasar controles de otro alcance.

Si hubo replay instrumentado, documentá las comparaciones económicas reales; no basta igualar el saldo final redondeado. Un error genuino del motor fuera de alcance se informa por separado y no se corrige silenciosamente como si fuera sensibilidad.

No hagas commit, push, cambios de índice, reset destructivo, renormalización global, escrituras en servicios externos ni uso de credenciales de cuenta. No inventes pruebas aprobadas ni resultados de una corrida que no terminó.

Resumen final requerido: qué riesgo pudo reconstruirse, cuánto difiere del diario, cuáles fueron los incidentes relevantes, qué holgura o necesidad hipotética de fondos apareció, qué datos siguen faltando y qué parte del feedback queda pendiente. No marques toda la Entrega 4 como completa.

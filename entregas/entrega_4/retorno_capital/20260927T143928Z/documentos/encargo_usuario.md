# Encargo para Codex: bloque 1, retorno, capital y diagnósticos

Trabajá en el proyecto Backtesting del repositorio `pgs00/crypto-carry-thesis-pablo-salerno`.

## 1. Objetivo y alcance cerrado

Este encargo agrupa tres preguntas relacionadas para la Entrega 4:

1. ¿En cuántos ciclos y días se concentra el resultado de las carteras?
2. ¿Qué condiciones restringen las entradas y cómo se relaciona esto con el tiempo activo y el capital utilizado?
3. ¿Contra qué alternativa remunerada conviene comparar el capital completo, con fuentes y supuestos explícitos?

Ejecutá de principio a fin los dos primeros análisis, con pruebas, tablas y reporte. Para el tercero, investigá y prepará una propuesta verificable. Todavía NO se eligieron tasa, instrumento ni metodología de remuneración: antes de calcular una comparación histórica remunerada, necesitás la aprobación expresa del usuario de esa propuesta. La aceptación de este bloque no constituye aprobación de un producto o una tasa no especificados.

No frenes los diagnósticos independientes por esa decisión pendiente. Podés investigar candidatos mientras avanzás con ellos, pero no lances varios procesos que modifiquen los mismos scripts o salidas. Al cerrar, formulá una única pregunta concreta sobre la alternativa recomendada y su protocolo. Con la aprobación posterior, continuá sólo ese componente, reutilizando los diagnósticos ya terminados.

El profesor pidió estudiar pérdidas intradía y garantías, conservar la desagregación anual, leer retorno junto con capital utilizado y, como complemento, comparar con una alternativa remunerada. El bloque intradía ya fue desarrollado. Este encargo no lo rehace ni completa por sí solo toda la Entrega 4.

## 2. Inspección, fuentes y referencia

Leé las instrucciones del repositorio. Identificá raíz, rama, HEAD, entorno, cambios locales e índice. No reviertas trabajo ajeno. La última referencia revisada fue `120f94309e724a7a25e68e5ade67eed43a98f9e7`; comprobá cambios posteriores, sin volver automáticamente a ese commit.

Leé y verificá las fuentes pertinentes:

- Padre de las doce carteras: `entregas/entrega_4/reglas_historicas/20260925T005436Z/`.
- Corrección vigente de exposición y H2: `entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/`.
- Riesgo intradía: `entregas/entrega_4/riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z/`. Leé especialmente `documentos/feedback_e3.md`, el reporte y la cobertura pendiente.
- `docs/methodology.md`, las configuraciones y manifiestos efectivos, `scripts/rules_sensitivity_exposure.py` y `scripts/rules_sensitivity_h2.py`.
- `scripts/continuous_delivery/portfolio.py`, especialmente `cycle_rows()`, y el código archivado de E3 que produjo sus entradas.
- `src/crypto_carry/diagnostics.py`, especialmente `signal_diagnostics()`, `renewal_diagnostics()` y `FILTER_ORDER`, junto con las llamadas y decisiones del motor congelado aplicable. Inspección de sólo lectura, no ejecución del motor.
- `Paquete de evidencia`, sus tablas de ciclos, exposición y decisiones que realmente existan. Localizá los archivos por sus manifiestos, sin inventar nombres ni afirmar haber leído un PDF ausente.

Alcance económico principal: únicamente las dos BASE_E3, condicional `run_ad71d751b20623006c195ff3` y permanente `run_dfea4b7ac1475668d5968c97`. Cada una inicia con 10.000 USDT, BTCUSDT/ETHUSDT spot y perpetuos USD-M, trayectoria continua en `[2022-01-01T00:00:00Z, 2026-09-01T00:00:00Z)`.

No amplíes automáticamente el diagnóstico a las doce carteras. Podés citar comparaciones de costos ya verificadas como contexto, sin recalcularlas ni convertirlas en nuevas pruebas de este bloque.

Conservá las definiciones: entrada condicional con pronóstico superior al costo del ciclo; renovación con pronóstico positivo; permanente sin esos filtros de funding pero con los demás controles. El basis de entrada base admite `[0, 0,005]`. Recuperá los demás parámetros de cada configuración efectiva, no de cifras redondeadas del reporte.

Inventariá y autenticá las entradas antes de calcular. Preservá E3, motor económico, configuraciones, carteras, paquetes sellados, código congelado y verificaciones anteriores. No cambies H1, H2, H3 ni sus resultados financieros.

## 3. Protocolo y etapas

Escribí un protocolo breve antes de producir las nuevas tablas, con población, unidad de análisis, períodos, fórmulas, fuentes, comparadores, convenciones de atribución y controles de aceptación.

Orden de ejecución:

1. Autenticar entradas, comprobar esquemas e identificar qué diagnósticos ya existen.
2. Implementar y verificar concentración y atribución por ciclos/días.
3. Implementar y verificar restricciones de entrada, sin mezclar diagnósticos con decisiones efectivamente ejecutadas.
4. Integrar los dos análisis con el resumen anual y preparar la propuesta remunerada.
5. Publicar localmente un paquete nuevo verificable y el estado de cada tarea. No hacer commit ni push.

Una fase con cifras no conciliadas no habilita conclusiones sobre ellas. Un bloqueo específico no impide completar las otras fases. No agregues optimizaciones, parámetros ganadores, escenarios de demora, shocks, nuevos backtests o inferencia estadística de los bloques posteriores.

## 4. Concentración del resultado por ciclos y días

### Identidad y atribución

Usá los identificadores originales de cartera, activo, ciclo, órdenes y operaciones. Distingí intentos sin ejecución, aperturas incompletas, ciclos cerrados y posiciones abiertas al final. Una renovación no es una operación nueva si la semántica original conserva el ciclo. No elimines intentos fallidos ni sus costos.

Reconstruí la contribución económica por ciclo desde sus movimientos y estados persistidos, no asignando todo el cambio de equity de la cartera al activo que estaba operando. Separá spot, futuros, funding, comisiones y cargos; el deslizamiento incluido en los precios no se descuenta nuevamente.

Con cantidades variables, rebalanceos o cierres parciales, usá los movimientos reales. Conservá resultado realizado y no realizado a cada corte. No supongas una venta terminal ni una comisión que no ocurrió.

La compra spot neta, su costo y la comisión deben respetar la contabilidad original. Trasladar dinero entre cuentas o constituir/liberar garantía no genera P&L. Un residuo incorporado a una entrada posterior no se compra de nuevo ni permite reconocer dos veces su ganancia previa.

El polvo sigue valuado en el patrimonio. Si su variación fuera de un ciclo activo no tiene una asignación inequívoca, informala en una categoría separada y documentada, sin adjudicarla arbitrariamente al ciclo siguiente. Cualquier importe no asignable debe tener fuente y motivo; no uses una bolsa de residuos para ocultar un fallo contable.

Conciliá la suma de contribuciones de ciclos y categorías explícitas fuera de ciclo con el P&L por activo y cartera. Respetá la tolerancia original `1E-8` USDT donde corresponda. No cambies tolerancias para obtener un pase.

### Períodos y medidas

Presentá muestra completa, 2022, 2023, 2024, 2025, enero-agosto de 2026 y los dos cortes originales de H3. Un ciclo que cruza el año contribuye a cada período por los cambios económicos dentro de ese período, sin reiniciar cuentas ni asignar todo su resultado al año de cierre.

Conservá adicionalmente una tabla de vida completa de los ciclos. No confundas atribución por fecha de los cambios económicos con agrupación por año de apertura o cierre.

Calculá número de ciclos por estado, contribución de BTC/ETH y concentración de los ciclos con resultado positivo y negativo. Como diagnóstico prefijado, mostrá los 1, 3 y 5 ciclos más rentables y los más perdedores; si hay menos, usá todos e indicá el número efectivo.

Usá denominadores explícitos:

- Ganancias positivas: `G = suma(max(P&L_ciclo, 0))`.
- Pérdidas absolutas: `L = suma(max(-P&L_ciclo, 0))`.
- Contribución positiva sobre G y contribución negativa sobre L, cuando sean positivos.
- Contribución sobre beneficio neto sólo identificada como tal, con advertencia si es pequeño o no positivo. No recortes porcentajes superiores a 100% ni los presentes como proporciones del capital.

Dejá visible el P&L fuera de ciclos activos y el grado de atribución logrado. Los porcentajes sobre G/L describen los ciclos incluidos, no automáticamente toda la cartera.

Para concentración diaria, reutilizá el P&L diario conciliado de cada cartera; mostrá los 1, 5 y 10 mejores y peores días. No sumes rentabilidades porcentuales para obtener el retorno acumulado ni trates dos activos simultáneos como dos días distintos.

No recalcules un CAGR ficticio «sin los mejores ciclos» restando sus ganancias. Quitar operaciones alteraría caja, tamaños y decisiones posteriores. Cualquier resta meramente descriptiva debe rotularse como atribución contable, no como backtest ni prueba causal.

## 5. Diagnóstico de restricciones de entrada

### Población y valores conocidos

Identificá el archivo real de diagnósticos persistidos y sus claves. En el código revisado existen `decision_kind`, `decision_time`, `funding_filter_enabled`, `estimated_cycle_cost`, `filter_funding`, `filter_basis_negative`, `filter_basis_above_max`, `sequential_rejection`, `simultaneous_rejections` y campos de estado, datos, fondos y sizing. Comprobá su presencia y semántica en los registros, no sólo en el código actual.

La población principal son los registros de evaluación de entrada (`decision_kind=entry`). Las renovaciones se analizan aparte, con su umbral cero y sus filtros propios; no les impongas el filtro de basis ni el costo de entrada.

Verificá unicidad y cobertura de las claves sin descartar empates legítimos: dos eventos simultáneos distintos pueden requerir secuencia o identificador adicional. No conviertas el historial de evaluaciones en un conteo de órdenes enviadas.

Separá valores `pass`, `fail` y `not_evaluable`. Conservar un dato desconocido no equivale a que el filtro falle, a que no existan oportunidades ni a que la estrategia esté voluntariamente inactiva.

### Tres vistas diferentes

**A. Coincidencia de los filtros de mercado.** Para evaluaciones con funding y basis evaluables, clasificá cada registro en exactamente una celda:

1. Pasan ambos.
2. Falla sólo funding.
3. Falla sólo basis.
4. Fallan ambos.

Agregá fuera de esas celdas los registros no evaluables con sus motivos. La partición debe reconciliar con la población declarada. Dentro de falla de basis, distinguí negativo de superior al techo; los límites 0 y 0,005 se admiten. Esto cuenta condiciones, no aperturas que necesariamente podían concretarse.

**B. Restricciones de la cartera y operatividad.** Mostrá por separado posición previa, cooldown, órdenes pendientes, deuda, calidad/frescura/alineación de precios, reglas, mercado no operativo, sizing y presupuesto. Conservá el orden registrado por el diagnóstico, no un orden elegido para hacer parecer dominante a un filtro.

Un gráfico de motivos simultáneos puede tener solapamientos y debe decirlo. Un embudo secuencial debe tener grupos excluyentes, denominadores y orden explícitos. No sumes rechazos simultáneos como si fueran oportunidades independientes perdidas.

**C. Acciones efectivas.** Cruzá las evaluaciones con transiciones, órdenes e intentos reales cuando las claves lo permitan. Separá «primer bloqueo según el diagnóstico» de «causa acreditada en el log de la decisión» y de «intento enviado que falló al ejecutar». No afirmes que toda fila que pasa el diagnóstico produjo una apertura.

### Diferencia esencial entre las estrategias

En la permanente se calcula el filtro de funding para análisis, pero no impide abrir ni renovar. Puede figurar como fallo en una vista descriptiva; no lo cuentes como rechazo aplicado cuando `funding_filter_enabled=false`.

Distinguí la evaluación prospectiva del tamaño de posición de una restricción efectivamente aplicada. Una fila generada mientras ya hay posición abierta no demuestra que se haya perdido una entrada por falta de fondos.

Mostrá resultados por activo, estrategia y períodos. Sólo emparejá registros entre carteras cuando compartan activo, instante y tipo de evaluación; informá cobertura y faltantes. Sus estados de caja y posiciones pueden ser distintos. No fuerces poblaciones idénticas ni interpretes el conteo bruto como una comparación causal.

Estas evaluaciones no son los minutos elegibles de H3. No sustituyas la serie de H3 por este diagnóstico ni uses el número de rechazos como porcentaje de tiempo fuera del mercado.

No calcules la rentabilidad hipotética de entradas rechazadas con resultados futuros para declarar qué filtro «debería» quitarse. Este bloque explica la referencia, no optimiza la estrategia ni ejecuta una ablación de filtros.

## 6. Retorno, capital y lectura anual

Integrá los dos diagnósticos con las métricas financieras y de exposición corregidas que ya existen: P&L, retorno, CAGR con período explícito, utilización media y máxima diaria, tiempo activo sin polvo, cantidad de ciclos e intentos fallidos.

Conservá 2026 como enero-agosto y no lo compares como doce meses observados. Diferenciá proporción de tiempo invertido de proporción del patrimonio utilizado. No dividas CAGR por utilización media para inventar una rentabilidad comparable sobre capital empleado.

La pregunta interpretativa es por qué una señal más precisa no mejoró el resultado económico en la referencia. Separá lo que muestran los registros de las explicaciones posibles. Pocos ciclos, filtros restrictivos y efectivo ocioso son diagnósticos; por sí solos no prueban cuánto rendimiento habría generado otra política.

Reutilizá H1 y la evaluación corregida de H2 sin redefinirlas. El análisis anual complementa H3 y no cambia su corte original. No rehagas el drawdown intradía ni sus series de millones de observaciones para este bloque.

## 7. Alternativa remunerada: propuesta con aprobación puntual

### Qué investigar ahora

Investigá como máximo dos alternativas defendibles para comparar una inversión inicial de todo el capital con las dos BASE, sobre el mismo período. Priorizá fuentes primarias, historia accesible y metodología transparente; no busques la alternativa que produzca la conclusión más favorable al carry.

Podés considerar un instrumento real de corto plazo o una cuenta/índice hipotético ligado a una referencia monetaria oficial. Presentalos como categorías distintas. Una tasa de referencia no es automáticamente un producto accesible para el inversor y una tasa publicada no equivale a una serie de retorno total.

Revisá moneda, naturaleza del rendimiento, cobertura, datos, metodología, reinversión, costos, mínimos, disponibilidad, riesgos y posibilidad real o hipotética de acceso. Para un instrumento, no reemplaces dividendos o retorno total por su cotización sin ajustar. Para una cuenta hipotética, no inventes un costo neto o una remuneración efectivamente pagada por un exchange.

La referencia del carry está en USDT. Si proponés un benchmark USD, explicitá el uso de la paridad USDT/USD como supuesto de comparabilidad del estudio, no como equivalencia de riesgo o convertibilidad garantizada. Una alternativa en otra moneda requiere una metodología de conversión explícita, no comparaciones directas de porcentajes.

Recuperá sólo los datos y documentos públicos necesarios para comprobar viabilidad y cobertura. Guardá originales, URL, fecha de consulta, fechas de vigencia/publicación y hash. No uses una tasa actual para toda la historia, no rellenes faltantes con cero, no extrapoles un producto a fechas anteriores a su existencia ni uses credenciales, cuentas privadas o proveedores pagos.

No calcules retornos acumulados de varios candidatos para elegir después el mejor. Seleccioná una recomendación por comparabilidad, trazabilidad y alcance, sin atribuirle aprobación del usuario ni del profesor.

### Propuesta que debe quedar lista

Entregá `propuesta_benchmark.md` y una ficha estructurada con:

- Candidato recomendado y alternativa descartada, con razones y fuentes.
- Instrumento real o construcción hipotética; moneda y relación con USDT.
- Serie exacta, campos, cobertura y tratamiento de días hábiles, fines de semana, feriados y años bisiestos.
- Regla de devengamiento/capitalización o retorno total; base de días de la fuente y unidades.
- Fechas de observación, devengamiento, publicación y revisión. Una tasa realizada que se publica después puede servir para medir un devengamiento retrospectivo, pero no era información disponible para decidir antes de publicarse.
- Alineación con los cortes y cierres UTC de las carteras, incluidos inicio y fin cuando no sean días hábiles. No desplaces silenciosamente la muestra para hacerla coincidir con la serie.
- Costos, conversión, disponibilidad y riesgos. Todo supuesto no verificado debe quedar identificado.
- Cálculos previstos y límites; datos faltantes concretos y decisión que falta aprobar.

Dejá el estado `pendiente_aprobacion_benchmark` cuando no exista aprobación previa explícita de esa ficha. No atribuyas a la aprobación general de este encargo una elección no definida. Terminá concentración, rechazos y sus verificaciones antes de solicitar la decisión final al usuario.

### Qué hacer sólo después de aprobarse la ficha

Conservá el protocolo aprobado y ejecutá una cartera benchmark separada, iniciada con 10.000 en la unidad acordada, sin transferencias hacia/desde el carry. Usá la serie histórica y la capitalización o metodología de retorno total aprobadas. Los cortes anuales deben conservar el saldo heredado; no reinicies capital cada enero.

Compará evolución del capital, P&L, retorno y CAGR sobre períodos alineados con las BASE. Aclarar si una tasa o índice hipotético no mide precios de liquidación; no presentar su estabilidad contable como ausencia de riesgo. No inventes una volatilidad o un Sharpe de cero ante una métrica indefinida.

Este benchmark es un complemento de costo de oportunidad. No sustituye a la permanente en H2, no cambia su Sharpe con tasa libre de riesgo cero ni altera H1/H3. No agregues el interés del benchmark al P&L de ninguna estrategia.

Remunerar el efectivo libre dentro de las estrategias y reinvertirlo continúa fuera de alcance. Requeriría otra política de disponibilidad y, si cambia capital utilizable o decisiones, otra trayectoria. No remuneres garantías o efectivo comprometido como si estuviera libre.

La incorporación posterior debe ir en una versión nueva que enlace los diagnósticos terminados, sin sobrescribir su sello ni repetir sus cálculos sin necesidad.

## 8. Pruebas de aceptación

Antes de implementar comportamiento nuevo, agregá casos pequeños con resultados esperados explícitos. Los fixtures no son resultados históricos. Como mínimo:

- Ciclos con P&L 100, 50 y -80: G=150, L=80 y neto=70; el mejor aporta 100/150 de las ganancias y 100/70 del neto. No limitar ese segundo cociente a 100%.
- Ciclo que cruza un año: contribuciones 80 y 120, total 200; no asignar todo al año de cierre.
- Renovación sin nuevo ciclo, intento fallido con costos y ciclo abierto al final sin cierre ficticio.
- Polvo heredado y su variación: conservar unidades, costo y P&L sin duplicar atribución; mantenerlo fuera del tiempo activo según la corrección vigente.
- Eventos simultáneos, funding sobre la posición correcta, comisiones únicas y transferencias sin P&L.
- Cuatro filas que representan las cuatro celdas funding/basis, más una no evaluable: conteos 1/1/1/1/1, total 5.
- Funding que falla en la permanente: fallo diagnóstico, no rechazo de entrada aplicado. Renewal con pronóstico positivo pero inferior al costo de entrada: no rechazar por ese costo.
- Basis negativo, cero, techo exacto y superior al techo; unknown no se convierte en cero.
- Motivos simultáneos frente a embudo secuencial; duplicados ilegítimos y empates legítimos; acciones reales sin enlace acreditable conservadas como no reconciliadas, no inventadas.
- Atribución por activo/ciclo/período conciliada con la cartera y misma información financiera antes/después.
- Constructor rechaza sobrescritura y verificador detecta cifras, clasificaciones, intervalos o denominadores alterados, además de hashes incorrectos.

Después de la aprobación del benchmark, añadí los tests específicos del método elegido: unidades de tasa, base de días, cobertura, fronteras, dividendos/capitalización si corresponden y conservación del saldo en cortes. No implementes por adelantado un motor genérico para todas las alternativas posibles.

## 9. Entregables, portabilidad y límites de escritura

Creá una carpeta nueva bajo `entregas/entrega_4/retorno_capital/`, con fecha real e identificador propio. Guardá código nuevo y pruebas en la estructura existente, con módulos pequeños. Reutilizá las herramientas verificadas cuando corresponda; no dupliques una infraestructura general ni refactorices `src/crypto_carry/`.

Entregá:

- Protocolo, mapa de fuentes y decisiones metodológicas.
- Reporte Markdown y HTML con concentración, restricciones de entrada, relación con capital utilizado y estado explícito del benchmark. No generes todavía el PDF final.
- CSV de ciclos y sus contribuciones por período, concentración diaria/por ciclos y conciliación de atribuciones.
- Registros clasificados de decisiones, grupos excluyentes, motivos simultáneos/secuenciales y cruce con acciones. Cada cifra debe remitir a su población y fuente.
- Resumen anual integrado y figuras con unidades, períodos y denominadores claros.
- Propuesta remunerada documentada; resultados remunerados sólo después de aprobar su ficha.
- Manifiesto nuevo, verificador, pruebas y comandos/resultados reales. Cada bloque tiene estado `ejecutado`, `parcial`, `bloqueado` o `pendiente_aprobacion_benchmark`, según corresponda.

El nuevo verificador debe recalcular las relaciones que declara comprobar, no sólo hashes. Usá dependencias padre/corrección por rutas explícitas; no copies otra vez cientos de MB. Documentá qué archivos son indispensables y el alcance con y sin fuentes completas. Probá desde otra ruta y sin depender de HEAD o índice de una sesión pasada. Resultados de auditoría en rutas nuevas externas, sin modificar evidencias selladas.

Ejecutá los tests pertinentes y Ruff con el entorno del proyecto. Verificá invariancia de las carteras y los valores financieros/H1/H2/H3 reutilizados, con los comandos aplicables a cada paquete. Un control histórico cuyo alcance quedó desactualizado se explica y conserva, no se hace pasar modificando su manifiesto.

Protegé los nuevos archivos de evidencia contra conversiones de finales de línea mediante reglas Git acotadas cuando sea necesario. No cambies configuración global, renormalices todo el repositorio ni alteres el índice del usuario.

Prohibido: nuevos backtests históricos, modificación del motor o parámetros económicos, eliminación de datos/ciclos desfavorables, descargas masivas de mercado, nuevas series intradía, servicios pagos, credenciales de cuenta, commit, push, reset destructivo o sobrescritura de paquetes previos.

Una ausencia de evidencia se documenta; no se completa con una explicación plausible ni con resultados inventados. Preservá trabajo independiente ya completado y dejá comandos concretos para continuar el bloque afectado.

## 10. Respuesta final de Codex

Resumí los hallazgos comprobados de concentración y rechazos, cómo se relacionan con el capital utilizado y qué afirmaciones siguen siendo sólo hipótesis. Indicá archivos, controles ejecutados, pendientes y límites.

Si el benchmark espera aprobación, cerrá con una única pregunta que identifique el candidato recomendado y remita a su ficha concreta, no con una pregunta genérica sobre qué hacer. No digas que ya comparaste una alternativa que sólo propusiste.

Si luego se aprueba, ejecutá esa comparación y entregá su versión nueva. En ningún caso presentes este bloque como la Entrega 4 completa ni confundas archivos preparados localmente con una publicación en GitHub.

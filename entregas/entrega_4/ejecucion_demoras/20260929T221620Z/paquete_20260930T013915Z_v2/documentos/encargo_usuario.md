# Encargo para Codex: bloque 4, convención de ejecución y demoras

Trabajá en el proyecto Backtesting del repositorio `pgs00/crypto-carry-thesis-pablo-salerno`.

## 1. Objetivo y alcance cerrado

Evaluá cuánto dependen los resultados de la referencia de precio de ejecución y de la demora hasta una ventana ejecutable. Implementá las extensiones mínimas, ejecutá las seis variantes de la sección 3 para ambas estrategias, conciliá y entregá un reporte con evidencia verificable. No te limites a presentar un plan.

Este bloque reúne tres familias: OHLC4 frente a VWAP; demora general de las órdenes del cliente; demora aplicada exclusivamente a órdenes de cierre. No combines familias, no optimices parámetros ni adoptes una configuración favorable de bloques anteriores.

El feedback de E3 ya fue recibido. Los bloques de riesgo intradía/garantías, retorno/capital con SOFR, señal/entradas y costos/capacidad están terminados con sus alcances documentados. No los rehagas. El objetivo final es redactar la Entrega 4 en Word una vez terminados y revisados los análisis: ahora no generes Word ni PDF final.

Las magnitudes y convenciones nuevas de este encargo son decisiones experimentales explícitas, no una estimación de latencia real de Binance ni requisitos numéricos del profesor. Enviar este prompt autoriza esa matriz y las adaptaciones acotadas aquí definidas. Consultá sólo decisiones que excedan el alcance.

## 2. Inspección y preservación

Leé las instrucciones del repositorio. Identificá raíz, rama, HEAD, entorno, datos locales, espacio y cambios ajenos, incluidos los preparados en el índice. La última versión revisada fue `d43d155c1a8f0444022b0226e75bcf5bd5dd926a`. No retrocedas automáticamente a ese commit ni descartes avances posteriores.

Leé y autenticá los materiales pertinentes:

- `docs/methodology.md`, `docs/entrega_4/matriz_avance.csv` y las configuraciones efectivas BASE.
- Padre: `entregas/entrega_4/reglas_historicas/20260925T005436Z/`.
- Corrección de exposición/H2: `entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/`.
- Riesgo intradía: `entregas/entrega_4/riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z/`, especialmente feedback, cancelaciones, garantías, valoración y propuestas de demoras.
- Bloque 1: `entregas/entrega_4/retorno_capital/20260927T143928Z/paquete_20260927T152732Z/` y `entregas/entrega_4/retorno_capital/20260927T154653Z_sofr/paquete_20260927T162350Z/`, sólo como contexto y dependencias.
- Bloque 2: `entregas/entrega_4/senal_entradas/20260927T170230Z/paquete_20260927T185305Z/`.
- Bloque 3 vigente: `entregas/entrega_4/costos_capacidad/20260927T200204Z/paquete_20260927T231610Z/`, su compatibilidad, auditoría de ejecución y límites. No uses sus candidatos anteriores como versión vigente.
- `Paquete de evidencia` y la consigna académica cuando estén disponibles. No afirmes haber leído un documento ausente.

Inspeccioná `src/crypto_carry/config.py`, `models.py`, `execution.py`, `strategy.py`, `costs.py`, `diagnostics.py`, `portfolio.py`, `ledger.py`, `nautilus_adapter.py`, la serialización/checkpoints y el lector de datos. Reutilizá componentes compatibles de `scripts/signal_sensitivity*`, `scripts/cost_capacity*` y los clasificadores corregidos de exposición/H2, sin alterar sus copias selladas.

Guardá hashes iniciales. Preservá E3, configuraciones BASE, datos originales, corridas y paquetes sellados. Las modificaciones activas autorizadas deben tener diff, pruebas e identidad propios. No actualices manifiestos históricos ni retoques otros bloques para corregir presentación.

## 3. Referencia y seis escenarios

Referencias originales:

- Condicional: `run_ad71d751b20623006c195ff3`.
- Permanente: `run_dfea4b7ac1475668d5968c97`.

Muestra continua UTC `[2022-01-01T00:00:00Z, 2026-09-01T00:00:00Z)`, 10.000 USDT por cartera, BTCUSDT/ETHUSDT spot y perpetuos USD-M. Derivá las configuraciones de las efectivas BASE, no de `Config()` con sus valores predeterminados.

| ID | Referencia de ejecución | Demora adicional por orden | Órdenes afectadas por la demora |
| --- | --- | --- | --- |
| E_OHLC4 | `(open + high + low + close) / 4` | 0 | Ninguna |
| L01 | VWAP BASE | 60 segundos | Todas las órdenes del cliente |
| L05 | VWAP BASE | 300 segundos | Todas las órdenes del cliente |
| LC01 | VWAP BASE | 60 segundos | Sólo `close_perp` y `close_spot` |
| LC05 | VWAP BASE | 300 segundos | Sólo `close_perp` y `close_spot` |
| LC15 | VWAP BASE | 900 segundos | Sólo `close_perp` y `close_spot` |

Cada variante tiene condicional y permanente: doce pares nuevos, más dos BASE reutilizables, catorce resultados previstos. Las corridas de control se registran aparte. No agregues L15, otras referencias de precio, combinaciones OHLC4+latencia ni cruces con costos o AUM.

L01/L05 retoman el plan general. LC01/LC05/LC15 concretan las magnitudes de cierre propuestas en el reporte intradía. Este encargo fija explícitamente su alcance como regla causal aplicada a TODOS los cierres correspondientes de cada nueva trayectoria, no sólo a los incidentes de BASE seleccionados retrospectivamente. Es una especificación de ese experimento, no una reproducción literal de la propuesta anterior sobre episodios catalogados. Conservá esa diferencia en el registro de decisiones y no ejecutes además otra tanda duplicada por calendario de incidentes.

Se mantienen: horizonte y tenencia 168 h; vida media 24 h; historial 336 h; precarga 360 h; disponibilidad de funding 60 s; basis inclusivo `[0,0.005]`; costo de selección de 34 pb; renovación condicional con forecast positivo; permanente sin filtro de funding. Capital 10.000, objetivo spot 30% por activo, garantía aislada 2x, comisiones BASE 0,10%/0,05%, deslizamiento 1 pb y multiplicador 1; sin promoción ni mantenimiento duplicado. Participación 1%, `joint_quantity`, reglas, stops, calendario, marks documentados y precios de funding BASE.

No copies `base_e3_total` desde las variantes de costos: conservá el modo de costo de decisión de la configuración BASE. Las extensiones optativas del bloque 3 deben seguir funcionando sin cambios.

## 4. Extensiones mínimas autorizadas

### Lo observado en la versión revisada

`minute_window(t)` redondea hacia arriba al comienzo del minuto y devuelve una única ventana de 60 segundos. `_submit()` asigna esa ventana desde el envío y fija el vencimiento efectivo en su final. `_fill_minute_windows()` usa `minute_vwap(bar)`. Varias ramas de riesgo/cancelación/segunda pata dependen de `execution_model == "next_minute_vwap"`; en ese modo la segunda pata no usa el retardo ordinario `leg_delay_seconds`.

Por eso, cambiar solamente `signal_delay_seconds` o `leg_delay_seconds` NO implementa el experimento solicitado. Tampoco sirve agregar un nombre nuevo de ejecución sin adaptar todas las ramas afectadas.

### Diseño acotado preferido

Si no existe ya una implementación equivalente, agregá opciones de investigación independientes del modelo temporal de ventana, por ejemplo:

- `research_minute_price_model`: `"vwap"` por defecto, `"ohlc4"` en E_OHLC4.
- `research_execution_delay_seconds`: entero no negativo, 0 por defecto.
- `research_execution_delay_scope`: `"all_client"` por defecto, `"close_only"` en LC.

Son nombres propuestos: reutilizá una interfaz equivalente si ya existe y documentá su correspondencia. No crees dos mecanismos para el mismo comportamiento. Restringí las opciones no predeterminadas a investigación prescrita y al modelo de ventana de un minuto; no las habilites silenciosamente para otras rutas.

Podés conservar `execution_model="next_minute_vwap"` como identificador técnico de la ruta temporal y variar únicamente la referencia mediante el nuevo campo. En tal caso, las salidas deben indicar explícitamente `reference_price_model="ohlc4"` cuando corresponda, sin presentar sus fills como VWAP.

Con opciones apagadas, conservá semántica, defaults, serialización y digest de configuraciones previas. Omití los nuevos valores predeterminados del formato canónico cuando sea necesario para preservar identidad histórica. Con opciones activas, registrá todos los valores económicos efectivos, incluidas demora y población afectada.

La autorización cubre cambios mínimos de configuración, selección del precio, asignación de ventanas, metadatos, persistencia, pruebas y auditoría. No rediseñes el motor, no cambies filtros ni lógica de cartera. Si encontrás un defecto económico preexistente que exija cambiar la referencia, documentalo y pedí aprobación para esa parte antes de mezclarlo con este bloque.

## 5. Contrato E_OHLC4

Aplicá OHLC4 sobre la MISMA vela completa que habría usado la referencia temporal BASE para esa orden. Conservá volumen real de esa ventana, step, tick adverso, deslizamiento, comisiones, límites de órdenes, secuencia y registro al cierre.

La cantidad solicitada se fija con información disponible al enviar, sin conocer el OHLC4 de la vela futura. Al cierre, el volumen, fondos y demás controles originales pueden producir un fill parcial o nulo. No uses el precio futuro para mejorar retrospectivamente el sizing.

Verificá OHLC válido, positivo y consistente, con `low <= open, close <= high`. Una vela sin actividad/volumen no habilita fills aunque tenga cuatro precios. Ausencia no documentada es un problema de datos, no un permiso para usar otra vela. No cambies ventanas ni inventes ejecución durante una suspensión.

No sustituyas con OHLC4 el cierre spot usado para señales/valoración, el precio de mark, el cálculo de basis ni el precio de funding. No reescribas velas ni alteres `quote_volume/base_volume` para fingir que OHLC4 era su VWAP. Persistí ambos valores en la auditoría y el utilizado en cada fill.

E_OHLC4 cambia la referencia de todos los fills de la ruta de ventana, incluidos los de propósito `liquidate` cuando usen esa misma ruta. No cambia sus disparadores, cargos, prioridad o reglas. Esto es sensibilidad de la convención agregada del motor, no reconstrucción del precio de una liquidación real.

No agregues una prueba al open: OHLC4 frente a VWAP es la única variante de precio autorizada. El promedio OHLC no acredita un precio ejecutable garantizado ni el orden de operaciones intravela.

## 6. Contrato temporal de las demoras

### Envío, elegibilidad y registro

Este experimento modela una demora adicional hasta que una orden puede acceder a su ventana de ejecución, NO una reconstrucción completa de red, confirmaciones o cancelaciones del exchange.

Para una orden enviada en `t`:

1. Conservá `submitted_at=t`, su cantidad e identidad originales. No reescribas el envío como si hubiera ocurrido después.
2. Determiná `delay_applied` por su propósito al crearla, sin mirar fills ni rentabilidad futura.
3. Definí `eligible_at=t + delay_applied`.
4. Definí `(window_start, window_end)=minute_window(eligible_at)`.
5. El único intento de esa orden usa esa ventana; el fill se registra al final, cuando sus datos están disponibles, conforme al orden de eventos BASE.
6. El vencimiento efectivo de esa orden es `window_end`, no la ventana calculada desde el envío sin demora. No sumes dos veces el retraso ni extiendas la ventana a varios minutos.

Especificación de ejemplo, en UTC: envío 12:00:20, demora de 60 s, elegibilidad 12:01:20, ventana [12:02:00,12:03:00), registro 12:03:00. Sin demora: [12:01:00,12:02:00). Si el envío es exactamente 12:00:00 y la demora es 60 s, la ventana es [12:01:00,12:02:00), sin añadir otro minuto artificial.

Persistí en metadatos auditables: propósito, envío, demora configurada/aplicada, elegibilidad, ventana, vencimiento, cancelación solicitada/efectiva y fill. Conservá nanosegundos y orden de eventos. Una etiqueta sin cambio real de elegibilidad no cuenta como implementación.

### Órdenes incluidas

En L01/L05, aplicá la demora a `open_spot`, `open_perp`, `increase_spot`, `increase_perp`, `reduce_perp`, `reduce_spot`, `correct`, `close_perp` y `close_spot`, con sus reintentos. Contrastá esta enumeración con todos los propósitos reales del código: una categoría adicional exige clasificación documentada, no inclusión/exclusión silenciosa.

En LC01/LC05/LC15, aplicala únicamente a `close_perp` y `close_spot`, incluidos cierres ordinarios, preventivos, por fallos, deuda o suspensión que se canalicen por esos propósitos. `reduce_perp`, `reduce_spot` y `correct` NO son cierres de ciclo para esta definición, aunque reduzcan exposición.

La demora corresponde a CADA orden, incluida la segunda pata cuando realmente se envía. No equivale a sumar una sola vez cinco minutos al ciclo completo ni a retrasar únicamente su P&L final. Reintentar crea una nueva orden con su demora y única ventana; no prolonga la anterior.

El catálogo BASE sirve para comparar episodios, no para decidir cuándo activar el escenario. Nuevos cierres, incidentes y ausencia de un episodio anterior se conservan como resultados válidos.

### Riesgo, reservas, cancelaciones y plazos

Desde el envío, la orden permanece pendiente conforme al contrato del motor. No liberes reservas anticipadamente ni permitas entradas duplicadas durante la espera. Conservá controles de fondos, inventario, deuda, margen y todos los eventos de precios/funding. No avances el reloj saltando minutos ni uses `sleep` real para representar demora histórica.

Mantené la cronología BASE: funding sobre la posición anterior al fill en el mismo instante; liquidación/riesgo y cancelaciones en sus fases originales. No uses eventos aún no disponibles para decisiones anteriores.

Sólo se traslada el vencimiento del intento de orden a su nueva ventana. NO traslades automáticamente `correction_deadline`, holding, cooldown, controles de riesgo o plazos de estrategia. Una corrección puede ser cancelada legítimamente antes de su ventana demorada por su plazo preventivo original. Registralo como efecto de la política de riesgo, no como una falla a ocultar ni como autorización para alargar ese plazo. Separá ese caso del bug de hacer vencer una orden contra su antigua ventana.

Las cancelaciones siguen la política BASE: antes de comenzar la ventana pueden anular el intento; dentro de una ventana comprometida se conserva el tratamiento diferido original. No apliques una nueva latencia de cancelación. La elegibilidad es un requisito temporal, no un fill ni una confirmación real del exchange. Probá también la frontera exacta y la escalada de cierre preventivo a liquidación, sin inventario duplicado ni órdenes huérfanas.

No reevalues el filtro de funding ni recalcules la cantidad solicitada al alcanzar la elegibilidad, salvo lo que ya exigían los controles originales. Hacerlo sería otra política.

### Liquidaciones forzosas y límite del modelo

El propósito `liquidate` queda EXCLUIDO de la demora adicional en L y LC. El cierre spot posterior, si se envía como `close_spot`, sigue siendo una orden del cliente y recibe el retraso correspondiente.

El bloque 3 documentó que la ruta original también representa `liquidate` mediante ventana/cupo de volumen, sin un motor independiente de liquidación del exchange. Preservá esa aproximación BASE, con demora adicional cero para ese propósito; no conviertas la liquidación en instantánea o sin límite de volumen para hacer más realista sólo una variante. La exclusión de latencia de cliente no certifica realismo de la liquidación BASE.

Si aparece una vía distinta de liquidación, identificá su comportamiento antes de integrar el cambio. No elimines liquidaciones, deuda o escenarios insolventes de los resultados.

Al final exclusivo de la muestra, una orden cuya ventana termina en o después del límite no obtiene un fill posterior dentro del backtest. Conservá inventario, órdenes y valoración según la semántica original, sin completar el cierre con datos futuros.

## 7. Pruebas y regresión antes del lote

Escribí primero fixtures con expectativas explícitas; después implementá la extensión mínima. Aprovechá los tests existentes. Deben cubrir:

1. Matriz de seis variantes exactas, dos estrategias, diffs económicos permitidos y rechazo de cruces o de parámetros de costos/capital/señal no autorizados.
2. Opciones apagadas conservan configuración canónica/digest y resultados de la ruta previa. Los modos `realized`, `base_e3` y `base_e3_total` conservan sus contratos.
3. Vela sintética con O=100, H=110, L=90, C=104, volumen base=10 y quote=1.020: OHLC4=101 y VWAP=102. El fill usa la referencia seleccionada, después slippage/tick una sola vez; la señal/valoración mantiene close=104. No convertirla en evidencia histórica.
4. OHLC inválido, volumen cero, dato ausente, suspensión documentada y disponibilidad de la vela sólo al cierre. Ningún método conoce high/low/close al enviar la orden futura.
5. Ejemplos temporales anteriores, nanosegundos en frontera, cero demora, demora de 60/300/900 s, ventana de duración exacta 60 s y vencimiento en su final.
6. Clasificación por propósito: todas las órdenes cliente en L; sólo close_perp/close_spot en LC; liquidate sin demora adicional; cierre spot posterior sí demorado. Segunda pata y reintento reciben su propia demora.
7. Cancelación antes de ventana, en el inicio exacto y dentro de ventana comprometida; orden pendiente y reservas durante la espera; ausencia de doble fill/compra/venta; cancelación de corrección por su plazo original.
8. Riesgo y funding durante la espera, liquidación que desplaza un cierre preventivo, prioridad de eventos simultáneos y no postergación del control de riesgo para permitir un fill.
9. Una única ventana por orden; parciales, cancelaciones, expiraciones y reintentos con volumen compartido bruto por cartera/activo/mercado/minuto. BTC/ETH y spot/futuros no comparten artificialmente unidades/cupos.
10. Fin de muestra, posiciones heredadas entre años, residuos valorados pero fuera del tiempo activo, checkpoints reanudados con toda la información temporal del escenario.
11. H1 y oportunidad de mercado H3 no cambian por un parámetro de ejecución; H2 y el contraste completo de H3 sí pueden cambiar por la nueva economía. No imponer invariancia cuando falte cobertura.
12. Verificador rechaza referencia de precio, demora, propósito, ventanas, cantidades, volumen, fees, secuencia o resultados adulterados aun cuando se renueven hashes en copias descartables.

Antes de interpretar variantes, compará la extensión apagada con el código previo congelado sobre ventanas técnicas deterministas que ejerciten envío, cancelación, corrección y cierre. Si no acredita suficientemente compatibilidad con BASE, ejecutá un replay BASE separado y compará fills, ledger, estados y cierres completos a máxima precisión. No reemplaces la referencia ni fuerces coincidencias redondeadas.

## 8. Etapas de ejecución

A. Autenticar referencias y datos, escribir protocolo previo, mapa de cambios y pruebas. Congelar la versión que ejecutará las variantes después de los controles de compatibilidad.

B. Ejecutar E_OHLC4 para ambas estrategias, conciliar y auditar referencia/ventanas.

C. Ejecutar L01/L05, conciliar y auditar la cronología efectiva y las decisiones preventivas durante la espera.

D. Ejecutar LC01/LC05/LC15, conciliar y comprobar población de órdenes afectadas sin seleccionar sólo episodios favorables.

E. Consolidar las seis variantes y BASE, verificar el paquete desde otra ruta y actualizar la matriz global.

Las corridas son continuas, con destinos, logs y estados separados. Comenzá sin concurrencia; aumentala sólo después de medir memoria/tiempo. No lances doce procesos por defecto. No reutilices un checkpoint BASE a mitad de muestra para iniciar otra política. Sólo reanudá la misma configuración, datos, código y estado completo.

Si una corrección posterior cambia la economía, preservá las salidas anteriores y repetí sólo las afectadas en destinos nuevos. Una cifra sin conciliación no habilita su interpretación. Separá ejecutado/reutilizado/bloqueado/fallido del estado económico; insolvencia no es fallo técnico y no autoriza omitirla.

## 9. Auditoría y métricas

Por variante/cartera, publicá total, 2022–2023, enero de 2024–agosto de 2026, años 2022–2025 y enero–agosto de 2026. Conservá saldos heredados; no sumes retornos anuales ni presentes 2026 como doce meses.

Incluí equity inicial/final, P&L y componentes, retorno, CAGR365, Sharpe RF=0, volatilidad y drawdown diario; tiempo activo sin polvo, capital utilizado y utilización diaria; ciclos, renovaciones, aperturas incompletas, parciales, fallos, cierres, deuda y liquidaciones.

Reutilizá la semántica corregida de exposición sobre cada trayectoria completa antes de recortar períodos. Integrá uniones BTC/ETH sin sumar doble tiempo. No copies valores de BASE a variantes.

Adaptá la auditoría del bloque 3 en herramientas nuevas o con opciones compatibles. Su regla previa `window=minute_window(submitted_at)` y la igualdad del precio al VWAP no bastan para las variantes nuevas. En este bloque se comprueban `minute_window(eligible_at)` y la referencia autorizada; no se elimina el control para lograr un pase.

Por orden y fill, conservar cantidades brutas/netas, envío, ventana, demoras, propósito, eventos de cancelación/expiración, reintento y fuentes. Auditar tiempos generación/envío/elegibilidad/fill por separado; órdenes sin fill no tienen latencia de ejecución cero. Los percentiles de fills sólo describen esa población y se acompañan de canceladas, expiradas, pendientes y no ejecutadas.

Auditar el cap en el minuto realmente utilizado, con OHLC/volúmenes autenticados y fondos reales; no usar el volumen de la ventana BASE si cambió. Respetar orden persistido para capacidad compartida, sin ordenar por una clave arbitraria que cambie quién consumió el cupo primero. Diferenciar falta de volumen, reglas, fondos/reservas no identificables, cancelación preventiva, plazo de corrección y fin de muestra.

Conservar el catálogo completo de episodios sin cobertura. Seleccionar previamente, para explicar, los cinco de mayor duración por cartera (desempate por primer inicio y activo) y estudiar además el 24/03/2023 cuando exista exposición en esa variante. No exigir que dure 121 minutos ni que siga ocurriendo con las mismas posiciones. Comparar L frente a LC de igual demora sin presentar su diferencia como efecto aditivo aislado.

Para esos casos seleccionados, reutilizar los helpers de valoración y margen sobre ventanas locales acotadas cuando los datos lo permitan: pérdida transitoria desde el inicio, exposición spot/corto y holgura mientras exista corto. No reconstruir toda la muestra intradía ni adjudicar un máximo global a una muestra de casos. Un mark ausente o un spot arrastrado conserva sus límites; un precio de valoración no acredita una venta durante la suspensión. Después de cerrar el corto no inventar un requerimiento de margen para ese contrato.

La tabla principal de drawdown de estas variantes es DIARIA. El análisis acotado de incidentes debe indicar su ventana/frecuencia/cobertura y no sustituirla. No recalcular SOFR, concentración completa o los millones de estados de riesgo ya sellados.

Conciliar cada cierre y período con componentes a tolerancia original `1E-8` USDT. Slippage/tick ya están en el precio, no se descuentan otra vez. Transferencias/garantías no son P&L. No ampliar tolerancias ni completar artificialmente días posteriores a un bloqueo o insolvencia.

## 10. Hipótesis e interpretación

H1 conserva método, historia, horizonte y disponibilidad. Comprobá igualdad de proyecciones relevantes/targets y reutilizá una sola evaluación BASE autenticada cuando corresponda; no sumes cohortes idénticas como más evidencia.

La oportunidad de mercado H3 conserva forecast, basis, umbral de 34 pb y operatividad. No usa tiempo de llegada de órdenes, caja, capacidad o posiciones. Comprobá su invariancia separadamente de los nuevos CAGR. Una condición de ejecución no puede eliminar retrospectivamente una oportunidad del mercado. Si se interrumpe una corrida, distinguir observaciones realmente persistidas de una serie de mercado reutilizada independientemente.

H2 usa la condicional y permanente del MISMO escenario/período: CAGR condicional definido, finito y positivo, junto con Sharpe definido y superior al permanente. Conservar ND, cobertura y motivos. No exigir mayor retorno ni adoptar RF=SOFR. No imponer la conclusión BASE o de otros bloques.

H3 conserva los dos cortes originales: ambos indicadores disminuyen, favorable; ambos aumentan, contraria; restantes casos evaluables, mixta; faltantes indispensables, no concluyente. La oportunidad puede ser invariante entre escenarios y el veredicto cambiar por los CAGR. El desglose anual complementa el contraste, no cambia las fechas retrospectivamente.

Presentá todos los escenarios, incluidos resultados nulos, favorables al filtro o no monotónicos. Una demora mayor puede modificar toda la trayectoria y no tiene por qué empeorar siempre el P&L observado. No la selecciones como política ganadora ni atribuyas probabilidades a seis sensibilidades exploratorias.

## 11. Productos, preservación y portabilidad

Destinos nuevos propuestos: `entregas/entrega_4/ejecucion_demoras/<identificador_real>/` y configuraciones bajo `configs/entrega_4/ejecucion_demoras/`. Scripts y pruebas siguen la estructura vigente. No dupliques Backtesting ni los paquetes anteriores.

Entregá protocolo previo, decisiones metodológicas (incluido alcance de LC), matriz exacta de escenarios, run_id/estados/comandos, código ejecutado/congelado, configuraciones efectivas, reporte Markdown/HTML y síntesis integrable.

Incluir CSV/Parquet comparativos, curvas, evidencia diaria/P&L, H2/H3, invariancias H1/oportunidad, auditoría de precios/cronología/capacidad, catálogo y detalle de incidentes, fuentes de figuras y matriz de cumplimiento del bloque. Un identificador reutilizado no debe presentarse como una corrida nueva.

Conservar fuentes masivas en lectura local. Exportar las velas y registros necesarios para los controles compactos declarados; usar rutas explícitas para controles con datos completos. Un hash de una fuente ausente no prueba que fue recalculada. Declarar lógica compartida entre constructor y verificador.

El verificador debe funcionar offline desde una copia limpia en otra ruta usando sus herramientas incluidas, sin depender del HEAD/índice de una sesión pasada. No permitir escrituras en entradas ni dentro de sellos; logs de auditoría en destinos nuevos externos. Ejecutar las pruebas históricas pertinentes sobre el paquete final, sin contar omisiones como aprobaciones ni sumar suites solapadas.

Ejecutar Ruff, regresión, verificación numérica, invariancia de fuentes y exportación binaria con índice temporal aislado. Proteger EOL sólo para la nueva evidencia cuando corresponda. Comprobar UTF-8 y enlaces. Diferenciar la incompatibilidad histórica de inventario/config de los cambios nuevos autorizados, que requieren identidad y pruebas propias.

Actualizar `docs/entrega_4/matriz_avance.csv` y su historial sin sobrescribir matrices selladas: bloque 4 según estado real; bloques 5 y 6 todavía pendientes. Anotar que los shocks y el escenario sin interrupción NO se ejecutaron aquí, y que el alcance de LC especifica una regla global de cierre distinta de la antigua propuesta por episodios. Mantener enlaces a versiones vigentes y dejar pendiente la revisión transversal/redacción.

## 12. Fuera de alcance y cierre

No ejecutar movimientos sintéticos de precios, contrafactual sin suspensión, nuevas búsquedas históricas, otros horizontes/costos/AUM, fechas iniciales alternativas, inferencia estadística, selección de parámetros, remuneración de caja/garantías ni nuevos cálculos SOFR. No descargar trades/aggTrades, ampliar muestra/activos, usar credenciales o servicios pagos.

No hacer commit, push, cambios en el índice del usuario, reset destructivo, renormalización global ni modificaciones a paquetes sellados. No declarar terminada toda la Entrega 4. Si falta un dato, explicitarlo y continuar sólo las tareas independientes válidas.

Respuesta final: qué variantes terminaron, qué extensiones y regresiones se realizaron, cómo se verificaron las demoras realmente aplicadas, qué cambió en precio/actividad/riesgo/capital/H2/H3, qué sigue bloqueado y dónde están reporte y evidencias. Separar archivos preparados localmente de su publicación en GitHub.

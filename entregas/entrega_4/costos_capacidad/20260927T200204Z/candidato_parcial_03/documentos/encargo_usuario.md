# Encargo para Codex: bloque 3, costos y capacidad

Trabajá en el proyecto Backtesting del repositorio `pgs00/crypto-carry-thesis-pablo-salerno`.

## 1. Objetivo y alcance cerrado

Ejecutá tres familias de sensibilidad para la Entrega 4: costos de transacción/deslizamiento, participación máxima en volumen y capital inicial. La pregunta es cuánto dependen los resultados y la viabilidad operativa de esos supuestos. No busques parámetros que hagan ganar a una estrategia.

Este encargo autoriza las ocho variantes de la sección 3, para condicional y permanente, y una extensión mínima para mantener fijo el costo utilizado por el filtro de funding mientras se estresan los costos de las operaciones. No se autoriza otra lógica de negociación ni combinar dimensiones.

Trabajá por etapas: autenticar referencia, fijar protocolo, probar la extensión, ejecutar cada familia, conciliar y generar el reporte. No te limites a presentar un plan. Consultá únicamente decisiones que excedan este alcance. Un bloqueo específico no impide terminar las tareas independientes.

El feedback de E3 ya llegó. Se completaron los bloques de riesgo intradía/garantías, retorno/capital con SOFR y señal/entradas. No los rehagas. El usuario redactará la entrega en Word después de completar los análisis y revisarlos transversalmente: ahora producí evidencia técnica y una síntesis integrable, no Word ni PDF final.

## 2. Referencia, fuentes y preservación

Identificá instrucciones del proyecto, raíz, rama, HEAD, entorno y cambios existentes, incluidos los del índice. La última referencia revisada fue `af9fc227915a340665fce2f917d810dec6507d12`. No vuelvas automáticamente a ella ni descartes avances posteriores.

Leé y verificá las entradas relevantes:

- `docs/methodology.md` y las configuraciones efectivas de BASE_E3.
- Padre: `entregas/entrega_4/reglas_historicas/20260925T005436Z/`.
- Corrección de exposición/H2: `entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/`.
- Riesgo intradía: `entregas/entrega_4/riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z/`, especialmente feedback y límites.
- Retorno/capital: `entregas/entrega_4/retorno_capital/20260927T143928Z/paquete_20260927T152732Z/`.
- SOFR: `entregas/entrega_4/retorno_capital/20260927T154653Z_sofr/paquete_20260927T162350Z/`, sólo como contexto ya terminado.
- Bloque 2: `entregas/entrega_4/senal_entradas/20260927T170230Z/paquete_20260927T185305Z/`, sus controles y runner congelado.
- `Paquete de evidencia`, manifiestos de datos y corridas, y consigna académica si está disponible. No afirmes haber leído un documento ausente.

Inspeccioná `src/crypto_carry/config.py`, `costs.py`, `portfolio.py`, `diagnostics.py`, `strategy.py`, `execution.py`, `ledger.py`, las reglas prescritas y la carga de datos. Reutilizá los scripts del bloque 2 y los métodos corregidos de exposición/H2 mediante interfaces compatibles, sin modificar sus copias selladas ni ejecutar matrices predeterminadas de otro alcance.

Comparadores:

- BASE condicional: `run_ad71d751b20623006c195ff3`.
- BASE permanente: `run_dfea4b7ac1475668d5968c97`.

Muestra continua `[2022-01-01T00:00:00Z, 2026-09-01T00:00:00Z)`, BTCUSDT/ETHUSDT spot y perpetuos USD-M. Capital inicial BASE: 10.000 USDT por cartera. No reiniciar cuentas, posiciones, ciclos o pronósticos al cambiar de año.

Derivá cada configuración desde la efectiva de BASE, no desde `Config()` con sus defaults. En particular, no adoptes H336, V048 ni otra variante del bloque 2 por su resultado. Los comparadores de este bloque siguen siendo las BASE originales.

Guardá huellas iniciales. Conservá intactos E3, datos originales, configuraciones BASE, corridas, documentos y paquetes sellados de todos los bloques. Los cambios activos autorizados deben tener diff y código nuevo identificable. Nunca actualices un manifiesto histórico para que acepte archivos cambiados.

## 3. Ocho variantes, sin cruces

Los valores siguientes retoman el plan experimental acordado; no son parámetros impuestos por la cátedra ni estimaciones de impacto de mercado.

| ID | Cambio económico | Campos de escenario respecto de BASE | Capital inicial | Participación máxima |
| --- | --- | --- | --- | --- |
| C02 | Duplicar comisiones ordinarias y deslizamiento | `cost_multiplier=2`; activar costo de señal fijo según sección 4 | 10.000 | 1% |
| C03 | Triplicar comisiones ordinarias y deslizamiento | `cost_multiplier=3`; activar costo de señal fijo según sección 4 | 10.000 | 1% |
| S02 | Deslizamiento de 2 pb por operación ejecutada | `slippage=Decimal("0.0002")`, multiplicador BASE; activar costo de señal fijo | 10.000 | 1% |
| S05 | Deslizamiento de 5 pb por operación ejecutada | `slippage=Decimal("0.0005")`, multiplicador BASE; activar costo de señal fijo | 10.000 | 1% |
| P050 | Menor capacidad por instrumento/minuto | `max_volume_participation=Decimal("0.005")` | 10.000 | 0,50% |
| P025 | Menor capacidad por instrumento/minuto | `max_volume_participation=Decimal("0.0025")` | 10.000 | 0,25% |
| A050 | Mayor capital inicial | `capital=Decimal("50000")` | 50.000 | 1% |
| A100 | Mayor capital inicial | `capital=Decimal("100000")` | 100.000 | 1% |

Son dieciséis pares variante/cartera, más dos referencias reutilizables: dieciocho resultados previstos. Corridas técnicas de regresión se registran aparte, no se cuentan como nuevas sensibilidades. Reutilizar una variante exige verificar identidad exacta de configuración, datos, código y período, no que su saldo final se parezca.

Se mantienen horizonte/tenencia 168 h, vida media 24 h, ventana 336 h, precarga 360 h, disponibilidad de funding 60 s, basis de entrada inclusivo `[0,0.005]`, objetivo spot 30% del patrimonio por activo, apalancamiento aislado 2x, rebalanceo y controles de riesgo BASE. Se conservan `next_minute_vwap`, `joint_quantity`, secuencia de patas, ventana única de un minuto por orden, límites de tiempo, parciales y reintentos originales.

Comisiones ordinarias BASE: spot 0,10%, futuros 0,05%, sin promoción. Deslizamiento BASE: 1 pb. Mantenimiento BASE, sin duplicarlo. No cambiar tarifa/regla de cargos de liquidación, marks documentados ni precios de funding. No remunerar caja o garantías.

El runner debe rechazar campos económicos fuera de la lista permitida por escenario. Registrá aparte cambios de rutas/identidad y el modo explícito de costo de señal. No ejecutes C03 junto con A100 o P025, ni S05 junto con C02.

## 4. Punto crítico: separar el filtro de funding de los costos de ejecución

### Contrato económico

Todas las variantes conservan `forecast > Decimal("0.0034")` como condición de funding para entrar en la condicional y `forecast > 0` para renovar. La permanente omite ambos requisitos de funding, pero conserva los demás filtros.

Sólo se congela esa condición de funding/costo. NO se congelan las decisiones efectivas, el presupuesto, el sizing, las cantidades netas, las órdenes ni la economía. Los costos del escenario intervienen normalmente en los precios estimados para dimensionar, las comisiones, la disponibilidad de fondos, el inventario, la garantía y la ejecución.

Es un estrés con regla de selección sin recalibrar, no una estrategia que adapta su umbral a tarifas nuevas. Tampoco supone ignorar costos en los controles de solvencia. Explicá esta distinción en el protocolo.

### Acoplamiento observado y adaptación autorizada

En el código revisado, `cycle_cost()` multiplica por `config.cost_multiplier` e incluye `config.slippage`. El modo existente `research_decision_fee_mode="base_e3"` fija las tarifas nominales, pero NO fija el costo completo: el multiplicador y el deslizamiento siguen entrando en el cálculo. Por tanto, usarlo sin otra adaptación no garantiza 34 pb en C02/C03/S02/S05.

Comprobá el estado actual del código. Si no existe ya una solución equivalente y comprobada, queda autorizada esta extensión mínima:

1. Agregar un nuevo valor explícito, por ejemplo `"base_e3_total"`, a `research_decision_fee_mode`, válido sólo para investigación prescrita. No reutilizar ni redefinir los valores existentes `"realized"` o `"base_e3"`.
2. En ese modo, resolver el costo completo de selección en `cycle_cost()` como `Decimal("0.0034")`, independiente del multiplicador y del deslizamiento realizados.
3. Activarlo únicamente en las cuatro variantes de costos/deslizamiento de esta matriz. P050/P025/A050/A100 conservan el modo BASE.
4. Mantener la serialización, defaults y digest de configuraciones anteriores cuando no se active el nuevo modo. La configuración efectiva de cada corrida debe registrar claramente la activación.
5. Comprobar todos los consumidores: entrada, diagnósticos, oportunidades H3 y tablas del reporte. El mismo concepto no puede valer 34 pb en la estrategia y 68 pb en su diagnóstico.

Si una extensión equivalente ya existe, reutilizala después de probar su semántica y ajustá el mapa técnico del protocolo. No crees un segundo mecanismo. La autorización cubre esa separación y metadatos/pruebas indispensables, no un rediseño general del motor.

En los diagnósticos del modo nuevo, distinguí el costo usado para selección, sus componentes BASE y las tarifas/deslizamiento del escenario. No conserves componentes que suman 68 pb bajo un encabezado que afirme explicar un umbral de 34 pb. No cambies la forma de los registros originales archivados.

Valores que las pruebas deben comprobar, antes de redondeo adverso por tick:

| Escenario | Fee spot aplicado | Fee futuros aplicado | Deslizamiento aplicado | Umbral funding de entrada |
| --- | --- | --- | --- | --- |
| BASE | 0,10% | 0,05% | 1 pb | 34 pb |
| C02 | 0,20% | 0,10% | 2 pb | 34 pb |
| C03 | 0,30% | 0,15% | 3 pb | 34 pb |
| S02 | 0,10% | 0,05% | 2 pb | 34 pb |
| S05 | 0,10% | 0,05% | 5 pb | 34 pb |

C02/C03 escalan conjuntamente dos componentes de fricción; S02/S05 aíslan deslizamiento. No etiquetes C02/C03 como estrés exclusivo de comisiones. No añadas otra familia para separar comisiones sin aprobación.

Las compras spot siguen pagando comisión en activo base; las ventas spot y futuros, según el contrato original. Aplicá el multiplicador una sola vez. El deslizamiento y el redondeo ya están en el precio: se muestran como diagnóstico, no se descuentan nuevamente del P&L.

La regla/tasa del cargo específico de liquidación no se multiplica. Su importe puede cambiar si cambia la base imponible o la trayectoria. Si las reglas originales incluyen además comisión ordinaria en una liquidación, separala del cargo específico y conservá el tratamiento documentado.

## 5. Capacidad y tamaño: contratos y medición

P050/P025 reducen el presupuesto de volumen dentro de la ventana elegible original. No cambian el volumen observado, la duración de la ventana, los tiempos de envío/fill, los reintentos ni permiten repartir una misma orden en ventanas adicionales.

Usá la capacidad agregada por `(cartera, activo, mercado, minuto)`. Las órdenes que comparten esa clave consumen el mismo presupuesto. No netees compras y ventas para ocultar participación bruta. Las carteras de escenarios distintos son simulaciones alternativas, no competidores que deban compartir capacidad entre sí.

La función revisada `minute_capacity()` descuenta volumen ya utilizado y redondea hacia abajo al step. Verificá su aplicación efectiva en el runner. Un minuto sin volumen no permite una ejecución ficticia. El mark es para riesgo, no sustituye al precio ejecutable.

Para A050/A100, recalculá toda la trayectoria con los mismos objetivos porcentuales. No multipliques las cantidades o ganancias de BASE por cinco o diez. Se mantienen los tramos de margen y restricciones prescritos: verificá cruces de tramo, tamaños mínimos/máximos, importes y redondeos. Un rechazo por límite de regla no equivale a falta de volumen. No amplíes tramos ni límites para hacer funcionar una cartera mayor; una regla no evaluable se informa como tal.

Construí una auditoría de ejecución desde órdenes, fills, estados y volúmenes autenticados. Por instrumento y período, y con agregados de cartera bien definidos, mostrar:

- Órdenes solicitadas, completas/parciales, sin fill, canceladas, vencidas y reintentos; distinguir estado terminal de eventos intermedios para evitar doble conteo.
- Cantidad solicitada y ejecutada por orden, fracción ejecutada y causa acreditada del faltante. No mezclar cantidad spot bruta ejecutada con cantidad neta recibida después de comisiones.
- Participación realizada: suma de cantidades ejecutadas sujetas al límite dividida por volumen base de la ventana, una vez por clave; utilización del cupo: cantidad ejecutada dividida por `participación_máxima × volumen`.
- Máximo y distribución de esas fracciones sobre una población identificada. Separar volumen cero/dato ausente, presupuesto agotado, step, límites de regla y fondos insuficientes.
- Tiempo activo sin cobertura, descalce, intentos fallidos, aperturas y cierres demorados, a partir de los registros de cada nueva cartera.

No sumes cantidades de BTC y ETH como si fueran la misma unidad. Un agregado de fracciones debe declarar ponderación y denominador. No confundas el volumen anterior al envío con el volumen posterior de la ventana elegible; este último no se conoce al decidir. No lo uses retrospectivamente para mejorar el sizing.

Respetá el tratamiento original de órdenes forzosas del exchange y documentá si están fuera del contrato de participación. No amplíes esas excepciones a órdenes voluntarias ni apliques una nueva regla de liquidación para hacer pasar una auditoría.

Seleccioná para explicación los cinco casos con mayor utilización de cupo y los cinco de mayor exposición activa sin cobertura por cartera, usando criterios y desempates fijados antes. Conservá el catálogo completo; un registro presente en ambos grupos se identifica, no se suma dos veces.

Estas pruebas son sensibilidades de capacidad y fricciones con velas de un minuto. No estiman empíricamente cola de órdenes, spread ni impacto de mercado. Si todos los tamaños funcionan, la conclusión se limita a esos tamaños y supuestos; no demuestra escalabilidad ilimitada.

## 6. Etapas y puertas de control

### A. Entradas, protocolo y prueba de compatibilidad

Autenticá fuentes, configuraciones y versiones vigentes. Fijá protocolo y matriz de ocho escenarios antes de sus resultados. Medí tiempo/memoria en una ventana corta y mantené la lectura local de un minuto con los argumentos de la ruta BASE, incluida precarga y tratamiento de marks.

Escribí primero pruebas que reproduzcan el acoplamiento costo/umbral y después la extensión autorizada. Contrastá comportamiento anterior/nuevo con la extensión apagada, en BASE y en los modos de comisiones ya existentes. Con BASE, activar el modo de costo total fijo debe conservar la economía; cualquier nuevo metadato se distingue de la proyección económica comparada.

Antes del lote histórico, ejecutá controles técnicos deterministas contra código congelado anterior. Si la compatibilidad con BASE no queda suficientemente demostrada, realizá un replay BASE de control separado y contrastá fills, ledger, estados y todos los cierres, no sólo el saldo final. No reemplaces las referencias originales.

Congelá la identidad del código ejecutor antes de las variantes. Si una corrección posterior afecta su economía, identificá las corridas afectadas y repetilas en destinos nuevos; no mezcles resultados de versiones incompatibles bajo un mismo sello.

### B. Costos y deslizamiento

Ejecutá C02/C03 y S02/S05, ambas estrategias, sin cruces. Conciliá cada corrida y verificá que el umbral siga fijo antes de interpretar su rentabilidad. Una discrepancia contable bloquea la interpretación de la corrida afectada.

### C. Participación

Ejecutá P050/P025, ambas estrategias, conservando costos BASE. Verificá la auditoría de volumen compartido y separá capacidad de restricciones de fondos/reglas.

### D. Capital inicial

Ejecutá A050/A100, ambas estrategias, conservando participación 1% y costos BASE. Revisá tamaños, tramos, redondeos y solvencia sin imponer escala lineal.

### E. Consolidación

Publicá localmente resultados, protocolo y controles de los dieciocho pares previstos. Usá `ejecutado`, `reutilizado_verificado`, `bloqueado` o `fallido`, separado del estado económico. Insolvencia o ausencia de operaciones no equivalen a fallo técnico ni permiten descartar el escenario.

Empezá sin concurrencia; aumentala sólo después de medir recursos. No lances dieciséis backtests simultáneos. Corridas reanudables, logs y destinos separados. Un checkpoint sólo sirve para la misma configuración, datos y código; no retomes una variante desde una trayectoria BASE intermedia.

## 7. Métricas, hipótesis y lectura anual

Mostrá los ocho períodos habituales: muestra completa, 2022–2023, enero de 2024–agosto de 2026 y cada año 2022–2025 más enero–agosto de 2026. Conservá saldos heredados y denominadores reales. No trates 2026 como doce meses ni sumes porcentajes anuales.

Por escenario/cartera/período incluí patrimonio inicial/final, P&L y componentes, retorno, CAGR365, Sharpe RF=0, volatilidad y drawdown diario; utilización media/máxima diaria, capital utilizado, tiempo activo sin polvo, ciclos, renovaciones, parciales, fallas, exposición descubierta y eventos de margen/deuda/liquidación.

Para A050/A100 presentá tanto valores absolutos como retorno y curva normalizada por su propio capital inicial. Una diferencia absoluta frente a BASE no mide por sí sola eficiencia o deterioro. No dividas CAGR por utilización media ni presentes garantías como nocional o caja libre.

El polvo conserva unidades, valoración y riesgo, aunque se excluya de actividad según el clasificador corregido. Clasificá la trayectoria completa antes de recortar años; integrá uniones de BTC/ETH, sin sumar exposición simultánea dos veces.

H1: en este bloque no cambian fórmula, ventana, horizonte, vida media ni datos de funding. Comprobá igualdad de las proyecciones relevantes y reutilizá la evaluación BASE cuando corresponda, registrando su identidad. No dupliques observaciones para aparentar más evidencia. Una corrida interrumpida no autoriza copiar una cobertura observada que no tuvo.

H2: usá el contrato corregido, CAGR condicional definido, finito y positivo junto con Sharpe superior al de la permanente del mismo escenario, capital, período y ventana. Conservá ND y motivos. No impongas la conclusión del bloque 2 ni exijas CAGR superior al permanente. SOFR no sustituye al comparador ni a RF=0.

H3: el componente de oportunidad de mercado debería permanecer igual porque no cambian forecast, basis, operatividad ni el umbral de 34 pb. Verificá por separado esos inputs y sus agregados. Participación, tamaño y fondos de cartera no deben entrar retrospectivamente en la definición del indicador. Si el generador usa costos realizados en H3, corregí exclusivamente esa conexión para el modo nuevo y probala, sin alterar el indicador histórico.

La invariancia de oportunidad NO implica invariancia de todo H3: el CAGR condicional de los dos cortes puede cambiar. Recalculá el contraste con la oportunidad autenticada y los nuevos CAGR. Ambos bajan: favorable; ambos suben: contraria; demás casos evaluables: mixta; faltantes indispensables: no concluyente. Conservá los cortes originales y unidad pb/168 h.

Los drawdowns de las variantes son diarios. No reutilices como intradía de una variante el resultado BASE de otro paquete ni generes nuevas series de millones de observaciones en este bloque. Extremos de garantías calculados en cierres se rotulan como diarios; eventos de riesgo persistidos son otra fuente con su frecuencia indicada.

Explicá conjuntamente costos, actividad, capital y resultado. Mayores fricciones pueden alterar órdenes y la trayectoria; no exijas monotonicidad de P&L como prueba de corrección. No elimines resultados invariantes, negativos o favorables al filtro. No calcules probabilidades, significancia ni un umbral óptimo de rentabilidad con sólo estos escenarios.

## 8. Pruebas y conciliaciones mínimas

Antes de interpretar resultados históricos, probar con fixtures explícitos:

1. Ocho variantes exactas, dos estrategias por variante, sin campos ni combinaciones no autorizados; configuración BASE y modos anteriores preservados.
2. Nuevo modo de decisión devuelve 34 pb para C02/C03/S02/S05; los modos antiguos conservan sus resultados anteriores, aunque no fijen ese total.
3. Umbral estricto: forecast=34 pb no habilita entrada condicional; superior sí supera ese filtro. Renovación con forecast positivo menor que 34 pb supera funding; cero no. La permanente omite esos filtros, no los demás.
4. Misma referencia 100 y sin tick adicional: C02 produce compra 100,02 y venta 99,98; C03, 100,03/99,97; S05, 100,05/99,95. Probar además tick adverso y ausencia de doble multiplicación.
5. Compra spot de cantidad bruta 1, precio ejecutado 1.000 y fee 0,20%: recibe 0,998, comisión 0,002 de base valorada en 2 USDT y salida de caja 1.000. Sizing y ledger deben coincidir en unidades y presupuesto.
6. Con igual base imponible, la tarifa específica de liquidación sigue igual al activar C02/C03; distinguir comisión ordinaria, slippage y cargo especial conforme a la regla original.
7. Con volumen 100, participación 0,5%, step 0,1 y capacidad previamente usada 0,3, una solicitud restante 0,4 sólo puede ejecutar 0,2. Otra orden no recibe otra vez el cupo completo. Volumen cero no ejecuta.
8. Separación de mercados/activos/carteras, capacidad bruta compartida, órdenes parciales y reintentos sin duplicar cantidades ni extender una ventana. Tratar ausencia de precio/volumen como no evaluable, no volumen inventado.
9. Capital 50.000/100.000 modifica objetivos porcentuales desde el estado real. Fixtures sin restricciones pueden ser proporcionales; fixtures con cupo, step o tramos deben permitir divergencia, no imponerla ni suprimirla.
10. Fuentes idénticas y costo de selección fijo conservan H1 y oportunidad de mercado H3; H2 y la lectura completa de H3 sí pueden variar con los nuevos retornos. AUM no cambia el horizonte ni contamina H3 con fondos.
11. Parciales, comisiones en base, funding antes de fills simultáneos, garantías/transferencias sin P&L, ciclos entre años, polvo y fin sin cierre ficticio; ND ante patrimonio o métricas no evaluables.
12. Conciliación de cierres y períodos con componentes a tolerancia original `1E-8` USDT, conciliación órdenes/fills/ledger y cap de volumen donde aplique. No ampliar tolerancias para obtener un pase.
13. Verificador detecta cambios de configuración, tarifas, costo de selección, participación, cantidades, denominadores, períodos e hipótesis aun después de renovar hashes en copias descartables. Verificación de sólo lectura y portabilidad real.

Diferenciá fixtures de evidencia histórica. Registrá comandos, fallos, correcciones y pases reales. Pruebas omitidas no cuentan como aprobadas; no sumes conteos solapados de suites. El aumento de costos puede causar insolvencia válida: conservarla con sus saldos, deuda, cobertura y tratamiento de métricas, sin fabricar días posteriores.

## 9. Productos y verificación

Creá destinos nuevos bajo `entregas/entrega_4/costos_capacidad/<identificador_real>/`; configuraciones bajo `configs/entrega_4/costos_capacidad/`, con scripts y tests en la estructura existente. Son destinos propuestos. No dupliques la raíz Backtesting ni paquetes anteriores completos.

Entregá:

- Protocolo previo y matriz de ocho escenarios, diffs exactos, estado, run_id, código ejecutado, datos, comandos y reanudaciones.
- Reporte Markdown/HTML: síntesis, costos/deslizamiento, participación, tamaño, años/capital, H1/H2/H3 y límites. Sin Word/PDF final.
- Tablas comparativas y deltas, curvas de equity absoluta/normalizada, evidencia diaria/componentes y conciliaciones.
- Auditoría de ejecución con claves de instrumentos/minutos, fuentes de volumen, órdenes/fills, participación/cupo, restricciones, casos extremos y descalce; evidencia suficiente para revisar los límites declarados.
- Exposición corregida, resultados de H2, trazabilidad de la oportunidad reutilizada y contraste H3 con los nuevos CAGR.
- Configuraciones, código nuevo/congelado, referencias autentificadas, manifiesto nuevo y verificador con alcance declarado.
- Síntesis breve: qué se probó, qué cambió, qué permaneció estable, límites y qué conclusiones admite. No seleccionar un ganador.

Mantené precios masivos y salidas voluminosas locales, compartidos en lectura entre escenarios. Incluí en el paquete compacto las ventanas de volumen o evidencia suficiente para los controles que declare recalcular. Si sólo autentica un resumen de capacidad y el contraste de todos los fills requiere datos locales, indicá exactamente esa diferencia y los argumentos necesarios. Un hash de una serie ausente no acredita que se la recalculó.

Probá el verificador offline desde una copia en otra ruta, usando exclusivamente las herramientas incluidas y dependencias explícitas. No exijas HEAD o índice de una sesión pasada. Salidas de auditoría nuevas y externas al sello. Declarar lógica compartida es obligatorio cuando constructor y verificador la comparten.

Antes del cierre, ejecutá pruebas finales pertinentes, regresión de la extensión, Ruff, preservación de entradas, conciliaciones y portabilidad. Verificá bytes de exportación con índice temporal aislado o mecanismo equivalente, sin tocar el índice del usuario. Aplicá protección de EOL acotada sólo a nueva evidencia cuando haga falta.

La incompatibilidad preexistente del inventario histórico con `config.py` debe seguir documentada como tal. Las modificaciones de este bloque, en cambio, requieren su diff, pruebas e identidad nuevos. No las ocultes detrás de esa excepción ni actualices hashes antiguos para fingir preservación. La revisión vigente del motor y los verificadores históricos tienen alcances diferentes.

No reescribas el README externo del bloque 2 ni otros archivos ajenos para corregir presentación durante esta tarea. Evitá propagar texto con acentos dañados en los documentos nuevos; verificá UTF-8 al escribir y releer.

## 10. Matriz global de avance y pendientes

Actualizá o creá una única matriz de avance no sellada bajo `docs/entrega_4/`, preservando su historial de cambios. Vinculá requisito/pregunta, origen (consigna, feedback, compromiso o decisión experimental), bloque, estado, paquete vigente, evidencia y limitación. Los estados previos se confirman leyendo sus productos, no sólo sus nombres.

El esquema de trabajo acordado es:

- Bloque 1: retorno/capital, concentración, rechazos y SOFR aprobada.
- Bloque 2: horizonte, vida media y techo del basis.
- Bloque 3: este encargo, costos y capacidad.
- Bloque 4 pendiente: convención de ejecución y demoras, coordinando latencia general y demora exclusiva de cierres sin duplicar escenarios.
- Bloque 5 pendiente: movimientos adversos y trayectoria hipotética sin interrupción, con sus supuestos por aprobar antes de ejecutar.
- Bloque 6 pendiente: fechas iniciales alternativas, incertidumbre estadística y evaluación conjunta.
- Después: revisión transversal de versiones/definiciones y redacción final en Word. No es otra sensibilidad.

El bloque previo de riesgo intradía/garantías también debe quedar enlazado como antecedente terminado con sus límites. No lo presentes como tarea pendiente ni como reconstruido para estas dieciséis variantes. Remunerar/reinvertir caja libre sigue fuera del alcance acordado, distinto del benchmark SOFR sobre todo el capital, y no debe ejecutarse por inferencia.

## 11. Restricciones y cierre requerido

No ejecutar otros escenarios de señal, horizonte, latencia, convención de precio, fechas iniciales, shocks o contrafactual sin interrupción; nuevos cálculos SOFR; remuneración de caja/garantías; búsquedas históricas generales; inferencia estadística; optimización o selección de parámetros.

No descargar trades/aggTrades, ampliar activos/fechas, usar credenciales o servicios pagos, hacer commit, push, cambios en el índice del usuario, resets destructivos, renormalización global ni escrituras en servicios externos. No sobrescribir resultados incompletos de una corrida sin conservar su estado y procedencia.

La respuesta final debe indicar qué escenarios terminaron y cuáles no, qué se reutilizó, cómo quedó garantizado el umbral de 34 pb, qué pasó con costos/ejecución/capital, qué lecturas H2/H3 cambiaron, qué controles pasaron realmente y dónde está cada evidencia. Diferenciá resultados económicos nuevos de diagnósticos reutilizados. No declares completa toda la Entrega 4 ni confundas archivos locales con un push a GitHub.

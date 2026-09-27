# Encargo para Codex: bloque 2, señal y selección de entradas

Trabajá en el proyecto Backtesting del repositorio `pgs00/crypto-carry-thesis-pablo-salerno`.

## 1. Objetivo y alcance autorizado

Ejecutá un análisis de sensibilidad de tres dimensiones: horizonte de pronóstico y tenencia, vida media de EWMA y techo del basis de entrada. Implementá únicamente las adaptaciones necesarias, ejecutá las variantes, conciliá sus resultados y entregá un reporte verificable. No te limites a otro plan.

La pregunta es cuánto dependen las conclusiones de la configuración elegida, no cómo encontrar parámetros que hagan ganar a la condicional. Las seis variantes indicadas aquí están autorizadas. No agregues combinaciones, optimizaciones ni escenarios de otros bloques.

El feedback de la Entrega 3 ya fue recibido. Se desarrollaron riesgo intradía/garantías y el bloque de retorno/capital, incluida la cuenta SOFR hipotética aprobada. Este encargo no los rehace. Conservá la desagregación anual y leé el retorno junto con la utilización del capital. El reporte sigue siendo técnico preliminar de Entrega 4, pero no debe decir que esperamos el feedback de E3.

Este bloque autoriza nuevas simulaciones de las variantes: no puede resolverse ajustando aritméticamente las ganancias de las carteras anteriores. La referencia presentada y todos sus paquetes siguen intactos.

## 2. Punto de partida, lectura y preservación

Leé las instrucciones del proyecto. Identificá raíz, rama, HEAD, entorno, datos locales y cambios ajenos, incluidos los preparados en el índice. La última versión revisada fue `70b03969afed2637ae6819acc5c0c439dbdac1f0`. No vuelvas automáticamente a ese commit ni descartes avances posteriores.

Leé las fuentes pertinentes y comprobá sus manifiestos:

- `docs/methodology.md` y las configuraciones efectivas de las carteras BASE_E3.
- `entregas/entrega_4/reglas_historicas/20260925T005436Z/`, padre de las doce carteras de la primera tanda.
- `entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/`, referencia vigente para exposición y H2.
- `entregas/entrega_4/riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z/`, en particular feedback, metodología y límites de las métricas intradía.
- `entregas/entrega_4/retorno_capital/20260927T143928Z/paquete_20260927T152732Z/`, diagnóstico de ciclos, entradas y capital.
- `entregas/entrega_4/retorno_capital/20260927T154653Z_sofr/paquete_20260927T162350Z/`, sólo como contexto ya terminado. No recalcules SOFR.
- `Paquete de evidencia` y el material académico disponible. No afirmes haber leído un PDF o una consigna ausentes.

Inspeccioná `src/crypto_carry/config.py`, `forecast.py`, `evaluation.py`, `strategy.py`, `risk.py`, `robustness.py`, la carga de datos y los scripts de ejecución de la tanda anterior. Reutilizá el posprocesamiento corregido de `scripts/rules_sensitivity_exposure.py` y `scripts/rules_sensitivity_h2.py` cuando corresponda.

En el código revisado ya existen `horizon_hours`, `holding_hours`, `half_life_hours`, `window_hours` y `basis_max`. No inventes otro motor de pronóstico. `robustness.py` contiene una matriz más amplia que este encargo y variantes de otro alcance: no ejecutes su matriz predeterminada. Podés aprovechar componentes compatibles mediante una selección explícita o un runner acotado.

Antes de calcular, guardá hashes de las entradas y de los archivos que deben permanecer intactos. No modifiques fuentes de datos, configuraciones BASE, PDF presentado, corridas existentes, snapshots, paquetes sellados ni sus manifiestos. Un código de posprocesamiento nuevo no debe atribuirse retrospectivamente a una corrida antigua.

## 3. Referencia y matriz cerrada

Usá como referencia las dos carteras continuas:

- Condicional: `run_ad71d751b20623006c195ff3`.
- Permanente: `run_dfea4b7ac1475668d5968c97`.

Período: `[2022-01-01T00:00:00Z, 2026-09-01T00:00:00Z)`, 10.000 USDT iniciales por cartera, BTCUSDT y ETHUSDT spot/perpetuos USD-M, sin reinicios anuales.

Derivá cada configuración desde la efectiva del caso base, no desde `Config()` con sus valores predeterminados. Estos últimos incluyen convenciones que no describen por sí solas la implementación presentada.

| ID | Dimensión | Únicos campos económicos modificados | Valor |
| --- | --- | --- | --- |
| H072 | Horizonte y tenencia | `horizon_hours`, `holding_hours` | 72, 72 |
| H336 | Horizonte y tenencia | `horizon_hours`, `holding_hours` | 336, 336 |
| V012 | Vida media EWMA | `half_life_hours` | 12 |
| V048 | Vida media EWMA | `half_life_hours` | 48 |
| B025 | Techo de basis | `basis_max` | Decimal `0.0025` |
| B100 | Techo de basis | `basis_max` | Decimal `0.01` |

Cada variante se evalúa para condicional y permanente: doce pares variante/cartera, más las dos referencias. Esto no exige volver a simular las referencias ni fabricar run_id nuevos para resultados reutilizados.

Campos que permanecen como en BASE, entre otros:

- Ventana de funding de 336 horas y disponibilidad de la señal 60 segundos después del evento.
- Horizonte/tenencia de 168 horas salvo H072/H336; vida media de 24 horas salvo V012/V048.
- Basis mínimo cero, máximo `0.005` salvo B025/B100; control de ampliación de basis sin cambios.
- Comisiones BASE: 0,10% spot y 0,05% futuros, sin promoción; deslizamiento de 1 punto básico por orden; mantenimiento BASE, no duplicado.
- Costo de entrada BASE de 34 pb por ciclo y renovación condicional con pronóstico estrictamente positivo.
- Objetivo spot de 30% del patrimonio por activo, garantía aislada 2x y reglas originales de rebalanceo.
- `next_minute_vwap`, `joint_quantity`, señales de minuto cerrado y participación máxima de 1% por instrumento/minuto/cartera.
- Secuencia de patas, parciales, cancelaciones, reintentos, tolerancias, salidas de riesgo y bloqueos.
- Método `futures_scaled` sólo para los 15 marks documentados y tratamiento original de precios de funding.
- Sin intereses sobre caja o garantías, sin modificaciones a SOFR y sin cambio de moneda.

El runner debe rechazar una variante cuyo diff económico exceda los campos permitidos. Cambios de rutas, identificadores o destinos se registran aparte y no justifican alterar parámetros económicos.

## 4. Ejecución por etapas y condiciones para continuar

### Etapa A: protocolo, pruebas y referencia

Fijá el protocolo y el registro de los seis escenarios antes de calcular sus resultados. Incluí pregunta, campos, unidades, población, métricas, reglas de exclusión, comparador y estados de ejecución. Esta historia ya fue observada: es sensibilidad exploratoria, no datos fuera de muestra nuevos.

Comprobá datos, entorno, espacio y costo de una ventana técnica. Reutilizá las fuentes locales de un minuto, sin descargarlas ni duplicarlas por escenario. La precarga conserva la ventana de 336 horas y el antecedente requerido; en BASE se utilizan 360 horas. No la sustituyas por el horizonte de 72 horas ni por la vida media de 12/48 horas.

Preferí configuraciones y scripts nuevos fuera del motor. No cambies la lógica económica ni los defaults para realizar este bloque. Si una incompatibilidad exige cambiar una interfaz o el motor, documentá el cambio mínimo necesario y pedí aprobación para esa parte; continuá con tareas independientes. No ocultes una corrección del motor dentro de una sensibilidad.

Verificá que la ruta elegida reproduce las convenciones de BASE. Si el runner cambia, contrastá una ejecución de control con la ruta original en una ventana técnica determinista. Si no podés demostrar compatibilidad suficiente con la evidencia presentada, ejecutá un replay BASE separado y compará las trayectorias completas antes de interpretar variantes. Coincidir en el saldo final redondeado no alcanza.

### Etapas B, C y D: seis variantes, sin cruces

Ejecutá primero H072/H336, después V012/V048 y finalmente B025/B100. En cada etapa: pruebas de parámetros, simulaciones de ambas estrategias, conciliación y resultados provisionales. No pases a interpretar una corrida con errores contables.

No es necesaria otra aprobación para esta matriz ya especificada. Sí corresponde consultar una decisión económica no autorizada. Un bloqueo puntual no detiene las dimensiones independientes que tengan entradas válidas.

Las corridas deben ser reanudables, con estados y logs individuales. Empezá sin concurrencia o con concurrencia prudente después de medir memoria; no lances doce backtests simultáneos por defecto. Los checkpoints sólo se reutilizan para la misma configuración, datos y código, restaurando íntegramente cuentas, posiciones, órdenes y pronósticos. No inicies una variante a mitad de la trayectoria BASE.

Reutilizá una corrida anterior únicamente si corresponde exactamente a la configuración, datos, implementación y período requeridos y sus verificaciones pasan. No reutilices una permanente con otra configuración sólo porque te parezca económicamente equivalente: ejecutala o acreditá una equivalencia específica y mantené separados los diagnósticos afectados. No copies forecasts, H1/H3 ni run_id con una etiqueta nueva.

### Etapa E: reporte y paquete

Consolidá todos los resultados, incluidos negativos, nulos e invariantes. Registrá `ejecutado`, `reutilizado_verificado`, `bloqueado` o `fallido`, más el estado económico real. Insolvencia no equivale a fallo técnico y no habilita eliminar el escenario. Una configuración sin ejecutar no cuenta como sensibilidad completada.

## 5. Contratos metodológicos de las tres dimensiones

### Horizonte

H072/H336 cambian conjuntamente el pronóstico, el objetivo de su evaluación y la tenencia/renovación de ambas estrategias. Esa es una dimensión económica compuesta, no una prueba que aísle exclusivamente calidad predictiva.

Calculá el forecast y el no-change para el nuevo horizonte usando los intervalos reales de funding. Para cada predicción, el objetivo realizado debe cubrir ese horizonte desde el instante definido por la evaluación original, no desde un ancla nominal elegida para mejorar coincidencias.

No escales el costo de 34 pb por `H/168`: sigue representando las cuatro órdenes de un ciclo. El pronóstico de cada horizonte se compara con ese mismo costo del ciclo. La renovación condicional conserva umbral cero, no vuelve a exigir todo el costo de entrada. El nuevo plazo no suprime las salidas anticipadas por riesgo.

El mayor horizonte puede excluir más predicciones finales de H1, pero no debe recortar la simulación financiera. No fuerces cierres, impidas entradas cercanas al final ni agregues funding después del fin exclusivo para completar targets. Conservá posiciones abiertas valuadas al final conforme a la metodología original.

### Vida media EWMA

V012/V048 cambian sólo los pesos. Mantienen ventana de 336 horas, pronóstico/tenencia de 168 horas, costos y no-change. Una observación con edad igual a la vida media debe pesar la mitad de una actual.

En la permanente el funding no decide entradas ni renovaciones. La posible invariancia económica frente al cambio de vida media debe comprobarse, no imponerse. Sus forecasts y diagnósticos sí pueden cambiar. Si cambian sus operaciones, investigá qué dependencia lo explica antes de llamar al resultado efecto económico del filtro.

### Techo del basis

B025/B100 mantienen el piso en cero y ambos extremos inclusivos. No cambian el control de ampliación de basis ni agregan ese filtro de entrada a la renovación.

El bloque anterior no encontró rechazos por superar el techo BASE en sus evaluaciones de entrada. Es un antecedente sobre esa población, no prueba de invariancia de todas las variantes o de todos los minutos de H3. B025 puede rechazar valores que antes pasaban; B100 puede dejar las carteras iguales y aun así cambiar el indicador de oportunidades de otros minutos. Comprobá por separado decisiones, economía y H3. No elimines el piso ni amplíes otra vez el techo para conseguir más operaciones.

## 6. H1, H2, H3 y comparabilidad

Conservá los resultados originales como referencia. Una evaluación de una variante no reemplaza las hipótesis ni las cifras de E3.

### H1: capacidad predictiva

Evaluá EWMA y no-change sobre las mismas observaciones válidas dentro de cada escenario, con MAE por activo y promedio BTC/ETH de igual peso. Incluí todos los pronósticos elegibles para H1, no sólo los que generaron entradas. Informá muestra completa, cortes originales y años.

Guardá horizonte, instante de señal, disponibilidad, forecast, no-change, target, límites temporales, validez y motivo de exclusión. Respetá la convención original del final exclusivo y la comprobación del calendario de funding. No fuerces los conteos de 168 horas sobre H072/H336 ni conviertas un forecast inválido cuyo campo numérico sea cero en una predicción válida.

Rotulá errores como pb/72 h, pb/168 h o pb/336 h. Un MAE menor en un horizonte más corto no demuestra por sí solo mejor modelo. Para comparar descriptivamente habilidad dentro de cada horizonte, podés mostrar `1 - MAE_EWMA/MAE_no_change`, sólo cuando el denominador sea positivo y la población sea común; no lo presentes como rentabilidad.

En V012/V048, targets y no-change deben conservarse si las observaciones son las mismas. En B025/B100, H1 debería ser invariante cuando sus inputs sean idénticos: comprobá igualdad de insumos y permití reutilización explícita de esa evaluación, no del resto de la cartera.

### H2: valor económico

Usá el contrato corregido: favorable sólo con CAGR condicional definido, finito y positivo, y Sharpe condicional definido y superior al de la permanente del mismo escenario y período. No exijas CAGR superior al permanente ni Sharpe positivo, porque no son requisitos originales.

Aplicá `no_favorable` y `no_concluyente` con los motivos de la corrección vigente. Usá valores sin redondear; conservá ND, cobertura y ventanas comparables. El Sharpe usa retornos diarios incluidos los días inactivos, desvío muestral, 365 días y RF=0. SOFR no reemplaza al comparador ni a esa tasa en este bloque.

### H3: oportunidad y cambio de período

Conservá los cortes 2022–2023 y enero de 2024–agosto de 2026, sin reiniciar cuentas. Para cada variante calculá su indicador con el forecast y filtros de ese escenario, independientemente de caja y posiciones: forecast completo cuando pasa funding/costo, basis y operatividad; cero si los datos son conocidos y no pasa; desconocido no equivale a cero.

Promediá los minutos de cada día válido por activo y luego ambos activos 50/50. Conservá conteos y sumas suficientes para revisar el cálculo, los timestamps reales de disponibilidad y el tratamiento de las interrupciones documentadas. No reemplaces esta población por el conteo de evaluaciones de entrada.

Dentro de cada escenario, compará oportunidad media y CAGR condicional entre los dos períodos: ambos disminuyen, favorable; ambos aumentan, contraria; otros casos evaluables, mixta; faltantes indispensables, no concluyente.

El indicador de H072/H336 tiene unidad propia, pb por su horizonte. Etiquetalo como evaluación de sensibilidad de H3 a ese horizonte, no como un nuevo valor de la H3 original de 168 horas. No mezcles magnitudes de horizontes distintos en una columna sin identificarlos ni transformes el indicador en retorno neto restando costos.

## 7. Métricas, diagnósticos y lectura del feedback

Por escenario/cartera, presentá muestra completa, los dos cortes y 2022, 2023, 2024, 2025, enero-agosto de 2026. Conservá saldos heredados y no sumes retornos anuales. Para cada período incluí:

- Patrimonio inicial/final, P&L y componentes, retorno, CAGR, Sharpe, volatilidad y drawdown diario.
- Tiempo activo sin polvo, utilización media/máxima diaria y capital utilizado. El polvo conserva valor y riesgo en equity; no se deduce del patrimonio.
- Ciclos, intentos, aperturas completas, renovaciones, parciales, fallas y motivos de cierre; no confundas intentos de órdenes con ciclos.
- Exposición activa sin cobertura como unión temporal entre BTC/ETH, y eventos de margen/liquidación/deuda de los registros disponibles.
- H1/H2/H3 con sus unidades, comparadores, cobertura y diferencias respecto de BASE.

Reutilizá la semántica corregida de exposición sobre la trayectoria completa de cada nueva cartera y luego recortá períodos. No copies el 28,32%/98,21% de BASE a variantes ni cuentes residuos no negociables como posiciones activas.

Adaptá el diagnóstico de entradas ya implementado: partición excluyente de funding/basis, no evaluables, primer bloqueo y acciones efectivas. La permanente puede fallar funding descriptivamente sin rechazar por él. Las renovaciones se estudian aparte, sin imponer costo ni basis de entrada.

No rehagas ahora concentración completa por ciclos, SOFR ni millones de observaciones intradía. Los drawdowns nuevos de este bloque son diarios. Podés referir el intradía BASE previamente publicado con su etiqueta, pero no atribuirlo a una variante no reconstruida ni comparar ambos como si tuvieran la misma frecuencia. Los extremos de garantía calculados sólo en cierres diarios deben rotularse como tales.

La conclusión debe indicar qué cambia en predicción, actividad, capital utilizado y resultado económico, y qué permanece estable. Los cambios anuales complementan el agregado. No atribuyas causalmente toda variación de retorno a un único contador ni concluyas robustez universal porque seis variantes sean favorables o invariantes. La selección estadística y la optimización quedan fuera de alcance.

## 8. Pruebas y controles mínimos

Escribí primero pruebas pequeñas con expectativas explícitas. Aprovechá las existentes, sin recrear una infraestructura general. Como mínimo:

1. La matriz tiene sólo seis variantes y cada diff económico coincide con la tabla; BASE sigue igual. Una combinación accidental horizonte+vida media se rechaza.
2. H072/H336 modifican horizonte y holding de ambas estrategias, sin modificar window, warmup requerido, comisiones ni umbrales. Verificá vencimientos y renovaciones con riesgo prioritario.
3. Con historial idéntico y válido, forecast/no-change escalan con H conforme a la fórmula; sus targets realizados se reconstruyen para H, no escalando el target de 168 horas. Cubrí intervalos de funding irregulares.
4. Ventana de historial exclusiva/inclusiva y disponibilidad exactas; peso 1 a edad cero y 1/2 a edad igual a la vida media. No uses tasas publicadas después de decidir.
5. Forecast igual al costo no habilita entrada; forecast de renovación positivo pero inferior al costo sí supera su condición de funding; cero no. La permanente omite ambos filtros, no los demás.
6. Basis negativo, cero, cada techo exacto y un valor inmediatamente superior; basis de entrada no se impone a renovaciones y su stop de ampliación queda intacto.
7. H1 excluye horizontes fuera de muestra o sin calendario acreditado, mantiene motivos y no confunde inválido con cero. Cambiar H no corta el período financiero.
8. H2 con CAGR negativo y Sharpe menos negativo que el permanente no es favorable; ND conserva el contrato corregido. H3 no depende de posiciones y no trata desconocidos como ceros.
9. Ciclos/posiciones heredados entre años, parciales, polvo, simultaneidad de activos, funding antes de fills simultáneos y ausencia de cierres ficticios al final.
10. Cachés y reutilización identifican campos relevantes: cambiar H o vida media invalida forecast; cambiar basis invalida elegibilidad/H3 y decisiones aunque no necesariamente H1. No reetiquetes resultados viejos.
11. Cada cierre diario y cada período concilian contra componentes de P&L a la tolerancia original `1E-8` USDT. Compará BASE con su evidencia de máxima precisión, no sólo los redondeos del PDF.
12. Verificadores rechazan corrupción de configuración, H1, H2, H3, períodos y cifras aun cuando se renueven hashes en una copia temporal. Verificar no escribe en fuentes ni paquetes sellados.

Los casos sintéticos son pruebas, no resultados históricos. Registrá fallos, correcciones y pases reales. No copies números de tests de sesiones anteriores. Si una fuente indispensable falta, informá el bloqueo sin fabricar valores y continuá las partes independientes.

## 9. Productos, identidad y publicación

Usá una carpeta nueva bajo `entregas/entrega_4/senal_entradas/`, con fecha real e identificador. Configuraciones nuevas pueden ir en `configs/entrega_4/senal_entradas/`; scripts y pruebas deben seguir la organización vigente. Esas rutas son destinos propuestos, no archivos que se afirme haber encontrado.

Entregá:

- Protocolo y registro de seis escenarios, campos modificados, estados, run_id, procedencia y comandos.
- Reporte Markdown/HTML con síntesis, tres secciones de sensibilidad, resultados anuales/capital, hipótesis y límites. No generes el PDF final ni reescribas E3.
- Tabla comparativa y deltas contra BASE, curvas de patrimonio, evidencia diaria y componentes de P&L.
- H1 por observación/período, H2 completo, H3 con agregados diarios por activo y diagnóstico de entradas/exposición suficiente para auditar las métricas publicadas.
- Configuraciones efectivas, hashes de inputs, snapshots del código realmente usado, índices de corridas y fuentes de cada cifra. Si el código no cambia, registrá esa identidad en vez de fingir una nueva versión económica.
- Matriz de requisitos de este bloque con cumplido/parcial/bloqueado y referencias concretas. No marques toda E4 como completa.
- Verificador, pruebas y resultados de conciliación/preservación, con manifest y checksum nuevos.

Mantené las fuentes masivas y salidas voluminosas locales, sin duplicarlas por escenario. El paquete publicable debe contener evidencia suficiente para los recálculos que declara y dependencias explícitas para los demás. No dupliques por defecto todos los paquetes anteriores. Un hash de una serie ausente no acredita haber recalculado sus indicadores.

El verificador debe poder ejecutarse offline desde otra ruta, sin HEAD/índice idénticos a una sesión pasada. Probalo en copia limpia con dependencias indicadas por argumentos. Registrá qué comprueba numéricamente, qué autentica sólo por hash y qué requiere datos locales. No atribuyas independencia total a constructor y verificador si comparten lógica.

Protegé los nuevos archivos verificables contra conversión de finales de línea mediante reglas Git limitadas a la nueva evidencia. No cambies reglas globales ni renormalices el repositorio. Comprobá los bytes que se publicarían mediante una exportación o índice temporal aislado, sin modificar el índice del usuario.

Al final ejecutá las pruebas nuevas y de regresión pertinentes, Ruff, verificadores de entradas, conciliaciones de cada corrida y verificación portable. El control histórico general que espera hashes antiguos puede tener un alcance distinto del árbol actual: documentá la causa, no actualices el manifiesto viejo para forzar su pase ni declares por ello validado todo el motor.

## 10. Fuera de alcance y cierre

No ejecutar: otras sensibilidades de costos, capacidad, latencia, fecha inicial, shocks o contrafactual sin interrupción; remuneración de efectivo/garantías; nuevos cálculos SOFR; búsquedas históricas amplias; inferencia estadística; optimización o selección de ganadores.

No descargar trades/aggTrades ni ampliar activos/fechas, usar credenciales o servicios pagos, modificar paquetes anteriores, hacer commit, push, cambios de índice, reset destructivo o escrituras en servicios externos. No ajustar tolerancias para aceptar discrepancias.

La respuesta final debe resumir qué escenarios terminaron, qué se reutilizó, qué hipótesis cambian descriptivamente y cuáles no, qué bloqueos quedan, dónde está la evidencia y qué comandos pasaron realmente. Separá nuevos resultados económicos de diagnósticos recalculados. Una variante sin cambios es un resultado válido, no una invitación a cambiar el experimento.

No solicites aprobación por cada paso ya definido. Ejecutá el bloque por etapas, con controles entre ellas, y consultá únicamente decisiones que excedan este alcance.

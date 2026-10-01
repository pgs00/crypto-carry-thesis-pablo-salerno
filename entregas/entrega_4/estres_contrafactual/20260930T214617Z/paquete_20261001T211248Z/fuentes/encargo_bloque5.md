# Encargo para Codex: bloque 5, movimientos adversos y escenario sin interrupción

Trabajá en el proyecto Backtesting del repositorio `pgs00/crypto-carry-thesis-pablo-salerno`.

## 1. Objetivo, alcance y aprobación necesaria

Este bloque debe responder dos preguntas distintas:

1. Qué pérdidas y necesidades de garantías pueden producir movimientos adversos durante la exposición sin cobertura.
2. Cómo cambia la trayectoria del carry bajo un escenario explícitamente hipotético sin la interrupción spot del 24/03/2023.

No es una búsqueda de parámetros rentables. No repitas las demoras del bloque 4 ni combines shocks con latencia, OHLC4, costos estresados o capitales mayores. No generes todavía Word ni PDF.

El esquema acordado dejó los supuestos del bloque 5 pendientes de aprobación. Este encargo tiene dos etapas:

- **Etapa A, autorizada ahora:** verificar entradas y referencia corregida, recuperar la calibración existente, preparar un protocolo concreto para cada familia y un inventario breve de limpieza sin modificar archivos anteriores. Entregar una única solicitud de aprobación metodológica, con una recomendación definida, no un menú abierto.
- **Etapa B, sólo después de aprobación expresa:** implementar, probar, ejecutar y verificar únicamente los escenarios aprobados. Las instrucciones de esta etapa ya están incluidas abajo para que puedas continuar con el mismo encargo.

Recibir este archivo NO aprueba automáticamente una senda sintética, una liquidez inventada, una ampliación de escenarios ni borrar paquetes antiguos. No ejecutes los escenarios propuestos para comparar rendimientos antes de elegir el protocolo. Sí podés recalcular estadísticas descriptivas de entradas, revisar cobertura y ejecutar pruebas técnicas neutras que no determinen qué escenario elegir.

Antes de detenerte por la aprobación, terminá las tareas independientes de la etapa A. No declares completo el bloque 5 por haber preparado sus fichas.

## 2. Contexto y referencias que deben preservarse

Identificá instrucciones del proyecto, raíz, rama, HEAD, entorno, datos locales y cambios ajenos, incluido el índice. La última versión revisada es `65ff8c412366817c68bdf1f37ca62a1cbfcfea6e`; no retrocedas a ella ni descartes cambios posteriores.

Leé y autenticá los materiales pertinentes:

- `docs/methodology.md`, `docs/entrega_4/matriz_avance.csv` y su historial.
- Las configuraciones efectivas y salidas BASE: condicional `run_ad71d751b20623006c195ff3` y permanente `run_dfea4b7ac1475668d5968c97`.
- `entregas/entrega_4/reglas_historicas/20260925T005436Z/` y la corrección `entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/`.
- `entregas/entrega_4/riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z/`: feedback, metodología, catálogo de episodios, garantías, proxy de valoración y propuestas pendientes.
- Dentro de ese paquete de riesgo: `figuras/fuentes/calibracion_episodios.csv` y `figuras/fuentes/calibracion_escenarios_pendientes.csv`.
- Bloque 4 vigente: `entregas/entrega_4/ejecucion_demoras/20260929T221620Z/paquete_20260930T013915Z_v2/` y sus controles externos, incluidos `control_compatibilidad_base_completa.json` y `entrega_verificada.md` en la carpeta de trabajo.
- Bloques 1, 2 y 3 mediante los enlaces de la matriz global, sin duplicar sus paquetes completos ni recalcular sus estudios.
- Encargo general de Entrega 4 y consigna académica, si están disponibles. No afirmes haber leído un documento ausente.

El feedback ya fue recibido. El bloque 5 complementa la reconstrucción intradía observada; no la sustituye con datos hipotéticos. Las demoras generales y exclusivas de cierre ya fueron ejecutadas en el bloque 4. SOFR ya está terminado y no remunera la caja del carry.

Referencia económica: muestra continua UTC `[2022-01-01T00:00:00Z, 2026-09-01T00:00:00Z)`, 10.000 USDT por cartera, BTCUSDT/ETHUSDT spot y perpetuos USD-M, sin reinicios anuales. Mantener horizonte/tenencia 168 h, vida media 24 h, ventana 336 h, precarga 360 h, disponibilidad de funding 60 s, basis inclusivo `[0,0.005]`, costo de selección 34 pb, renovación condicional con forecast positivo y permanente sin filtro de funding. Conservar asignación, margen, tarifas, slippage, VWAP, participación y controles de BASE; opciones de demoras apagadas. Derivar desde la configuración efectiva original, no desde `Config()` ni desde una variante ganadora.

Guardá hashes e identidades iniciales. No modificar fuentes originales, archivos entregados, BASE, corridas ni paquetes sellados.

## 3. Usar el motor corregido, sin reabrir toda la investigación

La reparación aprobada del bloque 4 evita reenviar como cierre ordinario un remanente ya escalado a liquidación y evita restaurar HOLDING mientras quede corto por liquidar. Revisá la aprobación, el cambio y sus pruebas, no sólo el saldo final.

Autenticá los dos controles BASE completos con el motor corregido y las comparaciones ordenadas de sus once artefactos. Se publicaron como `run_d7c7cb5da666e22321598598` y `run_415276e8a8b5bb9101e2d13b`, separados de las BASE originales. Confirmá sus identidades en el índice, sin imponerlas si existe una revisión posterior documentada.

La igualdad de esos controles cubre BASE, no automáticamente todas las variantes antiguas. Conservá en la matriz transversal la comprobación pendiente de alcance sobre los bloques 2 y 3. No la marques resuelta porque no haya un fill etiquetado como liquidación: el defecto podía precisamente perder esa clasificación. Tampoco repitas todas esas variantes dentro del bloque 5.

Para iniciar este bloque, la referencia corregida debe estar identificada y conciliada. Si la nueva capa de escenarios modifica código común, las opciones apagadas deben volver a demostrar equivalencia con esa referencia. Si aparece una discrepancia económica en BASE, detené la interpretación afectada, documentá el caso y consultá antes de reemplazar comparadores.

## 4. Etapa A: ficha de movimientos adversos

### 4.1 Recuperar la calibración existente

Recalculá y conciliá, desde el catálogo publicado, los niveles P90 y máximo de caída spot por activo. Conservá la definición original de caída dentro del episodio, los ceros, el tratamiento de faltantes, la población y el método de percentil. No cambies el método para obtener valores más convenientes.

La tabla existente separa `original_reconstructed` de `valoracion_proxy_hipotetica`, con 100 episodios BTC y 133 ETH. Estos conteos son controles a verificar, no resultados a imponer. Conservá las fracciones exactas de los archivos y convertí a porcentajes sólo para presentar. No confundas un valor decimal con puntos básicos.

P90 y máximo son magnitudes descriptivas de una muestra ya observada, no probabilidades de pérdidas futuras, niveles de confianza ni calibración disponible ex ante en 2022. Los episodios de ambas carteras pueden compartir mercado y no son ensayos independientes. El precio spot antiguo durante la suspensión puede afectar esa calibración.

La propuesta inicial parte de dos niveles por activo, P90 y máximo de la valoración original. Mostrá cuánto difieren de los niveles calculados con el proxy, sin ejecutar automáticamente otra matriz con ese proxy. Si recomendás cambiar la calibración principal, explicá por qué y pedilo en la misma ficha, antes de calcular resultados económicos.

### 4.2 Cerrar la especificación que aún falta

Proponé un protocolo recomendado y sin ambigüedades para dos escenarios principales, provisionalmente `SH_P90` y `SH_MAX`. Debe definir:

- La pregunta exacta: shock al spot descubierto o movimiento conjunto spot/perpetuo. La propuesta previa era de caída spot; no la transformes silenciosamente en un shock conjunto de mark y spot.
- Qué series se modifican y cuáles se conservan. Una caída sólo del spot con futuro/mark intactos es también una perturbación de la relación entre mercados; debe nombrarse así. No prueba por sí sola resistencia del corto a subas ni cubre todos los riesgos de garantías.
- Población, activos, disparador, instante inicial, duración, final y tratamiento de solapamientos. No aplicar un nuevo shock en cada minuto del mismo episodio ni componer repetidamente el mismo descenso sin una regla explícita.
- Qué ocurre si, por el shock, el cierre llega antes o después que en BASE, desaparece un episodio o aparece uno nuevo.
- Si es una trayectoria continua de mercado común a ambas estrategias o un conjunto de replays locales emparejados por episodio. Elegí y recomendá una opción; explicá la diferencia de interpretación, costo y métricas permitidas.
- Si se usan fechas del catálogo BASE, reconocer que es un calendario de estrés retrospectivo fijado antes de ejecutar el escenario. No es una señal de negociación ni una política que pudiera conocer incidentes futuros.
- Si se activa según el estado de cada estrategia, reconocer que las dos carteras pueden recibir sendas distintas. No presentar su diferencia como H2 bajo un mismo mercado.
- Cómo termina o revierte la perturbación y qué inventario queda. No restablecer precios al cerrar la posición y atribuir una recuperación artificial a la estrategia. Todo salto de retorno al precio original debe ser explícito, medido y no elegido según el P&L.
- Cómo se trata el intervalo sin spot observado. Un proxy de valoración no permite inventar transacciones durante una suspensión. Las suspensiones originales permanecen en estos escenarios de shock.

Para una comparación H2 de trayectorias completas, preferí que ambas carteras reciban la MISMA senda exógena hipotética y la misma liquidez. Si el diseño más defendible son replays locales, pedí aprobar expresamente ese alcance y no fabricar una cartera anual sumando experimentos incompatibles.

No queda fijado por este prompt el calendario ni la duración del shock. Son precisamente decisiones que la ficha debe resolver y el usuario aprobar. No reemplaces la simulación solicitada por multiplicar cantidad inicial por caída y llamar a eso backtest. Ese cálculo puede ser un control estático, identificado como tal.

## 5. Etapa A: ficha del escenario sin interrupción

Proponé un escenario principal, provisionalmente `CF_SIN_INTERRUPCION`, con la misma senda hipotética para ambas estrategias.

Primero identificá el intervalo exacto de interrupción spot del 24/03/2023 desde el calendario y las fuentes del proyecto, por activo. No confundas la duración del cierre del mercado con los 121 minutos de exposición descubierta de BASE. Reconstruí la cronología antes/durante/después, sin rehacer todo el estudio intradía.

La ficha debe especificar por separado:

1. **Operatividad:** qué cierres del calendario y validadores se sustituyen sólo dentro de la capa de escenario y cuáles permanecen iguales. No borrar globalmente la suspensión ni convertir cualquier hueco de datos en mercado abierto.
2. **Precios:** fórmula exacta de OHLC/VWAP sintético, fuentes, anclas y disponibilidad. Una propuesta que use futuros y una relación spot/futuro anterior al cierre debe indicar los datos exactos del ancla y no utilizar el precio posterior a la reapertura para reconstruir decisiones anteriores.
3. **Volumen:** una regla cuantitativa defendible para el volumen spot hipotético, calibrada con una ventana definida anterior al cierre. Justificar ventana, estadístico, estacionalidad y unidades. No copiar volumen de futuros como si fuese spot, no asumir liquidez infinita y no escoger el mínimo volumen que haga funcionar la cartera.
4. **Coherencia de velas:** volumen base, volumen cotizado, precio de referencia, OHLC y actividad consistentes. Un producto precio por volumen puede ser una construcción sintética, no una medición oficial de esas operaciones.
5. **Disponibilidad:** publicar la vela sintética sólo en su final; no usar sus valores finales para dimensionar una orden anterior. Los metadatos deben distinguir observaciones reales de supuestos.
6. **Reapertura:** cuándo vuelve la fuente observada y cómo se trata cualquier salto de valoración. No ajustar el ancla usando el futuro para que la unión parezca perfecta. Cuantificar el salto y los efectos de borde por separado.
7. **Alcance económico:** precios/volúmenes hipotéticos alteran decisiones, ejecución, inventario, funding monetario cuando corresponda y garantías. No mantener los cierres originales y sólo cambiar su valoración.

Podés presentar una alternativa descartada si ayuda a justificar la elección, pero entregá una recomendación concreta con reglas completas. No comparar rendimientos de candidatos antes de elegir. No lanzar una búsqueda general de nuevos datos ni descargar trades/aggTrades.

Mantener sin cambios las series de futuros, marks y tasas de funding es una posible condición de este contrafactual, no prueba de que hubieran sido iguales en un mercado realmente abierto. Nombrar esa limitación. El contrafactual no identifica causalmente cuánto beneficio real causó la interrupción ni afirma lo que habría sucedido.

El objetivo de esta familia es una trayectoria completa hasta el fin de la muestra, no restar el resultado de un día o eliminar una línea de calendario. Si no hay una especificación defendible, entregar el bloqueo concreto; no marcarlo como cumplido ni ocultarlo detrás del proxy de valoración ya realizado.

## 6. Entrega y puerta de aprobación de la etapa A

Entregá una ficha breve de decisión con apoyo técnico separado. Debe contener, para cada escenario: ID, pregunta, activos, magnitud/unidad, fuente, fórmula, disparador, duración, calendario, series alteradas, liquidez, regla al terminar, comparador y límites.

Fijá el número propuesto de trayectorias y un presupuesto razonado de tiempo/espacio. El objetivo es dos niveles de shock y un contrafactual, no una cuadrícula de parámetros. Si se aprueban como trayectorias continuas compartidas, serían seis carteras nuevas, dos estrategias por escenario, más referencias. Los controles técnicos se contabilizan aparte. Si recomendás un diseño local por episodios, explicá el conteo diferente antes de ejecutarlo.

La solicitud de aprobación debe mostrar todas las decisiones económicas materiales. No usar “aprobado con supuestos a definir después”. Puede aprobarse una familia y quedar la otra pendiente, sin frenar la primera.

Estado de matriz hasta entonces: `protocolo_preparado_pendiente_aprobacion`. Guardá respuesta y ficha aprobada con identidad verificable. Al aprobarse, fijá el protocolo antes de correr resultados y continuá con la etapa B sin volver a pedir permiso para cada paso ya definido.

## 7. Etapa B: arquitectura de escenarios y pruebas previas

Usá el motor corregido del bloque 4 y una capa derivada de datos/calendario identificable. No reescribas precios originales ni copies toda la base de minutos por escenario. Podés implementar adaptadores pequeños o extensiones optativas estrictamente necesarias para las fichas aprobadas; no rediseñar el motor ni desactivar validaciones globales.

Inspeccioná los lectores/calendarios, `strategy.py`, `execution.py`, `models.py`, las auditorías del bloque 4 y los helpers de riesgo antes de elegir la interfaz. Registrá qué validador acepta cada dato hipotético y por qué: una etiqueta sintética no debe ocultar ausencias inexplicadas fuera de la intervención.

Conservar:

- Fuente, valor y hash originales; valor modificado; fórmula; escenario; intervalo de aplicación; momento de disponibilidad y unidad de cada dato intervenido.
- Un único criterio consistente para señales, ejecución y valoración cuando dependen de la misma serie. No presentar un feed transformado como precio oficial.
- OHLC internamente consistente y volumen cotizado coherente con el VWAP sintético cuando se lo modifica; volumen cero no habilita ejecución.
- Ventana de un minuto, participación bruta compartida, secuencia de patas, parciales, reintentos, comisiones, slippage, tick y reservas originales, salvo los cambios expresamente aprobados.
- Funding sobre las posiciones anteriores a fills simultáneos, controles de margen y la reparación de prioridad de liquidación. No eliminar cargos, cambiar plazos preventivos o demorar liquidaciones para mejorar el resultado.

Un shock revelado en un instante no puede modificar la ventana ya consumida para producir el estado desde el que se lo aplica. Definí y probá la fase y el primer intervalo afectado. No conocer extremos futuros de una vela al abrir la posición ni imputar retrospectivamente una caída al precio de una orden ya ejecutada.

Con tasa de funding sin cambios, el importe puede cambiar por cantidades o marks; separar ambas cosas. Si la ficha modifica marks, sus efectos sobre garantías y liquidación no pueden quedar congelados ni seguir etiquetados como oficiales. No usar mínimos spot y máximos mark de una vela como si se hubieran observado simultáneamente.

### Controles obligatorios antes de interpretar

1. Capa apagada reproduce la referencia corregida en config, órdenes, fills, ledger y cierres; perturbación de magnitud cero conserva la economía.
2. El modo contrafactual apagado conserva la suspensión; el modo shock no habilita transacciones en ella. Otros huecos siguen siendo errores de cobertura.
3. No se modifica ningún dato anterior al instante aprobado, posterior al intervalo autorizado o de un instrumento no incluido. Probar fronteras y nanosegundos.
4. La capa no usa información de reapertura para decidir durante la suspensión. Probá la independencia cambiando datos posteriores en un fixture.
5. Units, porcentajes, factores, OHLC, quote/base, cupo, step, comisiones en base y tick adverso correctos, sin doble descuento de slippage.
6. Shock aplicado una vez según la regla de episodios/solapamientos, sin propagación accidental entre escenarios o activos; su final no depende de elegir la ganancia observada.
7. Riesgo con corto, spot descubierto, liquidación escalada con remanente, deuda, reservas y funding simultáneo. Después de cerrar el corto no existe margen para ese contrato.
8. Checkpoint restaura TODO el estado y produce el mismo resultado que la ejecución continua, incluida la capa de intervención, RNG si existiera y órdenes pendientes. No hay aleatoriedad salvo aprobación explícita.
9. Conciliación diaria y por período a la tolerancia original `1E-8` USDT. Un shock cambia valor de mercado, no es depósito/retiro ni cargo inventado. Aportes hipotéticos no se inyectan al resultado BASE.
10. Pruebas negativas del verificador realmente modifican bytes/celdas antes de invocarlo, respetan tipos Parquet y conservan evidencia de la modificación. No confundir error al fabricar una adulteración con rechazo del verificador.

Escribí las pruebas antes de implementar cada extensión. Registrá fallos y correcciones. Si una modificación económica posterior afecta corridas, repetí sólo las afectadas con identidad nueva. No reutilizar una corrida de distinto código sólo porque tenga el mismo saldo final.

## 8. Ejecución, resultados y métricas permitidas

Ejecutá por familia, con controles intermedios, sin concurrencia indiscriminada. Usá las BASE originales como referencias preservadas y el control corregido autenticado como ancla de compatibilidad. No adoptar L01, H336, A100 u otra variante por haber mejorado H2.

Para el contrafactual continuo y para shocks continuos aprobados, recalculá desde inicio hasta fin o desde un checkpoint previo cuya equivalencia integral se demuestre. No reiniciar cuentas cada año ni retomar desde un estado BASE posterior a la intervención. Mantener estados ejecutado/reutilizado/bloqueado/fallido separados del estado económico real, incluyendo insolvencia.

Informá total, los dos cortes H3 y los cinco años, con 2026 parcial: equity inicial/final, P&L y componentes, retorno, CAGR365, Sharpe RF=0, volatilidad, drawdown diario, utilización diaria, tiempo activo sin polvo, ciclos, ejecución, exposición, deuda y liquidaciones. No sumar porcentajes anuales ni dividir CAGR por utilización media.

Para replays locales por episodio aprobados: comparar estado común de partida, senda/ejecuciones, pérdida transitoria, duración, resultado hasta el final local y fondos requeridos. No sumar pérdidas de experimentos alternativos para construir una cartera, no anualizar replays cortos y no atribuirles H2/H3 de la muestra completa. Si se cambia el alcance a local, registrarlo como decisión aprobada, no como cumplimiento ficticio de una trayectoria continua.

Analizá pérdidas y garantías dentro de las ventanas intervenidas, con frecuencia y cobertura explícitas. Separá mantenimiento, saldo de margen, holgura, necesidad preventiva hipotética y posible faltante externo. Caja bruta no equivale a caja libre de compromisos; conservar ND o cotas cuando las reservas no sean acreditables. No introducir capital externo o rehypotecar garantías sin aprobación.

En el escenario sin interrupción, separar: divergencia de precios/operatividad/liquidez, cambios de decisiones, desempeño del día y efecto posterior hasta el fin. El efecto bajo esos supuestos no es una estimación causal identificada de la interrupción real.

No reconstruir por defecto toda la muestra intradía para cada escenario. El drawdown de la tabla principal será diario; las pérdidas/márgenes de ventanas concretas no se llaman máximos intradía globales. Mantener cualquier valoración de spot antiguo o hipotético claramente identificada.

## 9. H1, H2 y H3: no trasladar invariancias sin comprobarlas

- **H1:** si sólo se modifican precios/volumen/operatividad, las tasas y targets de funding pueden permanecer iguales. Comprobar las proyecciones, disponibilidad y cobertura antes de reutilizar una cohorte. Una simulación detenida no autoriza atribuirle observaciones que no persistió. Datos de evaluación no son información ex ante de negociación.
- **H2:** sólo comparar carteras continuas bajo el mismo escenario de mercado, período y capital. Mantener CAGR condicional positivo y Sharpe superior al permanente del escenario, con ND y RF=0. Una intervención dependiente de la cartera no es automáticamente un experimento H2 comparable.
- **H3:** a diferencia del bloque 4, cambiar spot, basis u operatividad PUEDE cambiar la oportunidad de mercado. Recalcularla sobre la senda hipotética común cuando corresponda, independiente de posiciones/fondos. No copiar la oportunidad BASE por conveniencia. Conservar forecast completo cuando pasa los filtros, cero para fallas conocidas y ND para desconocidos, promedio diario por activo y 50/50 entre activos, cortes originales y unidad pb/168 h.

Conservar H1/H2/H3 originales como referencia. Una evaluación con datos hipotéticos es sensibilidad de esas hipótesis, no nueva evidencia histórica ni validación fuera de muestra. Sin mercado contrafactual común o cobertura suficiente, no fabricar un indicador H3 formal.

No imponer resultados monótonos ni omitir escenarios que ganan más o pierden menos. No atribuir probabilidad al P90 usado como magnitud, no buscar la intensidad que haga ganar al filtro y no modificar reglas tras observar los resultados.

## 10. Productos y verificación, sin multiplicar copias completas

Destinos nuevos propuestos: `entregas/entrega_4/estres_contrafactual/<id_real>/`, configuraciones en `configs/entrega_4/estres_contrafactual/`, scripts/tests en la estructura vigente. Estos nombres son destinos propuestos, no archivos que se afirme haber encontrado.

Etapa A: informe de entradas/compatibilidad, calibración autenticada, fichas de aprobación, cobertura y un plan breve de ejecución. Etapa B: protocolo aprobado, escenarios/estados/run_id, reporte Markdown/HTML y síntesis integrable, tablas/figuras con fuentes, evidencia de intervención, conciliaciones, pruebas, manifiesto y verificador de alcance declarado.

El paquete final debe distinguir:

- Observaciones y fuentes preservadas.
- Transformaciones y supuestos aprobados.
- Resultados de nuevas ejecuciones.
- Diagnósticos reutilizados y controles que exigen datos masivos locales.

Verificar offline desde otra ruta, sin HEAD/índice original, con herramientas incluidas o dependencias explícitas verificadas. Indicar qué se recalcula y qué sólo se autentica; declarar lógica compartida con el constructor. Auditorías finales van fuera del sello. Probar regresión, Ruff, integridad de inputs, bytes de exportación y reproducción de la capa. No renovar hashes antiguos para ocultar diferencias.

**Política nueva de trabajo para este bloque:**

1. Un único candidato de presentación NO sellado mientras se revisan reportes y tablas. Mantener corridas originales inmutables y logs/diffs de revisiones; no hace falta clonar todos los datos por cada cambio de texto.
2. Temporales y copias de pruebas fuera del árbol versionado, en directorios exclusivos creados para esta tarea. Usar copias reales, no enlaces o junctions hacia originales que una limpieza pueda recorrer.
3. Sellar una sola entrega final después de las pruebas. Si luego hay una corrección real de algo ya sellado, conservar trazabilidad y crear la versión necesaria; no falsificar un sello anterior ni prohibir una revisión necesaria por ahorrar archivos.
4. No duplicar todos los paquetes previos. Incluir únicamente evidencia necesaria o dependencias con ubicación e identidad explícitas, verificando la portabilidad que se declare.
5. Un índice editable muestra la versión vigente y qué reemplaza. Cada versión nueva debe tener un motivo técnico concreto, no sólo un nombre distinto.

## 11. Limpieza existente: diagnóstico separado, sin borrados

El usuario preguntó si conviene retirar versiones anteriores. En este encargo se autoriza INVENTARIAR y PROPONER, no eliminar, mover, comprimir como sustitución, modificar sellos ni reescribir historia Git.

En la carpeta del bloque 4 revisada aparecen `paquete_20260930T012056Z` y `paquete_20260930T013915Z_v2`. No asumir que existe `paquete_20260930T013915Z` sin sufijo ni usar un comodín para “borrar la primera”. Verificar el árbol real.

Crear una propuesta breve bajo `docs/entrega_4/` con rutas exactas, tamaño, estado vigente/reemplazado/temporal, referencias entrantes y acción sugerida. Identificar específicamente las dependencias entre los dos paquetes del bloque 4 y sus controles. Un hash igual puede acreditar duplicación de contenido, pero no que una ruta no sea necesaria.

Clasificar lo que podría archivarse intacto fuera del árbol activo, lo que debe conservarse como dependencia, y temporales regenerables candidatos a eliminación. Para archivos versionados, comprobar que estén publicados y recuperables por commit concreto; no usar “está en Git” como prueba sin verificar contenido e identidad. Para datos sólo locales, exigir respaldo comprobado antes de proponer retirarlos.

Antes de recomendar retiro de una carpeta, probar en una COPIA AISLADA la verificación de las versiones vigentes sin esa carpeta, incluyendo enlaces/documentación y los controles de procedencia que todavía se quieran reproducir. Una referencia histórica puede redirigirse en un índice externo a un archivo preservado; no editar por eso documentos dentro de un sello. No declarar seguro un borrado sólo porque pasa el verificador principal.

No ejecutar `git clean`, `reset --hard`, `filter-repo`, BFG, force-push, borrados recursivos globales o cambios del índice del usuario. No seguir symlinks/junctions al calcular candidatos de limpieza. Tampoco crear otra copia completa de todo el repositorio para hacer este inventario.

Entregar la lista para una autorización posterior y separada por rutas. Retirar archivos del árbol vigente ordena el trabajo; no implica que desaparezcan de commits anteriores ni que se reduzca proporcionalmente el historial Git. Este encargo no incluye migrar a LFS, Releases u otro servicio ni subir archivos fuera del repositorio.

La propuesta de limpieza es una tarea pequeña e independiente. No debe expandirse a una reestructuración general ni impedir completar las fichas del bloque 5.

## 12. Cierre y restricciones

Actualizar la matriz global con el estado real de cada familia, las decisiones pendientes y enlaces a la versión vigente. Bloque 6 y revisión transversal/redacción siguen pendientes. El control de alcance del defecto sobre variantes previas permanece separado hasta tener evidencia suficiente.

No repetir bloques 1 a 4, SOFR, demoras, otras sensibilidades o búsquedas históricas amplias. No ejecutar inferencia estadística, optimización, caja remunerada, aportes de capital ni escenarios adicionales por iniciativa propia. No descargar trades/aggTrades, ampliar universo/muestra, usar servicios pagos o credenciales. No hacer commit, push ni modificar el índice del usuario.

Respuesta final de la etapa A: qué entradas validaste, la propuesta concreta y sus supuestos, qué aprobación se necesita y dónde está el inventario de limpieza, dejando claro que aún no hay resultados de shocks/contrafactual.

Respuesta final de la etapa B: qué se ejecutó y verificó realmente, impactos observados bajo los supuestos aprobados, límites, pendientes, rutas de evidencia y comandos ejecutados. No declarar toda Entrega 4 completa, ni afirmar publicación en GitHub por haber preparado archivos localmente.

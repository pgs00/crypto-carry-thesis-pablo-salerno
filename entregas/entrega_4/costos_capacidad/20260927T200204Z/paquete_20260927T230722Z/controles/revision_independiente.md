# Revisión independiente y correcciones

Revisor: agente `review_cost_extension`, lectura acotada sin edición de archivos.
No es una segunda implementación del motor. La inspección se complementa con
pruebas negativas y conciliaciones; no sustituye los controles reproducibles.

## Extensión económica y recuperación

No se encontraron cambios económicos ajenos al alcance en la extensión de
cuatro archivos. El revisor comprobó las pruebas de contrato y ejecución.
Se señalaron cuatro controles técnicos: escenario/estrategia en reanudación,
exclusión mutua por par, H3 por intento y autenticación de datos realmente leídos.
Se implementaron en revisión técnica 2, sin cambiar la identidad económica.

La revisión técnica 3 permite reutilizar una corrida terminada con protocolo
técnico anterior autenticado, siempre que configuración, datos y código económico
coincidan. Se conservan protocolos v1/v2 y snapshots de cada runner. Una prueba
real retomó C02 condicional v1 desde v3 sin ejecutar nuevamente su trayectoria.
La prueba de dos procesos acredita la exclusión mutua del mismo par.

## Posprocesamiento y verificador

Hallazgos importantes reproducidos en copias en memoria del candidato parcial:

- Un envío posterior al fill podía pasar el auditor. Ahora se exige ventana
  `minute_window(submitted_at)`, identidad de activo/mercado/lado, ventana y
  tiempo del fill; el estado final es único y consistente con lo ejecutado.
- Una alteración del saldo o inventario en ledger no se enlazaba con cierres.
  Ahora se reconstruyen flujos de caja/deuda, inventario neto, P&L realizado y
  garantías, y se cotejan todos los cierres y estados persistidos. El buffer
  original de pérdida de apertura se conserva como dato persistido declarado.
- El posprocesamiento heredado exigía cobertura completa. Ahora una eventual
  interrupción conserva sólo el calendario observado, sus saldos y ND con
  motivo. Insolvencia que continúa observando todo el calendario se distingue
  de una interrupción y no requiere inventar `stopped_at`.

Hallazgos menores corregidos: estado `rejected` en resúmenes y mark ausente
como ND en tramos. No se encontraron errores de capacidad/denominadores en
las cinco carteras del primer candidato revisado: cantidades brutas, clave
por cartera/instrumento/minuto, VWAP y ponderación declarada eran consistentes.

Estas fallas de verificación no son evidencia de fallas económicas en las
corridas. No motivaron un cambio del motor ni una repetición de trayectorias.
La conciliación reforzada se ejecutó sobre siete carteras disponibles y pasó;
las puertas de cada etapa aplicarán los mismos controles al lote completo.

## Seguimiento

La segunda revisión confirmó las cascadas de caja, la ruta de insolvencia con
calendario completo y el cierre de los reproducer anteriores. Señaló además
que el permiso de estados pre/post no debía aplicarse a la última posición
efectiva de un instante: se corrigió, con fixture negativo y positivo y control
histórico posterior de nueve carteras. Los snapshots intermedios se conservan.
También se concilió el reloj de una eventual interrupción con `stopped_at` y
se rechazan eventos posteriores. La batería focalizada completa pasó 67 tests;
su conteo no se suma al de la regresión general.
# Revisión de consolidación tras la etapa de costos

## Compresión de evidencia, sin cambio económico

La revisión posterior del formato gzip detectó ambigüedad si coexistían CSV y
gzip y se validaba un archivo distinto del indicado por el catálogo. Se agregó
un fixture que falla antes de corregirlo: ahora se rechaza la coexistencia y el
catálogo descomprime exactamente su ruta declarada. El revisor confirmó lectura
compatible de los CSV de candidatos previos y ausencia de dependencia circular.

Pruebas actuales: 70 focalizadas y Ruff aprobados. Tres diagnósticos históricos
se comprimieron de 16.375.811 bytes a unos 905.000, con recuperación idéntica de
bytes, filas y SHA-256 original. Evidencia: `compresion_historica.json` y logs
RED/GREEN en `pruebas/`. La población H1 sigue siendo una sola cohorte BASE.

El revisor comprobó H2/H3, períodos, normalización por capital propio y la
población de capacidad. No ejecutó las once pruebas de corrupción pendientes
del paquete final y no las contó como pases.

Detectó una comparación impropia en la rama de insolvencia interrumpida:
los deltas heredados podían restar P&L parcial menos BASE de ventana completa.
Se agregó un control local al bloque 3: conserva ambos saldos observados,
pero el delta es ND con motivo `incomplete_comparable_window` si falta cobertura
o difieren las fronteras. Fixture RED/GREEN y cinco pruebas de cobertura/paquete
pasaron. Las ocho carteras de costos completas no cambian por esta corrección;
no se modificó código económico ni se repitieron sus replays.

También se corrigió una frase del resumen parcial que daba por evaluado capital
antes de incluir esas carteras. Los borradores parciales se conservan como
desarrollo; no se sellan ni se presentan como la matriz final.

## Revisión final de tramos y síntesis

El primer candidato completo pasó sus conciliaciones. El revisor detectó una
etiqueta errónea en tramos: «sin corto» con corto activo y mark faltante. La
corrección conserva ND en snapshots y agrega otra tabla calculada exclusivamente
con cantidades y marks de cierres diarios autenticados. Las transiciones son
ND si no existen pares evaluables; plano, mark ausente y días discontinuos
interrumpen la comparación. No se construye una serie de precios intradía.

La revisión independiente posterior confirmó esta corrección, las pruebas
nuevas de borde de tramo/mantenimiento/discontinuidades y la separación de
frecuencias en el reporte. También confirmó la interpretación de A100: H2
favorable por CAGR positivo y Sharpe superior, aunque su retorno sea menor
que el permanente. No encontró otro defecto concreto en esos cambios.

El revisor no repitió la suite ni editó archivos. La ejecución principal
acredita 72 pruebas focalizadas aprobadas y Ruff aprobado. Las pruebas negativas
del paquete sellado y su exportación offline se registran posteriormente en
archivos externos al sello, sin anticipar aquí su resultado.


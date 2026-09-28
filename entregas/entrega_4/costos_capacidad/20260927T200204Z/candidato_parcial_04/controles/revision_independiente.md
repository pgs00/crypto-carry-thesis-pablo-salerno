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

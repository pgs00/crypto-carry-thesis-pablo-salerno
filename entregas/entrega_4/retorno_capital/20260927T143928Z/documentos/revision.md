# Revisión y correcciones antes del sellado

Revisión independiente de sólo lectura realizada el 27/09/2026 sobre módulos,
pruebas y documentación. No ejecutó el motor ni modificó fuentes o Git.

Se detectaron dos debilidades, sin incidencia en los resultados históricos:

1. El verificador compacto podía aceptar ventanas, fracciones, conteos o
   referencias alteradas, e incluso la eliminación de un ciclo perdedor, si
   alguien renovaba los hashes. Se añadieron controles de población exacta,
   ventanas canónicas por fila, agregación desde evaluaciones, conteos de
   ciclos por período y referencias entre tablas. La modalidad completa ya
   detectaba esas alteraciones mediante recomputación desde las fuentes.
2. Un fill del mismo activo al instante de entrada requeriría dos fronteras
   contables distintas para no atribuir sus costos al estado anterior. Ninguna
   BASE presenta el caso; ambas usan next_minute_vwap. Se añadió una guardia
   explícita que rechaza esa entrada ambigua antes de reconstruir las cuentas.

La selección de regresión se ejecutó antes de las correcciones: **10 fallos
esperados y 16 pases, 42,46 s**. Este párrafo es un resumen de la ejecución,
no una transcripción de su stdout. Tras corregir: **173 pruebas pasaron**
(37 del bloque nuevo y 136 de exposición, H2 y verificador de la corrección).
Los comandos y stdout reales de la ejecución final se conservan en
`documentos/auditoria_previa/`; la auditoría del paquete ya sellado es externa.

La segunda lectura del revisor no dejó hallazgos importantes. Sus observaciones
documentales —nombre outside_dust y guardia de simultaneidad— fueron incorporadas.
El verificador también contrasta MD/HTML y datos de figuras con las tablas.
Las imágenes se sellan por hash; su legibilidad se revisa visualmente después
del armado y se registra en la auditoría externa.

La revisión del benchmark contrastó la propuesta con los originales públicos.
No implica aprobación del usuario ni cálculo de rendimiento remunerado.

# Revisión técnica de la entrega después del primer sello

El primer candidato sellado fue `paquete_20260930T012056Z`, con manifiesto
`955205887cf139bc41fd1edcdf9e63a482d0b498d8998680890cd6273ccc5603`.
Se preserva sin editar. Pasó el recálculo de los 14 resultados con fuentes
locales y un recálculo offline desde una copia en otra ruta.

Las adulteraciones detectaron un problema en el generador de pruebas: los
campos `delay_applied_seconds`, `fill_sequence` y `event_sequence` son texto
en el Parquet nativo. Asignarles enteros provocaba `ArrowTypeError` antes de
escribir la alteración y antes de invocar al verificador. La copia de demora
examinada seguía teniendo demora cero y el mismo sello; su aceptación offline
no era aceptación de una demora adulterada. El diagnóstico y sus logs se
conservan fuera del sello, en `verificacion_final/` de la carpeta de trabajo.

El generador corregido respeta los tipos físicos y comprueba que las filas
persistidas cambiaron. El ataque de vencimiento ordena numéricamente la
secuencia original antes de renumerar. Se repite la suite completa de 24
adulteraciones sobre la nueva versión; las expectativas del verificador no
se debilitan y no cambian el motor, los resultados ni su conciliación.

La exportación binaria encontró dos condiciones de Windows/Git. Primero,
algunas rutas superan el límite predeterminado de Git: se activa
`core.longpaths=true` sólo en el entorno del proceso, sin modificar configuración
global ni del repositorio. Segundo, los logs de diagnóstico contienen espacios
originales que Git señala: se agrega una excepción de whitespace acotada a
los `.txt` de la nueva evidencia. Sus bytes se preservan. Se retira solamente
una línea vacía terminal de la nota de revisión editable, en la nueva versión.
El prefijo original de `.gitattributes` y el índice real permanecen intactos.

La nueva versión enlaza el manifiesto del primer candidato y compara sus
miembros. Los datos de corridas, configuraciones, código económico, tablas,
figuras y extractos de fuentes deben conservar bytes idénticos. Sólo cambian
el generador de pruebas y los registros/documentos de esta revisión técnica.
No se repite ningún replay ni estudio histórico terminado.

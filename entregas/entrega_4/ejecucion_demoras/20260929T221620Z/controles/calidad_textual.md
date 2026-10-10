# Control de codificación y transcripción

Se identificó que `$OutputEncoding` de Windows PowerShell era `us-ascii`,
aunque la salida de consola era UTF-8. Una tubería con texto español hacia
Python sustituyó tildes por `?`. Las notas editables se corrigieron mediante escritura directa
UTF-8; no se alteró código económico ni resultados.

El único texto afectado que ya formaba parte del protocolo congelado era
`controles/aprobacion_reparacion.md`. Sus bytes y hash se preservan; su
transcripción legible, cotejada con la respuesta expresa del usuario, está en
`controles/aprobacion_reparacion_transcripcion_utf8.md`. El reporte principal
enlaza esa transcripción. Los candidatos preliminares temporales pueden
conservar notas anteriores a esta corrección; no son paquetes finales.

Los 57 logs UTF-16 creados por la redirección de PowerShell se convirtieron a
UTF-8 después de cerrar todos los procesos, conservando además los bytes
originales en archivos `.bin` y un mapa de hashes antes/después en
`normalizacion_logs_utf8.json`. No se modifica ningún
miembro de los paquetes anteriores. El control final comprueba decodificación,
enlaces e imágenes y registra por separado la revisión visual.

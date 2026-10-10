# Entrega verificada: bloque 4, ejecución y demoras

Estado: **ejecutado**. Finalizaron E_OHLC4, L01, L05, LC01, LC05 y LC15 para
las estrategias condicional y permanente, sin cruces de parámetros. Las doce
corridas nuevas tienen estado económico `complete`. Se reutilizan las dos
BASE originales y se conservan aparte dos controles BASE completos.

Lectura vigente: **distribucion_20261010**, con [identidad documental propia](distribucion_20261010/protocolo_distribucion.md).
Los controles y conteos siguientes corresponden al paquete original
`paquete_20260930T013915Z_v2`; no certifican por sí mismos esta distribución.
SHA-256 del manifiesto original:
`88af2936e2dc243080abdf3909cc578c184778527eb847d6b021ce76d357335b`.

- [Reporte Markdown](distribucion_20261010/reporte.md) y
  [reporte HTML](distribucion_20261010/reporte.html).
- [Lectura comparada de resultados](distribucion_20261010/lectura_resultados.md)
  y [síntesis integrable](distribucion_20261010/sintesis.md).
- [Corridas, identidades y comandos](distribucion_20261010/indice_corridas.json),
  [métricas de los ocho períodos](distribucion_20261010/tablas/metricas.csv),
  [auditoría de ejecución](distribucion_20261010/auditoria_ejecucion.md)
  y [casos locales](distribucion_20261010/incidentes.md).
- [Reproducción offline](distribucion_20261010/README.md) y
  [manifiesto completo](distribucion_20261010/manifiesto_paquete.json).
- [Matriz global actualizada](../../../../docs/entrega_4/matriz_avance.csv).

## Alcance comprobado

El paquete comprende 14 resultados, 23.856 cierres diarios, 112 períodos,
4.994 órdenes, 3.255 fills, 91 casos locales y 33.397 observaciones de esos
casos. Incluye 40 tablas CSV, 41 Parquet y 21 figuras, cada una en PNG y SVG.
Los 1.204 miembros sellados preservan la evidencia; manifiesto y sidecar son
dos archivos adicionales. No se generaron Word ni PDF.

La conciliación mantiene la tolerancia original de 1E-8 USDT. Se verifican
envío, generación, elegibilidad, ventana, vencimiento, cancelación y fill,
con nanosegundos y orden persistido. La demora se aplica a cada orden según
su propósito; `liquidate` recibe demora adicional cero. Funding, reservas,
garantías y controles de riesgo permanecen activos; los plazos preventivos
no se extienden. La reparación de prioridad aprobada por el usuario tiene
identidad propia y controles separados, con igualdad de once artefactos
completos por cartera respecto de las BASE preservadas.

La [verificación con fuentes completas](verificacion_final/fuentes_completas.json)
recalculó las 14 carteras desde los datos locales. La revisión técnica posterior
conserva idénticos todos los datos, configuraciones, tablas, figuras, extractos
y código económico, según la
[comparación entre versiones](distribucion_20261010/documentos/comparacion_con_candidato_anterior.json).
El [control offline del sello final](verificacion_final/offline_exportacion_v2.json)
repitió el recálculo desde una copia reconstruida de blobs Git, con herramientas
incluidas, desde otra ruta y sin acceder a las fuentes masivas.

## Pruebas y preservación

| Control | Resultado | Evidencia |
|---|---|---|
| Última regresión de fuente | 1.175 aprobadas | [Log](pruebas/regresion_final_fuente_02.txt) |
| Focalizadas vigentes del bloque | 110 aprobadas | [Log](pruebas/focalizadas_fuente_final_02.txt) |
| Paquetes históricos pertinentes | 24 pruebas distintas aprobadas: 18 iniciales y seis reintentadas | [Inicial](pruebas/paquetes_historicos_01.txt), [reintento](pruebas/paquetes_historicos_reintento.txt) |
| Adulteraciones reales del sello final | 24 aprobadas, cero omitidas | [Resumen y comandos](verificacion_final/adulteraciones_v2_resumen.json) |
| Ruff final, sin caché | Aprobado | [Log](verificacion_final/ruff_final.txt) |
| UTF-8, enlaces y formatos | Aprobado | [Control](verificacion_final/artefactos_finales_v2.json) |
| Exportación binaria con índice aislado | 1.207 blobs exactos, incluido `.gitattributes` | [Control](verificacion_final/preservacion_y_exportacion_v2.json) |
| Preservación después del cierre | Aprobada | [Control](verificacion_final/preservacion_despues_del_cierre.json) |
| Integridad de ambos sellos nuevos | Aprobada | [Control](verificacion_final/sellos_finales_intactos.json) |

Las suites solapadas no se suman. Los fallos iniciales permanecen documentados:
cachés accidentales de Ruff archivadas y retiradas sin alterar miembros previos;
errores del generador de ataques al escribir tipos Parquet, corregidos en la
versión final; y ajustes de rutas largas y whitespace de logs en Git. Los
detalles están en la
[revisión técnica](distribucion_20261010/documentos/revision_tecnica_paquete.md).
No se cambió la economía ni se repitieron replays por esa revisión de entrega.

Se conservaron siete paquetes sellados anteriores, las dos BASE originales y
las 1.731 identidades de entrada. Las comprobaciones cubren hashes e inventarios
de archivos. El índice real conserva SHA-256
`02c819872c5891bed1fde6bacc46ef56b100e562295bc8620c8d0ebab67cb99b`;
HEAD sigue en `d43d155c1a8f0444022b0226e75bcf5bd5dd926a`.
Son archivos preparados localmente: no hubo commit, push ni cambios en el
índice del usuario.

## Resultado y trabajo pendiente

OHLC4 cambia el P&L frente a BASE en +7,33/−22,63 USDT
(condicional/permanente). Las demoras modifican los reintentos, la exposición
sin cobertura y el capital usado, con resultados no monótonos. En L05, el
tiempo descubierto es 546/972 minutos, frente a 189/274 en BASE. El drawdown
diario más profundo entre las variantes es −0,8990% en LC15 condicional y
−1,1540% en LC01 permanente. No hubo fills de liquidación; la deuda máxima
en cierres diarios fue cero.

H2 resulta favorable sólo en L01 para la muestra completa. H1 y la oportunidad
de H3 permanecen invariantes; H3 conserva el resultado contrario en el
contraste temporal original. Las observaciones H1 se reutilizan una sola vez,
sin multiplicar cohortes. Los períodos anuales conservan sus propios resultados
y motivos ND.

El bloque 4 no tiene tareas pendientes dentro del alcance solicitado. En su
cierre original quedaban pendientes los bloques 5 y 6 y la revisión transversal;
el [índice actual de E4](../../README.md) enlaza esos resultados y el PDF final.
Este bloque no ejecutó shocks, escenario sin interrupción, nuevos cálculos SOFR ni
una reconstrucción intradía global. Los casos locales conservan sus límites
de cobertura y de precios de valoración; no acreditan ejecución durante una
suspensión ni un máximo de riesgo global.

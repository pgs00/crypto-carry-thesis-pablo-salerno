# Bloque 3: costos y capacidad

Lectura vigente: **`distribucion_20261010`**, con [identidad documental propia](distribucion_20261010/protocolo_distribucion.md).
Los controles y el sello citados abajo describen el paquete original
`paquete_20260927T231610Z`; no certifican por sí mismos la distribución nueva.
Se ejecutaron C02, C03, S02, S05, P050, P025, A050 y A100 en ambas estrategias:
16 trayectorias completas y dos BASE originales reutilizadas. No quedan
escenarios bloqueados o fallidos. Las variantes no se combinan ni adoptan
parámetros del bloque 2.

- [Reporte Markdown](distribucion_20261010/reporte.md) y [HTML](distribucion_20261010/reporte.html).
- [Síntesis integrable](distribucion_20261010/sintesis.md).
- [Tablas de ocho períodos](distribucion_20261010/tablas/metricas.csv) y [deltas](distribucion_20261010/tablas/deltas.csv).
- [Figura de costos](distribucion_20261010/figuras/costos.png), [participación](distribucion_20261010/figuras/participacion.png), [capital absoluto/normalizado](distribucion_20261010/figuras/capital.png) y [distribución del uso de cupo](distribucion_20261010/figuras/capacidad_distribucion.png); también SVG.
- [Auditoría de ejecución](distribucion_20261010/auditoria_ejecucion.md), [índice de corridas](distribucion_20261010/indice_corridas.json) y [casos extremos](distribucion_20261010/casos_extremos.md).
- [Protocolo](protocolo.md) y [compatibilidad anterior/nueva](control_compatibilidad.json).
- [Instrucciones del verificador portátil](distribucion_20261010/README.md), [manifiesto](distribucion_20261010/manifiesto_paquete.json) y [SHA-256](distribucion_20261010/manifiesto_paquete.sha256).
- [Matriz global vigente](../../../../docs/entrega_4/matriz_avance.csv).

El modo optativo `base_e3_total` separa selección y costos realizados: entrada
condicional estrictamente superior a 34 pb; renovación con forecast positivo.
Las doce comparaciones contra código previo congelado pasaron. Sizing, precios,
comisiones, inventario y garantías conservan los costos de cada escenario.

| Escenario | Retorno condicional | Retorno permanente |
| --- | ---: | ---: |
| BASE reutilizada | 7,8576% | 16,8007% |
| C02 | 6,3783% | 14,0495% |
| C03 | 5,0058% | 9,9984% |
| S02 | 7,7020% | 16,1843% |
| S05 | 7,1717% | 15,6722% |
| P050 | 7,7105% | 16,3871% |
| P025 | 6,1510% | 15,3055% |
| A050 | 6,1813% | 12,5623% |
| A100 | 4,8786% | 5,4635% |

Retornos acumulados de toda la muestra, no anuales. Con A100 aumenta el uso del
cupo y baja la utilización media del capital. H2 full sólo cambia a favorable
en A100 por CAGR positivo y Sharpe superior al de su permanente, aunque su
retorno sea menor. Hay nueve cambios H2 entre escenario/período, enumerados
en el reporte. H3 sigue contraria: oportunidad y CAGR condicional aumentan
entre los dos cortes. H1 conserva una sola cohorte BASE autenticada.

Los tramos calculados con cierres diarios se distinguen de los snapshots sin
mark, que permanecen ND. No se infieren máximos intradía ni escalabilidad
ilimitada; las reglas son prescritas y el cupo usa velas de un minuto.

## Controles históricos finales externos al sello original

- [Fuentes locales y conciliación consolidada](controles/verificacion_final_sin_sello_02.json): 18 carteras, 30.672 cierres, 144 períodos, 8.903 órdenes y 4.887 fills/claves. Se aplica a los mismos bytes económicos de la versión final, documentados en la [derivación de presentación](controles/derivacion_final.json).
- [Pruebas reales](pruebas/resumen_final.json): regresión 1.061 aprobadas; 72 focalizadas; once corrupciones con hashes renovados aprobadas en dos grupos disjuntos; Ruff aprobado. No sumar suites solapadas. De las 24 omisiones iniciales, once se ejecutaron sobre el sello final y trece corresponden al artefacto del bloque 2.
- [Preservación y exportación Git](controles/preservacion_exportacion_final_02.json): seis paquetes previos, dos BASE, 3.633 archivos anteriores y 1.731 identidades de datos controlados; 882 archivos exportados con bytes exactos e índice temporal aislado.
- [Verificación offline de esa exportación](controles/verificacion_offline_final_02.json): 880 miembros y todas las conciliaciones, sin datos masivos, con herramientas incluidas desde otra ruta. [Comando y entorno](controles/comando_offline_final.json).
- [Integridad posterior a las pruebas](controles/integridad_tras_pruebas.json), [QA de documentos y figuras](controles/qa_documentos_final_03.json) y [comandos del cierre](controles/comandos_cierre_v2.json).

Sello del paquete original:
`db68d839aa5837db72314b4f3de5509ecff283cc34d13a36e3c4f9d30298e1fb`.
Estas auditorías permanecen fuera del sello para conservarlo intacto.

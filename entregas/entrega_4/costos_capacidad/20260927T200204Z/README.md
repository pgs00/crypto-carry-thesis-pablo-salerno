# Bloque 3: costos y capacidad — entrega local terminada

Versión vigente: **`paquete_20260927T231610Z`**, sellada y verificada.
Se ejecutaron C02, C03, S02, S05, P050, P025, A050 y A100 en ambas estrategias:
16 trayectorias completas y dos BASE originales reutilizadas. No quedan
escenarios bloqueados o fallidos. Las variantes no se combinan ni adoptan
parámetros del bloque 2.

- [Reporte Markdown](paquete_20260927T231610Z/reporte.md) y [HTML](paquete_20260927T231610Z/reporte.html).
- [Síntesis integrable](paquete_20260927T231610Z/sintesis.md).
- [Tablas de ocho períodos](paquete_20260927T231610Z/tablas/metricas.csv) y [deltas](paquete_20260927T231610Z/tablas/deltas.csv).
- [Figura de costos](paquete_20260927T231610Z/figuras/costos.png), [participación](paquete_20260927T231610Z/figuras/participacion.png), [capital absoluto/normalizado](paquete_20260927T231610Z/figuras/capital.png) y [distribución del uso de cupo](paquete_20260927T231610Z/figuras/capacidad_distribucion.png); también SVG.
- [Auditoría de ejecución](paquete_20260927T231610Z/auditoria_ejecucion.md), [índice de corridas](paquete_20260927T231610Z/indice_corridas.json) y [casos extremos](paquete_20260927T231610Z/casos_extremos.md).
- [Protocolo previo](protocolo.md), [encargo íntegro](encargo_usuario.md) y [compatibilidad anterior/nueva](control_compatibilidad.json).
- [Instrucciones del verificador portátil](paquete_20260927T231610Z/README.md), [manifiesto](paquete_20260927T231610Z/manifiesto_paquete.json) y [SHA-256](paquete_20260927T231610Z/manifiesto_paquete.sha256).
- [Matriz global vigente](../../../../docs/entrega_4/matriz_avance.csv), [historial](../../../../docs/entrega_4/historial_avance/cambios.md), [plan cerrado](plan.md) y [registro completo](progreso.md).

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

## Controles finales externos al sello

- [Fuentes locales y conciliación consolidada](controles/verificacion_final_sin_sello_02.json): 18 carteras, 30.672 cierres, 144 períodos, 8.903 órdenes y 4.887 fills/claves. Se aplica a los mismos bytes económicos de la versión final, documentados en la [derivación de presentación](controles/derivacion_final.json).
- [Pruebas reales](pruebas/resumen_final.json): regresión 1.061 aprobadas; 72 focalizadas; once corrupciones con hashes renovados aprobadas en dos grupos disjuntos; Ruff aprobado. No sumar suites solapadas. De las 24 omisiones iniciales, once se ejecutaron sobre el sello final y trece corresponden al artefacto del bloque 2.
- [Preservación y exportación Git](controles/preservacion_exportacion_final_02.json): seis paquetes previos, dos BASE, 3.633 archivos anteriores y 1.731 identidades de datos controlados; 882 archivos exportados con bytes exactos e índice temporal aislado.
- [Verificación offline de esa exportación](controles/verificacion_offline_final_02.json): 880 miembros y todas las conciliaciones, sin datos masivos, con herramientas incluidas desde otra ruta. [Comando y entorno](controles/comando_offline_final.json).
- [Integridad posterior a las pruebas](controles/integridad_tras_pruebas.json), [QA de documentos y figuras](controles/qa_documentos_final_03.json) y [comandos del cierre](controles/comandos_cierre_v2.json).

Sello definitivo:
`db68d839aa5837db72314b4f3de5509ecff283cc34d13a36e3c4f9d30298e1fb`.
Estas auditorías permanecen fuera del sello para conservarlo intacto.

## Versiones de desarrollo conservadas

| Carpeta | Estado |
| --- | --- |
| `candidato_parcial_01` | Cinco carteras; detectó discrepancia de listas CSV |
| `candidato_parcial_02` | Construcción interrumpida por Decimal anidado |
| `candidato_parcial_03` | Siete carteras; verificación local y exportada aprobadas |
| `candidato_parcial_04` | Diez carteras; verificación aprobada |
| `paquete_20260927T225401Z` | Dieciocho carteras verificadas; sin sello, corregido diagnóstico de tramos después |
| `paquete_20260927T230722Z` | Sello previo conservado; controles financieros y once corrupciones aprobados, reemplazado por ajuste de presentación/exportación |
| `paquete_20260927T231610Z` | Versión final vigente; derivación documentada, verificada y exportada |

El bloque 3 está terminado localmente. Bloques 4–6 y revisión transversal
continúan pendientes. No se repitieron los análisis previos, no se generaron
Word/PDF y no hubo commit, push ni cambios del índice del usuario.

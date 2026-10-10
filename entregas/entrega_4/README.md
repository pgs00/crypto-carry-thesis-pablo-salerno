# Entrega 4: resultados y paquetes vigentes

**[PDF final de Entrega 4 (24 páginas)](documento_final/Tesina_Entregas_3_y_4_Pablo_Salerno.pdf)**.
La [matriz de resultados](../../docs/entrega_4/matriz_avance.csv) identifica los
paquetes vigentes y sus dependencias.

La lectura conjunta está en la [síntesis integrable B6][b6-sintesis]. Conserva
H1 por horizonte y activo, H2 por escenario/período con ND y excepciones,
y H3 con sus regímenes originales. BASE total mantiene H2 `no_favorable` y
dirección descriptiva H3 `contraria`; esas etiquetas no se extienden a todos
los años o variantes. Las cuentas nuevas B6 no son cortes heredados de BASE.
La síntesis conserva su estado histórico, cuando Word/PDF estaban pendientes;
el documento de presentación actual es el PDF final enlazado arriba.

## Paquetes vigentes

Cada fila enlaza el reporte, las tablas, el protocolo y la herramienta incluida
en su paquete. Riesgo y B1–B6 se presentan en distribuciones documentales del
10/10/2026, con identidad propia y evidencia científica conservada. Sus herramientas
y fuentes compactas permiten la comprobación descrita sin recuperar los prompts
retirados. Los certificados originales conservan su alcance histórico; no
certifican por sí mismos las nuevas distribuciones ni todo el motor.

| Bloque y versión vigente | Reporte / tablas | Protocolo | Verificador y alcance | Límites de lectura |
|---|---|---|---|---|
| BASE y reglas: padre `20260925T005436Z` + corrección `20260926T204312Z` | [Reporte corregido][base-reporte] · [Tablas][base-tablas] | [Reglas][base-protocolo] · [Métricas corregidas][base-metricas] | [V2][base-verificador], requiere el padre completo | [Guía][base-guia]: reglas prescritas; no cronología certificada del exchange. |
| Riesgo intradía: distribución `20261010` | [Reporte][riesgo-reporte] · [Tablas][riesgo-tablas] | [Protocolo][riesgo-protocolo] | [Verificador][riesgo-verificador], compacto o completo con series/precios locales | [Límites][riesgo-guia]: BASE/MARGEN_2X; el compacto no reconstruye máximos globales. |
| B1 capital: distribución `20261010` | [Reporte][capital-reporte] · [Tablas][capital-tablas] | [Protocolo][capital-protocolo] | [Verificador][capital-verificador], compacto o con cuatro dependencias | [Guía][capital-guia]: concentración descriptiva; la ficha SOFR pendiente es histórica. |
| B1 SOFR: distribución `20261010` | [Reporte][sofr-reporte] · [Tablas][sofr-tablas] | [Protocolo][sofr-protocolo] | [Verificador][sofr-verificador], cuenta y dependencia B1 capital | [Límites][sofr-limites]: hipotética bruta USD, ACT/360, paridad nominal; no caja carry. |
| B2 señal/entradas: distribución `20261010` | [Reporte][b2-reporte] · [Tablas][b2-tablas] | [Protocolo][b2-protocolo] | [Verificador][b2-verificador], evidencia compacta | [Guía][b2-guia]: seis variantes aisladas; MAE comparable sólo dentro del mismo horizonte. |
| B3 costos/capacidad: distribución `20261010` | [Reporte][b3-reporte] · [Tablas][b3-tablas] | [Protocolo][b3-protocolo] | [Verificador][b3-verificador], contabilidad y ventanas incluidas | [Guía][b3-guia]: ocho variantes aisladas, selección a 34 pb; capacidad 1m sin impacto/cola. |
| B4 ejecución/demoras: distribución `20261010` | [Reporte][b4-reporte] · [Tablas][b4-tablas] | [Protocolo][b4-protocolo] | [Verificador][b4-verificador], versión con prioridad de liquidación corregida | [Revisión v2][b4-limites]: seis variantes aisladas; LC global causal y ventanas intradía acotadas. |
| B5 estrés/contrafactual: distribución `20261010` | [Reporte][b5-reporte] · [Resultados][b5-tablas] | [Contrato ejecutado][b5-protocolo] · [Fórmulas][b5-formulas] | [Verificador][b5-verificador], controles, escenarios y testigos exportados | [Alcance][b5-limites]: recuperación impuesta y anclas fijas; no causalidad histórica identificada. |
| B6 estabilidad/incertidumbre: distribución `20261010` | [Reporte][b6-reporte] · [Tablas][b6-tablas] · [Síntesis][b6-sintesis] | [Ejecución][b6-protocolo] · [Bootstrap][b6-bootstrap] | [Verificador][b6-verificador], finanzas, estadística y síntesis compactas | [Guía][b6-guia]: inicios retrospectivos, intervalos marginales y supuestos por año. |

El [diagnóstico dirigido B2/B3][b6-diagnostico] excluye la precondición del
defecto de prioridad de liquidación en las 28 variantes autenticadas. Su
alcance se limita a esas corridas y esa rama; no prueba equivalencia universal
entre motores. La síntesis B6 autentica selectivamente las fuentes reutilizadas
y conserva el alcance de los controles históricos previos.

## Alcance de los resultados

Los documentos dentro de paquetes sellados conservan su fecha y alcance
originales; sus pendientes se interpretan junto con la matriz vigente.

El informe padre de reglas se lee con la corrección de exposición
y H2. [E3 continua](../entrega_3/continua_distribucion_20261010/README.md) conserva la referencia BASE;
las [ventanas independientes E3](../entrega_3/archivo/README.md) son históricas.

Las reglas históricas incompletas siguen siendo una limitación. La
[segunda tanda propuesta](../../docs/entrega_4/reglas_historicas/decisiones_integracion.md#segunda-tanda-propuesta--no-ejecutada)
permanece sin ejecutar. Las sensibilidades retrospectivas no constituyen
evidencia fuera de muestra.

La remuneración/reinversión de caja libre o garantías del carry permanece
fuera del estudio. El comparador SOFR es una cuenta hipotética separada.

## Dependencias y reproducción

La [guía única de reproducción](../../docs/reproduction.md) contiene los nueve
comandos de verificación vigentes, preparación del entorno y extracción autenticada
del ZIP continuo E3. El archivo histórico E3 se verifica desde su distribución.
BASE requiere el padre completo `reglas_historicas/20260925T005436Z`.
Riesgo compacto requiere padre y corrección BASE; B1 SOFR requiere B1 capital.
B1 capital puede autenticar además padre, corrección, riesgo y referencia E3
extraída. Las demás dependencias quedan incluidas en los paquetes de la tabla.
Ninguna copia de desarrollo archivada sustituye esas versiones.

La comparación literal del CSV B6 tiene un antecedente de fallo integral en
Linux: diferencia máxima `6.938893903907228e-18`, con controles numéricos
aprobados en aquella comprobación. Windows es el entorno de referencia.

[base-reporte]: reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/comparacion/reporte.md
[base-tablas]: reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/comparacion
[base-protocolo]: reglas_historicas/20260925T005436Z/documentos/protocolo.md
[base-metricas]: reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/documentos/guia_metricas.md
[base-verificador]: reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/herramientas/verify_rules_sensitivity_correction.py
[base-guia]: reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/README.md
[riesgo-reporte]: riesgo_intradia/20260926T214118Z/distribucion_20261010/reporte.md
[riesgo-tablas]: riesgo_intradia/20260926T214118Z/distribucion_20261010/tablas
[riesgo-protocolo]: riesgo_intradia/20260926T214118Z/distribucion_20261010/documentos/protocolo.md
[riesgo-verificador]: riesgo_intradia/20260926T214118Z/distribucion_20261010/herramientas/scripts/verify_intraday_risk.py
[riesgo-guia]: riesgo_intradia/20260926T214118Z/distribucion_20261010/README.md
[capital-reporte]: retorno_capital/20260927T143928Z/distribucion_20261010/reporte.md
[capital-tablas]: retorno_capital/20260927T143928Z/distribucion_20261010/tablas
[capital-protocolo]: retorno_capital/20260927T143928Z/distribucion_20261010/documentos/protocolo.md
[capital-verificador]: retorno_capital/20260927T143928Z/distribucion_20261010/herramientas/scripts/verify_return_capital.py
[capital-guia]: retorno_capital/20260927T143928Z/distribucion_20261010/README.md
[sofr-reporte]: retorno_capital/20260927T154653Z_sofr/distribucion_20261010/reporte.md
[sofr-tablas]: retorno_capital/20260927T154653Z_sofr/distribucion_20261010/tablas
[sofr-protocolo]: retorno_capital/20260927T154653Z_sofr/distribucion_20261010/documentos/protocolo.md
[sofr-verificador]: retorno_capital/20260927T154653Z_sofr/distribucion_20261010/herramientas/scripts/verify_sofr_benchmark.py
[sofr-limites]: retorno_capital/20260927T154653Z_sofr/distribucion_20261010/documentos/limites_verificacion.md
[b2-reporte]: senal_entradas/20260927T170230Z/distribucion_20261010/reporte.md
[b2-tablas]: senal_entradas/20260927T170230Z/distribucion_20261010/tablas
[b2-protocolo]: senal_entradas/20260927T170230Z/distribucion_20261010/documentos/protocolo.md
[b2-verificador]: senal_entradas/20260927T170230Z/distribucion_20261010/herramientas/scripts/verify_signal_sensitivity.py
[b2-guia]: senal_entradas/20260927T170230Z/distribucion_20261010/README.md
[b3-reporte]: costos_capacidad/20260927T200204Z/distribucion_20261010/reporte.md
[b3-tablas]: costos_capacidad/20260927T200204Z/distribucion_20261010/tablas
[b3-protocolo]: costos_capacidad/20260927T200204Z/distribucion_20261010/documentos/protocolo.md
[b3-verificador]: costos_capacidad/20260927T200204Z/distribucion_20261010/herramientas/scripts/verify_cost_capacity.py
[b3-guia]: costos_capacidad/20260927T200204Z/distribucion_20261010/README.md
[b4-reporte]: ejecucion_demoras/20260929T221620Z/distribucion_20261010/reporte.md
[b4-tablas]: ejecucion_demoras/20260929T221620Z/distribucion_20261010/tablas
[b4-protocolo]: ejecucion_demoras/20260929T221620Z/distribucion_20261010/documentos/protocolo.md
[b4-verificador]: ejecucion_demoras/20260929T221620Z/distribucion_20261010/herramientas/scripts/verify_execution_delays.py
[b4-limites]: ejecucion_demoras/20260929T221620Z/distribucion_20261010/documentos/revision_tecnica_paquete.md
[b5-reporte]: estres_contrafactual/20260930T214617Z/distribucion_20261010/reporte.md
[b5-tablas]: estres_contrafactual/20260930T214617Z/distribucion_20261010/resultados
[b5-protocolo]: estres_contrafactual/20260930T214617Z/distribucion_20261010/protocolo_ejecucion.json
[b5-formulas]: estres_contrafactual/20260930T214617Z/distribucion_20261010/protocolo_tecnico.md
[b5-verificador]: estres_contrafactual/20260930T214617Z/distribucion_20261010/herramientas/scripts/verify_stress_counterfactual.py
[b5-limites]: estres_contrafactual/20260930T214617Z/distribucion_20261010/reproducibilidad.md
[b6-reporte]: estabilidad_incertidumbre/20261001T215423Z/distribucion_20261010/reporte.md
[b6-tablas]: estabilidad_incertidumbre/20261001T215423Z/distribucion_20261010/tablas
[b6-sintesis]: estabilidad_incertidumbre/20261001T215423Z/distribucion_20261010/sintesis.md
[b6-protocolo]: estabilidad_incertidumbre/20261001T215423Z/distribucion_20261010/protocolo_ejecucion.json
[b6-bootstrap]: estabilidad_incertidumbre/20261001T215423Z/distribucion_20261010/estadistica/protocolo.json
[b6-verificador]: estabilidad_incertidumbre/20261001T215423Z/distribucion_20261010/herramientas/scripts/verify_stability_uncertainty.py
[b6-guia]: estabilidad_incertidumbre/20261001T215423Z/distribucion_20261010/README.md
[b6-diagnostico]: estabilidad_incertidumbre/20261001T215423Z/distribucion_20261010/tablas/diagnostico_b2_b3_corridas.csv

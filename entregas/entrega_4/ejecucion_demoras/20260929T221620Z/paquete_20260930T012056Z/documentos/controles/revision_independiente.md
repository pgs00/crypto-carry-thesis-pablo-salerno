# Revisión del motor y auditor de ejecución

Revisión independiente de código por subagente, requerida por el flujo de revisión
de desarrollo. Se realizó en lectura, con reproducciones pequeñas en memoria;
no hizo nuevos replays históricos ni escribió sobre las referencias.

El primer hallazgo económico preexistente fue la prioridad de reintentos tras
escalar a liquidación. La propuesta, aprobación del usuario y controles propios
se conservan en esta carpeta. El motor valida OHLC antes de ejecutar un fill.
La revisión posterior no identificó otro defecto en la reparación aplicada.

Hallazgos del auditor y respuesta:

| Hallazgo reproducido | Control incorporado | Pruebas |
|---|---|---|
| Cancelación seguida de fill; eventos eliminados | Ciclo submitted/eventos/final y enlace uno a uno con fills | auditoria_cruzada_red / green |
| Expiración contra la antigua ventana | Timeout exactamente en deadline de la ventana elegible | test_old_window_expiration_is_rejected |
| Propósito incompatible con mercado, lado o cargo | Clasificación explícita y flag de liquidación | test_cross_record_mutations_rejected |
| Propósito plausible pero contrario a la causa | Transiciones vigentes y eventos de entrada/fallo enlazados | test_same_market_purpose_must_match_original_causal_transition |
| Secuencias simultáneas renumeradas | Orden relativo cruzado con ledger y eventos de fill | test_renumbering_fills_cannot_change_original_ledger_order |
| Timestamps de fill/cancelación arbitrarios | Comparación por etapa del ciclo y contra el envío original | test_cross_record_mutations_rejected |
| Pendiente posterior al vencimiento o snapshot anterior al envío | Frontera del snapshot final y ventana aún futura si sigue pendiente | auditoria_final_pendiente_red / green |
| Cobertura de reducción sin fill tras liquidación | Fixture nativo específico | test_zero_fill_reduction_cannot_restore_holding_after_liquidation |
| Funding simultáneo omitido antes del cierre local | Corte por índice del ledger antes del fill pertinente, conservando POST intermedios | incidentes_fronteras_RED / GREEN |
| Movimiento de otro activo absorbido en el equity inicial local | Corte después del movimiento inicial del activo, sin eliminar los posteriores simultáneos | incidentes_fronteras_RED / GREEN |
| Precio disponible en final exclusivo usado por un caso censurado | Última observación en final−1 ns, sin cambiar duración original | incidentes_terminal_RED / GREEN |
| Frontera de polvo sin fill y ventana calendario | Políticas explícitas separadas, verificadas con fixtures | test_state_only_end_keeps_pre_timestamp_and_identifies_missing_movement; test_calendar_case_includes_pre_and_all_post_states_at_both_boundaries |
| Duplicación de una estrategia en controles BASE | Población exacta conditional/permanent y enlace con estados de ejecución | anclas_originales_RED / GREEN |
| Manifiesto BASE sustituido con índice renovado | SHA y run_id contra autenticación original congelada | anclas_originales_RED / GREEN |
| Comparación de controles insensible al orden de filas | Digest ordenado, once artefactos y nueva comprobación completa sin replay | orden_catalogo_RED / GREEN; compatibilidad_base_orden_persistido |
| Catálogo de transferencias incompleto o mal rotulado | Población exacta por corrida/archivo, ruta y convención de copia | orden_catalogo_RED / GREEN |

Las pruebas focalizadas pasaron después de las correcciones. El auditor también
validó ambas BASE originales: 258/735 órdenes y 138/332 fills, respectivamente,
sin usar redondeos ni alterar registros. El motor económico permaneció congelado
durante las mejoras del auditor. Los controles del paquete final y su dictamen
se registran fuera del sello con el hash exacto de la versión comprobada.

La prueba preliminar offline del constructor encontró además que Arrow infería
las columnas del extracto local desde la primera fila (mark), omitiendo el volumen
spot posterior. Se corrigió el exportador para conservar la unión de columnas,
con fixture RED/GREEN y posterior repetición del verificador. No afecta al motor
ni requiere replay de las variantes.

Límite: el verificador comparte funciones de posprocesamiento con el constructor.
Cruzar evidencias y rechazar adulteraciones concretas no equivale a demostrar
una implementación independiente de todo el motor ni impedir una falsificación
coordinada de absolutamente todas las fuentes y sus identidades de confianza.
# Cierre adicional de revisión: integridad de H1 reutilizada

2026-09-30 00:52 UTC. La lectura final de verificador, reporte y documentación
detectó que se autenticaban sólo los archivos presentes de `hipotesis_base`.
Faltaba exigir la población completa del manifiesto original del bloque 2.
Se agregó esa igualdad de conjuntos antes de interpretar resultados, se
obtiene el contador H1 del archivo autenticado y se prueban la ausencia de
observaciones o resumen. Nueve pruebas de integridad aprobadas; se incorpora
además `h1_missing` a las adulteraciones reales del paquete final (24 casos).
No se recalcula H1 ni cambia el motor, el protocolo o las corridas.

La revisión final no encontró otros defectos materiales en los tres archivos
examinados. El verificador y el constructor comparten lógica, como se declara.


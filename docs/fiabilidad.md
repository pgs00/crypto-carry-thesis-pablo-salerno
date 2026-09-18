# Fiabilidad y condiciones para interpretar los resultados

Requisito del usuario, 18/09/2026: el backtest debe ser lo más fiable posible porque podría servir para evaluar una futura prueba con capital propio. Este documento fija criterios de trabajo y pendientes; no acredita que se hayan cumplido ni amplía el proyecto a un bot de trading real.

## Criterio de aceptación histórico

La rentabilidad no decide si una corrida es válida. La evidencia de datos, el modelo temporal y la conciliación contable se revisan antes de interpretar el resultado. Un resultado negativo también debe conservarse y explicarse.

| Control | Evidencia exigida | Situación al 18/09/2026 |
| --- | --- | --- |
| Procedencia y cobertura | Archivos originales, hashes, períodos y faltantes identificados; discrepancias resueltas con evidencia. | Muestra auditada; descarga completa y validación pendientes. |
| Reglas históricas | Tarifas, filtros, margen, liquidación y operatividad con vigencia y disponibilidad temporal verificadas. | Investigación parcial; registro ejecutable aún vacío. |
| Funding realizado | Tasa, timestamp y mark de cobro acreditados para cada evento necesario. | Faltan 2.005 marks por activo dentro del período económico consultado. |
| Información disponible al decidir | Ninguna decisión utiliza datos futuros; funding para señales y mark cerrado tienen su demora documentada. | Implementado y cubierto por pruebas; revisar también los nuevos datos y reglas al incorporarlos. |
| Contabilidad y posiciones | Equity conciliado con P&L, funding, comisiones, deuda y posiciones nativas; movimientos aplicados una sola vez. | Implementado y probado con escenarios controlados; falta la corrida histórica completa. |
| Reproducibilidad | Mismos inputs, reglas, configuración y código reproducen resultados; reanudación conserva exposición y eventos. | Pruebas y demo documentadas; no sustituyen evidencia económica histórica. |
| Robustez | Publicar todos los escenarios predefinidos y sus faltantes, pérdidas, drawdowns y costos. | Infraestructura implementada; evaluación económica pendiente del baseline válido. |

El detalle de pruebas y corridas está en [avance](progress.md), y la evidencia histórica en [investigación](research/README.md). Los tests comprueban casos del software; su cantidad no estima una probabilidad de éxito económico ni prueba ausencia de errores.

Los controles estrictos continúan bloqueando resultados completos cuando falta evidencia necesaria. No se aprueba un hueco porque sea pequeño o porque resolverlo perjudique la rentabilidad. Un checksum prueba integridad del archivo; conciliar dos productos del mismo proveedor no descarta una omisión compartida.

## Límites del modelo que afectan una futura operación

El baseline conserva las reglas de la [especificación](sources/Prompt_Codex_Backtesting.md) y la [metodología](methodology.md). Cambiar su economía requiere documentar el cambio y conservar una comparación reproducible.

- **Ejecuciones completas:** cada orden se llena al primer trade posterior elegible, independientemente de su volumen. No se reconstruyen spread, profundidad, colas ni ejecuciones parciales. El slippage fijo es un supuesto, no una medición de capacidad. La participación en volumen es un diagnóstico y no prueba que una orden pudiera ejecutarse.
- **Riesgo al cierre de minuto:** el mark cerrado puede omitir movimientos intraminuto capaces de afectar margen o liquidación. No observar una liquidación con esta frecuencia no demuestra que no hubiera ocurrido con observación más fina.
- **Latencia y fallos operativos:** demora entre patas, caducidad y reintentos se simulan con reglas explícitas. Todavía no están calibrados contra comunicaciones, rechazos, desconexiones y respuestas reales del exchange.
- **Alcance económico:** USDT a la par, transferencias instantáneas y gratuitas, sin insolvencia del exchange, ADL, liquidaciones parciales ni impuestos. Esos supuestos impiden interpretar el equity simulado como una estimación exhaustiva de pérdidas posibles.

La NFA identifica retrospectividad, liquidez y slippage como limitaciones de resultados hipotéticos. Se usa esa observación metodológica como referencia; no se presenta este documento como una evaluación jurídica de sus reglas. [NFA, nota interpretativa 9025](https://www.nfa.futures.org/rulebooksql/rules.aspx?RuleID=9025&Section=9).

## Validación adicional antes de considerar capital propio

Estos pasos son requisitos pendientes de trabajo, no funciones ya desarrolladas ni una autorización para operar:

1. **Cerrar la evidencia histórica.** Resolver reglas, marks y cobertura; revisar las primeras operaciones, cobros, cierres y episodios de estrés contra cálculos independientes. Un supuesto aprobado se etiqueta como supuesto y no se convierte en dato verificado.
2. **Medir sensibilidad sin seleccionar sólo ganadores.** Conservar el baseline y todos los escenarios de costos, slippage y demoras, incluidos los desfavorables. Informar concentración por activo/período y los casos que revierten la conclusión. Las ventanas de funding solapadas no se cuentan como observaciones independientes.
3. **Evaluar datos no usados para ajustar.** Fijar versión, parámetros y criterios antes de observar ese resultado. Reetiquetar una parte ya examinada como “fuera de muestra” no elimina el sesgo. Si se ajusta con ella, hace falta una nueva validación independiente. Esta extensión no cambia retrospectivamente el período de la tesina.
4. **Simular en vivo sin enviar órdenes.** Registrar señales, cotizaciones y cantidades disponibles, tiempos de recepción, funding y fallos. Comparar las ejecuciones hipotéticas con esas observaciones y medir las discrepancias del modelo. La simulación sigue sin probar fills reales, impacto propio ni ejecución garantizada.
5. **Revisar la preparación operativa por separado.** Antes de cualquier prueba real hacen falta límites de pérdida/exposición definidos de antemano, tratamiento de fills parciales, reconciliación con el exchange y parada controlada. Su implementación y una eventual operación con capital son una etapa futura, con decisión expresa del usuario.

No se fija ahora un capital de prueba, una duración arbitraria, un drawdown aceptable ni un umbral de Sharpe que habilite operar. Esos criterios se definirán antes de observar el resultado de la etapa correspondiente, con información sobre tolerancia a pérdidas y evidencia de ejecución. Un backtest rentable por sí solo no satisface estas condiciones.

## Verificación de esta revisión

Se contrastó este documento con `execution.py`, `strategy.py`, `robustness.py`, la validación de datos, las pruebas de temporización/contabilidad/checkpoints y la especificación aprobada. El registro de 107 pruebas del turno anterior permanece en `progress.md`; no se lo presenta como una nueva corrida ni como una validación del mercado. Esta revisión modifica documentación, sin cambiar el motor, los parámetros ni los archivos de la descarga activa.

# Fiabilidad y condiciones para interpretar los resultados

Requisito del usuario, 18/09/2026: el backtest debe ser lo más fiable posible porque podría servir para evaluar una futura prueba con capital propio. Este documento distingue los controles ejecutados y los límites del estudio con supuestos aprobados. El alcance sigue siendo un backtest, sin órdenes reales.

## Criterio de aceptación histórico

La revisión del 19/09/2026 introduce `next_minute_vwap`, capacidad simulada del
1%, parciales y sizing conjunto. Sus pruebas y corridas se registran en
[avance](progress.md); la tabla fechada abajo conserva la evidencia del baseline
anterior. No se reutiliza la auditoría de trades como validación del nuevo modelo.

La rentabilidad no decide si una corrida es válida. La evidencia de datos, el modelo temporal y la conciliación contable se revisan antes de interpretar el resultado. Un resultado negativo también debe conservarse y explicarse.

| Control | Evidencia exigida | Situación al 18/09/2026 |
| --- | --- | --- |
| Procedencia y cobertura | Archivos originales, hashes, períodos y faltantes identificados; discrepancias resueltas con evidencia. | Ambas ventanas por minuto validadas; seis diarios oficiales completan marks y la suspensión spot queda documentada. Las reglas siguen siendo supuestos. |
| Reglas históricas | Tarifas, filtros, margen, liquidación y operatividad con vigencia y disponibilidad temporal verificadas. | La reconstrucción exacta continúa incompleta. Las dos ventanas usan reglas prescritas aprobadas, exportadas con cada corrida. |
| Funding realizado | Tasa, timestamp y mark de cobro acreditados para cada evento necesario. | En 2022–2023 se aplicaron 2.190 proxies causales; en 2025–2026, 2.190 marks exactos. Son conteos de eventos de ambos activos; cada cartera los procesa por separado. El calentamiento se informa aparte. |
| Información disponible al decidir | Ninguna decisión utiliza datos futuros; funding para señales y mark cerrado tienen su demora documentada. | Precios y volumen cerrado se publican por separado; pruebas de señales, cobros, órdenes y checkpoints aprobadas. Las aperturas al inicio del minuto siguen siendo una convención del modelo. |
| Contabilidad y posiciones | Equity conciliado con P&L, funding, comisiones, deuda y posiciones nativas; movimientos aplicados una sola vez. | Auditoría independiente de las cuatro carteras: 106 fills y posiciones conciliados; equity final reconstruido exactamente. Máximo residuo de caja 2,413 × 10⁻²⁴ USDT, dentro de 10⁻⁸. |
| Reproducibilidad | Mismos inputs, reglas, configuración y código reproducen resultados; reanudación conserva exposición y eventos. | Dos baselines inmutables con 43 artefactos verificados cada uno; hashes de fuentes y código, parámetros y pruebas de reanudación conservados. |
| Robustez | Publicar los escenarios evaluados y sus faltantes, pérdidas, drawdowns y costos. | Los siete escenarios priorizados terminaron para ambas ventanas; índices y corridas verificados. Las demás dimensiones del motor están identificadas como no ejecutadas en este conjunto. |

El detalle de pruebas y corridas está en [avance](progress.md), y la evidencia histórica en [investigación](research/README.md). Los tests comprueban casos del software; su cantidad no estima una probabilidad de éxito económico ni prueba ausencia de errores.

Los controles estrictos continúan bloqueando resultados completos cuando falta evidencia necesaria. No se aprueba un hueco porque sea pequeño o porque resolverlo perjudique la rentabilidad. Un checksum prueba integridad del archivo; conciliar dos productos del mismo proveedor no descarta una omisión compartida.

## Límites del modelo que afectan una futura operación

El baseline sigue la [especificación](sources/Prompt_Codex_Backtesting.md) con las modificaciones de alcance, reglas y ejecución aprobadas en el [protocolo vigente](escenario_investigacion.md). Cambiar su economía requiere documentar el cambio y conservar una comparación reproducible.

- **Ejecución agregada:** el modelo vigente usa el VWAP del minuto elegible y una capacidad simulada del 1%, con parciales y expiración. No reconstruye spread, profundidad ni colas. Tanto la participación como el slippage fijo son supuestos, no evidencia de liquidez accesible. El modelo `minute_open` con fills completos se conserva sólo como referencia.
- **Riesgo al cierre de minuto:** el mark cerrado puede omitir movimientos intraminuto capaces de afectar margen o liquidación. No observar una liquidación con esta frecuencia no demuestra que no hubiera ocurrido con observación más fina.
- **Latencia y fallos operativos:** demora entre patas, caducidad y reintentos se simulan con reglas explícitas. Todavía no están calibrados contra comunicaciones, rechazos, desconexiones y respuestas reales del exchange.
- **Alcance económico:** USDT a la par, transferencias instantáneas y gratuitas, sin insolvencia del exchange, ADL, liquidaciones parciales ni impuestos. Esos supuestos impiden interpretar el equity simulado como una estimación exhaustiva de pérdidas posibles.

La NFA identifica retrospectividad, liquidez y slippage como limitaciones de resultados hipotéticos. Se usa esa observación metodológica como referencia; no se presenta este documento como una evaluación jurídica de sus reglas. [NFA, nota interpretativa 9025](https://www.nfa.futures.org/rulebooksql/rules.aspx?RuleID=9025&Section=9).

## Validación adicional antes de considerar capital propio

Estos pasos son requisitos pendientes de trabajo, no funciones ya desarrolladas ni una autorización para operar:

1. **Ampliar la evidencia histórica y de ejecución.** La cobertura de las ventanas y la reconstrucción independiente de sus operaciones ya están verificadas. Aún faltan las reglas históricas exactas, los marks sustituidos por proxies y evidencia de ejecución más fina para validar los supuestos. Un supuesto aprobado se etiqueta como supuesto y no se convierte en dato verificado.
2. **Medir sensibilidad sin seleccionar sólo ganadores.** Conservar el baseline y todos los escenarios de costos, slippage y demoras, incluidos los desfavorables. Informar concentración por activo/período y los casos que revierten la conclusión. Las ventanas de funding solapadas no se cuentan como observaciones independientes.
3. **Evaluar datos no usados para ajustar.** Fijar versión, parámetros y criterios antes de observar ese resultado. Reetiquetar una parte ya examinada como “fuera de muestra” no elimina el sesgo. Si se ajusta con ella, hace falta una nueva validación independiente. Esta extensión no cambia retrospectivamente el período de la tesina.
4. **Simular en vivo sin enviar órdenes.** Registrar señales, cotizaciones y cantidades disponibles, tiempos de recepción, funding y fallos. Comparar las ejecuciones hipotéticas con esas observaciones y medir las discrepancias del modelo. La simulación sigue sin probar fills reales, impacto propio ni ejecución garantizada.
5. **Revisar la preparación operativa por separado.** Antes de cualquier prueba real hacen falta límites de pérdida/exposición definidos de antemano, tratamiento de fills parciales, reconciliación con el exchange y parada controlada. Su implementación y una eventual operación con capital son una etapa futura, con decisión expresa del usuario.

No se fija ahora un capital de prueba, una duración arbitraria, un drawdown aceptable ni un umbral de Sharpe que habilite operar. Esos criterios se definirán antes de observar el resultado de la etapa correspondiente, con información sobre tolerancia a pérdidas y evidencia de ejecución. Un backtest rentable por sí solo no satisface estas condiciones.

## Verificación de esta revisión

Se contrastó este documento con el motor, los artefactos anuales y el protocolo aprobado. La suite vigente pasó 302 pruebas; la [auditoría financiera independiente](../data/research/minute-download-20260918/annual-economic-audit.json) reproduce la economía sin importar el ledger ni sus funciones de costos. Estos controles respaldan la consistencia del estudio declarado, no la precisión de sus supuestos frente a una operación real.

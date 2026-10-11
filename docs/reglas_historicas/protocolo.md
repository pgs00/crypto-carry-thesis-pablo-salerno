# Sensibilidad de reglas: protocolo de los seis escenarios

Este protocolo fija la sensibilidad de reglas antes de observar sus resultados. Conserva la referencia continua y sus parámetros; las variantes no se seleccionan por rentabilidad. Los resultados y la corrección de exposición/H2 se presentan en la [lectura de BASE](../../results/base/README.md).

## Secuencia de validación

1. Verificar la integridad y procedencia fuera del paquete sellado. El verificador original y sus resultados conservan su alcance histórico.
2. Completar la matriz de integración, separar observaciones, vigencias verificadas y supuestos, y verificar código, configuración, datos y resultados BASE_E3.
3. Probar la extensión con casos pequeños y con una reproducción acotada de la base antes/después. Ejecutar después las cinco variantes, con dos carteras independientes cada una. Reutilizar la base completa sólo tras verificarla.
4. Conciliar resultados, H1/H2/H3 y exposición a reglas parciales. Verificar el paquete nuevo, la publicación original, la referencia continua y la suite completa.

Las configuraciones y los resultados anteriores se conservan. El inventario previo está en `data/evidence/reglas_historicas/estado_inicial.json`. Los originales externos se autentican mediante hashes completos; cada reproducción escribe en una carpeta nueva.

## Base y comparadores fijados

Ventana continua `[2022-01-01T00:00:00Z, 2026-09-01T00:00:00Z)`. Capital inicial 10.000 USDT en cada cartera independiente; conditional y permanent no comparten efectivo ni posiciones. Se conserva íntegra la configuración efectiva de `run_ad71d751b20623006c195ff3` y `run_dfea4b7ac1475668d5968c97`: señales de minuto cerrado, next_minute_vwap, 1% del volumen agregado, parciales, joint_quantity, Decimal, horizonte y tenencia 168 h, ventana 336 h, semivida 24 h, margen aislado y apalancamiento inicial 2x. Se conserva la capa futures_scaled y sus limitaciones documentadas de marks/funding.

| Variante | Comisión realizada | Comisión usada para decisión | Comparador causal |
| --- | --- | --- | --- |
| BASE_E3 | Spot 0,001; futuros 0,0005 | Entrada 0,0034; renovación 0 | Base archivada verificada |
| BTC_PROMO_REALIZADA | Sólo BTC spot 0 dentro del intervalo documentado; 0,001 fuera | Entrada 0,0034; renovación 0 | BASE_E3 |
| BTC_PROMO_DECISION | Igual a BTC_PROMO_REALIZADA | 2×spot vigente + 2×futuros vigente + 4×slippage: BTC 0,0014 durante promoción, 0,0034 fuera; ETH 0,0034 | BTC_PROMO_REALIZADA |
| FUT4_REALIZADA | Futuros BTC y ETH 0,0004 toda la muestra; spot 0,001 | Entrada 0,0034; renovación 0 | BASE_E3 |
| FUT4_DECISION | Igual a FUT4_REALIZADA | Entrada 0,0032; renovación 0 | FUT4_REALIZADA |
| MARGEN_2X | Igual a BASE_E3 | Igual a BASE_E3 | BASE_E3 |

MARGEN_2X duplica coherentemente la tasa de mantenimiento y la deducción en cada tramo. Conserva pisos, techos, apalancamiento inicial 2x, comisiones y umbrales de salida. Los factores se evalúan por separado; las sensibilidades adicionales de reglas quedan fuera del alcance ejecutado.

## Evidencia, supuestos y reloj

`BTC_SPOT_ZERO`, fuentes `PROMO_START`/`PROMO_END`, respalda `[2022-07-08T14:00:00Z, 2023-03-22T00:00:00Z)`. El 0,001 fuera de ese intervalo es el supuesto BASE_E3, no una cronología demostrada. `known_from_utc` permanece nulo en la investigación. Para BTC_PROMO_DECISION se adopta explícitamente conocimiento al inicio efectivo; las decisiones consultan sólo la tarifa vigente en ese instante, sin anticipar el fin de la promoción ni la tarifa futura de salida. La fórmula es un estimador contemporáneo, no una previsión perfecta de costos realizados.

Las observaciones de futuros 0,0004 y 0,0005 no identifican una transición efectiva ni certifican vigencia entre capturas. FUT4 es un contrafactual constante en toda la muestra. Las tablas de filtros y mantenimiento son puntos o eventos documentados, sin rellenar huecos ni convertirlos en un RuleBook histórico completo.

Los cambios de la promoción son fronteras exactas de minuto. Para ejecuciones next_minute_vwap, la tarifa corresponde al comienzo de la ventana completa `[window_start, window_end)` y el movimiento contable sigue ocurriendo al cierre, después de conocer precio y volumen. Así una ventana que termina justo al comenzar la promoción paga la tarifa anterior; una que termina justo al finalizarla conserva la tarifa promocional. No se distribuye volumen dentro del minuto ni se inventa el instante de trades individuales. El reloj de decisión es el instante actual, distinto del de la ventana de ejecución.

Compras spot descuentan comisión en unidades base; ventas spot y futuros pagan USDT. Los fees nativos siguen en cero. Slippage permanece incorporado al precio y se informa, sin restarlo otra vez. Funding se liquida antes de fills de la misma frontera.

## Extensión y controles

Dos controles opt-in: calendario de comisión BTC spot y elección de tarifas para el costo de decisión. Los valores por defecto conservan comportamiento y serialización de configuraciones previas. Las reglas estrictas y su validación de cobertura no se relajan. La salida del escritor de corridas admite un destino explícito nuevo sin alterar la raíz de lectura de datos.

Pruebas antes de implementación: porcentajes/bps y tasa cero; costo realizado independiente del de decisión; activos y fronteras de promoción; ausencia de anticipación; neto spot, comisiones únicas y conciliación nativa; funding antes de fills; margen y deducciones duplicados incluyendo fronteras; extensión apagada equivalente. Se registran los fallos iniciales pertinentes, los pases focalizados, pytest completo y Ruff. No se modifican pruebas para ocultar cambios económicos.

## Ejecución y criterios de éxito

Se verifican hashes de los 1.731 identificadores de entrada de la base, sin descargar trades ni duplicar datos de mercado. Se mide una ventana real acotada antes de la tanda y se controla memoria/tiempo. No se registra una corrida fallida como período sin operaciones. Cada resultado indicará ejecutado, reutilizado_verificado, fallido o bloqueado, con motivo.

Tablas por variante/cartera/período: muestra completa, 2022–2023, enero 2024–agosto 2026 y años disponibles. Capital de cada subperíodo: equity anterior, no reinicio. Se presentan equity/P&L, retorno, CAGR, Sharpe y drawdown diario; funding, precio/basis, fees y slippage informativo; aperturas, fallos, parciales, exposición, utilización, tiempo sin cobertura, cierres por margen y liquidaciones. Las magnitudes no definidas quedan ND con motivo.

H1: comparar pronósticos, objetivos, exclusiones y ponderación 50/50 exactamente, sin depender de inversiones. H2: conditional frente a permanent dentro de la misma variante. H3: todos los minutos, independiente de posiciones/efectivo; promedio por activo y luego 50/50, días completos y dos cortes temporales. DECISION recalcula elegibilidad con su propio costo. Las demás variantes deben demostrar invariancia. El valor es forecast bruto elegible, no forecast neto de costos. Datos desconocidos no equivalen a cero.

Las conciliaciones usan Decimal y tablas primitivas: variación de equity = funding + P&L spot realizado/no realizado + P&L futuro realizado/no realizado − fees − liquidación. Los deltas emplean el comparador declarado y ambas estrategias conservan trazabilidad por run_id. Los umbrales numéricos usan la tolerancia original 1E-8; la equivalencia de la reproducción acotada y H1 se exige exacta en campos económicos, ignorando únicamente metadatos de identidad.

## Resultados y portabilidad

La evidencia incluye reporte comparativo, registro de ejecución, tablas CSV, figuras, configuraciones efectivas, manifiestos, fuentes por fact_id/source_id, matriz y diagnóstico de cobertura pendiente. La [guía de reproducción](../reproduction.md) distingue la verificación offline de evidencia compacta de la reproducción del motor y detalla sus dependencias. Los certificados históricos conservan su fecha y alcance.

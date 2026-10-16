# Diccionario de datos

## Convenciones

| Campo o unidad | Significado |
|---|---|
| `strategy` | `conditional`: condicional; `permanent`: incondicional. El identificador histórico se conserva en los datos. |
| `symbol` | `BTCUSDT` o `ETHUSDT`. |
| `scenario` | BASE o variante cuyos parámetros se describen en su informe. |
| `period` | Muestra completa, corte original o año. Enero–agosto de 2026 es parcial. |
| `run_id` | Identifica una trayectoria simulada. |
| `event_time`, `time_ns` | Momento UTC del evento, en nanosegundos desde el origen Unix. |
| `available_at` | Primer instante en que una decisión puede usar la observación. |
| `*_usdt` | Importes en USDT. La cuenta SOFR usa USD y explicita la paridad nominal. |
| Tasas y retornos | Proporciones decimales: `0.01` significa 1%. Un punto básico es `0.0001`. |
| Cantidades y volúmenes | Unidades de BTC/ETH para base; USDT para volumen cotizado. |
| ND, vacío o `null` | Resultado no disponible o no definido; consultar el campo `reason` correspondiente. |

Las cifras de evidencia conservan su precisión. La presentación en tablas y
figuras aplica el redondeo publicado. Los importes del motor se procesan con
`Decimal`; los cálculos estadísticos que requieren punto flotante mantienen
sus convenciones y tolerancias.

## Evidencia para leer y recalcular

| Archivo o carpeta | Contenido |
|---|---|
| [`data/evidence/carteras_continuas.zip`](../data/evidence/carteras_continuas.zip) | Observaciones, saldos, posiciones, fills, ciclos y configuraciones de las dos carteras BASE; tablas originales dentro de `tablas/`. |
| [`results/base/continuo/tablas/`](../results/base/continuo/tablas/) | Resultados por período, patrimonio diario, actividad, tiempo invertido, filtros, H1 y H3. |
| [`results/capital/evidencia/tablas/`](../results/capital/evidencia/tablas/) | Utilización del patrimonio, P&L por ciclo y motivos de decisión. |
| [`results/benchmark_sofr/evidencia/tablas/`](../results/benchmark_sofr/evidencia/tablas/) | Cuenta SOFR diaria, calendario y comparación por períodos. |
| [`results/complementaria/Evidencia_complementaria_Pablo_Salerno.zip`](../results/complementaria/Evidencia_complementaria_Pablo_Salerno.zip) | Comparadores adicionales de H1, oportunidad anual/mensual H3, basis, funding y sensibilidad de caja. |
| [`results/`](../results/README.md) | Informes, agregados y series diarias por tema, junto a las fuentes de las figuras. |
| [`data/evidence/thesis_baseline.json`](../data/evidence/thesis_baseline.json) | Valores publicados por tabla, fuentes, rutas requeridas y hashes de integridad. |

`equity_usdt` es patrimonio, `daily_return` su retorno diario y `net_pnl_usdt`
el resultado neto. La atribución separa P&L spot y futuro, funding, comisiones
y cargos de liquidación. `slippage_informational_usdt` es un diagnóstico del
precio ejecutado. `cagr` es retorno compuesto anualizado; `sharpe` usa tasa
libre de riesgo cero; `max_drawdown` es una proporción con signo negativo.
Las definiciones están en [metodología](methodology.md#evaluación).

En H1, `mae_ewma` y `mae_no_change` miden error absoluto de funding en el
horizonte indicado. En H3, `opportunity` es funding previsto elegible y
`eligible_fraction` es la fracción temporal que pasa filtros. `complete`
distingue un día completo de uno excluido por datos desconocidos.

## Datos de mercado preparados para el motor

| Dataset | Campos principales | Disponibilidad y uso |
|---|---|---|
| `minute_bars` | `open_time`, `end_time`, OHLC, `base_volume`, `quote_volume`, `trade_count` | Al terminar la vela. Alimenta señales y VWAP de ejecución. |
| `funding` | `funding_time`, `funding_rate`, `interval_hours`, `settlement_mark_price`, `interval_verified` | El cobro ocurre en `funding_time`; la tasa informa decisiones 60 segundos después. |
| `marks` | `open_time`, `close_time`, OHLC, `estimation_method`, `anchor_open_time` | Tras el cierre. Valúa exposición y margen; identifica aproximaciones. |
| Reglas | Vigencia, conocimiento, cantidades mínimas, ticks, comisiones y tramos de mantenimiento | La decisión requiere una regla válida y conocida. BASE utiliza los supuestos prescritos. |

Las particiones Parquet conservan precios, tasas y cantidades como texto decimal.
`source_file` identifica la fuente de cada observación. Una ausencia desconocida
bloquea cobertura; los cierres documentados de mercado se distinguen de esos
faltantes. Los archivos de mercado completos se requieren solamente para
repetir el motor, como explica [reproducción](reproduction.md#repetir-el-motor-con-datos-preparados).

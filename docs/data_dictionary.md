# Diccionario de datos

Todos los timestamps normalizados son enteros UTC en nanosegundos. Los precios, cantidades, tasas y montos se conservan como texto decimal exacto en Parquet y se convierten a `Decimal` al hacer replay. `event_time` describe cuándo ocurrió el hecho; `available_at`, cuándo puede usarlo una decisión. No son intercambiables.

## Trades

Formato conservado para las referencias anteriores. El escenario vigente
`next_minute_vwap` no consume ni descarga operaciones individuales.

| Campo | Tipo normalizado | Unidad y significado |
|---|---|---|
| `symbol` | string | `BTCUSDT` o `ETHUSDT`. |
| `market` | string | `spot` o `futures` USD-M. |
| `trade_id` | string | Identificador de la operación individual provisto por Binance. No se usan `aggTrades`. |
| `event_time` | int64 | Timestamp UTC ns de la operación. Spot usa milisegundos antes de 2025 y microsegundos desde 2025; Futures conserva milisegundos. |
| `available_at` | int64 | Igual a `event_time`: una operación pública queda disponible al ocurrir. |
| `price` | string decimal | USDT por unidad del activo, estrictamente positivo. |
| `quantity` | string decimal | Unidades del activo base, estrictamente positivas. |
| `source_file` | string | Archivo ZIP oficial del cual salió la fila. |

## Precios y volúmenes por minuto

El nuevo dataset `minute_bars` conserva, por símbolo y mercado, `open_time`,
`end_time` exclusivo, `available_at = end_time`, `open`, `high`, `low`, `close`,
`base_volume`, `quote_volume`, `trade_count` y `source_file`. Los volúmenes son
unidades base y USDT, respectivamente. `quote_volume/base_volume` es el VWAP
cuando el volumen base es positivo. La barra sólo informa decisiones y fills
una vez cerrada; no se convierte en trades artificiales.

Los fills de `next_minute_vwap` agregan `window_start`, `window_end`,
`window_base_volume`, `window_quote_volume`, `slippage_rate`,
`participation`, `max_volume_participation`, `capacity_used`,
`partial`, `remaining_quantity`, `fill_reason`, `execution_model` y
`source_file`. La comisión y el slippage están identificados por separado,
sin descontar dos veces el costo ya incluido en el precio.

`signals.parquet` incluye `filter_*` (`pass`, `fail`, `not_evaluable`),
`filter_order`, causas simultáneas y `sequential_rejection`, tiempos de
disponibilidad, forecast, costo descompuesto, basis y plan de cantidades.
`renewal_diagnostics.parquet` conserva las evaluaciones de renovación sin
agregarlas a las observaciones de H1.

El escenario `minute_open` conserva dos datasets separados; no fabrica trades.

| Dataset | Campos específicos | Disponibilidad |
|---|---|---|
| `minute_prices` | `symbol`, `market`, `reference_id`, `event_time`, `available_at`, `price`, `source_file` | Apertura asignada al límite inicial del minuto; sólo si existen operaciones. |
| `minute_volumes` | `symbol`, `market`, `open_time`, `close_time`, `available_at`, `quantity`, `trade_count`, `source_file` | Cierre observado más una unidad del timestamp original: 1 ms o 1 µs. |

`reference_id = bar:<symbol>:<market>:<open_ns>` identifica una vela, no una
operación individual. El precio sólo se puede utilizar para llenar una orden
enviada estrictamente antes. Cantidades y precios son decimales exactos; los
tiempos son ns UTC y `trade_count` es entero. Las velas vacías conservan su
volumen cero observado pero no producen un precio ejecutable.

Una suspensión documentada puede explicar minutos sin filas. La ausencia se
declara en `documented_closures` de la calidad de datos: no se insertan velas,
precios ni volúmenes sintéticos. Fuera de esos intervalos, un minuto ausente
impide certificar la cobertura. La vela vacía que terminó antes de tiempo
durante la suspensión de marzo de 2023 conserva su cierre real.

## Funding

| Campo | Tipo normalizado | Unidad y significado |
|---|---|---|
| `symbol` | string | Símbolo del perpetuo USD-M. |
| `funding_time` | int64 | Momento UTC ns en que se liquida económicamente el funding. |
| `available_at` | int64 | `funding_time + 60 segundos`; evita adelantar la señal. |
| `funding_rate` | string decimal | Tasa final del intervalo, en proporción decimal. Nunca se rellena con cero. |
| `interval_hours` | string decimal | Diferencia exacta entre liquidaciones observadas, calculada desde nanosegundos. |
| `settlement_mark_price` | string decimal o null | Mark informado por `/fapi/v1/fundingRate`; `null` conserva una ausencia de la fuente. |
| `interval_verified` | bool | Exige timestamps corroborados por Data Vision, ninguna liquidación esperada intermedia, duración nominal horaria publicada compatible y tasa coincidente. Un gap no se interpreta como cambio de frecuencia. |
| `source_file` | string | Respuesta API cruda que originó la fila. |

La descarga de muestra comienza `window_hours + 24 horas` antes del inicio solicitado y pide un día adicional. La primera observación, que no tiene antecedente para medir su intervalo, no se publica; el día extra conserva el antecedente necesario para formar el primer forecast completo al inicio de evaluación.

El calendario publica intervalos nominales en horas enteras; algunos timestamps oficiales de liquidación tienen milisegundos posteriores a la hora. Para corroborar ese campo nominal se comparan los límites horarios UTC de ambos timestamps. Para EWMA y cobros se conservan los timestamps exactos y la duración efectiva en nanosegundos, sin redondearla a ocho horas. Un salto de dieciséis horas declarado como ocho sigue siendo inválido. También se exige que la API contenga todos los eventos esperados hasta el fin solicitado, incluida la cola.

## Mark price por minuto

| Campo | Tipo normalizado | Unidad y significado |
|---|---|---|
| `symbol` | string | Símbolo del perpetuo USD-M. |
| `open_time`, `close_time` | int64 | Límites UTC ns de la vela según la fuente. |
| `available_at` | int64 | `close_time + 1 ms`. La estrategia nunca ve la vela en `open_time`. |
| `open`, `high`, `low`, `close` | string decimal | Mark price en USDT, estrictamente positivo. |
| `source_file` | string | ZIP oficial de `markPriceKlines/1m`. |

## Reglas de mercado

Cada registro es un snapshot completo: `symbol`, `market`, `rule_type=market`, `valid_from`, `valid_to`, `known_from`, `source_url`, `source_publication_time`, `retrieved_at`, `evidence_status` y un objeto `values`. Los tiempos pueden ser ISO 8601 UTC o ns enteros. `values` contiene `step`, `tick`, `min_qty`, `max_qty`, `min_notional`, `max_notional`, `taker_fee`, `tiers`, `liquidation_fee`, `liquidation_regular_fee`, `liquidation_fee_basis` y `operational`.

`RuleBook.get` exige simultáneamente vigencia y conocimiento. Acepta evidencia `verified`; un `current_snapshot` sólo desde su fecha conocida, nunca hacia atrás. Los registros `synthetic` requieren `allow_synthetic=True` y quedan limitados a pruebas y demo. `data/rules/history.json` permanece vacío hasta obtener evidencia histórica exacta: una consulta actual no certifica reglas pasadas y las comisiones VIP 0 ilustrativas no se presentan como una tarifa constante de la muestra.

## Manifiestos y cobertura

Las rutas `data/manifests/` del checkout conservan el [piloto histórico](../data/manifests/README.md); los manifiestos continuos están junto a las fuentes locales. En cada raíz de datos, `data/manifests/download.json` registra por objeto `source_url`, ruta local, SHA-256, bytes, dataset, símbolo, mercado, rango, estado, errores y hora de recuperación. Los ZIP conservan además el archivo `.CHECKSUM` oficial. `processed.json` registra hashes, filas, esquema, rango, duplicados idénticos removidos, conflictos y verificaciones de continuidad. `coverage.json`, `data_coverage.csv` y `data_quality_report.md` distinguen `complete` de `incomplete_data`, el alcance acotado del baseline completo y las reglas faltantes.

Un archivo ausente o incompleto es información desconocida. No se convierte en inactividad, funding cero, precio interpolado ni retorno inventado. Sólo se eliminan duplicados idénticos; dos filas distintas con la misma clave invalidan la partición.

Los diarios oficiales que completan un mensual se registran en `supplements`
del archivo principal, con rutas, SHA-256 y checksums oficiales. La normalización
verifica cada fuente y vuelve a comprobar la continuidad conjunta. Los originales
permanecen intactos y los hashes de los suplementos forman parte de la corrida.

La identidad económica de los inputs incluye hashes de crudos, checksums, Parquet, reglas y contenido semántico de `processed.json`; excluye la hora de recuperación y su hash indirecto. Cada corrida histórica conserva copias exactas de los tres manifiestos en `source_manifests/`. Una demo sintética no incorpora esos manifiestos históricos. Los informes económicos se guardan con decimales exactos en Parquet; todos los CSV/Parquet de resultados tienen `run_id`, estrategia/activo cuando corresponde, timestamps UTC y una descripción de unidades por columna.

# Prompt para Codex del backtesting de crypto carry

Implementá el proyecto descrito a continuación dentro de la carpeta existente `Backtesting`. Este documento contiene el diseño y el plan de implementación. Tu tarea es construir, ejecutar y verificar el proyecto, no devolver solamente otro plan.

## 1. Objetivo y alcance

Desarrollá un backtest reproducible de una estrategia de crypto carry condicional en Binance: long spot y short perpetuo lineal USD-M en BTCUSDT y ETHUSDT. Comparalo con un carry permanente que comparta todas las reglas salvo las condiciones de funding para entrar y renovar.

El proyecto debe permitir preparar la Entrega 3 de la tesina, implementación y resultados preliminares, y la Entrega 4, robustez y análisis crítico. Debe producir datos, tablas, gráficos e informes que luego puedan incorporarse al Executive Briefing y al Whitepaper. No redactes una tesina completa ni desarrolles un bot de trading real.

La pregunta es si el pronóstico de funding permite mejorar el resultado neto ajustado por riesgo y si la oportunidad se comprimió desde 2024. Los resultados pueden ser negativos. No optimices parámetros para conseguir una conclusión favorable.

### Documentación de referencia

Buscá estos archivos en el proyecto o en los adjuntos disponibles y leelos si están accesibles:

| Documento | Función |
|---|---|
| `Entregables - Track Finanzas Computacionales(2).docx` | Requisitos académicos, especialmente Entregas 3 y 4. |
| `Entrega 1 - Crypto Carry Binance (Salerno Pablo & Rodriguez Facundo).pdf` | Motivación e hipótesis iniciales. |
| `Entrega 2 Crypto Carry Binance Pablo Salerno(6).pdf` | Fuente principal de las reglas operativas y de evaluación. |
| `3cce414b-a788-41f0-bd6e-54b3bda4871b.png` | Feedback sobre la Entrega 2. |

El feedback es favorable: destaca que conservar activos, sizing, ejecución, riesgos y costos permite aislar razonablemente el valor del filtro de funding. No solicita cambiar la estrategia.

Este instructivo es autocontenido. Si los adjuntos no están disponibles, implementá a partir de las reglas transcritas aquí y registrá que no pudiste contrastarlos directamente. No finjas haberlos leído.

Ante diferencias entre Entrega 1 y Entrega 2, prevalece la Entrega 2. Por ejemplo, la evaluación principal es descriptiva, sin exigir significancia estadística. Las convenciones adicionales de este prompt completan ambigüedades operativas y deben identificarse como decisiones de implementación, no como afirmaciones textuales de la tesina.

### Requisitos generales

- Todos los archivos del proyecto, incluidos datos, configuraciones, documentación, pruebas y resultados, deben quedar dentro de `Backtesting`. Si ya estás ubicado allí, no crees `Backtesting/Backtesting`.
- Inspeccioná el contenido existente y respetá las instrucciones aplicables del repositorio. Conservá archivos ajenos y trabajo previo.
- Código claro, modular y bien comentado. Identificadores, comentarios, docstrings, mensajes técnicos y nombres de pruebas en inglés. README, explicación metodológica y análisis de resultados en español.
- Comentá especialmente las decisiones financieras, unidades, signos, reglas temporales y supuestos. Evitá comentarios que solamente repitan la línea de código.
- Usá funciones pequeñas, type hints y objetos de estado explícitos. Evitá un notebook monolítico y abstracciones innecesarias.
- No solicites credenciales para operar, no envíes órdenes reales y no conectes cuentas privadas. Usá datos públicos y archivos locales.
- Avanzá por hitos verificables. Resolvé decisiones técnicas menores con criterio y documentalas. Si aparece un bloqueo de datos o dependencias, completá lo que sea verificable y reportá el bloqueo concreto.

## 2. Arquitectura y herramientas

Usá Python 3.14, NautilusTrader, pandas, NumPy y Matplotlib, como establece la Entrega 2. Agregá PyArrow para Parquet, pytest para pruebas y una biblioteca HTTP sencilla para descargar datos. Usá `uv` y un lockfile para fijar dependencias.

Antes de desarrollar el motor, verificá la compatibilidad real entre Python, sistema operativo y una versión concreta de NautilusTrader. Preferí una versión estable compatible. Si Python 3.14 no resulta compatible en el entorno, documentá el error y elegí una versión soportada, sin modificar las reglas financieras. Registrá esa desviación. No uses APIs inventadas ni mezcles ejemplos de distintas versiones.

La documentación `latest` consultada el 17/09/2026 diferencia NautilusTrader 2.x y las instalaciones estables 1.x. Revalidá esto al implementar y usá documentación correspondiente a la versión fijada. [Instalación oficial de NautilusTrader](https://nautilustrader.io/docs/latest/getting_started/installation/).

### Diseño elegido

Motor de eventos con lógica de dominio propia para señales, ejecución, posiciones, funding, garantías y evaluación. NautilusTrader debe participar efectivamente en el replay y la simulación; una importación decorativa no cumple el requisito.

El ledger del proyecto será la fuente económica de verdad. Tendrá una única vía para registrar cada ejecución, comisión, pago de funding, transferencia, realización de P&L y cargo de liquidación. El adaptador deberá mantenerlo coherente con los eventos y posiciones que exponga NautilusTrader, evitando aplicar el mismo movimiento dos veces.

Usá una sola implementación de la estrategia con `funding_filter_enabled=True/False`. Este flag cambia únicamente la condición de funding de entrada y de renovación. El resto del código, los datos y los parámetros deben ser compartidos. Cada cartera tendrá su propio estado y sus propios 10.000 USDT.

Antes de escalar, implementá una prueba de integración mínima que demuestre:

1. Una orden no ejecuta con una operación anterior ni con la operación que generó la decisión.
2. La segunda pata respeta el segundo de espera desde la ejecución de la primera.
3. Funding, órdenes y riesgo respetan la prioridad temporal de este documento.
4. Funding y comisiones se registran una sola vez.
5. Terminar la corrida no cierra posiciones ni ejecuta órdenes fuera de la muestra.

NautilusTrader puede liquidar funding automáticamente y su flujo de matching no equivale necesariamente al orden de eventos de la tesina. Deshabilitá o adaptá los mecanismos que entren en conflicto mediante interfaces verificadas de la versión elegida. No asumas que la configuración por defecto cumple la especificación. Si usás eventos de funding propios, no alimentes además un mecanismo nativo que vuelva a cobrarlos. [Funding y cuentas](https://nautilustrader.io/docs/latest/concepts/backtesting/accounts-and-margin/), [orden de ejecución](https://nautilustrader.io/docs/latest/concepts/backtesting/execution-flow/).

El fill por la primera operación posterior, completo e independiente de su tamaño, es un supuesto específico del estudio. No lo reemplaces silenciosamente por fills parciales o matching pasivo del motor. Verificá el adaptador con una prueba que incluya una operación histórica menor que la orden simulada. [Ejecución basada en trades de NautilusTrader](https://nautilustrader.io/docs/latest/concepts/backtesting/trade-execution/).

### Estructura de archivos

Todas las rutas de esta tabla son relativas a `Backtesting`. Podés agrupar módulos pequeños si mejora la lectura, conservando estas responsabilidades.

| Ruta | Responsabilidad |
|---|---|
| `README.md`, `pyproject.toml`, `uv.lock` | Instalación, comandos y dependencias reproducibles. |
| `configs/base.toml`, `configs/robustness.toml` | Parámetros base y escenarios de sensibilidad separados. |
| `docs/methodology.md` | Reglas, ecuaciones, calendario, convenciones y límites. |
| `docs/requirements_traceability.md` | Mapeo de requisito a fuente, módulo, prueba y salida. |
| `docs/decisions.md`, `docs/data_dictionary.md` | Decisiones técnicas y significado de cada campo. |
| `docs/progress.md` | Hitos, evidencia de verificación y bloqueos. |
| `src/crypto_carry/config.py`, `models.py` | Configuración validada y tipos de datos y estado. |
| `src/crypto_carry/data/download.py` | Descargas reanudables, caché y manifiestos. |
| `src/crypto_carry/data/normalize.py`, `validate.py` | Esquemas, UTC, deduplicación y cobertura. |
| `src/crypto_carry/data/rules.py`, `replay.py` | Reglas históricas y lectura cronológica por particiones. |
| `src/crypto_carry/forecast.py`, `costs.py` | EWMA, no-change y costo de entrada estimado. |
| `src/crypto_carry/portfolio.py`, `ledger.py` | Sizing, saldos, inventarios, deuda y P&L. |
| `src/crypto_carry/margin.py`, `risk.py` | Garantía aislada, tramos, liquidación y controles. |
| `src/crypto_carry/execution.py` | Órdenes, fills, timeouts, secuencias y reintentos. |
| `src/crypto_carry/strategy.py`, `events.py` | Máquina de estados, decisiones y prioridades. |
| `src/crypto_carry/nautilus_adapter.py` | Integración efectiva con la versión fijada del motor. |
| `src/crypto_carry/evaluation.py`, `reporting.py` | H1, H2, H3, métricas, tablas y gráficos. |
| `src/crypto_carry/cli.py`, `__main__.py` | Comandos de uso reproducible. |
| `tests/unit/`, `tests/integration/`, `tests/fixtures/` | Pruebas financieras, temporales y de integración. |
| `data/raw/`, `data/processed/`, `data/rules/`, `data/manifests/` | Datos originales, normalizados, reglas y trazabilidad. |
| `outputs/<run_id>/` | Configuración efectiva, logs, tablas, gráficos e informe de cada corrida. |

No agregues interfaz web, base de datos, servicios persistentes ni entrenamiento de modelos complejos. Un notebook explicativo es opcional y debe consumir resultados del paquete, sin duplicar su lógica.

## 3. Parámetros base congelados

Configurá explícitamente los siguientes valores. Las tasas y proporciones se almacenan como decimales.

| Parámetro | Valor |
|---|---|
| Activos | BTCUSDT y ETHUSDT, spot y perpetuos lineales USD-M. |
| Moneda contable | USDT, supuesto de paridad con USD. |
| Historia prevista | Desde 2020-08-11 hasta 2026-08-31 inclusive. |
| Preparación | 2020 y 2021, sin resultados económicos de evaluación. |
| Evaluación | Desde 2022-01-01 00:00:00 UTC hasta antes de 2026-09-01 00:00:00 UTC. |
| Capital inicial | 10.000 USDT por cartera, sin posiciones. |
| Calentamiento | 14 días completos de funding y la observación previa necesaria para medir el primer intervalo. |
| Ventana EWMA | 336 horas reales. |
| Vida media EWMA | 24 horas reales. |
| Horizonte del pronóstico | 168 horas reales. |
| Demora para señal | 60 segundos después de cada liquidación efectiva de funding. |
| Entrada condicional | Pronóstico estrictamente mayor al costo estimado del ciclo. |
| Basis permitido para entrar | Entre 0 y 0,005 inclusive. |
| Duración inicial y renovaciones | 168 horas cada una. |
| Renovación condicional | Último pronóstico estrictamente positivo y controles válidos. |
| Objetivo spot por activo | 0,30 del patrimonio total de su cartera. |
| Apalancamiento del perpetuo | 2x, garantía aislada por activo. |
| Rebalanceo | Solo al renovar, si el desvío relativo del valor spot al objetivo supera 0,05. |
| Slippage base | 0,0001 por orden, equivalente a 0,01% o 1 bp. |
| Espera entre patas | 1 segundo desde el fill de la primera pata. |
| Timeout de cada orden | 30 segundos. |
| Antigüedad máxima de trades para señales y basis | 60 segundos. |
| Control periódico de basis y mark | Al cierre de cada minuto. |
| Salida por ampliación del basis | Incremento de al menos 0,02, equivalente a 2 puntos porcentuales. |
| Salida preventiva por margen | Mantenimiento / saldo de margen mayor o igual a 0,50. |
| Salida preventiva por distancia a liquidación | Estrictamente menor a 0,15. |
| Inicio de corrección de descalce | Estrictamente mayor a 0,02. |
| Descalce máximo al abrir, rebalancear o terminar corrección | 0,005. |
| Plazo de corrección | 60 segundos desde su detección. |
| Salida por falta real de operaciones | Más de 30 minutos en cualquiera de las dos patas. |
| Bloqueo por riesgo, liquidación o intento fallido | 24 horas por activo. |
| Rendimiento del efectivo y tasa libre de riesgo | Cero. |
| Anualización del Sharpe diario | Raíz cuadrada de 365. |

No confundas 2 puntos porcentuales de basis con un aumento relativo del 2%. No conviertas 168 horas en 21 eventos ni 14 días en 42 observaciones: los intervalos efectivos pueden cambiar.

Las constantes de las fórmulas de este documento describen el baseline. En el código deben provenir de la configuración validada, para que cada sensibilidad cambie también sus ventanas, timers y etiquetas relacionadas sin alterar el baseline guardado.

## 4. Datos y reglas históricas

### Fuentes y acceso

Fuente principal: Binance Data Vision. Usá la API oficial para completar o verificar información. Implementá descarga por símbolo, mercado, tipo y fecha, con reanudación, retries acotados con backoff, límites de solicitudes, validación de archivos y checksums cuando estén publicados.

Necesitás:

- Funding final efectivamente liquidado, timestamp y mark price asociado al cobro.
- Operaciones individuales de spot y perpetuos para ejecutar y medir el basis.
- Mark price por minuto cerrado para valuación y riesgo.
- Reglas históricas de comisiones taker, tamaños, incrementos, mínimos y máximos aplicables, tramos de mantenimiento, deducciones, cargos de liquidación y estado operativo del mercado.

Usá `trades` para el caso base. Si solamente hay `aggTrades`, registrá el cambio de granularidad y demostrá qué permite preservar; no afirmes que reconstruís el orden individual de operaciones dentro de una agregación. Un escenario con esa aproximación debe quedar identificado.

El endpoint USD-M `/fapi/v1/fundingRate` ofrece tasas históricas, `fundingTime` y el mark asociado. Paginá sin omisiones ni duplicaciones y verificá su cobertura real. `/fapi/v1/premiumIndex` y `/fapi/v1/fundingInfo` no reemplazan una historia completa de tasas o reglas. [Documentación oficial de datos de mercado USD-M](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data).

Los archivos spot de Binance usan microsegundos desde el 01/01/2025. El parser debe determinar la unidad según fuente y esquema, validar las fechas y normalizar a UTC sin perder resolución. No apliques esa conversión indiscriminadamente a futuros o endpoints que usan milisegundos. [Binance Public Data](https://github.com/binance/binance-public-data).

### Esquemas mínimos

| Dataset | Campos esenciales |
|---|---|
| Trades | `symbol`, `market`, `trade_id`, `event_time`, `available_at`, `price`, `quantity`, `source_file`. |
| Funding | `symbol`, `funding_time`, `available_at`, `funding_rate`, `interval_hours`, `settlement_mark_price`, `source_file`. |
| Mark | `symbol`, `open_time`, `close_time`, `available_at`, `open`, `high`, `low`, `close`, `source_file`. |
| Reglas | `symbol`, `market`, `rule_type`, valores y unidad, `valid_from`, `valid_to`, `known_from`, `source_url`, `source_publication_time`, `retrieved_at`, `evidence_status`. |
| Cobertura | Dataset, activo, rango esperado, rango observado, huecos, duplicados, conflictos, verificaciones y estado. |

`event_time` representa cuándo ocurrió algo; `available_at`, desde cuándo puede usarlo la estrategia. `retrieved_at` registra cuándo lo descargó el investigador. No son intercambiables. Una reconstrucción posterior puede acreditar una regla histórica, pero una consulta actual sin evidencia de vigencia no permite aplicarla retrospectivamente.

La disponibilidad de trades y reglas se modelará con las convenciones documentadas. El funding final estará disponible para señales 60 segundos después de su liquidación. El ledger registra el flujo económico en el timestamp efectivo de funding. Mantené separadas esas dos funciones para no adelantar la señal.

### Calidad y cobertura

Validá orden temporal, unicidad por clave, precios positivos, cantidades válidas, tasas en decimal, intervalos de funding positivos, continuidad, headers y esquemas. Quitá solo duplicados idénticos documentados; un duplicado conflictivo requiere resolución o invalida el tramo. No elimines operaciones genuinas por ser parecidas.

Calculá `interval_hours` con la liquidación previa real y contrastalo con la información del intervalo cuando exista. No conviertas un funding faltante en un intervalo legítimamente más largo. Para acreditar 14 días completos hay que verificar cobertura y calendario aplicable, no solamente contar filas.

Distinguí:

| Situación | Tratamiento |
|---|---|
| No hubo trades, con archivo completo y ausencia verificada | Inactividad real. Aplican caducidad de precios, timeouts y control operativo. |
| Falta un archivo, una porción o una regla indispensable | Información desconocida. No equivale a inactividad ni a funding cero. |
| Falta información relevante sin posiciones abiertas | Bloquear entradas; rehabilitar cuando existan nuevamente 14 días válidos de funding y los demás datos requeridos. |
| Falta información indispensable con una posición abierta | Detener la certificación de la corrida en ese punto, guardar el estado y marcarla incompleta hasta corregir datos y repetir. |

No rellenes funding con cero, no interpoles precios para fabricar fills y no cierres posiciones ficticiamente antes de un hueco. Si no puede verificarse una valuación diaria, no produzcas un retorno diario inventado. La antigüedad de un trade por inactividad real no es lo mismo que desconocerlo por un archivo faltante.

Creá un registro histórico con fuentes oficiales fechadas. Las comisiones ilustrativas de 0,10% spot y 0,05% perpetuos no son evidencia de tarifas aplicables durante toda la muestra. Tampoco uses `exchangeInfo` actual como reglas históricas universales. No inventes mínimos, tramos ni cargos.

Si faltan reglas históricas, el proyecto puede quedar funcional y probado, pero el informe debe separar esa condición de haber completado un backtest histórico válido. Un dataset sintético sirve para pruebas y demo; nunca para resultados académicos ni para completar huecos históricos.

### Volumen de datos

Procesá por particiones de fecha, mercado y símbolo, con Parquet y lectura incremental. No cargues todos los trades de varios años en RAM. Conservá posiciones, timers, deuda, garantías y ventanas de funding al cambiar de partición. No cortes un mismo timestamp entre lotes sin preservar su orden completo.

Primero verificá funding, reglas y una muestra pequeña de ejecución. Luego ampliá. La historia de preparación de 2020-2021 no obliga a reproducir todos sus ticks sin utilidad: descargá la cobertura necesaria para preparación y ventanas, y explicitá qué datasets cubren cada período. La evaluación económica comienza siempre el 01/01/2022.

## 5. Pronóstico y costo esperado

Sea `tau` el timestamp del funding que acaba de liquidarse y `s = tau + 60 segundos` el momento de la nueva señal.

Tomá observaciones con `tau - 336 horas < funding_time <= tau`, todas ya disponibles en `s`. La observación de exactamente 14 días antes queda excluida de la suma, aunque puede hacer falta como antecedente para calcular el primer intervalo.

Para cada observación `j`:

- `age_hours_j = (tau - funding_time_j)` expresado en horas.
- `w_j = 2 ** (-age_hours_j / 24)`.
- `delta_j = horas entre funding_time_j y la liquidación previa`.
- `forecast_168h = 168 * sum(w_j * funding_rate_j) / sum(w_j * delta_j)`.
- `no_change_168h = 168 * last_funding_rate / last_interval_hours`.

No reemplaces esta EWMA por una media simple ni por una EWMA sobre un número fijo de filas. La fórmula normaliza por duración real. Recalculá después de cada funding, incluso con posiciones abiertas. Entre actualizaciones, usá el último pronóstico disponible.

El benchmark estadístico no-change solo sirve para H1. El benchmark económico de H2 es el carry permanente.

Para la entrada, usá este costo porcentual estimado, en relación con el nocional aproximado de una pata:

`estimated_cycle_cost = 2 * spot_taker_fee + 2 * futures_taker_fee + 4 * slippage_per_order`.

Es una aproximación ex ante de las cuatro órdenes, usando las tarifas vigentes conocidas al decidir. No usa precios ni comisiones futuras observadas retrospectivamente. La contabilidad realizada aplica cantidades, precios y tarifas efectivas de cada fill.

Con las tarifas exclusivamente ilustrativas de 0,001 y 0,0005 y slippage 0,0001, debe dar 0,0034, es decir 0,34%. No compares un retorno sobre patrimonio con ese umbral sobre nocional.

## 6. Tiempo, eventos y ejecución

### Orden determinista

Agrupá los eventos de un mismo timestamp físico. Aplicá, en este orden:

1. Actualizar datos disponibles y reglas que entran en vigencia.
2. Registrar funding para las posiciones existentes antes de los fills de ese timestamp.
3. Controlar liquidación y situación de insolvencia/deuda.
4. Atender salidas de riesgo, timers de corrección, timeouts y vencimientos de tenencia.
5. Actualizar señales que ya cumplieron su demora y decidir renovaciones o entradas habilitadas.
6. Ejecutar órdenes previamente enviadas que resulten elegibles.

La rutina de riesgo puede invalidar una orden de aumento antes de su fill. Las entradas nuevas no pueden consumir trades del mismo timestamp en que se enviaron. Si un cierre y un funding coinciden exactamente, se contabiliza primero el funding; una apertura ejecutada en ese timestamp no lo cobra retroactivamente.

Usá una secuencia estable dentro de cada fase, con BTCUSDT antes que ETHUSDT y después un identificador de evento. Para decisiones simultáneas, calculá los objetivos con un mismo snapshot del patrimonio previo a ese lote de decisiones y reservá fondos en ese orden. Ambos backtests usan la misma convención.

Los cambios de garantía, cantidad, reglas o funding exigen actualizar inmediatamente el riesgo usando el último mark válido. El precio de mark se actualiza solo cuando está disponible un nuevo minuto cerrado. Los timers deben activarse aunque no lleguen trades.

### Fills y expiración

Una orden enviada en `t_submit` puede ejecutar con la primera operación del mercado correspondiente que satisfaga:

`t_submit < trade_time < t_submit + 30 segundos`.

La igualdad con el deadline vence la orden, por la prioridad de timeouts sobre fills. Documentá esta convención de borde y probala.

- Compra: `fill_price = reference_trade_price * (1 + slippage)`.
- Venta: `fill_price = reference_trade_price * (1 - slippage)`.
- Ejecución completa, aunque el trade histórico tenga menor cantidad. Esta simplificación debe figurar como limitación.
- Validá filtros de cantidad y de mercado aplicables. No uses futuros ticks para elegir hoy la cantidad de una orden.
- Aplicá precisión de precio de forma conservadora si el modelo necesita tick size: compras hacia arriba y ventas hacia abajo. Registrá ese efecto por separado del supuesto de slippage.

Para abrir o aumentar: comprar spot; desde su fill esperar un segundo; enviar la venta del perpetuo por la cantidad neta a cubrir.

Para cerrar o reducir: recomprar el perpetuo; desde su fill esperar un segundo; vender el spot correspondiente. El segundo de espera en el cierre completo es una convención explícita coherente con el rebalanceo de la entrega.

Si la compra inicial falla, cancelar el intento. Si falla la cobertura del perpetuo después de comprar spot, desarmar vendiendo el spot. Conservar todas las comisiones y pérdidas del intento. Las órdenes de salida que vencen se reenvían inmediatamente con nuevo identificador y otro plazo de 30 segundos; esto no reinicia el plazo de corrección de descalce.

Mientras un cierre está pendiente, persisten inventario, mark-to-market, funding y liquidación. No conviertas la intención de cierre en un fill. Evitá órdenes duplicadas y reconciliá cualquier cierre parcial o cambio de cantidad antes de reenviar.

## 7. Estados, entradas, permanencia y riesgos

Implementá estados explícitos equivalentes a `FLAT`, `OPENING_SPOT`, `OPENING_PERP`, `HOLDING`, `REBALANCING`, `CORRECTING_HEDGE`, `CLOSING_PERP`, `CLOSING_SPOT`, `LIQUIDATING` y `COOLDOWN`. La deuda y la integridad de datos son además condiciones globales de cartera. Podés usar subestados para registrar la pata pendiente.

Cada transición debe guardar timestamp, estado anterior, siguiente estado, causa, orden y referencia del par. No permitas dos ciclos simultáneos del mismo activo ni una apertura mientras existe exposición negociable pendiente de cierre.

### Entrada

La estrategia condicional entra únicamente en los momentos de señal, después de funding + 60 segundos, si:

- No tiene un par abierto ni órdenes incompatibles, y no está en cooldown.
- `forecast_168h > estimated_cycle_cost`.
- `basis = futures_last_trade / spot_last_trade - 1` cumple `0 <= basis <= 0.005`.
- Ambos trades tienen antigüedad máxima de 60 segundos, existe el último mark cerrado válido y la ventana de funding está completa.
- Los mercados están operativos, las reglas históricas necesarias son válidas y existen fondos suficientes.
- No hay deuda pendiente ni una salida global de riesgo que impida aumentar exposición.

El carry permanente elimina solamente la segunda condición. Conserva las demás, incluida la necesidad de datos válidos y el filtro de basis.

### Permanencia y renovación

Las primeras 168 horas se cuentan desde que se completan ambas patas y se verifica el descalce admitido. Un funding posterior negativo no genera por sí solo un cierre antes de vencer esas 168 horas.

En el vencimiento, la estrategia condicional renueva si su último pronóstico disponible es mayor que cero, siguen válidos los datos y la operatividad y no existe una salida de riesgo. No vuelve a exigir cubrir el costo completo de entrada.

La renovación se decide en el timer de vencimiento, con la información disponible entonces. No se posterga hasta el siguiente funding ni usa una tasa que todavía no terminó su demora de 60 segundos. La próxima fecha es el vencimiento actual más 168 horas. Renovar sin cambiar tamaño no genera órdenes ni comisiones.

El carry permanente renueva sin condición de funding, manteniendo todos los demás requisitos. El filtro `0 <= basis <= 0.005` es de entrada; no lo conviertas en un nuevo filtro de renovación. Sigue vigente la salida por ampliación adversa del basis.

Si no corresponde renovar, cerrá el par. Una salida ordinaria por vencimiento no impone cooldown: la próxima entrada solo podrá evaluarse en el siguiente momento de señal.

### Riesgos

| Control | Regla exacta |
|---|---|
| Basis | En cada cierre de minuto con precios recientes, cerrar si `basis_now - basis_reference >= 0.02`. |
| Margen | Cerrar preventivamente si `maintenance / margin_balance >= 0.50`, siempre que todavía no corresponda liquidación. |
| Distancia | Cerrar preventivamente si `(liquidation_price - mark_price) / mark_price < 0.15`. |
| Descalce | En un par completo, `abs(q_spot_net - q_perp_short) / q_spot_net > 0.02` inicia corrección. |
| Operatividad | Cerrar por suspensión conocida o por más de 30 minutos sin operaciones reales en cualquiera de los mercados. |

Si uno de los trades supera los 60 segundos, bloqueá entradas, aumentos y renovaciones, y suspendé solamente el cálculo de basis hasta disponer de ambos precios recientes. Los controles de margen y las salidas deben continuar con la información válida que requieran. No confundas esa situación con faltantes de archivo.

Fijá `basis_reference` con los últimos trades válidos al completar la entrada. Actualizalo al terminar un rebalanceo que cambie tamaño. Una renovación sin órdenes y una corrección de hedge conservan la referencia. No uses los fills con slippage como si fueran el basis observado del mercado.

Corregí el descalce modificando únicamente el perpetuo hacia `floor_to_futures_step(q_spot_net)`, respetando fondos, mínimos y ejecución. Si no llega a `<= 0.005` en 60 segundos desde la detección inicial, ordená cerrar. La tolerancia puede superarse durante la secuencia normal entre patas, pero eso no habilita a ignorar otros riesgos; evitá que el detector trate el segundo de espera normal como un nuevo incidente independiente.

Al terminar una apertura o rebalanceo, exigir descalce `<= 0.005`. Si el redondeo lo impide, la apertura se considera fallida o el ajuste falla y debe desarmarse. Si `q_spot_net = 0` con un short restante, tratá esa exposición como descalce crítico y cerrá el short.

Después de riesgo, liquidación o intento fallido, el cooldown empieza cuando finaliza el desarme de la exposición negociable, o inmediatamente si nunca hubo fill. Dura 24 horas. Mientras haya cierre pendiente se prohíbe reabrir aunque transcurra ese tiempo. El polvo no negociable permanece identificado y valuado.

## 8. Sizing, rebalanceo y garantías

### Tamaño y rebalanceo

Cada activo apunta a spot por `0.30 * equity`. Calculá la cantidad con el precio conocido, redondeando hacia abajo al incremento histórico permitido. Incorporá cualquier remanente spot del mismo activo para no comprarlo otra vez.

La compra spot descuenta su comisión en unidades del activo. El short debe cubrir la cantidad neta efectivamente disponible, redondeada al incremento de futuros. No uses igualdad de nocionales como sustituto de igualdad de cantidades: con basis positivo, nocionales iguales dejan un descalce.

La asignación aproximada con ambos activos abiertos es 60% spot, 30% garantías y 10% efectivo. Las garantías son capital reservado; no se suman otra vez al patrimonio como dinero nuevo. La exposición bruta de las dos patas tampoco es el patrimonio.

Antes de abrir reservá fondos para spot, comisión de futuros, garantía y open loss estimado, con precios disponibles. Revalidá al ejecutar: si un movimiento de precio vuelve inviable la segunda pata, aplicá el desarme especificado. No financies la orden con un saldo negativo oculto.

Al renovar, rebalanceá solo si:

`abs(current_spot_value - 0.30 * equity) / (0.30 * equity) > 0.05`.

El 5% se interpreta respecto del objetivo, no como cinco puntos porcentuales del patrimonio. Si el objetivo no es positivo, corresponde la gestión de insolvencia, no dividir por cero.

Los aumentos siguen spot y luego perpetuo. Las reducciones siguen perpetuo y luego spot. Si un aumento no puede financiarse, omitilo y mantené el par si cumple los demás controles. Si falla la segunda pata de un ajuste iniciado, cerrá todo el par. Si falla la primera sin haber cambiado exposición, cancelá el ajuste y registrá el intento fallido, sin crear fills.

Una falla de rebalanceo conserva el estado real del par; si aún hay exposición no se la reemplaza por un estado FLAT. Un bloqueo de nuevas entradas puede coexistir con una posición hasta su cierre. Si hay ambigüedad adicional, elegí la resolución conservadora que no borre exposición y dejala en `docs/decisions.md`.

Al salir, vendé toda la cantidad spot negociable. El remanente menor que el mínimo sigue dentro del inventario y del patrimonio y se aprovecha en una entrada futura. No desaparece ni se vende a precio ficticio.

### Garantía aislada

Para un short de cantidad positiva `q`, precio medio `P0`, mark `M` y garantía aislada `I`:

- `unrealized_futures_pnl = q * (P0 - M)`.
- `margin_balance = I + unrealized_futures_pnl`.
- `maintenance = q * M * maintenance_rate - maintenance_amount`.
- `liquidation_price = (I + q * P0 + maintenance_amount) / (q * (1 + maintenance_rate))` dentro de un tramo válido.

Usá los tramos históricos correspondientes. Para el mantenimiento actual elegí el tramo de `q * M`. Para el precio de liquidación, verificá que el nocional `q * liquidation_price` pertenezca al tramo usado; si cruza un límite, resolvé por tramos. No apliques ciegamente la tasa del nocional actual a todo precio futuro.

Como convención de apertura, la garantía base será `q * execution_price / 2` y el open loss adicional del short será `max(0, q * (mark_price - execution_price))`. En aumentos agregá garantía para la cantidad nueva, recalculá el precio medio y verificá suficiencia de la posición resultante. No cuentes el open loss como comisión: es garantía adicional y el P&L se reconoce mediante la valuación.

En un cierre parcial, liberá la misma fracción de garantía que la fracción de cantidad cerrada y reconocé el P&L realizado y la comisión. El precio medio de la cantidad restante no cambia por reducirla. No transfieras automáticamente ganancias spot no realizadas ni efectivo libre a la garantía para impedir una salida de riesgo.

Si `margin_balance <= maintenance`, o el saldo ya es no positivo, la liquidación tiene prioridad sobre el cierre preventivo. Evitá divisiones inválidas. El test exacto de igualdad es una convención conservadora de esta implementación.

La liquidación simulada es total. Como convención, enviá recompra forzosa del perpetuo con la primera operación posterior y el slippage definido, luego vendé spot siguiendo la secuencia de salida. Si falta actividad real, el cierre permanece pendiente y reintenta. Aplicá el cargo histórico de liquidación sobre la base que indique su regla, una sola vez; documentá también si la regla exige comisión ordinaria adicional para no duplicar conceptos.

Esta mecánica es una aproximación, no una reproducción del mecanismo interno de Binance. No modela liquidaciones parciales ni ADL. El control de mark por minuto puede omitir extremos intraminuto. Si el gap corresponde a datos ausentes, la corrida es incompleta en vez de simular una ausencia de liquidez.

### Funding y deuda

En cada liquidación efectiva, calculá `funding_cashflow = q_short_before_fills * settlement_mark_price * funding_rate`. El signo positivo acredita al short; el negativo lo debita. Usá el mark asociado al cobro, no el precio actual descargado ni un cierre futuro. Si falta ese mark indispensable, no lo sustituyas silenciosamente.

El funding positivo aumenta efectivo libre de Futures. El negativo consume primero ese efectivo y luego la garantía aislada del contrato, actualizando el riesgo. Registrá exactamente los movimientos, sin incrementar o reducir a la vez dos cuentas por el mismo importe.

Definí un waterfall determinista para otras obligaciones realizadas: efectivo libre Futures, transferencias de efectivo libre spot y garantías liberadas por cierres. Nunca uses las ganancias spot no realizadas como efectivo ni la garantía de otro contrato como saldo libre. Las transferencias internas admitidas son inmediatas y gratuitas y no cambian el patrimonio.

Si después de agotar fondos utilizables queda una obligación, registrala como deuda. La deuda bloquea nuevas entradas y aumentos y exige cerrar posiciones para cancelarla. Para elegir cierres usá el mismo orden determinista BTC y ETH, verificando la deuda después de cada realización. Las entradas de efectivo cancelan deuda antes de financiar nuevas posiciones.

Si un funding negativo agota tanto el efectivo Futures como la garantía del contrato, el faltante es una obligación realizada: utilizá el efectivo spot libre mediante transferencia antes de registrar deuda residual. Eso cancela la obligación, sin reponer automáticamente la garantía consumida ni anular una liquidación ya disparada. Registrá esta convención de disponibilidad de fondos.

Si tras realizar y conciliar las obligaciones el patrimonio final es no positivo, declaralo insolvente. Preservá las pérdidas: no truncar el equity en cero ni descartar el resto de la corrida como si no hubiera ocurrido el evento.

## 9. Contabilidad y valuación

Llevá por separado efectivo libre spot, efectivo libre Futures, garantías aisladas, inventario spot, cantidades short, precio medio, P&L realizado, funding y deuda. Las reservas de órdenes no crean dinero ni permiten gastar dos veces el mismo efectivo.

Una identidad de patrimonio debe ser:

`equity = free_spot_cash + free_futures_cash + sum(isolated_collateral) + spot_inventory_value + unrealized_futures_pnl - outstanding_debt`.

Incluí en el inventario todo el polvo spot y las posiciones en tránsito. No sumes nuevamente P&L realizado o funding si ya forman parte de los saldos. Las cantidades short y el principal del perpetuo no son dinero recibido por una venta spot.

Valuá spot con la última operación conocida y perpetuos con el último mark cerrado disponible. Una marca antigua por inactividad real puede usarse para valorizar, con antigüedad visible, pero no convierte el precio en ejecutable ni habilita señales que exigen frescura. Si el dato es desconocido por un hueco de archivo, aplicá la política de corrida incompleta.

Para un tramo con cantidades constantes:

`net_pnl = funding + q_spot * change_in_spot_price - q_short * change_in_futures_price - explicit_costs`.

Cuando las cantidades son iguales y las valuaciones son consistentes, el componente de precios equivale a `-q * change_in(F - S)`. Esto usa la diferencia absoluta de precios, no el cambio del basis porcentual. Durante intervalos entre patas, descalces o cambios de tamaño, calculá cada exposición real por separado.

Distinguí el precio trade del perpetuo para ejecutar y medir basis del mark para valorar y controlar margen. Si la atribución por basis usa trades, mostrale por separado al lector la diferencia de valuación contra mark; no la hagas desaparecer para forzar una identidad.

La comisión de compra spot se descuenta de las unidades recibidas y se valúa al fill. Esa reducción ya afecta el patrimonio: no vuelvas a restar la misma comisión del efectivo. Las demás comisiones se pagan en USDT conforme a las reglas históricas aplicables.

El slippage ya está incluido en el fill. Podés reportar su costo atribuible frente al trade de referencia, pero no volver a debitarlo en el ledger. Presentá una atribución que reconcilie exactamente, separando columnas informativas de los movimientos de caja.

Al final de cada día UTC guardá equity y componentes después de todos los eventos del día, antes de cualquier evento del siguiente. El primer retorno parte de los 10.000 USDT iniciales. Conservá todos los días, incluidos los inactivos. Al terminar el 31/08/2026, valuá posiciones abiertas sin forzar su cierre, sin agregar comisiones hipotéticas y sin permitir que el apagado del motor ejecute órdenes fuera de la muestra.

Si mostrás un valor neto de cierre hipotético, debe ser una sensibilidad aparte, nunca reemplazar la curva base.

## 10. Evaluación de las hipótesis

Los resultados principales son descriptivos, como establece la Entrega 2. No uses expresiones de causalidad ni de significancia estadística a partir de estas comparaciones. Guardá todos los valores, incluso los desfavorables.

### H1 Capacidad predictiva

Para cada señal emitida en `s`, el objetivo será la suma de tasas efectivamente liquidadas en `(s, s + 168 horas]`. Esta es la convención de anclaje elegida para las 168 horas siguientes. El histórico del pronóstico sigue anclado en `tau` según la sección 5.

La tabla tendrá activo, timestamp de señal, rango de historia, pronóstico EWMA, pronóstico no-change, objetivo observado, error de cada modelo y validez del horizonte.

- Evaluá todos los momentos con funding histórico y horizonte completos, incluso si no hay señal económica de entrada, no hay fondos o el basis no es elegible.
- Usá exactamente las mismas observaciones para comparar ambos modelos.
- Calculá el MAE por activo y el agregado como `(MAE_BTC + MAE_ETH) / 2`.
- Excluí las observaciones finales cuyo horizonte se extienda fuera de la muestra y las etiquetas con funding faltante. Informá sus cantidades.
- No rellenes objetivos incompletos con cero ni uses el funding futuro como feature.
- Reportá la muestra completa y los dos subperíodos definidos para H3.

EWMA con menor MAE es evidencia descriptiva favorable; mayor MAE, contraria; igualdad o datos insuficientes, resultado no concluyente. Los horizontes se solapan: explicalo como límite para inferencia estadística. El buen pronóstico no demuestra rentabilidad.

### H2 Resultado económico

Compará las dos carteras sobre el mismo calendario y cobertura válida. Cada una empieza con 10.000 USDT el 01/01/2022 y mantiene su propio equity. Las diferencias posteriores de tamaño y efectivo causadas por sus resultados son legítimas; las reglas de sizing siguen siendo idénticas.

Calculá, como mínimo:

- Retorno neto acumulado y CAGR, usando duración calendario real sobre base de 365 días.
- Sharpe con retornos diarios, tasa libre de riesgo cero y factor `sqrt(365)`.
- Volatilidad diaria anualizada, máximo drawdown y duración del drawdown.
- Funding neto, P&L de spot y perpetuos, comisiones y cargos de liquidación.
- Atribución informativa del slippage, sin doble descuento.
- Tiempo invertido por activo y de cartera, incluyendo el tiempo con una sola pata expuesta.
- Rotación y cantidad de aperturas, renovaciones, rebalanceos, correcciones, cierres, intentos fallidos y liquidaciones.
- Tiempo en efectivo, cooldown y exposición sin cobertura completa.
- Deuda, insolvencia, posiciones finales y remanentes.

Usá desviación estándar muestral para el Sharpe y documentalo. Si hay menos de dos observaciones, volatilidad nula o insolvencia que vuelve inaplicable una métrica, devolvé nulo con motivo; no un Sharpe infinito ni una rentabilidad engañosa. El equity y las pérdidas observadas se conservan aunque una métrica no se pueda calcular.

H2 es descriptivamente favorable si el CAGR condicional es positivo y su Sharpe supera al del carry permanente. Si alguna métrica necesaria no es válida, no afirmes cumplimiento. Si la corrida histórica está incompleta, los resultados del prefijo pueden mostrarse como diagnóstico con fechas exactas, sin presentarlos como evaluación de toda la muestra.

### H3 Compresión desde 2024

Compará 2022-2023 con 2024-01-01 a 2026-08-31. No reinicies carteras, posiciones, garantías ni capital el 01/01/2024. Los CAGR de cada tramo usan el equity que realmente llega a su inicio y las duraciones respectivas.

Construí un indicador de oportunidad independiente de estar invertido. En cada minuto UTC y para cada activo:

1. Tomá el último pronóstico ya disponible, sin recalcularlo con información futura.
2. Verificá funding esperado mayor al costo de ciclo conocido, basis de entrada y condiciones de datos y operatividad.
3. Si cumple, el valor es el pronóstico de funding de 168 horas.
4. Si los datos están completos pero no cumple los filtros, el valor es cero.

Para que sea un indicador común de oportunidades de mercado, no lo condiciones a posiciones, saldo libre, cooldown o resultados específicos de una cartera. Esta delimitación es una convención explícita para medir H3. Una ausencia real de trades puede hacer fallar operatividad y producir cero; un dato desconocido hace incompleto el día.

Promediá los 1.440 minutos de un día completo por activo, incluidos los ceros. Luego combiná BTC y ETH con igual peso. Si un activo tiene datos requeridos incompletos, excluí el día entero del indicador conjunto e informalo. No promedies solamente minutos elegibles. Un día completo sin elegibilidad vale cero.

Compará el promedio diario del indicador y el CAGR del carry condicional entre subperíodos:

| Cambio desde 2024 | Lectura descriptiva |
|---|---|
| Disminuyen ambos | Favorable a H3. |
| Aumentan ambos | Contraria a H3. |
| Direcciones distintas o empates | Mixta. |
| Cobertura insuficiente o CAGR no definido | No concluyente por falta de evidencia evaluable. |

Mostrá también cobertura y frecuencia de elegibilidad. No atribuyas causalmente un cambio a la entrada de arbitrajistas solo con esta comparación.

## 11. Robustez y análisis crítico de la Entrega 4

Implementá la infraestructura junto con el proyecto, pero ejecutá primero el caso base verificado. Cada escenario vive en su propia configuración y salida. No reemplace al caso base y no selecciones retrospectivamente el mejor.

Usá sensibilidades de una variable por vez y corré las dos estrategias bajo el mismo cambio, conservando todo lo demás. No hagas una búsqueda exhaustiva de combinaciones.

| Dimensión | Escenarios iniciales |
|---|---|
| Costos de transacción | 1x, 2x y 3x sobre comisiones taker y slippage; los cargos de liquidación mantienen su regla salvo escenario expresamente separado. |
| Slippage aislado | 0, 1, 2 y 5 bps por orden, manteniendo comisiones base. El escenario de 0 bps es un límite optimista. |
| Vida media | 12, 24 y 48 horas, ventana fija de 14 días. |
| Ventana de historia | 7, 14 y 28 días, vida media fija de 24 horas, con calentamiento adecuado. |
| Funding disponible | Demoras de señal de 60, 120 y 300 segundos; nunca una señal antes de la disponibilidad supuesta. |
| Espera entre patas | 1, 5 y 10 segundos desde el primer fill. |
| Horizonte y permanencia | Escenarios de 72, 168 y 336 horas, cambiando conjuntamente pronóstico, target H1 y ciclo de tenencia, claramente separados del base. |
| Precio de ejecución | Primera operación posterior frente a VWAP de una ventana posterior de 5 segundos, calculado con trades reales y ejecutado al terminar esa ventana. |

El escenario VWAP no puede usar esos cinco segundos de datos para decidir antes de conocerlos. Debe mantener el timeout de cada orden, la espera entre fills y la misma ventana para ambas carteras. Si no hay trades en la ventana, no fabriques un precio: registrá un intento sin fill y aplicá las reglas de expiración/reintento. Si se compara con open u OHLC4 como alternativa adicional, identificá la aproximación y el instante en que esa barra termina de conocerse.

Además:

- Mostrá resultados por año, por activo como atribución de la cartera y por los dos regímenes de H3.
- Para aislar sensibilidad a fecha inicial, agregá corridas separadas que comiencen el 01/01/2023 y el 01/01/2024 con el mismo capital y warmup. No las mezcles con el H3 principal, que no reinicia carteras.
- Medí monto de cada orden frente al volumen negociado de una ventana reciente y reportá distribución de participación. El baseline sigue suponiendo ejecución completa y no incorpora un impacto de mercado estimado sin datos.
- Agregá un diagnóstico de AUM con 10.000, 100.000 y 1.000.000 USDT usando las mismas reglas y compará participación, tramos y restricciones. Si faltan reglas para nocionales mayores, marcá ese escenario incompleto. Que las rentabilidades sean parecidas bajo fills completos no demuestra escalabilidad real.
- Analizá operaciones fallidas, liquidaciones, aperturas evitadas, señales no rentables, sensibilidad a costos y períodos sin exposición.

Mantené los escenarios sintéticos de fallas y extremos como pruebas del software, separados de los resultados históricos de robustez. No inyectes eventos artificiales dentro de una serie y la presentes como historia observada.

## 12. Salidas y reproducibilidad

Cada corrida debe tener identificador estable y un manifiesto con versión de Python y dependencias, versión de código o hash, configuración completa, origen y hashes de datos, fechas solicitadas, fechas cubiertas, convenciones y estado.

Estados mínimos: `complete`, `incomplete_data`, `insolvent` y `failed`. Registrá además si los datos son históricos o sintéticos. La insolvencia es un resultado económico, no una excusa para suprimir pérdidas. Un escenario sintético jamás debe rotularse como backtest histórico completo.

No sobrescribas resultados previos. Para comparar escenarios identificá cuál es el baseline y cuál la única dimensión modificada. Los mismos inputs y configuración deben reproducir las mismas decisiones, fills y saldos, excluyendo metadatos operativos como hora de creación.

Generá estos entregables bajo `outputs/<run_id>/`:

| Archivo o carpeta | Contenido |
|---|---|
| `run_manifest.json`, `effective_config.toml` | Reproducibilidad y estado real. |
| `data_quality_report.md`, `data_coverage.csv` | Fuentes, cobertura, faltantes, conflictos y criterios de validez. |
| `signals.parquet` | Forecasts, costo estimado, basis y motivos de aceptación/rechazo. |
| `orders.parquet`, `fills.parquet` | Tiempos de envío, deadline, trade usado, precios, cantidades, fees y causas. |
| `ledger.parquet`, `funding_payments.parquet` | Movimientos económicos auditables e identificadores únicos. |
| `positions.parquet`, `risk_events.parquet` | Estados, exposición, garantías, descalces y transiciones relevantes. |
| `equity_daily.csv`, `metrics.csv` | Curvas y métricas de ambas estrategias. |
| `forecast_evaluation.csv` | Observaciones, etiquetas, errores y resumen H1. |
| `opportunity_daily.csv`, `regime_comparison.csv` | Indicador de oportunidad y H3. |
| `robustness_summary.csv` | Configuraciones, cobertura y resultados de sensibilidad. |
| `figures/` | Gráficos PNG y SVG exportables. |
| `report.md` | Metodología, resultados, interpretación, limitaciones y próximos análisis. |

Cada tabla debe incluir `run_id`, identificador de estrategia cuando corresponda, activo, timestamps UTC y unidades bien definidas. Las tablas extensas pueden permanecer en Parquet; exportá a CSV los resúmenes destinados a la tesina.

Gráficos mínimos: equity comparada, drawdown, P&L por componente sin doble conteo, funding pronosticado contra realizado, oportunidad diaria con separación de regímenes y sensibilidad de métricas a costos. Mostrá fechas, unidades, leyendas y cobertura. Evitá escalas o títulos que sugieran una mejora no demostrada.

El informe debe responder a la Entrega 3: qué se implementó, período y frecuencias, supuestos y construcción de posiciones, resultados preliminares, relación con H1-H3, problemas y próximos ajustes. La sección de Entrega 4 cubre sensibilidad, ejecución, costos, liquidez, AUM, latencia y conclusiones críticas. Todo número y gráfico debe salir de las tablas de la corrida, no de valores escritos manualmente.

Documentá los límites expresos: USDT a la par, transferencias inmediatas y gratuitas, sin impuestos, insolvencia del exchange ni restricciones de liquidez dentro del fill base, ejecución total, mark por minuto, liquidaciones totales, sin ADL ni libro de órdenes completo. Aclarar estos límites no reemplaza ejecutar los controles definidos.

## 13. Pruebas financieras y temporales obligatorias

Usá fixtures pequeñas con resultados independientes calculables a mano. No pruebes una función replicando su propia fórmula en otra función idéntica. No dependas de internet en las pruebas unitarias.

| Caso | Resultado esperado |
|---|---|
| Tasa horaria constante de 0,00001 con intervalos de distinta duración, completos | EWMA y no-change pronostican 0,00168 en 168 horas. |
| Observación con antigüedad 0, 24 y 48 horas | Pesos relativos 1, 0,5 y 0,25. |
| Observación exactamente en el borde de 336 horas | Excluida de la suma, sin perder la referencia necesaria del primer intervalo. |
| Funding faltante entre dos tasas conocidas | No tratar el gap como un cambio de frecuencia; bloquear ventana. |
| Cambio de tasas o trades posteriores a un corte temporal | Ninguna decisión, fill o saldo anterior al corte cambia. Las etiquetas H1 se evalúan por separado. |
| Entrada con forecast igual a costo | No entrar; la condición es estricta. |
| Costo ilustrativo 0,10% spot, 0,05% Futures y 1 bp de slippage | Costo estimado del ciclo 0,34%. |
| Basis 0 y 0,005 | Ambos elegibles. Basis mayor que 0,005 o negativo bloquea entrada. |
| Basis de referencia 0,003 y actual 0,023 | Salida por ampliación de 2 puntos porcentuales. |
| Spot 100 a 110 y perpetuo 101 a 111, una unidad de cada uno, sin costos ni funding | P&L de precios cero, aunque varíe el basis porcentual. |
| Mismo caso con perpetuo final 112 | P&L de precios menos 1 USDT. |
| Short de 2 unidades, mark 100 y funding 0,001 | Crédito de 0,2 USDT; con tasa negativa, débito equivalente. |
| Compra spot de 10 unidades a 100 con comisión 0,001 | Se reciben 9,99 unidades; la comisión vale 1 USDT y no se descuenta nuevamente de caja. |
| Transferencia de 1.000 USDT de efectivo a garantía | Equity sin cambios. |
| Garantía 50, short 1, precio medio 100, mantenimiento 0,005 y deducción 0 | Precio de liquidación 150 / 1,005, dentro de un tramo que lo contenga. |
| Precio de liquidación que cruza un tramo | Selección de tramo consistente con el nocional de liquidación. |
| Funding negativo consume efectivo y luego garantía | Saldos y riesgo actualizados una sola vez; deuda solo por faltante residual. |
| Dos fuentes notifican el mismo funding o fill | Un solo movimiento económico por identificador. |
| Trade anterior, simultáneo al envío o exactamente en el deadline | No ejecuta; solo un trade estrictamente posterior y anterior al vencimiento puede hacerlo. |
| Spot llena en segundo 10 | La orden de cobertura no se envía antes del segundo 11. |
| Primera pata ejecuta, segunda vence | Desarme con costos conservados y sin borrar exposición mientras se cierra. |
| Cierre pendiente durante un funding | El short aún existente cobra o paga funding. |
| Funding y apertura/cierre al mismo timestamp | Se usa la posición anterior a esos fills. |
| Renovación con forecast positivo pero menor al costo de entrada | Renovar, si los demás controles lo permiten. |
| Renovación sin rebalanceo | Sin fills ni comisiones y sin cambiar referencia de basis. |
| Desvío de sizing exactamente 5% | No rebalancear; sí al superar el umbral. |
| Descalce exactamente 2% y luego superior | Solo el segundo activa corrección; a los 60 segundos debe quedar <= 0,5% o cerrar. |
| Corrección de hedge | Cambia solo perpetuo y conserva la referencia de basis. |
| Riesgo y renovación coinciden | Prioridad al riesgo, sin nueva exposición. |
| Trade obsoleto frente a archivo ausente | El primero activa reglas de frescura; el segundo invalida datos. |
| Cierre parcial y polvo spot | Garantía proporcional, P&L y comisiones correctos, remanente valuado. |
| H3 con BTC elegible 720 minutos a forecast 0,004 y ETH nunca elegible, día completo | Indicador conjunto de ese día 0,001. |
| H3 con día completo sin oportunidades | Indicador cero; con datos incompletos en un activo, excluir el día. |
| Mismo config y filtro desactivado en dos instancias | Igualdad de órdenes, ledger y equity, sin compartir estado mutable. |
| Corrida completa frente a replay por particiones y reanudación | Mismos saldos, decisiones y fills; sin pérdida de timers o ventanas. |
| Fin de muestra con par abierto | P&L no realizado incluido, sin cierre, funding posterior ni comisión terminal ficticia. |

Agregá una prueba integral del adaptador Nautilus que incluya las dos patas, un funding, una renovación, un cierre con retry y conciliación del equity. También una prueba de deuda e insolvencia y otra que confirme que una corrida con datos indispensables faltantes no se presenta como completa.

Verificá la identidad contable después de cada movimiento económico con tolerancia explícita coherente con la precisión usada. Usá Decimal o cantidades enteras escaladas para dinero, fees y redondeos donde corresponda; reservá floats para análisis estadístico. Una divergencia contable debe fallar visiblemente, no corregirse sumando un ajuste inexplicado.

## 14. Plan de implementación por hitos

Trabajá en este orden. Al cerrar cada hito, anotá archivos implementados, comandos ejecutados, resultado y limitaciones en `docs/progress.md`. Si un hito no puede verificarse, no lo marques como completado.

### Hito 1 Contrato del proyecto e integración mínima

- [ ] Inspeccionar la carpeta y fuentes, crear matriz de requisitos y registrar convenciones.
- [ ] Fijar dependencias, validar configuración y establecer CLI mínima.
- [ ] Verificar con una fixture el replay y los puntos de extensión reales de NautilusTrader.
- [ ] Probar prioridad de eventos, primer trade posterior, demora entre patas, funding único y corte final.

Salida verificable: entorno reproducible y prueba de integración mínima pasando. Si el motor presenta una limitación real, documentá APIs probadas y la adaptación concreta; no cambies de motor en silencio.

### Hito 2 Datos históricos y cobertura

- [ ] Implementar descarga, caché, normalización y manifiestos.
- [ ] Implementar esquemas y consulta de reglas por vigencia y disponibilidad.
- [ ] Probar cambio de unidades de timestamp, paginación, duplicados, huecos y cambio real de intervalos.
- [ ] Descargar una muestra acotada y producir un informe de calidad y cobertura real.

Salida verificable: datos validados y faltantes identificados. Si las reglas históricas están incompletas, conservar el bloqueo para evaluación estricta y seguir probando el software con fixtures claramente sintéticas.

### Hito 3 Forecast, ledger, sizing y margen

- [ ] Implementar EWMA y no-change con pruebas manuales.
- [ ] Implementar costos ex ante, comisiones realizadas y redondeos.
- [ ] Implementar ledger, transferencias, funding, deuda y conciliación.
- [ ] Implementar cantidades netas, garantías, tramos y liquidación.
- [ ] Ejecutar las pruebas numéricas correspondientes antes de conectar señales a órdenes.

Salida verificable: cálculos financieros independientes correctos y movimientos reconciliados.

### Hito 4 Estrategia y ejecución completas

- [ ] Implementar estados, entrada, expiración, renovación y rebalanceo.
- [ ] Implementar timeouts, desarme, retry, cooldown y descalce.
- [ ] Integrar riesgos y prioridad de liquidación.
- [ ] Ejecutar ambas estrategias mediante el mismo código y config compartida.
- [ ] Verificar ejecución por particiones y ausencia de look-ahead.

Salida verificable: backtest integral de fixtures, trazabilidad completa y comparación controlada.

### Hito 5 Caso histórico base y Entrega 3

- [ ] Ejecutar primero un intervalo real pequeño con todos sus datos indispensables verificados.
- [ ] Extender la corrida al período solicitado con lectura incremental y checkpoints.
- [ ] Generar H1, H2, H3, métricas, tablas, figuras e informe.
- [ ] Conciliar resultados con ledger y publicar el estado real de cobertura.

Salida verificable: resultados históricos del rango efectivamente validado. Si no se alcanza toda la muestra, el informe debe decir exactamente hasta dónde se llegó, por qué y qué falta para repetirla.

### Hito 6 Robustez y Entrega 4

- [ ] Ejecutar escenarios predefinidos de una variable por vez en ambas carteras.
- [ ] Comparar cobertura y supuestos para que las diferencias sean interpretables.
- [ ] Generar tablas y análisis de sensibilidad, ejecución, liquidez, AUM y latencia.
- [ ] Elaborar conclusiones descriptivas y próximos análisis sin retocar el baseline.

Salida verificable: resumen de robustez que incluye resultados favorables y desfavorables y escenarios no evaluables.

### Hito 7 Entrega reproducible

- [ ] Ejecutar pruebas pertinentes y una reproducción desde configuración guardada.
- [ ] Completar README, diccionario, metodología y matriz de trazabilidad.
- [ ] Confirmar que todo está dentro de `Backtesting` y que no se mezclaron datos sintéticos con históricos.
- [ ] Explicar al usuario cómo repetir el análisis y distinguir software terminado de cobertura histórica completa.

## 15. Comandos y criterio de aceptación

Exponé una CLI consistente mediante `python -m crypto_carry`. Debe cubrir estos comandos o equivalentes igualmente claros, y el README debe contener los comandos efectivamente probados:

| Acción | Interfaz esperada |
|---|---|
| Instalar entorno bloqueado | `uv sync --frozen` |
| Ejecutar pruebas | `uv run pytest` |
| Verificar entorno y configuración | `uv run python -m crypto_carry doctor --config configs/base.toml` |
| Descargar rango solicitado | `uv run python -m crypto_carry download --config configs/base.toml` |
| Normalizar y validar cobertura | `uv run python -m crypto_carry validate-data --config configs/base.toml` |
| Correr ambas carteras | `uv run python -m crypto_carry backtest --config configs/base.toml --strategy both` |
| Generar evaluación y reporte | `uv run python -m crypto_carry report --run-id <id_real_de_corrida>` |
| Ejecutar robustez | `uv run python -m crypto_carry robustness --config configs/robustness.toml` |
| Demo sin red | `uv run python -m crypto_carry demo` |

El identificador de `report` se obtiene de una corrida real; el README debe mostrar uno de ejemplo sin afirmar que sus resultados existen si todavía no se generaron. La demo debe utilizar exactamente el mismo motor y lógica con fixtures identificadas como sintéticas.

El trabajo está completo como software cuando los módulos y comandos funcionan, las pruebas verifican las reglas, el ledger concilia y las dos estrategias se ejecutan sin diferencias ajenas al filtro. Está completo como evaluación histórica únicamente cuando también existen datos indispensables verificados para todo el período informado y resultados reales reproducibles.

No entregues un esqueleto con funciones vacías ni resultados inventados. Si una restricción externa impide finalizar la evaluación histórica, entregá el proyecto funcional, su verificación y un listado preciso de datasets o reglas faltantes, con los pasos para completar la corrida.

En tu respuesta final informá brevemente qué implementaste, qué verificaste, qué período histórico efectivamente corriste, dónde están los resultados y cuál es el siguiente comando concreto. No presentes la estrategia como rentable antes de observar resultados válidos.

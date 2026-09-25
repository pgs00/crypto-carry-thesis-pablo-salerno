# Crypto carry: PRECIOS OBSERVADOS CON SUPUESTOS PRESCRIPTOS

Corrida `run_d3ebbfeb6f98be343782ccbb` · escenario `E4-reglas-BTC_PROMO_REALIZADA` · estado `complete`.

Los resultados se limitan a la cobertura verificada. Un prefijo incompleto es diagnóstico; no evalúa toda la muestra solicitada.

## Entrega 3: implementación, muestra y método

Se implementó replay con Nautilus, la máquina de estados compartida por carry condicional y permanente, ledger decimal, funding, reglas prescriptas declaradas, gestión de margen y deuda, conciliación y evaluación descriptiva. Las cantidades, decisiones y saldos se conservan en Parquet; este informe y las figuras usan exclusivamente las tablas guardadas.

Rango solicitado UTC: [2022-01-01T00:00:00Z, 2026-09-01T00:00:00Z); historia prevista en configuración desde 2022-01-01T00:00:00Z. El extremo final solicitado es exclusivo. Los extremos observados se muestran abajo. Cartera del intervalo solicitado con 10000 USDT iniciales por estrategia; no se reinician posiciones ni capital al cambiar de año o régimen. Cobertura completed_with_approximations: método `futures_scaled`, opción limitada a los 15 minutos documentados, con disponibilidad al minuto siguiente. Se conserva la aproximación de funding vigente.

| strategy | funding_filter_enabled | start | end | status | capital_usdt | final_equity_usdt | debt_usdt | reasons |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| permanent | False | 2022-01-01T00:00:00Z | 2026-08-31T23:59:59.999999999Z | complete | 10000 | 11683.38048945462628528569999 | 0E-27 | [] |


Convencion de ejecucion por minuto cerrado: cada orden usa el VWAP, calculado como volumen cotizado dividido por volumen base, del primer minuto completo que comienza al momento de envio o despues. El fill se registra al cierre de ese minuto, cuando precio y volumen ya son conocidos. La capacidad maxima es 1% del volumen base observado; la cantidad restante vence al cierre. Una ejecucion parcial produce un solo evento nativo.

| parameter | value |
| --- | --- |
| capital | 10000 |
| window_hours | 336 |
| half_life_hours | 24 |
| horizon_hours | 168 |
| holding_hours | 168 |
| signal_delay_seconds | 60 |
| target_fraction | 0.30 |
| leverage | 2 |
| slippage | 0.0001 |
| cost_multiplier | 1 |
| leg_delay_seconds | 1 |
| order_timeout_seconds | 120 |
| participation_seconds | 60 |
| execution_model | next_minute_vwap |
| sizing_model | joint_quantity |
| signal_price_model | closed_minute |
| max_volume_participation | 0.01 |


### Cobertura, bloqueos y reglas

| dataset | symbol | market | expected_start_utc | expected_end_utc | observed_start_utc | observed_end_utc | rows | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| minute_bars | BTCUSDT | spot | 2022-01-01T00:00:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 2022-01-01T00:00:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 2453681 | complete |
| minute_bars | BTCUSDT | futures | 2022-01-01T00:00:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 2022-01-01T00:00:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 2453761 | complete |
| marks | BTCUSDT | futures | 2022-01-01T00:00:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 2021-12-01T00:01:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 2498400 | complete |
| funding | BTCUSDT | futures | 2021-12-17T00:00:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 2021-12-16T16:00:00.000000000Z | 2026-08-31T16:00:00.001000000Z | 5201 | complete |
| minute_bars | ETHUSDT | spot | 2022-01-01T00:00:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 2022-01-01T00:00:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 2453681 | complete |
| minute_bars | ETHUSDT | futures | 2022-01-01T00:00:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 2022-01-01T00:00:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 2453761 | complete |
| marks | ETHUSDT | futures | 2022-01-01T00:00:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 2021-12-01T00:01:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 2498400 | complete |
| funding | ETHUSDT | futures | 2021-12-17T00:00:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 2021-12-16T16:00:00.000000000Z | 2026-08-31T16:00:00.001000000Z | 5201 | complete |


No se registraron bloqueos adicionales.

### Cierres documentados de mercado

Estos cierres publicados por la fuente son evidencia ex post de cobertura. No se clasifican como datos faltantes, no generan barras sintéticas y no se entregaron anticipadamente a la estrategia.

| symbols | market | start_utc | end_utc | minutes | source_url | description |
| --- | --- | --- | --- | --- | --- | --- |
| BTCUSDT, ETHUSDT | spot | 2023-03-24T11:28:00.000000000Z | 2023-03-24T14:00:00.000000000Z | 152 | https://www.binance.com/en/blog/from-our-ceo/6789340645608890113 | Binance spot trading halt; full unavailable minutes after the 11:27 partial minute |


### Resultados diarios, anuales y por régimen

Las métricas usan calendario real, anualización de 365 días, Sharpe con tasa libre de riesgo cero y desviación estándar muestral. El primer retorno parte del capital inicial. Las métricas indefinidas quedan vacías con motivo; se conservan días inactivos, pérdidas e insolvencia. Los días parciales permanecen en la curva y no se usan como retornos diarios completos.

| strategy | period | start | end | observations | coverage_complete | net_return | cagr | sharpe | annual_volatility | max_drawdown | max_drawdown_days | cagr_reason | sharpe_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| permanent | full | 2022-01-01T00:00:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 1704 | True | 0.16833804894546267 | 0.03388754609592004 | 6.543972219536867 | 0.005094838222508591 | -0.00478261652480183 | 154.0 | — | — |
| permanent | 2022-2023 | 2022-01-01T00:00:00.000000000Z | 2024-01-01T00:00:00.000000000Z | 730 | True | 0.0619248121977376 | 0.030497361567576986 | 4.637062925125143 | 0.006483354855339346 | -0.00478261652480183 | 143.0 | — | — |
| permanent | 2024+ | 2024-01-01T00:00:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 974 | True | 0.10020788244649292 | 0.036435754281543886 | 9.601177444137601 | 0.0037283306560628605 | -0.0032322176102658196 | 154.0 | — | — |
| permanent | 2022 | 2022-01-01T00:00:00.000000000Z | 2023-01-01T00:00:00.000000000Z | 365 | True | 0.011076489699056502 | 0.011076489699056502 | 2.6659250949692046 | 0.00413525892815119 | -0.00478261652480183 | 134.0 | — | — |
| permanent | 2023 | 2023-01-01T00:00:00.000000000Z | 2024-01-01T00:00:00.000000000Z | 365 | True | 0.050291271745242394 | 0.050291271745242394 | 6.08623210420022 | 0.00806790760996572 | -0.0012932707577797409 | 13.0 | — | — |
| permanent | 2024 | 2024-01-01T00:00:00.000000000Z | 2025-01-01T00:00:00.000000000Z | 366 | True | 0.06470718265129238 | 0.06452480225202839 | 11.738524517526612 | 0.005328439402494508 | -0.0032322176102658196 | 24.0 | — | — |
| permanent | 2025 | 2025-01-01T00:00:00.000000000Z | 2026-01-01T00:00:00.000000000Z | 365 | True | 0.027285095715736674 | 0.027285095715736674 | 13.681908449702572 | 0.001967738366427902 | -0.00044808196419421353 | 16.0 | — | — |
| permanent | 2026 | 2026-01-01T00:00:00.000000000Z | 2026-09-01T00:00:00.000000000Z | 243 | True | 0.005897157752066784 | 0.008870970697021807 | 6.323551461640334 | 0.0013968310724198935 | -0.001978550320687167 | 154.0 | — | — |


![Equity en USDT](figures/equity.png)

![Drawdown](figures/drawdown.png)

### Hipótesis: lecturas descriptivas

H1: favorable.

| period | symbol | observations | excluded | mae_ewma | mae_no_change |
| --- | --- | --- | --- | --- | --- |
| full | BTCUSDT | 5090 | 22 | 0.0005738673687550346 | 0.0007883688661062381 |
| full | ETHUSDT | 5090 | 22 | 0.0006859281684077234 | 0.0009522955567889762 |
| full | EQUAL_WEIGHT | 10180 | 44 | 0.000629897768581379 | 0.0008703322114476072 |
| 2022-2023 | BTCUSDT | 2190 | 0 | 0.0006289535940745395 | 0.0008781982522651852 |
| 2022-2023 | ETHUSDT | 2190 | 0 | 0.0008478924536525869 | 0.0011770984092330681 |
| 2022-2023 | EQUAL_WEIGHT | 4380 | 0 | 0.0007384230238635632 | 0.0010276483307491266 |
| 2024+ | BTCUSDT | 2900 | 22 | 0.0005322677710137531 | 0.0007205321917310335 |
| 2024+ | ETHUSDT | 2900 | 22 | 0.0005636172081710851 | 0.0007825306440811964 |
| 2024+ | EQUAL_WEIGHT | 5800 | 44 | 0.0005479424895924191 | 0.0007515314179061149 |


Ambos pronósticos usan las mismas observaciones válidas; el MAE conjunto da igual peso a cada activo. El objetivo suma tasas liquidadas después de la señal y hasta el extremo inclusivo del horizonte. Los horizontes se solapan: estas comparaciones no establecen significancia estadística. Un menor error predictivo no demuestra rentabilidad.

H2: no concluyente: faltan dos carteras comparables o métricas válidas.

H3: no concluyente: cobertura insuficiente de ambos regímenes. En las ventanas de evaluación por minuto, la clasificación anterior/posterior a 2024 es descriptiva dentro de esta corrida; un informe de una sola ventana no establece una comparación entre ventanas reiniciadas independientemente.

| period | observed_days | valid_days | coverage_complete | opportunity_mean | eligible_fraction | conditional_cagr | h3_descriptive |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-2023 | 730 | 730 | False | 0.00013404148677285764 | 0.02495148401826484 | — | no_concluyente |
| 2024+ | 974 | 974 | False | 0.0004019673830496383 | 0.0635837326032398 | — | no_concluyente |


La oportunidad promedia todos los minutos de días completos, incluyendo ceros, y pondera por igual los activos. No depende del saldo, posiciones o cooldown de una cartera. Un minuto desconocido excluye el día conjunto. La clasificación temporal de esta ventana no enlaza capital, posiciones ni equity con otra corrida de evaluación.

![Funding pronosticado y realizado](figures/forecast.png)

![Oportunidad diaria](figures/opportunity.png)

### Atribución, costos y cierre de la muestra

| strategy | symbol | spot_pnl_usdt | futures_pnl_usdt | funding_usdt | fees_usdt | liquidation_fees_usdt | total_pnl_usdt | slippage_informational_usdt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| permanent | BTCUSDT | 2493.604057171400000000000000 | -2449.090400000000000000000006 | 946.6070299632576497722 | -101.4549413514 | 0 | 889.665745783257649772199994 | 13.72115862682556778365190036 |
| permanent | ETHUSDT | -74.858514478999999999999999 | 142.080230004249999999999996 | 851.1013783911186355135 | -124.608350245 | 0 | 793.714743671368635513499997 | 16.71090054827368526800282144 |


La suma de spot, perpetuos, funding y comisiones negativas reconcilia con equity menos capital inicial. El slippage es informativo: ya está en los precios de fill y no se resta otra vez. Spot usa el último open de barra de un minuto conocido y perpetuos el último mark disponible; no se mezcla un basis de ejecución con una valuación mark para forzar la identidad. La comisión de compra spot reduce inventario; se valora al fill. La conciliación nativa ajusta las unidades base cobradas como comisión porque el ledger económico conserva ese descuento. Las posiciones finales se valúan sin cierre forzado ni comisiones hipotéticas.

![P&L por componente](figures/pnl_components.png)

| strategy | symbol | timestamp_utc | state | spot | short | collateral | dust_spot | spot_price | mark_price | spot_price_age_seconds | mark_age_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| permanent | BTCUSDT | 2026-08-31T23:59:59.999999999Z | HOLDING | 0.03200125 | 0.032 | 1577.956519163189573970541177 | 0.00000125 | 78564.00000000 | 78528.00000000 | 59.999999999 | 60.000999999 |
| permanent | ETHUSDT | 2026-08-31T23:59:59.999999999Z | HOLDING | 1.0750247 | 1.075 | 2296.710030406850177615885518 | 0.0000247 | 2467.28000000 | 2466.01725581 | 59.999999999 | 60.000999999 |


El polvo forma parte del inventario y del patrimonio. Una valuación antigua conserva su antigüedad; no habilita ejecución ni señales frescas. La deuda y cualquier equity no positivo permanecen en las tablas.

## Entrega 4: ejecución, liquidez y análisis crítico

| strategy | symbol | orders | fills | failed_attempts | openings | renewals | rebalances | corrections | closes | liquidations | blocked_orders | rejected_signals | turnover_usdt | risk_events |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| permanent | PORTFOLIO | 727 | 324 | 407 | 20 | 458 | 125 | 0 | 20 | 0 | 0 | 10204 | 300422.0921164 | 1430 |
| permanent | BTCUSDT | 384 | 148 | 236 | 9 | 234 | 58 | 0 | 8 | 0 | 0 | 5103 | 136439.8207414 | 727 |
| permanent | ETHUSDT | 343 | 176 | 171 | 11 | 224 | 67 | 0 | 12 | 0 | 0 | 5101 | 163982.271375 | 703 |


| strategy | symbol | invested_seconds | unhedged_seconds | cash_seconds | cooldown_seconds | participation_observations | participation_missing | participation_p50 | participation_p90 | participation_p95 | participation_max | native_fill_count | native_reconciliation_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| permanent | PORTFOLIO | 146966279.999999999 | — | 259320.000000000 | — | 318 | 409 | 9.616593443290283e-05 | 0.0010259477328313509 | 0.002421541054273473 | 0.015719789932276577 | 324 | 324 |
| permanent | BTCUSDT | 146966279.999999999 | 2697480.000000000 | — | 813180.012000000 | 145 | 239 | 6.197441819965554e-05 | 0.0006454458480206848 | 0.001481555129849161 | 0.015719789932276577 | — | — |
| permanent | ETHUSDT | 146851019.999999999 | 7877940.000000000 | — | 1067760.016000000 | 173 | 170 | 0.0001383346561870175 | 0.0013412042129777842 | 0.004948808234600072 | 0.014100291566690284 | — | — |


Los tiempos se expresan en segundos. La exposición sin cobertura se muestra por activo, incluyendo intervalos entre patas. El tiempo invertido de cartera es la unión temporal de activos expuestos; no la suma. La participación es cantidad de cada orden frente al volumen reciente del mismo mercado conocido al enviarla, incluyendo órdenes sin fill; si no existe denominador verificable queda vacía. Sus cuantiles describen órdenes y no estiman impacto de mercado. Para la ejecución por minuto, el denominador es el volumen del minuto cerrado anterior, una aproximación del volumen móvil de 60 segundos; el volumen no está disponible antes del cierre de la barra.

### Robustez pendiente o ejecutada

| label | strategy | dimension | value | status | cagr | sharpe | coverage_complete | scenario_evaluated |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E4-reglas-BTC_PROMO_REALIZADA | permanent | baseline | 1 | complete | 0.03388754609592004 | 6.543972219536867 | True | False |


Sin escenarios de costos evaluados en esta corrida individual. Las comparaciones reales de sensibilidad se guardan por separado y no se reemplaza el baseline ni se elige retrospectivamente el mejor escenario.

![Sensibilidad a costos](figures/cost_sensitivity.png)

AUM: sensibilidad pendiente de ejecutar y validar con reglas aplicables al nocional. También deben compararse costos, slippage, latencia entre patas, disponibilidad del funding, ventana, vida media, horizonte, e inicios alternativos en sus propias corridas. Retornos similares bajo fills completos no demuestran escalabilidad.

### Supuestos y límites

USDT a la par; transferencias inmediatas y gratuitas; ejecución total de cada pata; mark por minuto; liquidación total; sin ADL, libro completo, impuestos ni insolvencia del exchange. El baseline no incorpora restricciones de liquidez dentro del fill ni impacto estimado sin datos. Los fallos artificiales son pruebas de software separadas de la historia observada. Las liquidaciones por minuto no modelan una trayectoria intraminuto de máximos y mínimos; el riesgo usa el último mark de un minuto cerrado disponible.

### Reproducibilidad y próximos pasos

La configuración efectiva, hashes de código e inputs, versiones, estado y hashes de artefactos están en `run_manifest.json`; `run_manifest.sha256` controla cambios accidentales del manifiesto. `source_manifests/` conserva los manifiestos de descarga, procesamiento y cobertura disponibles al crear la corrida; `input_hashes` identifica los inputs efectivos. La verificación no certifica autenticidad externa. Los importes Parquet son cadenas decimales exactas; las figuras convierten copias a punto flotante para dibujar. La regeneración usa las tablas guardadas y rechaza cambios sobre resultados previos. Completar los bloqueos de cobertura y reglas precede a cualquier conclusión histórica de muestra completa.

### Declaración del escenario de investigación

Los precios y tasas son observados; los marks sustituidos y las reglas de mercado son supuestos prescriptos declarados en 2026. Esta corrida no certifica una reconstrucción histórica. H2 y H3 se evalúan dentro de ese escenario, por separado de la cobertura histórica estricta. `research_assumptions.json` declara las reglas y `funding_mark_audit.json` separa los marks validados de los usados, con conteos exactos y sustituidos. El motor consumió 6214 exactos, 4010 proxies causales y 92 observaciones de precalentamiento sin imputación. Son observaciones entregadas al motor y no implican, por sí solas, pagos de funding en efectivo.

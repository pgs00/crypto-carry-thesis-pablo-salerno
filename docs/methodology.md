# Metodología de las carteras continuas

## Alcance vigente

Esta página describe el contrato de la **BASE continua**. La
[Entrega 4](../entregas/entrega_4/README.md) reúne la corrección de exposición/H2,
el riesgo intradía y los protocolos particulares de los bloques 1–6.
Las variantes se interpretan dentro de su bloque y escenario; sus parámetros
no se incorporan a BASE ni se combinan entre bloques por defecto.

Se comparan dos carteras independientes entre sí, condicional y permanente,
desde **01/01/2022 hasta 31/08/2026 UTC**, intervalo
`[2022-01-01T00:00:00Z, 2026-09-01T00:00:00Z)`. Cada una comienza con 10.000 USDT.
No se reinician capital, posiciones, ciclos ni pronósticos al cambiar de año.
Los cortes `[2022-01-01, 2024-01-01)` y `[2024-01-01, 2026-09-01)` conservan
los saldos de entrada de la trayectoria continua.

Las corridas principales son `run_ad71d751b20623006c195ff3` (condicional) y
`run_dfea4b7ac1475668d5968c97` (permanente), con `futures_scaled`. Sus parámetros
provienen de `configs/download_minutes_2022_2026_d.toml` y de las configuraciones
efectivas conservadas en el [ZIP vigente](../entregas/entrega_3/paquete_actualizacion_entrega_3_continua.zip).

Las ventanas independientes de septiembre de 2022–agosto de 2023 y septiembre
de 2025–agosto de 2026, cada una iniciada con capital nuevo, son
[antecedentes archivados](../entregas/entrega_3/archivo/README.md). La ampliación
continua conserva `next_minute_vwap` y `joint_quantity` de la revisión por minuto.

## Datos y causalidad

Universo: spot y perpetuos USD-M de BTCUSDT y ETHUSDT. Se usan OHLC y volúmenes
de un minuto, tasas de funding en sus timestamps reales y mark prices de un
minuto. Los timestamps internos son UTC en nanosegundos. Los datos spot desde
2025 se normalizan desde microsegundos; los anteriores y futuros desde milisegundos.
El calentamiento de diciembre de 2021 informa los pronósticos y no genera P&L.

Una vela se conoce al cerrar, en el límite del minuto siguiente; no se utiliza
su high, low o close antes. El basis usa cierres spot/perpetuo alineados del
mismo minuto cerrado, con actividad positiva y frescura máxima de 60 segundos:
`basis = futures_close / spot_close − 1`. El mark valúa el riesgo; no es un
precio ejecutable. Las ausencias desconocidas bloquean cobertura. El calendario
documentado de interrupción spot del 24/03/2023 clasifica cobertura, sin anunciar
anticipadamente la suspensión a la estrategia.

La cobertura estricta original tiene 15 marks ausentes. La opción explícita
`futures_scaled` estima `mark[t] = futures_close[t] × mark_close[s] / futures_close[s]`,
donde `s` es el último minuto oficial anterior al hueco. Mantiene esa ancla en
huecos consecutivos y escala los OHLC con el mismo factor, sin agregar basis.
La sensibilidad `last_official` mantiene constante el cierre oficial anterior.
Sólo se admiten los 15 minutos documentados, con datos ya cerrados; las fuentes
originales siguen intactas. La cobertura se considera **completada mediante
aproximaciones**, no enteramente oficial. La validación estricta sigue siendo
el valor predeterminado. Ver [reglas y evidencia de marks](continuous_mark_gaps.md).

## Funding y pronóstico

Se conserva el precio oficial de liquidación cuando existe. De 10.224
observaciones económicas, 6.214 tienen precio oficial y 4.010 usan
`previous_closed_1m`: el cierre del minuto inmediatamente anterior al límite
truncado del funding, disponible antes o en su timestamp real. Se respetan
los milisegundos; no se usa el precio posterior ni se altera la tasa.
Esta aproximación es distinta de los 15 huecos de velas de mark.

El funding se calcula sobre el short existente **antes de los fills del mismo
instante**: `q × mark_de_cobro × tasa`. Una tasa positiva produce un ingreso
para el short. La tasa queda disponible para señales 60 segundos después del
cobro. Los pronósticos nunca usan las tasas futuras que después servirán como
objetivo de H1.

En un ancla `a`, se toman tasas con `a − 336h < t_i <= a` y un antecedente para
medir el primer intervalo. Con duración real `d_i` en horas y
`w_i = 2^(-(a-t_i)/24h)`:

`forecast = 168 × sum(w_i × funding_rate_i) / sum(w_i × d_i)`.

`no_change = 168 × última_tasa / último_intervalo_horas`.

El costo ex ante es `2 × fee_spot + 2 × fee_futures + 4 × slippage`:
0,10% spot, 0,05% futuros y 1 bp de slippage por orden producen **0,34%**.
Son tarifas y reglas prescritas del escenario, no una serie histórica certificada.

## Carteras, sizing y ejecución

La condicional exige `forecast > costo` para entrar y `forecast > 0` para
renovar. La permanente omite sólo esas condiciones; conserva basis, fondos,
operatividad y riesgos. Un fallo de funding en su diagnóstico no es un rechazo
aplicado. El filtro de entrada de basis es inclusivo `[0, 0,005]`.

El objetivo spot es `0,30 × equity` por activo. `joint_quantity` calcula antes
de comprar una pareja viable, neta de comisión spot, con fondos, margen, filtros
y desbalance máximo de 0,5%. Incluye polvo existente y redondea cantidades/ticks.
La compra spot paga fee en base; ventas spot y operaciones de futuros en USDT.
La garantía de otra posición no se reutiliza como efectivo disponible.

`next_minute_vwap` ejecuta en una única ventana completa que comienza en
`ceil(envío / minuto) × minuto`. Una orden a las 12:01 usa `[12:01,12:02)` y
registra el fill a las 12:02; a las 12:01:15 usa `[12:02,12:03)`. El precio es
`volumen_cotizado / volumen_base`, con slippage y tick adversos. No se usa OHLC4
ni un recorrido intraminuto reconstruido. La participación agregada máxima por
instrumento/minuto/cartera es 1% del volumen base observado, compartida entre
órdenes. Volumen cero impide fills; capacidad observada no garantiza liquidez real.

La secuencia de entrada es spot → futuro, enviando la segunda pata después de
completar la primera; los cierres son futuro → spot. Los parciales, cancelaciones,
remanentes y reintentos se concilian con el inventario real. Una apertura parcial
fallida se desarma; no se presupone una cobertura completa. NautilusTrader mantiene
órdenes y fills; el ledger Decimal concilia cantidades y economía.

Orden temporal: incorporar datos → liquidar funding sobre el short previo →
contabilizar fills comprometidos → riesgo/estado → vencimientos y reintentos →
decisiones. Un riesgo detectado al cierre no borra un fill del intervalo acabado.
Se mantienen tenencias de 168 horas, renovables; se rebalancea al renovar si el
desvío del objetivo supera 5%. No se aplica el filtro de basis de entrada a la renovación.

Las reservas de ambos activos usan un snapshot común del equity y prioridad
BTC→ETH. Una primera pata de rebalanceo fallida sin fills conserva el par en
HOLDING, libera la reserva y bloquea ampliaciones durante 24 horas; permite
renovar la tenencia existente si cumple sus controles. En `next_minute_vwap`,
una primera pata parcialmente ejecutada que falla se desarma; una falla de
segunda pata también desarma el par. Una suspensión conserva inventario e
intención de cierre hasta poder negociar. Polvo es cantidad inferior a los
filtros de cantidad o nocional mínimo, y sigue valuado.

## Motor y reproducción de estado

[NautilusTrader](../pyproject.toml) 1.231.0 gestiona órdenes, fills y posiciones
nativas. El adaptador deshabilita el matching automático de trades/barras y
usa órdenes límite inertes como portadoras del ciclo de vida. Sus precios
límite no son precios económicos: el motor del estudio determina elegibilidad
y precio de cada fill. La cuenta nativa permanece congelada y sus comisiones
son cero; sólo el ledger del proyecto contabiliza dinero y funding.

La posición spot nativa bruta se concilia con spot neto más comisiones
acumuladas en unidades base; el futuro nativo se concilia con el short del
ledger. Cada fill exige coincidencia de cantidad, precio y reloj. El equity
nativo no es el resultado de la tesina. Dinero y cantidades usan Decimal;
la tolerancia contable de 1e-8 USDT no amplía los umbrales de riesgo. Las
portadoras nativas tienen ocho decimales y una divergencia visible falla.

`manage_stop=False` evita liquidaciones terminales. Los timers se conservan
entre particiones. Los checkpoints JSON vinculan hashes de configuración,
reglas, inputs y código; reconstruyen las portadoras sin nuevos movimientos
del ledger y no usan pickle. Cambiar esa identidad requiere otra corrida.
Ante datos indispensables desconocidos con exposición, la estrategia se
detiene conservando posición, deuda y estado. La validación estricta fallida
produce un diagnóstico, sin fabricar una curva de efectivo.

## Riesgo y contabilidad

Se conserva apalancamiento aislado 2x. Garantía al aumentar short:
`q × fill / 2 + max(0, q × (mark − fill))`. Para el short,
`UPnL = q × (precio_medio − mark)` y `margin_balance = garantía + UPnL`.
Mantenimiento = `q × mark × tasa_del_tramo − deducción`, según reglas prescritas.

Se conservan la liquidación si el saldo no cubre mantenimiento y la salida preventiva
por ratio de mantenimiento >= 0,50 o distancia de liquidación < 0,15. El descalce
`> 2%` activa corrección de futuros hacia `<= 0,5%`; se evalúa al terminar la ventana
elegible, con los controles de riesgo activos. La inactividad > 30 minutos
provoca salida y el ensanchamiento de basis >= 0,02 frente a la referencia del
par activa su control. Los cargos de liquidación siguen los supuestos guardados.

Funding negativo usa caja futures, garantía del mismo contrato y caja spot libre;
el remanente es deuda. No se crea dinero ni se trunca equity negativo. Transferencias
y constitución/liberación de garantía no producen P&L. Al fin exclusivo se valúan
posiciones abiertas sin inventar cierre, fee terminal, funding o fill posterior.
Para realizar deuda se actúa primero sobre BTC y se reevalúa antes de ETH;
las liquidaciones independientes conservan prioridad.

`equity = caja_spot + caja_futures + garantías + spot × precio_spot + UPnL_futures − deuda`.

La atribución concilia P&L spot y futuros (realizado/no realizado), funding,
comisiones y cargos de liquidación con el cambio de equity. Slippage ya está en
los precios y sólo se muestra como diagnóstico; no se resta dos veces.

## Evaluación

H1 compara el funding realizado acumulado en `(señal, señal+168h]` contra EWMA
y no-change. Usa muestras emparejadas por activo y promedia sus MAE con peso
BTC/ETH 50/50. Hay 10.180 observaciones válidas y 44 exclusiones: 42 horizontes
fuera de muestra y dos límites de calendario no verificables. Los cortes se
asignan por fecha de señal; un horizonte de diciembre de 2023 puede finalizar
en 2024. Los horizontes solapados no son observaciones independientes.

H3 se calcula en cada minuto UTC, **independientemente de las posiciones**:
forecast semanal completo si pasa funding/costo, basis y operatividad; cero
si los datos son conocidos y falla un filtro. No se resta el costo al forecast.
Se promedian los 1.440 minutos de cada día por activo y luego BTC/ETH 50/50.
Datos desconocidos excluyen el día conjunto; las ausencias de la suspensión
spot documentada son ceros operativos. Hay 1.704 días válidos. Se conserva la
publicación exacta: una señal disponible a 00:01:00.006 entra en la grilla a 00:02.

Retornos y drawdown usan equity al cierre UTC. CAGR usa duración/365; Sharpe
usa desviación muestral (`ddof=1`), raíz de 365 y RF cero. Los cortes usan su
saldo inicial real, sin reiniciar carteras; los retornos de tramos no se suman.
Tiempo invertido excluye polvo; el tiempo de cartera es la unión de intervalos
por activo. Capital utilizado al cierre = valor spot + garantía aislada, dividido
por equity; es una medida diaria, y puede superar 100% por la valuación del short.

H2 exige CAGR condicional finito y positivo y Sharpe condicional finito superior
al permanente, también finito, para el mismo escenario y período. Con los
componentes evaluables y alguna condición incumplida es `no_favorable`;
con métricas ND o ventanas no comparables es `no_concluyente`, conservando
el motivo. No se sustituye el Sharpe de volatilidad nula por cero. La
[guía corregida de métricas](../entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/documentos/guia_metricas.md)
fija la clasificación y la exclusión de polvo de exposición/actividad.
H3 contrasta
oportunidad y CAGR condicional entre ambos regímenes. Son comparaciones descriptivas,
no pruebas causales ni garantías de rentabilidad. El
[análisis del precio de funding](../data/research/funding-price-sensitivity-20260920/README.md)
cuantifica efectos con posiciones fijas y escenarios P95 ilustrativos; no incluye
cambios de decisiones o margen ni garantiza extrapolación a los precios ausentes.

Los [resultados conservados de E3](../entregas/entrega_3/continua/README.md) se regeneran
desde el ZIP verificado, sin nuevas simulaciones. Los datos masivos y corridas
completas siguen locales; hashes y configuraciones preservan su trazabilidad.

## Alcances adicionales de Entrega 4

El drawdown de cierres diarios, la reconstrucción intradía global de
BASE/MARGEN_2X y las ventanas locales B4/B5 tienen poblaciones distintas.
Las ventanas locales no acreditan máximos intradía globales. La suspensión
spot conserva la distinción entre precio antiguo y proxy hipotético.

El comparador SOFR aprobado es una cuenta hipotética bruta USD, ACT/360,
con paridad nominal 1 USDT = 1 USD y CAGR365. No remunera caja o garantías
del carry ni representa un producto accesible o una rentabilidad realizada
libre de riesgo. B3 mantiene la selección ex ante a 34 pb mientras varía
costos, participación o capital. B4 distingue la demora de órdenes desde
`eligible_at` de la liquidación, que conserva prioridad. B5 interviene
trayectorias hipotéticas aprobadas; su recuperación impuesta y sus anclas
fijas no identifican el costo causal histórico de una interrupción.

B6 compara cuentas nuevas desde I2023/I2024 con sus pares, separadas de los
cortes BASE con saldos heredados. Es una evaluación retrospectiva. El
bootstrap de BASE usa bloques circulares emparejados dentro de año/segmento,
28 días principal y 14/56 como sensibilidad, 5.000 réplicas por longitud e
intervalos percentiles marginales nominales 95%. Esos intervalos dependen
de los supuestos de remuestreo y no constituyen una prueba conjunta al 95%
de H2 ni probabilidades de ganancia futura. No ejecutan el motor.

Los protocolos, límites y la síntesis integrable se consultan desde el
[índice único E4](../entregas/entrega_4/README.md). La verificación de hashes,
la recomputación de evidencia compacta y el replay económico son alcances
distintos; ninguno convierte reglas prescritas en historia certificada.

La [guía única de reproducción](reproduction.md) distingue lectura, evidencia
compacta y datos masivos. `configs/base.toml` y `configs/robustness.toml` son
perfiles anteriores del CLI con `first_trade`; no son las configuraciones
efectivas de BASE continua/E4. Se conservan sin cambiar sus parámetros.

## Limitaciones e interpretación

La rentabilidad no determina la validez de una corrida: se conservan resultados
adversos y se exige procedencia, causalidad y conciliación. Un checksum prueba
integridad, no cobertura; coincidir entre productos del mismo proveedor no
descarta omisiones compartidas. Los tests verifican casos del software, sin
estimar una probabilidad de éxito económico ni probar ausencia de errores.

Se supone USDT a la par de USD, transferencias instantáneas y gratuitas y
efectivo sin remuneración. No se modelan impuestos, insolvencia del exchange,
ADL ni liquidaciones parciales. VWAP, participación y slippage fijo no
reconstruyen spread, profundidad, colas o impacto, ni acreditan liquidez
accesible. El mark cerrado por minuto puede omitir extremos que afecten margen
o liquidación. Latencia, rechazos, desconexiones y reintentos no están
calibrados contra operativa real.

Una eventual prueba con capital requiere validación independiente no utilizada
para ajustar parámetros, observación en vivo sin órdenes y revisión operativa
separada. El backtest no establece límites aceptables de pérdida, capital o
duración ni acredita preparación para operar.

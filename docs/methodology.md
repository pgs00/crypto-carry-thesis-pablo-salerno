# Metodología

## Diseño y datos

Se comparan dos cuentas independientes de 10.000 USDT, con BTCUSDT y ETHUSDT en
spot y perpetuos USD-M de Binance. La muestra comprende el intervalo UTC
`[2022-01-01, 2026-09-01)`, de 1.704 días. Capital, posiciones y pronósticos
continúan entre años. Los cortes 2022–2023 y enero de 2024–agosto de 2026 heredan
sus saldos de entrada. El historial previo prepara el pronóstico sin producir
rentabilidad evaluada.

La referencia es [BASE_E3.toml](../configs/reglas_historicas/BASE_E3.toml), con
reglas prescritas en [prescribed.py](../src/crypto_carry/data/prescribed.py).
El [paquete continuo](../data/evidence/carteras_continuas.zip) conserva las
configuraciones efectivas y la evidencia de las dos cuentas.

Los datos son velas y volúmenes de un minuto, eventos de funding y mark prices.
Una vela informa decisiones una vez cerrada. El basis utiliza cierres spot y
futuro alineados, con actividad positiva y antigüedad máxima de 60 segundos:
`futuro / spot − 1`. El mark valúa el riesgo; las órdenes usan precios de
negociación. Los [campos y unidades](data_dictionary.md) distinguen el momento
del evento de su disponibilidad.

BASE aproxima 15 marks ausentes multiplicando el cierre del futuro por la
relación mark/futuro del último minuto oficial anterior. Conserva esa ancla
para faltantes consecutivos y escala los OHLC con el mismo factor. La
sensibilidad alternativa mantiene el último mark oficial. De 10.224 eventos
económicos de funding, 6.214 tienen precio de liquidación oficial y 4.010
utilizan el cierre de mark anterior al minuto del evento. Las tasas y los
timestamps efectivos permanecen intactos.

## Pronóstico y reglas de cartera

El EWMA usa una ventana de 336 horas y semivida de 24 horas. Para un ancla `a`,
una tasa `r_i`, su intervalo real en horas `d_i` y peso
`w_i = 2^(-(a − t_i)/24h)`, el pronóstico es:

`forecast = 168 × sum(w_i × r_i) / sum(w_i × d_i)`.

El comparador de última tasa es `168 × última_tasa / último_intervalo_horas`.
Cada tasa puede informar señales 60 segundos después de su liquidación.

| Regla BASE | Aplicación |
|---|---|
| Entrada condicional | Pronóstico de 168 horas superior al costo del ciclo completo: 34 pb. |
| Renovación condicional | Pronóstico positivo al terminar una tenencia de 168 horas. |
| Incondicional | Omite esas dos condiciones de funding y conserva las demás reglas. |
| Basis de entrada | Entre 0 y 0,50%, inclusive; no vuelve a exigirse al renovar. |
| Tamaño objetivo | Spot por 30% del patrimonio en cada activo, con cantidad conjunta viable para ambas patas. |
| Garantía | Aislada, con apalancamiento de 2x. |
| Rebalanceo | Al renovar, si el desvío del objetivo supera 5%. |
| Costos por orden | Comisión spot 0,10%; futuro 0,05%; slippage 1 pb. El ciclo suma dos operaciones de cada mercado. |
| Participación | Máximo agregado de 1% del volumen base por instrumento, minuto y cartera. |

La entrada compra spot y luego vende el futuro; el cierre recompra el futuro
y luego vende spot. Las cantidades incorporan comisiones, filtros de mercado,
redondeos y un desbalance máximo de 0,5%. Las aperturas fallidas se desarman.
El polvo no negociable conserva su valoración y queda fuera del tiempo activo.

## Ejecución, riesgo y contabilidad

Una orden se ejecuta en la siguiente ventana completa de un minuto. Una orden
enviada a las 12:01 usa `[12:01,12:02)`; a las 12:01:15 usa `[12:02,12:03)`.
El fill se registra al terminar la ventana, a su VWAP
`volumen_cotizado / volumen_base`, con slippage y redondeo adversos. Se respetan
parciales, reservas, volumen disponible y cancelaciones.

En cada instante se incorporan datos, se liquida funding sobre el short previo,
se registran fills comprometidos y se evalúan riesgo, vencimientos y decisiones.
El funding del short es `cantidad × precio_de_liquidación × tasa`; con tasa
positiva genera un ingreso.

El margen del short es garantía más P&L no realizado. Se liquida al incumplir
mantenimiento y se inicia salida preventiva si el ratio de mantenimiento
alcanza 0,50 o la distancia de liquidación cae por debajo de 0,15. Un descalce
superior al 2% activa corrección hacia 0,5% o menos. También se controla la
inactividad superior a 30 minutos y el aumento del basis de 0,02 frente a la
referencia de la posición. Los tramos de mantenimiento y cargos están en las
reglas prescritas.

Una suspensión mantiene el inventario de la pata que no puede negociarse.
Durante el episodio de marzo de 2023 se cerraron los futuros mientras el spot
seguía suspendido: el largo permaneció hasta poder venderse. Eso explica la
exposición sin cobertura. Un faltante desconocido de datos indispensables,
en cambio, detiene la corrida y conserva posición, deuda y estado.

`patrimonio = caja spot + caja futuros + garantías + valor spot + P&L no realizado del futuro − deuda`.

El funding negativo consume caja, garantía del mismo contrato y caja spot
libre; el saldo pendiente se registra como deuda. Las transferencias y cambios
de garantía no generan P&L. Al cierre de la muestra se valúan las posiciones
abiertas, sin imponer un cierre terminal. La atribución concilia funding,
P&L spot/futuro, comisiones y liquidación con el cambio de patrimonio.
El slippage ya forma parte del precio ejecutado y se presenta como diagnóstico.

## Evaluación

| Hipótesis o métrica | Cálculo |
|---|---|
| H1, predicción | MAE del funding acumulado en las siguientes 168 horas, con observaciones emparejadas y peso BTC/ETH 50/50. Hay 10.180 válidas y 44 excluidas por horizonte o calendario. |
| H2, resultado económico | CAGR condicional finito y positivo y Sharpe condicional superior al incondicional, ambos evaluables y en el mismo período. Una métrica indefinida conserva su motivo. |
| H3, compresión | Compara oportunidad y CAGR condicional entre los dos subperíodos originales. La oportunidad es el pronóstico completo cuando pasan los filtros y cero ante una falla conocida; se promedian minutos, días y ambos activos. |
| CAGR | Crecimiento compuesto sobre el saldo de entrada, con duración en días dividida por 365. |
| Sharpe | Retornos diarios, desviación muestral, anualización por raíz de 365 y tasa libre de riesgo cero. |
| Drawdown diario | Caída del patrimonio al cierre UTC respecto de su máximo previo. |
| Capital utilizado | Valor spot más garantía aislada, dividido por patrimonio al cierre diario. |
| Tiempo invertido | Unión de intervalos de exposición por activo, excluyendo polvo. |

El [índice de resultados](../results/README.md) separa cada sensibilidad. En
costos y capacidad se mantiene el umbral de selección de 34 pb. Las demoras de
órdenes cliente conservan la prioridad de liquidación. El estrés modifica
trayectorias predefinidas; estabilidad compara cuentas nuevas con sus pares y
remuestrea BASE con bloques circulares emparejados dentro de año/segmento:
5.000 réplicas, 28 días como referencia y 14/56 como sensibilidad.

SOFR es una cuenta alternativa sobre el capital completo, con interés ACT/360
y CAGR365. La sensibilidad de caja agrega interés a una fracción del saldo
contable libre del día anterior, sin cambiar las operaciones ni sus tamaños.

## Limitaciones

- Muestra: el inicio en 2022 es una decisión del diseño. Quedan fuera 2020–2021,
  y H2 se apoya en nueve ciclos cerrados condicionales. Los resultados describen
  estos activos, intervalos y escenarios.
- Datos y reglas: los precios aproximados tienen la cobertura indicada arriba.
  Las tarifas, filtros y mantenimiento son supuestos prescritos; la evidencia
  histórica de sus vigencias permanece incompleta.
- Ejecución: VWAP por minuto, participación y slippage fijo omiten spread,
  profundidad, colas e impacto. Los extremos dentro del minuto y la latencia
  real pueden cambiar pérdidas y necesidades de garantía.
- Financiamiento: se supone paridad USDT/USD, transferencias instantáneas y
  gratuitas y caja BASE sin rendimiento. Quedan fuera impuestos, insolvencia
  del exchange, ADL y liquidación parcial. SOFR es una referencia bruta
  hipotética; su uso requiere supuestos de acceso, conversión y custodia. El
  saldo de la sensibilidad de caja tampoco descuenta reservas de órdenes.
- Inferencia: los horizontes H1 se solapan. Los intervalos bootstrap son
  marginales y dependen del remuestreo; las comparaciones entre períodos y los
  escenarios de estrés son descriptivos. Las recuperaciones y anclas impuestas
  en estrés condicionan sus resultados.
- Riesgo intradía y reproducción: la evidencia compacta conserva las
  observaciones que originan los picos y valles publicados. Permite recalcular
  su aritmética; verificar de forma independiente que son extremos globales
  requiere la historia completa por minuto, que queda fuera de este checkout.
  Durante la suspensión se distinguen precios antiguos y escenarios
  hipotéticos. Las ventanas locales de ejecución y estrés tienen otro alcance.

La [guía de reproducción](reproduction.md) explica qué comprueba cada comando.

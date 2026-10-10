# Bloque 5: decisión metodológica pendiente

Estado de ambas familias: **protocolo_preparado_pendiente_aprobacion**.
Esta ficha propone seis carteras continuas nuevas, dos por escenario. No se
ejecutó ninguna ni se compararon rendimientos de candidatos. La aprobación
puede abarcar las dos familias o solamente una; cada familia se ejecutará
con estas reglas completas, sin nuevas consultas por pasos ya autorizados.

## Familia de shocks: SH_P90 y SH_MAX

Recomiendo una **perturbación descendente del spot respecto del perpetuo**,
en una senda exógena común a ambas estrategias. No es un shock conjunto:
futuros, marks y tasas de funding conservan sus datos originales. Por eso
no prueba resistencia del corto a subas del mark ni cubre todos los riesgos
de garantías.

| Escenario | BTCUSDT: reducción del nivel spot | ETHUSDT: reducción del nivel spot |
| --- | ---: | ---: |
| SH_P90 | 0,09944179003125626% | 0,1214060739531364% |
| SH_MAX | 0,5498931623931669% | 1,4434038177835395% |

Las fracciones exactas son, respectivamente,
`0.0009944179003125626` / `0.001214060739531364` y
`0.005498931623931669` / `0.014434038177835395`. Proceden de la valoración
original del catálogo BASE: 100 episodios BTC y 133 ETH, incluidos los ceros,
sin faltantes evaluativos; percentil lineal de NumPy, sin cambiar población.
El proxy produciría P90 de 0,0906929488802944% / 0,11398306672389502% y máximos
de 0,25588691020874688% / 0,35721494895898376%. Mantengo la calibración original
por continuidad con la propuesta publicada; su spot antiguo durante el cierre
es una limitación explícita. No ejecuto otra matriz con el proxy.

**Calendario y duración:** unión de los episodios BASE de ambas estrategias,
por activo, según las 233 filas de
[calendario propuesto](tablas/calendario_shocks_propuesto.csv).
Cada inicio se lleva al primer minuto completo que empieza en o después del
inicio del episodio; su fin al techo de minuto del fin BASE, con mínimo una
vela. El descenso se mantiene en ese intervalo y se retira linealmente durante
los siguientes **60 minutos**. Este plazo es un supuesto de diseño; no es un
percentil estimado ni un plazo elegido por P&L. En solapamientos se usa la
mayor intensidad vigente, nunca el producto de shocks. Son 99 ventanas BTC
y 131 ETH después de unir los intervalos que incluyen la recuperación.

**Precio y liquidez:** multiplicar OHLC y VWAP spot por `f = 1 − magnitud × intensidad`;
volumen base y número de operaciones observados se conservan, volumen cotizado
se multiplica por `f`. Siguen el cupo bruto de 1%, ticks, fees y slippage BASE.
Durante la suspensión no se crean velas operables ni fills: sólo se valúa el
spot al último precio original conocido multiplicado por el factor del último
minuto terminado, rotulado **hipotético sobre referencia antigua**. No se
renueva su disponibilidad ni se habilitan señales con datos obsoletos.

El primer minuto alterado termina después del estado BASE que dispara el
calendario; no modifica órdenes ya ejecutadas. Si desaparece, se prolonga o
aparece una exposición en la nueva cartera, el calendario permanece fijo.
No se agregan shocks por estados nuevos. La recuperación tampoco depende del
cierre de posiciones; se informará su contribución de valoración por separado.
Al final del pulso vuelve la fuente original, manteniendo todo el inventario,
órdenes y saldos resultantes. No se liquidan ni reinician cuentas por ese motivo.

El calendario es retrospectivo y no se revela por adelantado a la estrategia.
Las magnitudes tampoco estaban disponibles ex ante en 2022. P90 no significa
probabilidad de pérdida ni nivel de confianza; los episodios comparten mercado.
Prefiero estas cuatro carteras continuas a 466 replays locales: permiten H2/H3
bajo un mercado común y evitan sumar experimentos incompatibles.

## Familia sin interrupción: CF_SIN_INTERRUPCION

Recomiendo sustituir **únicamente spot BTCUSDT/ETHUSDT del 24/03/2023,
aperturas de vela `[11:27,14:00) UTC`**: 153 velas por activo. Incluye la vela
parcial real de 11:27; las otras 152 corresponden al cierre completo documentado.
BASE conserva 121 minutos de exposición descubierta, `[12:00,14:01)`, una
duración distinta. [Cronología y fórmulas](protocolo_tecnico.md#contrafactual).

- **Ancla:** última vela completa anterior, abierta 11:26 y disponible 11:27.
  `k = spot_close / futures_close`: BTC `28068.79000000 / 28053.70`;
  ETH `1788.70000000 / 1787.90`. No usa la vela parcial ni la reapertura.
- **Precios:** `OHLC_spot* = k × OHLC_futuros`; `VWAP_spot* = k ×
  quote_futuros/base_futuros`, usando la misma vela. Son precios hipotéticos;
  la relación de cierres spot/futuro queda constante por construcción.
- **Volumen:** mediana del volumen spot por minuto de la misma **hora UTC**
  durante `[22/03/2023 00:00,24/03/2023 00:00)`, con 120 observaciones por hora
  y activo, incluidos ceros. Se usan dos días completos posteriores al fin de
  la promoción BTC; no una ventana que mezcle esos regímenes. La ventana corta
  no acredita estacionalidad semanal ni profundidad del libro.
- **Velas coherentes:** volumen cotizado = volumen base hipotético × VWAP
  hipotético. Cantidad de operaciones = piso de la mediana de operaciones de
  la misma muestra; no se reconstruyen trades. Ceros impiden fills; no hay
  liquidez infinita. Cupo compartido de 1% por cartera, fees y slippage BASE.
- **Disponibilidad y operatividad:** cada vela aparece sólo al terminar.
  Sustituir en la capa de escenario la clasificación de cierre y los registros
  de volumen cero/ausentes de ese intervalo exacto. Fuera de él, ninguna
  excepción nueva. La orden enviada antes de terminar no conoce OHLC, VWAP ni
  volumen final de esa vela para dimensionarse.
- **Reapertura:** retorna el spot observado desde la vela 14:00, conocida
  a las 14:01; no se suaviza la unión ni se ajusta retrospectivamente el ancla.
  Se separarán salto de precio, cambio de fuente y efectos sobre inventario.

| Hora UTC de la vela | BTC por minuto | ETH por minuto |
| --- | ---: | ---: |
| 11, desde 11:27 | 42,534745 | 233,203900 |
| 12 | 58,955960 | 309,456600 |
| 13 | 84,440200 | 371,094550 |

La trayectoria común se ejecutará hasta 01/09/2026, conservando decisiones,
ejecuciones, inventario, funding monetario y garantías que resulten. Mantener
futuros, marks y tasas originales es una condición hipotética, no una predicción
de cómo habrían reaccionado esos mercados. No identifica causalmente el costo
real de la interrupción. No reutiliza los cierres BASE cambiando sólo valoración.

## Comparadores, recursos y decisión solicitada

Ambas familias mantienen 10.000 USDT por estrategia, muestra continua UTC
`[2022-01-01,2026-09-01)`, parámetros y reglas BASE, demoras apagadas y motor
corregido. Referencias originales preservadas, controles corregidos autenticados:
`run_d7c7cb5da666e22321598598` y `run_415276e8a8b5bb9101e2d13b`.
No hay latencia añadida, OHLC4, estrés de costos, caja remunerada, aportes,
otros capitales, nueva calibración o aleatoriedad.

Seis carteras económicas, más cuatro controles continuos técnicos separados
(dos con capa apagada y dos con shock cero); ejecución serial por familia.
Presupuesto orientativo de replay/controles: **6–10 horas**, con margen de
espacio de **5 GB** y unos 3 GB de RAM medidos por proceso BASE, reservando
6 GB. Desarrollo y revisión agregan tiempo; no es una promesa de duración.
No se copian bases completas por escenario ni paquetes previos completos.

**Aprobación solicitada:** aprobar estas reglas materiales para la familia
`SH_P90 + SH_MAX`, para `CF_SIN_INTERRUPCION`, o para ambas. La aprobación
remitirá a esta ficha y al [protocolo técnico](protocolo_tecnico.md), con las
identidades de [identidad_propuesta.json](identidad_propuesta.json).
La limpieza tiene un inventario independiente y requerirá autorización
posterior por rutas; esta aprobación metodológica no autoriza retiros.

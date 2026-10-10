# Especificación propuesta del bloque 5

Pendiente de aprobación. Este documento fija supuestos para resultados que
todavía no existen. Sus tablas de entradas son descriptivas; ninguna contiene
P&L de shocks o contrafactual. La cuenta SOFR finalizada permanece separada.

## Referencia y reglas comunes

Muestra `[2022-01-01T00:00:00Z,2026-09-01T00:00:00Z)`, UTC nanosegundos,
10.000 USDT por cartera; BTCUSDT/ETHUSDT spot y perpetuos USD-M. Condicional y
permanente son cuentas independientes con el mismo mercado, no competidoras
por un único cupo entre estrategias. El cupo sí se comparte entre órdenes de
la misma cartera e instrumento/minuto.

Derivar la configuración desde `effective_config.toml` de cada BASE original,
cuya igualdad semántica con su control corregido fue comprobada. Preservar
168 h de horizonte/tenencia, EWMA 24 h, ventana 336 h y precarga de 360 h;
funding disponible 60 s después; basis inclusivo `[0,0.005]`; selección a 34 pb,
renovación condicional con forecast positivo, permanente sin filtro de funding.
Objetivo 30% de equity por activo, apalancamiento aislado 2x, fees prescritos
0,10% spot/0,05% futuros, slippage 1 pb por orden y participación 1%.
Conservar todos los demás campos efectivos, incluido timeout, cooldown,
restricciones de cantidades/ticks, reservas y cargos de liquidación.
No construir la referencia desde `Config()` ni desde una variante de otro bloque.

Código económico corregido autenticado:
`e7effba8baf808562d4a1f7340eba6c8f9352860484bfd2a199c6013660a09ce`.
La guardia de `_timeout` conserva `liquidate` para el remanente de corto y
no permite volver a HOLDING desde una corrección/rebalanceo con liquidación
pendiente. Se preservan las ventanas comprometidas y el funding sobre el
corto anterior a los fills simultáneos. El historial de aprobación y las
pruebas del bloque 4 son dependencias autenticadas, no una aprobación de B5.

## Calibración recuperada

Fuente primaria dentro del estudio: catálogo sellado de riesgo,
`tablas/catalogo_incidentes.csv` y `evidencia/episodios.parquet`. Se ejecutó
su función publicada `episode_price_descriptions` en una copia real mínima
fuera del árbol versionado. Las 466 filas de detalle y las cuatro filas de
resumen coinciden celda por celda con lo publicado.

Para cada episodio BASE se conserva la máscara `incident_exposure_mask`,
la presencia de spot positivo y precios finitos: estado activo y observación
previa al cierre, excluyendo estados POST ya cubiertos o sólo polvo.
`d_i = max(0, 1 − min(S_i)/S_i,inicial)`. No es una tasa por minuto.
Sin observación evaluable se conserva ND y motivo; no se inventa cero.
Se incluyen ceros genuinos: BTC 48/49, ETH 51/53, original/proxy. Hay 0 ND
en ambas poblaciones actuales. P90 usa `numpy.quantile(q=.9, method='linear')`,
posición `(n−1)×.9`, interpolación lineal. Se conservan los decimales textuales
publicados, no los porcentajes redondeados de un reporte.

| Activo | Nivel | Original % | Proxy % | Proxy menos original, puntos porcentuales |
| --- | --- | ---: | ---: | ---: |
| BTC | P90 | 0,09944179003125626 | 0,0906929488802944 | −0,00874884115096186 |
| BTC | máximo | 0,5498931623931669 | 0,25588691020874688 | −0,29400625218442002 |
| ETH | P90 | 0,1214060739531364 | 0,11398306672389502 | −0,00742300722924138 |
| ETH | máximo | 1,4434038177835395 | 0,35721494895898376 | −1,08618886882455574 |

El máximo del original puede incorporar una referencia anterior al cierre.
El proxy no es una transacción observada. Se conserva el original como
calibración principal por continuidad documental, no por pérdidas de escenarios.
La escala puede ser pequeña y no se aumentará después de observar resultados.

## Shocks: calendario, fórmula y fase

Para cada fila del catálogo BASE, por activo, sea `M=60 segundos`:

```
a_i = ceil(start_i / M) × M
b_i = max(a_i + M, ceil(end_i / M) × M)
R = 60 × M
w_i(u) = 0                       si u < a_i o u >= b_i + R
         1                       si a_i <= u < b_i
         1 − (u − b_i)/R          si b_i <= u < b_i + R
w_s(u) = max_i(w_i(u))            (0 si no hay un pulso vigente)
f_s(u) = 1 − m_s × w_s(u)
```

`u` es la apertura de la vela, siempre alineada. La primera vela de recuperación
todavía tiene intensidad uno; las siguientes 59 reducen la intensidad por
escalones de 1/60 y en `b_i+R` el factor es uno. Queda definida la pequeña
discontinuidad de cada escalón; no se presume un recorrido intravela. En un
nuevo inicio durante la recuperación, la regla `max` puede restablecer intensidad
uno, sin multiplicar descensos. Activos distintos tienen sus calendarios
propios. SH_P90 y SH_MAX sólo difieren en las dos magnitudes.

Se preservan las 233 identidades, incluso coincidencias entre estrategias;
no se las cuenta como 233 ensayos independientes. La envolvente produce 6.163
aperturas BTC y 8.117 ETH con factor distinto de uno, por nivel; no son filas
de ejecuciones. La regla no depende de posiciones resultantes, tampoco de
que el episodio original desaparezca. Los episodios nuevos no añaden fechas.

En velas reales spot `OHLC*=f(u)×OHLC`, `quote*=f(u)×quote`, base y operaciones
invariables; entonces `VWAP*=quote*/base=f(u)×VWAP`. No cambiar futures,
marks, tasas o settlement marks de funding, ni convertir la marca de riesgo
en un precio ejecutable. Usar Decimal con el contexto original del motor;
los valores `m` proceden de las cadenas exactas publicadas.

**Fase causal:** el pulso empieza en la apertura `a_i` y sólo su primera vela
terminada está disponible en `a_i+M`. Un fill en `a_i` usa la ventana previa
intacta. Una orden dimensionada en `a_i` usa información disponible hasta ese
instante; si se ejecuta en `[a_i,a_i+M)`, recibe el VWAP alterado al final.
No informar a la estrategia del calendario ni de próximos factores. Conservar
funding → fills comprometidos → riesgo/estado → reintentos → decisiones.

**Valoración durante falta de actividad documentada:** para un instante `t`,
`u(t)=floor(t/M)×M−M` es la última vela potencial completamente terminada.
Sea `S_ref(t)` el último cierre original con volumen positivo y disponibilidad
`<=t`. Valorar spot a `S_ref(t)×f(u(t))`, conservando el timestamp, fuente,
edad y motivo de arrastre de `S_ref`. Esta regla coincide con el cierre
transformado cuando la última vela es válida. Durante la suspensión sólo
produce una referencia hipotética no operable: no inserta trades, volumen
positivo, velas frescas o señales admisibles. La frescura de entrada se evalúa
con la disponibilidad original; la operatividad permanece cerrada. Los huecos
desconocidos fuera de la suspensión siguen bloqueando la ejecución.

Esta valoración es un supuesto material adicional y se aprueba junto con los
shocks. No usa el proxy ligado a futuros ni mezcla su calibración. Se exige una
sola referencia transformada para equity, basis cuando sea admisible y riesgo;
los validadores de disponibilidad son metadatos distintos del valor hipotético.
Se evita que la actualización del reloj del factor rejuvenezca un precio viejo.

Al terminar el pulso, el factor vuelve a uno por el calendario fijado; no se
restaura un estado BASE, no se reinicia el capital y no se fuerza una venta.
Descomponer la variación de referencia como
`S_prev×(f_new−f_prev) + f_new×(S_new−S_prev)` y documentar convención/orden.
Multiplicar el primer término por inventario común preevento sólo como
diagnóstico de valoración, sin sumarlo nuevamente al ledger. Separar esa
reversión de P&L realizado, fees y cambios de decisiones. No atribuir la
recuperación impuesta a habilidad de la estrategia.

## Contrafactual

### Cronología acreditada y ancla

El [informe oficial del incidente](https://www.binance.com/en/blog/from-our-ceo/6789340645608890113)
ubica el inicio spot a las 11:27 UTC. El
[anuncio de reapertura](https://www.binance.com/en/support/announcement/detail/813a31506e9f478ea8c1058b425df87a)
informa las 14:00 UTC y muestra publicación 13:38; fue aclarado el 16/05/2023.
Se consultaron esas dos fuentes, sin búsqueda general ni descarga de trades.
No se recuperó una publicación contemporánea exacta del inicio del cierre.

Por activo, el calendario del proyecto declara `[11:28,14:00)`: 152 minutos
completos. Las velas 11:28–12:39 son 72 registros con volumen cero; 12:40–13:59
son 80 registros ausentes. La vela 11:27 es parcial y se publica 11:28.
Los futuros tienen las 153 velas positivas de 11:27 a 13:59.
La primera vela spot posterior abre 14:00 y se conoce 14:01.

En las BASE preservadas, el corto ETH condicional y BTC/ETH permanente termina
12:00; el spot se vende 14:01. La exposición descubierta dura 121 minutos por
activo afectado, no 153 ni 152. Ver
[fills originales](controles/cronologia_fills_base.json) y
[precios de frontera](tablas/cronologia_spot_futuros.csv).

Se propone reemplazar la vela parcial 11:27 además de las 152 cerradas, para
no conservar una huella de la interrupción en el contrafactual. El ancla es
11:26, disponible 11:27. No se reaprovecha silenciosamente el ancla 11:27 del
proxy de valoración anterior. Se guardan numeradores/denominadores exactos:
BTC `28068.79000000/28053.70`, ETH `1788.70000000/1787.90`. La división se hace
con la precisión Decimal original, 28 dígitos; las tablas muestran ese cociente.

### Operatividad y precios

La intervención afecta sólo BTC/ETH spot y aperturas `[11:27,14:00)` de ese día.
La capa sustituye la vela parcial, las velas sin actividad y los registros
ausentes por una única vela sintética por clave, con marcador de escenario,
procedencia, originales y motivo. El calendario de calidad deja de clasificar
esas 152 aperturas como suspensión únicamente para CF. Los controles de
actividad/frescura reciben las velas sintéticas de este intervalo. Las reglas
prescritas BASE ya declaran `operational=True`; no se debe inventar una línea
de RuleBook que no existe ni cambiar las reglas históricas globalmente.
El resto del calendario y los validadores permanecen idénticos.

Para cada apertura `u`, `k=S_close(11:26)/F_close(11:26)`:

```
(O,H,L,C)_spot*(u) = k × (O,H,L,C)_futures(u)
VWAP_spot*(u) = k × Q_futures(u)/V_futures(u)
V_spot*(u) = mediana{V_spot(v): fecha(v) en 22 y 23/03, horaUTC(v)=horaUTC(u)}
Q_spot*(u) = V_spot*(u) × VWAP_spot*(u)
N_spot*(u) = floor(mediana{N_spot(v): mismos v})
available_at(u) = end_time(u) = u + 60 segundos
```

Hay 120 observaciones por grupo de hora/activo. Mediana par = promedio exacto
de los elementos 60 y 61 ordenados. No se retiran ceros; una ausencia no es
cero y detiene la calibración. Un grupo con volumen mediano cero genera
volumen/quote/trade_count cero y no permite ejecución. Si volumen positivo
y mediana de operaciones menor que uno fueran incompatibles, bloquear; no
fabricar actividad mínima. En las seis celdas actuales ambos son positivos.
La mediana de operaciones sólo completa metadatos de actividad: no prueba
que existieran esas operaciones ni habilita un motor de trades.

Se autenticaron 2.880 minutos previos sin ausencias por activo. La ventana
se justifica por el fin documentado de la promoción BTC el 22/03: no se mezclan
sus volúmenes con semanas anteriores. Agregar 60 minutos por hora reúne 120
observaciones, permite un patrón horario simple y limita valores extremos.
No identifica estacionalidad por día de semana, impacto o liquidez que hubiera
existido. El volumen es independiente de la orden, de la estrategia y de su
P&L; no se busca el mínimo que permita cerrar. El VWAP se deriva de futuros,
pero **el volumen base nunca se copia de futuros**.

OHLC debe satisfacer `low <= open <= high` y `low <= close <= high`; también el VWAP escalado
debe ser positivo y quedar dentro del rango. Si la fuente viola esto,
bloquear y documentar antes de ejecutar, sin recortar precios. El producto
quote/base es una construcción sintética, no volumen cotizado oficial.
La capa sustituye coherentemente `minute_bars`, la referencia de cierres y
los volúmenes derivados que realmente consuma el lector; no permite que
señal, ejecución y equity lean tres versiones diferentes.

### Disponibilidad, reapertura y trayectoria

La primera vela hipotética está disponible 11:28. No afecta el estado ni fills
de 11:27 que utilizaron `[11:26,11:27)`. Las órdenes vigentes evolucionan con
los mismos timeouts/participación/secuencia, sin reiniciarlas. No usar el cierre
futuro de una vela en su apertura para sizing. Mantener futures, marks,
settlement marks y tasas originales es una condición del experimento; el
importe de funding puede cambiar por inventario. Si el motor se detiene por
cobertura o insolvencia, conservar ese estado, no forzar completar tablas.

Desde la apertura 14:00 no se alteran datos. La primera fuente spot real nueva
se publica 14:01; hasta entonces permanece el último cierre sintético conocido.
No se suaviza el salto. Como control descriptivo de frontera, el cociente
`S_real_open(14:00)/(k×F_open(14:00))−1` es +0,3611584178% BTC y +1,2807749167%
ETH; usando cierres de esa vela, +0,0630157582% y +0,2160869636%.
Son diferencias de precios de entrada, no retornos de carteras. Para el resultado
se medirá su impacto sobre el inventario preevento. El salto desde el cierre
sintético 13:59 al open observado 14:00 es +0,3611584178% BTC y +1,2813483945%
ETH; hasta el cierre observado, disponible 14:01, es −0,1906851854% y
−0,1799926517%. El open es un control retrospectivo de unión, no información
disponible antes de terminar la vela. Los valores fuente y fórmulas están en
[frontera descriptiva](controles/frontera_reapertura_descriptiva.json).
Ninguna de esas cifras corrige el ancla; todavía no hay impacto monetario simulado.

Se reejecuta continuamente desde 2022 al fin, sin retomar un estado BASE
posterior al incidente. Se prefiere inicio completo a checkpoints para reducir
supuestos; si se usaran después, exigir equivalencia de TODO el estado,
órdenes/reservas y capa. No hay aleatoriedad.

## Resultados permitidos y controles de la etapa B

Seis trayectorias económicas y cuatro controles técnicos continuos por separado;
ninguna en etapa A. Reportar muestra total, cinco años (2026 parcial) y los
dos regímenes H3 con saldos heredados: equity, P&L y componentes, retorno,
CAGR365, Sharpe RF=0, volatilidad, drawdown diario, utilización diaria, tiempo
activo sin polvo, ciclos, ejecución, exposición, deuda y liquidaciones. Conservar
ND con motivo, no anualizar incidentes ni sumar porcentajes anuales.

Dentro de las ventanas intervenidas y sus bordes se estudiarán pérdidas
transitorias/garantías a cierres de minuto y eventos financieros. No reconstruir
por defecto toda la muestra intradía ni denominar sus extremos máximos globales.
Separar mantenimiento, saldo, holgura, necesidad preventiva y faltante externo;
caja bruta no equivale a disponible. Sin reservas acreditables, faltante exacto
ND/cotas. Después de cerrar un corto no existe margen de ese contrato. No se
inyecta dinero ni se suman máximos de momentos distintos.

H1 requiere autenticar señales/proyecciones, disponibilidad, targets y cobertura
antes de reutilizar una cohorte; no atribuir registros no persistidos. H2 sólo
compara carteras continuas del mismo escenario y mantiene CAGR condicional
positivo y Sharpe superior al permanente. H3 se recalcula desde el mercado
hipotético común: forecast completo al pasar filtros, cero en fallas conocidas,
ND en desconocidas; promedio diario por activo y 50/50, unidad pb/168 h.
Cambiar spot/basis/operatividad puede cambiar oportunidad: no copiar BASE.
Mantener H1/H2/H3 originales como referencias históricas.

Antes de interpretar: equivalencia apagada y shock cero; suspensión preservada
en shock y CF apagado; fronteras/nanosegundos; independencia de datos de reapertura;
OHLC/VWAP/quote/base, unidades y ticks; solapamientos sin composición;
liquidación con remanente, funding simultáneo, deuda/reservas; checkpoint completo;
conciliación diaria/períodos a `1E-8` USDT; pruebas negativas que realmente alteran
bytes/celdas. Las diez clases de controles del encargo se conservan como puerta.

El contraste de B2/B3 con el defecto corregido sigue **pendiente y separado**.
La igualdad de BASE y la ausencia de fills etiquetados liquidación no lo resuelven.

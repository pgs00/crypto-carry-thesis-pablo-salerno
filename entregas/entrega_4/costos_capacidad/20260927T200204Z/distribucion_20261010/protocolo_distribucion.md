# Protocolo descriptivo: costos y capacidad

Distribución documental del 10 de octubre de 2026, derivada del paquete del
27 de septiembre de 2026. Ocho variantes independientes para ambas carteras:
dieciséis corridas nuevas históricas y dos referencias BASE reutilizadas.

| ID | Cambio económico | Modo de costo de selección |
|---|---|---|
| C02 | cost_multiplier=2 | base_e3_total |
| C03 | cost_multiplier=3 | base_e3_total |
| S02 | slippage=0.0002 | base_e3_total |
| S05 | slippage=0.0005 | base_e3_total |
| P050 | max_volume_participation=0.005 | BASE |
| P025 | max_volume_participation=0.0025 | BASE |
| A050 | capital=50000 | BASE |
| A100 | capital=100000 | BASE |

base_e3_total fija sólo cycle_cost de selección en Decimal('0.0034'); los modos
realized/base_e3, configuraciones anteriores y sus digests conservan semántica.
Los componentes de selección suman 34 pb y scenario_* describe las fricciones
realizadas. Las decisiones, sizing, fondos, inventario, garantías, cantidades y
trayectorias responden a las fricciones del escenario. No son órdenes congeladas.

| Caso | Fee spot | Fee futuros | Deslizamiento |
|---|---:|---:|---:|
| BASE | 0,10% | 0,05% | 1 pb |
| C02 | 0,20% | 0,10% | 2 pb |
| C03 | 0,30% | 0,15% | 3 pb |
| S02 | 0,10% | 0,05% | 2 pb |
| S05 | 0,10% | 0,05% | 5 pb |

C02/C03 cambian comisiones y slippage conjuntamente, una sola vez. Compra spot
paga fee en activo base; cantidad bruta ejecutada y neta recibida se distinguen.
La tarifa específica de liquidación no se multiplica; su base imponible puede
cambiar con la trayectoria. Comisión ordinaria y cargo especial son separados.

La capacidad agrega fills brutos por (cartera, activo, mercado, window_start),
sin netear BUY/SELL; un volumen por clave, step redondeado hacia abajo y capacidad
ya consumida descontada. Cada escenario es una cartera alternativa independiente.
La participación es q/volumen y utilización es q/(participación máxima*volumen).
El volumen posterior al envío sirve para auditoría, no para sizing retrospectivo.
La ventana original no se extiende. Ausencia, volumen cero, reglas, step, fondos
y reservas mantienen causas distintas; si no hay identificación única, queda ND
o conjunto explícito de causas compatibles. Las forzosas mantienen la aproximación
original; no se extiende una excepción a órdenes voluntarias.

Distribuciones empíricas: una observación por clave con volumen positivo y fills
voluntarios, sin ponderación; resúmenes de orden usan una observación por orden.
BTC y ETH no se suman como cantidades. Selección prefijada por cartera: cinco
claves de mayor utilización, desempate window_start/símbolo/mercado ascendentes;
cinco episodios descubiertos de mayor duración, desempate inicio/símbolo. El
catálogo completo se conserva, con cruces identificados sin doble recuento.

A050/A100 son trayectorias efectivas con metas porcentuales, reglas, límites y
tramos originales; se comparan capital propio, retornos y curvas normalizadas,
sin proporcionalidad impuesta. Garantías de cierre diario no son máximo intradía.
H1 y oportunidad H3 se reutilizan una vez sólo tras verificar proyecciones,
identidades y cobertura. El contraste H3 usa nuevos CAGR. Capacidad/AUM/caja
no entran retrospectivamente en el indicador de mercado. No se deduce
escalabilidad ilimitada ni estimaciones de spread, cola o impacto de velas 1m.
Las revisiones técnicas de runner conservan identidad económica y antecedentes.

## Convenciones científicas conservadas

Las dos carteras alternativas son conditional y permanent, con BTCUSDT/ETHUSDT
spot y perpetuos USD-M durante [2022-01-01T00:00:00Z, 2026-09-01T00:00:00Z).
Las referencias son run_ad71d751b20623006c195ff3 y
run_dfea4b7ac1475668d5968c97. Cada configuración se deriva de la efectiva BASE.
Las trayectorias son continuas: los ocho períodos (full, 2022-2023, 2024+,
2022, 2023, 2024, 2025, enero-agosto 2026) heredan saldos, posiciones y ciclos.
El capital inicial BASE es 10.000 USDT. No hay cierre terminal artificial.

La referencia utiliza horizonte/tenencia 168 h, vida media 24 h, ventana 336 h,
precarga 360 h, disponibilidad de funding 60 s, basis inclusivo [0, 0.005],
objetivo spot 30% por activo, garantía aislada 2x, participación 1%,
next_minute_vwap y joint_quantity. Las comisiones ordinarias BASE son
0,10% spot y 0,05% futuros; deslizamiento de 1 pb por orden, sin promoción.
El costo del ciclo es 34 pb; la condicional exige forecast estrictamente
superior al costo al entrar y forecast positivo al renovar. La permanente
omite ambos filtros de funding y conserva los restantes. El basis de entrada
no se aplica a renovación. Las excepciones por escenario se explicitan abajo.
Se preservan reglas prescritas, riesgo, orden de patas, parciales, reintentos,
funding anterior a fills simultáneos y los 15 marks futures_scaled documentados.
Caja y garantías no devengan intereses en estos experimentos.

Cada cierre/período concilia equity final menos inicial con spot, futuros,
funding, comisiones y liquidaciones a la tolerancia original 1E-8 USDT.
Slippage y tick están incorporados en precio; garantías/transferencias no son
P&L. CAGR usa 365 días; Sharpe usa retornos diarios, días inactivos incluidos,
desvío muestral y RF=0. ND conserva motivo y cobertura. El polvo mantiene
valor/riesgo aunque no cuente como actividad. Exposición y ciclos se clasifican
en la trayectoria completa antes de recortar períodos; la cartera usa unión
temporal BTC/ETH. Capital utilizado diario es spot valuado más garantía;
utilización, capital, nocional y caja libre son magnitudes diferentes.

H1 compara EWMA/no-change sobre población válida común, por activo y promedio
de igual peso; no sólo sobre entradas. Los targets respetan tiempos reales,
calendario acreditado y final global exclusivo. H2 es favorable sólo con CAGR
condicional definido, finito y positivo, y Sharpe definido superior al de la
permanente del mismo escenario/período: no exige CAGR superior ni Sharpe positivo.
H3 compara oportunidad media y CAGR condicional entre 2022-2023 y 2024-agosto
2026: ambos caen=favorable, ambos suben=contraria, otros evaluables=mixta,
faltantes indispensables=no_concluyente. La oportunidad usa todos los minutos
de mercado, con independencia de posiciones/caja: forecast completo si supera
funding/costo, basis y operatividad; cero para fallo conocido; desconocido no
es cero. Cada día válido contiene 1440 minutos por activo y peso BTC/ETH 50/50.

Los drawdowns y extremos de garantía ordinarios son diarios. Los estados
técnicos y económicos se conservan por separado; insolvencia no es fallo
técnico ni justifica fabricar días o descartar una trayectoria. Los resultados
son sensibilidades exploratorias de historia observada, sin inferencia de
probabilidades, optimización ni prueba fuera de muestra. Las hipótesis de E3
conservan sus cifras e identidades originales.

## Procedencia y verificación de esta distribución

Los índices de corridas, configuraciones, protocolos previos JSON, fuentes,
resultados numéricos, código económico congelado y tolerancias mantienen sus bytes.
Sólo se actualizan enlaces documentales en reportes y la referencia introductoria
del protocolo Markdown; el contenido metodológico y las cifras permanecen iguales.
`documentos/protocolo.md` es un registro metodológico histórico autenticado;
sus referencias a documentos operativos retirados identifican antecedentes,
sin imponer instrucciones a esta distribución. Los protocolos JSON mantienen
los hashes originales porque integran la identidad científica de las corridas.

`procedencia/manifiesto_original.json` y su sidecar identifican el paquete
histórico de procedencia: no son el sello de la distribución actual ni prueban
una verificación nueva. `procedencia/derivacion.json` enumera exactamente las
omisiones operativas, adaptaciones de empaquetado y adiciones. El manifiesto
exterior actual tiene identidad propia. El verificador exige los bytes de todo
miembro científico retenido contra el manifiesto original autenticado y conserva
los controles numéricos del bloque. La excepción documental sólo alcanza las
rutas autorizadas expresamente en el registro cerrado del helper.

El modo compacto es autónomo con las dependencias Python del lock incluido:
no requiere Git, red, ruta original, datos masivos ni conversaciones previas.
Los recálculos adicionales con datos masivos siguen exigiendo una ruta local
explícita. Hash de una fuente ausente no significa reconstrucción de esa fuente.
Constructor/verificador comparten lógica de posprocesamiento; no son motores
económicos independientes. La distribución no ejecuta nuevos backtests.
Los reportes, pruebas, matrices y controles retenidos describen su fecha original;
sus pendientes de redacción/publicación no acreditan el estado global actual.

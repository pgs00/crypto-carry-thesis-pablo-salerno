# Protocolo descriptivo: ejecución y demoras

Distribución documental del 10 de octubre de 2026, derivada del paquete v2 del
30 de septiembre de 2026. Seis variantes independientes para ambas estrategias: doce carteras nuevas
históricas y dos BASE reutilizadas; dos controles BASE completos permanecen separados de esa matriz.

| ID | Precio | Demora adicional | Propósitos afectados |
|---|---|---:|---|
| E_OHLC4 | (open+high+low+close)/4 | 0 s | Ninguno demorado |
| L01 | VWAP | 60 s | Todos los del cliente |
| L05 | VWAP | 300 s | Todos los del cliente |
| LC01 | VWAP | 60 s | close_perp, close_spot |
| LC05 | VWAP | 300 s | close_perp, close_spot |
| LC15 | VWAP | 900 s | close_perp, close_spot |

No se cruzan familias; el costo de decisión conserva el modo efectivo BASE.
LC es regla causal para todos los cierres de cada trayectoria, no activación
retrospectiva sobre incidentes BASE. Las opciones research_minute_price_model,
research_execution_delay_seconds y research_execution_delay_scope son optativas;
apagadas conservan canonical/digest anteriores y la ruta next_minute_vwap.

OHLC4 usa la misma vela elegible completa y su volumen, con sizing conocido al
envío, fondos, tick adverso, slippage y fees originales. Incluye liquidate en esa
ruta. No sustituye señales, marks, basis, funding ni quote_volume/base_volume.
OHLC es positivo y consistente, low<=open,close<=high. Sin actividad/volumen no
hay fill; ausencia no explicada no permite otra vela. OHLC4 no garantiza precio
ejecutable real ni revela el orden intravela. Fixture descriptivo: O=100,H=110,
L=90,C=104, volumen=10, quote=1020 implica OHLC4=101, VWAP=102, close=104.

Cada orden conserva submitted_at=t; su propósito fija delay_applied, luego
eligible_at=t+delay_applied y ventana única minute_window(eligible_at).
Fill y vencimiento se registran en window_end, cuando la vela está disponible.
Ejemplo UTC: envío 12:00:20+60 s => elegible 12:01:20, ventana [12:02,12:03),
registro 12:03. Envío exacto 12:00:00+60 s => ventana [12:01,12:02).
No se suma otra demora ni se reevalúa funding/sizing en la elegibilidad.

L cubre open_spot,open_perp,increase_spot,increase_perp,reduce_perp,reduce_spot,
correct,close_perp,close_spot. LC sólo close_perp/close_spot, incluyendo cierre
preventivo, por fallos, deuda o suspensión. Cada segunda pata y reintento tiene
envío, demora y ventana propios. liquidate tiene demora adicional cero; el
close_spot posterior sí recibe la correspondiente. Se conserva la aproximación
BASE de liquidación mediante ventana/cupo; exclusión de demora no acredita
realismo de la liquidación del exchange.

Durante la espera se mantienen pendientes, reservas, fondos, riesgo y eventos.
Funding precede fills simultáneos. Sólo se traslada vencimiento de la orden:
holding, correction_deadline y cooldown conservan sus relojes. La cancelación
antes de ventana y en su inicio exacto es inmediata; dentro de ventana comprometida
mantiene el diferimiento BASE. El final exclusivo no admite fills cuya ventana
termine en o después del límite. Nanosegundos y orden persistido se conservan.
Órdenes sin fill no tienen latencia de ejecución cero; percentiles de fills
describen sólo esa población, acompañada de canceladas/expiradas/pendientes.

## Reparación histórica separada de la sensibilidad

La identidad económica congelada e7effba8baf808562d4a1f7340eba6c8f9352860484bfd2a199c6013660a09ce
incluye una reparación preexistente de la prioridad al reintentar un cierre
parcial escalado a liquidación. Si queda corto pendiente de liquidar, el nuevo
intento de futuros usa purpose=liquidate, demora adicional cero y cargos de
liquidación; la ventana ya comprometida conserva su tratamiento original.
La guardia también impide restaurar HOLDING desde corrección/rebalance mientras
permanezca corto por liquidar. No cambia ventana/volumen BASE del nuevo envío.

El caso sintético documentado tenía envío t=240 s, ventana [540,600), escalada
t=570, parcial t=600: el nuevo remanente se clasifica liquidate, en lugar de
heredar close_perp demorado hasta t=960. La reparación y controles están en el
código congelado, extensión aplicada, fixtures, controles de compatibilidad y
auditorías retenidos. Los controles BASE tienen identidades propias y comparan
once artefactos en orden persistido a precisión original; no reemplazan las
referencias ni cuentan como nuevas sensibilidades. Los mensajes conversacionales
de aprobación y la propuesta operativa fueron omitidos; sus huellas históricas
se conservan en la procedencia y el protocolo JSON original.

## Incidentes y límites

El catálogo completo conserva episodios descubiertos. Los casos explicativos
son los cinco de mayor duración por cartera (desempate primer inicio/activo),
más 24/03/2023 cuando haya exposición. No se impone duración de 121 minutos.
Valoración y margen sólo cubren esas ventanas: pérdida desde inicio, spot/corto
y holgura mientras existe corto, con frecuencia y cobertura explícitas. Mark
ausente o precio arrastrado conserva sus límites; precio de valoración no
prueba venta durante suspensión ni máximo intradía global. H1/oportunidad H3
son poblaciones BASE autenticadas cuando hay cobertura; H2/H3 financiero usa
cada trayectoria. L frente a LC no es una descomposición aditiva. Mayor demora
no impone P&L monótono ni define una política ganadora.

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

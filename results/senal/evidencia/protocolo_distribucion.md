# Protocolo descriptivo: señal y selección de entradas

Distribución documental del 10 de octubre de 2026, derivada del paquete del
27 de septiembre de 2026. Matriz cerrada: seis variantes independientes para
las dos estrategias, doce corridas nuevas históricas y dos BASE reutilizadas.

| ID | Únicos campos económicos diferentes de BASE |
|---|---|
| H072 | horizon_hours=72; holding_hours=72 |
| H336 | horizon_hours=336; holding_hours=336 |
| V012 | half_life_hours=12 |
| V048 | half_life_hours=48 |
| B025 | basis_max=0.0025 |
| B100 | basis_max=0.01 |

No hay cruces de dimensiones. H072/H336 modifican conjuntamente pronóstico,
target y tenencia/renovación; son una dimensión económica compuesta, con riesgo
prioritario. El costo sigue siendo 34 pb por ciclo, sin escala H/168. La
financiación realizada del target usa intervalos reales de funding en
(señal, señal+H], sin escalar un target de 168 h. La exclusión de predicciones
finales incompletas de H1 no recorta la trayectoria financiera ni agrega datos
posteriores al final exclusivo. Los errores se expresan en pb/72 h, pb/168 h
o pb/336 h; un MAE menor de otro horizonte no ordena calidad predictiva.
La habilidad descriptiva 1-MAE_EWMA/MAE_no_change requiere denominador positivo.

V012/V048 sólo cambian pesos, con peso 1/2 a edad igual a la vida media;
mantienen historia, targets, no-change y costo. La invariancia de la permanente
se comprueba en la economía; forecasts y diagnósticos pueden cambiar. B025/B100
mantienen piso cero y extremos inclusivos, sin cambiar stop de ampliación ni
renovación. Economía, decisiones, H1 y oportunidad H3 se verifican separadamente;
un H1 reutilizado o una cartera invariante no determina la invariancia de H3.

Entradas distinguen partición excluyente funding/basis, no evaluables, primer
bloqueo y acciones efectivas. En la permanente, fallo descriptivo de funding
no es bloqueo. Renovaciones, intentos, ciclos, órdenes y fills son poblaciones
diferentes. Se conservan sumas/conteos de H3 y la causa de observaciones no válidas.
La ciencia completa y los contratos de pruebas están además en el protocolo
previo, registro de escenarios, configuraciones, código y controles retenidos.

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

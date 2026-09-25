# Decisiones de integración — versión técnica preliminar

Este documento acompaña la primera tanda acotada del [protocolo](protocolo.md).
El feedback del profesor sigue pendiente. La [matriz](matriz_integracion.csv)
contiene una fila por cada uno de los 345 hechos del registro sellado, con los
campos pedidos, `fact_id`, `source_id`, conocimiento y aplicabilidad originales.
Fue generada antes de modificar el comportamiento económico. No modifica
`loadable_by_rulebook=false`, los estados documentales ni los hashes originales.

El [registro](../evidencia_historica/data/research/historical-rules-followup-20260924T234206Z/reglas_historicas.json)
y el [catálogo de fuentes](../evidencia_historica/data/research/historical-rules-followup-20260924T234206Z/fuentes.json)
distinguen `intervalo_respaldado`, `evento_respaldado`, `observacion_puntual`,
`derivado`, `supuesto`, `contradictorio`, `pendiente` y `fuera_de_alcance`.
El estado `contradictorio` tiene cero hechos en este paquete; se conserva como
categoría admisible y no se usa para diferencias legítimas antes/después.

## Decisiones que habilitan la primera tanda

| Decisión | Respaldo documental | Tratamiento |
|---|---|---|
| Cero realizado BTCUSDT spot | `BTC_SPOT_ZERO`; `PROMO_START`, `PROMO_END` | Intervalo `[2022-07-08T14:00:00Z, 2023-03-22T00:00:00Z)`; no se extiende a ETH ni perpetuos. Los dos extremos se cotejaron contra los textos conservados. |
| BTC promoción en decisiones | Mismo hecho; `knowledge.known_from_utc=null` | Conocer la tarifa al entrar en vigencia es una hipótesis experimental explícita. No se inventa un timestamp de conocimiento histórico. No se anticipa el fin de promoción para calcular el costo contemporáneo. |
| Spot 10 pb fuera de promoción | `FEE_SPOT26_BTCUSDT`, `FEE_SPOT26_ETHUSDT`; `SPOT26` | La captura acredita una tabla base puntual. Mantener 10 pb fuera del intervalo es el supuesto BASE_E3, sin certificar toda la tarifa histórica ni ausencia de otras promociones. |
| FUT4 a lo largo de la muestra | `FEE_A1_BTCUSDT`, `FEE_A1_ETHUSDT`, `FEE_A2_BTCUSDT`, `FEE_A4_BTCUSDT`, `FEE_A3_BTCUSDT`; `A1–A4` | Comparación experimental de 4 frente a 5 pb. `PENDING_FEE_DATE_BTCUSDT/ETHUSDT` sigue pendiente. Una FAQ o la pista `LEAD_OCT` no fecha la transición. |
| Doble mantenimiento | Supuesto experimental del protocolo | `MM_estres(N)=2*MM_base(N)`, preservando pisos y techos, escalando tasas y deducciones; apalancamiento inicial 2x sin cambio. No es tabla histórica Binance. |

Los [textos de inicio](../evidencia_historica/data/research/historical-rules-followup-20260924T234206Z/extraidos/PROMO_START_web.txt)
y [fin](../evidencia_historica/data/research/historical-rules-followup-20260924T234206Z/extraidos/PROMO_END_web.txt)
contienen UTC explícito en los extremos operativos. Sus etiquetas de publicación
`2022-07-06 14:00` y `2023-03-15 06:10` no tienen zona acreditada; los cuerpos
actuales tienen enmiendas. No se convierten esas etiquetas en `known_from`.
Las reglas de tarifa dentro de una ventana VWAP y los controles de las variantes
se fijan en el protocolo económico; este diagnóstico sólo informa las fronteras
de fills originales.

## Filtros: campos distintos y cobertura incompleta

Las siete capturas API contienen observaciones, no intervalos de vigencia.
`SPOTI22`, `SPOTI23`, `SPOTI25`, `FUTI22`, `FUTI22B`, `FUTI26`, `FUTI26B`
se conservan con sus capturas reales; `serverTime` tampoco es `valid_from`.
La matriz mantiene un `fact_id` distinto por símbolo, filtro y componente,
por ejemplo `SPOTI22_BTCUSDT_MARKET_LOT_SIZE_stepSize` y
`FUTI26_BTCUSDT_MIN_NOTIONAL_notional`, vinculados a sus `source_id` homónimos.

`LOT_SIZE.minQty`, `maxQty` y `stepSize` se leen por separado. No se deriva el
mínimo del step. `MARKET_LOT_SIZE` no borra automáticamente `LOT_SIZE`.
Los ceros spot MARKET se retienen como valores publicados, con semántica
pendiente: se omite la operación aritmética no definida y se cuenta el caso como
no evaluable, sin módulo por cero ni imputación de un valor positivo.
La documentación actual `DOCSPOTRAW` sobre ceros de `PRICE_FILTER` no basta
para acreditar la interacción histórica de todos los filtros MARKET.

`maxQty` limita cantidad de cada orden; `NOTIONAL.maxNotional` limita nocional
de orden sólo bajo sus banderas; el techo de una tabla de mantenimiento limita
nocional de posición en el tramo correspondiente. No son intercambiables.
Los hechos `SPOTI23_*_NOTIONAL_maxNotional` y
`SPOTI25_*_NOTIONAL_maxNotional` llevan `applyMaxToMarket=false`: el máximo
publicado de 9.000.000 USDT no se impone a las órdenes MARKET diagnosticadas.
El precio de referencia y `avgPriceMins` del filtro tampoco equivalen
automáticamente al precio de un fill. Banderas no publicadas de futuros
permanecen desconocidas.

`EVENT_MINSPOT23_*` / `MINSPOT23` y `EVENT_MINFUT23_*` / `MINFUT23` dicen
«a más tardar»; no se convierte su deadline en instante efectivo.
`EVENT_MINBTC26_BTCUSDT` / `MINBTC26` anuncia comienzo y duración aproximada
de cuatro horas, sin final garantizado. Las órdenes previas conservan reglas
en esos avisos; una regla global por timestamp no representa esa excepción.
`EVENT_TICK22_BTCUSDT` / `TICK22` sí tiene instante explícito, pero tampoco
demuestra continuidad posterior ilimitada.

El motor actual `RuleBook` exige snapshots completos, valores positivos para
step/mínimos/máximos y validez/conocimiento comprobables. Usa un solo juego
de filtros por mercado. No hay representación separada de todas las banderas,
despliegues, cohortes o campos API. La matriz describe estas incompatibilidades;
no debilita los controles del motor ni crea un `history.json` mixto.

## Margen: tablas relativas, deducciones y cohortes

Las 16 tablas `TIERS_MARG22_*`, `TIERS_MARG23_*`, `TIERS_MARG24_*`,
`TIERS_MARGBTC25_*` y `TIERS_MARGAUG25_*`, fuentes `MARG22`, `MARG23`,
`MARG24`, `MARGBTC25`, `MARGAUG25`, se diagnostican individualmente.
Las tablas `before` no prueban desde cuándo regían. No se vinculan tablas
coincidentes mediante continuidad supuesta ni se fechan cambios intermedios ETH.

Cada tramo publicado tiene piso exclusivo y techo inclusivo. El diagnóstico
comprueba los 177 techos, la selección del tramo inferior en la frontera y la
igualdad de las fórmulas a ambos lados de cada frontera interna. Las deducciones
`*_DERIVED` usan `D0=0; Di=D(i-1)+floor_i*(rate_i-rate_(i-1))`; la continuidad
y la deducción inicial cero son supuestos analíticos. No se recuperaron importes
`cum` publicados. El código de margen original ordena tramos y acepta ambos
extremos; al escoger primero el inferior coincide en fronteras contiguas, pero
esa coincidencia no resuelve tablas discontinuas ni las políticas de cohortes.

`TIERS_MARG22_ETHUSDT_after` afecta posiciones existentes.
Los eventos `TIERS_MARG23_*_after` y `TIERS_MARG24_*_after` las preservan.
Junio/agosto de 2025 las afectan. Diciembre de 2023 aparece en un anuncio
publicado retrospectivamente en enero de 2024, sin timezone acreditada:
no se iguala `known_from` a su vigencia. Mayo de 2024 y junio/agosto de 2025
son despliegues aproximados. La política para aumentos posteriores no está
resuelta y se identifica con los `fill_id` reales en el diagnóstico.

La elección aislada 2x permanece independiente de la tabla de mantenimiento.
El máximo apalancamiento inicial por tramo se conserva documentalmente;
no se usa 2x como índice de fila ni se confunde un límite de posición con una
cantidad máxima por orden. Las capturas `FUTI*_..._liquidationFee` y
`LIQ_BASIS_*` / `FAQ_LIQ` tampoco completan la cronología de los cargos de
liquidación o su cobro simultáneo con la comisión regular.

## Diagnóstico ejecutado y límites

El comando nuevo [diagnose_historical_rules_exposure.py](../herramientas/diagnose_historical_rules_exposure.py)
no importa el motor, no hace backtests y sólo escribe en una carpeta nueva.
Lee las corridas originales `run_ad71d751b20623006c195ff3` y
`run_dfea4b7ac1475668d5968c97`, comprueba manifiestos y hashes, y conserva
Decimal. Los resultados y definiciones están en
[diagnostico_historico](../diagnostico_historico/README.md).

Las cantidades de órdenes son las solicitadas en eventos `submitted`, una
sola vez por `order_id`, y no el total repetido de eventos más filas finales.
El nocional candidato es `quantity solicitada * reference_price del primer
fill`, sólo cuando existe fill. No se presume precio de aceptación ni precio
medio histórico del filtro. Las órdenes sin fill quedan sin nocional.
Los nocionales de posición usan short × mark al cierre diario; no máximos
intradiarios. Las cantidades existentes en eventos se reconstruyen del ledger,
sin imponer una política de migración o cohortes.

Un resultado sin candidatos en órdenes existentes no descarta operaciones
que habrían aparecido con filtros más permisivos ni prueba ausencia de riesgo
entre cierres diarios. Las diferencias de mantenimiento son saldos requeridos,
no costos ni P&L; no se suman a rentabilidad y no sustituyen recálculo de cartera.

## Segunda tanda propuesta — no ejecutada

No se propone cruzar automáticamente variantes de comisiones y margen.
Cada caso siguiente usaría ambas carteras y BASE_E3 como comparador, manteniendo
datos, ejecución, parámetros de estrategia y comisiones base. Son candidatos
para decidir después de revisar la primera tanda; no cronología certificada.

| Caso acotado | Parámetros y comparación | Fundamento | Condición y limitación antes de ejecutar |
|---|---|---|---|
| TICK_BTC_20220215 | Único evento de tick BTC perpetuo 0,01→0,1 en 2022-02-15 03:30 UTC; observar ventana local y trayectoria posterior | `EVENT_TICK22_BTCUSDT` / `TICK22` | Requiere explicitar política de persistencia fuera de la ventana y conservar tick de órdenes previas. El evento es exacto; la continuidad posterior no está probada. |
| MINIMOS_LOCALES | Evaluar spot 10→5, futuros BTC 5→100/ETH 5→20 y BTC 100→50 como ramas separadas, en ventanas breves predefinidas de cada aviso | `EVENT_MINSPOT23_*` / `MINSPOT23`; `EVENT_MINFUT23_*` / `MINFUT23`; `EVENT_MINBTC26_BTCUSDT` / `MINBTC26` | Acordar instantes alternativos sólo como hipótesis, banderas MARKET y exenciones. No interpretar deadline o duración aproximada como fecha exacta; no prolongar forward-fill. Prioridad menor por ausencia de órdenes candidatas registradas, sin inferir ausencia de entradas latentes. |
| ETH_MARGEN_COHORTES | Evento ETH septiembre 2022; luego prueba separada del evento diciembre 2023 sobre cohortes nuevas frente a existentes | `TIERS_MARG22_ETHUSDT_after` / `MARG22`; `TIERS_MARG23_ETHUSDT_after` / `MARG23` y `*_DERIVED` | Acordar duración de aplicación, conocimiento experimental y política de aumentos. Mantener deducciones como derivadas. En diciembre hay posiciones previas y un aumento posterior de la permanente: reemplazar todas las posiciones sería una hipótesis adicional. |

Las siete capturas completas y las 16 tablas no se cargan masivamente.
No se ejecutan interpolaciones, barridos de fechas de transición FUT4→FUT5,
forward-fill prolongado ni políticas de cohortes implícitas. Su decisión queda
pendiente; ese límite es independiente de las seis configuraciones autorizadas
de la primera tanda.

## Reproducción

Con el intérprete del proyecto y una ruta de salida que todavía no exista:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/diagnose_historical_rules_exposure.py --root . --runs-root D:/Backtesting/outputs --output entregas/entrega_4/reglas_historicas/reproduccion_diagnostico_nueva
.venv/Scripts/python.exe -X utf8 -m pytest tests/unit/test_historical_rules_exposure.py -q -p no:cacheprovider
.venv/Scripts/ruff.exe check scripts/diagnose_historical_rules_exposure.py tests/unit/test_historical_rules_exposure.py
```

`--evidence` permite ubicar el paquete en otra ruta; deben conservarse también
las dependencias A1–A3 bajo la raíz indicada y los antecedentes de `docs/research`.
Para regenerar la matriz se usa `--matrix ruta_nueva.csv`; el comando rechaza
sobrescribirla. La verificación documental de publicación independiente corresponde
al nuevo verificador y su guía, no a este diagnóstico de exposición.

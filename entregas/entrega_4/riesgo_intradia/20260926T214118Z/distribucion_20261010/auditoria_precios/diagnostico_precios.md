# Auditoría de precios y disponibilidad temporal

La reconstrucción de precios puede realizarse con las fuentes locales existentes. Se verificaron contra los hashes publicados las 344 particiones relevantes: 228 de velas, 114 de marks y dos de funding. No faltan archivos. Se verificaron los 38 archivos de código congelado de cada una de las cuatro corridas. Esta comprobación no acredita por sí sola la completitud contable, que corresponde a la auditoría del ledger.

La ejecución reproducible y sus tiempos reales están en [resultado_auditoria_precios.json](resultado_auditoria_precios.json); la segunda ejecución desde `C:/Users/pablo/Downloads` está en [resultado_desde_otra_ruta.json](resultado_desde_otra_ruta.json). Ambas terminaron con `passed=true`. La comparación exacta mediante Decimal comprende 27.264 precios: cuatro campos por cierre, 1.704 cierres y cuatro carteras, sin diferencias. Esta es una conciliación de precios; todavía no es la conciliación de equity.

## Fuentes y código aplicable

- BASE condicional: `run_ad71d751b20623006c195ff3`; BASE permanente: `run_dfea4b7ac1475668d5968c97`; código `codigo_base/` del paquete padre.
- MARGEN_2X condicional: `run_70383794701c4f0fc157b2ed`; permanente: `run_3f5d9cce8ff1c2ba5447e3b6`; código `codigo_ejecutado/` del paquete padre.
- Raíz efectiva de datos: `D:/Backtesting`. Manifiesto: `data/minutes/2022_2026_continuous/derived_marks/futures_scaled/manifests/processed.json`, SHA256 `cc5cd0821513fd98d39a4f299a62ce77d94e0865595805db2f9e806b513e3cc5`.
- Cada ruta de `entries[].path` se resuelve contra esa raíz. La carpeta derivada contiene solamente tres particiones de marks sustituidas; las demás entradas apuntan a las particiones originales. No debe globearse solamente la carpeta derivada ni mezclarse con los marks originales que reemplaza.
- Velas: `processed/dataset=minute_bars/symbol={BTCUSDT|ETHUSDT}/market={spot|futures}/month=YYYY-MM/`. Marks: `processed/dataset=marks/...` con las tres sustituciones explícitas. Funding: `processed/dataset=funding/symbol={symbol}/market=futures/date=all/part-00000.parquet`. Los nombres de archivo de antecedentes de diciembre de 2021 no son uniformes; manda el manifiesto.

Los esquemas y rutas concretas están en el JSON. Las cantidades y precios son strings decimales; todos los tiempos normalizados son int64 en nanosegundos UTC. `timestamp_unit` del manifiesto describe el archivo de origen: spot cambia de milisegundos a microsegundos desde 2025. No es la unidad del Parquet normalizado.

## Política original que debe reproducirse

En `codigo_base/src/crypto_carry/strategy.py:90-98`, spot se toma de `trades[(symbol,"spot")].price` y futuros se valúan al `marks[symbol].close`. `models.py:49-77` define que la propiedad `MinuteBar.price` es el cierre y que `end_time` es el límite exclusivo. `strategy.py:919-959` actualiza referencias de velas sólo con `base_volume > 0`; el mark se actualiza cuando llega su disponibilidad. Los mismos bloques tienen igual comportamiento en el código MARGEN_2X.

Por tanto, a un instante `t` se selecciona el último cierre spot con volumen positivo y `available_at <= t`. Una vela de volumen cero no renueva ni el precio observado ni su edad. Un registro inexistente tampoco renueva la observación. Para el mark se selecciona el último `available_at <= t`, conservando `estimation_method`, `anchor_open_time` y fuente.

Las velas se conocen en `open_time + 60 s = end_time = available_at` (`data/normalize.py:283-296`). Los marks oficiales tienen `close_time = open_time + 59.999 s` y `available_at = close_time + 1 ms` (`data/normalize.py:391-411`). Las velas de ejecución y los marks confluyen en la misma frontera disponible, pero no debe confundirse cierre crudo con límite exclusivo.

Los cierres diarios originales son `23:59:59.999999999 UTC`, por `strategy.py:1146-1147,1182-1203`. En condiciones normales utilizan la vela abierta a las 23:58, disponible a las 23:59. La vela abierta a las 23:59 recién estará disponible a las 00:00 del día siguiente. Los cuatro campos de precio de cada cierre publicado coinciden exactamente con esta selección causal.

`_fresh` (`strategy.py:140-152`) exige barras spot/perpetuo alineadas, volumen positivo en ambas y edad spot dentro de 60 segundos para controles de entrada. Esta regla no elimina del patrimonio un saldo spot cuyo último precio quedó antiguo. La edad de valoración y la admisibilidad para ejecutar son conceptos distintos.

El reloj económico del funding usa `funding_time`, no `available_at` (`events.py:18-25`). Los 5.112 eventos por símbolo conservan sus tiempos exactos; 2.176 no caen en una hora exacta y su disponibilidad informativa se retrasa 60 segundos. El código carga los datos del instante, aplica funding sobre el corto anterior a fills, procesa fills y luego controles (`strategy.py:892-1025`). No debe desplazarse el pago al timestamp de publicación ni redondearlo a una hora.

## Cobertura y dos excepciones diferentes

La muestra tiene 2.453.760 puntos de minuto en `[2022-01-01,2026-09-01)`. Ambas series de marks cubren todos esos puntos, después de las 15 aproximaciones ya aprobadas: dos BTC y trece ETH, en julio de 2022 y agosto de 2024. Se mantienen como `futures_scaled`, no como observaciones oficiales. Su regla y anclas están en `data/mark_gaps.py:24-124`; no se extiende la excepción.

Independientemente, cada fuente de funding tiene 2.005 marks de liquidación nulos dentro de la muestra. `data/funding_proxy.py:12-51` resuelve esas liquidaciones con `previous_closed_1m`, cuando existe el mark previo correcto y disponible. Esta excepción no es la de los 15 huecos de marks.

Cada spot tiene 2.453.680 registros dentro de la muestra: faltan 80, todos en la suspensión documentada de marzo de 2023; otros 72 registros de esa suspensión tienen volumen cero. Futuros dispone de todos los registros, aunque 308 velas BTC y 213 ETH tienen volumen cero; estos ceros no se convierten en fills ni actualizan la referencia de ejecución. Los marks de riesgo son otra fuente y permanecen disponibles. Los bloques precisos de ceros y las procedencias se conservan en el JSON.

## Suspensión del 24 de marzo de 2023

El calendario congelado (`data/market_calendar.py:23-31`) documenta las aperturas de minuto spot suspendidas en `[11:28,14:00) UTC`. Hay 72 velas de volumen cero abiertas entre 11:28 y 12:39; faltan 80 abiertas entre 12:40 y 13:59. El último registro crudo de volumen cero de las 12:39 tiene cierre anticipado, conservado en las muestras crudas del JSON; su normalización como vela no aporta un precio negociado nuevo.

La última vela spot válida y alineada se abrió a las 11:27 y estuvo disponible a las 11:28. El ancla fija es:

| Activo | Spot del ancla | Cierre perpetuo del ancla | Disponible UTC |
|---|---:|---:|---|
| BTC | 28.080,00 | 28.070,00 | 2023-03-24 11:28:00 |
| ETH | 1.789,52 | 1.788,54 | 2023-03-24 11:28:00 |

Todos los futuros necesarios durante el hueco existen y tienen volumen positivo. El proxy solicitado es viable sin descarga y sin usar la reapertura futura. En los puntos de disponibilidad 11:29–14:00, el spot original conserva el ancla: 152 puntos sin precio nuevo, no 152 archivos ausentes. En 14:00, la antigüedad de disponibilidad es 9.120 segundos; el nuevo spot sólo se conoce a las 14:01, al cerrar la primera vela de reapertura.

Los mínimos del proxy de precios durante todo el hueco, antes de considerar posiciones, ocurren a las 11:48: BTC 27.430,568721 y ETH 1.739,882817. No son pérdidas de cartera ni mínimos necesariamente pertenecientes a los 121 minutos posteriores al cierre del futuro. El JSON conserva esos cálculos como diagnóstico de factibilidad de valoración. A las 14:01 se observa BTC 27.925,59 y ETH 1.763,69; el proxy en esa misma frontera habría sido 27.902,936943 y 1.760,063869. Se retoma el spot observado, con una diferencia respectivamente de 22,653057 y 3,626131 USDT por unidad. No se infiere un precio ejecutable durante la suspensión.

La valoración original sigue siendo computable con su arrastre, pero el precio spot contemporáneo es desconocido durante la interrupción. La ausencia de un precio nuevo es una limitación de valoración de mercado, no prueba de una pérdida nula ni una carencia que un replay del mismo archivo pudiera subsanar. Este análisis de precios no justifica un replay instrumentado.

## Repetición y lectura eficiente

```powershell
& 'C:/Users/pablo/Documentos/UCEMA/Tesina/Backtesting/.venv/Scripts/python.exe' -B -X utf8 `
  'C:/Users/pablo/Documentos/UCEMA/Tesina/Backtesting/entregas/entrega_4/riesgo_intradia/20260926T214118Z/auditoria_precios/auditar_precios.py' `
  --package 'C:/Users/pablo/Documentos/UCEMA/Tesina/Backtesting/entregas/entrega_4/reglas_historicas/20260925T005436Z' `
  --data-root 'D:/Backtesting'
```

El programa sólo escribe JSON en stdout. Utiliza `ParquetFile.iter_batches(batch_size=65536, columns=...)`, cast de strings con Arrow a float64 y búsqueda temporal con NumPy. Mantiene un bloque de precios por fuente y convierte únicamente los precios diarios y muestras pequeñas a Decimal. Evita construir millones de objetos Decimal y evita `pq.read_table` con inferencia de particiones Hive; los esquemas se leen directamente del archivo. La lectura mensual debe compartirse entre las cuatro carteras.

El primer intento del programa falló porque `Array.to_numpy()` exige copia explícita para strings. La corrección fue `zero_copy_only=False`, sin alterar entradas; el traceback real se conserva como `primer_intento_resultado_auditoria_precios.stderr.txt`. La ejecución posterior y la repetición desde otra carpeta pasan. [ruff.txt](ruff.txt) registra `All checks passed!`.

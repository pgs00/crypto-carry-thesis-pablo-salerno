# Linaje comprobado de la exposición editorial de E3

La clasificación original se recuperó exactamente. No falta ningún metadato imprescindible en las doce corridas conservadas. No hizo falta reconstruir posiciones desde ledger y eventos: las doce contienen la trayectoria completa en `positions.parquet`, además de dos snapshots finales. Se ejecutaron exclusivamente lecturas y las dos funciones puras archivadas de E3, sin iniciar el motor ni consultar fuentes externas.

## Fuentes originales y cadena de preparación

- `Paquete de evidencia/codigo/scripts/continuous_delivery/portfolio.py`: funciones `exposure_intervals` y `exposure_summary` archivadas.
- `Paquete de evidencia/codigo/scripts/continuous_delivery/build.py`: carga `positions.parquet` mediante `read_rows`, clasifica una sola vez entre `timestamp(config.start)` y `timestamp(config.end)`, y después recorta los tres períodos al resumir. La misma carga se exporta a `evidencia/positions.csv`.
- `Paquete de evidencia/codigo/scripts/continuous_delivery/common.py`: `read_rows` usa `ParquetFile.read().to_pylist()` y elimina únicamente `units`, `data_kind`, `run_id`; no ordena ni agrega filas. Los números monetarios se conservan como cadenas decimales y luego `Decimal`.
- `Paquete de evidencia/codigo/src/crypto_carry/strategy.py`: `_transition` registra el evento, actualiza el estado y llama `_position_row`. `_position_row` guarda estado y `asdict` de la posición del ledger. Después de un fill aplicado al ledger y de `_after_fill`, vuelve a guardar la posición. `_daily` también registra ambas posiciones. Inicialmente se construyen posiciones vacías para los símbolos configurados.
- `Paquete de evidencia/codigo/src/crypto_carry/reporting.py`: `_persist_tables` conserva el orden de `b.positions`, marca esas filas `snapshot_kind=event` y añade `_final_positions`. Los finales incorporan cantidades negociables y polvo calculados con las reglas y precios del momento de la corrida. `_write_table` conserva el orden de las filas.
- `Paquete de evidencia/tablas/exposicion_intervalos.csv` y `tablas/tiempo_invertido.csv`: evidencia numérica editorial original.
- `entregas/entrega_3/continua/tablas/tiempo_invertido.csv`: tabla publicada, idéntica en bytes a la tabla del paquete.
- `entregas/entrega_3/paquete_actualizacion_entrega_3_continua.zip`: se comprobaron diez miembros relevantes contra los archivos de `Paquete de evidencia`; todos son idénticos en bytes. No se extrajo ni se modificó el ZIP.

El diagnóstico adjunto guarda 84 hashes de entradas. Los snapshots ejecutados originales y los scripts nuevos de auditoría conservan identidades separadas.

## Contrato de clasificación

Por símbolo, E3 introduce una posición inicial vacía en el inicio completo de la muestra, ordena establemente por `time_ns` y conserva la última fila persistida para cada timestamp. Los empates no se ordenan por estado, tipo de evento, id ni cantidad. Hay 92 filas duplicadas por símbolo/timestamp en BASE condicional y 217 en BASE permanente; no son errores de datos, sino actualizaciones efectivas simultáneas.

Para cada intervalo hasta el siguiente timestamp o el final exclusivo:

1. `dust`: `spot > 0`, `short == 0`, y al menos una condición: `dust_spot > 0`, estado `FLAT` o `COOLDOWN`, o `spot <= known_dust`. Cuando se clasifica polvo, `known_dust` pasa a ser el saldo spot observado.
2. `covered`: si no fue polvo, ambas patas son positivas y `abs(spot-short)/spot <= hedge_tolerance`.
3. `unhedged`: si no se cumplieron las anteriores, alguna pata es positiva.
4. `flat`: ambas patas vacías.

`known_dust` se conserva durante las fases activas y no se reinicia al abrir otra posición, cambiar de estado o recortar un período. Esta es la semántica archivada; no se sustituyó por un umbral monetario ni por reglas actuales. El polvo puede ser el saldo heredado durante una nueva apertura, pero un fill que aumenta la cantidad por encima del residuo conocido sigue siendo exposición activa. Un corto sin spot es exposición activa sin cobertura. Una suspensión por sí misma no produce polvo.

Los snapshots de eventos carecen habitualmente de `dust_spot`; no es una carencia para esta metodología porque incluyen el estado persistido y la historia completa. Los finales tienen los metadatos adicionales originales. No se debe interpretar una ausencia de estado/cantidades en una fuente distinta como cero ni como reproducción exacta.

Se clasifica desde `2022-01-01T00:00:00Z` hasta `2026-09-01T00:00:00Z`, exclusivo, y después se recortan períodos. Ejecutar el clasificador desde un corte tardío podría perder `known_dust`; no reproduce este flujo original.

## Cruce con ledger, eventos y cobertura

Las doce corridas del paquete padre `20260925T005436Z` tienen entre 3747 y 4158 snapshots, incluidos dos finales. El auditor comprobó para cada una:

- Cero filas de posiciones sin estado, spot o short.
- Cada cambio de cantidades spot/short en el ledger tiene un snapshot de posición en el mismo timestamp.
- Las últimas cantidades de posición por timestamp coinciden exactamente con las últimas cantidades del ledger disponibles a ese momento.
- El último estado de cada timestamp con transición coincide con el último snapshot de posición.
- Estado de corrida `complete`, límites solicitados iguales y snapshots finales en `1788220799999999999`.

El ledger incluye cobros de funding sin cambio de cantidades; esos timestamps no necesitan nuevos intervalos de exposición. Usar ledger a solas descarta la información que permite excluir polvo. Rehacer una unión de tablas en estas fuentes sería redundante y podría introducir un orden artificial entre eventos simultáneos.

`run_context.full_baseline_coverage=False` no significa aquí un período incompleto: `data/validate.py` exige explícitamente `not research` para activar esa bandera. Estas corridas son `prescribed_research`; los registros de calidad tienen alcance `full` y estado `complete`. Deben distinguirse cobertura temporal y certificación histórica de reglas. El estado, las fechas y los registros diarios efectivos permiten validar la comparación temporal; una bandera de certificación no sustituye esos controles.

## Equivalencia exacta de BASE

El auditor extrajo por AST solamente las dos funciones puras del archivo archivado y las aplicó a los Parquet del paquete padre. Comparó todos los campos, por fila y en orden, sin tolerancias ni redondeos:

- 3710 intervalos condicionales: cero diferencias con E3.
- 3913 intervalos permanentes: cero diferencias con E3.
- Los 18 resúmenes de los tres períodos y tres ámbitos: cero diferencias con E3.
- Todas las filas y campos leídos de ambas trayectorias BASE: cero diferencias con `evidencia/positions.csv` de E3.

| Métrica completa | Condicional | Permanente |
|---|---:|---:|
| Segundos calendario | 147225600 | 147225600 |
| Segundos invertidos, unión | 41691120 | 144587820 |
| Porcentaje, expresión exacta | 41691120 / 147225600 × 100 | 144587820 / 147225600 × 100 |
| Porcentaje decimal (28 dígitos significativos) | 28.31784689619196661450182577 | 98.20834148408972352634324465 |
| Segundos con algún activo sin cobertura | 11340 | 16440 |
| Segundos con algún activo cubierto | 41682240 | 144579240 |
| Segundos con ambos activos cubiertos | 22773720 | 138662400 |
| Segundos sin posiciones activas, admite polvo | 105534480 | 2637780 |

Los porcentajes impresos 28,32% y 98,21% son consecuencia del redondeo. `any_covered` y `any_unhedged` se superponen: su suma excede tiempo invertido en 2460 segundos condicionales y 7860 permanentes. Debe integrarse la unión, no sumarse esos dos indicadores.

En el episodio del 24/03/2023, de 12:00 a 14:01 UTC, hay exactamente 7260 segundos (121 minutos) sin cobertura en ETH condicional y en BTC/ETH permanente. La unión de cartera es 7260 segundos en ambas. El resto del día comprende 43200 segundos cubiertos y 35940 segundos posteriores con polvo en los activos afectados. No representa todo el tiempo sin cobertura de la muestra.

## Nanosegundo terminal

E3 usa el final exclusivo configurado `1788220800000000000`; el último snapshot ocurre un nanosegundo antes. Con esa convención no existe discrepancia frente a E3, ni de intervalos ni de duraciones.

Si se usara por error `end-1` como final exclusivo, faltaría exactamente `0.000000001` segundo calendario. En la condicional faltaría ese nanosegundo de polvo en cada activo y de tiempo sin posiciones activas de cartera; tiempo invertido no cambiaría. En la permanente faltaría ese nanosegundo de cobertura en cada activo y en las uniones de invertido, alguno cubierto y ambos cubiertos. La comparación cuantificada se conserva en `terminal_nanosecond_if_wrong_end_used`. No se aplicó tolerancia para ocultarla.

## Contabilidad y límites

`covered + unhedged + dust + flat = calendario` por activo. La cartera integra sobre los extremos comunes de todos los intervalos. Debe separar tiempo sin posiciones activas, tiempo únicamente con polvo y tiempo sin inventario: conservar polvo no equivale a efectivo puro. El bruto con cualquier saldo positivo es otra métrica. Excluir polvo del indicador operativo no retira sus unidades, valuación ni riesgo de precio de equity o P&L.

Esta auditoría no volvió a calcular resultados económicos, no ejecutó pruebas del motor ni verificadores generales, y no cambió fuentes. Acredita la recuperación exacta de la metodología e inputs editoriales y su disponibilidad para las doce carteras; los demás controles pertenecen a la corrección principal.

Comando ejecutado desde la raíz del proyecto:

```powershell
& .venv/Scripts/python.exe -B -X utf8 entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/auditoria_linaje/reproducir_linaje.py
```

Resultado: 12 corridas, 10 comparaciones de miembros del ZIP, 84 hashes de fuentes, cruces posición/ledger/transición sin diferencias y equivalencia BASE exacta. La salida detallada está en `linaje_resultados.json`. El script escribe únicamente ese JSON nuevo, junto al propio script.

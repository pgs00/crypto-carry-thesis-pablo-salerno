# Auditoría de cuentas y reglas congeladas

La evidencia persistida permite reconstruir caja, deuda, cantidades, precio medio y garantía sin replay. La comprobación ejecutada concilia exactamente los 6.816 cierres diarios de las cuatro carteras, usando sus precios diarios originales. Esto acredita integridad contable; todavía no acredita cobertura ni frescura de los precios de minuto.

El prompt original se leyó completo. Esta auditoría se limita a cuentas, secuencia económica, reglas de margen y evidencia de compromisos de órdenes. No recalcula el drawdown ni produce resultados nuevos de estrategia. El procesamiento lee exclusivamente el paquete padre; no importa ni ejecuta el motor.

## Comando y resultado ejecutados

Desde la raíz del proyecto:

```powershell
.venv/Scripts/python.exe -B -X utf8 entregas/entrega_4/riesgo_intradia/20260926T214118Z/auditoria_contable/auditar_cuentas.py --source-package entregas/entrega_4/reglas_historicas/20260925T005436Z --output entregas/entrega_4/riesgo_intradia/20260926T214118Z/auditoria_contable/resultados.json
```

Resultado real: exit code 0, `status=pass`, 6.816 cierres y cero cambios en 128 fuentes observadas. El JSON guarda comando, hashes, comprobaciones por corrida, fórmulas, referencias y todos los residuos diarios. Omitir `--output` imprime el JSON y no escribe archivos. La salida explícita no puede estar dentro del paquete padre.

La validación leyó 38 archivos de código por versión congelada y los contrastó con los hashes de los manifiestos originales. `codigo_base` corresponde a las dos BASE y `codigo_ejecutado` a las dos MARGEN_2X. `ledger.py`, `margin.py`, `risk.py`, `portfolio.py`, `models.py` y `data/rules.py` son idénticos entre ambas versiones. La diferencia de `strategy.py` es la función que resuelve la tarifa realizada; las reglas de contabilidad, secuencia y reservas auditadas permanecen iguales. La configuración efectiva mantiene las tarifas BASE para estas cuatro carteras.

| Corrida | Ledger | Fills | Funding | Cierres | Residuos de cuentas/equity |
| --- | ---: | ---: | ---: | ---: | --- |
| BASE condicional `run_ad71d751b20623006c195ff3` | 2.372 | 138 | 2.234 | 1.704 | cero |
| BASE permanente `run_dfea4b7ac1475668d5968c97` | 10.159 | 332 | 9.827 | 1.704 | cero |
| MARGEN_2X condicional `run_70383794701c4f0fc157b2ed` | 1.943 | 110 | 1.833 | 1.704 | cero |
| MARGEN_2X permanente `run_3f5d9cce8ff1c2ba5447e3b6` | 9.906 | 324 | 9.582 | 1.704 | cero |

El orden original de sumas Decimal reproduce equity exactamente. Una agrupación algebraicamente equivalente de sumas en el tanteo inicial producía diferencias de hasta 1E-23; el script guardado replica `Ledger.equity` y obtiene cero. Se conserva la tolerancia original 1E-8, sin ensancharla.

## Contrato de reconstrucción

Las rutas siguientes son relativas al paquete padre `entregas/entrega_4/reglas_historicas/20260925T005436Z`.

- `codigo_base/src/crypto_carry/ledger.py:29-53`: estado inicial `free_spot=10000`, `free_futures=debt=0`. `strategy.py:52-54` inicializa cada posición en cero. No es preciso inferir el inicio a partir del primer cierre, y no hay reinicios anuales.
- `ledger.py:121-148`: cada fila contiene el estado POST de `free_spot`, `free_futures`, `debt`, y `spot`, `short`, `average`, `collateral` del activo. Las cajas y deuda son de cartera, no deben sumarse entre activos. Aplicar cada fila al estado previo y conservar los otros activos.
- `reporting.py:498-574,802-827`: la serialización conserva el orden de las listas. Leer por ordinal físico original y guardar ese ordinal como procedencia. No ordenar empates por `kind` ni `event_id`.
- `ledger.py:315-366`: funding modifica caja y puede consumir garantía. Los snapshots de posiciones se emiten en transiciones, fills y cierres diarios; no en cada funding. En estas corridas el funding consumió garantía en 0/96/1/89 filas, respectivamente. No basta con arrastrar `positions.parquet`.
- `funding_payments.parquet` es un subconjunto exacto de `ledger.parquet`, ya contabilizado. Los IDs de fills tienen correspondencia exacta con las otras filas del ledger. No sumarlos por segunda vez.
- `amount_usdt` del ledger representa el cambio de valoración del evento según su referencia; no es una columna de movimiento de caja. Para reconstruir se usan estados POST y se auditan los deltas.

Equity se obtiene empezando con `free_spot + free_futures - debt` y agregando, por activo configurado y en este orden, `collateral`, `spot * spot_reference`, `short * (average - risk_mark)`. No restar nuevamente fees ni slippage. Las fees de compra spot ya redujeron inventario (`ledger.py:169-198`); las demás ya afectaron caja o garantía.

El script comprueba álgebra de cada movimiento: cambios conjuntos de caja, garantía y deuda; cantidades spot/short; deltas persistidos de caja y garantía; IDs únicos; monotonicidad temporal; correspondencia funding/fills y cada cierre diario. No aparece deuda no nula en las cuatro corridas. La lógica de deuda sigue siendo necesaria para pruebas y escenarios: las entradas pagan primero deuda, el funding negativo consume caja futures, garantía propia, caja spot y finalmente crea deuda (`ledger.py:94-119,335-350`).

## Secuencia simultánea

`events.py:18-34` agrupa por tiempo financiero; funding usa `funding_time`, no su hora nominal redondeada. Dentro del timestamp, el código congelado aplica:

1. Datos disponibles, en el orden de entrada estable del motor (`strategy.py:891-995`).
2. Funding sobre el corto previo a los fills (`1004-1014`).
3. Fills de intervalos ya comprometidos (`1015-1018`): `_fill_minute_windows` itera `orders.values()` en orden de inserción (`786-838`), no por nombre del tipo de fill.
4. Controles de margen, deuda, corrección, timeout y patas siguientes (`1019-1063`).
5. Renovaciones y nuevas entradas sobre snapshot de equity; símbolos en el orden configurado BTC, ETH (`1064-1094`).
6. Cierre diario si corresponde (`1146-1147`, `1182-1212`), en el nanosegundo original anterior al día siguiente.

El ordinal del ledger resuelve por sí mismo todos los cambios financieros simultáneos. Hay 790/4.837/786/4.591 grupos de ledger con más de una fila; ninguno mezcla funding y fills en estas cuatro corridas. La prueba de simultaneidad funding/fill sigue siendo necesaria para el módulo nuevo porque esa regla es parte del contrato.

No existe un ordinal global común entre ledger, órdenes, posiciones y riesgos. Para estados de caja basta el ordinal financiero. Para combinar controles, reservas y clasificación de posiciones debe conservarse el ordinal propio de cada tabla y las fases del código. Los estados PRE/POST a un mismo timestamp tienen duración cero; el último estado rige el intervalo siguiente.

## Mantenimiento, liquidación y política preventiva

Funciones efectivas: `margin.py:12-83`, `risk.py:21-30`, `data/prescribed.py:29-85`. Las reglas completas también están en `corridas/<run_id>/research_assumptions.json`. Son restricciones prescritas del modelo, constantes sobre la ventana; no una cronología histórica de condiciones del exchange (`data/prescribed.py:105-121`).

Sea `q>0` corto, `m>0` mark, `a` precio medio y `C` garantía. El saldo de margen es `B=C+q*(a-m)`. El nocional `N=q*m` selecciona el primer tramo ordenado por `(floor,cap)` que cumpla `floor<=N<=cap`. `M(N)=N*r-d`, sin redondeo monetario adicional.

| Activo | Tramo nocional BASE USDT | Tasa `r` | Deducción `d` USDT |
| --- | --- | ---: | ---: |
| BTC | [0, 50000] | 0.004 | 0 |
| BTC | [50000, 100000000] | 0.01 | 300 |
| ETH | [0, 50000] | 0.0065 | 0 |
| ETH | [50000, 100000000] | 0.01 | 175 |

En 50000 ambos tramos incluyen el extremo; gana el primero, y el mantenimiento es continuo. MARGEN_2X multiplica por 2 tanto `r` como `d`, por lo que duplica el importe completo. El apalancamiento de apertura continúa en 2. Estas funciones no redondean precios a tick ni cantidades a step; esos redondeos corresponden a órdenes/fills, ya persistidos.

Para cada tramo, el candidato de liquidación es `L=(C+q*a+d)/(q*(1+r))`. Se conservan sólo candidatos no negativos cuyo nocional `q*L` caiga dentro del tramo, y se toma el menor. Si ningún tramo cubre el resultado, se informa no evaluable; no se extiende la tabla. Liquidación se activa con `B<=0`, `B<=M(N)` o `m>=L`. El ratio es `M(N)/B` si `B>0`; un saldo no positivo es inseguro. La distancia es `(L-m)/m`.

La salida preventiva se activa si hay liquidación, `ratio>=0.50` o `distancia<0.15`. Por tanto, **igualdad en ratio falla e igualdad en distancia pasa**.

Tres cantidades distintas:

1. Exigencia e intervalo de holgura: `M(N)` y `B-M(N)`.
2. Déficit hasta la frontera de mantenimiento: `max(0,M(N)-B)`. Alcanzar esa frontera exacta sigue satisfaciendo el predicado de liquidación.
3. Transferencia adicional hipotética `x>=0` para conservar los umbrales preventivos. En estos tramos continuos positivos y parámetros efectivos debe cumplir conjuntamente:

```text
x > M(N)/0.50 - B                       # estricta por ratio
x >= q*m*0.15 + M(q*m*1.15) - B         # no estricta por distancia
```

La segunda condición se obtiene exigiendo `L>=m*(1+0.15)` y calculando mantenimiento en ese precio objetivo, incluyendo cualquier cruce de tramo. No reutilizar necesariamente la tasa del tramo del mark actual. El ínfimo es `max(0, límite_ratio, límite_distancia)`. Si el límite de ratio liga a igualdad, ese importe no basta: en números reales no existe un mínimo alcanzado. Guardar importe y bandera de desigualdad estricta; si se informa una transferencia cuantizada (por ejemplo céntimos), declarar esa nueva convención explícitamente y volver a evaluar los predicados. No añadir un epsilon silencioso ni cambiar tolerancias.

Con corto cero, mantenimiento cero y ratio/distancia ND. El helper original puede producir valores aritméticos para `q=0`, pero el control de riesgo omite ese contrato. No imputar margen a un spot descubierto después de haberse cerrado el futuro.

## Reservas y liquidez redistribuible

`reservations` no está guardado como columna independiente. Sí existen sus importes de asignación y las causas de liberación:

- `signals.parquet` con `decision=accepted`: `budget_required_cash` corresponde al plan viable usado para la entrada. Se verifican 10/20/10/21 entradas aceptadas, sin importes ausentes.
- `renewal_diagnostics.parquet` con `state_after=REBALANCING`, corroborado con evento `renewal_rebalance` y orden enviada: mismo importe. Hay 49/129/36/124 ajustes, todos con plan viable e importe presente.
- `diagnostics.py:152-205` muestra cómo el diagnóstico usa `joint_quantity` con exactamente los precios de sizing, caja, posiciones y garantía del motor. No usar propuestas inviables de otras filas: cuando falta caja el diagnóstico puede mostrar una propuesta teórica sin límite de caja.
- `strategy.py:481-508,546-572` asigna la reserva inicial; `202-207` define caja disponible por activo como ambas cajas menos reservas de los **otros** activos.
- `636-650`: después de un fill spot completo, sin cancelación diferida, descuenta `order.quantity * último spot close disponible` de la reserva y limita a cero. El valor no es el fill VWAP ni el importe ejecutado. Un parcial no ejecuta esta reducción (`778-779`).
- `622-634`: `_complete_pair` borra reserva antes del control final de cobertura/frescura. `288-315`: `_finish_close` la borra sólo cuando el cierre efectivamente termina. `458-461`: `_failed_first_adjustment` también la borra. La cancelación ordinaria, por sí sola, no la libera; un intervalo comprometido puede generar inventario después de pedir cancelación (`256-268`).

Propuesta de interfaz para el módulo nuevo: mantener `reservation[symbol]` por estados con timestamp y fase. Inicializar cero; asignar desde diagnóstico viable y evento correspondiente; reducir con el precio spot causal del fill completo; liberar en las ramas anteriores. Contrastar la caja disponible derivada contra `available_cash` de todos los diagnósticos, respetando la secuencia BTC/ETH. Las cantidades propuestas y órdenes aportan comprobaciones adicionales. En renovaciones o entradas simultáneas, no tomar ambos diagnósticos como si fueran un único estado PRE: ETH ya puede observar reserva de BTC.

Con reservas acreditadas, fondos redistribuibles de cartera = `max(0,free_spot+free_futures-sum(reservations))`, con tratamiento separado de cualquier deuda. Se compara una vez con la suma de necesidades **simultáneas**. Nunca sumar garantías ajenas, spot sin vender, picos de activos ocurridos en momentos distintos ni déficits de minutos consecutivos.

**Límite de la comprobación contable:** `auditar_cuentas.py` verifica importes iniciales, inventario de eventos y existencia de fuentes; su JSON conserva `full_reservation_trajectory_verified=false`. La extensión descrita a continuación reconstruye una trayectoria conservadora y valida diagnósticos, conservando como no determinables los compromisos que no puede resolver. Caja bruta continúa siendo un techo de disponibilidad durante esos compromisos. Este límite no impide reconstruir equity ni necesidades brutas de margen. Tampoco demuestra una carencia indispensable que autorice replay.

## Extensión ejecutada de reservas

El módulo nuevo `scripts/intraday_risk_reservations.py` expone:

```python
reservation_grid(run_path, times_ns, phases=None)
```

`times_ns` es un vector int64 y no necesita estar ordenado. `phases` es un vector opcional con `post` (fin del timestamp, valor predeterminado), `pre` (antes de ese timestamp) o `intermediate` (fase intermedia sin ordinal global acreditado). Devuelve arrays `reserved_cash`, `available_known`, `reason`, `pending_orders_count`, `reserved_cash_lower`, `reserved_cash_upper`, `cash_available_lower`, `cash_available_upper` y un diccionario `validation` con los conteos de diagnósticos comprobados.

Los importes no determinables son NaN, nunca cero. `pending_orders_count=-1` identifica una fase intermedia no determinable. Los límites de caja disponible son finitos y descuentan deuda. Cierres/liquidaciones y correcciones de futuros sin presupuesto explícito conservan obligación no acotada superiormente (`reserved_cash_upper=+inf`, `available_known=false`); ese infinito es una frontera no determinada, no una pérdida observada, y no debe imprimirse como importe histórico. Para comparación y reporte usar los límites finitos de caja disponible.

El módulo lee sólo columnas necesarias y usa Decimal al contrastar diagnósticos. Convierte los vectores de salida a float para su unión con la grilla de precios; los códigos de razón usan referencias a cadenas compartidas para evitar truncación y grandes copias de texto. No importa el motor ni evalúa decisiones de estrategia. Una referencia spot contemporánea inequívoca en `positions` permite reducir exactamente la reserva; en los snapshots ordinarios congelados falta ese campo. Nunca usa una observación posterior para rellenar el pasado.

La comprobación real está en `reservas_verificacion.json`: compara 10.327/10.682/10.308/10.671 diagnósticos `available_cash`, respectivamente, sin contradicciones. En la unión de timestamps de tablas (no una grilla de riesgo por minuto) conserva 43/217/34/215 observaciones POST no determinables: cierres spot faltantes para reducción de reserva o compromisos de futuros sin precio. Los controles preservaron los hashes de entrada. No se puede extrapolar esos conteos a minutos o duración sin unir la grilla correspondiente.

Pruebas ejecutadas: 11 casos propios de reservas; la ejecución integrada con `test_intraday_risk_math.py` y `test_intraday_risk_sources.py` pasó 50 pruebas. Ruff pasó para el módulo y sus pruebas. El registro conserva RED inicial, dos casos detectados de compromisos de futuros y un caso de truncación de razón, seguidos del GREEN real. La prueba de la auditoría contable desde otra carpeta (`%TEMP%`), con rutas absolutas y salida a stdout, pasó los 6.816 cierres sin escribir en fuentes. La suite completa del repositorio queda a cargo de la aceptación integrada del agente principal, que coordina las modificaciones concurrentes.

## Alcance y límites restantes

Los precios minuto, su disponibilidad y el proxy de la suspensión se auditan por separado. Para reconciliar la trayectoria minuto deben incluirse exactamente los cierres diarios originales y sus precios causales; pasar esta auditoría con precios guardados no demuestra que esos precios fueran frescos durante una interrupción. No se alteró ninguna configuración, corrida, manifiesto original ni índice Git. El nuevo resultado acredita las cuentas de estas cuatro corridas; no completa toda la Entrega 4 ni el feedback.

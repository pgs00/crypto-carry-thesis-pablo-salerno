# Quince marks aproximados: resultado continuo y sensibilidad

**Las cuatro carteras completaron el 01/01/2022–31/08/2026 UTC sin reinicios
anuales.** Cada una comenzó con 10.000 USDT y registra 1.704 cierres diarios.
La cobertura se identifica como `completed_with_approximations`; los originales
siguen bloqueados bajo la validación estricta predeterminada.

El método principal, definido antes de ejecutar, es `futures_scaled`:
`mark[t] = futuro_close[t] × mark_close[s] / futuro_close[s]`. Se escala todo
el OHLC con el mismo factor, manteniendo el último ancla oficial anterior
durante cada hueco consecutivo, sin sumar nuevamente el basis. La sensibilidad
`last_official` mantiene todos los OHLC en ese cierre oficial. Ambas opciones
admiten exclusivamente los [15 faltantes documentados](../continuous-preparation-20260919/unresolved_mark_minutes.csv),
usan velas cerradas disponibles al minuto siguiente y conservan el bloqueo
ante otro faltante o un insumo necesario ausente.

## Rentabilidad y decisiones

Los dos métodos produjeron exactamente los mismos saldos finales, fills,
señales, eventos de riesgo y equity diario para cada estrategia.

| Cartera, con ambos métodos | Equity final (USDT) | Retorno neto acumulado | CAGR | Drawdown máximo diario | Solicitudes de cierre por margen, período completo |
|---|---:|---:|---:|---:|---:|
| Condicional | 10.785,76 | 7,8576% | 1,6335% | −0,2062% | 5 |
| Permanente | 11.680,07 | 16,8007% | 3,3825% | −0,4827% | 7 |

No se ejecutaron liquidaciones en ninguna corrida. **Durante los huecos no
hubo eventos de riesgo, solicitudes de cierre ni cambios de posición**, con
ninguno de los métodos. Las solicitudes de margen de la tabla ocurrieron fuera
de los huecos y fueron iguales entre métodos.

El drawdown se mide sobre equity diario, como en las corridas anteriores;
no es un drawdown intraminuto. Las [métricas por año y régimen](period_metrics.csv)
son cortes de las mismas carteras continuas, sin reiniciar su capital.
El [informe generado por el estudio](mark_gap_report.md), la
[tabla de cuatro corridas](comparison.csv) y el
[contraste de decisiones](method_differences.json) conservan los valores fuente.

## Posiciones durante los huecos

Las cantidades siguientes son unidades del activo; el short se expresa como
cantidad positiva. Fueron iguales con ambos métodos.

| Huecos, apertura UTC | Cartera | Activo | Spot | Short | Colateral aislado (USDT) |
|---|---|---|---:|---:|---:|
| ETH: 12/07/2022, todos los minutos documentados | Permanente | BTC | 0,14600377 | 0,146 | 2.068,013650 |
| ETH: 13/07/2022 06:59 | Permanente | BTC | 0,15600376 | 0,156 | 2.164,685650 |
| BTC/ETH: 12/08/2024 10:02 y 10:03 | Condicional | BTC | 0,05300678 | 0,053 | 1.665,391455 |
| BTC/ETH: 12/08/2024 10:02 y 10:03 | Condicional | ETH | 0,0000560 | 0 | 0 |
| BTC/ETH: 12/08/2024 10:02 y 10:03 | Permanente | BTC | 0,05900933 | 0,059 | 1.793,739328 |
| BTC/ETH: 12/08/2024 10:02 y 10:03 | Permanente | ETH | 1,1900866 | 1,190 | 1.914,349088 |

En todos los huecos de julio de 2022 la condicional tenía ambos activos en
cero; la permanente conservaba además **0,0000690 ETH spot residual, sin short
ni colateral ETH**. Los marks de BTC eran oficiales en esos instantes: el
faltante de ETH no implicaba una cartera completamente cerrada.

El [detalle de las 104 posiciones](portfolio_positions_during_gaps.csv) cubre
ambos activos en los 13 timestamps distintos, para las cuatro carteras.
Se reconstruyó desde el ledger persistido y los marks causalmente disponibles.
`runtime_position_match = True` indica contraste adicional con el control
grabado durante el replay del activo afectado; `False` identifica al BTC sin
hueco en julio, reconstruido sin ese registro especial. No indica una discrepancia.
Los [116 controles observados](gap_risk_checks.csv) incluyen por corrida los
15 marks estimados, siete anclas y siete primeras recuperaciones oficiales.

## Margen, liquidación y diferencias entre métodos

Permanecen los umbrales vigentes: cierre preventivo si mantenimiento/balance
es **≥ 50%** o si la distancia al precio de liquidación es **< 15%**.
La distancia es `(precio_liquidación − mark) / mark` para el short.
Estos fueron los extremos durante los marks faltantes con posición short:

| Cartera / activo | Máximo ratio: escalado / constante | Mínima distancia: escalado / constante |
|---|---:|---:|
| Condicional / BTC | 0,648109% / 0,647572% | 61,0737% / 61,1247% |
| Permanente / BTC | 0,709112% / 0,708491% | 55,7854% / 55,8347% |
| Permanente / ETH | 0,757757% / 0,757859% | 84,5797% / 84,5683% |

El BTC oficial de la permanente durante los huecos de ETH en julio tuvo un
ratio máximo de 0,353839% y distancia mínima de 112,1970%, iguales en ambos
métodos. En ninguna observación se activó el predicado de liquidación o cierre
preventivo. Precios de liquidación, balances, mantenimiento y estados están
en los CSV; el [resumen por hueco](gap_positions_summary.csv) conserva los siete grupos.

Sí cambiaron las valoraciones intradía. La máxima diferencia absoluta de
equity entre métodos fue **1,968728 USDT** para la condicional y
**6,685324 USDT** para la permanente, a las **10:04 UTC del 12/08/2024**
(velas abiertas a las 10:03). La máxima diferencia de ratio fue 0,001080 y
0,002382 puntos porcentuales, respectivamente; la de distancia a liquidación,
0,102780 y 0,268685 puntos. No se trasladaron a operaciones ni a equity diario.
El [resumen recalculable](sensitivity_summary.json) registra esos extremos.

## Integridad, verificación y reproducción

Se preservaron los originales, las corridas anteriores y el paquete de la
Entrega 3. Cada capa derivada reemplaza únicamente tres particiones de mark;
las otras 797 entradas siguen referenciando los Parquet originales. Las
auditorías [escalada](marks_futures_scaled.json) y [constante](marks_last_official.json)
contienen activo, timestamps de apertura/disponibilidad, ancla, OHLC estimados,
insumos y hashes. No se alteraron los parámetros económicos.

La [verificación independiente](verification.json) comprobó **1.735 archivos
fuente**, recalculó ambos métodos y los retornos/drawdowns, y contrastó las
104 posiciones. La conciliación contable difiere como máximo en `1E-24 USDT`,
dentro de la tolerancia vigente `1E-8`. Se conserva el funding: por corrida,
en el período económico y sumando ambos activos, 6.214 observaciones usan mark
exacto y 4.010 usan `previous_closed_1m`. Pasaron **455 pruebas y Ruff**.

Esta carpeta contiene sólo evidencia compacta. El estudio y las cuatro corridas
completas permanecen en `D:\Backtesting\outputs`; el
[índice](study_index.json) identifica sus rutas. La
[copia del manifiesto fuente](source_study_manifest.json) conserva referencias
locales, incluida la validación estricta, y no pretende incluir esos datos
masivos aquí. [Proveniencia de las copias](copy_provenance.json) conserva sus
hashes originales; [manifiesto compacto](evidence_manifest.json) y su
[SHA-256](evidence_manifest.sha256) protegen los archivos publicados.
`.gitattributes` preserva sus bytes entre plataformas.

Desde la raíz del repositorio, verificar esta evidencia y recalcular sus
diferencias **sin D: ni nuevas simulaciones**:

```powershell
& '.\.venv\Scripts\python.exe' '.\data\research\continuous-marks-20260919\summarize_sensitivity.py' --verify
```

Verificar también fuentes masivas, fórmulas, parámetros y corridas guardadas:

```powershell
& '.\.venv\Scripts\python.exe' '.\scripts\verify_continuous_marks.py' --root 'D:\Backtesting' --study 'D:\Backtesting\outputs\continuous_marks_b417d512a416058238193c79'
```

La [guía de ejecución](../../../docs/continuous_mark_gaps.md) documenta la
preparación optativa y la repetición de las cuatro carteras.

## Limitaciones

El escalado supone estable la relación mark/futuro dentro del hueco; mantener
el cierre oficial constante ignora los movimientos del futuro. Ninguno recupera
el mark oficial desconocido ni un recorrido intraminuto. La igualdad de
decisiones observada depende de estas posiciones y distancias a los umbrales;
no prueba que ambas aproximaciones sean intercambiables en otra cartera.
Continúan las limitaciones de ejecución por minuto, reglas/comisiones prescritas
y funding aproximado. El método principal se conserva por la hipótesis fijada
antes del ensayo, sin elegirlo por rentabilidad.

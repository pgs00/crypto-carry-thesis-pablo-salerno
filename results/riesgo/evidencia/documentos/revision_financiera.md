# Revisión financiera independiente de la reconstrucción intradía

Fecha: 2026-09-26. Alcance: lectura de `intraday_risk_sources.py`, `build_intraday_risk.py`, `intraday_risk_tables.py`, `intraday_risk_math.py`, sus pruebas y las primeras tablas completas de `paquete_20260926T220400Z`. Se contrastó con el encargo original, `protocolo.md` sellado y el código congelado de `reglas_historicas/20260925T005436Z`. No se modificó código, índice, fuentes preservadas ni particiones. Las reproducciones ejecutadas fueron consultas locales y llamadas unitarias en memoria; no hubo replay ni backtest.

Esta revisión registra la versión observada mientras el implementador aplicaba correcciones. Un hallazgo comunicado no implica que permanezca abierto en una versión posterior: se debe comprobar contra la regeneración final. No se encontró un P1 en la contabilidad reconstruida. Se identificó un P2 observado en el catálogo, dos P2 de validación/integración y un pendiente de alcance del paquete.

## 1. P2 observado: los extremos de exposición incluyen el estado posterior al episodio

Fuente observada: `scripts/intraday_risk_tables.py`, `build_tables`, lectura de `window(lower, upper)`, corte al último POST inicial y agregaciones `maximum_short_quantity`, `minimum_signed_net_exposure_usdt` (líneas 287–310 en la versión revisada).

El catálogo declara `end_exclusive_utc`, pero sus máximos/mínimos usan también los POST financieros del extremo final. Ese estado puede estar cubierto o ser polvo, por lo que deja de describir la exposición activa del episodio. Mantener ese POST para la variación patrimonial final es razonable; mezclarlo en los extremos de exposición no lo es.

Resultados reales, BASE condicional, `run_ad71d751b20623006c195ff3`:

| Episodio | Campo | Tabla observada | Estado activo, incluyendo PRE final |
| --- | --- | ---: | ---: |
| ETHUSDT_002, 2023-01-15 16:02→16:03 UTC | máximo corto | 1.925 | 0 |
| ETHUSDT_002 | mínimo neto USDT | -1.9205211439998493 | 2993.340978856 |
| ETHUSDT_009, 2023-03-24 12:00→14:01 UTC | mínimo neto USDT | 0.015873210000000002 | 2954.19662321 |

En ETH002, el PRE de 16:03 tiene spot 1.9250524 y corto 0; el POST crea el corto 1.925 y termina la exposición descubierta. En ETH009, el PRE de 14:01 tiene spot 1.675009; el POST deja polvo 0.000009. Si se exige estrictamente `time < end`, sin PRE terminal, los mínimos son respectivamente 2993.9954966719997 y 2997.4621056799997. Esta diferencia confirma que hay que documentar la convención de riesgo instantáneo: el protocolo incluye PRE y POST como observaciones de duración cero.

Cambio recomendado: separar el conjunto usado para estados de exposición del conjunto usado para P&L hasta `end_post`. Conservar PRE final y cualquier POST de otro activo que todavía preceda al cierre del activo del episodio; excluir la observación que cambia a cobertura/polvo y las posteriores. No alcanza con quitar siempre una fila final si hay eventos simultáneos.

Prueba recomendada: episodio de apertura con último POST corto positivo, cierre con polvo residual y otro movimiento contable en el mismo timestamp antes de cerrar. Los extremos de exposición deben conservar la valoración PRE terminal y excluir el inventario posterior; el P&L final debe seguir incluyendo la ejecución y su costo.

## 2. P2 de control: `nested_daily_check=True` con patrimonio intradía NaN en el cierre

Fuente: `scripts/intraday_risk_tables.py:24`, `compare_drawdowns`. La comparación `abs(intraday-daily) > tolerance` da False si la diferencia es NaN. Así acepta un cierre diario finito que no aparece como valor evaluable en la serie intradía. La función de drawdown marca correctamente la serie incompleta, pero el control de anidación dice True.

Reproducción ejecutada con `.venv/Scripts/python.exe -B -X utf8`:

```python
import numpy as np
from scripts.intraday_risk_tables import compare_drawdowns
r = compare_drawdowns(np.array([0, 1]), np.array([100., np.nan]),
                      np.array([1]), np.array([101.]), 100., 0)
print({k: r[k] for k in ("daily_complete", "intraday_complete", "nested_daily_check")})
# {'daily_complete': True, 'intraday_complete': False, 'nested_daily_check': True}
```

Cambio recomendado: exigir finitud de ambos valores antes de acreditar igualdad/anidación. Si faltan precios en un cierre, rechazar la comparación o devolver explícitamente un control ND/falso; no acreditar igualdad. Agregar casos NaN e infinito en cada lado y NaN simultáneo.

Impacto observado: el producto completo declara 6816 conciliaciones y máximo residuo 3.637978807091713e-12 USDT; no se observó este caso en los cierres reales. `reconcile_daily` ya tiene el control finito; el hueco está en la segunda interfaz de comparación y sus pruebas de corrupción.

## 3. P2 de integración, sin impacto en estas corridas: la deuda vuelve a contarse como caja libre

Fuente: `scripts/build_intraday_risk.py`, `add_liquidity` (líneas 188–217 en la versión revisada), frente al contrato de `reservation_grid`: `cash_available_lower/upper` deducen la deuda y las reservas. La integración sólo copia reserva/known/count/reason, vuelve a calcular `max(0, free_cash-reserved)` e ignora deuda y límites de caja del módulo. Su límite inferior externo usa también caja bruta.

Reproducción unitaria en memoria, sin leer ni crear una corrida: caja bruta 100, deuda 90, reservas conocidas 0, necesidad 20. Se suministró al límite de integración una respuesta de reservas con caja disponible inferior=superior=10. `add_liquidity` produjo redistribuible 100 y déficit externo 0; respetando el contrato son redistribuible 10 y déficit 10.

```python
from unittest.mock import patch
import numpy as np
from scripts.build_intraday_risk import add_liquidity
reservation = dict(available_known=np.array([True]), reserved_cash=np.array([0.]),
    pending_orders_count=np.array([0]), reason=np.array(["verified_no_reservation"]),
    cash_available_lower=np.array([10.]), cash_available_upper=np.array([10.]))
v = dict(time_ns=np.array([1]), phase=np.array([0]), free_cash_usdt=np.array([100.]),
    debt_usdt=np.array([90.]), maintenance_need_joint_usdt=np.array([20.]),
    preventive_need_joint_infimum_usdt=np.array([20.]))
with patch("scripts.intraday_risk_reservations.reservation_grid", return_value=reservation):
    add_liquidity(v, dict(path="not_accessed"))
assert v["redistributable_cash_usdt"][0] == 100  # resultado defectuoso observado
```

Cambio recomendado: mantener caja bruta como dato distinto; para el estado conocido usar la disponibilidad acreditada por el contrato, o restar deuda de manera explícita y consistente. Para incertidumbre, los límites de disponibilidad permiten límites de déficit; usar disponibilidad cero para el extremo conservador sigue siendo válido. No es un error que el límite superior conservador actual sea menos ajustado.

Prueba recomendada: caso anterior y dos necesidades simultáneas de 60 con caja bruta 100 y deuda 10: faltante teórico 30, no 20. Verificar tanto el valor exacto como los límites. La auditoría de los cuatro ledgers originales encontró deuda=0 en todas sus filas; por eso este defecto no cambia sus cifras actuales.

## 4. P2 de entrega pendiente: faltan las ventanas de extremos prefijadas

`protocolo.md:9` fija ventanas del peor DD desde pico hasta valle/recuperación y, para mínimos de margen, día previo y posterior. La versión revisada de `build_tables` escribe un punto por valle/minimum headroom y exporta `eventos_financieros`, `episodios` y `marzo_2023`; no escribe aquellas ventanas de extremos. Las series locales completas sí existen, de modo que esto es una extracción pendiente y no una carencia de datos ni una necesidad de replay.

Cambio/prueba recomendados: exportar ventanas identificadas por corrida/criterio, con pico, valle y recuperación si existe (o fin de muestra y razón si no); para margen verificar días completos alrededor del extremo con truncamiento documentado en bordes. Comprobar cobertura de los límites y que el punto seleccionado corresponde al mínimo/máximo anunciado. Si el implementador ya lo agrega en una fase posterior, este pendiente queda resuelto con esa comprobación.

## Confirmaciones y límites del examen

- La reconstrucción financiera usa ledger POST, arrastra el resto de los activos y conserva orden físico; no se detectó doble conteo de funding, fees ni slippage. La comprobación Decimal independiente está en `auditoria_contable/resultados.json`.
- Las reglas BASE/MARGEN_2X se leen de las suposiciones preservadas; las tasas y deducciones ya escaladas no reciben otro factor 2. Los umbrales preventivos distinguen ratio estricto y distancia inclusiva. No se encontró un error material de fórmulas en esos estados.
- La política de máximo reiniciado y la de trayectoria acumulada se calculan separadamente. La selección causal de precios usa `available_at <= t`, respeta barras spot inactivas y conserva fuente/edad. El proxy de marzo mantiene un ancla previa fija y no cambia fills ni cantidades.
- El indicador `intraday_complete` acredita valores numéricos finitos bajo una valoración; no demuestra observación del mercado spot durante la interrupción. Las tablas ya etiquetan `original_with_documented_carry_and_estimates`; el informe debe mantener explícita esta diferencia y no presentar máximo histórico de mercado completamente observado sólo porque concilia.
- Reserva ND y déficit superior con caja cero es una cota conservadora válida. No se cuestiona por omitir un intervalo más estrecho, ni se interpreta el extremo superior como aporte real.
- `utc_ns` descarta fracciones de segundo al hacer `int(timestamp()) * SECOND`. Los límites usados actualmente son medianoches y los eventos financieros usan enteros originales, por lo que no se detectó impacto real. Una futura aceptación de argumentos subsegundo debe conservarlos o rechazarlos; no se debe generalizar su exactitud actual a cualquier ISO.

## Semántica verificada para clasificar esperas de ejecución

Congelado `codigo_base/src/crypto_carry/execution.py:12`: `window_start=ceil(submitted_at/minuto)*minuto`; `window_end=window_start+minuto`. `strategy.py:639–643` fija `leg_delay=0` para `next_minute_vwap`; `645–657` agenda la segunda pata, y `1042–1043` la presenta en la fase posterior del mismo timestamp. Una presentación en borde de minuto espera 60 segundos; una presentación fuera del borde puede acercarse a 120 segundos. Por tanto, duración>60 no prueba retraso extraordinario. Debe usarse el `window_end` de la orden relevante, con propósito/mercado que pueda completar el episodio. Una orden bloqueada o presentada tardíamente no permite inferir por sí sola la causa anterior; `attempt_failed` tampoco demuestra un fill parcial. Los fills tienen indicador `partial` para esa evidencia.

## Repetición de los valores del hallazgo 1

Desde el checkout, ejecutar el bloque siguiente con `.venv/Scripts/python.exe -B -X utf8`; sólo lee el CSV y dos particiones locales del manifiesto:

```python
from pathlib import Path
import csv, json
import numpy as np
import pyarrow.parquet as pq
p = Path("entregas/entrega_4/riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z")
root = Path(json.loads((p / "series_locales.json").read_text(encoding="utf-8"))["root_recorded"])
rows = list(csv.DictReader((p / "tablas/catalogo_incidentes.csv").open(encoding="utf-8-sig")))
for r in rows:
    if r["episode_id"] not in ("run_ad71d751b20623006c195ff3_ETHUSDT_002",
                               "run_ad71d751b20623006c195ff3_ETHUSDT_009"):
        continue
    tab = pq.read_table(root / r["run_id"] / (r["start_utc"][:7] + ".parquet"))
    cols = {k: tab[k].to_numpy() for k in ("time_ns", "phase", "ETHUSDT_short",
                                         "ETHUSDT_net_exposure_usdt")}
    lo, hi = int(r["start_ns"]), int(r["end_ns"])
    first = np.searchsorted(cols["time_ns"], lo, side="right") - 1
    active = ((np.arange(len(tab)) >= first) & (cols["time_ns"] < hi))
    active |= (cols["time_ns"] == hi) & (cols["phase"] == 1)
    print(r["episode_id"], np.max(cols["ETHUSDT_short"][active]),
          np.min(cols["ETHUSDT_net_exposure_usdt"][active]))
```

Para estos dos casos el final sólo tiene PRE y un POST financiero; el código de producción general debe manejar otros eventos simultáneos, como se explicó arriba.

Hashes SHA-256 de las versiones leídas en este corte (pueden cambiar con las correcciones del implementador):

| Archivo | SHA-256 |
| --- | --- |
| intraday_risk_sources.py | 459e90c0a754610463cbce13abd4d91dda2054f27a2e19ac17e052dee2b38665 |
| build_intraday_risk.py | 5fb82e91343ad4cd0f11fdf7be67c9cf589ae2cc0d785f5a875508e793a1b3dc |
| intraday_risk_tables.py | 2af0666d064c90144b85b1f3c3d2da844e334b0a5a09ccbc1ff366700c438b21 |
| intraday_risk_math.py | 98f26a8c331e5225e588fcf66e3e17470de702916b40926276282ca2eed0463b |

El archivo documenta evidencia de revisión y recomendaciones; no certifica una regeneración posterior ni reemplaza la verificación final del paquete.

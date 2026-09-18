# Revisión independiente de core y datos

Revisión de solo lectura del árbol actual, sin commits existentes. Alcance: `src/crypto_carry` excepto reporting/CLI/fixtures/robustness en construcción, con foco en contabilidad, tiempo, datos, Nautilus y reanudación. Referencia: `docs/sources/Prompt_Codex_Backtesting.md`. No se modificaron fuentes ni pruebas. Se excluyen los problemas ya conocidos por el coordinador: huecos interiores de reglas, cobertura del rango solicitado y rutas fijas de replay.

## Resultado

**Verificación final: todos los hallazgos de esta revisión quedaron corregidos.** Se verificaron los seis hallazgos originales y los dos casos adicionales de la segunda ronda. La última ejecución del conjunto core/data produjo **68 passed, 60 warnings in 5.95s**. No quedan pendientes de los hallazgos enumerados; esto no certifica una corrida histórica ni los módulos fuera del alcance. Se conserva abajo la evidencia de ambas rondas como historial.

Fortalezas verificadas:

- La integración Nautilus es efectiva: usa el motor de replay, órdenes nativas, `OrderMatchingEngine.fill_order`, callbacks de fill y conciliación de posiciones. No es una importación decorativa.
- El ledger usa Decimal, aplica una sola vía económica y concilia los casos de comisiones, funding, liquidación y deuda del conjunto revisado.
- Funding anterior a fills, deadline estricto, segundo entre patas, ausencia de cierre terminal y reanudación con hedge pendiente tienen pruebas de integración que pasan.

Comando ejecutado:

```powershell
.venv\Scripts\python.exe -m pytest -q tests/unit/test_config.py tests/unit/test_data.py tests/unit/test_execution.py tests/unit/test_finance.py tests/unit/test_finance_integration.py tests/integration/test_native_adapter.py tests/integration/test_checkpoint.py tests/integration/test_strategy.py
```

Resultado observado: **59 passed, 50 warnings in 2.08s**. Las advertencias son de pandas/Nautilus. El intento inicial de suite completa se interrumpió al importar CLI/fixtures todavía en construcción; eso no se considera hallazgo de esta revisión.

## Verificación final de las dos últimas correcciones

Se leyó la implementación final y se repitió el comando core/data completo indicado arriba:

```text
68 passed, 60 warnings in 5.95s
```

- `test_suspended_spot_inventory_is_not_mistaken_for_dust` pasa. `_spot_is_dust` comprueba mínimos genuinos de cantidad/nocional; `_finish_close` conserva `CLOSING_SPOT` cuando sigue existiendo inventario negociable bloqueado. La venta se ejecuta tras rehabilitarse el mercado y el cooldown comienza después del desarme.
- `test_failed_first_rebalance_leg_preserves_existing_pair` pasa. Una `increase_spot` obsoleta se cancela sin fill; `_failed_first_adjustment` libera reservas, conserva `HOLDING`, registra la falla y bloquea nuevas ampliaciones durante el cooldown. El caso mantiene únicamente los cuatro fills de apertura originales.
- Continúan pasando las pruebas de deuda, liquidación, reintentos, funding, no look-ahead, particiones y checkpoint de la primera revisión.

No se realizó otra búsqueda general después de esta verificación, conforme al pedido del coordinador de estabilizar el core. Solo se actualizó este informe.

## Segunda ronda: evidencia histórica de fixes y pendientes ya resueltos

Se repitió el mismo comando core/data, incluyendo los nuevos tests agregados por el coordinador. Resultado observado: **66 passed, 56 warnings in 5.58s**. La revisión siguió siendo de solo lectura de fuentes y pruebas.

Confirmaciones:

- La apertura obsoleta ahora se cancela antes del fill, con causa `stale_data_at_fill`; el test nuevo pasa.
- La suspensión temporal de Futures mantiene la intención y reenvía el cierre al rehabilitarse; el test nuevo pasa.
- `_debt_close` selecciona un activo por vez y preserva ETH si BTC ya pagó la deuda; el test nuevo pasa.
- La paginación ahora conserva un mapa de timestamps y rechaza duplicados conflictivos, incluidos los vistos en páginas anteriores.
- El calendario conserva intervalo y tasa; `funding_records` compara ambas fuentes. Pasan los tests de omisión de 8 horas y cambio legítimo de 8 a 4 horas. El flujo real de `normalize()` conecta ambos diccionarios con esos controles y revalida además los hashes raw.
- `_code_hash` ahora usa `rglob("*.py")` con rutas relativas estables e incluye el subpaquete de datos. Confirmado por lectura directa.
- Los tests de días solicitados y huecos interiores de reglas pasan; la lectura muestra revisión de los límites efectivos y `known_from`. Las rutas de replay e input hashes ahora reciben la configuración.

No se revisaron aquí los faltantes de marks anteriores al inicio, cola de calendario ni límite de escrituras temporales, que el coordinador indicó estar corrigiendo.

### Caso A, corregido: suspensión de spot termina el cierre con todo el spot expuesto

Ubicación de la segunda ronda: `strategy.py:149-155`, `strategy.py:355-358`, `strategy.py:543-552`. Severidad: importante; continuación del hallazgo original 2.

`_tradable_spot` devuelve cero tanto para polvo real como para un mercado suspendido, por `valid_quantity(...).operational`. `_next_leg` y el nuevo reintento interpretan ese cero como desarme finalizado y llaman a `_finish_close`. En cambio, el inventario de magnitud negociable debe conservar intención de cierre hasta volver la operatividad; el cooldown todavía no debe empezar.

Reproducción ejecutada con Nautilus real: BTC **spot** suspendido t120 inclusive a t180 exclusive, precios en `[0,60,61,62,63,120,121,122,123,180,181,182,183,240]`, fin t250.

```text
BTC fills: open_spot t61, open_perp t63, close_perp t121
t122: unwind_complete -> COOLDOWN
BTC final: COOLDOWN, spot=29.97000, short=0.000, pending=[]
```

Luego de rehabilitarse t180 hay suficientes trades y nunca aparece `close_spot`. El nuevo test cubre suspensión de Futures, pero no esta segunda pata. También conviene distinguir exceder máximos de estar debajo de mínimos: ninguno de los dos primeros casos es polvo.

### Caso B, corregido: un rebalanceo obsoleto antes del primer fill cierra innecesariamente todo el par

Ubicación de la segunda ronda: `strategy.py:403-405`. Severidad: importante; regresión del fix de frescura. Requisito: consigna, líneas 338-340.

La condición nueva llama a `_close` para todos los propósitos de apertura/aumento. Cuando `increase_spot` aún no llenó, no cambió ninguna exposición: la consigna exige cancelar el ajuste, registrar el fallo y preservar el par real, como ya hacen los otros caminos de timeout/rechazo de primera pata. El cierre total corresponde a un ajuste cuya segunda pata falló después de ejecutar la primera.

Reproducción ejecutada con `holding_hours=1`: entrada normal; precios 100/100.3 hasta t3600; ambos mercados 90/90.3 en t3603; solo spot 90 en t3663/t3664; ambos mercados 90/90.3 en t3665/t3666/t3667/t3668. En t3663 la renovación y el aumento son válidos; al intento de fill t3664 el último futuro tiene 61 segundos.

```text
t3663: renewal -> REBALANCING
t3664: stale_data_at_fill -> CLOSING_PERP
t3665: close_perp fill
t3667: close_spot fill -> COOLDOWN
```

No hubo fill `increase_spot`, por lo que el resultado esperado es cancelar esa orden, liberar su reserva, registrar el intento fallido y volver a `HOLDING`, sin nuevos fills ni comisiones. Conservar la fecha de renovación ya decidida y el estado económico del par.

## Primera ronda: hallazgos y reproducciones originales

### 1. Una apertura pendiente aumenta exposición con la otra pata obsoleta

Ubicación revisada: `strategy.py:391-420` (`_execute`), `strategy.py:192-226` (`_risk`). Requisito: consigna, línea 310.

Al enviar una compra se exige frescura, pero al llenar una orden pendiente solamente se revalidan filtros, fondos y reservas. `_risk` tampoco cancela aumentos por frescura. Una orden aceptada exactamente cuando el último trade de la otra pata tiene 60 segundos puede llenar un segundo después con ese precio ya obsoleto.

Reproducción ejecutada con `conftest.FixedRules`, `warmup`, `prices` y Nautilus real:

```python
rows = warmup(s) + prices(s, [0], mark="100.3")
rows += [r for r in prices(s, [60, 61, 62], mark="100.3")
         if not isinstance(r, Trade) or r.market == "spot"]
rows += prices(s, [63], mark="100.3")
b = Backtest(Config(start=iso(s), end=iso(s+100*SECOND)), FixedRules())
b.run(sorted(rows, key=event_key))
```

Resultado: para BTC y ETH, envío `open_spot` en t60, fill spot en t61 y fill futuro en t63. En t61 el último trade futuro es t0, edad **61 segundos**, superior al máximo de 60. También se envía `open_perp` en t62 sin frescura, aunque esa cobertura debe distinguirse del aumento inicial para preservar la exposición ya existente.

Impacto: la regla de bloqueo de entradas/aumentos no rige durante el intervalo envío-fill y produce posiciones que el contrato prohíbe.

Corrección sugerida: revalidar antes de un fill que aumenta exposición y cancelar/desarmar de acuerdo con si ya hubo una pata; conservar siempre las salidas y distinguir la cobertura de riesgo del aumento spot.

### 2. Una salida que no pudo enviarse queda permanentemente sin reintento

Ubicación revisada: `strategy.py:174-185`, `strategy.py:119-126`. Requisitos: consigna, líneas 265-267 y 308.

`_close` cambia a `CLOSING_PERP` antes de saber si `_submit` fue aceptado. Si un mercado está suspendido, `valid_quantity` devuelve falso y no queda una orden pendiente ni un timer de reintento. Los siguientes llamados a `_close` retornan inmediatamente por el estado de cierre, aunque no exista orden. Cuando vuelve la operatividad, la posición continúa indefinidamente.

Reproducción ejecutada: regla BTC futures con `operational=False` desde t120 inclusive hasta t180 exclusive; apertura normal con precios en `[0,60,61,62,63]`; nuevos precios en `[120,180,181,182,183,240]`; fin t250.

Resultado exacto:

```text
BTC final: CLOSING_PERP spot=29.97000 short=29.970 pending=[]
BTC events after suspension:
  (120, close_requested, market_suspended)
  (120, transition, market_suspended)
  (120, order_blocked, historical_quantity_filter)
BTC fills: (open_spot,61), (open_perp,63)
```

Impacto: no se realiza la salida de riesgo ni siquiera tras volver trades y reglas ejecutables. También afecta otros rechazos de envío de una salida, no solo suspensión.

Corrección sugerida: conservar explícitamente la intención de salida cuando no se puede enviar; reintentar al recuperarse operatividad/filtros y no retornar únicamente por el estado cuando no hay orden pendiente ni espera entre patas. No confundir inventario no vendible por suspensión/máximo con polvo bajo mínimo.

### 3. El waterfall por deuda cierra ETH aunque el cierre BTC ya la canceló

Ubicación revisada: `strategy.py:438-440` y el bucle equivalente de deuda en `process` (líneas 525-527 del árbol leído). Requisito: consigna, línea 373.

Al aparecer deuda, se solicitan cierres de ambos activos de inmediato. No se comprueba la deuda entre realizaciones antes de seleccionar el siguiente activo, y una orden ETH por deuda permanece aun cuando BTC ya la canceló.

Reproducción ejecutada: apertura normal de ambos activos; funding BTC con tasa `-1` en t90 (escenario sintético de estrés); futuros BTC en t91; spot BTC en t93; futuros ETH en t94; spot ETH en t96.

```text
t90 BTC funding:      debt=512.891591600, free_spot=0
t91 BTC liquidate:    debt=545.659590800
t93 BTC close_spot:   debt=0, free_spot=2448.044008900
t94 ETH close_perp:   debt=0, se ejecuta de todos modos
t96 ETH close_spot:   debt=0, se ejecuta de todos modos
```

Impacto: se liquida exposición y se pagan costos ETH que no eran necesarios para satisfacer la obligación. Cambia la trayectoria económica frente a la secuencia BTC→ETH indicada.

Corrección sugerida: seleccionar un desarme por deuda por vez en orden BTC/ETH y volver a comprobar la obligación después de cada realización; mantener separadas otras causas de riesgo que sí justifiquen cierres simultáneos.

### 4. La paginación elimina duplicados conflictivos antes de la validación

Ubicación revisada: `data/download.py:65-71`. Requisito: consigna, línea 177.

`fetch_funding_pages` conserva solo timestamps estrictamente mayores al último agregado. Dos registros con igual `fundingTime` pero tasas/marks diferentes se convierten en un único registro sin excepción ni registro de conflicto. El validador de duplicados de normalización ya no puede recuperar la evidencia descartada.

Reproducción ejecutada con cliente offline, una página de dos filas:

```text
input:  fundingTime=1000, fundingRate=0.0001, markPrice=100
        fundingTime=1000, fundingRate=-0.25,  markPrice=100
output: [fundingTime=1000, fundingRate=0.0001, markPrice=100]
```

Impacto: una contradicción de fuente se transforma silenciosamente en funding aparentemente único; afecta señales, flujos económicos y trazabilidad.

Corrección sugerida: deduplicar por clave comparando todos los campos económicos; solamente eliminar idénticos con contador y rechazar/preservar un conflicto. Aplicar también a duplicados entre páginas.

### 5. Se descarta el intervalo de funding publicado y se puede certificar un hueco como cambio de frecuencia

Ubicación revisada: `data/normalize.py:64-71` y `data/normalize.py:215-232`. Requisito: consigna, línea 179.

El parser del calendario conserva únicamente timestamps, descartando `funding_interval_hours`. `funding_records` calcula la diferencia de timestamps y la marca verificada si no hay otro timestamp dentro del conjunto; no contrasta la duración publicada, incluso si viene en `fundingIntervalHours` de la fila.

Reproducción ejecutada:

```python
rows = [
    dict(fundingTime=0, fundingRate="0.0001", markPrice="100", fundingIntervalHours=8),
    dict(fundingTime=16*3600*1000, fundingRate="0.0001", markPrice="100", fundingIntervalHours=8),
]
records = funding_records(rows, symbol="BTCUSDT", source_file="x",
                          expected_times_ms={0,16*3600*1000})
```

Resultado segundo registro: `interval_hours=Decimal('16')`, `interval_verified=True`, aunque la fuente declara **8 horas**. Si las dos fuentes tienen la misma omisión, el conjunto de timestamps por sí solo no acredita un cambio legítimo.

Impacto: se puede habilitar una ventana de funding inválida y subestimar su tasa horaria. Este problema es distinto de verificar que los archivos cubran el rango solicitado.

Corrección sugerida: conservar y contrastar la duración/calendario aplicable de la fuente oficial; una discrepancia debe permanecer incompleta hasta resolución, nunca convertirse automáticamente en un intervalo legítimo de 16 horas.

### 6. El hash de código del checkpoint excluye todo el paquete de datos

Ubicación revisada: `strategy.py:689-694` (`_code_hash`). Requisito: reproducibilidad, consigna líneas 503-507; identidad de replay/reanudación, línea 574.

La enumeración usa `Path(__file__).parent.glob("*.py")`. Incluye módulos directos pero omite `data/replay.py`, `data/normalize.py`, `data/validate.py`, `data/rules.py` y `data/download.py`. La inspección directa confirma que esos archivos nunca contribuyen al digest.

Impacto: cambiar la interpretación u orden de inputs dentro de `data/` no invalida un checkpoint, aunque un replay continuo con ese código nuevo puede diferir del prefijo guardado. `inputs` controla bytes de datos, no la implementación que los interpreta.

Corrección sugerida: recorrer recursivamente los módulos del paquete, con ruta relativa estable en el hash. Añadir una prueba que varíe un archivo de `data/` en un árbol temporal y verifique que el hash cambie, sin modificar fuentes reales.

## Límites de la revisión

No se atribuye a la implementación la falta de reglas históricas disponibles: `incomplete_data` estricto es deliberado y correcto. No se revisaron resultados históricos ni módulos todavía en construcción. Los números anteriores son reproducciones sintéticas de errores de software, no resultados académicos.

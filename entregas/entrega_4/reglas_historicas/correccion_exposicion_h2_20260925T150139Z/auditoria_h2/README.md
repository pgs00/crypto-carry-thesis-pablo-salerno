# Auditoría H2: corrección de posprocesamiento

Las fuentes financieras se leyeron desde el paquete padre `20260925T005436Z` sin modificarlas. Los casos sintéticos no son backtests.

## RED y GREEN

1. Se creó primero `tests/unit/test_rules_sensitivity_h2.py` importando el constructor original `scripts.report_historical_rules_sensitivity.h2_comparison`. La prueba exigió `no_favorable` para CAGR condicional `-0.01`, Sharpe condicional `-0.5` y Sharpe permanente `-1`.
2. Se ejecutó desde la raíz del proyecto:

   ```powershell
   & .venv/Scripts/python.exe -m pytest tests/unit/test_rules_sensitivity_h2.py -q
   ```

   Resultado registrado en `red_original.log`: **1 failed**, porque el constructor original devolvió `favorable`. No se ejecutó ninguna simulación.
3. Se ampliaron las expectativas explícitas y se implementó el módulo puro `scripts/rules_sensitivity_h2.py`; la prueba de regresión pasó a importar ese módulo. Se ejecutó el mismo comando: `green_initial.log`, **51 passed**.
4. Se hicieron literales también las diferencias de Sharpe esperadas y se formatearon los dos archivos:

   ```powershell
   & .venv/Scripts/python.exe -m ruff format scripts/rules_sensitivity_h2.py tests/unit/test_rules_sensitivity_h2.py
   & .venv/Scripts/python.exe -m pytest tests/unit/test_rules_sensitivity_h2.py -q
   & .venv/Scripts/python.exe -m ruff check scripts/rules_sensitivity_h2.py tests/unit/test_rules_sensitivity_h2.py
   ```

   `green_final.log`: **51 passed**; `ruff.log`: **All checks passed!**

## Contrato

`h2_comparison(rows) -> list[dict]` recibe filas nativas o de `csv.DictReader`, con claves `scenario`, `period`, `strategy`, `run_id`, `start_utc`, `end_exclusive_utc`, `coverage_complete`, `cagr` y `sharpe`. Las razones originales de métricas indefinidas se conservan cuando existen. Se rechazan claves fuente duplicadas y estrategias desconocidas.

La salida tiene `scenario`, `period`, `start_utc`, `end_exclusive_utc`, límites separados `conditional_start_utc`, `conditional_end_exclusive_utc`, `permanent_start_utc`, `permanent_end_exclusive_utc`, `conditional_run_id`, `permanent_run_id`, `conditional_cagr`, `conditional_sharpe`, `permanent_sharpe`, `sharpe_difference`, `cagr_positive`, `sharpe_superior`, `verdict`, `reason`.

Los números son `Decimal` o `None`; los indicadores son `bool` o `None`. Los límites comunes son `None` si falta una cartera o las ventanas no son comparables. Los límites originales separados permiten auditar el motivo. La evaluación no redondea ni requiere Sharpe positivo ni compara los CAGR de ambas carteras.

- `favorable`: cobertura completa, ventanas comparables, tres métricas finitas, CAGR condicional > 0 y Sharpe condicional > Sharpe permanente.
- `no_favorable`: caso comparable y evaluable sin cumplir ambas desigualdades. Esto no equivale automáticamente a evidencia contraria.
- `no_concluyente`: cartera faltante, ventana no comparable, cobertura incompleta o alguna métrica requerida indefinida/no finita. Se conservan los componentes evaluables.

`validate_h2_rows(actual, metrics) -> None` acepta filas nativas o serializadas a CSV y lanza `ValueError` ante incumplimientos. No llama al constructor: verifica claves, cantidades de filas, identidades, límites, valores, diferencia, condiciones, veredicto y motivo. Las dos evaluaciones de la condición económica son independientes.

La prueba `test_literal_contract_catches_joint_constructor_and_verifier_mutation` modifica ambas comparaciones de CAGR en una copia AST sólo en memoria. El constructor y verificador mutados coinciden al favorecer el ejemplo negativo, pero la expectativa literal `no_favorable` detecta la contradicción. La copia mutada nunca se escribe sobre los scripts reales.

## Lectura real del padre

La evaluación directa de las 96 filas de `comparacion/metricas_cartera_periodo.csv` produce 48 filas H2 en 6 escenarios: 43 `no_favorable` y 5 `no_concluyente`. Comparadas por escenario/período con el `h2.csv` padre, no cambió ningún veredicto real. Sí cambian el contrato explícito, los componentes y la trazabilidad de H2.

Esta auditoría focalizada no reemplaza la suite de integración ni los verificadores de paquetes que debe ejecutar la entrega completa.

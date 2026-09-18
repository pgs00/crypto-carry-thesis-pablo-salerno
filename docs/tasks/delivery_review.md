# Revisión independiente de entrega

Fecha: 2026-09-17. Revisión de solo lectura de `cli.py`, `robustness.py`,
`reporting.py`, `evaluation.py`, `fixtures.py`, sus pruebas y las secciones 10–15
de `docs/sources/Prompt_Codex_Backtesting.md`. Las referencias de línea
corresponden al estado inspeccionado antes de las correcciones del coordinador.
No se editaron fuentes, pruebas, datos ni resultados existentes.

## Fortalezas verificadas

- Las corridas individuales identifican configuración, código, inputs y filtro;
  antes de reutilizarlas verifican los artefactos y el digest de resultados.
- El reporte y los gráficos consumen tablas persistidas. Parquet conserva los
  importes como cadenas decimales; la atribución comprueba conciliación y no
  vuelve a descontar slippage.
- Una corrida histórica bloqueada conserva esquemas vacíos y motivos, sin
  fabricar equity ni métricas. Los datos sintéticos se identifican expresamente.
- H1 usa observaciones comunes, MAE por activo y promedio de igual peso; H2
  requiere dos calendarios y métricas comparables; H3 incluye minutos cero y
  excluye días incompletos. Los escenarios modifican un factor por vez, salvo
  el cambio conjunto de horizonte y permanencia exigido por la consigna.

## Hallazgos iniciales importantes (P2, cerrados)

Los tres puntos siguientes describen el estado previo. Se conservan como
traza de revisión; sus correcciones y verificación figuran al final.

1. **La CLI rechaza derivados ausentes antes de poder restaurarlos.**
   `src/crypto_carry/cli.py:94-97` exige una verificación completa antes de llamar
   a `regenerate_report`, pero `reporting.py:1605-1642` admite deliberadamente
   restaurar `report.md` y figuras ausentes si sus hashes reconstruidos coinciden.
   Por ello, `report --run-id <corrida>` falla cuando falta solamente un derivado
   recuperable. La validación de fuentes y derivados modificados debe permanecer
   en el regenerador; verificar nuevamente al terminar. Comprobación por lectura
   del flujo; el coordinador confirmó el defecto.

2. **El índice de robustez no cumple el contrato del comando report.**
   `src/crypto_carry/robustness.py:177-233` crea un `run_manifest.json` agregado sin
   sidecar ni `artifacts_complete`, y con artefactos distintos de los exigidos
   universalmente por `reporting.py:1443-1485`. Así, el identificador
   `robustness-*` emitido por la CLI no puede verificarse ni regenerarse mediante
   `report --run-id`. Además, su reutilización comprueba hashes de los archivos
   declarados, pero no la integridad del propio manifiesto. Requiere un contrato
   explícito de índice, sus artefactos mínimos, sidecar y verificación de corridas
   enlazadas; su reporte y gráfico pueden regenerarse desde el CSV guardado.
   Comprobación por lectura del flujo; el coordinador confirmó el defecto.

3. **Escenarios no solicitados pueden invalidar un rango corto válido.**
   `src/crypto_carry/robustness.py:42-50,64-69` construye todas las configuraciones
   antes de aplicar `selected`. Con un baseline del 01/01/2022 al 03/01/2022,
   intentar construir el inicio alternativo de 2023 provoca `ValueError: Invalid
   history/evaluation range`; también impide pedir exclusivamente `cost-2`.
   Esto bloquea una sensibilidad acotada que sería válida y no necesita ampliar
   la muestra. Aplicar la selección antes de construir configuraciones, y tratar
   explícitamente los inicios alternativos fuera del rango.

   Reproducción ejecutada en el entorno instalado, sin red:

   ```python
   from crypto_carry.config import Config
   from crypto_carry.robustness import scenario_configs

   scenario_configs(Config(
       start="2022-01-01T00:00:00Z",
       end="2022-01-03T00:00:00Z",
   ))
   # ValueError: Invalid history/evaluation range
   ```

## Verificación ejecutada

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_reporting.py tests/unit/test_evaluation.py tests/unit/test_cli.py tests/integration/test_demo.py -q -p no:cacheprovider
```

Resultado: **18 passed in 17.05s**. Son pruebas focalizadas; el coordinador
ejecuta la suite completa y la demo final. No se descargó historia ni se pidió
superar el presupuesto inicial de datos. Las reglas históricas pendientes y
los huecos conocidos de identificadores Futures siguen siendo bloqueos de
evidencia, no defectos de esta revisión.

## Confirmación de correcciones

Se revisaron únicamente las tres correcciones solicitadas, sin ampliar el
alcance ni editar fuentes:

1. **Cerrado.** `cli.py` llama primero a `regenerate_report` y luego a
   `verify_run`. La prueba `test_cli_report_restores_a_missing_derived_file`
   elimina el reporte de una corrida temporal y confirma que la CLI lo restaura
   con exactamente los bytes originales.
2. **Cerrado.** El agregado declara `kind="robustness_index"`, sidecar SHA-256
   y `artifacts_complete`. `verify_robustness` comprueba el manifiesto, los
   artefactos propios y las corridas enlazadas. `regenerate_robustness` reconstruye
   desde el CSV guardado, exige los hashes originales y solo crea derivados
   ausentes. La CLI dirige estos índices a ese contrato. La prueba
   `test_robustness_index_has_a_working_report_command_and_checks_subruns`
   confirma el comando válido y el rechazo después de alterar `metrics.csv` de
   una corrida enlazada.
3. **Cerrado.** `scenario_configs` omite inicios alternativos iguales o
   posteriores al fin del baseline. El índice explica esa omisión y seleccionar
   expresamente un inicio excluido devuelve un motivo de rango. La prueba
   `test_short_range_does_not_fail_because_of_unrequested_future_start_scenarios`
   confirma que el intervalo corto de la reproducción conserva `cost-2` y ya no
   falla por los inicios de 2023/2024.

Verificación independiente posterior a las correcciones:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_cli.py -q -p no:cacheprovider
```

Resultado: **7 passed in 5.10s**, sin warnings. Esta comprobación incluye las
tres regresiones anteriores y la conservación del baseline de robustez.

## Evaluación

**Apto en el alcance revisado. Los tres hallazgos están cerrados y verificados.**
No se identificaron otros bugs concretos de H1/H2/H3 en la revisión original.
Esta confirmación se limita a los tres fixes; no constituye una nueva revisión
general ni certifica cobertura histórica pendiente.

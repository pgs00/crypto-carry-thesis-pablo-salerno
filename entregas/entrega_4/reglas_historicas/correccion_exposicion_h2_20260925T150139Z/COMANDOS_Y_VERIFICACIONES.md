# Comandos y verificaciones ejecutados

Directorio de trabajo del proyecto salvo indicaci?n expl?cita. Cada registro JSON conserva comando, cwd, fecha, duraci?n y c?digo real. Los logs no se reescribieron para ocultar fallos.

Los nombres `red_*` registran fallos esperados antes de implementar. `e3_publicacion` es el control hist?rico de limpieza fuera de alcance; los detalles est?n en control_historico_alcance.json. Los intentos iniciales de TEMP y Pillow tienen una ejecuci?n posterior corregida. El conteo final v?lido de la suite es 751; no se suman ejecuciones repetidas.

## e3_publicacion

Inicio: 2026-09-25T15:09:32.703905+00:00. Salida: **1**. Duraci?n: 2.137 s.

[Registro JSON](controles/e3_publicacion.json) ? [Log UTF-8](controles/e3_publicacion.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-X' 'utf8' '-m' 'scripts.verify_repository_evidence'
```

## padre_original

Inicio: 2026-09-25T15:09:32.707152+00:00. Salida: **0**. Duraci?n: 19.985 s.

[Registro JSON](controles/padre_original.json) ? [Log UTF-8](controles/padre_original.log)

```powershell
& '.venv/Scripts/python.exe' '-I' '-S' '-B' 'entregas/entrega_4/reglas_historicas/20260925T005436Z/herramientas/verify_rules_sensitivity_package.py' '--package' 'entregas/entrega_4/reglas_historicas/20260925T005436Z'
```

## fuentes_historicas_original

Inicio: 2026-09-25T15:09:32.716762+00:00. Salida: **1**. Duraci?n: 0.135 s.

[Registro JSON](controles/fuentes_historicas_original.json) ? [Log UTF-8](controles/fuentes_historicas_original.log)

```powershell
& '.venv/Scripts/python.exe' '-I' '-S' '-B' 'entregas/entrega_4/reglas_historicas/20260925T005436Z/herramientas/verify_historical_rules_publication.py' '--root' 'entregas/entrega_4/reglas_historicas/20260925T005436Z/evidencia_historica' '--evidence' 'entregas/entrega_4/reglas_historicas/20260925T005436Z/evidencia_historica/data/research/historical-rules-followup-20260924T234206Z' '--temp-dir' '$env:TEMP'
```

## fuentes_historicas_ruta_correcta

Inicio: 2026-09-25T15:10:01.161545+00:00. Salida: **0**. Duraci?n: 2.312 s.

[Registro JSON](controles/fuentes_historicas_ruta_correcta.json) ? [Log UTF-8](controles/fuentes_historicas_ruta_correcta.log)

```powershell
& '.venv/Scripts/python.exe' '-I' '-S' '-B' 'entregas/entrega_4/reglas_historicas/20260925T005436Z/herramientas/verify_historical_rules_publication.py' '--root' 'entregas/entrega_4/reglas_historicas/20260925T005436Z/evidencia_historica' '--evidence' 'entregas/entrega_4/reglas_historicas/20260925T005436Z/evidencia_historica/data/research/historical-rules-followup-20260924T234206Z' '--temp-dir' 'C:\Users\pablo\AppData\Local\Temp'
```

## e3_paquete_original

Inicio: 2026-09-25T15:10:01.166143+00:00. Salida: **0**. Duraci?n: 0.822 s.

[Registro JSON](controles/e3_paquete_original.json) ? [Log UTF-8](controles/e3_paquete_original.log)

```powershell
& '.venv/Scripts/python.exe' '-I' '-S' '-B' 'Paquete de evidencia/verificar.py'
```

## e3_publicacion_alcance_correcto

Inicio: 2026-09-25T15:10:24.224062+00:00. Salida: **0**. Duraci?n: 0.954 s.

[Registro JSON](controles/e3_publicacion_alcance_correcto.json) ? [Log UTF-8](controles/e3_publicacion_alcance_correcto.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-X' 'utf8' '-m' 'scripts.publish_thesis' '--verify'
```

## e3_archivo_original

Inicio: 2026-09-25T15:10:24.236930+00:00. Salida: **1**. Duraci?n: 0.113 s.

[Registro JSON](controles/e3_archivo_original.json) ? [Log UTF-8](controles/e3_archivo_original.log)

```powershell
& '.venv/Scripts/python.exe' '-I' '-S' '-B' '-X' 'utf8' 'entregas/entrega_3/archivo/paquete_redaccion/scripts/verificar_paquete.py'
```

## red_constructor

Inicio: 2026-09-25T15:11:22.550753+00:00. Salida: **1**. Duraci?n: 0.892 s.

[Registro JSON](controles/red_constructor.json) ? [Log UTF-8](controles/red_constructor.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-m' 'pytest' 'tests/unit/test_rules_sensitivity_correction_builder.py' '-q'
```

## green_constructor_helpers

Inicio: 2026-09-25T15:14:35.945720+00:00. Salida: **0**. Duraci?n: 0.604 s.

[Registro JSON](controles/green_constructor_helpers.json) ? [Log UTF-8](controles/green_constructor_helpers.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-m' 'pytest' 'tests/unit/test_rules_sensitivity_correction_builder.py' '-q'
```

## red_destino_sellado

Inicio: 2026-09-26T20:29:20.509741+00:00. Salida: **1**. Duraci?n: 0.715 s.

[Registro JSON](controles/red_destino_sellado.json) ? [Log UTF-8](controles/red_destino_sellado.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-m' 'pytest' 'tests/unit/test_rules_sensitivity_correction_builder.py' '-q'
```

## green_destino_sellado

Inicio: 2026-09-26T20:30:06.551188+00:00. Salida: **0**. Duraci?n: 0.616 s.

[Registro JSON](controles/green_destino_sellado.json) ? [Log UTF-8](controles/green_destino_sellado.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-m' 'pytest' 'tests/unit/test_rules_sensitivity_correction_builder.py' '-q'
```

## e3_archivo_dependencias_correctas

Inicio: 2026-09-26T20:32:21.524677+00:00. Salida: **0**. Duraci?n: 1.318 s.

[Registro JSON](controles/e3_archivo_dependencias_correctas.json) ? [Log UTF-8](controles/e3_archivo_dependencias_correctas.log)

```powershell
& '.venv/Scripts/python.exe' '-I' '-B' '-X' 'utf8' 'entregas/entrega_3/archivo/paquete_redaccion/scripts/verificar_paquete.py'
```

## preservacion_previa_cierre

Inicio: 2026-09-26T20:34:54.761695+00:00. Salida: **0**. Duraci?n: 15.835 s.

[Registro JSON](controles/preservacion_previa_cierre.json) ? [Log UTF-8](controles/preservacion_previa_cierre.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-X' 'utf8' 'entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/verificar_preservacion.py' '--output' 'entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/preservacion_previa_cierre.json'
```

## construccion_previa

Inicio: 2026-09-26T20:36:29.785239+00:00. Salida: **0**. Duraci?n: 24.723 s.

[Registro JSON](controles/construccion_previa.json) ? [Log UTF-8](controles/construccion_previa.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-X' 'utf8' 'scripts/correct_rules_sensitivity_report.py' '--source-package' 'entregas/entrega_4/reglas_historicas/20260925T005436Z' '--destination' 'C:\Users\pablo\AppData\Local\Temp\e4_correction_preview_20260926T173629' '--e3-reference' 'Paquete de evidencia'
```

## verificacion_previa_integral

Inicio: 2026-09-26T20:38:46.334180+00:00. Salida: **0**. Duraci?n: 28.230 s.

[Registro JSON](controles/verificacion_previa_integral.json) ? [Log UTF-8](controles/verificacion_previa_integral.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-X' 'utf8' 'scripts/verify_rules_sensitivity_correction.py' '--package' 'C:\Users\pablo\AppData\Local\Temp\e4_correction_preview_20260926T173629' '--parent' 'entregas/entrega_4/reglas_historicas/20260925T005436Z' '--output' 'entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/verificacion_previa_integral.json'
```

## suite_completa

Inicio: 2026-09-26T20:38:46.336494+00:00. Salida: **0**. Duraci?n: 187.863 s.

[Registro JSON](controles/suite_completa.json) ? [Log UTF-8](controles/suite_completa.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-X' 'utf8' '-m' 'pytest' '-q'
```

## red_carga_verificador_sin_cache

Inicio: 2026-09-26T20:39:44.687781+00:00. Salida: **1**. Duraci?n: 1.029 s.

[Registro JSON](controles/red_carga_verificador_sin_cache.json) ? [Log UTF-8](controles/red_carga_verificador_sin_cache.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-m' 'pytest' 'tests/unit/test_rules_sensitivity_correction_builder.py::test_generic_v2_entrypoint_is_readonly_even_without_python_B' '-q'
```

## green_carga_verificador_sin_cache

Inicio: 2026-09-26T20:39:46.087892+00:00. Salida: **0**. Duraci?n: 0.926 s.

[Registro JSON](controles/green_carga_verificador_sin_cache.json) ? [Log UTF-8](controles/green_carga_verificador_sin_cache.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-m' 'pytest' 'tests/unit/test_rules_sensitivity_correction_builder.py::test_generic_v2_entrypoint_is_readonly_even_without_python_B' '-q'
```

## ruff_final

Inicio: 2026-09-26T20:42:44.063282+00:00. Salida: **0**. Duraci?n: 0.109 s.

[Registro JSON](controles/ruff_final.json) ? [Log UTF-8](controles/ruff_final.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-X' 'utf8' '-m' 'ruff' 'check' 'scripts/correct_rules_sensitivity_report.py' 'scripts/rules_sensitivity_correction_docs.py' 'scripts/rules_sensitivity_exposure.py' 'scripts/rules_sensitivity_h2.py' 'scripts/verify_rules_sensitivity_correction.py' 'scripts/report_historical_rules_sensitivity.py' 'scripts/verify_rules_sensitivity_package.py' 'tests/unit/test_rules_sensitivity_correction_builder.py' 'tests/unit/test_rules_sensitivity_correction_verifier.py' 'tests/unit/test_rules_sensitivity_exposure.py' 'tests/unit/test_rules_sensitivity_h2.py' 'tests/unit/test_rules_sensitivity_reporting.py'
```

## suite_completa_final

Inicio: 2026-09-26T20:43:12.276002+00:00. Salida: **0**. Duraci?n: 179.187 s.

[Registro JSON](controles/suite_completa_final.json) ? [Log UTF-8](controles/suite_completa_final.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-X' 'utf8' '-m' 'pytest' '-q'
```

## construccion_final

Inicio: 2026-09-26T20:43:12.348504+00:00. Salida: **0**. Duraci?n: 24.852 s.

[Registro JSON](controles/construccion_final.json) ? [Log UTF-8](controles/construccion_final.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-X' 'utf8' 'scripts/correct_rules_sensitivity_report.py' '--source-package' 'entregas/entrega_4/reglas_historicas/20260925T005436Z' '--destination' 'entregas\entrega_4\reglas_historicas\correccion_exposicion_h2_20260925T150139Z\paquete_20260926T204312Z' '--e3-reference' 'Paquete de evidencia'
```

## verificacion_final

Inicio: 2026-09-26T20:45:30.659041+00:00. Salida: **0**. Duraci?n: 28.407 s.

[Registro JSON](controles/verificacion_final.json) ? [Log UTF-8](controles/verificacion_final.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-X' 'utf8' 'entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/herramientas/verify_rules_sensitivity_package.py' '--package' 'entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z' '--parent' 'entregas/entrega_4/reglas_historicas/20260925T005436Z' '--output' 'entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/verificacion_final.json'
```

## portabilidad_corrupciones

Inicio: 2026-09-26T20:45:30.661179+00:00. Salida: **0**. Duraci?n: 139.480 s.

[Registro JSON](controles/portabilidad_corrupciones.json) ? [Log UTF-8](controles/portabilidad_corrupciones.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-X' 'utf8' 'entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/auditar_portabilidad_corrupciones.py' '--package' 'entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z' '--parent' 'entregas/entrega_4/reglas_historicas/20260925T005436Z' '--output' 'entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/portabilidad_corrupciones.json'
```

## preservacion_final

Inicio: 2026-09-26T20:49:21.886880+00:00. Salida: **0**. Duraci?n: 1.500 s.

[Registro JSON](controles/preservacion_final.json) ? [Log UTF-8](controles/preservacion_final.log)

```powershell
& '.venv/Scripts/python.exe' '-B' '-X' 'utf8' 'entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/verificar_preservacion.py' '--package' 'entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z' '--output' 'entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/preservacion_final.json'
```

## Auditor?as adicionales

El linaje archivado y sus comandos est?n en [auditoria_linaje/linaje_exposicion.md](auditoria_linaje/linaje_exposicion.md). Las fases RED/GREEN focales de H2 est?n en [auditoria_h2/README.md](auditoria_h2/README.md); las de exposici?n en `auditoria_exposicion/`. La revisi?n independiente y la inspecci?n de la figura est?n en [revision_independiente.md](revision_independiente.md).

Los ocho comandos de corrupciones y el comando con padre/correcci?n trasladados, sus salidas y errores sem?nticos esperados, est?n dentro de [portabilidad_corrupciones.json](portabilidad_corrupciones.json). Fueron copias temporales: recalcular el sello fue parte del ensayo negativo, no una alteraci?n del producto ni del padre.

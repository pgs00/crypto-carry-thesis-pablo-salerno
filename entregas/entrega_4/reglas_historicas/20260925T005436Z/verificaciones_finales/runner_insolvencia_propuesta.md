# Propuesta pendiente: conservar trayectorias insolventes terminadas

No aplicada. Los cuatro procesos activos conservan el runner, motor, configuraciones y snapshot originales. Las pruebas usan dobles controlados de replay y escritura; no ejecutan una simulación histórica.

## Evidencia RED

Comando: `.venv/Scripts/python.exe -B -X utf8 -m pytest tests/unit/test_rules_sensitivity_runner.py -q`.

Resultado: exit 1; 4 failed, 4 passed en 13.42 s. Salida completa en `runner_insolvencia_tdd_red.txt` y hashes de los tres archivos de producción vigilados en `runner_insolvencia_tdd_red.json`, sin cambios.

Fallan por el comportamiento pendiente: guardar una trayectoria insolvente terminada, resolver PROJECT cuando el helper está reubicado, seleccionar el helper autenticado de herramientas, y rechazar ese helper alterado después del sellado. Pasan el caso complete terminado y los tres rechazos de trayectoria incompleta.

Ruff del archivo nuevo: exit 0; `runner_insolvencia_ruff.txt` y `.json`.

## Cambio mínimo propuesto, después del cierre de los procesos

En el runner corregido, resolver el proyecto desde el módulo Config efectivamente importado:

```python
PROJECT = Path(sys.modules[Config.__module__].__file__).resolve().parents[2]
```

Conservar la validación del reloj y la conciliación. Cambiar sólo los estados terminados admitidos:

```python
if b.status not in {"complete", "insolvent"} or b.now != timestamp(config.end) - 1:
    raise ValueError(f"Incomplete scenario: {b.status}: {b.reasons}")
```

El replay existente continúa hasta end-1 aunque el estado sea insolvent. No se modifica el motor, no se fuerza el estado a complete y no se descartan patrimonio negativo, fills, H3 ni artefactos diarios. La escritura conserva engine_status y la conciliación original. El snapshot codigo_ejecutado permanece intacto; el helper corregido se publicaría en herramientas/run_historical_rules_sensitivity.py y quedaría incluido en el manifiesto del paquete.

En el reproductor, después de verificar íntegramente la fuente sellada y antes de crear destino, preferir herramientas/run_historical_rules_sensitivity.py si existe; exigir que sea miembro del manifiesto autenticado y verificar su SHA256 explícitamente. Si está presente pero no está autenticado, fallar sin fallback. Si no existe, conservar el runner del snapshot, igualmente autenticado por el manifiesto. Mantener cwd y PYTHONPATH apuntando a codigo_ejecutado, para usar exactamente su motor y configuraciones. Registrar ruta y SHA256 del runner seleccionado en la auditoría fresca.

La selección propuesta no autoriza modificar las copias congeladas ni ejecutar un lote nuevo. Tras autorización, ejecutar las pruebas focalizadas de runner y reproducción y Ruff; conservar este RED como evidencia anterior a la corrección.

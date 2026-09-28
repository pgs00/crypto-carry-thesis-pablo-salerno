# Evidencia de costos y capacidad

[Reporte](reporte.md) · [HTML](reporte.html) · [Síntesis](sintesis.md)

Verificación offline desde cualquier ruta con Python 3.14 y las dependencias
fijadas en `herramientas/pyproject.toml` y `herramientas/uv.lock`:

```powershell
python -B -X utf8 herramientas/scripts/verify_cost_capacity.py --package . --output ../auditoria_nueva.json
```

El destino debe ser nuevo y externo al sello. No se exige HEAD ni índice Git.
El verificador recalcula cierres/períodos, exposición corregida, H2/H3,
órdenes/fills/ledger, tarifas/precios y capacidad desde ventanas incluidas.
H1 y oportunidad BASE se autentican y se comprueba igualdad de inputs y agregados;
no se cuentan 18 poblaciones independientes. No se ejecuta el motor ni se vuelve
a recorrer cada minuto H3. Constructor/verificador comparten lógica declarada.

Para contrastar nuevamente las ventanas contra archivos masivos locales:

```powershell
python -B -X utf8 herramientas/scripts/verify_cost_capacity.py --package . --data-root D:/Backtesting --output ../auditoria_local_nueva.json
```

Los volúmenes incluidos son extractos exactos por ventana solicitada, ligados
a partición, SHA-256 y manifiesto autenticado. El modo offline comprueba sus
denominadores y la ejecución; no lee una serie masiva ausente. Las corridas
completas permanecen bajo la raíz local indicada en `dependencias.json`.

`codigo_ejecutado` conserva la primera identidad congelada. `codigo_runner_v2`
y protocolos v1/v2 documentan el endurecimiento técnico de recuperación después
del lanzamiento de C02, sin cambio de identidad económica. Las configuraciones,
comandos, intentos, tiempos, RAM, fallos de pruebas y correcciones se conservan.
La incompatibilidad histórica de inventario/config.py continúa documentada;
no se usó para ocultar los cambios de este bloque.

# Evidencia de costos y capacidad

[Reporte](reporte.md) · [HTML](reporte.html) · [Síntesis](sintesis.md) · [Auditoría](auditoria_ejecucion.md)

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

`forecast_evaluation.csv.gz` conserva sin pérdida el CSV original de cada
corrida. El verificador descomprime en memoria y coteja SHA-256 y tamaño de los
bytes originales; no escribe dentro del sello. El catálogo de transferencias
distingue hash/tamaño del archivo incluido y del original. Esos diagnósticos
acreditan la igualdad por corrida, sin aumentar la población H1 reutilizada.

`codigo_ejecutado` conserva la primera identidad congelada. `codigo_runner_v2`,
`codigo_runner_v3` y protocolos v1/v2/v3 documentan la recuperación reforzada después
del lanzamiento de C02, sin cambio de identidad económica. Las configuraciones,
comandos, intentos, tiempos, RAM, fallos de pruebas y correcciones se conservan.
La incompatibilidad histórica de inventario/config.py continúa documentada;
no se usó para ocultar los cambios de este bloque.

Las once pruebas negativas operan sobre copias descartables, renuevan hashes y
exigen el rechazo semántico de configuración, tarifas, selección, cantidades,
volumen, períodos, hipótesis, caja y ventana elegible. Se pueden reproducir con
las dependencias de pruebas fijadas para el mismo entorno:

```powershell
$env:COST_CAPACITY_PACKAGE = (Resolve-Path .).Path
python -B -m pytest herramientas/tests/integration/test_cost_capacity_package_integration.py -q -p no:cacheprovider
```

Los controles realizados después del sello (pruebas negativas, preservación,
exportación binaria y verificación offline) se guardan en `../pruebas/` y
`../controles/`. Esos archivos son externos al paquete para preservar el sello;
sus resultados indican el paquete comprobado. Las herramientas incluidas
permiten repetir los controles semánticos aun sin esa carpeta de trabajo.

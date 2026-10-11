# Distribución documental B3 — 2026-10-10

Derivada de `paquete_20260927T231610Z`. Esta distribución tiene manifiesto propio;
preserva ciencia, configuraciones, fuentes y resultados, y omite instrucciones
operativas de la conversación. No corresponde a una ejecución económica nueva.

[Protocolo descriptivo](protocolo_distribucion.md) ·
[Inventario de derivación](procedencia/derivacion.json) ·
[Manifiesto histórico de procedencia](procedencia/manifiesto_original.json)

El manifiesto histórico no verifica el nuevo paquete: la verificación actual
usa `manifiesto_paquete.json` más los controles científicos originales y
comprueba identidad de todos los miembros retenidos. Los registros y pendientes
del reporte/README histórico que sigue se refieren a su fecha, no al estado
global actual de E4. Las referencias a documentos retirados en registros
congelados son trazabilidad histórica, no instrucciones operativas vigentes.

Los comandos de verificación compacta funcionan desde la distribución o desde una copia
limpia, con las dependencias del lock incluido y salida nueva fuera del sello.
El modo compacto usa sólo evidencia incluida, sin Git, red ni datos masivos.

---

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

Las suites de adulteración semántica incluidas conservan las pruebas y
mensajes esperados del paquete histórico original. Sus comandos corresponden
a aquel paquete, conservado en el respaldo externo, no a esta distribución.
La guardia adicional de preservación aquí rechaza primero cualquier byte
científico alterado, aun con hashes exteriores renovados; por ello el mensaje
puede anteceder al rechazo económico específico exigido por la suite original.
Las pruebas históricas permanecen intactas y no se declaran ejecutadas sobre
esta distribución. La verificación compacta vigente es el comando anterior.
Los controles actuales de integridad están en la suite viva del repositorio
`tests/unit/test_documentary_distribution.py` y en los certificados externos
identificados por el hash de cada distribución; incluyen omisión científica,
bytes cambiados y exclusiones arbitrarias con sellos renovados.

Los controles realizados después del sello (pruebas negativas, preservación,
exportación binaria y verificación offline) se guardan en `../pruebas/` y
`../controles/`. Esos archivos son externos al paquete para preservar el sello;
sus resultados indican el paquete comprobado. Las herramientas incluidas
permiten repetir la verificación compacta sin esa carpeta de trabajo.

# Riesgo intradía, incidentes y garantías

Distribución documental `20261010`. Consultar el reporte y las tablas indicados abajo. [Protocolo y procedencia de esta distribución](protocolo_distribucion.md). Los controles históricos incluidos no constituyen una verificación de esta nueva distribución.


Informe técnico preliminar sobre cuatro carteras publicadas: BASE y MARGEN_2X, condicional y permanente. Se reconstruyen sus estados originales sobre la unión de minutos, eventos financieros y cierres diarios entre enero de 2022 y agosto de 2026. No se ejecutó un backtest ni un replay. Este bloque no completa toda la Entrega 4.

## Lectura

- [Reporte HTML](reporte.html) y [Markdown](reporte.md): resultados, convenciones, límites y propuestas pendientes.
- [Catálogo completo](catalogo_completo.html): 449 episodios por activo y ciclo, sin selección por signo del resultado.
- [Matriz de cobertura](documentos/matriz_cobertura_feedback.csv), [feedback literal](documentos/feedback_e3.md) y [protocolo previo](documentos/protocolo.md).
- [Cobertura pendiente](cobertura_pendiente.md) y [resolución de la revisión](revision_resuelta.md).
- `tablas/`: precisión numérica completa, procedencia por corrida y copias intactas de H1/H2/H3.
- `figuras/`: 13 figuras PNG/SVG y sus fuentes CSV; las envolventes visuales no sustituyen las métricas calculadas sobre la serie completa.
- `evidencia/`: estados financieros, todos los episodios descubiertos y la ventana del 23 al 25 de marzo de 2023.
- `evidencia/calidad_precios.parquet`: razón explícita de selección o arrastre por referencia y `time_ns`; se comparte entre carteras y fases del mismo instante. El diccionario y la cobertura están en `evidencia/calidad_precios.json`. El origen, edad y carácter estimado se conservan en cada observación de la serie financiera, enlazada por esa clave.
- `herramientas/scripts/` y `herramientas/tests/`: posprocesadores, verificador y pruebas. `codigo_reconstruccion_ejecutado/` conserva además la versión exacta que produjo las particiones.

## Dependencias e identidad

La muestra comprende 9.851.104 observaciones y 224 particiones comprimidas (2.934.571.231 bytes). La serie completa permanece fuera del paquete publicable. `series_locales.json` enumera sus archivos, intervalos y hashes; `fuentes_precios.json` identifica las fuentes locales compartidas. Los nombres de rutas registrados documentan la ejecución, pero el verificador exige rutas proporcionadas por argumento.

| Entrada | Identidad SHA-256 del manifiesto |
| --- | --- |
| Padre, doce carteras | `77f1cfcaf4fb13044dbcb3b242a2eb19749cf7e88806db023a08bbe4ec272057` |
| Corrección de exposición/H2 | `e735207869c08bbd0b9b04818c8855ecd9576bd979d3127b5ff108f61d3843ce` |
| Protocolo sellado antes de calcular | `b62ead9cc80ebf91f71080383bc613db24a8b81bccef02dfd347572050c2ce15` |

El último hash corresponde a `documentos/protocolo.md`, no a un manifiesto. La identidad del presente paquete está en `manifiesto_paquete.sha256`. Ese manifiesto enumera todos los miembros excepto él mismo y su sidecar. No se debe regenerar el manifiesto para ocultar una diferencia: cualquier revisión posterior requiere una nueva carpeta.

Entorno probado: Python 3.14.3, NumPy 2.3.5 y PyArrow 25.0.1; Matplotlib 3.11.2 para figuras, pytest 9.1.1 y Ruff 0.16.8 para pruebas. El archivo `documentos/entorno_ejecucion.json` registra versiones y ejecutable reales. No hace falta cargar el motor económico para verificar este producto.

## Verificación desde cualquier ruta

Ejemplo PowerShell con rutas explícitas; cambiar las variables si se traslada la evidencia. El resultado debe ser un archivo nuevo y externo a las entradas. El verificador no escribe bytecode, no consulta Git y rechaza una salida dentro de cualquier fuente protegida.

```powershell
$repo = 'C:/Users/pablo/Documentos/UCEMA/Tesina/Backtesting'
$py = "$repo/.venv/Scripts/python.exe"
$paquete = "$repo/entregas/entrega_4/riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z"
$padre = "$repo/entregas/entrega_4/reglas_historicas/20260925T005436Z"
$correccion = "$repo/entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z"
$series = 'D:/Backtesting/outputs/riesgo_intradia_20260926T214118Z/completa'
$datos = 'D:/Backtesting'
$verificador = "$paquete/herramientas/scripts/verify_intraday_risk.py"

# Compacta: hashes, aritmética, catálogo, tablas y linaje proporcionado.
& $py -B -X utf8 $verificador --scope compact --package $paquete --parent $padre --correction $correccion

# Completa: además reconstruye toda la grilla desde estados/precios locales.
& $py -B -X utf8 $verificador --scope complete --package $paquete --parent $padre --correction $correccion --series-root $series --data-root $datos
```

La modalidad compacta permite omitir padre/corrección para revisar el paquete solo; entonces declara esos linajes no autenticados. No recalcula el máximo global ni certifica completitud de precios por minuto. La modalidad completa exige las cuatro dependencias, autentica precios y particiones, reconstruye sus valores, enlaza la evidencia compacta con esos estados y recalcula los drawdowns globales. Reutiliza las funciones archivadas de estados, grilla y selección de precios; la aritmética contable y la reducción global de drawdown se comprueban además en el verificador. No se presenta como una implementación independiente de todo el posprocesador.

Las pruebas del paquete pueden ejecutarse desde `herramientas` con el mismo entorno, sin escribir cachés:

```powershell
Push-Location "$paquete/herramientas"
try { & $py -B -m pytest -p no:cacheprovider "$paquete/herramientas/tests" } finally { Pop-Location }
```

Los resultados efectivos del cierre se conservan fuera del paquete sellado, en la carpeta de ejecución, asociados a su SHA-256. Así una verificación posterior no cambia el paquete que verifica.

## Reproducción de productos

Los comandos ejecutados, duración de la ventana corta, auditorías y logs se conservan en la carpeta de ejecución. Para reconstruir en otra oportunidad, proporcionar a `build_intraday_risk.py` un `--output` nuevo y vacío, un `--series-root` nuevo y los mismos `--parent` y `--data-root`; luego ejecutar `intraday_risk_tables.py` con la corrección original y `intraday_risk_report.py`. Nunca apuntar un generador a este paquete sellado.

Los argumentos de período utilizados fueron medianoches UTC completas. Los timestamps financieros conservan los enteros originales con nanosegundos, sin redondear funding. La interfaz auxiliar `utc_ns` no se utiliza para reinterpretar instantes financieros ni se acredita aquí para argumentos futuros con fracciones de segundo.

La contabilidad Decimal independiente concilia exactamente los cierres. La reconstrucción vectorizada usa float64 y la tolerancia monetaria original de 1E-8 USDT; el mayor residual de sus 6.816 cierres es 3,637978807091713e-12 USDT. Ninguna cifra se ajustó para coincidir con un PDF redondeado.

# Reproducción del estudio

Usar desde la raíz del checkout. Las configuraciones efectivas y snapshots
congelados, no los perfiles CLI antiguos `configs/base.toml` y
`configs/robustness.toml`, determinan las carteras finales. Los destinos nuevos
se crean fuera de los paquetes sellados. No sobrescribir manifiestos ni cambiar
hashes para aceptar divergencias. Esta guía conserva comandos reproducibles;
el [registro local](repository_cleanup.md#verificaciones) identifica cuáles
se ejecutaron durante la limpieza, sus resultados y bloqueos.


## 1. Lectura, sin ejecutar código

Abrir los reportes Markdown/HTML, tablas CSV y protocolos del [índice de resultados E4](../entregas/entrega_4/README.md).
No requiere Python ni datos de mercado. Los índices de corridas y manifiestos
identifican las fuentes; leerlos no equivale a volver a verificarlas.

## 2. Verificación offline de evidencia compacta

Los comandos siguientes usan los verificadores congelados de cada paquete.
Requieren **Python 3.14** y las dependencias de [pyproject.toml](../pyproject.toml)
y [uv.lock](../uv.lock); el entorno local de referencia usa Python 3.14.3
en Windows. En Linux se comprobó una diferencia de últimos dígitos que hace
fallar la comparación literal del CSV de intervalos B6, aunque sus controles
numéricos pasaron en esa comprobación histórica. La diferencia máxima fue
`6.938893903907228e-18`; no se relaja la comparación ni se afirma un PASS
integral en Linux. Ver el [alcance comprobado](repository_cleanup.md#recuperacion-de-antecedentes).
Preparar el entorno desde la raíz del checkout, antes de la verificación:

```powershell
uv sync --frozen --python 3.14.3
```

La preparación puede necesitar acceso a paquetes si no están instalados o
en caché. Los verificadores posteriores no requieren red ni `D:/Backtesting`.
No ejecutar `uv sync` dentro de un paquete sellado. Sus copias de código/lock
fijan la procedencia; el entorno reutilizado queda fuera de las evidencias.

Desde la **raíz del repositorio**, parametrizar ubicación y salida. La matriz
resuelve las rutas vigentes; si se trasladan paquetes, reemplazar sus valores
en `$paquetes` y `$padre`. Elegir siempre una carpeta de auditoría nueva y
externa a todos los paquetes; los JSON/logs son los únicos productos esperados.

```powershell
$repo = (Resolve-Path .).Path
$py = Join-Path $repo '.venv/Scripts/python.exe'
$paquetes = @{}
Import-Csv (Join-Path $repo 'docs/entrega_4/matriz_avance.csv') | ForEach-Object {
    if ($_.paquete_vigente) { $paquetes[$_.id] = Join-Path $repo $_.paquete_vigente }
}
$padre = Join-Path $repo 'entregas/entrega_4/reglas_historicas/20260925T005436Z'
$salida = Join-Path $env:TEMP ('e4_offline_' + (Get-Date -Format 'yyyyMMddTHHmmss'))
if (Test-Path -LiteralPath $salida) { throw 'Elegir una salida nueva' }
New-Item -ItemType Directory -Path $salida | Out-Null
```

Ejecutar cada línea por separado y comprobar su código de salida y JSON.
Una ayuda `--help` satisfactoria sólo valida la interfaz; no acredita el pase
del paquete. Los resultados ejecutados durante esta limpieza local están en el
[registro de verificaciones](repository_cleanup.md#verificaciones). Los
[controles históricos](repository_cleanup.md#recuperacion-de-antecedentes)
conservan sus fechas y alcances originales.

```powershell
& $py -B -X utf8 "$($paquetes.BASE)/herramientas/verify_rules_sensitivity_correction.py" --package $paquetes.BASE --parent $padre --output "$salida/base.json"
& $py -B -X utf8 "$($paquetes.RIESGO)/herramientas/scripts/verify_intraday_risk.py" --scope compact --package $paquetes.RIESGO --parent $padre --correction $paquetes.BASE --output "$salida/riesgo.json"
& $py -B -X utf8 "$($paquetes.B1_CAPITAL)/herramientas/scripts/verify_return_capital.py" --package $paquetes.B1_CAPITAL --output "$salida/b1_capital.json"
& $py -B -X utf8 "$($paquetes.B1_SOFR)/herramientas/scripts/verify_sofr_benchmark.py" --package $paquetes.B1_SOFR --previous $paquetes.B1_CAPITAL --output "$salida/b1_sofr.json"
& $py -B -X utf8 "$($paquetes.B2)/herramientas/scripts/verify_signal_sensitivity.py" --package $paquetes.B2 --output "$salida/b2.json"
& $py -B -X utf8 "$($paquetes.B3)/herramientas/scripts/verify_cost_capacity.py" --package $paquetes.B3 --output "$salida/b3.json"
& $py -B -X utf8 "$($paquetes.B4)/herramientas/scripts/verify_execution_delays.py" --package $paquetes.B4 --output "$salida/b4.json"
& $py -B -X utf8 "$($paquetes.B5)/herramientas/scripts/verify_stress_counterfactual.py" $paquetes.B5 --output "$salida/b5.json"
& $py -B -I -X utf8 "$($paquetes.B6)/herramientas/scripts/verify_stability_uncertainty.py" --candidate $paquetes.B6 --output "$salida/b6.json" --forbid-root 'D:/Backtesting'
```

BASE requiere su padre completo. Riesgo autentica los linajes suministrados,
pero el modo compacto no recalcula extremos globales ni precios por minuto.
B1 capital, sin dependencias adicionales, comprueba el paquete interno; su
[guía][capital-guia] documenta el modo con padre, corrección, riesgo y E3.
SOFR recalcula la cuenta hipotética y autentica B1 capital. B2–B5 recomputan
lo declarado en cada guía desde extractos y agregados; no vuelven a leer
toda la historia de mercado. B6 vuelve a calcular también las estadísticas
del bootstrap desde inputs compactos, sin simular carteras. Las herramientas
comparten partes del posprocesamiento; imágenes verificadas por hash y tablas
de origen no equivalen a una inspección visual nueva.

Los manifiestos comprueban bytes y pertenencia al inventario, no autenticidad
histórica del exchange. Los sellos y sus sidecars nunca se renuevan para
hacer pasar una divergencia. Los controles de integridad binaria Git/exportación
de cada revisión están separados de los cálculos en el registro externo.

El script archivado `scripts.verify_repository_evidence` corresponde a la limpieza histórica del
20/09/2026 y exige hashes antiguos del código económico. Su fallo anterior por
fuentes evolucionadas se conserva en los antecedentes; no es un control universal
de E4. Los verificadores por paquete de arriba fijan su propio alcance.

## Entrega 3: presentación y extracción autenticada

La presentación E3 se comprueba desde el ZIP original, sin datos masivos ni
nuevos backtests. Para regenerarla, elegir otra salida externa que no exista:

```powershell
$repo = (Resolve-Path .).Path
$py = Join-Path $repo '.venv/Scripts/python.exe'
& $py -B -X utf8 -m scripts.publish_thesis --verify
$presentacion = Join-Path $env:TEMP ('e3_presentacion_' + (Get-Date -Format 'yyyyMMddTHHmmss'))
if (Test-Path -LiteralPath $presentacion) { throw 'Elegir una salida nueva' }
& $py -B -X utf8 -m scripts.publish_thesis --output $presentacion
```

El paquete continuo tiene miembros directamente en la raíz del ZIP. El ZIP v2
histórico contiene el subdirectorio `paquete_redaccion`. Autenticar cada ZIP
contra su sidecar conservado **antes** de extraer. No volver a crear checksums:

```powershell
function Expand-AuthenticatedE3([string]$zip, [string]$destination) {
    if (Test-Path -LiteralPath $destination) { throw 'El destino debe ser nuevo' }
    $esperado = ((Get-Content -LiteralPath ($zip + '.sha256') -Raw).Trim() -split '\s+')[0]
    $observado = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
    if ($observado.ToLowerInvariant() -ne $esperado.ToLowerInvariant()) { throw 'SHA-256 divergente' }
    Expand-Archive -LiteralPath $zip -DestinationPath $destination
}
$e3 = Join-Path $env:TEMP ('e3_continua_' + (Get-Date -Format 'yyyyMMddTHHmmss'))
Expand-AuthenticatedE3 (Join-Path $repo 'entregas/entrega_3/paquete_actualizacion_entrega_3_continua.zip') $e3
Push-Location $e3
try { & $py -I -S -B -X utf8 verificar.py } finally { Pop-Location }

$v2destino = Join-Path $env:TEMP ('e3_v2_' + (Get-Date -Format 'yyyyMMddTHHmmss'))
Expand-AuthenticatedE3 (Join-Path $repo 'entregas/entrega_3/archivo/paquete_redaccion_entrega_3_v2.zip') $v2destino
$v2 = Join-Path $v2destino 'paquete_redaccion'
& $py -B -X utf8 "$v2/scripts/verificar_paquete.py"
```

Comprobar los códigos de salida; SHA-256 autentica el ZIP preservado y los
verificadores internos comprueban inventario/evidencia. Las carpetas extraídas
son copias de trabajo externas; no editar sus miembros para fabricar un pase.
Para los comandos históricos de `reproducir.py`, `diccionario.py` o
`preparar_paquete.py`, usar las herramientas incluidas en `$v2`, sus dependencias
y destinos nuevos; no reconstruir ni sobrescribir los ZIP canónicos.

La corrección BASE recibe una **ruta de directorio** mediante `--e3-reference`,
no el ZIP. Después de la extracción autenticada anterior, el ejemplo editorial
sin replay es:

```powershell
$correccion = Join-Path $env:TEMP ('e4_correccion_' + (Get-Date -Format 'yyyyMMddTHHmmss'))
& $py -B -X utf8 scripts/report_historical_rules_sensitivity.py `
  --source-package entregas/entrega_4/reglas_historicas/20260925T005436Z `
  --destination $correccion `
  --e3-reference $e3
```

Este comando construye y sella un derivado editorial nuevo; no modifica la
corrección vigente ni las carteras. La
[guía de exposición/H2](entrega_4/reglas_historicas/lectura_resultados.md)
describe su verificación posterior. Para consumidores históricos que exigen
las rutas originales, restaurar previamente sólo las raíces necesarias según
[recuperación de antecedentes](repository_cleanup.md#recuperacion-de-antecedentes).

## 3. Fuentes masivas y replay del motor, fuera de este cierre

Volver a autenticar mercados o reconstruir todo el riesgo intradía exige las
fuentes locales indicadas por sus manifiestos, normalmente `D:/Backtesting`.
Los parámetros `--data-root`, `--series-root` o riesgo `--scope complete`
amplían la verificación y no implican necesariamente un replay económico.
No se confunden con el nivel compacto ni se ejecutan en este cierre.

Repetir carteras requiere además el snapshot económico, configuraciones,
dependencias y contratos exactos de cada bloque, junto con destinos nuevos.
La [guía de reglas](entrega_4/reglas_historicas/reproduccion.md),
la [reproducción B5][b5-limites] y los protocolos del índice E4 conservan los
requisitos y comandos históricos. Los runners pueden escribir estados:
nunca deben apuntar al paquete sellado. Esta guía no ordena una nueva
tanda ni convierte una comprobación offline en reproducción del motor.


## Control de navegación

```powershell
& '.\.venv\Scripts\python.exe' -B -X utf8 -m scripts.verify_documentation
```

Comprueba codificación y enlaces locales de una lista explícita de documentos
activos. No verifica economía ni todos los documentos históricos o sellados.

[capital-guia]: ../entregas/entrega_4/retorno_capital/20260927T143928Z/paquete_20260927T152732Z/README.md
[b5-limites]: ../entregas/entrega_4/estres_contrafactual/20260930T214617Z/paquete_20261001T211248Z/reproducibilidad.md

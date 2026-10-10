# Reproducción del estudio

Usar desde la raíz del checkout. Las configuraciones efectivas y snapshots
congelados, no los perfiles CLI antiguos `configs/base.toml` y
`configs/robustness.toml`, determinan las carteras finales. Los destinos nuevos
se crean fuera de los paquetes sellados. No sobrescribir manifiestos ni cambiar
hashes para aceptar divergencias.


## 1. Lectura, sin ejecutar código

Abrir los reportes Markdown/HTML, tablas CSV y protocolos del [índice de resultados E4](../entregas/entrega_4/README.md).
No requiere Python ni datos de mercado. Los índices de corridas y manifiestos
identifican las fuentes; leerlos no equivale a volver a verificarlas.

## 2. Verificación offline de evidencia compacta

Los comandos siguientes usan los verificadores incluidos en las distribuciones
vigentes. Sus adaptaciones documentales comprueban la identidad nueva y conservan
los controles científicos; no requieren los prompts retirados ni Git.
Requieren **Python 3.14** y las dependencias de [pyproject.toml](../pyproject.toml)
y [uv.lock](../uv.lock); el entorno local de referencia usa Python 3.14.3
en Windows. En Linux se comprobó una diferencia de últimos dígitos que hace
fallar la comparación literal del CSV de intervalos B6, aunque sus controles
numéricos pasaron en esa comprobación histórica. La diferencia máxima fue
`6.938893903907228e-18`; no se relaja la comparación ni se afirma un PASS
integral en Linux.
Preparar el entorno desde la raíz del checkout, antes de la verificación:

```powershell
uv --cache-dir .uv-cache sync --frozen --python 3.14.3
```

La preparación puede necesitar acceso a paquetes si no están instalados o
en caché; con el entorno/caché disponible se puede añadir `--offline`.
Los verificadores posteriores no requieren red ni `D:/Backtesting`.
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
del paquete. Los controles históricos incluidos en los paquetes conservan
sus fechas y alcances originales.

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
SOFR recalcula la cuenta hipotética y comprueba la distribución B1 capital
indicada, conservando por separado la identidad histórica de su dependencia.
Ese control no se presenta como comprobación íntegra del sello original retirado.
B2–B5 recomputan
lo declarado en cada guía desde extractos y agregados; no vuelven a leer
toda la historia de mercado. B6 vuelve a calcular también las estadísticas
del bootstrap desde inputs compactos, sin simular carteras. Las herramientas
comparten partes del posprocesamiento; imágenes verificadas por hash y tablas
de origen no equivalen a una inspección visual nueva.

Los manifiestos comprueban bytes y pertenencia al inventario, no autenticidad
histórica del exchange. Los sellos y sus sidecars nunca se renuevan para
hacer pasar una divergencia. Las herramientas históricas conservadas en los
snapshots pueden exigir estados antiguos del repositorio; los verificadores
por paquete de arriba fijan el alcance actual de la comprobación compacta.

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

El paquete continuo tiene miembros directamente en la raíz del ZIP. Autenticarlo
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

$v2 = Join-Path $repo 'entregas/entrega_3/archivo/distribucion_20261010'
& $py -B -X utf8 "$v2/scripts/verificar_paquete.py"
```

Comprobar los códigos de salida; SHA-256 autentica el ZIP continuo preservado y
los verificadores internos comprueban inventario/evidencia. La distribución
histórica E3 se comprueba directamente, sin extraer los ZIP retirados. Su
[LEEME](../entregas/entrega_3/archivo/distribucion_20261010/LEEME.md) documenta
herramientas, fuentes y límites. Los scripts históricos de construcción conservan
su contexto original y no deben sobrescribir ninguna distribución.

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
[recuperación de antecedentes](#recuperación-de-antecedentes).

## 3. Fuentes masivas y replay del motor

Volver a autenticar mercados o reconstruir todo el riesgo intradía exige las
fuentes locales indicadas por sus manifiestos, normalmente `D:/Backtesting`.
Los parámetros `--data-root`, `--series-root` o riesgo `--scope complete`
amplían la verificación y no implican necesariamente un replay económico.
Son controles distintos del nivel compacto.

Repetir carteras requiere además el snapshot económico, configuraciones,
dependencias y contratos exactos de cada bloque, junto con destinos nuevos.
La [guía de reglas](entrega_4/reglas_historicas/reproduccion.md),
la [reproducción B5][b5-limites] y los protocolos del índice E4 conservan los
requisitos y comandos históricos. Los runners pueden escribir estados:
nunca deben apuntar al paquete sellado. Una comprobación offline no equivale
a reproducir el motor. La [guía de datos](descarga_d.md) documenta adquisición
y preparación; el [diccionario](data_dictionary.md), los artefactos generados.

## Pruebas

Desde la raíz, estas pruebas verifican navegación y codificación sin mercados
ni simulaciones. Se usa un temporal nuevo y se evita escribir cachés:

```powershell
$pruebas = Join-Path $env:TEMP ('tesina_tests_' + [guid]::NewGuid().ToString('N'))
& '.\.venv\Scripts\python.exe' -B -X utf8 -m pytest tests/unit/test_documentation.py tests/unit/test_repository_evidence.py -q -p no:cacheprovider --basetemp $pruebas
```

`tests/` conserva además las pruebas del motor y de integridad de paquetes;
algunas necesitan datos o rutas de evidencia indicadas en sus fixtures.


## Control de navegación

```powershell
& '.\.venv\Scripts\python.exe' -B -X utf8 -m scripts.verify_documentation
```

Comprueba codificación y enlaces locales de una lista explícita de documentos
activos. No verifica economía ni todos los documentos históricos o sellados.

## Recuperación de antecedentes

El respaldo completo previo a esta limpieza se conserva en
`../Backtesting_antecedentes/limpieza_final_20261010/originales/`, con inventario
SHA-256 externo y recuperación comprobada. Los paquetes originales mantienen
sus bytes, manifiestos y certificados históricos. Su conservación no constituye
una nueva validación. Las distribuciones actuales incluyen herramientas y fuentes
compactas para su comprobación, con las dependencias explícitas indicadas arriba.
Recuperar originales siempre en destinos nuevos; los constructores históricos
requieren su contexto y herramientas originales. Los antecedentes retirados antes
de este respaldo se recuperan de
`b5bf5909c1793c684a0acd110b6fab2e90718cca` o de los respaldos anteriores
`../Backtesting_antecedentes/segunda_limpieza_20261010/` y
`../Backtesting_antecedentes/limpieza_20261010/bytes_git/`.
Los originales que necesitan documentos internos se recuperan completos desde
esos respaldos. La presentación continua E3, el archivo histórico E3 y los bloques
Riesgo/B1–B6 tienen distribuciones documentales identificadas en sus índices.

[capital-guia]: ../entregas/entrega_4/retorno_capital/20260927T143928Z/distribucion_20261010/README.md
[b5-limites]: ../entregas/entrega_4/estres_contrafactual/20260930T214617Z/distribucion_20261010/reproducibilidad.md

# Reproducción del estudio

| Objetivo | Requisitos | Alcance |
| --- | --- | --- |
| Leer el estudio | PDF, reportes y tablas del repositorio | Consultar resultados y supuestos. |
| Verificar evidencia compacta | Python y dependencias; paquetes incluidos | Comprobar identidad y recalcular los controles declarados por cada tema. |
| Repetir las carteras | Datos de mercado, snapshot, configuración y contrato de cada corrida | Ejecutar de nuevo el motor económico. |

Los comandos parten de la raíz del checkout. Crear salidas nuevas fuera de los
paquetes sellados; no sobrescribir manifiestos ni cambiar hashes para aceptar
divergencias. Los perfiles CLI antiguos `configs/base.toml` y
`configs/robustness.toml` usan `first_trade`: **no son la BASE vigente**.
La referencia continua usa `next_minute_vwap`, `joint_quantity`, señales de minuto
cerrado y `futures_scaled`; mandan las configuraciones efectivas de sus snapshots.

## 1. Lectura, sin ejecutar código

Comenzar por la [tesina](../Tesina_Pablo_Salerno.pdf), la [metodología](methodology.md)
y el [índice de resultados por tema](../results/README.md), que enlaza reportes,
tablas y protocolos.
No requiere Python ni datos de mercado. Los índices de corridas y manifiestos
identifican las fuentes; leerlos no equivale a volver a verificarlas.

## 2. Verificación offline de evidencia compacta

Los verificadores incluidos en las distribuciones no requieren Git ni mercados
masivos. Usan Python 3.14 y las dependencias de [pyproject.toml](../pyproject.toml)
y [uv.lock](../uv.lock). Los ejemplos PowerShell corresponden al entorno de
referencia Windows con Python 3.14.3.

**Portabilidad:** los nueve verificadores originales tienen un pase documentado
en Windows. En Linux pasaron BASE, riesgo, capital y SOFR; los otros cinco
presentaron diferencias en comparaciones exactas de métricas o CSV. La
[evidencia complementaria](../results/complementaria/README.md) conserva el
diagnóstico, las versiones y una capa externa de comparación numérica portable.
Su parche está **incluido para revisión, no aplicado** al motor, las pruebas ni
los paquetes de este checkout. El pase de esa capa no equivale a un pase de los
nueve verificadores originales sin modificar.

### Preparar el entorno y comprobar la distribución

```powershell
uv --cache-dir .uv-cache sync --frozen --python 3.14.3
```

La preparación puede necesitar acceso a paquetes si no están instalados o
en caché; con el entorno/caché disponible se puede añadir `--offline`.
Los verificadores posteriores no requieren red ni `D:/Backtesting`.
No ejecutar `uv sync` dentro de un paquete sellado.

```powershell
& '.\.venv\Scripts\python.exe' -B -X utf8 -m scripts.verify_product
& '.\.venv\Scripts\python.exe' -B -X utf8 -m scripts.verify_documentation
```

El primero comprueba inventarios e identidad del producto; el segundo,
codificación y enlaces de los documentos activos. No recalculan la economía.

### Verificar los nueve temas

Desde la raíz del repositorio, parametrizar ubicación y salida. La matriz
resuelve las rutas vigentes; si se trasladan paquetes, reemplazar sus valores
en `$paquetes` y `$padre`. Elegir siempre una carpeta de auditoría nueva y
externa a todos los paquetes; los JSON/logs son los únicos productos esperados.

```powershell
$repo = (Resolve-Path .).Path
$py = Join-Path $repo '.venv/Scripts/python.exe'
$paquetes = @{}
Import-Csv (Join-Path $repo 'results/matriz_resultados.csv') | ForEach-Object {
    if ($_.paquete_vigente) { $paquetes[$_.id] = Join-Path $repo $_.paquete_vigente }
}
$padre = Join-Path $repo 'data/evidence/reglas_historicas'
$salida = Join-Path $env:TEMP ('tesina_offline_' + (Get-Date -Format 'yyyyMMddTHHmmss'))
if (Test-Path -LiteralPath $salida) { throw 'Elegir una salida nueva' }
New-Item -ItemType Directory -Path $salida | Out-Null
```

Ejecutar cada línea por separado y comprobar código de salida y JSON.
Una respuesta correcta de `--help` no acredita el pase del paquete.

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
Capital, sin dependencias adicionales, comprueba el paquete interno; su
[guía][capital-guia] documenta el modo con padre, corrección, riesgo y la referencia continua.
SOFR recalcula la cuenta hipotética y comprueba la distribución de capital
indicada, conservando por separado la identidad histórica de su dependencia.
Ese control no se presenta como comprobación íntegra del sello original retirado.
Señal, costos/capacidad, ejecución y estrés recomputan
lo declarado en cada guía desde extractos y agregados; no vuelven a leer
toda la historia de mercado. Estabilidad vuelve a calcular también las estadísticas
del bootstrap desde inputs compactos, sin simular carteras. Las herramientas
comparten partes del posprocesamiento; imágenes verificadas por hash y tablas
de origen no equivalen a una inspección visual nueva.

Los manifiestos comprueban bytes e inventario, no autenticidad histórica del
exchange. Los certificados conservan su fecha y alcance original; las
herramientas históricas pueden requerir estados anteriores del repositorio.

### Referencia continua y extracción autenticada

La presentación continua se comprueba desde el ZIP original, sin datos masivos ni
nuevos backtests. Para regenerarla, elegir otra salida externa que no exista:

```powershell
$repo = (Resolve-Path .).Path
$py = Join-Path $repo '.venv/Scripts/python.exe'
& $py -B -X utf8 -m scripts.publish_thesis --verify
$presentacion = Join-Path $env:TEMP ('continua_presentacion_' + (Get-Date -Format 'yyyyMMddTHHmmss'))
if (Test-Path -LiteralPath $presentacion) { throw 'Elegir una salida nueva' }
& $py -B -X utf8 -m scripts.publish_thesis --output $presentacion
```

El paquete continuo tiene miembros directamente en la raíz del ZIP. Autenticarlo
contra su sidecar conservado antes de extraer. No volver a crear checksums:

```powershell
function Expand-AuthenticatedE3([string]$zip, [string]$destination) {
    if (Test-Path -LiteralPath $destination) { throw 'El destino debe ser nuevo' }
    $esperado = ((Get-Content -LiteralPath ($zip + '.sha256') -Raw).Trim() -split '\s+')[0]
    $observado = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
    if ($observado.ToLowerInvariant() -ne $esperado.ToLowerInvariant()) { throw 'SHA-256 divergente' }
    Expand-Archive -LiteralPath $zip -DestinationPath $destination
}
$e3 = Join-Path $env:TEMP ('continua_' + (Get-Date -Format 'yyyyMMddTHHmmss'))
Expand-AuthenticatedE3 (Join-Path $repo 'data/evidence/carteras_continuas.zip') $e3
Push-Location $e3
try { & $py -I -S -B -X utf8 verificar.py } finally { Pop-Location }

$v2 = Join-Path $repo 'data/evidence/ventanas_independientes'
& $py -B -X utf8 "$v2/scripts/verificar_paquete.py"
```

Los verificadores internos comprueban inventario y evidencia. La distribución
de ventanas independientes es un antecedente archivado; su
[LEEME original autenticado](https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/blob/634c88fcf985da742cfa55d83bc4c0f99e082610/data/evidence/ventanas_independientes/LEEME.md) documenta
herramientas, fuentes y límites.

La corrección BASE recibe una ruta de directorio mediante `--e3-reference`,
no el ZIP. Después de la extracción autenticada anterior, el ejemplo editorial
sin replay es:

```powershell
$correccion = Join-Path $env:TEMP ('base_correccion_' + (Get-Date -Format 'yyyyMMddTHHmmss'))
& $py -B -X utf8 scripts/report_historical_rules_sensitivity.py `
  --source-package data/evidence/reglas_historicas `
  --destination $correccion `
  --e3-reference $e3
```

Este comando construye y sella un derivado editorial nuevo; no modifica la
corrección vigente ni las carteras. La
[guía de exposición/H2](reglas_historicas/lectura_resultados.md)
describe su verificación posterior.

## 3. Fuentes masivas y replay del motor

Volver a autenticar mercados o reconstruir todo el riesgo intradía exige las
fuentes locales indicadas por sus manifiestos, normalmente `D:/Backtesting`.
Los parámetros `--data-root`, `--series-root` o riesgo `--scope complete`
amplían la verificación y no implican necesariamente un replay económico.
Son controles distintos del nivel compacto.

Repetir carteras requiere además el snapshot económico, configuraciones,
dependencias y contratos exactos de cada tema, junto con destinos nuevos.
La [guía de reglas](reglas_historicas/reproduccion.md),
la [reproducción de estrés][b5-limites] y los protocolos del índice temático conservan los
requisitos y comandos históricos. Los runners pueden escribir estados:
nunca deben apuntar al paquete sellado. Una comprobación offline no equivale
a reproducir el motor. La [guía de datos](descarga_d.md) documenta adquisición
y preparación; el [diccionario](data_dictionary.md), los artefactos generados.

## Pruebas y procedencia documental

Desde la raíz, estas pruebas verifican navegación y codificación sin mercados
ni simulaciones. Se usa un temporal nuevo y se evita escribir cachés:

```powershell
$pruebas = Join-Path $env:TEMP ('tesina_tests_' + [guid]::NewGuid().ToString('N'))
& '.\.venv\Scripts\python.exe' -B -X utf8 -m pytest tests/unit/test_documentation.py tests/unit/test_repository_evidence.py -q -p no:cacheprovider --basetemp $pruebas
```

`tests/` conserva además las pruebas del motor y de integridad de paquetes;
algunas necesitan datos o rutas de evidencia indicadas en sus fixtures. Una
adaptación de ubicación o un pase de pruebas no acredita una nueva corrida económica.

La [procedencia documental](procedencia/README.md) identifica los PDF finales
proporcionados por el autor y los controles de los archivos publicados.

[capital-guia]: https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/blob/634c88fcf985da742cfa55d83bc4c0f99e082610/results/capital/evidencia/README.md
[b5-limites]: https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/blob/634c88fcf985da742cfa55d83bc4c0f99e082610/results/estres/evidencia/reproducibilidad.md

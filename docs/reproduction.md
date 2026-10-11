# Reproducción del estudio

Usar desde la raíz del checkout. Las configuraciones efectivas y snapshots
congelados, no los perfiles CLI antiguos `configs/base.toml` y
`configs/robustness.toml`, determinan las carteras finales. Los destinos nuevos
se crean fuera de los paquetes sellados. No sobrescribir manifiestos ni cambiar
hashes para aceptar divergencias.


## 1. Lectura, sin ejecutar código

Abrir los reportes Markdown/HTML, tablas CSV y protocolos del [índice de resultados por tema](../results/README.md).
No requiere Python ni datos de mercado. Los índices de corridas y manifiestos
identifican las fuentes; leerlos no equivale a volver a verificarlas.

## 2. Verificación offline de evidencia compacta

Los comandos siguientes usan los verificadores incluidos en las distribuciones
vigentes. Comprueban la identidad de cada distribución y conservan los controles
científicos de sus fuentes; no requieren Git.
Requieren Python 3.14 y las dependencias de [pyproject.toml](../pyproject.toml)
y [uv.lock](../uv.lock); el entorno local de referencia usa Python 3.14.3
en Windows.

**Verificación local del 11/10/2026:** se ejecutaron completos los nueve
comandos de esta sección en Windows 11 nativo (`sys.platform=win32`), con
CPython 3.14.3 de 64 bits y las versiones de `uv.lock`. BASE, riesgo intradía,
capital, SOFR, señal, costos/capacidad, ejecución, estrés y estabilidad e
incertidumbre terminaron cada uno con código 0 y JSON final positivo
(`status: passed` o `passed: true`). La preparación con
`uv sync --frozen --python 3.14.3` encontró acceso denegado a la caché global; el comando con
la caché local indicado abajo terminó con código 0, sin modificar el lock.
Las versiones efectivas, rutas resueltas desde la matriz, comandos, JSON,
stdout, stderr y códigos de salida quedaron en la carpeta externa
`%TEMP%/tesina_revision_windows_20261011_7c6770a0/`. No se ejecutaron nuevos
backtests ni se descargaron mercados. Este pase corresponde a los alcances
compactos descritos abajo y no acredita la revisión del whitepaper ni del
executive briefing externos.

**Antecedente externo en Linux, aportado para esta revisión:** con Python
3.14.3 y dependencias del lock pasaron BASE, riesgo, capital y SOFR. Señal,
costos/capacidad, ejecución y estrés fallaron en comparaciones exactas de
métricas. En los cuatro se identificó, para BASE_E3 condicional de 2024, un
CAGR publicado de `0.0522270351463172` frente al recalculado
`0.05222703514631721`; ambos se muestran como `5,2227 %`. Estabilidad falló
en la comparación literal de `bootstrap_intervalos.csv`, con diferencias de
últimos decimales de hasta `6.938893903907228e-18`; sus controles numéricos
pasaron en aquella comprobación. Estos ejemplos no delimitan todas las
divergencias posibles ni acreditan un PASS integral en Linux. Esta revisión
no repitió la auditoría Linux y conserva las comparaciones exactas, las
tolerancias, las cifras y los sellos existentes.

Preparar el entorno desde la raíz del checkout, antes de la verificación:

```powershell
uv --cache-dir .uv-cache sync --frozen --python 3.14.3
```

La preparación puede necesitar acceso a paquetes si no están instalados o
en caché; con el entorno/caché disponible se puede añadir `--offline`.
Los verificadores posteriores no requieren red ni `D:/Backtesting`.
No ejecutar `uv sync` dentro de un paquete sellado. Sus copias de código/lock
fijan la procedencia; el entorno reutilizado queda fuera de las evidencias.

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

Los manifiestos comprueban bytes y pertenencia al inventario, no autenticidad
histórica del exchange. Los sellos y sus sidecars nunca se renuevan para
hacer pasar una divergencia. Las herramientas históricas conservadas en los
snapshots pueden exigir estados antiguos del repositorio; los verificadores
por paquete de arriba fijan el alcance actual de la comprobación compacta.

## Referencia continua y extracción autenticada

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

Comprobar los códigos de salida; SHA-256 autentica el ZIP continuo preservado y
los verificadores internos comprueban inventario/evidencia. La distribución
de ventanas independientes se comprueba directamente, sin extraer los ZIP retirados. Su
[LEEME original autenticado](../data/evidence/ventanas_independientes/LEEME.md) documenta
herramientas, fuentes y límites. Los scripts históricos de construcción conservan
su contexto original y no deben sobrescribir ninguna distribución.

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
describe su verificación posterior. Los paquetes y sus dependencias compactas se encuentran en este repositorio;
los ejemplos utilizan las rutas temáticas actuales.

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

## Procedencia y dependencias

Las evidencias temáticas incluyen sus datos compactos, herramientas, fuentes y
manifiestos de procedencia. BASE requiere el padre completo en
`data/evidence/reglas_historicas`; riesgo requiere ese padre y la corrección
`results/base/evidencia`; SOFR requiere `results/capital/evidencia`.
La referencia continua se conserva en `data/evidence/carteras_continuas.zip`
y las ventanas independientes en `data/evidence/ventanas_independientes`.
La comprobación compacta no requiere respaldos privados ni rutas archivadas.
Los certificados originales conservan su fecha y alcance histórico; una
adaptación de ubicación no acredita una nueva ejecución económica.

Comprobar navegación, distribución del producto y sus dependencias:

```powershell
python -B -X utf8 -m scripts.verify_product
python -B -X utf8 -m scripts.verify_documentation
```

La [procedencia documental](procedencia/README.md) identifica la fuente editable
utilizada para exportar el PDF y distingue las versiones de consulta disponibles.

[capital-guia]: ../results/capital/README.md
[b5-limites]: ../results/estres/evidencia/reproducibilidad.md

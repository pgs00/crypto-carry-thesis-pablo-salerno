# Descarga vigente: dos ventanas por minuto en D:

BTCUSDT y ETHUSDT, spot y perpetuos USD-M:
01/09/2022–31/08/2023 y 01/09/2025–31/08/2026, con agosto previo como
calentamiento. Se usan archivos y consultas públicas de Binance, sin API key.

## Ejecutar o reanudar en PowerShell

Ejecutar una sola copia. Si ya está descargando, dejarla continuar.

```powershell
Set-Location 'C:\Users\pablo\Documentos\UCEMA\Tesina\Backtesting'
$configsMinuto = @('.\configs\download_minutes_2022_2023_d.toml', '.\configs\download_minutes_2025_2026_d.toml')
& '.\.venv\Scripts\python.exe' -u -m crypto_carry.data.minute_download --root 'D:\Backtesting' --config $configsMinuto
```

El comando es el mismo que antes de la limpieza del proyecto. Guarda los datos
en `D:\Backtesting\data\minutes\2022_2023` y
`D:\Backtesting\data\minutes\2025_2026`. El límite de **20 GB es compartido**
por ambas carpetas e incluye crudos, temporales y manifiestos.

## Contenido y tamaño

| Dataset | ZIP mensuales, ambas ventanas y activos |
|---|---:|
| Velas de un minuto de spot y futuros | 104 |
| Mark price de un minuto | 52 |
| Calendarios de funding | 52 |
| Total | **208** |

Se agregan cuatro respuestas de funding de la API pública y los checksums de
los ZIP. El funding se consulta desde 30 días antes de cada inicio, para permitir
28 días de calentamiento más antecedentes. Ese mes extra no cambia las fechas
de evaluación económica.

Verificación del 18/09/2026: 208/208 ZIP mensuales descargados, **257.252.762 bytes
(257,25 MB)** comprimidos. Los seis suplementos diarios de mark suman otros
206.818 bytes. Las dos ventanas completas, incluyendo API, checksums, Parquet
y manifiestos de cobertura, ocupan aproximadamente **643 MB**.
[Registro de preparación](../data/research/minute-download-20260918/preparation.json).

La revisión del 19/09/2026 recuperó OHLC y ambos volúmenes de los ZIP existentes,
sin descargas adicionales. Agregó 104 particiones compartidas de `minute_bars`,
con **260.960.966 bytes** de Parquet. Las dos carpetas, incluidos originales,
formatos de referencia y manifiestos conservados, ocupan **956.984.856 bytes**
(956,98 MB decimales) en la medición posterior a la migración.

## Progreso, finalización e interrupciones

La consola muestra el porcentaje de **archivos/respuestas verificados**:
`[53/212] 25.00% verificado`. No es porcentaje de bytes ni tiempo restante.
`cached` significa que un archivo existente pasó sus comprobaciones.

Terminó correctamente al aparecer:

```text
DESCARGA COMPLETA: 212/212 (100%). Integridad verificada; cobertura y normalizacion pendientes.
```

Si aparece `DESCARGA INCOMPLETA`, revisar los errores y repetir el mismo comando.
Con `Ctrl+C` puede interrumpirse; reanuda parciales cuando el servidor admite
HTTP Range y verifica los completos mediante SHA-256 y CRC antes de reutilizarlos.

Los manifiestos `manifests\download.json` de ambas carpetas se actualizan durante
la descarga. No extraer los ZIP ni convertirlos manualmente. Mantener el equipo
sin suspensión.

## Después de descargar

La descarga y la validación de ambas ventanas ya terminaron en este equipo.
Los siguientes comandos permiten reproducirlas en una instalación nueva.
El motor por minuto usa los mismos TOML. Antes de ejecutar, incorporar los seis
ZIP diarios de mark que completan omisiones de los mensuales y validar:

```powershell
& '.\.venv\Scripts\python.exe' -u '.\data\research\minute-download-20260918\repair_sources.py' --root 'D:\Backtesting'
if ($LASTEXITCODE -ne 0) { throw 'Falló la recuperación de fuentes diarias' }
foreach ($perfilMinuto in $configsMinuto) {
    $rutaPerfilMinuto = (Resolve-Path $perfilMinuto).Path
    & '.\.venv\Scripts\python.exe' -u -m crypto_carry --root 'D:\Backtesting' validate-data --config $rutaPerfilMinuto --scope full
    if ($LASTEXITCODE -ne 0) { throw 'La cobertura todavía no está validada' }
}
```

La recuperación conserva los ZIP mensuales originales y verifica los diarios
contra sus checksums oficiales. La suspensión spot del 24/03/2023 se documenta
como período sin negociación; no se inventan precios ni volúmenes.
El [protocolo vigente](escenario_investigacion.md) declara estas convenciones.

## Reproducir las corridas

Para la revisión vigente, que incluye el escenario principal `vwap_joint` y
los controles sobre ambas ventanas:

```powershell
& '.\.venv\Scripts\python.exe' -u -m crypto_carry --root 'D:\Backtesting' execution-revision `
  --early-config (Resolve-Path '.\configs\download_minutes_2022_2023_d.toml').Path `
  --late-config (Resolve-Path '.\configs\download_minutes_2025_2026_d.toml').Path
```

La preparación anterior con `validate-data` recupera las barras completas desde
la caché. La revisión valida cada política de datos antes de simular y escribe
`outputs/revision_<id>/execution_revision_report.md`.

### Corridas individuales del modelo de referencia

Desde la raíz del proyecto, ejecutar ambas carteras de cada ventana:

```powershell
$configsMinuto = @('.\configs\download_minutes_2022_2023_d.toml', '.\configs\download_minutes_2025_2026_d.toml')
foreach ($perfilMinuto in $configsMinuto) {
    $rutaPerfilMinuto = (Resolve-Path $perfilMinuto).Path
    & '.\.venv\Scripts\python.exe' -u -m crypto_carry --root 'D:\Backtesting' backtest --config $rutaPerfilMinuto
    if ($LASTEXITCODE -ne 0) { throw 'Falló una corrida anual; revisar el error' }
}
```

Cada ventana base tardó entre cuatro y seis minutos en este equipo, incluyendo
validación e informes. La consola devuelve su carpeta `outputs\run_<id>` al
terminar. Los resultados existentes se verifican antes de reutilizarlos.

Para repetir los siete escenarios priorizados, con las mismas configuraciones:

```powershell
foreach ($perfilMinuto in $configsMinuto) {
    $rutaPerfilMinuto = (Resolve-Path $perfilMinuto).Path
    & '.\.venv\Scripts\python.exe' -u -m crypto_carry --root 'D:\Backtesting' robustness --config $rutaPerfilMinuto --scenario cost-2 --scenario cost-3 --scenario futures-fee-0p0004 --scenario funding-proxy-plus-10 --scenario funding-proxy-minus-10 --scenario maintenance-2 --scenario liquidation-fee-0p03
    if ($LASTEXITCODE -ne 0) { throw 'Falló un conjunto de sensibilidades; revisar el error' }
}
```

Este segundo comando vuelve a ejecutar el baseline y luego cada escenario;
imprime un avance por escenario terminado. Mantiene resultados separados y
guarda el índice en `outputs\robustness-<id>`. Las tablas, figuras y auditorías
vigentes se identifican en [avance y evidencia](progress.md).

Para reconstruir el informe conjunto de las corridas verificadas actuales:

```powershell
& '.\.venv\Scripts\python.exe' '.\data\research\minute-download-20260918\build_study_report.py' --root 'D:\Backtesting' --early run_8fb22fa8b377466cff981b99 --late run_0cb21afbec7cdba1e5848df6 --early-robustness robustness-25034b88ecfa92b9 --late-robustness robustness-c252528c4dd8d7a3
```

Verifica fuentes de resultados, auditorías e índices antes de guardar el estudio.
Si se cambian datos, parámetros o código, usar los nuevos identificadores que
devuelva la ejecución correspondiente; el comparador exige el perfil aprobado
y una auditoría que corresponda a los baselines seleccionados.

La carpeta antigua `D:\Backtesting\data\raw` ya fue eliminada por el usuario.
Conservar `D:\Backtesting\data\minutes` y el `data` del proyecto en C:, que
contiene la muestra, el funding y las auditorías.

Fuente: [Binance Public Data](https://github.com/binance/binance-public-data).
Los timestamps de spot desde enero de 2025 vienen en microsegundos; el
normalizador respeta la unidad registrada en cada manifiesto.

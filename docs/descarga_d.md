# Adquisición y preparación de datos

Estudio vigente: BTCUSDT y ETHUSDT, spot y perpetuos USD-M, **01/01/2022–31/08/2026
UTC**, con diciembre de 2021 como calentamiento. Se usan fuentes públicas de
Binance. Las instrucciones de las ventanas independientes se conservan más
abajo como antecedentes. Para leer o reproducir las tablas publicadas no hace
falta descargar datos: ver la [guía principal](reproduction.md).
Los ejemplos PowerShell parten de la raíz del repositorio y usan
`D:\Backtesting` como destino de mercados; adaptar esa ruta a la instalación.
Ejecutar una sola descarga por destino y mantener las salidas fuera de los paquetes sellados.

## Ampliación continua: enero de 2022 a agosto de 2026

Para ejecutar ambas carteras con los dos tratamientos explícitos de los 15
marks faltantes, seguir [la guía de cartera continua](continuous_mark_gaps.md).
Los pasos de adquisición siguientes se conservan para reproducir la preparación.

```powershell
& '.\.venv\Scripts\python.exe' -u '.\scripts\download_continuous.py' --root 'D:\Backtesting'
```

Usa [el perfil continuo](../configs/download_minutes_2022_2026_d.toml) y guarda
los crudos en `D:\Backtesting\data\minutes\2022_2026_continuous`. Incluye
diciembre de 2021 para calentamiento. El límite compartido sigue siendo 20 GB.
Este comando adquiere datos; la normalización, la validación de cobertura y las
corridas del período ampliado son pasos posteriores.

El plan comprende **456 ZIP mensuales y dos consultas paginadas de funding**.
Con las dos ventanas archivadas presentes, reutiliza **208 ZIP** y sus seis
suplementos diarios de mark, después de verificar SHA-256 y CRC. Hace copias
independientes en el destino nuevo y conserva intactas las fuentes anuales.
No copia los Parquet anuales ni concatena sus snapshots de la API: consulta
el funding para todo el intervalo nuevo. `--plan-only` muestra el plan sin
descargar ni escribir datos. No requiere API key.

El progreso cuenta archivos y respuestas verificados, no bytes ni tiempo
restante; `cached` indica reutilización verificada. La finalización continua
es `DESCARGA COMPLETA: 458/458 (100%)`; todavía falta normalizar y validar
cobertura. Si se interrumpe o informa `DESCARGA INCOMPLETA`, repetir el mismo
comando: conserva los completos y reanuda parciales cuando hay soporte HTTP Range.

### Procesar y validar el período continuo

La descarga completa verifica los archivos, pero no garantiza que Binance haya
publicado todas las observaciones. La revisión del período ampliado encontró
un día de mark BTC recuperable desde el diario oficial (31/07/2022) y 15 minutos
ausentes también de los diarios y de la API. El procedimiento reproducible es:

```powershell
& '.\.venv\Scripts\python.exe' -u '.\data\research\continuous-preparation-20260919\repair_sources.py' --root 'D:\Backtesting'
$configContinuo = (Resolve-Path '.\configs\download_minutes_2022_2026_d.toml').Path
& '.\.venv\Scripts\python.exe' -u -m crypto_carry --root 'D:\Backtesting' validate-data --config $configContinuo --scope full --clip-price-warmup
```

El primer comando conserva los originales, adjunta únicamente observaciones
oficiales recuperadas y registra las consultas sin resultado. Devuelve código 2
si quedan huecos. El segundo convierte los crudos a Parquet y valida la cobertura
completa; también devuelve código 2 si faltan datos. No ejecuta backtests.
La conversión puede tardar varios minutos sin imprimir progreso.

`--clip-price-warmup` conserva los precios desde el antecedente cerrado y el
historial de volumen que necesita el modelo (31/12/2021 23:59 UTC con el perfil
actual). Evita que dos velas irregulares del 24/12/2021, fuera del período usado,
impidan importar los antecedentes válidos. Registra el alcance y las filas
excluidas; mantiene completos el calentamiento de funding y los marks. La
validación dentro del período utilizado conserva sus exigencias. La opción
es explícita: las reproducciones anuales anteriores mantienen su comportamiento.

Los informes quedan en la carpeta `manifests` del destino continuo:
`processed.json`, `coverage.json`, `data_coverage.csv` y `data_quality_report.md`.
Para repetir solamente la validación, agregar `--skip-normalize` al segundo
comando. Un estado `incomplete_data` impide iniciar el backtest; los minutos
ausentes no se rellenan ni se reclasifican como cierres del mercado.
La investigación y sus fuentes se conservan en
[preparación continua](../data/research/continuous-preparation-20260919/README.md).

## Antecedente archivado: dos ventanas independientes

Las ventanas septiembre de 2022–agosto de 2023 y septiembre de 2025–agosto de
2026 reinician capital por separado. Los comandos de esta sección reproducen
ese antecedente, no la BASE continua. Su [paquete conservado](../data/evidence/ventanas_independientes/LEEME.md)
identifica resultados, configuraciones y procedencia.

### Descargar y validar

```powershell
$configsMinuto = @('.\configs\download_minutes_2022_2023_d.toml', '.\configs\download_minutes_2025_2026_d.toml')
& '.\.venv\Scripts\python.exe' -u -m crypto_carry.data.minute_download --root 'D:\Backtesting' --config $configsMinuto
```

Guarda los datos en `D:\Backtesting\data\minutes\2022_2023` y
`D:\Backtesting\data\minutes\2025_2026`. El límite de **20 GB es compartido**
por ambas carpetas e incluye crudos, temporales y manifiestos.

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

El [registro de preparación](../data/research/minute-download-20260918/preparation.json)
conserva las mediciones de descarga. La finalización es
`DESCARGA COMPLETA: 212/212 (100%)`; se aplican las mismas reglas de reanudación
y verificación anteriores. Los manifiestos `manifests\download.json` se
actualizan durante la descarga. No extraer ni convertir los ZIP manualmente.

Antes de simular, incorporar los seis ZIP diarios de mark que completan
omisiones de los mensuales y validar con los mismos TOML:

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
El [protocolo del antecedente](escenario_investigacion.md) declara estas convenciones;
la [metodología vigente](methodology.md) corresponde a la trayectoria continua.

### Reproducir las corridas archivadas

Para la revisión por minuto archivada, que incluye el escenario `vwap_joint` y
los controles sobre ambas ventanas:

```powershell
& '.\.venv\Scripts\python.exe' -u -m crypto_carry --root 'D:\Backtesting' execution-revision `
  --early-config (Resolve-Path '.\configs\download_minutes_2022_2023_d.toml').Path `
  --late-config (Resolve-Path '.\configs\download_minutes_2025_2026_d.toml').Path
```

La preparación anterior con `validate-data` recupera las barras completas desde
la caché. La revisión valida cada política de datos antes de simular y escribe
`outputs/revision_<id>/execution_revision_report.md`.

### Corridas individuales y sensibilidades del antecedente

Desde la raíz del proyecto, ejecutar ambas carteras de cada ventana:

```powershell
$configsMinuto = @('.\configs\download_minutes_2022_2023_d.toml', '.\configs\download_minutes_2025_2026_d.toml')
foreach ($perfilMinuto in $configsMinuto) {
    $rutaPerfilMinuto = (Resolve-Path $perfilMinuto).Path
    & '.\.venv\Scripts\python.exe' -u -m crypto_carry --root 'D:\Backtesting' backtest --config $rutaPerfilMinuto
    if ($LASTEXITCODE -ne 0) { throw 'Falló una corrida anual; revisar el error' }
}
```

La consola devuelve `outputs\run_<id>` al terminar. Los resultados existentes
se verifican antes de reutilizarlos.

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
guarda el índice en `outputs\robustness-<id>`.

Para reconstruir el informe conjunto de las corridas archivadas identificadas:

```powershell
& '.\.venv\Scripts\python.exe' '.\data\research\minute-download-20260918\build_study_report.py' --root 'D:\Backtesting' --early run_8fb22fa8b377466cff981b99 --late run_0cb21afbec7cdba1e5848df6 --early-robustness robustness-25034b88ecfa92b9 --late-robustness robustness-c252528c4dd8d7a3
```

Verifica fuentes de resultados, auditorías e índices antes de guardar el estudio.
Si se cambian datos, parámetros o código, usar los nuevos identificadores que
devuelva la ejecución correspondiente; el comparador exige el perfil aprobado
y una auditoría que corresponda a los baselines seleccionados.

Fuente: [Binance Public Data](https://github.com/binance/binance-public-data).
Los timestamps de spot desde enero de 2025 vienen en microsegundos; el
normalizador respeta la unidad registrada en cada manifiesto.

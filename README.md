# Crypto carry: backtesting reproducible

Comparación de carry con filtro de funding y carry permanente en BTCUSDT y
ETHUSDT, spot y perpetuos USD-M. NautilusTrader 1.231.0 gestiona el replay y las
órdenes; un ledger Decimal registra y concilia la economía de ambas carteras.

## Alcance vigente

La extensión actual agrega una **cartera continua del 01/01/2022 al
31/08/2026 UTC**, sin reinicios anuales, con sensibilidad explícita para los
15 marks ausentes. Conserva los parámetros del modelo por minuto y la
aproximación de funding vigente. Ver [métodos, evidencia y reproducción](docs/continuous_mark_gaps.md).
La validación estricta continúa siendo el valor predeterminado.

Las cuatro corridas continuas ya están ejecutadas y verificadas. El
[reporte de resultados y sensibilidad](data/research/continuous-marks-20260919/README.md)
incluye posiciones durante los huecos, controles de margen y evidencia compacta
que se puede comprobar sin descargar los datos masivos.

Las siguientes ventanas independientes y su paquete de entrega se conservan
como resultados anteriores:

| Ventana independiente | Inicio UTC incluido | Fin UTC excluido |
|---|---|---|
| 2022–2023 | 01/09/2022 | 01/09/2023 |
| 2025–2026 | 01/09/2025 | 01/09/2026 |

Cada estrategia comienza con 10.000 USDT en cada ventana. La
[especificación vigente](docs/sources/Prompt_Codex_Ajuste_Backtesting_1m.md)
fija ejecución `next_minute_vwap` y sizing `joint_quantity` como escenario
principal. Se reutilizan velas de un minuto, funding y marks; las investigaciones
anteriores con trades no son una dependencia de esta revisión.

El modelo registra fills al final de la ventana, limita la participación al
1% de su volumen base y conserva parciales, remanentes y desarmes. Calcula
ambas cantidades antes de comprar y mantiene los filtros económicos anteriores.
Las aproximaciones históricas de funding y reglas continúan explícitas en la
[metodología](docs/methodology.md). Los resultados y verificaciones están en
[avance y evidencia](docs/progress.md).

## Empezar

1. Leer el [paquete vigente de la Entrega 3](entregas/entrega_3/paquete_redaccion/LEEME.md)
   o descargar su [ZIP revisado](entregas/entrega_3/paquete_redaccion_entrega_3_v2.zip).
2. Consultar el [informe corregido](entregas/entrega_3/paquete_redaccion/evidencia/execution_revision_report.md)
   y la [auditoría del basis](entregas/entrega_3/paquete_redaccion/evidencia/basis_audit_report.md).
3. Reproducir las tablas y figuras con el subconjunto incluido, siguiendo el bloque siguiente.
4. La [guía de descarga local](docs/descarga_d.md) y los
   [comandos de auditoría completa](docs/escenario_investigacion.md) sólo hacen falta
   para reconstruir datos o contrastar las fuentes de mercado locales.

## Reproducir tablas y figuras

Desde la raíz del repositorio, con el entorno instalado como se indica en
[Entorno y pruebas](#entorno-y-pruebas):

```powershell
& '.\.venv\Scripts\python.exe' entregas/entrega_3/paquete_redaccion/scripts/verificar_paquete.py
& '.\.venv\Scripts\python.exe' entregas/entrega_3/paquete_redaccion/scripts/reproducir.py --destino '.\.superpowers\entrega3\reproduccion'
& '.\.venv\Scripts\python.exe' entregas/entrega_3/paquete_redaccion/scripts/diccionario.py --destino '.\.superpowers\entrega3\reproduccion'
```

Estos comandos no requieren el disco D, acceso a Binance ni una nueva simulación.
Las salidas regeneradas quedan en una carpeta excluida de Git. El paquete conserva
los resultados verificados de `vwap_joint`, sus configuraciones y hashes originales.
Para usar sólo el ZIP, seguir su [LEEME](entregas/entrega_3/paquete_redaccion/LEEME.md).

`.gitattributes` conserva los bytes del paquete, incluidos los saltos CRLF/LF;
no se normalizan las fuentes para hacer coincidir sus hashes. El
[ZIP original verificado](entregas/entrega_3/paquete_redaccion_entrega_3.zip)
se conserva como referencia histórica; la revisión vigente es `v2`.

## Repetir la comparación anual con datos locales

Los TOML `download_minutes_*` conservan la configuración de la referencia
`minute_open`. La comparación deriva de ellos los escenarios nuevos y valida
la cobertura antes del replay. Los ZIP se leen sin extraerlos, y las barras
completas se comparten entre escenarios.

Desde esta carpeta, con los datos preparados en `D:\Backtesting`:

```powershell
& '.\.venv\Scripts\python.exe' -u -m crypto_carry --root 'D:\Backtesting' execution-revision `
  --early-config (Resolve-Path '.\configs\download_minutes_2022_2023_d.toml').Path `
  --late-config (Resolve-Path '.\configs\download_minutes_2025_2026_d.toml').Path
```

El comando conserva y verifica las referencias anteriores, ejecuta las variantes
pendientes y reutiliza resultados que coincidan en configuración, código y datos.
Puede volver a simular escenarios; no es el comando para reproducir las tablas del paquete.
La salida principal es `outputs/revision_<id>/execution_revision_report.md`.
Compara `legacy_reference`, `joint_sizing_only`, `vwap_only` y `vwap_joint`, más
el control `alignment_only` que identifica por separado la alineación de precios.
Cada corrida guarda configuración efectiva, hashes, órdenes, fills, ledger,
señales y riesgo. Los diagnósticos distinguen causas simultáneas, secuencia de
filtros y datos no evaluables; los resultados de las ventanas no se concatenan.

La comparación ya ejecutada está en el
[informe vigente publicado](entregas/entrega_3/paquete_redaccion/evidencia/execution_revision_report.md).
Para verificar y regenerar ese informe desde las mismas corridas guardadas:

```powershell
& '.\.venv\Scripts\python.exe' -m crypto_carry --root 'D:\Backtesting' report --run-id revision_eb5ed744b30836a39fd694fa
```

Una nueva versión del generador produce un informe con identidad propia y
conserva la versión de código y los saldos originales de cada simulación.
La [auditoría separada del motor](data/research/minute-download-20260918/verify_execution_revision.py)
reconstruye caja, inventario y funding y comprueba los VWAP contra los ZIP:

```powershell
& '.\.venv\Scripts\python.exe' '.\data\research\minute-download-20260918\verify_execution_revision.py' `
  --revision 'D:\Backtesting\outputs\revision_dcf7d66e69aaf51cea4590ff' `
  --output '.\data\research\minute-download-20260918\execution-revision-audit.json'
```

La [auditoría independiente del basis](data/research/basis-audit-20260919/README.md)
contrastó 4.380 observaciones únicas con 96 ZIP originales y reconcilió 8.760
decisiones. Confirmó precios, tiempos y basis; corrigió únicamente el reporte
que contaba funding omitido como rechazo de la permanente. Conservó las corridas,
sus saldos y el informe anterior. Incluye una muestra determinista de 80 filas
y el comando para reproducir todos los contrastes.

## Entorno y pruebas

Python 3.14 y `uv`, desde la raíz del proyecto:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
uv sync --frozen
uv run pytest -q
uv run python -m crypto_carry demo
```

La demo es sintética y valida el motor de referencia. Las pruebas específicas
de la revisión cubren ventanas causales, volumen, parciales, sizing, funding,
riesgo, cortes y conciliación. No usan red ni trades descargados.

## Organización

- `src/crypto_carry/`: motor, contabilidad, datos, evaluación e informes.
- `configs/download_minutes_*.toml`: descarga y ejecución de las dos ventanas en D:.
- `configs/base.toml`, `research.toml`, `robustness.toml`: configuración y
  controles del motor existente, mantenidos para pruebas y comparación.
- `data/raw/`, `data/processed/` y `data/manifests/` en C: conservan la muestra.
- `data/research/` y [auditorías](docs/research/README.md): fuentes, hashes,
  calibraciones y evidencia que respaldan los supuestos.
- `outputs/<run_id>/`: artefactos completos locales, excluidos de GitHub.
  `report --run-id <id>` verifica y regenera sus informes con los datos locales.
- `entregas/entrega_3/`: subconjunto publicado, ZIP original y ZIP revisado;
  permite leer y reproducir tablas/figuras sin publicar los datasets masivos.

La [metodología del motor](docs/methodology.md), las
[decisiones](docs/decisions.md), el [diccionario de datos](docs/data_dictionary.md)
y la [trazabilidad](docs/requirements_traceability.md) detallan los contratos.
La [fiabilidad](docs/fiabilidad.md) recoge los límites para interpretar el estudio.
La especificación original se conserva en `docs/sources/`; las decisiones
posteriores del usuario fijan el alcance vigente.

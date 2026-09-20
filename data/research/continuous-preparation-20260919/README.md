# Preparación del historial continuo por minuto

**Procesamiento terminado; backtest continuo pendiente por cobertura de mark.**
Se generaron y verificaron **800 particiones Parquet**, sin errores de
normalización. El destino continuo ocupa **1,97 GB** incluyendo fuentes,
versiones e informes; todas las carpetas de minutos suman **2,93 GB** del
presupuesto compartido de 20 GB.

Las velas spot/futuros y el funding tienen cobertura completa para el modelo
actual. La validación global devuelve `incomplete_data` exclusivamente por
**15 observaciones de mark ausentes**. No se habilitó ni se ejecutó una corrida
económica con esos huecos. Su tratamiento exige una convención adicional
explícita, distinta de la aproximación de funding ya aprobada.

[Resumen verificable del procesamiento](preparation.json) ·
[Informe final del validador](data_quality_report.md) ·
[Verificación de los 800 Parquet y comparación con la primera pasada](processed_verification.json).
La comparación verificó los hashes de los 800 archivos y confirmó que 788
coinciden con la primera pasada: permanecen iguales los datos del período
económico, todo el funding y todos los marks. Las 12 particiones restantes
aportan los antecedentes de precios seleccionados para diciembre de 2021.
Pasaron 428 pruebas y Ruff sobre el código revisado. No se repitieron backtests
anuales ni se cambiaron las reglas del motor financiero o sus parámetros.

Período económico: **01/01/2022–31/08/2026 UTC**, BTCUSDT y ETHUSDT,
spot y perpetuos USD-M. Se incluye diciembre de 2021 como antecedente.
Los crudos y Parquet permanecen en
`D:\Backtesting\data\minutes\2022_2026_continuous`, fuera de Git.

La adquisición terminó con 456 ZIP mensuales y dos snapshots paginados de
funding. Los seis suplementos diarios que ya respaldaban las ventanas anuales
se conservaron. Esta ampliación mantiene `next_minute_vwap`, sizing conjunto,
señales con velas cerradas y los parámetros económicos del perfil actual.

## Recuperación de observaciones y huecos pendientes

El mensual de mark BTC de julio de 2022 omite el 31/07 completo. El diario
oficial contiene sus **1.440 velas** y permite recuperarlas mediante el mecanismo
de suplementos existente. El mensual original no se modifica. El manifiesto
anterior se conserva como `manifests/download_before_repair_<hash>.json`.

Permanecen **15 observaciones de un minuto** ausentes de las fuentes oficiales consultadas:

| Activo | Fecha UTC | Aperturas de vela UTC ausentes | Minutos |
|---|---|---|---:|
| ETHUSDT | 12/07/2022 | 12:57; 13:07; 13:15 a 13:21; 13:52 | 10 |
| ETHUSDT | 13/07/2022 | 06:59 | 1 |
| BTCUSDT | 12/08/2024 | 10:02 y 10:03 | 2 |
| ETHUSDT | 12/08/2024 | 10:02 y 10:03 | 2 |

Son 13 observaciones de ETH y dos de BTC, correspondientes a 13 timestamps
distintos. Se contrastaron los mensuales, los diarios y la
[API oficial de mark klines](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Mark-Price-Kline-Candlestick-Data).
Las cuatro consultas acotadas a los huecos respondieron HTTP 200, pero no
devolvieron las observaciones faltantes. Los diarios que tampoco recuperan
filas se conservan como evidencia local; no se adjuntan como reparaciones.

Los timestamps de la tabla son aperturas de vela. La valoración utiliza el
mark cerrado disponible al minuto siguiente. Estos huecos no se han declarado
como cierres de mercado, ni se interpolaron precios. La validación estricta de
cobertura por minuto sigue siendo necesaria antes de iniciar una corrida.

Esto es distinto de los 2.005 marks de cobro de funding ausentes por activo:
para esos cobros ya existe la aproximación aprobada con el cierre de mark
inmediatamente anterior. Las tasas y fechas de 5.112 cobros por activo se
contrastaron con sus calendarios; 3.107 eventos por activo contienen mark exacto.
La recuperación de este día y los 15 huecos no cambian esa convención.

La interrupción spot del 24/03/2023 mantiene el tratamiento documentado del
estudio. Sus 80 minutos sin filas por activo están dentro del cierre conocido;
no se crean velas de negociación para rellenarlos.

## Alcance de los precios de calentamiento

La importación inicial detectó una vela irregular spot por activo, el
24/12/2021 a las 04:59 UTC: cierra a las 04:59:54.362 para BTC y
04:59:56.158 para ETH. Los diarios y la API también publican esos cierres
anticipados. Además, el diario/API de BTC contiene dos trades más que el
mensual para esa vela. No se corrige ni se combina esta observación.

Esa fecha es anterior al tramo de precios utilizado por el estudio. La opción
explícita `--clip-price-warmup` importa precios y volúmenes desde el antecedente
cerrado y el lookback de participación, redondeado hacia abajo a minutos. Con
los parámetros actuales comienza el **31/12/2021 a las 23:59 UTC**. El funding
y los marks conservan todo su calentamiento. La importación por defecto de
las ventanas anteriores permanece igual.

El manifiesto procesado registra `normalization_scope`, `source_scope_start`
y `excluded_before_start`. Es una selección temporal de las observaciones
utilizadas, no una validación de las filas excluidas. Las comprobaciones
estrictas de OHLC, volumen y timestamps siguen aplicándose desde el antecedente
necesario y durante todo el período económico.

El primer manifiesto procesado y su informe de errores se conservan en
`manifests/before_price_scope_5204a1773377a9c8`. Las pruebas verifican que un
cierre irregular en el antecedente requerido sigue rechazándose y que se
respeta un lookback de participación mayor a un minuto.

## Evidencia conservada

- [Auditoría de fuentes diarias y respuestas de la API](source_repair_audit.json):
  URLs, fechas, hashes, recuentos recuperados y respuestas de las cuatro consultas.
- [Inspección de grillas antes de esta reparación](source_grid_before_repair.json):
  342 mensuales de velas y mark, incluyendo los seis suplementos anteriores.
  Es anterior a incorporar el séptimo suplemento de BTC.
- [Quince observaciones todavía ausentes](unresolved_mark_minutes.csv).
- [Contraste de la vela spot de calentamiento con diarios y API](spot_warmup_probe.json).
- [Verificación de los antecedentes spot efectivamente importados](antecedent_verification.json):
  OHLC, volúmenes y cantidad de trades coinciden con las filas originales;
  ambas velas cerradas pasan la validación al inicio de 2022.
- [Verificación de fuentes originales](original_sources_verification.json):
  los 458 hashes se comprobaron contra los archivos locales; el único cambio
  de entrada del manifiesto consiste en añadir el diario de BTC.
- [Procedimiento reproducible](repair_sources.py).

Los archivos de esta carpeta preservan sus bytes mediante `.gitattributes`.
Las corridas, los informes y el paquete de entrega anteriores se conservan.

## Reproducción

Desde la raíz del repositorio, con la descarga continua completa:

```powershell
& '.\.venv\Scripts\python.exe' -u '.\data\research\continuous-preparation-20260919\repair_sources.py' --root 'D:\Backtesting'
$configContinuo = (Resolve-Path '.\configs\download_minutes_2022_2026_d.toml').Path
& '.\.venv\Scripts\python.exe' -u -m crypto_carry --root 'D:\Backtesting' validate-data --config $configContinuo --scope full --clip-price-warmup
```

La investigación devuelve código 2 cuando conserva huecos sin resolver. El
segundo comando procesa los crudos y genera el informe de calidad; devuelve
código 2 si la cobertura es incompleta. Los informes se guardan en `manifests`
dentro del destino continuo. Para revalidar sin recalcular Parquet, agregar
`--skip-normalize` al segundo comando. Ninguno de estos comandos ejecuta
backtests ni cambia el motor financiero.

# Marks de cobro faltantes: seguimiento del 18/09/2026

Esta investigación se puede realizar sin terminar la descarga de trades. Se usaron respuestas y ZIP de la muestra en C: y diez consultas públicas pequeñas. No se modificaron los inputs del backtest ni los archivos de D:.

## Resultado

**Siguen faltando 2.005 marks por activo dentro de la ventana económica; no se recuperó ninguno mediante estas consultas.** Se preparó un [inventario de los 4.010 eventos](../../data/research/funding-followup-20260918/missing-economic-settlement-marks.json) con símbolo, timestamp original en milisegundos, hora UTC, tasa y página de procedencia. El [informe de evidencia](funding_followup_20260918.json) incluye SHA-256, resultados y comparaciones.

| Alcance por activo | BTCUSDT | ETHUSDT |
|---|---:|---:|
| Filas de la consulta completa, incluida preparación | 6.684 | 6.684 |
| Marks ausentes, incluida preparación | 3.577 | 3.577 |
| Marks ausentes en `[2022-01-01, 2026-09-01)` | 2.005 | 2.005 |

Los primeros eventos económicos sin mark son del `2022-01-01T00:00:00.006Z`; los últimos, del `2023-10-31T00:00:00.001Z`. Cuatro consultas nuevas del 01/01/2022 y del 31/10/2023, para ambos activos, reprodujeron el dato vacío y la aparición del primer mark a las 08:00 UTC del 31/10/2023. Después se volvió a consultar **todo el intervalo faltante**: seis páginas, 449.953 bytes, exactamente los mismos 4.010 timestamps y tasas, **cero marks recuperados**. Se preservaron las diez respuestas originales en `data/research/funding-followup-20260918/`.

Los cuatro ZIP de calendario de funding de la muestra contienen `calc_time`, `funding_interval_hours` y `last_funding_rate`; no incluyen un precio de cobro. Esta comprobación se refiere a esos archivos concretos, no certifica todos los archivos del proveedor.

## Por qué las velas no completan el requisito exacto

Se compararon 12 cobros con mark conocido (31/12/2023 y 01/01/2024, ambos activos) contra las velas oficiales de mark price de un minuto. Se verificaron hashes de las 14 páginas previas, hashes/checksums e integridad ZIP de los archivos de la muestra. Los cálculos usan `Decimal` y los timestamps de funding se mantienen sin redondear. La alineación por minuto solo identifica la vela candidata; no cambia la hora de cobro.

| Precio candidato | Coincidencias exactas | Comparaciones disponibles |
|---|---:|---:|
| Apertura del minuto de cobro | 10 | 12 |
| Cierre del minuto de cobro | 0 | 12 |
| Cierre del minuto anterior | 4 | 10 |

Ejemplos del `2023-12-31T00:00:00.000Z`:

| Activo | Mark de cobro | Apertura de la vela |
|---|---:|---:|
| BTCUSDT | 42173.49474823 | 42173.50049291 |
| ETHUSDT | 2293.07001515 | 2293.07796970 |

Son contraejemplos a la equivalencia exacta; **esta muestra pequeña no estima el error del histórico completo ni su efecto sobre rentabilidad**. El cierre del propio minuto, además, solo se conoce después del evento.

El [changelog oficial](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/change-log) documenta la incorporación de `markPrice` al historial de funding el 01/11/2023. La [FAQ oficial, versión en-AE consultada](https://www.binance.com/en-AE/support/faq/detail/360033525031), distingue el mark calculado para funding del difundido cada segundo. Esa página mutable muestra publicación original en 2019, pero no acredita que su redacción actual estuviera disponible entonces.

## Fuentes alternativas y siguiente requisito

[Tardis documenta](https://docs.tardis.dev/historical-data-details/binance-futures) un archivo del canal `markPrice`, a intervalos de un segundo desde febrero de 2020. Es una posible fuente de marks observados; **su documentación no demuestra que conserve el precio interno exacto de cada cobro ausente**. No se contrató ningún servicio ni se descargó su histórico.

Para cerrar el requisito estricto hace falta una fuente que vincule explícitamente el precio con cada liquidación de funding: exportación oficial o un proveedor que acredite esa procedencia y cobertura. Los criterios concretos serían símbolo USD-M, timestamp efectivo sin redondear, tasa, precio de cobro, precisión y evidencia de origen; se contrastaría primero con eventos para los que Binance sí publica mark.

No se necesita una API key del usuario para continuar la investigación pública. Si solo se consiguieran marks aproximados, habría que definir un estudio adicional con esa limitación o cambiar la ventana de evaluación mediante una decisión metodológica explícita. No se incorporan aproximaciones al caso estricto por completar un archivo.

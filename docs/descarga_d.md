# Descargar la historia completa en D:

Preparado el 18/09/2026 a pedido del usuario, quien después inició la descarga en su consola. Estas instrucciones también sirven para reanudarla si se interrumpe; no ejecutar otra copia mientras siga activa.

## Ejecutar en PowerShell

Este comando usa el Python ya instalado en el proyecto. El codigo permanece en C: y los datos se guardan en `D:\Backtesting\data`.

```powershell
Set-Location 'C:\Users\pablo\Documentos\UCEMA\Tesina\Backtesting'
$configDescarga = (Resolve-Path '.\configs\download_full_d.toml').Path
& '.\.venv\Scripts\python.exe' -u -m crypto_carry --root 'D:\Backtesting' download --config $configDescarga --scope full
```

La configuracion separada admite hasta **800.000.000.000 bytes (800 GB decimales)** bajo `D:\Backtesting\data`; no reserva ese espacio. El presupuesto incluye archivos crudos, temporales, manifiestos y eventuales procesados. Al prepararla se verificaron 957.918.044.160 bytes libres en D:. `configs/base.toml` conserva el limite de 20 GB de la muestra.

## Que descarga

- BTCUSDT y ETHUSDT, spot y futuros perpetuos USD-M: trades individuales en ZIP diarios.
- Historia desde el 11/08/2020 hasta el 31/08/2026 inclusive.
- Mark price de futuros de un minuto, incluyendo el dia antecedente.
- Calendario mensual de funding y consultas publicas de funding, con el calentamiento adicional configurado.
- Checksums oficiales y, al finalizar, el manifiesto `D:\Backtesting\data\manifests\download.json` con procedencia y errores.

La estimacion anterior de **210,421 GB** correspondia a los 224 ZIP **mensuales de trades de 2022 a agosto de 2026**. Este comando usa ZIP diarios e incluye ademas 2020-2021 y otros datasets; su total sera distinto y mayor. No se debe interpretar 210,421 GB como el espacio total de todos los datos ni del procesamiento posterior.

## Espacio y Parquet

El normalizador ya produce **Parquet con compresión ZSTD**. Lee los CSV dentro de los ZIP sin extraerlos al disco y conserva los originales para verificar procedencia e integridad. Convertirlos localmente no reduce los bytes que se deben descargar desde Binance.

Medición del 18/09/2026 sobre los mismos **5.543.505 trades del 01/01/2024**, BTCUSDT y ETHUSDT, spot y Futures. Para Parquet se cuentan solamente las particiones activas del manifiesto, sin versiones anteriores ni otros datasets:

| Representación | Bytes | MB decimales |
|---|---:|---:|
| CSV sin comprimir, tamaño declarado dentro de los ZIP | 328.561.923 | 328,56 |
| ZIP oficiales descargados | 57.062.373 | 57,06 |
| Parquet/ZSTD normalizado | 55.076.025 | 55,08 |

En esta muestra, Parquet ahorra **83,24 % frente al CSV**, pero **3,48 % frente al ZIP**. Los porcentajes no se extrapolan al histórico completo. Conservar ZIP y Parquet requiere sumar ambos tamaños; no se eliminan automáticamente los originales. La estimación anterior de más de 200 GB ya correspondía a ZIP comprimidos, no a CSV sin comprimir.

## Corrección de velocidad del descargador

Se detectó que el control de presupuesto recorría todos los archivos por cada fragmento de red. El descargador ahora agrupa la lectura en bloques de **1 MiB** y mantiene la comprobación de espacio antes de cada escritura, además de SHA-256, CRC del ZIP y reanudación.

Ensayo local controlado con un ZIP de 1.240.118 bytes, 76 fragmentos de 16 KiB y 462 archivos existentes: **77 → 3 recorridos**, **2,09 → 0,10 segundos**. Este ensayo aísla el costo local; no mide la conexión a Binance ni permite prometer esa mejora en una descarga real. El costo de recorrer la carpeta también crecerá con el número de archivos.

El usuario interrumpió la descarga para este diagnóstico. Si se necesita reanudar, se utiliza el mismo comando de arriba: reutiliza los ZIP verificados y continúa el parcial cuando el servidor admite Range. No iniciar otra copia si ya está descargando.

## Interrupciones y comprobaciones

Se puede detener con `Ctrl+C` y volver a ejecutar el mismo comando. Los ZIP completos se verifican y reutilizan; los `.part` se intentan continuar mediante HTTP Range. Si el servidor no acepta Range, ese archivo parcial se vuelve a descargar. Se comprueban SHA-256 y la integridad interna del ZIP antes de publicarlo como completo.

El programa imprime su resumen al finalizar; durante la ejecucion van apareciendo archivos bajo `D:\Backtesting\data\raw`. No extraer los ZIP manualmente: el normalizador los lee directamente. Mantener el equipo encendido y sin suspension mientras descarga.

Si el resumen contiene `failed`, esos archivos o respuestas quedaron pendientes; los detalles estaran en `download.json`. Repetir el comando permite reintentar, pero no resuelve archivos ausentes en la fuente. Las reglas historicas siguen requiriendo la investigacion documental indicada en el README: descargar los precios no completa ese requisito.

Fuente publica oficial, sin API key: [Binance Public Data](https://github.com/binance/binance-public-data).

Los pasos posteriores y la comprobación `preflight`, que puede consultarse sin interrumpir esta descarga, están en [puesta en marcha](puesta_en_marcha.md).

Con las aproximaciones aprobadas el 18/09/2026, los comandos de validación, backtest y sensibilidades están en [escenario de investigación](escenario_investigacion.md). Ese modo usa precios observados y reglas prescritas, sin exigir el archivo de reglas históricas completas. Los controles de integridad y cobertura siguen activos.

# Puesta en marcha cuando termine la descarga

Actualizado el 18/09/2026. La descarga completa no elimina los bloqueos de evidencia histórica. Se puede preparar y comprobar el software ahora; una evaluación económica necesita datos y reglas válidos para todo su intervalo.

## Qué está preparado y qué falta

| Trabajo | Situación | Condición para cerrarlo |
| --- | --- | --- |
| Motor, dos carteras, contabilidad, riesgos, checkpoints e informes | Implementados y con pruebas registradas en [avance](progress.md). | Verificación de la corrida con datos históricos completos. |
| Reglas históricas | Fuentes parciales; `history.json` vacío. | Completar vigencias, tarifas, filtros, margen, liquidación y operatividad. Publicar la versión verificada en la raíz de datos elegida. |
| Funding inicial | La API consultada no aporta 2.005 marks de cobro por activo dentro del período económico. | Evidencia adicional de esos precios; no sustituirlos silenciosamente. |
| Continuidad de trades | La muestra concilia con velas, pero mantiene discontinuidades de IDs sin explicación individual. | Resolver con evidencia y un criterio documentado, manteniendo los controles estrictos hasta entonces. |
| Preparación en D: | Comprobación previa `preflight` y comandos disponibles. | Manifiesto de descarga completo, normalización y cobertura verificadas. |
| Pruebas de períodos cortos | Validación y replay acotados al intervalo y sus antecedentes necesarios. | Aplicar controles completos; recortar lectura no convierte un dato desconocido en válido. |
| Escala de varios años | Trades leídos por bloques; tablas de resultados crecen en memoria. | Medir tiempo, RAM, espacio y reanudación en una corrida histórica corta antes de ampliar. No se ha medido el conjunto completo. |
| Ajustes y sensibilidades | Configuraciones separadas, 30 escenarios predefinidos y artefactos por corrida. | Baseline verificable, comparación completa y evaluación en datos no usados para ajustar. |

La [investigación](research/README.md) describe las fuentes faltantes. La [fiabilidad](fiabilidad.md) define las condiciones adicionales para considerar una futura prueba con capital; la simulación en vivo es una etapa posterior al backtest histórico.

## 1. Comprobación rápida, disponible ahora

En PowerShell, desde el proyecto:

```powershell
Set-Location 'C:\Users\pablo\Documentos\UCEMA\Tesina\Backtesting'
$pythonBacktest = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$configBacktest = (Resolve-Path '.\configs\download_full_d.toml').Path
$raizBacktest = 'D:\Backtesting'
& $pythonBacktest -u -m crypto_carry --root $raizBacktest preflight --config $configBacktest
```

`preflight` sólo lee metadatos y archivos de reglas. Comprueba el plan de la **misma descarga completa**, el estado y tamaño de cada archivo previsto, presencia de checksums y cobertura temporal de reglas. Código 2 indica bloqueos; 0 y `ready_for_validation` indican que se puede pasar a validación. No verifica hashes de todos los datos, esquemas ni filas; por eso siempre informa `integrity_verified=false` y `historical_certified=false`. No inicia ni modifica la descarga.

El plan actual comprende 13.424 objetos de datos, además de los archivos de checksum. Es un número planificado, no un contador de progreso ni una prueba de cobertura. La comprobación realizada durante la descarga encontró ausencia del manifiesto final y de reglas en D:.

Los parámetros del backtest usan `data/rules/history.json` **bajo D:** porque `--root` es D:. El archivo existente en C: no se usa automáticamente. La publicación de un archivo de reglas en D: debe esperar a que haya una versión completa y revisada; copiar ahora el archivo vacío no resuelve el bloqueo.

## 2. Normalizar una vez y validar

Cuando el proceso de descarga haya terminado, comprobar que `preflight` informa `download.ready=true`. Las reglas pueden seguir pendientes: adelantar la normalización no acredita resultados económicos.

```powershell
& $pythonBacktest -u -m crypto_carry --root $raizBacktest validate-data --config $configBacktest --scope full
```

Esta fase lee los ZIP directamente y escribe Parquet en D:. **Puede llevar tiempo y necesita espacio adicional.** El límite conjunto sigue siendo 800 GB. El normalizador procesa las entradas exitosas del manifiesto completo; `--scope sample` por sí solo no reduce ese trabajo inicial. Por eso, después de normalizar, las comprobaciones de muestra deben usar `--skip-normalize`:

```powershell
& $pythonBacktest -u -m crypto_carry --root $raizBacktest validate-data --config $configBacktest --scope sample --skip-normalize
```

Si devuelve código 2, revisar `D:\Backtesting\data\manifests\coverage.json` y `data_quality_report.md`. No interpretar esa salida como autorización para una corrida económica. Una muestra de 2024 puede tener cobertura distinta de la historia completa; ambas se etiquetan y validan por separado.

No ejecutar normalización mientras se esté escribiendo la descarga ni lanzar dos normalizadores sobre la misma raíz. Repetir la normalización vuelve a leer los crudos; la infraestructura actual conserva archivos por hash, pero no ofrece todavía una reanudación rápida por archivo ya procesado.

## 3. Primera corrida y prueba de escala

Sólo cuando la muestra tenga cobertura válida:

```powershell
& $pythonBacktest -u -m crypto_carry --root $raizBacktest backtest --config $configBacktest --sample --strategy both
```

Guardar el `run_id` y revisar fills, funding, P&L, exposición entre patas y motivos de salida contra las fuentes. Medir RAM máxima, duración y tamaño de salidas; repetir con una configuración de intervalo más largo y comprobar reanudación antes de los años completos. La prueba sintética y una muestra de un día no predicen por sí solas el consumo de recursos de todo el estudio.

El replay omite particiones ajenas al intervalo cuando sus metadatos lo permiten, conservando antecedentes y orden temporal. Los hashes de procedencia todavía leen los inputs completos; su costo no desaparece al solicitar una muestra. La selección de particiones confía en extremos del manifiesto que deben provenir de datos validados.

Con cobertura **full** válida y recursos medidos:

```powershell
& $pythonBacktest -u -m crypto_carry --root $raizBacktest backtest --config $configBacktest --strategy both
```

El backtest vuelve a validar cobertura y conserva su configuración efectiva y hashes. Estado `complete` describe finalización dentro del modelo; `insolvent` preserva el resultado adverso. Los informes se escriben en `D:\Backtesting\outputs\<run_id>`.

## 4. Ajustar con comparaciones reproducibles

Conservar el baseline. Cada ajuste usa un TOML distinto y una corrida nueva; un cambio incompatible de código, parámetros, reglas o datos no puede reanudar el checkpoint anterior. `preflight` usa la configuración original de descarga; los experimentos con otra ventana se validan mediante `validate-data --skip-normalize` y `backtest` con su propio TOML.

Después del baseline, se puede empezar por un subconjunto de sensibilidades:

```powershell
& $pythonBacktest -u -m crypto_carry --root $raizBacktest robustness --config $configBacktest --scenario cost-2 --scenario cost-3
```

El baseline se incluye siempre. Omitir `--scenario` solicita las 30 configuraciones; no conviene iniciarlas juntas antes de medir una corrida. Actualmente cada escenario vuelve a validar y calcular hashes de inputs, de modo que su costo de lectura también debe medirse.

Registrar todos los ajustes y resultados, incluidos los negativos. Definir qué datos se reservarán para evaluación antes de usarlos para elegir parámetros. No cambiar simultáneamente varias reglas ni escoger sólo el mejor período y presentarlo como resultado general.

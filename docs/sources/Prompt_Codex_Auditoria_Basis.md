# Prompt para Codex: auditoría independiente del basis

Trabajá sobre el proyecto existente en `Backtesting`. Ejecutá una auditoría independiente del cálculo y uso del basis que aparece en `execution_revision_report.md`. Entregá evidencia reproducible y una conclusión, no solamente un plan.

## Objetivo y alcance

Necesito determinar si el basis casi siempre negativo proviene de los precios históricos originales o de un error de fuente, transformación, alineación temporal, fórmula o clasificación.

El escenario principal es `vwap_joint`, con dos ventanas independientes UTC:

- `[2022-09-01, 2023-09-01)`.
- `[2025-09-01, 2026-09-01)`.

El informe reciente muestra 1.095 evaluaciones por activo y ventana. En la ventana tardía, registra basis negativo en 1.090 observaciones de BTCUSDT y las 1.095 de ETHUSDT. Las medianas respectivas son aproximadamente `-0.000469` y `-0.000477`. Son cifras para contrastar, no objetivos que el código deba reproducir a cualquier costo.

No presupongas que estos resultados son erróneos. Tampoco uses el signo del funding como prueba de qué signo debería tener el basis.

Todos los archivos nuevos deben quedar dentro de `Backtesting`, respetando su estructura. Código, comentarios y docstrings en inglés; explicación y reporte en español. Conservá trabajo previo, configuraciones y resultados originales.

Los trades individuales y `aggTrades` están descartados. Usá exclusivamente las velas de un minuto y demás datos agregados ya autorizados. No descargues ticks ni datos subminuto para esta auditoría.

## 1. Identificar la cadena de datos

Leé las instrucciones del repositorio, configuración efectiva, manifiestos, señales persistidas y código que produce el basis y sus rechazos. Partí de las corridas que efectivamente alimentan el reporte, comprobando sus identificadores y versiones. Si hay un reporte más reciente, identificá claramente cuál auditás.

Trazá esta cadena con archivos, campos y funciones concretos:

`fuente original -> parser -> timestamps normalizados -> selección de vela -> precios de señal -> basis -> filtro -> tabla del reporte`

Verificá que los instrumentos sean BTCUSDT y ETHUSDT spot frente a sus perpetuos lineales USD-M. Descartá mezclas con COIN-M, futuros con vencimiento, otro par, mark price o índice.

## 2. Recalcular desde la fuente, independientemente

Construí un auditor pequeño y separado. Podés reutilizar localización de archivos, pero no la función de basis ni la transformación de precios que estás auditando. Leé directamente las columnas originales de las klines, verificando su esquema.

Para cada evaluación de las dos ventanas y ambos activos, recuperá el cierre spot `S` y el cierre del perpetuo `F` del mismo intervalo de un minuto, ya cerrado y disponible al decidir. Calculá con suficiente precisión:

`basis_raw = F / S - 1`

Los precios deben ser originales, sin slippage, comisiones, ajustes de cantidad ni anualización. El VWAP utilizado para simular una ejecución posterior no es el precio de la señal de basis.

Contrastá por separado precios originales contra precios normalizados, precios normalizados contra los seleccionados por la señal y basis independiente contra el persistido. Esto debe permitir ubicar la primera divergencia, no únicamente mostrar una diferencia final.

Usá como tolerancia inicial de comparación numérica `1e-12` en unidades decimales de basis. Si el formato persistido pierde precisión, documentá esa precisión y sus consecuencias; no amplíes la tolerancia para esconder diferencias. No audites igualdad usando únicamente los seis decimales impresos en el Markdown.

Si una diferencia modifica la clasificación respecto de cero o 0,005, señalala aunque sea numéricamente pequeña. La tolerancia del auditor no modifica los umbrales operativos.

Reutilizá las fuentes originales locales. Si faltan, recuperá solamente las particiones de klines indispensables y registrá origen y checksum. Si no podés obtenerlas, distinguí validación contra datos procesados de validación contra la fuente original y reportá la cobertura realmente alcanzada.

## 3. Verificar tiempos y disponibilidad

Comprobá explícitamente:

- Unidades de timestamps de cada fuente, especialmente spot en microsegundos desde 2025 frente a archivos que usan milisegundos. Normalización consistente a UTC.
- Diferencia entre timestamp de apertura, cierre reportado por el exchange, fin exclusivo del intervalo y momento de disponibilidad adoptado por el motor.
- Mismo intervalo para spot y perpetuo, sin joins por posición de fila, duplicados, desplazamientos de una vela ni relleno silencioso de huecos.
- Uso exclusivo de observaciones disponibles al decidir. Si la señal se emite en `tau + 60 segundos`, identificá exactamente qué vela selecciona cada mercado y justificá que ya estaba disponible bajo la convención del proyecto.
- Ausencia de precios de ejecución futuros, cierres de velas incompletas o datos de otro símbolo en la señal.

La estadística corresponde a los instantes de evaluación de la estrategia, no necesariamente a todos los minutos del año. No extrapoles automáticamente el porcentaje de basis negativo fuera de esa muestra temporal.

## 4. Evidencia y clasificación

Guardá un archivo con todas las evaluaciones auditadas, sin duplicar artificialmente las observaciones de mercado porque existan dos estrategias. Preservá por separado la decisión de cada estrategia cuando sus estados difieran.

Incluí al menos: ventana, símbolo, timestamp de decisión, identificador de señal, archivos y registros originales, unidad de tiempo de origen, intervalo spot/perpetuo, disponibilidad, precios originales y usados por el motor, basis independiente y persistido, diferencia, clasificación original y auditada, y motivo de discrepancia o imposibilidad de evaluar.

Prepará además una muestra legible de 20 observaciones por activo y ventana, 80 en total, seleccionada de forma determinista. Incluí fechas distribuidas por el año, extremos y casos próximos a cero. Registrá el criterio y evitá elegir solamente observaciones que confirmen una conclusión.

Para cada activo y ventana, resumí cobertura, cantidad de discrepancias, máximo error absoluto, mínimo, mediana, máximo y cantidades con basis negativo, cero, dentro de `[0, 0.005]` y superior a 0,005. Aclarar que cero también pertenece al rango elegible evita sumar categorías solapadas como excluyentes.

Reconciliá estos conteos con las señales y el reporte. Separá el resultado teórico de cada condición del rechazo que efectivamente bloqueó una orden. En particular, la permanente omite el filtro de funding: que su forecast no cubra costos puede mostrarse como diagnóstico, pero no contarse como bloqueo operativo de esa estrategia.

## 5. Pruebas mínimas y actuación según el hallazgo

Verificá con casos calculables a mano:

- `S=100, F=99.95`: basis `-0.0005`, equivalente a `-0.05%` o `-5 bps`, no elegible.
- `S=100, F=100`: basis cero, elegible.
- `S=100, F=100.5`: basis `0.005`, elegible por igualdad en el límite superior.
- `S=100, F=100.51`: basis `0.0051`, no elegible.
- Dos timestamps equivalentes expresados en milisegundos y microsegundos se normalizan al mismo instante.
- Una vela futura, un par desalineado o una fuente faltante se detectan explícitamente y no se convierten en una observación histórica válida.

Si encontrás un error, presentá su causa y una reproducción mínima. Corregí exclusivamente el defecto demostrado, agregá la prueba correspondiente y conservá los artefactos anteriores. Volvé a ejecutar el escenario principal en las ventanas afectadas para ambas estrategias con identificadores nuevos, comparando basis, decisiones, operaciones y resultados antes y después. Si el defecto es solo de presentación, corregí y regenerá el reporte sin fingir que se volvió a simular.

Si el cálculo y los datos son correctos, dejá las reglas intactas y cerrá la auditoría con esa evidencia. Si faltan elementos indispensables, identificá el bloqueo; no declares validado lo que no pudiste contrastar.

No cambies EWMA, horizonte de 168 horas, intervalo de basis, costos, tolerancia del hedge, sizing ni ejecución para producir más operaciones. Esta auditoría no autoriza optimización de la estrategia.

## Entrega

Guardá en un directorio de auditoría con identificador propio:

- `basis_audit_report.md`: conclusión, cadena revisada, cobertura, diferencias y límites.
- `basis_audit_all.csv` o Parquet equivalente: todas las observaciones auditadas.
- `basis_audit_sample.csv`: las 80 observaciones trazables a las fuentes.
- `basis_audit_summary.csv`: estadísticas y discrepancias por activo y ventana.
- Manifiesto con configuraciones, código, fuentes, checksums y comando efectivamente ejecutado para reproducir la auditoría.

En tu respuesta final indicá si el basis negativo quedó confirmado, si encontraste un error o si la evidencia es insuficiente. Si corregiste algo, mostrá qué cambió y qué pruebas ejecutaste. Explicá qué implica para los rechazos, sin afirmar que validar el basis demuestra por sí solo la rentabilidad o la corrección completa del backtest.

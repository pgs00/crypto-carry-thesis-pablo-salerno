# Lectura y reproducción de la primera comparación de reglas

Versión técnica preliminar, pendiente de comentarios del profesor. El reporte se construye desde artefactos persistidos; no ejecuta backtests ni reemplaza Entrega 3. Los seis escenarios y sus comparadores están fijados en [protocolo.md](protocolo.md).

El paquete de esta tanda es `entregas/entrega_4/reglas_historicas/20260925T005436Z/`. `indice_corridas.json` registra los doce pares escenario/cartera y los estados `ejecutado`, `reutilizado_verificado`, `fallido` o `bloqueado`. Un fallo conserva su motivo y no genera un año ficticio sin operaciones. Cada resultado remite al `run_id`, manifiesto y configuración de una única cartera independiente. `comparacion/reporte.md` explica los resultados; sus CSV conservan los números sin redondear.

## Construcción y sello

Desde la raíz del repositorio, con el intérprete y las dependencias del proyecto:

```powershell
.venv/Scripts/python.exe scripts/report_historical_rules_sensitivity.py --package entregas/entrega_4/reglas_historicas/20260925T005436Z
```

Este comando escribe sólo `comparacion/` dentro del paquete nuevo. Lee Parquet mediante PyArrow y produce figuras científicas con Matplotlib; no importa el motor. La opción `--no-figures` sirve para pruebas de aritmética. Se verifican los hashes de todos los artefactos de cada corrida antes de calcular resultados.

Una vez terminados todos los resultados, logs, documentos, copias de procedencia y herramientas, el sello es una acción explícita separada:

```powershell
.venv/Scripts/python.exe scripts/report_historical_rules_sensitivity.py --package entregas/entrega_4/reglas_historicas/20260925T005436Z --seal
```

El sello crea `manifiesto_paquete.json` y `manifiesto_paquete.sha256`. Incluye todo archivo del paquete salvo esos dos archivos, que se comprueban mediante el sidecar. Rechaza sobrescribir un sello existente. El constructor tampoco modifica un paquete ya sellado. El hash detecta cambios respecto de ese inventario; no es una firma digital ni prueba de autenticidad de una fuente.

## Verificación portable y de sólo lectura

El verificador usa únicamente la biblioteca estándar, no consulta red, Git, HEAD, índice, sesiones anteriores ni la unidad donde estaban los datos. Puede ejecutarse sin `site-packages`:

```powershell
python -I -S -B scripts/verify_rules_sensitivity_package.py --package <ruta-del-paquete>
```

En una exportación autocontenida, las herramientas se conservan juntas en `herramientas/`:

```powershell
python -I -S -B <ruta-del-paquete>/herramientas/verify_rules_sensitivity_package.py --package <ruta-del-paquete>
```

El resultado JSON va a stdout; código de salida 0 indica pase y 1 indica fallo. `--output <ruta-nueva-externa>` puede conservar el resultado fuera del paquete. Rechaza escribir dentro de las evidencias o sobre un archivo existente. No genera `__pycache__` ni resultados dentro del paquete. La verificación del paquete requiere todo su contenido; no requiere copiar datos masivos de mercado. Para verificar por separado la documentación histórica, use la guía y el verificador de publicación con las copias históricas/A1–A3 incluidas.

El control comprueba inventario, tamaños, hashes, sidecars, rutas confinadas al paquete, archivos requeridos, identidades de corrida/cartera, estados, cobertura diaria continua, conciliación Decimal, retornos, CAGR, Sharpe, drawdown, componentes, deltas y emparejamiento H2. Recalcula H1 desde el CSV de pronósticos/targets/exclusiones y H3 desde la tabla diaria de conteos por activo. Cada `code_files` se contrasta byte por byte con `codigo_base/` para BASE_E3 y `codigo_ejecutado/` para las variantes; también se verifica la agregación SHA-256 de ese mapa usando la serialización JSON canónica del motor. Los Parquet originales se verifican por hash; su interpretación para contadores de ejecución/exposición y el control de pronósticos Decimal de `signals.parquet` corresponde al constructor con PyArrow. El verificador portable no simula de nuevo ni prueba independientemente toda la implementación del motor. Los hashes de inputs y las versiones de dependencias quedan como procedencia; la relectura local previa de datos se documenta por separado, y no se afirma repetirla offline.

## Convenciones de las tablas

- `metricas_cartera_periodo.csv`: muestra completa, 2022–2023, 2024 en adelante y años disponibles. El capital de cada subperíodo es la equity del cierre previo. No se reinicia la cartera al cortar períodos.
- `diario_carteras.csv` y `componentes_por_activo_periodo.csv`: diferencias de cumulativos realizados/no realizados de spot/futuros, funding y costos. La suma de spot + futuros + funding − fees − cargos de liquidación reconcilia la variación de equity con tolerancia original `1E-8` USDT. Las columnas de fees ya llevan signo negativo. Slippage es informativo porque ya está incluido en los precios de ejecución; no se resta otra vez.
- Retorno, CAGR, volatilidad, drawdown y utilización son razones (`0.01 = 1%`). Sharpe usa media de retornos diarios, desviación estándar muestral, tasa libre de riesgo cero y 365 días. Si no hay dos retornos, si la volatilidad es cero o si aparece equity no positiva, Sharpe queda vacío en CSV y ND en Markdown, con motivo. Nunca se sustituye por cero. Drawdown es diario y su duración máxima se expresa en días.
- `deltas.csv`: REALIZADA y MARGEN_2X comparan con BASE_E3; DECISION compara con su REALIZADA. Los cambios de comisiones repercuten sobre caja, cantidades, exposición y decisiones posteriores. El delta de P&L no representa una resta de comisiones sobre posiciones fijas.
- `eventos_periodo.csv`: fecha efectiva de cada evento. Las aperturas cuentan transiciones a `OPENING_SPOT`, las aperturas completadas usan `opening_complete`, las fallas se deduplican por orden, los parciales cuentan fills y los cierres por margen cuentan solicitudes. Los fills de liquidación se informan por separado.
- `exposicion_periodo.csv`: integra cantidades del ledger entre eventos y preserva inventario anterior al corte. Los segundos de cartera son la unión de los activos; no su suma. Para coincidir con la definición original, cualquier spot positivo, incluso polvo, cuenta como inversión y puede quedar sin cobertura. La tolerancia de cobertura es la de la configuración efectiva. Se integra hasta el fin exclusivo de la muestra; el contador archivado terminaba en `end-1ns`, diferencia máxima de un nanosegundo.
- Utilización = (valor spot + collateral aislado)/equity; exposición bruta = valor spot + nocional corto. Las medias/máximos de utilización, collateral y mantenimiento son de cierres diarios, sin interpolación intradiaria. Los tramos para mantenimiento son los supuestos guardados en `research_assumptions.json` de cada corrida, no una cronología certificada de Binance. Una razón de margen sin corto activo queda ND.
- `fronteras_promocion.csv`: conserva fills que tocan el inicio/fin exacto de promoción, o declara su ausencia. La tarifa se atribuye al inicio de la ventana VWAP completa y se contabiliza al cierre de esa ventana. No se inventan trades subminuto.

## Hipótesis y procedencia de H3

H1 compara exactamente los campos de pronóstico de `signals.parquet` y todos los datos de evaluación, objetivos, exclusiones y resumen archivado, exceptuando identidad de corrida. El MAE se calcula por activo y después se promedia con pesos BTC/ETH 0,5/0,5. Esa invariancia es un control de inputs, no un nuevo hallazgo de rentabilidad. H2 compara las dos carteras dentro de cada escenario/período; un Sharpe indefinido impide un veredicto favorable o desfavorable.

`h3_minutos/<run_id>.csv` conserva por activo/día los minutos totales, conocidos, desconocidos, elegibles y la suma Decimal del forecast bruto elegible. Un día completo necesita los 1.440 minutos conocidos de cada activo. Se promedian primero los minutos de cada activo y luego ambos activos 50/50. Un dato desconocido no equivale a cero. `h3_diario.csv` reconcilia esa reconstrucción con `opportunity_daily.csv`, con tolerancia exclusivamente por su representación flotante original; `h3_invariancia.csv` exige igualdad exacta de los CSV diarios originales cuando el costo de decisión no cambia y entre las carteras del mismo escenario.

BASE_E3 no contenía ese desglose por activo/minuto en sus artefactos archivados. Si se usa una reconstrucción observada en una variante REALIZADA con idénticas entradas H3, `h3_procedencia.json` declara un alias con `source_run_id` real y `status=derivado_invariancia_verificada`. Se vuelve a comprobar la igualdad exacta de `forecast_evaluation.csv` y `opportunity_daily.csv` antes de aceptar ese alias. El desglose derivado no se presenta como una nueva ejecución BASE ni como un archivo archivado de Entrega 3.

H3 conserva los cortes 2022–2023 y enero de 2024–agosto de 2026. El veredicto descriptivo compara el cambio de oportunidad bruta elegible y el CAGR condicional: ambos menores, favorable; ambos mayores, contraria; sentidos distintos o empates, mixta; datos no definidos/incompletos, no concluyente. DECISION usa su costo ex ante contemporáneo, sin restarlo al forecast elegible.

Las limitaciones de `futures_scaled`, aproximaciones de funding/marcas, cobertura histórica parcial de reglas y ausencia de trayectorias intraminuto permanecen vigentes. La conservación de bytes de Entrega 3, la procedencia histórica, los cambios intencionales del código y la publicación en GitHub se verifican y reportan por separado.

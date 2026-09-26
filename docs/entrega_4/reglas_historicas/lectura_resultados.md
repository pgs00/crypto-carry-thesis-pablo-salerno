# Lectura y reproducción de la primera comparación de reglas

Versión técnica preliminar, pendiente de comentarios del profesor. El reporte se construye desde artefactos persistidos; no ejecuta backtests ni reemplaza Entrega 3. Los seis escenarios y sus comparadores están fijados en [protocolo.md](protocolo.md).

El paquete de esta tanda es `entregas/entrega_4/reglas_historicas/20260925T005436Z/`. `indice_corridas.json` registra los doce pares escenario/cartera y los estados `ejecutado`, `reutilizado_verificado`, `fallido` o `bloqueado`. Un fallo conserva su motivo y no genera un año ficticio sin operaciones. Cada resultado remite al `run_id`, manifiesto y configuración de una única cartera independiente. `comparacion/reporte.md` explica los resultados; sus CSV conservan los números sin redondear.

## Corrección editorial v2: exposición y H2

La revisión del 26/09/2026 corrige el indicador operativo para excluir polvo conforme a E3 y completa H2 con el requisito de CAGR condicional positivo. Las doce carteras existentes y el paquete padre sellado permanecen intactos. Las herramientas archivadas conservan soporte v1; los comandos activos construyen la corrección v2 en otro destino.

## Construcción y sello

Desde la raíz del repositorio, con el intérprete y las dependencias del proyecto:

```powershell
.venv/Scripts/python.exe -B -X utf8 scripts/report_historical_rules_sensitivity.py `
  --source-package entregas/entrega_4/reglas_historicas/20260925T005436Z `
  --destination <destino_nuevo_fuera_de_paquetes_sellados> `
  --e3-reference "Paquete de evidencia"
```

El constructor lee el padre y la referencia E3; escribe sólo un destino inexistente. Lee Parquet mediante PyArrow y genera figuras con Matplotlib; no importa el motor. `--no-figures` conserva los datos comprobables de la figura y omite las imágenes nuevas. Antes de calcular, verifica el paquete padre. Reutiliza las corridas sin copiarlas al producto derivado.

Al terminar sella automáticamente todos los productos nuevos. No admite los antiguos comandos activos `--package`/`--seal` para reconstruir v1. El sello nuevo fija la dependencia del manifiesto padre; no modifica hashes anteriores. Verificar después de construir:

```powershell
.venv/Scripts/python.exe -B -X utf8 scripts/verify_rules_sensitivity_package.py `
  --package <correccion_v2> `
  --parent entregas/entrega_4/reglas_historicas/20260925T005436Z `
  --output <resultado_nuevo_fuera_de_ambos_paquetes.json>
```

El sello crea `manifiesto_paquete.json` y `manifiesto_paquete.sha256`. Incluye todo archivo del paquete salvo esos dos archivos, que se comprueban mediante el sidecar. Rechaza sobrescribir un sello existente. El constructor tampoco modifica un paquete ya sellado. El hash detecta cambios respecto de ese inventario; no es una firma digital ni prueba de autenticidad de una fuente.

## Verificación portable y de sólo lectura

V2 exige PyArrow y una ruta padre explícita. Verifica independientemente las posiciones, intervalos, uniones, duraciones y H2 completo, además de conservar valores financieros y tablas H1/H3. No consulta red, Git, HEAD, índice, sesiones anteriores ni datos masivos de mercado. Desde otra ruta:

```powershell
python -B -X utf8 <correccion_v2>/herramientas/verify_rules_sensitivity_correction.py `
  --package <correccion_v2> --parent <paquete_padre>
```

La corrección no es autocontenida: requiere el padre completo. La verificación original del padre v1 sí usa sólo biblioteca estándar y conserva su alcance histórico:

```powershell
python -I -S -B -X utf8 <paquete_padre>/herramientas/verify_rules_sensitivity_package.py --package <paquete_padre>
```

El resultado JSON va a stdout; código de salida 0 indica pase y 1 indica fallo. `--output <ruta-nueva-externa>` puede conservar el resultado fuera del paquete. Rechaza escribir dentro de las evidencias o sobre un archivo existente. No genera `__pycache__` ni resultados dentro del paquete. La verificación del paquete requiere todo su contenido; no requiere copiar datos masivos de mercado. Para verificar por separado la documentación histórica, use la guía y el verificador de publicación con las copias históricas/A1–A3 incluidas.

El control original acredita integridad y aritmética persistida bajo v1; no incorpora por sí solo la semántica corregida. V2 también ejecuta ese control original y verifica exactamente los campos financieros no afectados, H1 y H3, la identidad del código económico en los manifiestos y la versión separada del posprocesador. Lee los Parquet de posiciones para validar la clasificación, no sólo sus hashes. No reejecuta el motor ni acredita una validación independiente de toda su implementación. Los hashes de datos masivos quedan como procedencia; no se afirma volver a leerlos offline.

## Convenciones de las tablas

- `metricas_cartera_periodo.csv`: muestra completa, 2022–2023, 2024 en adelante y años disponibles. El capital de cada subperíodo es la equity del cierre previo. No se reinicia la cartera al cortar períodos.
- `diario_carteras.csv` y `componentes_por_activo_periodo.csv`: diferencias de cumulativos realizados/no realizados de spot/futuros, funding y costos. La suma de spot + futuros + funding − fees − cargos de liquidación reconcilia la variación de equity con tolerancia original `1E-8` USDT. Las columnas de fees ya llevan signo negativo. Slippage es informativo porque ya está incluido en los precios de ejecución; no se resta otra vez.
- Retorno, CAGR, volatilidad, drawdown y utilización son razones (`0.01 = 1%`). Sharpe usa media de retornos diarios, desviación estándar muestral, tasa libre de riesgo cero y 365 días. Si no hay dos retornos, si la volatilidad es cero o si aparece equity no positiva, Sharpe queda vacío en CSV y ND en Markdown, con motivo. Nunca se sustituye por cero. Drawdown es diario y su duración máxima se expresa en días.
- `deltas.csv`: REALIZADA y MARGEN_2X comparan con BASE_E3; DECISION compara con su REALIZADA. Los cambios de comisiones repercuten sobre caja, cantidades, exposición y decisiones posteriores. El delta de P&L no representa una resta de comisiones sobre posiciones fijas.
- `eventos_periodo.csv`: fecha efectiva de cada evento. Las aperturas cuentan transiciones a `OPENING_SPOT`, las aperturas completadas usan `opening_complete`, las fallas se deduplican por orden, los parciales cuentan fills y los cierres por margen cuentan solicitudes. Los fills de liquidación se informan por separado.
- `exposicion_periodo.csv`: clasifica la trayectoria completa de posiciones persistidas como cubierta, activa sin cobertura, polvo o ausencia de inventario; después recorta períodos. Los segundos de cartera son uniones, no sumas de activos. Tiempo invertido y sin cobertura activa excluyen polvo conforme a E3; `raw_*` conserva el bruto con cualquier cantidad positiva. Se distingue polvo únicamente, ausencia de actividad y ausencia de inventario. La tolerancia es la de la configuración efectiva. Los intervalos BASE coinciden exactamente con E3 usando el final exclusivo configurado; no se corrige una supuesta diferencia terminal mediante tolerancias.
- Utilización = (valor spot + collateral aislado)/equity; exposición bruta = valor spot + nocional corto. Las medias/máximos de utilización, collateral y mantenimiento son de cierres diarios, sin interpolación intradiaria. Los tramos para mantenimiento son los supuestos guardados en `research_assumptions.json` de cada corrida, no una cronología certificada de Binance. Una razón de margen sin corto activo queda ND.
- `fronteras_promocion.csv`: conserva fills que tocan el inicio/fin exacto de promoción, o declara su ausencia. La tarifa se atribuye al inicio de la ventana VWAP completa y se contabiliza al cierre de esa ventana. No se inventan trades subminuto.

## Hipótesis y procedencia de H3

H1 compara exactamente los campos de pronóstico de `signals.parquet` y todos los datos de evaluación, objetivos, exclusiones y resumen archivado, exceptuando identidad de corrida. El MAE se calcula por activo y después se promedia con pesos BTC/ETH 0,5/0,5. Esa invariancia es un control de inputs, no un nuevo hallazgo de rentabilidad.

H2 es favorable únicamente con CAGR condicional finito y positivo y Sharpe condicional finito superior al permanente, también finito. No exige Sharpe positivo ni CAGR superior al permanente. Con los tres valores evaluables y alguna condición incumplida, es `no_favorable`; no significa automáticamente evidencia contraria. Valores faltantes/no finitos, cobertura incompleta, cartera faltante o ventanas no comparables producen `no_concluyente`, conservando los componentes evaluables y sus motivos. Se comparan valores sin redondear y se rechazan claves duplicadas.

`h3_minutos/<run_id>.csv` conserva por activo/día los minutos totales, conocidos, desconocidos, elegibles y la suma Decimal del forecast bruto elegible. Un día completo necesita los 1.440 minutos conocidos de cada activo. Se promedian primero los minutos de cada activo y luego ambos activos 50/50. Un dato desconocido no equivale a cero. `h3_diario.csv` reconcilia esa reconstrucción con `opportunity_daily.csv`, con tolerancia exclusivamente por su representación flotante original; `h3_invariancia.csv` exige igualdad exacta de los CSV diarios originales cuando el costo de decisión no cambia y entre las carteras del mismo escenario.

BASE_E3 no contenía ese desglose por activo/minuto en sus artefactos archivados. Si se usa una reconstrucción observada en una variante REALIZADA con idénticas entradas H3, `h3_procedencia.json` declara un alias con `source_run_id` real y `status=derivado_invariancia_verificada`. Se vuelve a comprobar la igualdad exacta de `forecast_evaluation.csv` y `opportunity_daily.csv` antes de aceptar ese alias. El desglose derivado no se presenta como una nueva ejecución BASE ni como un archivo archivado de Entrega 3.

H3 conserva los cortes 2022–2023 y enero de 2024–agosto de 2026. El veredicto descriptivo compara el cambio de oportunidad bruta elegible y el CAGR condicional: ambos menores, favorable; ambos mayores, contraria; sentidos distintos o empates, mixta; datos no definidos/incompletos, no concluyente. DECISION usa su costo ex ante contemporáneo, sin restarlo al forecast elegible.

Las limitaciones de `futures_scaled`, aproximaciones de funding/marcas, cobertura histórica parcial de reglas y ausencia de trayectorias intraminuto permanecen vigentes. La conservación de bytes de Entrega 3, la procedencia histórica, los cambios intencionales del código y la publicación en GitHub se verifican y reportan por separado.

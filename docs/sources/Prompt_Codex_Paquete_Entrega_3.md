# Prompt para Codex: preparar el paquete de redacción de la Entrega 3

Trabajá sobre el proyecto existente en `Backtesting`. La Entrega 3 se presenta el 20/09/2026. Prepará un paquete compacto, verificable y fácil de compartir, con los resultados y las figuras necesarios para redactar el informe académico. Ejecutá la preparación y entregá los archivos, no solamente otro plan.

La redacción y maquetación final se harán después, tomando la Entrega 2 como base y conservando los antecedentes de la Entrega 1. Tu tarea ahora es reunir evidencia, generar tablas y figuras desde las corridas guardadas y dejar claramente documentada la metodología efectivamente implementada.

## 1. Alcance cerrado para esta entrega

- Conservá `vwap_joint` como escenario principal. Usá el último reporte corregido posterior a la auditoría del basis, sus corridas y configuraciones verificadas.
- No cambies EWMA, horizonte, basis, costos, sizing ni ejecución. No abras una optimización ni nuevas sensibilidades. Los horizontes alternativos y cambios del filtro de basis quedan como próximos análisis de la Entrega 4.
- No descargues trades, aggTrades, ticks ni datos subminuto. La preparación del informe debe utilizar los artefactos ya disponibles.
- Reutilizá simulaciones verificadas. Regenerar tablas y gráficos no requiere volver a ejecutar los backtests completos. Si aparece un defecto demostrado que afecta resultados, documentalo y corregí solamente ese defecto, preservando la versión anterior y explicando cualquier simulación adicional indispensable.
- Respetá las instrucciones del repositorio y los archivos existentes. Todo archivo nuevo queda dentro de `Backtesting`; evitá una carpeta `Backtesting/Backtesting`.
- Si necesitás scripts auxiliares, mantenelos breves y claros, con comentarios y docstrings en inglés. Documentos explicativos, etiquetas y títulos de gráficos en español.

La Entrega 3 exige: implementación funcional, metodología, resultados preliminares, consistencia con las hipótesis, problemas detectados y próximos ajustes. No exige confirmar las hipótesis ni encontrar la parametrización más rentable.

## 2. Identificar las fuentes correctas

Localizá y leé los manifiestos, configuraciones efectivas, resultados, auditorías y los documentos académicos disponibles. Como referencia de identificación, los últimos archivos recibidos fueron:

- `execution_revision_report.md` corregido, revisión `revision_eb5ed744b30836a39fd694fa`.
- `basis_audit_report.md`, con 4.380 observaciones de mercado y 8.760 decisiones auditadas.
- Escenario principal temprano: `run_f4151cc97937f3704d77fb14`.
- Escenario principal tardío: `run_519a165818e2cadce24bc873`.

Verificá los identificadores contra los archivos reales. Si hay una versión posterior pertinente, explicá cuál utilizás y por qué. No mezcles configuraciones de una corrida con métricas de otra ni el reporte de rechazos anterior con el corregido.

Las ventanas son `[2022-09-01T00:00:00Z, 2023-09-01T00:00:00Z)` y `[2025-09-01T00:00:00Z, 2026-09-01T00:00:00Z)`. Cada estrategia reinicia 10.000 USDT y no hay continuidad de cartera entre ventanas.

Los antecedentes académicos son las consignas, la Entrega 1, la Entrega 2 y su feedback. La Entrega 2 ya integra idea, motivación, hipótesis y research inicial. Conservá los originales disponibles y no dupliques ese contenido al organizar la futura integración. Si un documento académico no está accesible en el proyecto, registralo y continuá con la preparación técnica; no inventes su contenido.

## 3. Preparar una base factual breve para la redacción

Creá `base_para_redaccion.md`, de aproximadamente 1.000 a 1.400 palabras como máximo, más tablas y referencias a archivos. Usá frases concretas y estas seis secciones:

1. **Implementación:** qué hace el motor, herramientas y versiones efectivamente utilizadas, activos, separación de carteras y fuente del registro económico. Describí el papel real de NautilusTrader si está integrado; no presentes una importación o un replay auxiliar como validación integral del motor.
2. **Metodología vigente:** períodos, calentamiento, capital, señal EWMA, costos, construcción y renovación de posiciones, ejecución por minuto, sizing conjunto y controles de riesgo. Distinguir observación de señales, ejecución y valuación.
3. **Resultados principales:** rendimiento, riesgo, P&L, actividad y capital utilizado en las cuatro carteras del escenario principal.
4. **Hipótesis:** evidencia de H1, H2 y H3, con su alcance real.
5. **Problemas y limitaciones:** ajustes implementados, concentración del resultado, restricciones de entrada y límites de datos y ejecución.
6. **Próximos análisis:** sensibilidad económica de horizonte y basis para la Entrega 4, identificada como pendiente y exploratoria.

Asociá cada cifra a su archivo, corrida, campo y filtro de selección en `fuentes_de_cifras.csv`. Obtené los números de artefactos de máxima precisión, no copiando tablas Markdown redondeadas. Conservá decimales originales en datos y redondeá solamente la presentación.

## 4. Documentar lo que cambió desde la Entrega 2

Generá `cambios_metodologicos.csv` con columnas de diseño anterior, implementación utilizada, motivo, implicación y fuente verificable. Incluí al menos:

- Muestra continua prevista desde 2022 frente a las dos ventanas anuales independientes realmente ejecutadas.
- Operaciones individuales frente a velas de un minuto, por viabilidad del volumen de datos.
- Última operación conocida frente a cierres de velas alineadas para señales y basis.
- Ejecución sobre la primera operación posterior frente a VWAP de la ventana posterior elegible, contabilizado al finalizar esa ventana.
- Demoras y vencimientos subminuto frente a las reglas temporales efectivas del modelo actual.
- Ejecución total frente al límite de participación del 1% y posibilidad de fills parciales.
- Cantidades calculadas secuencialmente frente al sizing conjunto previo a la apertura.
- Prioridad de eventos efectivamente aplicada en la implementación nueva.
- Reglas, tarifas, marks de funding y demás elementos históricamente observados frente a supuestos o proxies realmente usados.

La Entrega 2 preveía reconstruir reglas y costos según su vigencia histórica. El informe reciente reconoce supuestos prescritos y proxies causales de mark para funding temprano. Identificá exactamente su cobertura y procedencia. No conviertas un supuesto configurado en una tarifa histórica verificada ni un proxy en una observación exacta. Aclarar la cobertura es más útil que una afirmación general de datos perfectos.

Confirmá también las reglas financieras preservadas y que las dos estrategias comparten ejecución, sizing, riesgos y costos. La permanente omite el filtro de funding, pero conserva el de basis; no implica estar invertida continuamente.

## 5. Tablas y datos que necesito recibir

Generá estos archivos portables, con unidades y un diccionario de campos:

| Archivo | Contenido |
|---|---|
| `tablas/resultados_principales.csv` | Cuatro filas: ventana y estrategia, capital inicial, equity final, retorno neto, CAGR, Sharpe, drawdown diario, aperturas completas, ciclos cerrados, intentos fallidos y fills. |
| `tablas/pnl_componentes.csv` | P&L spot, futuros, funding, comisiones, liquidaciones y neto; slippage identificado como informativo, ya incorporado en precios. |
| `tablas/hipotesis.csv` | H1 por ventana, MAE de ambos pronósticos, observaciones y exclusiones; H2 con criterios y resultado; H3 con oportunidad y retorno por ventana. |
| `tablas/actividad_y_rechazos.csv` | Capital utilizado, tiempo cubierto, sin cobertura y polvo; filtros aplicables, diagnósticos no aplicados y rechazos secuenciales, con denominadores y unidades. Puede usar formato largo. |
| `tablas/cambios_metodologicos.csv` | Matriz de la sección anterior. |
| `tablas/basis_audit_summary.csv` | Resumen de la auditoría existente, por activo y ventana, con cobertura y discrepancias. |
| `tablas/episodio_2023_03_24.csv` | Cambio de equity diario, funding, fees, tiempos de cierre y exposición sin cobertura del episodio, para ambas estrategias principales. |
| `datos/equity_diaria.csv` | Fechas UTC, ventana, estrategia, run_id, equity y retornos diarios de las cuatro carteras, obtenidos de series persistidas. |
| `fuentes_de_cifras.csv` | Trazabilidad entre dato presentado y artefacto de origen. |

No confundas aperturas con ciclos cerrados. Una posición abierta al terminar la muestra puede generar P&L y funding sin completar un ciclo. No fuerces un cierre final. Separá polvo residual de carry activo y recordá que horas-activo pueden sumar exposición de dos símbolos.

Los ceros reales deben permanecer como ceros. Un Sharpe indefinido debe ser `ND` en la presentación y nulo con motivo en los datos, nunca cero. El drawdown diario no acota el riesgo intradiario.

## 6. Generar solamente dos figuras principales

Usá Matplotlib o la herramienta de gráficos que ya tenga el proyecto. Exportá PNG legible a 300 dpi y SVG, con títulos y ejes en español. Evitá texto minúsculo, leyendas superpuestas y decoración innecesaria.

1. **`equity_comparativa`:** dos paneles, uno por ventana, con condicional y permanente, usando las series diarias reales. Mostrá el capital inicial de 10.000 USDT y aclaración de reinicio independiente. Nunca conectes ambas ventanas ni reconstruyas curvas interpolando entre capital inicial y final.
2. **`pnl_comparativo`:** componentes del resultado de las cuatro carteras. Para facilitar la lectura, agrupá spot más futuros como resultado por precios; mantené funding y costos separados y señalá el neto. La tabla debe conservar spot y futuros por separado. No llames a todo el resultado por precios «funding» ni «basis puro» cuando existen cantidades distintas o períodos sin cobertura.

Guardá títulos, notas, definición y archivo de origen de cada figura en `figuras/notas_figuras.md`. Si una serie indispensable falta, recuperala de los artefactos persistidos y documentá cómo; no inventes puntos para completar el gráfico.

## 7. Interpretaciones que deben quedar claras

- H1: menor error de la EWMA es evidencia descriptiva en las ventanas analizadas. No demuestra significancia estadística ni rentabilidad.
- H2: distinguir resultado contrario al criterio en la ventana temprana de resultado no concluyente en la tardía, donde la condicional no opera y su Sharpe es indefinido.
- H3: la comparación entre estas dos ventanas no cubre continuamente 2024 ni identifica causalidad o una compresión estructural de todo el mercado.
- El costo del ciclo y el funding pronosticado se comparan en las mismas unidades. El reporte actual muestra costo 0,0034, equivalente a 0,34% o 34 bps; contrastá ese valor con la configuración.
- La auditoría confirmó el basis en los instantes de decisión. El porcentaje de basis negativo no representa automáticamente todos los minutos del año ni precios bid/ask simultáneamente ejecutables.
- El defecto corregido tras la auditoría afectaba el conteo de rechazos de funding en la permanente, no las operaciones. El reporte se regeneró sin resimular; describí ese alcance.
- Calculá con precisión la fracción del beneficio anual correspondiente al cambio de equity del 24/03/2023. Es una comparación de P&L diario y anual, no atribución causal a un fill ni un resultado obtenido al eliminar el episodio. Si el beneficio anual es cero o negativo, señalá que esa interpretación porcentual no resulta apropiada.
- Reconocé el número reducido de operaciones, las aproximaciones de ejecución, los proxies, las garantías segregadas y el riesgo direccional durante desarmes. No certifiques todo el motor a partir de la conciliación contable o de la auditoría del basis.

Incluí las variantes de ejecución ya realizadas como antecedentes o anexo técnico. El cuerpo del informe debe concentrarse en `vwap_joint`; no elijas otra variante porque tenga mayor retorno.

## 8. Organizar los antecedentes para la entrega final

Creá `indice_integracion.md` que proponga una estructura acumulativa: idea y motivación, hipótesis, research, diseño, implementación efectiva y cambios, resultados preliminares, limitaciones, y próximos análisis. La Entrega 2 es la referencia más reciente de diseño y ya contiene los antecedentes de la Entrega 1.

Indicá qué material existente se conserva, qué se resume y qué sección nueva corresponde a la Entrega 3. No pegues ambos documentos completos uno detrás del otro ni repitas sus bibliografías. No atribuyas a las entregas anteriores decisiones tomadas después de ver resultados.

Copiá los documentos académicos originales disponibles a `antecedentes/`, manteniendo su contenido y autoría. Conservá la bibliografía existente con su procedencia, sin agregar referencias inventadas. Si no están accesibles, listá los faltantes en el LEEME; la preparación de resultados puede continuar.

No redactes todavía un Whitepaper final ni des por completada la Entrega 4. El documento académico posterior integrará lo realizado hasta la Entrega 3, con explicaciones concisas y sin repetir innecesariamente el diseño anterior.

## 9. Verificación y entrega compacta

Antes de empaquetar:

- Comprobá que cifras, tablas y figuras correspondan a las mismas cuatro carteras y a sus configuraciones.
- Reconciliá equity final menos capital inicial con P&L por componentes usando precisión original y la tolerancia contable vigente. No restes slippage dos veces.
- Contrastá las métricas calculadas desde las series diarias con las persistidas y explicá cualquier diferencia. No sustituyas silenciosamente una convención de cálculo.
- Confirmá la exclusión del filtro de funding en los rechazos operativos de la permanente y la inclusión de observaciones de basis igual a cero como elegibles.
- Inspeccioná visualmente las dos figuras exportadas. No inventes validaciones ni presentes pruebas anteriores como ejecutadas ahora.
- Registrá comandos de esta preparación, resultados de verificaciones y limitaciones en `verificacion.md`. Reutilizá pruebas existentes relevantes; no amplíes innecesariamente la batería ni reconstruyas la arquitectura.

Guardá los archivos en `entregas/entrega_3/paquete_redaccion/` o un directorio equivalente coherente con el proyecto. Si ya hay un paquete, creá una versión nueva sin borrar el anterior.

Incluí `LEEME.md`, con orden de lectura, inventario, unidades, referencias a configuraciones, versiones y comandos efectivos para reproducir las tablas y figuras. Incluí el script o comando existente necesario y sus dependencias. Aclarar que reproducir el backtest completo requiere el proyecto y sus datos, mientras que las figuras deben poder reproducirse con el subconjunto entregado.

Agregá en `evidencia/` copias del reporte de ejecución corregido, la auditoría del basis, las configuraciones efectivas y los manifiestos pertinentes. Usá enlaces relativos dentro del paquete; no dependas de rutas `D:\` para leer sus tablas o figuras.

Entregá `paquete_redaccion_entrega_3.zip`. Excluí datasets masivos, ZIP de mercado, entornos virtuales, cachés, secretos y carpetas Git. Conservá los artefactos completos en sus ubicaciones originales y sus hashes en el manifiesto. El paquete compartido debe ser pequeño y contener la evidencia necesaria para escribir, verificar y graficar los resultados.

En tu respuesta final indicá la ruta del ZIP, qué verificaste y si hay algún faltante que afecte la redacción. Distinguí claramente preparación de reportes de nuevas simulaciones. No vuelvas a sugerir cambios de parámetros antes de cerrar esta entrega.

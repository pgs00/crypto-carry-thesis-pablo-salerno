# Protocolo técnico de la distribución B6 del 10/10/2026

Esta distribución documental conserva la ejecución y evidencia científica de B6. Sustituye instrucciones al asistente y notas operativas por esta descripción técnica. Las configuraciones, código económico, protocolo congelado, corridas, cifras, tablas, réplicas y tolerancias permanecen sin cambios de bytes. La identidad nueva corresponde a la distribución documental y no a una nueva ejecución económica.

## Estabilidad temporal

La matriz cerrada comprende I2023 e I2024, cada uno con estrategia condicional y permanente: cuatro cuentas nuevas. Inicios UTC 2023-01-01 y 2024-01-01; fin exclusivo 2026-09-01; 10.000 USDT iniciales por cartera. Se trata de reinicios desde efectivo sin inventario, deuda, reservas, órdenes o ciclos heredados. No equivalen a recortar o reescalar una curva iniciada en 2022.

Cada configuración procede de BASE y sólo altera start. Mantiene history_start original, precarga efectiva de 360 horas, ventana 336 horas, vida media 24 horas, horizonte/tenencia 168 horas y funding disponible 60 segundos después. La precarga prepara información; no genera operaciones o patrimonio antes del inicio. La primera apertura sigue las condiciones normales. Se mantienen VWAP, joint_quantity, selección 34 pb, activos, márgenes, costos, redondeos y controles BASE; shocks y demoras permanecen apagados.

Cada cuenta nueva se compara con el tramo coincidente de BASE continua, con su patrimonio e inventario reales heredados. Retornos y CAGR365 utilizan sus respectivos denominadores; un índice 100 sólo es una visualización. Se conservan Sharpe RF=0, drawdown diario, P&L/componentes, capital utilizado, actividad sin polvo y ejecución. Años completos, 2026 parcial y cortes parcialmente cubiertos se identifican por fechas efectivas. No existen filas cero anteriores al inicio. H2 compara ambas estrategias del mismo inicio y período. H3 original conserva BASE continua porque los nuevos inicios no cubren el régimen original completo 2022–2023. Estos inicios ya observados no constituyen validación fuera de muestra.

## Bootstrap BASE fijado antes del cálculo

El bootstrap utiliza sólo retornos diarios, oportunidades diarias y errores de pronóstico BASE autenticados. No ejecuta el motor ni agrega las variantes o escenarios hipotéticos B5 como nuevas observaciones históricas.

El método es de bloques circulares emparejados, estratificados por año calendario y segmentos contiguos. Dentro de cada segmento anual se sortean inicios uniformes, se toman bloques consecutivos con vuelta dentro del mismo segmento y se trunca a su número original de días. Se mantienen el orden y tamaño de los años al concatenarlos. No se cruza circularmente de 2026 a 2022 ni se pegan huecos desconocidos.

Longitud principal 28 días; sensibilidades 14 y 56 días; 5.000 réplicas por longitud. Intervalos percentiles marginales nominales 95%, cuantiles 0,025 y 0,975, método lineal. Semilla raíz 20261001 con PCG64 y SeedSequence; flujos por identificadores estables de longitud, réplica y estrato, independientes del PID u orden de ejecución. El lote congelado es 128 y el umbral mínimo de evaluabilidad es 0,95, tal como consta en [protocolo_ejecucion.json](protocolo_ejecucion.json). Esos valores son decisiones del estudio; la documentación del método no prescribe su elección.

El eje diario UTC conserva cobertura y motivos. Los mismos índices seleccionan ambas carteras, activos, oportunidades y errores. H1 mantiene sumas de errores absolutos emparejados y conteos válidos por día/activo; recalcula MAE_EWMA − MAE_no_change por activo y promedio BTC/ETH 50/50. Los targets del borde final conservan sus exclusiones. No se promedian medias diarias sin ponderar ni se reconstruyen targets futuros enlazando bloques remuestreados.

H2 recalcula CAGR condicional y Sharpe_condicional − Sharpe_permanente desde retornos diarios, incluidos días inactivos; usa compuestos, anualización 365 y ddof original. El veredicto histórico exige CAGR condicional positivo y Sharpe superior. H3 conserva la diferencia de oportunidad media y CAGR condicional entre 2024–agosto 2026 y 2022–2023, con días/pesos originales y oportunidad en pb/168 h. Oportunidad y retornos alineados se remuestrean juntos.

Los efectos e intervalos corresponden a la muestra total y cortes originales; años y variantes no abren familias adicionales de intervalos. Sharpe indefinido permanece ND; no se reemplaza por cero, se descartan réplicas silenciosamente ni se generan réplicas hasta conseguir una cantidad válida. Si aparece degeneración, los cuantiles finitos son condicionales a evaluabilidad; menos del 95% de réplicas válidas implica intervalo principal ND y diagnóstico.

La circularidad es una convención estadística, no continuidad histórica. La estratificación conserva composición anual, supone estabilidad aproximada dentro de cada estrato y corta dependencia entre años. Los intervalos no garantizan cobertura exacta; dos marginales del 95% no forman un contraste conjunto del 95%. Las frecuencias bootstrap no son probabilidades de verdad de H1/H2/H3 ni de ganancia futura. Se conservan límites por pocos ciclos, inactividad, selección histórica y supuestos del método.

## Cálculo, comprobaciones y síntesis

El análisis estadístico usa NumPy float64 con agregación diaria de sumas/conteos y cálculo vectorizado. La contabilidad y fills conservan Decimal y tolerancia 1E-8 USDT. Los controles escalares, identidad serial/paralela, casos ND, huecos/años, compuestos y adulteraciones se conservan en la evidencia original. El verificador recalcula desde insumos compactos las métricas financieras y el bootstrap; no se limita a leer tablas finales. Los parámetros y código de ejecución conservan identidades congeladas; no se actualizan dependencias para esta distribución.

La síntesis relaciona BASE, B1–B5, nuevos inicios e incertidumbre. Conserva las excepciones H2 acreditadas, diferencia SOFR hipotética bruta de costos netos modelados y separa drawdown diario, intradía global y ventanas locales. El diagnóstico B2/B3 utiliza logs/estados guardados y la condición de activación de liquidation_pending, no sólo la ausencia de fills de liquidación. Su cobertura específica no equivale a equivalencia universal ni a nuevos replays.

## Fecha del estado documental y PDF final

[sintesis.md](sintesis.md), [fuentes/sintesis_estado.json](fuentes/sintesis_estado.json) y [matriz_cumplimiento.csv](matriz_cumplimiento.csv) son registros científicos históricos del cierre B6. Sus referencias a revisión transversal y Word/PDF pendientes describen ese momento y se conservan porque el verificador reproduce exactamente esa síntesis. No representan la disponibilidad actual del documento final.

El PDF final existe en el repositorio en `entregas/entrega_4/documento_final/Tesina_Entregas_3_y_4_Pablo_Salerno.pdf`, SHA-256 `f98df37bee61164948e2b26537c6aadebf77335aa60b37ceace27ffa029ea3fb`. No forma parte del sello B6 histórico ni de esta distribución compacta. Los certificados B6 anteriores no verificaron su contenido, su redacción final ni su publicación. Esta nota identifica el archivo actual y su hash; no amplía retrospectivamente el alcance científico o documental de aquella verificación.

## Identidad y verificación portable

[La derivación](procedencia/derivacion.json) enumera omisiones, adaptaciones y agregados frente al [manifiesto original](procedencia/manifiesto_original.json). El protocolo congelado conserva el hash del encargo retirado como antecedente histórico; la adaptación estructural sólo admite esa omisión explícita. Todos los restantes miembros científicos conservan hash y tamaño originales. El nuevo manifiesto identifica la distribución del 10/10/2026.

La verificación utiliza las dependencias fijadas incluidas en herramientas, sin Git, red, datos masivos ni motor económico. Conserva el recálculo contable, bootstrap y síntesis, las identidades de cuatro carteras y cero replays BASE. Las particiones masivas no se releen; su identidad y extractos mínimos conservan el alcance declarado original. El certificado nuevo se escribe fuera del paquete e identifica su nuevo sello. Los certificados históricos mantienen su significado original.

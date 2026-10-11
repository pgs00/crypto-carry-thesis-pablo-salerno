# Protocolo técnico de la distribución B5 del 10/10/2026

Esta distribución documental conserva los resultados y las especificaciones científicas de la ejecución del 30/09–01/10/2026. Su nueva identidad corresponde al retiro de instrucciones de trabajo del asistente, planes y estados de coordinación. No corresponde a nuevas corridas, nuevos supuestos ni nuevas cifras.

La especificación económica completa permanece, con sus bytes y aprobación originales, en [protocolo_tecnico.md](protocolo_tecnico.md), [protocolo_propuesto.json](protocolo_propuesto.json), [especificaciones_ejecutables.json](especificaciones_ejecutables.json), [aprobacion_recibida.json](aprobacion_recibida.json) y [protocolo_ejecucion.json](protocolo_ejecucion.json). La redacción «pendiente» de la ficha preparatoria corresponde a su fecha de emisión; la aprobación posterior tiene identidad propia.

## Alcance científico preservado

SH_P90, SH_MAX y CF_SIN_INTERRUPCION son tres escenarios independientes, con las estrategias condicional y permanente bajo el mismo mercado dentro de cada escenario: seis carteras económicas. CONTROL_APAGADO y CONTROL_CERO son cuatro carteras técnicas aparte. Los controles BASE originales/corregidos y los intentos técnicos anteriores conservan sus identidades. La muestra continua UTC es [2022-01-01, 2026-09-01), con 10.000 USDT iniciales por cartera, BTCUSDT/ETHUSDT y configuración efectiva BASE. No hay combinación con demoras, precios OHLC4, costos estresados, capitales alternativos o caja remunerada.

La calibración descriptiva P90/máximo del spot descubierto conserva población, ceros, percentil lineal, fracciones y distinción entre valoración original y proxy. No representa probabilidades futuras ni calibración conocida en 2022. El calendario de shocks es retrospectivo y fijo. La envolvente máxima evita componer shocks solapados; la recuperación impuesta dura 60 minutos y no depende del cierre de una posición. La perturbación afecta spot con futuros/mark/funding intactos y también modifica la relación entre mercados. No constituye una prueba general de resistencia del corto ante subas.

El contrafactual sustituye sólo las 306 claves BTC/ETH spot de aperturas [11:27,14:00) UTC del 24/03/2023. Conserva el ancla 11:26 disponible 11:27, precios ligados a futuros mediante el cociente anterior y volumen spot hipotético mediano por hora UTC de los días 22 y 23/03. No usa información posterior a la reapertura, ni volumen de futuros como volumen spot. Cada vela está disponible a su final; la reapertura recupera la fuente observada sin suavizar el salto. La trayectoria completa permite cambios de decisiones, inventario, ejecución, garantías y funding monetario. Es un escenario hipotético condicionado, sin identificación causal de cuánto beneficio real produjo la interrupción.

## Interfaz, auditoría y convenciones

La capa se sitúa entre fuentes autenticadas y eventos consumidos. El registro de intervención conserva original, valor modificado, fórmula, unidad, escenario, intervalo y disponibilidad. Señal, ejecución y valoración usan una referencia transformada coherente; la edad y procedencia de una referencia antigua se mantienen. Un precio de valoración durante suspensión no habilita transacciones. La excepción de cobertura CF se limita a sus 306 claves; fuera de ellas permanecen los controles originales.

La secuencia causal es funding, fills comprometidos, riesgo/estado, reintentos y decisiones. Sizing anterior no utiliza el cierre final de su propia ventana. OHLC, VWAP, quote/base, actividad, tick/step, comisiones, reservas, deuda y participación conservan las reglas originales. Factor uno conserva la representación exacta del MinuteBar; el incidente del primer control cero y la nueva identidad están en los controles. Para las velas derivadas el auditor admite exclusivamente dos unidades del último decimal del contexto original por multiplicación/división; no recorta fuentes ni amplía tolerancias.

H1 mantiene cohortes, disponibilidad y targets autenticados. H2 exige CAGR condicional positivo y Sharpe superior al permanente para el mismo escenario/período. H3 se calcula desde el mercado común modificado, con su cobertura, unidades y testigos. Los ocho períodos heredan los saldos reales. La conciliación financiera conserva Decimal y tolerancia 1E-8 USDT. ND conserva su motivo; no se fuerza insolvencia o cobertura parcial a terminar artificialmente.

Los diagnósticos intradía cubren ventanas intervenidas y bordes, no un máximo intradía global de toda la muestra. La recuperación impuesta se separa de P&L realizado; no se suma por segunda vez al ledger. Mantenimiento, saldo, holgura, necesidad preventiva y faltante externo son conceptos distintos. Caja bruta no equivale a disponible; las reservas no acreditadas conservan ND/cotas. No se inyecta capital ni se suman máximos no simultáneos.

## Procedencia y coordinación histórica

El cambio de coordinación del 01/10/2026 utilizó procesos completos por cartera, locks exclusivos y fuentes de sólo lectura; no dividió años o activos. Reutilizó controles y carteras terminadas con identidad compatible. Un intento SH_P90 permanente interrumpido sin salida final ni checkpoint recuperable conserva su log/estado y no cuenta como otro resultado económico. Los límites operativos de memoria, PID y estimaciones del lanzamiento eran datos de coordinación, no parámetros del estudio.

Los controles reales, logs, revisiones emitidas, incidencias y resultados se conservan. El retiro de planes no altera esas evidencias. Las pruebas de frontera, causalidad, suspensión, solapamientos, liquidación y checkpoints, junto con las comparaciones exactas de controles y las pruebas de adulteración, se consultan en los registros originales. Las cuentas de pruebas de etapas distintas no se suman como si fueran conjuntos disjuntos.

## Verificación de esta distribución

[La derivación](procedencia/derivacion.json) registra los archivos omitidos y adaptados frente al [manifiesto original](procedencia/manifiesto_original.json). El contrato congelado conserva los hashes originales de documentos retirados; esos hashes son referencias históricas, no una afirmación de que sus bytes sigan incluidos. La adaptación estructural sólo reconoce las omisiones documentales explícitas. Todo miembro científico retenido debe conservar hash y tamaño originales; siguen activos los controles de corridas, contabilidad, ejecución, tablas y documentos científicos.

El verificador recalcula únicamente análisis desde entradas compactas incluidas, sin motor económico, red o datos masivos. La pertenencia original de extractos a particiones masivas, validez histórica de fuentes y oportunidad minuto a minuto fuera de los testigos conservan el alcance limitado del informe histórico. La nueva verificación debe identificar el nuevo manifiesto; los certificados anteriores siguen correspondiendo a sus sellos anteriores.

## Evidencia técnica de procedencia B4

Los registros `controles/inventario_limpieza.json`, `controles/blobs_limpieza.json`, `controles/comparacion_paquetes_b4.json` y `tablas/inventario_limpieza.csv` conservan rutas, tamaños, hashes y comparación de los antecedentes B4. `controles/aislamiento_limpieza.json`, `controles/v2_sin_anterior.json` y `controles/enlaces_copia_aislada.json` conservan el ensayo aislado y su alcance. Ese ensayo autentica el informe de comparación preservado; reproducir sus 1.200 comparaciones exige los bytes del antecedente B4 identificado por su manifiesto. Los datos de respaldo están en `controles/respaldo_caches.json`. Estos registros técnicos permanecen idénticos; la propuesta administrativa de acciones de limpieza se retira de esta distribución.

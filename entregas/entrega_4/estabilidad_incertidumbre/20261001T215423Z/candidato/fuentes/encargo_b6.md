# Codex: bloque 6, estabilidad temporal, incertidumbre y síntesis

Trabajá en `pgs00/crypto-carry-thesis-pablo-salerno`, proyecto Backtesting.

## 1. Resultado esperado y límites

Completá el último bloque analítico: **dos fechas iniciales alternativas para ambas estrategias, incertidumbre sobre BASE y síntesis de los bloques terminados**. Implementá, ejecutá y verificá, no devuelvas solamente un plan.

El envío de este encargo autoriza las cuatro carteras y el protocolo estadístico explícito de abajo. Los nuevos parámetros estadísticos son decisiones de este encargo, no requisitos numéricos del profesor. Fijalos antes de calcular resultados; no hace falta otra aprobación salvo contradicción material, defecto económico o ampliación del alcance.

Prioridades: preservar resultados, reutilizar trabajo válido, aprovechar Ryzen 7/32 GB RAM y reducir supervisión del modelo. No repitas los bloques 1 a 5. No cambies el motor, no migres a GPU y no construyas otro framework de investigación. No generes Word/PDF todavía.

## 2. Referencias y lectura acotada

Identificá raíz, rama, HEAD, intérprete, núcleos físicos, datos, recursos y cambios ajenos. Último commit revisado: `c25efa189cdf4c509d4f571756cb9bd8b6776a08`; no retrocedas automáticamente ni descartes cambios posteriores.

Partí de `docs/entrega_4/matriz_avance.csv` para localizar versiones vigentes. Leé los resúmenes, índices y certificados necesarios, no todos los paquetes íntegros de nuevo.

- BASE originales: `run_ad71d751b20623006c195ff3` y `run_dfea4b7ac1475668d5968c97`.
- Controles BASE corregidos: `run_d7c7cb5da666e22321598598` y `run_415276e8a8b5bb9101e2d13b`.
- Bloque 5 vigente: `entregas/entrega_4/estres_contrafactual/20260930T214617Z/paquete_20261001T211248Z/`; controles finales en su carpeta hermana. Reutilizá sus referencias autenticadas y el registro de compatibilidad.
- Recuperá la definición corregida de exposición/H2 y las convenciones financieras desde sus helpers vigentes. El feedback pide riesgo intradía/garantías, desglose anual y retorno junto al capital utilizado; esos bloques no se vuelven a simular aquí.
- Consultá el encargo general `Prompt_Codex_Entrega_4.md` y la consigna si están disponibles. No afirmes haber leído documentos ausentes.

Inspeccioná selectivamente `scripts/signal_sensitivity.py`, `scripts/continuous_delivery/`, `scripts/rules_sensitivity_h2.py`, `scripts/verify_rules_sensitivity_package.py`, los módulos de integridad y los auxiliares de ejecución/ledger. `src/crypto_carry/robustness.py` ya enumera inicios 2023/2024, pero su función general vuelve a correr BASE y otras variantes: **no ejecutes su matriz predeterminada**.

## 3. Recursos: ejecución automática desde el principio

**Sólo cuatro backtests nuevos previstos. Cero replays BASE completos por defecto.** No agregues otra tanda de cuatro controles apagado/cero: aquí no se introduce una capa económica de escenarios.

Reutilizá el patrón de `scripts/coordinate_stress_counterfactual.py` mediante un lanzador B6 pequeño y separado. No alteres sus constantes B5 ni sus copias selladas. Necesitamos cola de tareas, procesos independientes, bloqueo único, estado persistido y comandos reanudables; nada más.

- Objetivo: **cuatro carteras simultáneas**, si núcleos físicos y recursos reales lo permiten. Presupuesto inicial: 4 GiB por trabajador, contando su posible crecimiento, y al menos 6 GiB libres para sistema y margen. Son límites operativos, no mediciones prometidas.
- Subí rápidamente de dos a cuatro mientras las primeras corridas avanzan; no esperes que una termine para comprobar si puede comenzar otra. Si ya hay mediciones válidas de esa ruta, utilizalas. Reducí lanzamientos ante presión de memoria, paginación o caída del avance agregado, sin matar corridas útiles.
- Bootstrap y síntesis pueden trabajar mientras corren los backtests, con uno o dos procesos analíticos si cabe en el mismo presupuesto. Máximo seis procesos de trabajo totales y sin superar núcleos físicos útiles. No crear seis backtests para ocupar el equipo.
- Por trabajador, antes de importar bibliotecas: `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`, `PYTHONDONTWRITEBYTECODE=1`, `MPLBACKEND=Agg`. Registrá el entorno. Limitá también pools Arrow si se comprueba sobreasignación; no supongas que una variable controla todas las bibliotecas.
- Una cartera por proceso, salidas y logs exclusivos, fuentes sólo lectura. Nunca paralelices años o activos dentro de una misma cartera. Un único coordinador actualiza índices; usá escritura atómica y bloqueo para evitar duplicados.
- Detectá procesos existentes por PID, creación y comando, no sólo por nombre. No iniciar un segundo coordinador. Reutilizá carteras terminadas únicamente con identidad y controles compatibles; reanudá sólo checkpoints completos y compatibles.
- Autenticá una vez las entradas y dependencias efectivamente utilizadas. Compartí un inventario inmutable entre trabajadores; revalidá si cambia una entrada. No volver a recorrer todo el repositorio ni recalcular las mismas fuentes por cada réplica estadística o cambio de texto. No omitas la identidad exigida por el runner existente.
- No hagas profiling o pruebas completas sólo para estimar tiempos. Medí mientras avanza trabajo útil: tiempo por etapa, progreso, memoria y rendimiento agregado. Estimación separada de desarrollo, cálculo y verificación; el objetivo de una hora no autoriza recortar análisis ni prometer tiempos sin medición.

**Sin vigilancia conversacional:** generá un comando real de PowerShell externo que ejecute la cola y encadene posprocesamiento/verificación cuando estén listos. Sin llamadas al modelo/API durante la espera, sin `Get-Content` repetitivo desde el asistente. El proceso local puede guardar progreso cada 30-60 s. Si faltara esperar, dejá un traspaso explícito con PID o comando, estado y cómo retomar; no prometas actuar después de cerrar la respuesta. No cambies globalmente energía, seguridad o configuración del equipo.

## 4. Matriz cerrada de fechas iniciales

| ID | Inicio económico UTC | Fin exclusivo UTC | Capital inicial | Estrategias |
|---|---|---|---|---|
| I2023 | 2023-01-01 00:00:00 | 2026-09-01 00:00:00 | 10.000 USDT | condicional y permanente |
| I2024 | 2024-01-01 00:00:00 | 2026-09-01 00:00:00 | 10.000 USDT | condicional y permanente |

Son **reinicios económicos reales desde efectivo**, sin inventario, deuda, órdenes, reservas o ciclos heredados. No equivalen a recortar una curva iniciada en 2022 ni a reescalarla.

Derivá cada configuración de la efectiva BASE. Único campo económico alterado: `start`. Conservá `history_start` y demás parámetros BASE; la precarga efectiva de mercado es de **360 h anteriores al nuevo inicio** (`window_hours + 24`), con ventana 336 h, vida media 24 h, horizonte/tenencia 168 h y disponibilidad de funding 60 s. La precarga prepara información, nunca genera operaciones o patrimonio anterior al inicio. Aplicá las condiciones normales al comienzo, sin imponer una apertura inmediata.

Reutilizá la ruta de `GapAuditedBacktest`, reglas prescritas y lector de minutos equivalente a `signal_sensitivity.simulate`, con el motor corregido actual. Shocks y demoras apagados, VWAP y joint_quantity BASE, costos originales, selección 34 pb, mismos activos, márgenes, cantidad, redondeos y controles. No adoptar H336, A100, L01 ni otras variantes favorables.

Probá primero con fixtures: ventana de precarga, ausencia de movimientos previos, primer funding disponible, primer fill admisible y límites de fechas. No incorporar estadísticas B6 a `src/`: mantener estable la identidad económica y evitar invalidar corridas por modificar sólo análisis.

## 5. Comparación justa de fechas

Por cada nuevo inicio, calculá también desde evidencia preservada el **tramo coincidente de BASE continua**, con su patrimonio e inventario reales al inicio del tramo. Distinguí visualmente:

1. Cuenta nueva con 10.000 USDT y posiciones vacías.
2. Tramo de cuenta continua iniciada en 2022, con saldos heredados.

Compará retornos sobre sus respectivos denominadores, CAGR365, Sharpe RF=0, drawdown diario, P&L/componentes, capital utilizado, actividad sin polvo y ejecución. Una curva rebajada a índice 100 sólo sirve para visualizar; no simula una nueva cartera ni hace comparables directamente sus P&L monetarios.

Publicá muestra disponible, años completos y 2026 parcial. No crear filas cero anteriores al inicio. Un corte parcialmente cubierto debe mostrar fechas reales y no llamarse período original completo. H2 compara ambas estrategias del mismo inicio y período. **No validar H3 original con I2023/I2024:** falta parte o todo el régimen 2022-2023. Su comparación original permanece en BASE continua.

No exigir igualdad entre cuentas nuevas y tramos heredados: justamente medimos esa dependencia. Toda la historia ya fue examinada; estos inicios alternativos no son validación fuera de muestra.

## 6. Incertidumbre: sólo posprocesamiento de BASE

No ejecutar el motor dentro del remuestreo. Utilizá exclusivamente retornos diarios, oportunidades diarias y errores de pronóstico BASE autenticados. No aplicar bootstrap a todas las variantes ni convertir escenarios hipotéticos B5 en observaciones históricas adicionales.

### Protocolo fijado antes del cálculo

Usá **bootstrap de bloques circulares emparejados, estratificado por año calendario**. Dentro de cada año/tramo contiguo, se sortean inicios uniformes, se toman bloques consecutivos con vuelta del final al inicio de ese mismo tramo y se trunca al número original de días. Se mantienen el orden y tamaño de los años al concatenarlos; no se cruza circularmente de 2026 a 2022.

La circularidad es una convención de remuestreo, no contigüidad real. Estratificar por año mantiene la composición histórica, pero supone estabilidad aproximada dentro de cada estrato y corta dependencia entre años. No afirmar cobertura exacta ni que elimina toda no estacionariedad. Las decisiones siguientes son del estudio:

- Longitud principal: **28 días**; sensibilidad metodológica: **14 y 56 días**. Cubren varias semanas frente a objetivos de funding a 168 h, sin garantizar que toda dependencia quede capturada. No seleccionar la longitud que produzca una conclusión favorable.
- **5.000 réplicas por longitud**, mismas réplicas emparejadas para todas las estadísticas compatibles; no 5.000 backtests. Intervalos percentiles marginales nominales del **95%**, cuantiles 0,025/0,975 con método lineal.
- Semilla raíz **20261001**, `PCG64` y `SeedSequence`. Derivá flujos por IDs estables de longitud, réplica y estrato, no por PID, orden de finalización o número de workers. Versioná el esquema y probá identidad serial/paralela.
- Producí los efectos BASE para muestra total y los dos cortes originales. Los años permanecen como desglose descriptivo; no abrir una familia extra de intervalos por cada año y variante.

### Emparejamiento y métricas

Construí un eje diario UTC auditable. Los mismos índices seleccionan simultáneamente ambas carteras, activos, oportunidades y errores. No muestrear condicional/permanente por separado. No suprimir huecos y pegar fechas distantes como si fueran contiguas. Segmentar por huecos verdaderos, conservar cobertura y motivos; un dato desconocido no es cero ni cash. Identificá aparte las exclusiones de targets H1 en el borde final.

**H1:** conservar por día y activo sumas de errores absolutos emparejados y conteos válidos. Recalcular `MAE_EWMA - MAE_no_change` con la población original de cada activo y promedio BTC/ETH 50/50. No promediar medias diarias sin ponderar cuando cambian los conteos. Mantener juntas las observaciones de funding del mismo día y el solapamiento dentro de los bloques. Un error negativo favorece descriptivamente EWMA. No reconstruir targets futuros pegando tasas de bloques remuestreados.

**H2:** para cada réplica obtener CAGR condicional y diferencia `Sharpe_condicional - Sharpe_permanente` con retornos diarios, incluidos días inactivos. Recalcular compuestos desde retornos, no promediar CAGR; usar anualización 365 y definición/ddof original de Sharpe RF=0. El veredicto histórico sigue exigiendo CAGR condicional positivo y Sharpe superior. Los intervalos complementan, no redefinen H2.

**H3:** con cada réplica obtener diferencia de oportunidad media y diferencia de CAGR condicional entre 2024-agosto de 2026 y 2022-2023, conservando cantidad de días y pesos de cada período. Remuestrear conjuntamente oportunidad y retornos cuando estén alineados. Preservar la definición de oportunidad en pb/168 h y el contraste original. No mezclar años para inventar un régimen distinto.

Reportar efecto puntual, intervalos, población/fechas, tamaño de bloques y frecuencia de réplicas no evaluables. No reemplazar Sharpe indefinido por cero, descartar silenciosamente réplicas ni seguir generando hasta obtener 5.000 válidas. Si hay degeneración, los cuantiles finitos deben rotularse como condicionales a evaluabilidad; con menos del 95% de réplicas válidas, dejar el intervalo principal ND e informar el diagnóstico. Ese umbral es una regla de presentación, no un teorema estadístico.

Conservar límites: pocos ciclos, días inactivos, selección histórica de parámetros y supuestos del método. Dos intervalos marginales al 95% no constituyen un contraste conjunto al 95%. No interpretar frecuencias bootstrap como probabilidad de verdad de H1/H2/H3 ni probabilidad de ganancia futura. No añadir búsqueda de valores p, optimización, SPA o nuevas simulaciones por iniciativa propia.

### Costo del cálculo

Carga los insumos una vez; agregá funding por día conservando sumas/conteos. Usá NumPy float64 en el análisis estadístico, lotes de 128-256 réplicas y reducciones vectorizadas. La contabilidad y los fills conservan Decimal y tolerancia original. No crear DataFrames ni leer Parquet dentro de cada réplica. Guardá estadísticas por réplica e IDs/semillas, no copias completas de precios o carteras.

Calculá una versión escalar pequeña de control y comparala con la vectorizada; el punto original debe coincidir con los helpers existentes a precisión numérica documentada. Repetir sólo el cálculo estadístico es barato frente a nuevos replays. No instalar PyTorch/CUDA o actualizar el entorno para esta tarea.

Referencias primarias a consultar de forma acotada y registrar en el reporte:
- https://bashtage.github.io/arch/bootstrap/generated/arch.bootstrap.CircularBlockBootstrap.html
- https://bashtage.github.io/arch/bootstrap/timeseries-bootstraps.html
- https://numpy.org/doc/stable/reference/random/parallel.html
- https://numpy.org/doc/stable/reference/global_state.html

La documentación respalda el mecanismo, no nuestros valores de 28/14/56 días, 5.000 réplicas ni la estratificación anual. No es obligatorio instalar `arch`: puede implementarse el algoritmo explícito en NumPy con fixtures independientes. Usá las versiones fijadas del proyecto y verificá compatibilidad, sin actualizarlas a las versiones de páginas web.

## 7. Síntesis y pendiente del error anterior

Prepará una síntesis breve integrable, no el documento final completo. Una tabla por pregunta relaciona evidencia BASE, sensibilidad de bloques 1-5, inicios B6, incertidumbre, límites y estado de comprobación. Usá IDs/versión de cada cifra, sin volver a calcular todos los bloques.

Conservá las excepciones favorables a H2 cuando los archivos las acrediten: períodos H336, A100 y L01, y períodos del contrafactual. No generalizar el resultado total a todos los años ni elegir un ganador. Distinguir SOFR hipotética bruta, costos netos modelados y riesgo no comparable. Mantener separado drawdown diario, intradía global previo y ventanas locales.

El alcance del defecto corregido de liquidación sobre B2/B3 no está resuelto por la igualdad de BASE. Hacé sólo un diagnóstico dirigido de logs/estados ya guardados: escalada de liquidación seguida de timeout, reintento ordinario o vuelta a HOLDING con corto remanente. La ausencia de fills etiquetados como liquidación no basta. Si los registros demuestran que la rama relevante no pudo activarse, documentá cobertura y criterio; si no alcanzan, dejá el punto pendiente con los run_id afectados o indeterminados. **No autoriza repetir B2/B3 dentro de B6.** Ese pendiente debe condicionar las conclusiones que dependan de ellas, no ocultarse para declarar la entrega completa.

## 8. Validaciones suficientes, sin repetir por rutina

Antes de los cuatro replays: autenticación de referencias necesarias, igualdad del código económico y pruebas pequeñas de inicio/precarga/aislamiento. Si el motor permanece intacto y la ruta es la ya validada, reutilizar compatibilidad demostrada. Si aparece una discrepancia, no forzar equivalencia ni lanzar controles completos nuevos sin justificar la necesidad.

Cada corrida nueva debe conciliar ledger, funding, fees, posiciones, patrimonio diario y períodos a `1E-8` USDT. Reutilizar auditoría vigente de fills, ventanas y participación sobre sus registros; exportar las fuentes mínimas correspondientes. Mantener insolvencia, cierres parciales y ND, sin completar ficticiamente la muestra.

Cubrir con pruebas pequeñas: reinicio real frente a recorte; no operaciones en precarga; apertura/final exclusivos; H2 sin Sharpe evaluable; H3 fuera de cobertura; emparejamiento, conteos H1, años y huecos; compuestos; degeneración; semilla estable serial/paralela; variantes adicionales rechazadas. Pruebas negativas deben adulterar realmente datos/tipos antes de invocar al verificador.

Ejecutar una regresión final pertinente y Ruff, sin cachés dentro de fuentes selladas. No sumar suites solapadas ni contar skips como aprobaciones. Los paquetes históricos no modificados se reutilizan con identidad y alcance declarados; no disparar todas sus suites de adulteración automáticamente.

El verificador B6 debe recalcular las métricas de fechas y el bootstrap desde los insumos compactos incluidos, con opciones de código/semilla fijadas; no basta leer sus tablas finales. Una única corrida integral offline desde una copia limpia del paquete final, más las pruebas unitarias/negativas, no varias copias completas por cada corrección de prosa. El sello autentica todo el contenido; declarar qué fuentes masivas no se releen y qué lógica es compartida.

## 9. Entrega compacta y coordinación

Destinos propuestos: `entregas/entrega_4/estabilidad_incertidumbre/<id>/` y `configs/entrega_4/estabilidad_incertidumbre/`. Reutilizá componentes, con nuevos auxiliares B6 de contratos/runner, remuestreo, reporte/verificador y lanzador sólo donde falten. No introducir una arquitectura genérica ni modificar `src/` para el reporte.

Entregar un candidato editable y luego un único paquete final con:

- Protocolo previo, configuraciones, índice de cuatro carteras y referencias, tiempos/recursos/comandos y matriz de cumplimiento.
- Reporte Markdown/HTML, síntesis y tablas: inicios, tramos BASE comparables, desglose anual, H2, efectos/intervalos/degeneración, escenarios previos y pendientes. Tres o cuatro figuras legibles bastan; no duplicar decenas de gráficos históricos.
- Insumos estadísticos compactos y autenticados, salidas financieras/auditorías necesarias de las nuevas carteras, réplicas de estadísticas, fuentes de cifras/figuras y herramientas reproducibles. No duplicar todos los paquetes anteriores ni exportar millones de minutos innecesarios.
- Registro final de controles, manifiesto/sidecar y resultado de verificación externa. Actualizar la matriz global y el índice vigente según estado real, sin cambiar matrices selladas.

El coordinador debe guardar tareas terminadas/bloqueadas, detener la afectada ante error y evitar reintentos infinitos. En un relanzamiento valida lo existente y sólo ejecuta lo pendiente. Desarrollo y revisión breve por Codex; cálculo/espera autónomos en el PC. No prometer trabajo del asistente después de terminar su respuesta.

No hacer commit, push, cambios del índice del usuario, limpieza ni archivado. No sobrescribir sellos, repetir B5, ampliar fechas/activos, usar credenciales, introducir intereses al carry ni seleccionar parámetros. Si hay un bloqueo, completar las tareas independientes y dejarlo explícito. Al cerrar, distinguir B6 terminado de revisión transversal y Word todavía pendientes.

# Avance y evidencia

Especificación: `sources/Prompt_Codex_Backtesting.md`, aprobada por el usuario.

## Avance actual — 2026-09-18

**Continúan la investigación y el desarrollo; la evaluación histórica económica sigue pendiente.** Después del diagnóstico de velocidad y de recibir nuevamente el comando, se comprobó la descarga activa hacia `D:\Backtesting`. Conserva `configs/download_full_d.toml` y su presupuesto separado de 800 GB. Esta investigación no inició ni interrumpió la descarga ni modificó sus archivos. La muestra en C: conserva el límite inicial de 20 GB.

Investigación paralela independiente de la descarga:

- Comisiones: se recuperaron la tabla oficial archivada del 31/05/2023 (Regular USDT maker 0,02 %, taker 0,04 %) y dos versiones de la FAQ BTCUSDT: 0,04 % taker el 02/06/2023 y 0,05 % el 20/02/2024. Acreditan documentación publicada, no la fecha efectiva del cambio ni continuidad. Se documentaron cinco exclusiones de promociones/programas que no corresponden al perfil. [Capturas y límites](research/fees_followup_20260918.md).
- Se generó el inventario de **4.010 eventos económicos de funding sin mark** (2.005 por activo), con timestamp efectivo, tasa y procedencia. Cuatro consultas públicas puntuales y seis páginas de una nueva consulta completa confirmaron los faltantes. La nueva consulta completa recibió 449.953 bytes, con idénticos timestamps y tasas y cero marks recuperados. No se imputaron valores.
- Comparación de 12 cobros conocidos con velas oficiales: apertura distinta en 2/12; cierre del minuto distinto en 12/12; cierre del minuto anterior distinto en 6/10 comparables. Son contraejemplos de equivalencia exacta, no una estimación de error económico. [Evidencia y fuentes alternativas](research/funding_followup_20260918.md).
- Seguimiento de reglas: se documentaron antecedentes de especificaciones 2020, cambios de clearance de enero/febrero de 2021 y el mínimo nocional USD-M con exención Reduce-Only de febrero de 2021. No acreditan continuidad ni cierran reglas del período económico 2022–2026. [Fuentes y límites](research/rules_followup_20260918.md). `data/rules/history.json` conserva cero snapshots completos.
- Se verificaron los **33 hashes** de los inputs y artefactos del seguimiento de funding y la correspondencia exacta de los 4.010 eventos reconsultados. Las tres capturas de comisiones se recuperaron por segunda vez: hashes y fechas Memento idénticos; se guardaron copias locales (1.701.226 bytes) con manifiesto. Esta continuación añade investigación y evidencia; no modifica el motor ni certifica un resultado histórico.

Diagnóstico de descarga y espacio posterior a la interrupción:

- Inventario de D: de sólo lectura: 230 ZIP completos, un `.part`, 1.574.494.137 bytes en 462 archivos. Se pueden reutilizar al reanudar con el mismo comando.
- Parquet/ZSTD ya estaba implementado. Los mismos 5.543.505 trades de la muestra ocupan 328.561.923 bytes como CSV sin comprimir, 57.062.373 en ZIP oficiales y 55.076.025 en Parquet activo: ahorro de 83,24 % frente a CSV y 3,48 % frente a ZIP. Los CSV se leen dentro del ZIP sin extraerlos al disco; conservar originales y procesados suma ambos tamaños. [Medición y alcance](descarga_d.md#espacio-y-parquet).
- Corregido el recorrido de toda la carpeta por cada fragmento de red: la lectura ahora agrupa bloques de 1 MiB y conserva el control antes de cada escritura, reanudación y SHA/CRC. Ensayo local de 1.240.118 bytes y 462 archivos: 77 → 3 recorridos, 2,09 → 0,10 segundos; no mide la conexión a Binance. También se corrigió la eliminación de ZIP corruptos después de cerrar su lector, necesaria en Windows.
- Verificación actual: **179 passed in 27.76s**, Ruff y formato sin errores. Las ocho pruebas nuevas reprodujeron los problemas antes del cambio y comprueban frecuencia de recorridos, presupuestos exactos/excedidos, reanudación y rechazo de corrupción. Revisión independiente sin hallazgos materiales. No se certifica la velocidad de la descarga completa.

Preparación posterior para empezar a evaluar y ajustar:

- Nuevo comando `preflight`, de sólo lectura: coteja los metadatos de la descarga completa prevista y la cobertura temporal de reglas antes de validar. Plan de 13.424 objetos más checksums. La comprobación en D: encontró ausencia del manifiesto final y del archivo de reglas. Nunca certifica integridad ni economía; `ready_for_validation` no equivale a un backtest válido.
- Validación acotada al intervalo y antecedentes necesarios. Funding se comprueba por filas contra el calendario mensual independiente, cuyo SHA se verifica, incluyendo tasas, intervalos, cobros de la cola, marks y disponibilidad de 60 segundos. Los flags globales de archivos fuera de ventana no invalidan una muestra válida; la evidencia necesaria desconocida sigue bloqueando.
- Replay acotado por particiones, con antecedente, solapes ordenados y conservación de empates. Prueba controlada de 120 particiones/24.000 filas: 119 → 1 particiones abiertas y 23.771 → 171 registros recorridos para los mismos 21 eventos. Es una demostración funcional, no una estimación del tiempo del histórico completo. Los hashes de procedencia siguen leyendo todos los inputs.
- Verificación conjunta de esa preparación: **171 passed in 29.16s**; Ruff y formato sin errores. Incluye 18 pruebas de preflight, 19 de replay y 27 de alcance de validación. Revisión independiente de los tres componentes: todos los hallazgos corregidos y reproducidos con regresiones, incluido el bloqueo de fechas invertidas antes de podar particiones. La muestra real se validó en un directorio temporal con enlaces a los inputs originales: funding completo para ambos activos; permanecen únicamente los bloqueos de reglas y discontinuidades de IDs. No se modificaron sus manifiestos originales ni los datos de D:.
- [Puesta en marcha](puesta_en_marcha.md) registra comandos y pendientes. Falta medir RAM, duración y espacio del motor/reportes a escala; las tablas de resultados aún se conservan en memoria. Normalizar relee los crudos y cada sensibilidad revalida/calcula hashes, limitaciones que deben medirse antes de lanzar las 30 configuraciones.

Investigación y verificaciones de la continuación anterior:

- Se documentaron fuentes oficiales de comisiones, filtros, tramos de mantenimiento y operatividad. La promoción BTCUSDT spot tiene inicio y final acreditados. Faltan, entre otros puntos, la fecha de transición del taker Futures de 0,04% a 0,05% y snapshots históricos completos; `data/rules/history.json` permanece vacío.
- Se auditaron 14 respuestas públicas de funding: **13.368 registros y 1.583.680 bytes**, con hashes verificados. Dentro del período económico hay **2.005 cobros por activo sin mark**; el primer mark disponible observado es del 31/10/2023 a las 08:00 UTC. No se sustituyeron los valores ausentes.
- Se añadió `python -m crypto_carry.data.reconcile`, una auditoría offline de trades Futures contra velas de operaciones de un minuto. La muestra concilia exactamente **2.197.331 trades BTC y 1.694.881 ETH** en sus 1.440 minutos por activo. Identifica una anomalía de `quote_qty` BTC y conserva los 50 saltos de IDs como diagnóstico, sin modificar los crudos ni relajar la validación histórica.
- Pruebas de esa continuación: `python -m pytest -q --tb=short` → **107 passed in 22.98s**; `ruff check src tests` y `ruff format --check src tests`, sin errores. Las 14 pruebas nuevas cubren conciliación, datos omitidos, valores inválidos, esquemas, cambios del archivo durante la lectura y precisión decimal. Una revisión independiente confirmó las correcciones y repitió esas 14 pruebas. La auditoría de ambos ZIP reales produjo los mismos informes después de las correcciones.
- Detalle, fuentes, limitaciones y comandos: [Investigación histórica y auditorías](research/README.md). No hacen falta credenciales ni una nueva confirmación para continuar buscando evidencia y probando el software. Cambiar fechas económicas o admitir aproximaciones sigue requiriendo una decisión metodológica explícita.
- Requisito posterior del usuario: máxima fiabilidad ante una posible prueba futura con capital. Se revisaron las simplificaciones de ejecución y riesgo y se documentaron [criterios y validaciones pendientes](fiabilidad.md), incluidos datos nuevos y simulación en vivo. Es una revisión documental; no habilita operaciones ni modifica la descarga o el motor.

Las corridas de la tabla siguiente se conservan como evidencia de la entrega del 17/09. El nuevo módulo modifica el hash del código para futuras corridas; no se atribuyen los identificadores anteriores a esta versión ni se recalcularon resultados históricos incompletos.

## Entrega verificada — 2026-09-17 (registro anterior)

**Software implementado y verificado; evaluación histórica estricta pendiente.** No se amplió la descarga de trades después de la muestra. `configs/base.toml` conserva los parámetros confirmados y digest `e1437d00668b6fb1d4a06dcb145d161fadf4e2dc293314aae84d9edb381be07e`.

- `uv sync --frozen`: entorno reproducible, Python 3.14.3 y NautilusTrader 1.231.0. NumPy 2.3.5 evita los avisos de incompatibilidad de unidades temporales encontrados con 2.5.3. Pandas 2.3.3, PyArrow 25.0.1, Matplotlib 3.11.2, HTTPX 0.28.1; versiones completas en `uv.lock` y manifests.
- `uv run pytest -q --tb=short`: **93 passed in 21.98s**, sin warnings. `ruff check src tests`: sin errores; formato verificado. Incluye prueba integral con apertura de ambas patas, funding, renovación, cierre con retry y conciliación nativa/económica.
- Revisiones independientes: `tasks/core_review.md` y `tasks/delivery_review.md`; todos sus hallazgos corregidos, reproducidos como regresiones y verificados. La última revisión focalizada de CLI pasó 7/7 sin warnings.
- Muestra oficial: **14 objetos**. La primera fase descargó 12 y probó su caché; se añadieron dos ZIP de marks del día anterior para disponer de un mark cerrado inicial. Los trades siguen limitados al 01/01/2024 UTC. Funding incluye antecedentes desde el 16/12/2023.
- Normalización final: **63 particiones, 5.549.365 filas**, cero errores internos: 5.543.505 trades, 5.760 marks (dos días por activo), 100 tasas verificadas con settlement mark presente. Se contrastan timestamps, duración nominal publicada, duración efectiva exacta y tasas entre fuentes. Se preservan los milisegundos reales de liquidación.
- Almacenamiento medido después de validar: **112.692.905 bytes bajo data/** (0,113 GB), frente al máximo **20.000.000.000**. Crudos: 57.208.419 bytes; procesados incluidos versiones conservadas: 55.374.787. D: mantiene 957.918.044.160 bytes libres. No fue necesario mover ni ampliar.
- Cobertura estricta `incomplete_data`: faltan reglas históricas verificadas de los cuatro mercados y hay discontinuidades de IDs en ambos archivos de Futures. Spot, marks y funding pasan sus controles propios. **No se ejecutó ningún período histórico económico como completo.** Tampoco se descargó el período completo 2020–2026.
- Demo: ambas carteras completaron diez días sintéticos con el motor real. Repetirla desde su `effective_config.toml` produjo **el mismo run_id y los mismos resultados**, verificando los 38 artefactos existentes antes de reutilizarlos. Reporte y doce figuras regenerados sin diferencias de bytes.
- Robustez histórica: las **30 configuraciones / 60 filas de comparación** tienen config/salida propia. Permanecen `incomplete_data`; no se ejecutaron sensibilidades económicas sobre un baseline no verificado. El índice agregado y sus subcorridas pasaron verificación y regeneración.

### Corridas reales generadas por los comandos

| Tipo | ID | Estado | Informe |
|---|---|---|---|
| Demo sintética (28/12/2023–06/01/2024) | `run_4af4a649dc7f816177638a13` | complete, sólo software | [Demo](../outputs/run_4af4a649dc7f816177638a13/report.md) |
| Muestra histórica 01/01/2024 | `run_07777fef933238052ad040ba` | incomplete_data, sin curva inventada | [Calidad e impedimentos](../outputs/run_07777fef933238052ad040ba/report.md) |
| Baseline histórico solicitado 2022–2026 | `run_c20147bd0400f321b7bf5f50` | incomplete_data, sin resultados económicos | [Baseline](../outputs/run_c20147bd0400f321b7bf5f50/report.md) |
| Índice de robustez histórica | `robustness-997ddc3ab922a741` | incomplete_data, 30 configuraciones | [Robustez](../outputs/robustness-997ddc3ab922a741/report.md) |

Comandos ejecutados: `doctor`, `download` (sample), `validate-data` (normalización y luego control independiente con `--skip-normalize`), `backtest --sample --strategy both`, `backtest --strategy both`, `robustness`, `demo`, repetición de demo desde config guardada y `report` para la demo y el índice. Los comandos de datos/evaluación histórica devolvieron el estado incompleto previsto; es un resultado del control de cobertura, no una prueba aprobada del backtest económico. Los comandos de reporte verifican integridad aunque el estado económico sea incompleto.

Reproducción comprobada:

```powershell
uv run python -m crypto_carry demo --config outputs/run_4af4a649dc7f816177638a13/effective_config.toml
uv run python -m crypto_carry report --run-id run_4af4a649dc7f816177638a13
uv run python -m crypto_carry report --run-id robustness-997ddc3ab922a741
```

Los informes anteriores que aparecen en `outputs/` conservan sus hashes/versiones; no se sobrescribieron. Los enlaces de esta tabla corresponden al código verificado el 17/09/2026.

## Decisiones previas confirmadas

- VIP 0 fijo, sin BNB ni referidos; promociones generales únicamente documentadas.
- Máximo inicial de datos: 20.000.000.000 bytes. Validar muestra antes de ampliar.
- Disco D: comprobado con aproximadamente 958 GB libres; la muestra permanece dentro de Backtesting.
- Python local 3.14.3, Windows 11 x64. Se instaló el wheel Windows CPython 3.14 de NautilusTrader 1.231.0 y se verificaron importación y replay.
- Carpeta inicialmente vacía y sin repositorio; trabajo en rama local codex/crypto-carry, dentro de la ubicación solicitada.
- Entregas 1 y 2 leídas en la carpeta vecina Informes. La Entrega 2 local no tiene el sufijo (6); no se afirma identidad de versiones.
- No se encontraron el DOCX de entregables ni la imagen de feedback; se aplica el texto autocontenido autorizado.
- Consulta pública BTC del 01/01/2022: tasas disponibles, markPrice vacío. No se sustituirá por un cierre de minuto.
- La estimación de los 224 ZIP mensuales de trades del período económico fue 210.421 GB comprimidos, medidos por HEAD. La descarga iniciada posteriormente usa archivos diarios e incluye preparación desde 2020; no representa el mismo conjunto ni tamaño total.

## Hitos

- [x] 1. Configuración, entorno, CLI e integración efectiva Nautilus.
- [x] 2. Pipeline, muestra, controles y reglas por vigencia; faltantes históricos identificados.
- [x] 3. Forecast, contabilidad, sizing y margen, con pruebas numéricas independientes.
- [x] 4. Estados, riesgos, ejecución, particiones, checkpoints e integración completa.
- [ ] 5. Evaluación histórica económica: bloqueada por reglas y continuidad de fuentes. Reportes diagnósticos y demo terminados.
- [ ] 6. Evaluación histórica de robustez: bloqueada por baseline. Infraestructura, 30 configuraciones y motivos de no evaluación entregados.
- [x] 7. Reproducción del software, revisión, artefactos, documentación y separación histórica/sintética.

Los hitos se cierran solamente con evidencia. Software y cobertura histórica se certifican por separado.

## Registro intermedio anterior al cierre

Las cifras siguientes documentan pasos previos; el estado vigente es el bloque «Avance actual» de arriba.

- Entorno instalado: Python 3.14.3 + NautilusTrader 1.231.0; uv.lock guardado. PyArrow 25 requerido por Nautilus. Pandas fijado a 2.3.3 para API estable.
- Adaptador real: replay de CustomData por timestamp, órdenes nativas aceptadas, fills mediante OrderMatchingEngine.fill_order y conciliación de posiciones. Cuenta nativa congelada/comisión cero; ledger económico único. Sin feeds nativos de funding ni matching automático de trades/barras.
- Pruebas de temporización: datos antes de timers coincidentes, primer trade estrictamente posterior y anterior al deadline, segundo entre patas, conservación de exposición al terminar.
- Primitivas financieras y regresiones de integración: EWMA, costos 1x/2x/3x, reducción de sizing, funding deduplicado entre fuentes, transferencia de efectivo Futures para spot, margen por tramos, deuda y conciliación.
- Estado/ejecución: aperturas, desarme, retries, renovación positiva por debajo del costo de entrada, rebalanceo de reducción, riesgo antes de renovación, liquidación total e insolvencia probadas.
- Checkpoint JSON con hash (sin pickle), restauración de posiciones nativas sin doble movimiento económico, timer pendiente entre patas conservado. Corrida continua y reanudada generan iguales fills, ledger, equity y tiempos de exposición.
- Último conjunto general ejecutado: 52 pruebas aprobadas, antes de agregar evaluación (3 aprobadas) y escenarios adicionales (12 pruebas de estrategia aprobadas). Hay avisos de deprecación de dependencias NumPy/Pandas; no fallos de negocio.
- Datos: subagente informa 12/12 objetos oficiales descargados, 57.144.001 bytes, checksum/ZIP verificados; normalización en curso. No constituye todavía una evaluación histórica económica.
- En ese punto quedaban reportes, CLI, demo/robustez, validación y revisión; se completaron como software en el cierre documentado arriba, manteniendo los bloqueos históricos.

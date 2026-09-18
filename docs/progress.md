# Avance y evidencia

Especificación: `sources/Prompt_Codex_Backtesting.md`, aprobada por el usuario.

## Estado final verificado — 2026-09-17

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

Los informes anteriores que aparecen en `outputs/` conservan sus hashes/versiones; no se sobrescribieron. Los enlaces de esta tabla corresponden al código final verificado.

## Decisiones previas confirmadas

- VIP 0 fijo, sin BNB ni referidos; promociones generales únicamente documentadas.
- Máximo inicial de datos: 20.000.000.000 bytes. Validar muestra antes de ampliar.
- Disco D: comprobado con aproximadamente 958 GB libres; la muestra permanece dentro de Backtesting.
- Python local 3.14.3, Windows 11 x64. Se instaló el wheel Windows CPython 3.14 de NautilusTrader 1.231.0 y se verificaron importación y replay.
- Carpeta inicialmente vacía y sin repositorio; trabajo en rama local codex/crypto-carry, dentro de la ubicación solicitada.
- Entregas 1 y 2 leídas en la carpeta vecina Informes. La Entrega 2 local no tiene el sufijo (6); no se afirma identidad de versiones.
- No se encontraron el DOCX de entregables ni la imagen de feedback; se aplica el texto autocontenido autorizado.
- Consulta pública BTC del 01/01/2022: tasas disponibles, markPrice vacío. No se sustituirá por un cierre de minuto.
- Los 224 ZIP mensuales de trades del período económico existen: 210.421 GB comprimidos, medidos por HEAD. No descargados.

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

Las cifras siguientes documentan pasos previos; el estado vigente es el bloque final de arriba.

- Entorno instalado: Python 3.14.3 + NautilusTrader 1.231.0; uv.lock guardado. PyArrow 25 requerido por Nautilus. Pandas fijado a 2.3.3 para API estable.
- Adaptador real: replay de CustomData por timestamp, órdenes nativas aceptadas, fills mediante OrderMatchingEngine.fill_order y conciliación de posiciones. Cuenta nativa congelada/comisión cero; ledger económico único. Sin feeds nativos de funding ni matching automático de trades/barras.
- Pruebas de temporización: datos antes de timers coincidentes, primer trade estrictamente posterior y anterior al deadline, segundo entre patas, conservación de exposición al terminar.
- Primitivas financieras y regresiones de integración: EWMA, costos 1x/2x/3x, reducción de sizing, funding deduplicado entre fuentes, transferencia de efectivo Futures para spot, margen por tramos, deuda y conciliación.
- Estado/ejecución: aperturas, desarme, retries, renovación positiva por debajo del costo de entrada, rebalanceo de reducción, riesgo antes de renovación, liquidación total e insolvencia probadas.
- Checkpoint JSON con hash (sin pickle), restauración de posiciones nativas sin doble movimiento económico, timer pendiente entre patas conservado. Corrida continua y reanudada generan iguales fills, ledger, equity y tiempos de exposición.
- Último conjunto general ejecutado: 52 pruebas aprobadas, antes de agregar evaluación (3 aprobadas) y escenarios adicionales (12 pruebas de estrategia aprobadas). Hay avisos de deprecación de dependencias NumPy/Pandas; no fallos de negocio.
- Datos: subagente informa 12/12 objetos oficiales descargados, 57.144.001 bytes, checksum/ZIP verificados; normalización en curso. No constituye todavía una evaluación histórica económica.
- En ese punto quedaban reportes, CLI, demo/robustez, validación y revisión; se completaron como software en el cierre documentado arriba, manteniendo los bloqueos históricos.

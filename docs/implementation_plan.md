# Crypto Carry Implementation Plan

> For agentic workers: use superpowers:subagent-driven-development with scoped ownership and task review.

**Goal:** Implementar y verificar el prompt aprobado sin modificar reglas financieras.
**Architecture:** Datos y reglas con vigencia alimentan lotes cronológicos en NautilusTrader. Una lógica de dominio compartida y un ledger por cartera gobiernan todas las decisiones. Informes consumen las tablas guardadas.
**Tech Stack:** Python 3.14, NautilusTrader 1.231.0, uv, pandas, NumPy, Matplotlib, PyArrow, pytest.
**Spec:** `docs/sources/Prompt_Codex_Backtesting.md`.

## Global Constraints

Todo dentro de Backtesting. Código en inglés; documentación en español. Solo datos públicos. No órdenes reales. Baseline inalterado, VIP 0 fijo, tope inicial 20 GB. Sin sustitución de datos indispensables, sin resultados históricos inventados. Decimal para dinero y redondeos; tiempo entero UTC en nanosegundos.

## Task 1: Entorno y contrato

- [ ] Crear pruebas de configuración y orden temporal; observar fallos antes de implementación.
- [ ] Implementar `config.py`, `models.py`, `events.py` con dataclasses explícitas.
- [ ] Fijar uv.lock; verificar import y API real de Nautilus y fixture con fills posteriores.

## Task 2: Primitivas financieras

- [ ] Pruebas manuales del apartado 13: EWMA 0.00168, costos 0.0034, comisiones spot netas, transferencia neutra, liquidación por tramos y deuda.
- [ ] Implementar `forecast.py`, `costs.py`, `ledger.py`, `margin.py`, `portfolio.py`.
- [ ] Revisar identidad contable y deduplicación después de cada movimiento.

## Task 3: Datos

- [ ] Pruebas offline de unidades, duplicados, límites, paginación y reglas point-in-time.
- [ ] Implementar `data/download.py`, `normalize.py`, `validate.py`, `rules.py`, `replay.py`.
- [ ] Descargar funding y muestra de trades/mark, guardar checksums y cobertura; bloquear certificación si faltan reglas.

## Task 4: Simulación

- [ ] Escribir escenarios de integración del apartado 13 antes de cada bloque.
- [ ] Implementar `execution.py`, `strategy.py`, `risk.py`, `nautilus_adapter.py`.
- [ ] Comparar replay continuo y particionado/reanudado, prioridades, límites de tiempo y ausencia de look-ahead.

## Task 5: Evaluación y entrega

- [ ] Probar H1, H3=0.001, métricas nulas justificadas e insolvencia.
- [ ] Implementar evaluación, robustez, exportaciones, figuras y CLI del apartado 15.
- [ ] Ejecutar demo, doctor, validate-data, backtest, report y robustez; documentar estado real.
- [ ] Revisión independiente, pruebas pertinentes y reproducción determinista antes de cierre.

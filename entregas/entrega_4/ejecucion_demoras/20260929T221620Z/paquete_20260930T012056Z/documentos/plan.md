# Bloque 4 Implementation Plan

> Ejecución directa por etapas con superpowers:executing-plans, TDD y revisión
> final independiente. El encargo autoriza implementación y ejecución; prevalece
> sobre puertas adicionales de aprobación, commits y worktrees duplicados.

**Goal:** ejecutar y verificar las seis sensibilidades de precio/demora para
ambas carteras y entregar evidencia portable.

**Architecture:** conservar la ruta temporal next_minute_vwap; tres opciones
independientes de investigación, metadata derivada de la orden y configuración,
auditor específico que verifica elegibilidad y precio. Herramientas nuevas
reutilizan contabilidad, exposición y H2/H3 corregidos sin modificar sus sellos.

**Tech Stack:** Python 3.14, NautilusTrader, Decimal, Arrow, pytest, Ruff.

**Spec:** encargo_usuario.md; protocolo.md.

## Restricciones y revisión

Preservar bytes de fuentes, referencias, índice y paquetes. Opciones apagadas
conservan canonical/digest y resultados. No alterar plazos de riesgo. No confundir
orden sin fill con latencia cero. Auditar todos los propósitos y el orden persistido.
Probar frontera exacta de cancelación, liquidación durante espera, corrección
preventiva, reinicio con órdenes pendientes y adulteración con sello renovado.

## Tareas

- [x] A1. Autenticar dependencias y datos; guardar hashes, entorno y código previo.
- [x] A2. Fixtures en tests/unit/test_execution_delays.py y
  tests/integration/test_execution_delays_native.py: primero fallo por opciones ausentes.
- [x] A3. Configuración/validación en config.py; precio y clasificación en
  execution.py; ventana y metadatos en strategy.py; salida explícita en
  reporting.py y data/prescribed.py. Mantener modelos y serialización originales
  cuando sea posible; metadatos nuevos viajan en checkpoint del estado activo.
- [x] A4. scripts/execution_delays.py define la matriz y valida diffs exactos;
  scripts/prepare_execution_delays.py autentica y congela; runner separado.
- [x] A5. Controles old/current deterministas con digest de fills, órdenes, ledger,
  señales, riesgo, cierres y estados; regresión incluyendo modos de costo bloque 3.
- [x] B. Ejecutar OHLC4, medir memoria/tiempo y auditar antes de etapa C.
- [x] C. Ejecutar y conciliar L01/L05 antes de etapa D.
- [x] D. Ejecutar y conciliar LC01/LC05/LC15; revisar población y liquidaciones.
- [x] E1. scripts/execution_delays_audit.py, fuentes, reporte e incidentes;
  tests con precios, propósitos, ventanas, cantidades, fees y secuencia adulterados.
- [x] E2. Construir paquete nuevo: 14 resultados, ocho períodos, curvas, P&L,
  capital, actividad, H2/H3, invariancias, incidentes y cumplimiento.
- [ ] E3. Verificador offline desde otra ruta, Ruff/regresión, exportación con
  índice temporal aislado, UTF-8/enlaces, hashes de preservación y matriz global.

Estado capturado antes del sello: recálculo completo con fuentes locales,
UTF-8/enlaces e inspección de figuras aprobados. Las adulteraciones sobre el
sello, la exportación y la comprobación offline de sus blobs se registran
después, externamente, en `verificacion_final/` de la carpeta de trabajo.
El plan vigente fuera del sello y la matriz global registran el cierre final.

No se ejecutan pasos git add/commit de las guías. No se borra el registro de
progreso: el usuario exige evidencia verificable y no habrá commits de respaldo.

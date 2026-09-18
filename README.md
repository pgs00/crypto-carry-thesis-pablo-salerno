# Crypto carry: backtesting reproducible

Implementación de `docs/sources/Prompt_Codex_Backtesting.md`: BTCUSDT/ETHUSDT spot y perpetuos USD-M, dos carteras independientes y una sola estrategia con filtro de funding activado/desactivado. Usa **NautilusTrader 1.231.0** para replay, órdenes y fills nativos, más un ledger Decimal conciliado para la economía del estudio.

**Estado:** software ejecutable con demo sintética y controles financieros/temporales. La evaluación histórica estricta está bloqueada por reglas históricas sin evidencia completa, marks de cobro ausentes en el tramo inicial y discontinuidades de IDs pendientes de resolver. La conciliación de la muestra con velas oficiales coincide en precios, cantidades y conteos; no certifica por sí sola cobertura completa. No hay rentabilidad histórica certificada para 2022–2026. Los informes incompletos no contienen una curva ficticia de capital sin invertir.

## Instalación y comandos

PowerShell, desde esta carpeta, Python 3.14 y `uv` instalado:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
uv sync --frozen
uv run pytest -q
uv run python -m crypto_carry doctor --config configs/base.toml
uv run python -m crypto_carry demo
```

`demo` no usa red: genera diez días sintéticos, con warmup, y ejecuta ambas carteras mediante el mismo motor/código del backtest. Sus cifras sirven para validar el pipeline, no H1–H3 de la tesina.

Datos e informes históricos:

```powershell
uv run python -m crypto_carry download --config configs/base.toml
uv run python -m crypto_carry validate-data --config configs/base.toml
uv run python -m crypto_carry backtest --config configs/base.toml --strategy both --sample
uv run python -m crypto_carry backtest --config configs/base.toml --strategy both
uv run python -m crypto_carry robustness --config configs/robustness.toml
```

`download` y `validate-data` usan la **muestra del 01/01/2024 UTC** por defecto. Incluye trades individuales de ese día, marks antecedentes y funding de calentamiento. Se verificaron ZIP, checksums, schemas, fechas y continuidad, con los faltantes documentados. El límite inicial es **20.000.000.000 bytes** bajo `data/`; el tamaño observado está en `doctor` y `docs/progress.md`. La muestra permanece aquí. El usuario inició por separado la descarga completa en D: el 18/09/2026; su finalización y validación quedan pendientes. `download --scope full` descarga desde `history_start` y respeta el presupuesto de la configuración seleccionada.

`validate-data --skip-normalize` vuelve a comprobar hashes/cobertura del Parquet existente. Los datos crudos nunca se rellenan ni sobrescriben con respuestas diferentes. Los archivos normalizados que cambian se versionan por hash.

Para descargar personalmente la historia completa en D:, ver [instrucciones de descarga](docs/descarga_d.md). `configs/download_full_d.toml` admite hasta 800 GB bajo la nueva raíz; la configuración de la muestra conserva su límite de 20 GB. Crear esa configuración no inicia una descarga; el comando debe ejecutarse explícitamente.

El backtest imprime JSON con `run_id`, `status`, `data_kind` y `report`. Código de salida del programa: 0 para ejecución terminada (incluye resultado económico insolvente), 2 para evidencia incompleta y 1 para fallo. Que se genere un informe no implica `complete` histórico.

`report --run-id` verifica los hashes y reconstruye reporte y figuras desde tablas guardadas. Repetir inputs/config/código reutiliza la corrida sólo después de comprobar todos los artefactos; diferencias o corrupción fallan visiblemente. Ejemplo real generado y verificado:

```powershell
uv run python -m crypto_carry report --run-id run_4af4a649dc7f816177638a13
```

Abrir [demo sintética](outputs/run_4af4a649dc7f816177638a13/report.md), [diagnóstico de la muestra histórica](outputs/run_07777fef933238052ad040ba/report.md) o [índice de robustez](outputs/robustness-997ddc3ab922a741/report.md). Más evidencia y comandos reales en `docs/progress.md`.

## Archivos y lectura

- [Metodología](docs/methodology.md): calendario, fórmulas, ejecución, riesgo, ledger y H1–H3.
- [Decisiones](docs/decisions.md): perfil VIP 0 confirmado, adaptación real de Nautilus y convenciones conservadoras.
- [Fiabilidad](docs/fiabilidad.md): evidencia exigida, límites de ejecución y validaciones pendientes antes de considerar capital propio.
- [Puesta en marcha en D:](docs/puesta_en_marcha.md): comprobación previa, normalización, validación, corridas y ajustes separados.
- [Diccionario](docs/data_dictionary.md): unidades, disponibilidad y schemas de fuentes.
- [Trazabilidad](docs/requirements_traceability.md): requisitos → módulos → pruebas → resultados.
- [Avance y verificaciones](docs/progress.md): comandos reales, IDs y bloqueos vigentes.
- [Investigación histórica y auditorías](docs/research/README.md): cronologías de reglas, cobertura real de funding y conciliación reproducible de trades contra velas oficiales.
- `data/manifests/`: URLs exactas, checksums, hashes, filas, conflictos y cobertura.
- `outputs/<run_id>/`: configuración, manifiesto, snapshots de procedencia, Parquet, resúmenes CSV, PNG/SVG e informe.

Las salidas incluyen señales, órdenes, fills, ledger, funding, posiciones, riesgo, equity, métricas, evaluación H1, oportunidad H3, atribución y ejecución. El P&L por componente concilia con equity menos capital; slippage informativo no se resta dos veces. Las cifras monetarias permanecen decimales exactas; las estadísticas usan floats.

## Robustez y reanudación

Hay 30 configuraciones predefinidas, incluyendo el baseline: costos, slippage, vida media, ventana, demora de señal, espera entre patas, horizonte/permanencia, primera operación/VWAP, fechas iniciales y AUM. Son cambios de una variable por vez, salvo horizonte/permanencia conjuntamente. Ambas carteras reciben el mismo cambio. Cada configuración tiene salida propia y el índice agregado compara cobertura/participación. Si el baseline no está verificado, los escenarios quedan incompletos con motivo; no se ejecutan sustitutos sintéticos dentro de una historia.

Puede seleccionarse un subconjunto con `robustness --scenario cost-2 --scenario cost-3`; siempre se evalúa primero el baseline. La sensibilidad sintética está disponible mediante la API `run_robustness(..., data_kind='synthetic')` y permanece separada.

Cuando los datos históricos requeridos estén verificados, la CLI admite `backtest --stop-at <UTC> --checkpoint-dir data/checkpoints/<nombre_nuevo>` y `backtest --resume-dir data/checkpoints/<nombre>`. Las pruebas verifican igualdad entre corrida continua, particiones y reanudación con una pata ejecutada. El checkpoint incluye estado, órdenes/timers, ventanas, ledger, config, reglas e inputs; rechaza cambios incompatibles. No se cierra una posición por cortar o reanudar.

## Límites e interpretación

Fills completos sin modelo de impacto, mark cerrado por minuto, liquidación total sin ADL, USDT a la par, transferencias instantáneas/gratuitas, sin impuestos ni insolvencia del exchange. Las órdenes nativas son portadoras del modelo de ejecución explícito; la cuenta nativa congelada no es el equity reportado. Un resultado parecido al aumentar AUM no demuestra liquidez ni escalabilidad real.

Para avanzar históricamente faltan snapshots fechados de fees, filtros, tramos, deducciones, cargos de liquidación y operatividad, además de los marks de cobro ausentes y de resolver las discontinuidades de trades oficiales. La descarga de un checksum válido acredita integridad del archivo, no completitud del mercado. No se usarán reglas actuales como si fueran históricas.

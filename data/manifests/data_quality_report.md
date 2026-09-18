# Informe de calidad de datos

Estado: **incomplete_data**. Datos históricos: **sí**.
Rango solicitado: `2024-01-01T00:00:00.000000000Z` hasta antes de `2024-01-02T00:00:00.000000000Z`.
Inicio exigido para funding: `2023-12-17T00:00:00.000000000Z` (ventana más 24 horas y antecedente).
Cobertura completa del baseline: **no**.

## Problemas

- missing verified rules: BTCUSDT/futures
- missing verified rules: BTCUSDT/spot
- missing verified rules: ETHUSDT/futures
- missing verified rules: ETHUSDT/spot
- rule coverage gap: BTCUSDT/futures at 2024-01-01T00:00:00.000000000Z
- rule coverage gap: BTCUSDT/spot at 2024-01-01T00:00:00.000000000Z
- rule coverage gap: ETHUSDT/futures at 2024-01-01T00:00:00.000000000Z
- rule coverage gap: ETHUSDT/spot at 2024-01-01T00:00:00.000000000Z
- unresolved trade-id discontinuity: BTCUSDT/futures
- unresolved trade-id discontinuity: ETHUSDT/futures

La ausencia de un archivo se trata como información desconocida, no como inactividad ni funding cero.

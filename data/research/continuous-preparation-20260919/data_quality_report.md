# Informe de calidad de datos

Estado: **incomplete_data**. Datos históricos: **sí**.
Modo de análisis: **prescribed_research**. Las reglas prescritas no certifican reglas históricas.
Rango solicitado: `2022-01-01T00:00:00.000000000Z` hasta antes de `2026-09-01T00:00:00.000000000Z`.
Inicio exigido para funding: `2021-12-17T00:00:00.000000000Z` (ventana más 24 horas y antecedente).
Cobertura completa del baseline: **no**.

## Problemas

- incomplete one-minute mark coverage: BTCUSDT
- incomplete one-minute mark coverage: ETHUSDT
- incomplete source file: data/minutes/2022_2026_continuous/processed/dataset=marks/symbol=BTCUSDT/market=futures/month=2024-08/part-00000.parquet
- incomplete source file: data/minutes/2022_2026_continuous/processed/dataset=marks/symbol=ETHUSDT/market=futures/month=2022-07/part-00000.parquet
- incomplete source file: data/minutes/2022_2026_continuous/processed/dataset=marks/symbol=ETHUSDT/market=futures/month=2024-08/part-00000.parquet
- missing closed mark minute or initial antecedent: BTCUSDT, 2 minutes
- missing closed mark minute or initial antecedent: ETHUSDT, 13 minutes

## Cierres de mercado documentados

- spot BTCUSDT, ETHUSDT: `2023-03-24T11:28:00.000000000Z` a `2023-03-24T14:00:00.000000000Z` (152 minutos). Fuente primaria: https://www.binance.com/en/blog/from-our-ceo/6789340645608890113

La ausencia de un archivo se trata como información desconocida, no como inactividad ni funding cero.

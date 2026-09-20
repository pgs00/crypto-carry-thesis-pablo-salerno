# Sensibilidad de los 15 marks: cartera continua

Período UTC: 01/01/2022–31/08/2026 (fin exclusivo: 01/09/2026). Cada cartera comienza con 10.000 USDT y conserva capital y posiciones al cambiar de año. Cobertura **completed_with_approximations**: 13 minutos ETH y 2 BTC, en siete huecos por activo.

Método principal, fijado antes de observar resultados: `futures_scaled`. Se multiplica el OHLC del futuro por el cierre de mark oficial / cierre de futuro del minuto anterior al hueco. El ancla permanece fija; no se suma nuevamente el basis. Sensibilidad `last_official`: OHLC constante en el último cierre oficial. Ambos métodos se publican al minuto siguiente, exclusivamente con velas cerradas.

| Método | Cartera | Equity final USDT | Retorno neto | CAGR | Drawdown máximo diario | Cierres por margen | Liquidaciones ejecutadas |
|---|---|---:|---:|---:|---:|---:|---:|
| futures_scaled | conditional | 10,785.76 | 7.8576% | 1.6335% | -0.2062% | 5 | 0 |
| futures_scaled | permanent | 11,680.07 | 16.8007% | 3.3825% | -0.4827% | 7 | 0 |
| last_official | conditional | 10,785.76 | 7.8576% | 1.6335% | -0.2062% | 5 | 0 |
| last_official | permanent | 11,680.07 | 16.8007% | 3.3825% | -0.4827% | 7 | 0 |

El drawdown de esta tabla usa cierres diarios, igual que los informes anteriores; no representa el peor recorrido intraminuto. [Métricas por año y régimen](period_metrics.csv) se calculan sobre las mismas carteras continuas, sin reinicios.

## Decisiones y posiciones durante los huecos

- `conditional`: risk_events: idénticos; fills: idénticos; signals: idénticos; daily_equity: idénticos; funding_observations: idénticos.
- `permanent`: risk_events: idénticos; fills: idénticos; signals: idénticos; daily_equity: idénticos; funding_observations: idénticos.

[Controles individuales de riesgo](gap_risk_checks.csv): posiciones antes del control, precio medio del short, colateral, balance, mantenimiento, ratio, precio y distancia a liquidación, estado antes/después y eventos realmente emitidos. Incluyen el ancla y el primer mark oficial de recuperación. [Resumen por hueco](gap_positions_summary.csv).

| Método / cartera | Activo / primera apertura UTC | Spot (mín.–máx.) | Short (mín.–máx.) | Máx. ratio margen | Mín. distancia liquidación | Cierres durante hueco |
|---|---|---:|---:|---:|---:|---|
| futures_scaled / conditional | BTCUSDT 2024-08-12T10:02 | 0.05300678–0.05300678 | 0.053–0.053 | 0.6481% | 61.0737% | ninguno |
| futures_scaled / conditional | ETHUSDT 2022-07-12T12:57 | 0–0 | 0–0 | sin short | sin short | ninguno |
| futures_scaled / conditional | ETHUSDT 2022-07-12T13:07 | 0–0 | 0–0 | sin short | sin short | ninguno |
| futures_scaled / conditional | ETHUSDT 2022-07-12T13:15 | 0–0 | 0–0 | sin short | sin short | ninguno |
| futures_scaled / conditional | ETHUSDT 2022-07-12T13:52 | 0–0 | 0–0 | sin short | sin short | ninguno |
| futures_scaled / conditional | ETHUSDT 2022-07-13T06:59 | 0–0 | 0–0 | sin short | sin short | ninguno |
| futures_scaled / conditional | ETHUSDT 2024-08-12T10:02 | 0.0000560–0.0000560 | 0.000–0.000 | sin short | sin short | ninguno |
| futures_scaled / permanent | BTCUSDT 2024-08-12T10:02 | 0.05900933–0.05900933 | 0.059–0.059 | 0.7091% | 55.7854% | ninguno |
| futures_scaled / permanent | ETHUSDT 2022-07-12T12:57 | 0.0000690–0.0000690 | 0.000–0.000 | sin short | sin short | ninguno |
| futures_scaled / permanent | ETHUSDT 2022-07-12T13:07 | 0.0000690–0.0000690 | 0.000–0.000 | sin short | sin short | ninguno |
| futures_scaled / permanent | ETHUSDT 2022-07-12T13:15 | 0.0000690–0.0000690 | 0.000–0.000 | sin short | sin short | ninguno |
| futures_scaled / permanent | ETHUSDT 2022-07-12T13:52 | 0.0000690–0.0000690 | 0.000–0.000 | sin short | sin short | ninguno |
| futures_scaled / permanent | ETHUSDT 2022-07-13T06:59 | 0.0000690–0.0000690 | 0.000–0.000 | sin short | sin short | ninguno |
| futures_scaled / permanent | ETHUSDT 2024-08-12T10:02 | 1.1900866–1.1900866 | 1.190–1.190 | 0.7578% | 84.5797% | ninguno |
| last_official / conditional | BTCUSDT 2024-08-12T10:02 | 0.05300678–0.05300678 | 0.053–0.053 | 0.6476% | 61.1247% | ninguno |
| last_official / conditional | ETHUSDT 2022-07-12T12:57 | 0–0 | 0–0 | sin short | sin short | ninguno |
| last_official / conditional | ETHUSDT 2022-07-12T13:07 | 0–0 | 0–0 | sin short | sin short | ninguno |
| last_official / conditional | ETHUSDT 2022-07-12T13:15 | 0–0 | 0–0 | sin short | sin short | ninguno |
| last_official / conditional | ETHUSDT 2022-07-12T13:52 | 0–0 | 0–0 | sin short | sin short | ninguno |
| last_official / conditional | ETHUSDT 2022-07-13T06:59 | 0–0 | 0–0 | sin short | sin short | ninguno |
| last_official / conditional | ETHUSDT 2024-08-12T10:02 | 0.0000560–0.0000560 | 0.000–0.000 | sin short | sin short | ninguno |
| last_official / permanent | BTCUSDT 2024-08-12T10:02 | 0.05900933–0.05900933 | 0.059–0.059 | 0.7085% | 55.8347% | ninguno |
| last_official / permanent | ETHUSDT 2022-07-12T12:57 | 0.0000690–0.0000690 | 0.000–0.000 | sin short | sin short | ninguno |
| last_official / permanent | ETHUSDT 2022-07-12T13:07 | 0.0000690–0.0000690 | 0.000–0.000 | sin short | sin short | ninguno |
| last_official / permanent | ETHUSDT 2022-07-12T13:15 | 0.0000690–0.0000690 | 0.000–0.000 | sin short | sin short | ninguno |
| last_official / permanent | ETHUSDT 2022-07-12T13:52 | 0.0000690–0.0000690 | 0.000–0.000 | sin short | sin short | ninguno |
| last_official / permanent | ETHUSDT 2022-07-13T06:59 | 0.0000690–0.0000690 | 0.000–0.000 | sin short | sin short | ninguno |
| last_official / permanent | ETHUSDT 2024-08-12T10:02 | 1.1900866–1.1900866 | 1.190–1.190 | 0.7579% | 84.5683% | ninguno |

## Supuestos, límites y reproducción

Los controles existentes permanecen activos: cierre preventivo por ratio de mantenimiento ≥ 50% o distancia a liquidación < 15%, y liquidación según balance, mantenimiento y precio de liquidación del modelo. Un mark aproximado puede desplazar esos umbrales. El método escalado supone estable la relación mark/futuro durante el hueco; el constante ignora el movimiento del futuro. Ninguno reconstruye el mark oficial desconocido ni un recorrido intraminuto. Se conserva la aproximación de funding `previous_closed_1m`, junto con las comisiones y reglas prescritas actuales. La cobertura aproximada no certifica reglas históricas.

La validación estricta de los originales se conserva en `strict_validation/manifests/coverage.json`; continúa bloqueada por los 15 marks. Las capas derivadas reemplazan solamente tres particiones de mark y verifican todas sus filas frente al original más las 15 estimaciones. Los restantes precios, funding y parámetros económicos son compartidos sin cambios. Todos los resultados anteriores y las fuentes originales se conservan.

Desde el repositorio, ejecutar `python -u -m crypto_carry --root D:\Backtesting continuous-mark-study --config <ruta absoluta a configs/download_minutes_2022_2026_d.toml>`. `study_index.json` identifica las cuatro corridas; sus manifiestos registran código, parámetros y hashes de entradas/salidas. `python -m crypto_carry --root D:\Backtesting report --run-id <run_id>` verifica una corrida y reconstruye su informe sin repetirla. `verify_mark_gap_study(Path(...))` verifica el estudio y sus cuatro corridas.

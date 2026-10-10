# Síntesis del bloque 3

Bloque técnico terminado. Se ejecutaron 16 carteras alternativas sobre las ocho variantes cerradas y se reutilizaron dos BASE. Las variantes cambian costos conjuntos, sólo slippage, participación o capital inicial; no se cruzan dimensiones.

La selección conserva 34 pb estrictos para entrar y forecast positivo para renovar. La extensión deja vivos los costos realizados en sizing y contabilidad. La compatibilidad previa se cotejó contra código congelado anterior, con metadatos nuevos identificados por separado.

| Escenario | Cartera | Retorno | Capital usado medio | Actividad | P&L USDT |
|---|---|---|---|---|---|
| BASE_E3 | conditional | 7.8576% | 19.8068% | 28.3178% | 785.76 |
| BASE_E3 | permanent | 16.8007% | 82.6309% | 98.2083% | 1680.07 |
| C02 | conditional | 6.3783% | 19.8219% | 28.3179% | 637.83 |
| C02 | permanent | 14.0495% | 82.7337% | 98.1904% | 1404.95 |
| C03 | conditional | 5.0058% | 19.8000% | 28.3179% | 500.58 |
| C03 | permanent | 9.9984% | 79.1367% | 94.3578% | 999.84 |
| S02 | conditional | 7.7020% | 19.7994% | 28.3178% | 770.20 |
| S02 | permanent | 16.1843% | 82.6371% | 98.2377% | 1618.43 |
| S05 | conditional | 7.1717% | 19.7601% | 28.3178% | 717.17 |
| S05 | permanent | 15.6722% | 82.6690% | 98.2083% | 1567.22 |
| P050 | conditional | 7.7105% | 19.6931% | 28.3106% | 771.05 |
| P050 | permanent | 16.3871% | 82.2008% | 98.1303% | 1638.71 |
| P025 | conditional | 6.1510% | 16.1130% | 22.8784% | 615.10 |
| P025 | permanent | 15.3055% | 79.0298% | 97.2228% | 1530.55 |
| A050 | conditional | 6.1813% | 16.1406% | 22.8395% | 3090.64 |
| A050 | permanent | 12.5623% | 64.4432% | 83.2936% | 6281.14 |
| A100 | conditional | 4.8786% | 13.1244% | 20.2959% | 4878.61 |
| A100 | permanent | 5.4635% | 44.1517% | 72.9068% | 5463.49 |

Los costos pueden modificar también cantidades y trayectoria. La comparación de capital usa el capital inicial propio de cada cartera disponible; los valores absolutos no bastan para comparar eficiencia. Las cantidades brutas por minuto respetan el cupo compartido auditado, sin sumar unidades BTC y ETH.

H2 de muestra completa en variantes: {'no_favorable': 7, 'favorable': 1}. Contraste H3 entre cortes: {'contraria': 8}. Forecasts, targets y oportunidad se cotejan contra BASE; H1 mantiene una sola población de 10.224 observaciones. Los nuevos retornos determinan H2 y la lectura completa de H3.

A100 es la única variante con H2 favorable en la muestra completa: CAGR condicional positivo y Sharpe superior al de su permanente. Su retorno sigue por debajo del permanente; H2 no exige superar su CAGR.

La evidencia es descriptiva para estos tamaños y velas de un minuto: no estima impacto ni cola, no demuestra escalabilidad ilimitada y no selecciona un parámetro ganador. Drawdown es diario. Se conservan ND, limitaciones de fuentes y causas no identificables; no se rehace el riesgo intradía.

Resultados, conciliaciones, estados y explicación de extremos: [reporte](reporte.md), [auditoría por órdenes](tablas/ordenes.csv), [casos](casos_extremos.md) y [verificador](README.md). Bloques 4–6 y revisión transversal continúan pendientes; Word se redactará después.

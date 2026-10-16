# Precio de ejecución y demoras

Seis variantes separadas evalúan una referencia de precio alternativa y demoras de órdenes. Cada cartera comienza con 10.000 USDT y opera BTCUSDT/ETHUSDT del 01/01/2022 al 31/08/2026 UTC, sin reinicios. Se conservan señal, costos y participación máxima de BASE.

| Variante | Cambio | CAGR condicional | CAGR incondicional |
|---|---|---:|---:|
| BASE | VWAP de la siguiente ventana completa de un minuto | 1,63% | 3,38% |
| E_OHLC4 | Promedio de apertura, máximo, mínimo y cierre | 1,65% | 3,34% |
| L01 | Demora de 1 minuto en todas las órdenes cliente | 1,67% | 3,07% |
| L05 | Demora de 5 minutos en todas las órdenes cliente | 1,29% | 3,13% |
| LC01 | Demora de 1 minuto sólo en cierres cliente | 1,58% | 3,07% |
| LC05 | Demora de 5 minutos sólo en cierres cliente | 1,54% | 2,89% |
| LC15 | Demora de 15 minutos sólo en cierres cliente | 1,27% | 3,06% |

## Resultados

- La convención de precio cambia poco el resultado agregado de esta muestra. OHLC4 modifica el P&L frente a BASE en +7,33 USDT para la condicional y −22,63 para la incondicional. La cercanía no acredita que cualquiera de esos precios sea ejecutable en mercado real.
- Las demoras alteran trayectorias completas. El efecto no es monótono: cinco minutos no siempre generan peor resultado que uno. Durante la espera siguen funding, inventario, garantías y controles; cada pata tiene su propia demora. Los cierres demorados se aplican globalmente, no sólo al incidente de marzo.
- L01 es favorable a H2 en la muestra completa. La condicional obtiene Sharpe 4,74 frente a 4,21 de la incondicional, con RF=0 y CAGR positivo. Las demás variantes conservan H2 no favorable en el total. L01, LC01 y LC05 son favorables en 2022–2023 y 2023. La excepción no implica mayor CAGR condicional ni identifica una demora óptima.

## Alcance

La demora se añade antes de la ventana elegible; ninguna señal conoce su máximo, mínimo o cierre futuro. Slippage y redondeo adverso se aplican una vez. La liquidación conserva prioridad y no recibe demora cliente adicional, aunque el modelo mantiene su ventana y cupo de volumen; no reconstruye un motor autónomo de liquidación del exchange.

H1 reutiliza la evaluación BASE autenticada. H3 conserva la oportunidad independiente de posiciones y llegada de órdenes, y resulta `contraria` en todas las variantes. Los drawdowns principales son diarios; los episodios intradía estudiados son ventanas locales y no máximos globales. Permanecen las limitaciones de reglas prescritas y aproximaciones de precios.

## Evidencia y detalle

- [Informe completo](evidencia/reporte.md), [lectura financiera ampliada](https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/blob/634c88fcf985da742cfa55d83bc4c0f99e082610/results/ejecucion/evidencia/lectura_resultados.md), [protocolo](https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/blob/634c88fcf985da742cfa55d83bc4c0f99e082610/results/ejecucion/evidencia/documentos/protocolo.md) e [incidentes](https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/blob/634c88fcf985da742cfa55d83bc4c0f99e082610/results/ejecucion/evidencia/incidentes.md).
- [Métricas por período](evidencia/tablas/metricas.csv), [H2 y motivos](evidencia/tablas/h2.csv), [diferencias frente a BASE](https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/blob/634c88fcf985da742cfa55d83bc4c0f99e082610/results/ejecucion/evidencia/tablas/deltas.csv) y [cronología de ejecución](https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/blob/634c88fcf985da742cfa55d83bc4c0f99e082610/results/ejecucion/evidencia/tablas/cronologia_resumen.csv).
- [Verificación del paquete](https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/blob/634c88fcf985da742cfa55d83bc4c0f99e082610/results/ejecucion/evidencia/README.md), [estrés](../estres/README.md) e [índice del estudio](../README.md).

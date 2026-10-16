# Resultado base: carry condicional e incondicional

El pronóstico EWMA mejora la precisión frente al comparador de última tasa, pero la cartera que lo utiliza no supera el Sharpe del carry incondicional en la muestra completa. Ambas carteras comienzan con 10.000 USDT y operan BTCUSDT y ETHUSDT entre el 01/01/2022 y el 31/08/2026 UTC, sin reinicios anuales. La incondicional omite sólo el filtro de funding; comparte las demás reglas de entrada, ejecución y riesgo.

| Cartera | Patrimonio final (USDT) | Retorno neto | CAGR | Sharpe, RF=0 | Drawdown diario |
|---|---:|---:|---:|---:|---:|
| Condicional | 10.785,76 | 7,86% | 1,63% | 4,96 | −0,21% |
| Incondicional | 11.680,07 | 16,80% | 3,38% | 6,53 | −0,48% |

## Resultados

- H1: menor error de pronóstico. EWMA obtiene un MAE de 6,30 frente a 8,70 puntos básicos por 168 horas del comparador de última tasa, sobre 10.180 observaciones emparejadas y ponderación BTC/ETH 50/50. La mejora es descriptiva; los horizontes solapados no son observaciones independientes. Los [comparadores adicionales](../complementaria/README.md) amplían esta evaluación.
- H2: menor exposición no produce superioridad de Sharpe. La condicional está activa el 28,32% del tiempo, frente al 98,21% de la incondicional. Su menor drawdown diario acompaña menor rentabilidad y Sharpe. H2 es `no_favorable`: exige CAGR condicional positivo y Sharpe superior al de la incondicional, ambos evaluables. En 2022, el Sharpe condicional es ND por volatilidad cero.
- H3: los cortes originales no muestran una caída de oportunidad. Entre 2022–2023 y 2024–agosto de 2026, la oportunidad media sube de 1,34 a 4,02 pb/168 h y el CAGR condicional de 1,08% a 2,05%; la lectura es `contraria`. La [evolución anual](../capital/evidencia/tablas/resumen_integrado.csv) y el [complemento anual y mensual](../complementaria/README.md) permiten examinar lo que ocultan esos promedios.

## Cómo interpretar la referencia

La oportunidad H3 es el pronóstico completo cuando pasan los filtros, y cero ante fallas conocidas; no es rentabilidad realizada ni pronóstico neto de costos. Se mide independientemente de las posiciones. La [metodología](../../docs/methodology.md) define las tres hipótesis y sus unidades.

El tiempo activo excluye residuos no negociables, que conservan su valor en el patrimonio. La corrección de exposición y H2 no alteró las trayectorias económicas ni los 48 veredictos del conjunto de reglas: 43 no favorables y cinco no concluyentes. Los seis escenarios de ese conjunto tampoco resultan favorables a H2 en la muestra completa.

Los resultados usan reglas y tarifas prescritas, ejecución por minuto y aproximaciones explícitas de precios de mark y funding. El drawdown de esta tabla es diario; consultar el [riesgo intradía](../riesgo/README.md). Estos supuestos no acreditan condiciones históricas completas ni ejecución real.

## Tablas, figuras y evidencia

- [Vista continua: resultados, gráficos y P&L](continuo/README.md).
- [Informe completo de la corrección](evidencia/comparacion/reporte.md), [métricas financieras](https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/blob/634c88fcf985da742cfa55d83bc4c0f99e082610/results/base/evidencia/comparacion/preservacion_financiera.csv), [H2 por escenario y período](evidencia/comparacion/h2.csv) y [exposición corregida](https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/blob/634c88fcf985da742cfa55d83bc4c0f99e082610/results/base/evidencia/comparacion/antes_despues.csv).
- [Guía de métricas](https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/blob/634c88fcf985da742cfa55d83bc4c0f99e082610/results/base/evidencia/documentos/guia_metricas.md), [verificación del paquete](https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/blob/634c88fcf985da742cfa55d83bc4c0f99e082610/results/base/evidencia/README.md) e [índice del estudio](../README.md).

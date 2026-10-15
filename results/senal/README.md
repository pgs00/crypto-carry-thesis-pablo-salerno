# Señal y selección de entradas

Seis variantes exploran horizonte y tenencia, semivida de EWMA y techo del basis, cambiando una dimensión por vez. Se mantiene la muestra continua del 01/01/2022 al 31/08/2026 UTC, BTCUSDT/ETHUSDT y 10.000 USDT iniciales por cartera. Es una sensibilidad retrospectiva, sin selección de parámetros por rentabilidad.

| Variante | Cambio frente a BASE | CAGR condicional | Utilización media diaria |
|---|---|---:|---:|
| BASE | Horizonte 168 h; semivida 24 h; techo de basis 0,50% | 1,63% | 19,81% |
| H072 | Horizonte y tenencia de 72 h | 1,03% | 11,75% |
| H336 | Horizonte y tenencia de 336 h | 2,50% | 47,86% |
| V012 | Semivida de 12 h | 1,72% | 23,54% |
| V048 | Semivida de 48 h | 1,65% | 20,81% |
| B025 | Techo de basis 0,25% | 1,63% | 19,81% |
| B100 | Techo de basis 1,00% | 1,63% | 19,81% |

## Resultados

- Cambiar horizonte y tenencia afecta también al capital desplegado. H336 mejora el CAGR condicional frente a BASE, pero emplea más del doble de patrimonio en promedio. H072 reduce ambos. Como cambian conjuntamente pronóstico y tenencia, no se atribuye toda la diferencia a precisión predictiva ni se comparan directamente MAE de 72, 168 y 336 horas.
- Menor error no ordena por sí solo la rentabilidad. Con el mismo objetivo de 168 horas, V048 reduce el MAE EWMA de 6,30 a 6,17 pb y cambia poco el CAGR. V012 eleva el MAE a 6,75 pb, pero obtiene mayor CAGR que BASE. La economía incondicional permanece idéntica al variar sólo la semivida.
- Las seis variantes mantienen H2 no favorable en la muestra completa. La condicional no supera el Sharpe incondicional del mismo escenario, medido con RF=0. H336 sí resulta favorable en 2023 y 2024; en 2022 pasa del ND de BASE a no favorable. Las variantes de basis conservan todas las operaciones BASE, aunque alteran ligeramente la oportunidad de mercado H3.

## Interpretación

H3 mantiene la lectura `contraria` en las seis variantes: oportunidad y CAGR condicional suben entre los dos cortes originales. La oportunidad usa el pronóstico completo cuando pasan los filtros, cero ante fallas conocidas y exclusión ante datos desconocidos; no depende de las posiciones. Los horizontes alternativos conservan sus propias unidades y no sustituyen H3 de 168 horas.

Los drawdowns de estas sensibilidades son diarios. Se mantienen costos y reglas prescritos, ejecución por minuto y aproximaciones de mark/funding. Los resultados describen las variantes probadas; no establecen un parámetro óptimo ni validación fuera de muestra.

## Evidencia y detalle

- [Informe completo](evidencia/reporte.md), [protocolo](evidencia/documentos/protocolo.md) e [índice de corridas](evidencia/indice_corridas.json).
- [Métricas por año y corte](evidencia/tablas/metricas.csv), [H2 con motivos y ND](evidencia/tablas/h2.csv), [H3](evidencia/tablas/h3_resumen.csv), [diferencias entre hipótesis](evidencia/tablas/deltas_hipotesis.csv) e [invariancias](evidencia/tablas/invariancias.csv).
- [Verificación del paquete](evidencia/README.md) e [índice del estudio](../README.md).

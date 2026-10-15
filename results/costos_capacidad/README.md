# Costos, capacidad y tamaño de cartera

Ocho variantes separadas evalúan fricciones, participación en volumen y capital inicial sobre BTCUSDT/ETHUSDT, del 01/01/2022 al 31/08/2026 UTC. La selección condicional conserva el umbral de entrada de 34 pb por ciclo mientras cambian los costos realizados. No se recalibra la señal para compensarlos; cantidades, margen y decisiones posteriores sí pueden cambiar.

| Variante | Cambio frente a BASE | CAGR condicional | CAGR incondicional |
|---|---|---:|---:|
| BASE | 10.000 USDT; participación máxima 1% | 1,63% | 3,38% |
| C02 | Comisiones y slippage ×2 | 1,33% | 2,86% |
| C03 | Comisiones y slippage ×3 | 1,05% | 2,06% |
| S02 | Slippage de 2 pb por orden | 1,60% | 3,27% |
| S05 | Slippage de 5 pb por orden | 1,49% | 3,17% |
| P050 | Participación máxima 0,50% | 1,60% | 3,30% |
| P025 | Participación máxima 0,25% | 1,29% | 3,10% |
| A050 | Capital inicial 50.000 USDT | 1,29% | 2,57% |
| A100 | Capital inicial 100.000 USDT | 1,03% | 1,15% |

## Resultados

- Las fricciones reducen la rentabilidad de ambas carteras. Triplicar comisiones ordinarias y slippage baja el CAGR condicional a 1,05% y el incondicional a 2,06%. BASE paga 0,10% por cada compra o venta spot y 0,05% por cada apertura o cierre del futuro, más 1 pb de slippage por orden. El ciclo completo de dos patas suma 34 pb. El slippage ya integra los precios y no se descuenta nuevamente del P&L.
- Mayor capital no conserva el rendimiento porcentual. Con 100.000 USDT aparecen más ejecuciones parciales y cae la utilización media diaria a 13,12% en la condicional y 44,15% en la incondicional. El drawdown diario incondicional llega a −2,19%. Las carteras se simulan de nuevo; no son múltiplos de BASE.
- A100 es una excepción favorable a H2 en la muestra completa. Su Sharpe condicional es 4,21 frente a 2,76, ambos con RF=0 y CAGR condicional positivo. Esto ocurre pese a que el CAGR condicional sigue por debajo del incondicional y ambos caen frente a BASE. Las otras siete variantes son no favorables a H2 en la muestra completa.

## Excepciones y alcance

H2 también es favorable en A100 para 2022–2023, 2023 y 2024; en C03 para esos mismos cortes; y en A050 y S02 para 2024. La [tabla completa](evidencia/tablas/h2.csv) conserva todos los años, ND y motivos. H1 reutiliza una sola población BASE. H3 mantiene el umbral de 34 pb y la lectura `contraria` en las ocho variantes, con los CAGR propios de cada cartera.

La participación limita volumen bruto agregado por cartera, instrumento y minuto. No acredita profundidad, spread, colas ni impacto de mercado. Los tamaños probados no establecen capacidad comercial. Se conservan reglas prescritas, aproximaciones de mark/funding y drawdowns diarios; no se traslada a estas variantes el máximo intradía de BASE.

## Evidencia y detalle

- [Informe completo](evidencia/reporte.md), [protocolo](evidencia/documentos/protocolo.md) e [índice de corridas](evidencia/indice_corridas.json).
- [Métricas por período](evidencia/tablas/metricas.csv), [diferencias frente a BASE](evidencia/tablas/deltas.csv), [órdenes](evidencia/tablas/ordenes.csv), [capacidad](evidencia/tablas/capacidad.csv) e [hipótesis e invariancias](evidencia/tablas/invariancias.csv).
- [Verificación del paquete](evidencia/README.md) e [índice del estudio](../README.md).

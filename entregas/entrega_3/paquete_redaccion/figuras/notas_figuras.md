# Notas de las dos figuras principales

## Equity de las cuatro carteras

Archivos: [PNG a 300 dpi](equity_comparativa.png) y [SVG](equity_comparativa.svg).
Título: «Evolución del capital por ventana».

Cada panel representa una ventana anual UTC distinta, con condicional y permanente.
Los ejes muestran fechas UTC y equity en USDT. Cada curva contiene los 365 cierres
diarios efectivamente persistidos más el estado inicial conocido de 10.000 USDT,
tomado de la configuración. No se interpolaron observaciones ausentes ni se
conectaron las ventanas. Ambas carteras se reinician al comenzar cada panel.
Las escalas verticales son distintas, expresamente indicado en la figura: no
comparar las pendientes visuales como si compartieran escala.

Fuente: [equity_diaria.csv](../datos/equity_diaria.csv), agrupada por `ventana`
y `estrategia`, ordenada por `time_ns`; `equity_usdt` conserva la precisión original.
La transformación a punto flotante ocurre exclusivamente para graficar.
Origen persistido: `equity_daily.csv`, `partial_day=False`, de las dos corridas
principales indicadas en `run_id`. El gráfico no representa el riesgo intradiario.

## Descomposición del P&L

Archivos: [PNG a 300 dpi](pnl_comparativo.png) y [SVG](pnl_comparativo.svg).
Título: «Componentes del resultado neto».

Las cuatro barras separan precios, funding y costos en USDT. Precios es
`spot_usdt + futuros_usdt`; costos es `comisiones_usdt + liquidaciones_usdt`,
ambos campos firmados. El rombo identifica el neto. Se conserva el cero real
de la condicional tardía. El slippage está incorporado en los precios de fill
y no se resta otra vez. «Precios» no significa funding ni basis puro: pueden
existir cantidades distintas y lapsos con exposición direccional.

Fuente: [pnl_componentes.csv](../tablas/pnl_componentes.csv), las cuatro filas
`vwap_joint` identificadas por ventana y estrategia. Esta tabla mantiene spot
y futuros separados, slippage informativo y residuo contable. El neto de la
figura es `beneficio_equity_usdt`, el cambio de equity conciliado con los
componentes dentro de la tolerancia de 1e−8 USDT, convertido sólo para dibujar.

## Exportación y reproducción

Script [generar_figuras.py](../scripts/generar_figuras.py), invocado por
[reproducir.py](../scripts/reproducir.py). Tamaños: equity 4.080 × 1.740 píxeles;
P&L 3.780 × 1.890 píxeles; PNG a 300 dpi y equivalentes vectoriales SVG.
Etiquetas y meses en español. No se incorporan otras figuras principales.

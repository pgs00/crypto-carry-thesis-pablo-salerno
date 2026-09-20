# Estado y evidencia — 20/09/2026

## Estudio vigente

Las carteras continuas **01/01/2022–31/08/2026 UTC** están ejecutadas y verificadas.
La referencia principal usa `futures_scaled`; `last_official` es sensibilidad
sobre los mismos 15 huecos. Son cuatro corridas guardadas, dos estrategias por
método, sin reinicios anuales. Los cortes 2022–2023 y 2024–agosto de 2026 no son
simulaciones nuevas ni ventanas independientes.

| Cartera principal | Equity final (USDT) | Retorno neto | CAGR | Sharpe | DD diario |
|---|---:|---:|---:|---:|---:|
| Condicional | 10.785,763050 | 7,857630 % | 1,633462 % | 4,962371 | −0,206166 % |
| Permanente | 11.680,069217 | 16,800692 % | 3,382477 % | 6,533632 | −0,482749 % |

[Tablas y figuras consultables](../entregas/entrega_3/continua/README.md) ·
[Paquete vigente](../entregas/entrega_3/README.md) · [Metodología](methodology.md).

## Cobertura y aproximaciones

- [Preparación continua](../data/research/continuous-preparation-20260919/README.md):
  fuentes, hashes y 15 minutos de mark ausentes delimitados.
- [Sensibilidad de marks](../data/research/continuous-marks-20260919/README.md):
  capas derivadas causales, posiciones y controles de margen durante los huecos.
  La cobertura se completa mediante aproximaciones; el modo estricto sigue bloqueando
  esos faltantes y no admite otros sin documentación.
- [Precio de funding](../data/research/funding-price-sensitivity-20260920/README.md):
  10.224 observaciones conciliadas con las fuentes; 6.214 precios oficiales y
  4.010 cierres previos aproximados. P95 absoluto: BTC 0,938775 bps y ETH 1,135602 bps.
  Las perturbaciones ilustrativas de precios faltantes cambian funding en
  ±0,005970 USDT (condicional) y ±0,074339 USDT (permanente), con posiciones fijas.
  Ninguno de los cierres usados para funding pertenece a las 15 velas estimadas.

Las tasas, horarios, tarifas prescritas, reglas y parámetros están conservados.
`complete` describe la corrida bajo esos supuestos; no certifica historia de reglas
ni ejecución exacta. El [informe de calidad en data/manifests](../data/manifests/README.md)
pertenece al piloto del 01/01/2024 y no evalúa estas carteras.

## Hipótesis y episodio de riesgo

H1: MAE EWMA 6,298978 bps frente a 8,703322 bps para no-change, igual peso por
activo, 10.180 observaciones válidas y 44 exclusiones. H2 es contraria al criterio
porque el Sharpe condicional es inferior al permanente. H3 tiene 1.704 días
válidos: la oportunidad aumenta de 1,340415 a 4,019674 bps/168h y el CAGR
condicional de 1,0814% a 2,0492% entre cortes. No apoya una caída de ambas magnitudes.

El 24/03/2023 ambas carteras permanecieron 121 minutos sin cobertura al cerrar
futuros a las 12:00 UTC y spot a las 14:01. La exposición fue ETH en la condicional
y BTC+ETH en la permanente. P&L diario: 35,908876 y 73,859494 USDT, respectivamente.
Se conservan órdenes, reintentos, fills, funding y atribución; no se elimina el
episodio para presentar una rentabilidad alternativa.

## Verificación y reproducción

La preparación del paquete verificó 1.735 archivos fuente y las cuatro corridas.
El paquete continuo concilia 3.408 filas financieras diarias, 10.224 observaciones
H1 y 1.704 días H3 conjuntos. La sensibilidad del funding concilia 2.234 pagos
condicionales y 9.827 permanentes con posiciones anteriores a cada liquidación.

La [guía principal de reproducción](../README.md#reproducción) regenera tablas
y figuras desde el ZIP y verifica las evidencias sin datos masivos. Los detalles
y resultados de pytest, Ruff, enlaces y preservación de hashes de esta limpieza
se registran en [validaciones de presentación](repository_cleanup.md).

## Antecedentes históricos

Las ventanas independientes 01/09/2022–31/08/2023 y 01/09/2025–31/08/2026 se
conservan en el [archivo de Entrega 3](../entregas/entrega_3/archivo/README.md).
Incluyen las variantes de ejecución, la auditoría del basis y sus resultados
anteriores. Sus cifras de rentabilidad, observaciones y pruebas corresponden a
ese alcance histórico; no sustituyen los resultados continuos anteriores.

El [registro detallado anterior](archive/progress_before_cleanup_20260920.md.txt)
permanece como snapshot. Las exploraciones de trades, acceso a proveedores,
reglas y comisiones se ubican mediante el [Índice de investigación](../data/research/README.md).
Los datos de Binance y los outputs completos permanecen locales y excluidos de Git.

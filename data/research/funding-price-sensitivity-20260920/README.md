# Efecto de aproximar el precio de liquidación del funding

Análisis de las carteras continuas **01/01/2022–31/08/2026 UTC**, método de marks
`futures_scaled`, capital inicial de 10.000 USDT por cartera. Se reutilizan las
corridas condicional `run_ad71d751b20623006c195ff3` y permanente
`run_dfea4b7ac1475668d5968c97`, sin replay ni cambios de parámetros.

## Validación de precios

Se verificaron **10.224 observaciones: 6.214 precios oficiales y 4.010 aproximados**,
5.112 por activo. Se contrastaron el JSON local de la API, el Parquet normalizado,
las observaciones consumidas por ambas carteras y los marks de un minuto.
El primer precio oficial es `2023-10-31T08:00:00.000000000Z`; el último aproximado es `2023-10-31T00:00:00.001000000Z`.
Las observaciones de calentamiento anteriores a 2022 no forman parte del análisis.

Se llamó al mismo `resolve_funding_mark` del motor sobre una copia de cada evento,
quitando sólo su precio de liquidación para forzar la comparación. Sea `b` el
timestamp del funding truncado al minuto: se usa la vela abierta en `b − 1 minuto`,
cerrada entre `b − 1 ms` y `b` (excluido), disponible entre `b` y el instante real
del funding, inclusive. Se mantienen sus desfases de milisegundos. Las 4.010
aproximaciones reproducen exactamente los precios y la procedencia guardados.

Error firmado = `10.000 × (precio_aproximado / precio_oficial − 1)`.
Un sesgo positivo significa sobreestimar el precio; no necesariamente el funding
recibido. MAE, P95 y máximo usan el **valor absoluto del error relativo**.
P95 interpola linealmente en el rango `(n − 1) × 0,95` de la muestra ordenada.
Cada observación tiene igual peso dentro del activo/año; no se pondera por exposición.
2026 comprende enero–agosto. Sin precio oficial se informa ausencia, no error cero.

| Activo | Año | Oficiales / aproximados | Sesgo (bps) | MAE (bps) | P95 absoluto (bps) | Máximo absoluto (bps) |
|---|---|---:|---:|---:|---:|---:|
| BTCUSDT | 2022 | 0 / 1095 | — | — | — | — |
| BTCUSDT | 2023 | 185 / 910 | -0.005142 | 0.130842 | 0.747098 | 1.931791 |
| BTCUSDT | 2024 | 1098 / 0 | -0.006406 | 0.191243 | 1.015551 | 6.538303 |
| BTCUSDT | 2025 | 1095 / 0 | -0.004526 | 0.140834 | 0.859487 | 3.469112 |
| BTCUSDT | 2026 | 729 / 0 | 0.012327 | 0.203948 | 1.047258 | 2.992376 |
| BTCUSDT | all | 3107 / 2005 | -0.001273 | 0.172862 | 0.938775 | 6.538303 |
| ETHUSDT | 2022 | 0 / 1095 | — | — | — | — |
| ETHUSDT | 2023 | 185 / 910 | 0.002967 | 0.244769 | 1.167393 | 2.892795 |
| ETHUSDT | 2024 | 1098 / 0 | -0.011866 | 0.195865 | 1.001493 | 2.825124 |
| ETHUSDT | 2025 | 1095 / 0 | -0.030243 | 0.243186 | 1.174850 | 4.223599 |
| ETHUSDT | 2026 | 729 / 0 | 0.031936 | 0.268608 | 1.167920 | 10.229319 |
| ETHUSDT | all | 3107 / 2005 | -0.007182 | 0.232522 | 1.135602 | 10.229319 |

## Impacto económico observado en precios conocidos

Para un short de `q` unidades base, el funding recibido es `q × precio × tasa`.
La diferencia observada es `q × tasa × (aproximado − oficial)`: positiva mejora
el resultado de la cartera. Se reconstruye `q` con el ledger **estrictamente
anterior** a cada liquidación, se contrasta con los fills de futuros y se concilia
cada pago guardado. El funding precede a los fills con el mismo timestamp.
Las liquidaciones de funding son distintas de una liquidación forzosa por margen.

| Cartera | Eventos con posición: oficiales / aproximados | Funding oficial recibido (USDT) | Diferencia usando proxy (USDT) | Suma de diferencias absolutas (USDT) | Efecto sobre retorno total (bps) |
|---|---:|---:|---:|---:|---:|
| conditional | 2031 / 203 | 799.684301 | 0.000229 | 0.020051 | 0.000229 |
| permanent | 6155 / 3672 | 1377.549824 | 0.000515 | 0.035560 | 0.000515 |

Hay 6.214 comparaciones de precios conocidas para **cada cartera**, aun cuando
no tiene posición. Sólo los eventos con posición de la tabla generan flujos.
Los CSV desglosan también año y activo. La diferencia observada anterior no se
suma a los escenarios siguientes: éstos mantienen los precios oficiales vigentes.

## Sensibilidad de los 4.010 precios faltantes

Se usa el P95 absoluto agrupado por activo de **todas** sus observaciones oficiales:
BTC `0.938774559 bps` y
ETH `1.135601894 bps`. Con `h = P95 / 10.000`,
el precio favorable es `proxy × (1 + signo(tasa) × h)` y el desfavorable es
`proxy × (1 − signo(tasa) × h)`. Las posiciones son shorts; tasa cero no altera
el flujo. Se perturban sólo precios aproximados; los precios conocidos quedan
idénticos. La perturbación se centra en el proxy, no pretende recuperar el oficial.

| Cartera | Escenario | Diferencia acumulada (USDT) | Efecto sobre retorno total (bps) | Retorno total ajustado |
|---|---|---:|---:|---:|
| conditional | base | 0.000000 | 0.000000 | 7.857630% |
| conditional | favorable | 0.005970 | 0.005970 | 7.857690% |
| conditional | adverse | -0.005970 | -0.005970 | 7.857571% |
| permanent | base | 0.000000 | 0.000000 | 16.800692% |
| permanent | favorable | 0.074339 | 0.074339 | 16.801436% |
| permanent | adverse | -0.074339 | -0.074339 | 16.799949% |

`Retorno ajustado = (equity final guardado + diferencia) / 10.000 − 1`.
Son efectos aditivos con posiciones originales: no hay reinversión ni carteras
reiniciadas por año. Un bp de retorno es 0,01 puntos porcentuales; con 10.000 USDT
de capital, 1 USDT equivale a 1 bp. Las diferencias por año son contribuciones al
retorno de la muestra completa, no retornos anuales recalculados.

**Son escenarios ilustrativos, no límites garantizados ni intervalos de confianza.**
No se conoce el error real de los precios ausentes. Extrapolar desde fines de
2023–2026 a 2022–2023 supone una estabilidad que no se puede verificar: pueden
cambiar volatilidad, liquidez, saltos y microestructura. P95 deja fuera errores
observados más extremos y no garantiza cobertura futura. La dirección favorable
o desfavorable se aplica a todos los flujos; no representa una trayectoria de
errores estimada. No incluye cambios de decisiones, tamaños, caja disponible,
margen ni liquidaciones que un replay con otros precios podría producir.

No se modifican tasas, horarios ni la capa de los **15 marks de velas faltantes**,
que es otro supuesto. De los cierres utilizados aquí, **0** pertenecen a esa
capa estimada; el CSV identifica el método de cada vela. El contraste de precios
no valida la exactitud histórica de reglas, comisiones ni ejecución.

## Archivos y reproducción

- [Observaciones de precios](prices.csv): una fila por activo/liquidación, valores,
  error y tiempos/procedencia del mark. Los errores sin oficial quedan vacíos.
- [Resumen de precios](price_summary.csv): cobertura y errores por activo/año y
  `all`. Precios en USDT por unidad base; errores en bps.
- [Eventos con posición](funding_events.csv): cantidades base previas, pago original,
  diferencia conocida y escenarios; importes en USDT. No incluye eventos sin posición.
- [Impacto por cartera, activo y año](economic_summary.csv): conteos de precios y
  posiciones por separado; `ALL` suma BTC/ETH y `all` agrupa la muestra completa.
- [Escenarios de cartera](portfolio_scenarios.csv): equity, funding y retorno final;
  `net_return` es fracción, `delta_return_bps` bps y
  `delta_return_percentage_points` puntos porcentuales.
- [Verificación y fuentes](sources.json): 1735 archivos
  de entrada verificados, hashes originales y controles. [Manifiesto](manifest.json)
  y `manifest.sha256` preservan los bytes de esta evidencia compacta.

Los CSV usan UTF-8, separador coma y punto decimal. El análisis conserva precisión
Decimal; las tablas de este README redondean a seis decimales. Se reutilizan
fuentes locales públicas de Binance; no se descargó ni incluyó data masiva.
Desde la raíz de Backtesting, con su entorno instalado, usar un **destino nuevo**:

```powershell
& '.\.venv\Scripts\python.exe' -m scripts.analyze_funding_prices --root 'D:\Backtesting' --output '.\data\research\funding-price-sensitivity-reproduccion'
```

Para verificar hashes y recalcular las tablas a partir de los CSV compactos,
sin abrir los datos masivos:

```powershell
& '.\.venv\Scripts\python.exe' -m scripts.analyze_funding_prices --verify '.\data\research\funding-price-sensitivity-20260920'
```

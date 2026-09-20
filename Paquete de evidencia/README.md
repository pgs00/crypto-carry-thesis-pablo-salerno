# Actualización de la Entrega 3: backtest continuo

Evidencia de las carteras condicional y permanente, **01/01/2022–31/08/2026 UTC**,
con `futures_scaled` como método principal. Se reutilizaron las corridas guardadas:
no se ejecutaron estrategias nuevas ni se reiniciaron carteras en 2024. Los cortes
son `[2022-01-01, 2024-01-01)` y `[2024-01-01, 2026-09-01)`. Capital inicial:
10.000 USDT por cartera. Los CSV usan punto decimal, coma como separador y UTF-8.

| Período | Cartera | Equity al inicio / final (USDT) | Retorno neto | CAGR | Drawdown diario |
|---|---|---:|---:|---:|---:|
| full | conditional | 10000.00 / 10785.76 | 7.8576% | 1.6335% | -0.2062% |
| 2022-2023 | conditional | 10000.00 / 10217.44 | 2.1744% | 1.0814% | -0.1224% |
| 2024-2026-08 | conditional | 10217.44 / 10785.76 | 5.5623% | 2.0492% | -0.2062% |
| full | permanent | 10000.00 / 11680.07 | 16.8007% | 3.3825% | -0.4827% |
| 2022-2023 | permanent | 10000.00 / 10616.66 | 6.1666% | 3.0372% | -0.4827% |
| 2024-2026-08 | permanent | 10616.66 / 11680.07 | 10.0165% | 3.6420% | -0.3232% |

## H1 y H3

H1 evalúa todas las señales con historia válida, sin condicionarlas a entrada,
basis, saldo o posición. El objetivo suma las tasas liquidadas en `(s, s+168h]`.
La EWMA usa 336 horas y vida media de 24 horas, normalizada por intervalos reales;
no-change extrapola la última tasa por su duración. El MAE conjunto es la media
de los MAE de BTC y ETH (50/50), sobre muestras emparejadas. Los cortes se asignan
por fecha de señal: un horizonte de diciembre de 2023 puede terminar en enero de
2024; sólo se excluyen horizontes fuera de la muestra global o no verificables.

| H1, igual peso | MAE EWMA (bps/168h) | MAE no-change (bps/168h) | Válidas / excluidas, ambos activos |
|---|---:|---:|---:|
| full | 6.298978 | 8.703322 | 10180 / 44 |
| 2022-2023 | 7.384230 | 10.276483 | 4380 / 0 |
| 2024-2026-08 | 5.479425 | 7.515314 | 5800 / 44 |

H3 se recalculó una sola vez desde el mercado, independiente de las carteras.
Cada minuto UTC usa el último forecast disponible, velas cerradas publicadas al
minuto siguiente, mark verificado, basis inclusivo `[0, 0.005]`, volumen positivo
y reglas operativas del escenario. Si el forecast supera el costo de ciclo
vigente, el valor elegible es **todo el forecast**, sin restarle costos. Si los
datos son conocidos pero falla un filtro, vale cero. Se promedian los 1.440
minutos por activo y después BTC/ETH 50/50. Un dato requerido desconocido excluye
todo el día conjunto; las ausencias documentadas del cierre spot son ceros
operativos, no datos inventados. La disponibilidad conserva milisegundos: un
forecast publicado a 00:01:00.006 recién puede usarse en la grilla de 00:02.

| H3, igual peso | Oportunidad media (bps/168h) | Frecuencia elegible | Días válidos / excluidos |
|---|---:|---:|---:|
| full | 2.871869 | 4.7034% | 1704 / 0 |
| 2022-2023 | 1.340415 | 2.4951% | 730 / 0 |
| 2024-2026-08 | 4.019674 | 6.3584% | 974 / 0 |

Lectura descriptiva H3: **contraria_descriptiva** al comparar oportunidad y CAGR condicional.
Los CSV contienen resultados por activo, muestras válidas y motivos de exclusión.
Los horizontes H1 se solapan; un menor MAE no demuestra significancia ni rentabilidad.

## Contabilidad, actividad y episodio de marzo de 2023

El P&L diario y por tramo es la diferencia de componentes acumulados de las corridas:
spot y futuros incluyen realizado y variación de no realizado; funding es flujo neto;
fees y cargos de liquidación llevan signo negativo. El slippage es informativo y
ya está en los precios: no se resta otra vez. Cada día y cada tramo reconcilian
con el cambio de equity, con tolerancia de 1e-8 USDT. Las tasas y retornos están
en fracciones: 0.01 equivale a 1%; un basis point equivale a 0.0001.

Tiempo invertido excluye polvo de spot: carry cubierto requiere ambas patas y
descalce ≤ 0.5%; inventario negociable restante es exposición sin cobertura
completa. Los intervalos se recortan en los límites del tramo sin abrir ciclos
nuevos. Los segundos por activo pueden sumarse; los de cartera miden la unión
temporal y no duplican exposición simultánea. El polvo se identifica por los
estados terminales/metadatos conservados, sin volver a simular filtros de venta.
Capital utilizado al cierre diario = valor de spot + colateral aislado;
utilización = ese importe/equity. Las medias son de cierres diarios, no intradía.

Se distinguen intentos de apertura, aperturas completas, ciclos cerrados, fallas
y solicitudes de cierre. Un ciclo termina en su primer evento terminal; pedidos
repetidos y reintentos siguen visibles en eventos y órdenes. En el comparador
permanente el filtro de funding es diagnóstico, **no un rechazo aplicado**.

El 24/03/2023 los futuros se cerraron a las 12:00 UTC y el spot a las 14:01:
121 minutos sin cobertura, ETH en la condicional y BTC+ETH en la permanente.
El detalle conserva velas observadas de 11:20 a 14:10 UTC, volumen cero, filas
ausentes documentadas, órdenes, reintentos, fills, funding y ledger.

| Cartera | P&L diario (USDT) | Funding diario (USDT) | Comisiones diarias (USDT) | Minutos de cartera con exposición sin cobertura |
|---|---:|---:|---:|---:|
| conditional | 35.908876 | 0.607790 | -4.429328 | 121.00 |
| permanent | 73.859494 | 1.247107 | -9.148699 | 121.00 |

La proporción del P&L diario sobre beneficios positivos del período/año es una
comparación descriptiva, no atribución causal ni una cartera simulada sin el episodio.

## Archivos, fuentes y verificación

- [Catálogo de CSV](catalogo.csv): contenido, unidades y número de filas por archivo.
- `tablas/`: equity/P&L diarios, resultados por tramo, actividad, ciclos, exposición,
  H1, H3 y diagnósticos. `h3_grupos_forecast.csv` contiene los conteos y sumas
  suficientes para recalcular cada día; no se incluyen millones de velas.
- `evidencia/`: registros financieros compactos y revisión del episodio;
  `h3_muestra_minutos.csv` tiene una muestra fija diaria, cambios de forecast y
  todo el 24/03/2023, no una muestra seleccionada por rendimiento.
- [Sensibilidad previa de los 15 marks](data/research/continuous-marks-20260919/README.md):
  copiada con sus bytes y hashes originales, incluidos ambos métodos.
- [Fuentes y hashes](fuentes.json), `fuentes/` y `codigo/`: manifiestos originales,
  parámetros, supuestos y código del posprocesamiento. Los datos de mercado
  proceden de los archivos públicos de Binance ya descargados y normalizados.

Verificación local: 1735 archivos fuente, las cuatro corridas
de sensibilidad y sus parámetros. El ZIP omite los datos masivos de Binance.
Desde la carpeta extraída, `python verificar.py` valida hashes y recalcula H1,
H3 y las conciliaciones del subconjunto incluido; no requiere D: ni Binance.
Para regenerar el paquete desde el repositorio y las fuentes locales:

```powershell
& '.\.venv\Scripts\python.exe' -m scripts.continuous_delivery.build --root 'D:\Backtesting' --destination 'D:\Backtesting\outputs\entrega3_continua_nueva' --zip '.\entregas\entrega_3\paquete_actualizacion_continua_nuevo.zip'
```

Usar destinos nuevos conserva las evidencias anteriores. El código incluido en
`codigo/scripts/` es el mismo generador; utiliza el entorno y dependencias fijados
en `codigo/pyproject.toml` y `codigo/uv.lock`. Los manifiestos fuente conservan rutas
relativas al root local y referencias a archivos grandes que no forman parte del ZIP.

## Límites

Es un escenario de investigación con reglas y tarifas prescritas, ejecución
`next_minute_vwap`, funding aproximado cuando falta el mark de cobro y 15 marks
estimados mediante `futures_scaled`. No certifica reconstrucción histórica exacta.
El drawdown es diario y los marks cerrados no reconstruyen el recorrido intraminuto.
La comparación de regímenes es descriptiva y no identifica causalidad estructural.
Se conservaron todos los resultados, incluso los contrarios a las hipótesis.

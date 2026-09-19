# Convenciones de lectura

Los CSV están en UTF-8, separados por coma y con punto decimal. Las magnitudes
monetarias conservan las cadenas originales; si se importan en Excel, seleccionar
las columnas de alta precisión y `time_ns` como texto. Un CSV no impone el límite
numérico de precisión de Excel. Las fechas son UTC y los fines de período exclusivos.
Los vacíos son nulos o no aplicables, nunca ceros. En resultados, el motivo del
Sharpe nulo es explícito; en el anexo las convenciones se heredan de las métricas.

`1 = 100% = 10.000 bps`; los retornos, basis, MAE y pronósticos son proporciones,
no porcentajes impresos. El funding pronosticado y el costo del ciclo se comparan
sobre el mismo horizonte acumulado. La oportunidad de H3 es el exceso positivo
del forecast sobre costo, resumido diariamente y entre activos; no es beneficio
realizado ni una tasa anualizada. Su construcción consta en
[evaluation.py](evidencia/codigo/evaluation.py) y los `opportunity_daily.csv` incluidos.

En P&L, comisiones y cargos tienen signo negativo. Sólo la tabla del episodio
informa `fees_costo_positivo_usdt` como magnitud positiva. La suma contable es
spot + futuros + funding + comisiones + liquidaciones. El slippage informativo
ya se realizó mediante precios adversos y no se resta nuevamente.

Las métricas reproducen la convención binary64 del motor, con retorno diario
`equity_t/equity_anterior−1`, primer denominador igual a capital inicial,
desvío muestral (`ddof=1`), tasa libre de riesgo cero y anualización de 365 días.
La columna `retorno_diario_decimal` ofrece el cociente Decimal con precisión 60;
`retorno_diario_metricas` conserva la convención usada en Sharpe. No se sustituyó
silenciosamente una por otra. El CAGR se calcula con la duración real de la
ventana; aquí ambas duran exactamente 365 días. El drawdown diario incluye el
capital inicial como primer máximo y no describe mínimos intradiarios.

Las horas-activo suman exposición por símbolo: dos activos cubiertos una hora
suman dos horas-activo. El tiempo cubierto, sin cobertura y de sólo polvo son
estados distintos; polvo no implica carry activo. Capital utilizado es spot
valorizado más garantía propia de futuros en cortes diarios; puede superar
10.000 USDT por cambios de valorización. No confundir aperturas completas,
intentos de apertura, órdenes, fills, intentos fallidos y ciclos cerrados.

En `actividad_y_rechazos.csv`, cada fila de diagnóstico usa como denominador
1.095 evaluaciones de entrada por símbolo, estrategia y ventana. No incluye
renovaciones, que figuran por separado en la evidencia original. Los alcances son:

- `simultaneous_filter_states`: pueden fallar varios filtros en una misma evaluación;
  sus conteos no son aditivos. `simultaneous_reject` cuenta evaluaciones con al menos
  un filtro aplicable fallido. `not_evaluable` no es un rechazo demostrado del filtro.
- `sequential_first_rejection`: primera causa que bloqueó realmente la entrada;
  esas causas son mutuamente excluyentes dentro de cada grupo.
- `theoretical_not_applied`: diagnóstico del funding de la permanente. No se cuenta
  como bloqueo operativo ni dentro de los rechazos simultáneos aplicables.

`basis_negative` significa basis menor que cero; `state_active`, posición ya activa;
`cooldown`, enfriamiento; `budget`, presupuesto; `sizing`, cantidades no viables.
El resumen de origen es disperso: un código que nunca apareció no tiene fila.
La ausencia de rechazos de funding aplicables a la permanente se comprueba
expresamente en el script; no se confunde con sus diagnósticos teóricos.

En parámetros, sufijos `_hours` y `_seconds` indican horas y segundos, `_bytes`
indica bytes, `_bps` puntos básicos; capital y tolerancia contable son USDT.
`leverage`, multiplicadores, `window_hours`/vida media/horizonte y nombres de
modelo se interpretan según su nombre y configuración. Basis, fees, slippage,
fracciones de objetivo, participación, descalce, margen y rebalanceo son proporciones.
Las fechas de muestra auxiliar y el presupuesto de descarga se conservan como
metadatos de configuración y no recortan las ventanas económicas del manifiesto.
Los campos heredados `leg_delay_seconds=1` y `vwap_seconds=5` no gobiernan
`next_minute_vwap`. El código y la matriz de cambios explican su plazo efectivo.

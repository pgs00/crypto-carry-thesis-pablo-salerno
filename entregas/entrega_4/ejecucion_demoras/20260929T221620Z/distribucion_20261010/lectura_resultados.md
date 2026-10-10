# Lectura comparada de los resultados

Esta lectura usa la muestra completa UTC [01/01/2022,01/09/2026), con
10.000 USDT iniciales por cartera. Resume las tablas verificadas del paquete;
los ocho períodos y la precisión original permanecen en los archivos fuente.
Las seis sensibilidades son exploratorias y no seleccionan una política.

| Escenario | P&L condicional (USDT) | Diferencia con BASE | P&L permanente (USDT) | Diferencia con BASE |
|---|---:|---:|---:|---:|
| BASE_E3 | 785,76 | 0,00 | 1.680,07 | 0,00 |
| E_OHLC4 | 793,09 | +7,33 | 1.657,44 | −22,63 |
| L01 | 805,46 | +19,70 | 1.518,50 | −161,57 |
| L05 | 616,45 | −169,31 | 1.544,95 | −135,12 |
| LC01 | 760,21 | −25,56 | 1.517,24 | −162,83 |
| LC05 | 738,41 | −47,35 | 1.421,23 | −258,84 |
| LC15 | 604,49 | −181,28 | 1.512,01 | −168,06 |

Fuente: [métricas por período](tablas/metricas.csv) y
[diferencias con BASE](tablas/deltas.csv). Los importes de esta tabla se
redondean a centavos sólo para presentación.

OHLC4 cambia poco el P&L acumulado en esta muestra y conserva 138 fills en la
condicional y 332 en la permanente. La referencia de precio sigue afectando
precios, comisiones monetarias y la evolución posterior de fondos; la igualdad
de ese recuento no acredita identidad de todas las decisiones o cantidades.

Las demoras producen diferencias mayores y no monótonas. En la permanente,
L05 supera el P&L de L01; LC15 también supera a LC05. En la condicional, L01
termina por encima de BASE, mientras L05 y las tres LC terminan por debajo.
La [comparación L frente a LC de igual demora](tablas/comparacion_L_LC.csv)
conserva trayectorias completas distintas. Sus diferencias no identifican un
efecto aditivo aislado de demorar las aperturas.

La cronología aplicada se observa directamente: para órdenes con fill, la
mediana envío–fill pasa de 60 s en BASE a 120 s en L01 y 360 s en L05.
Desde elegibilidad hasta fill, la mediana sigue en 60 s. En LC la mediana
conjunta sigue en 60 s porque mezcla propósitos afectados y no afectados;
su máximo alcanza 120, 360 y 960 s respectivamente. El análisis por propósito
y las órdenes sin fill están en [cronología](tablas/cronologia_resumen.csv)
y [órdenes](tablas/ordenes.csv). No se interpreta la mediana conjunta de LC
como ausencia de demora en los cierres.

La actividad total sin polvo cambia poco: aproximadamente 28,3–28,4% del tiempo en
la condicional y 98,2–98,3% en la permanente. Sí cambia la exposición sin
cobertura, medida como unión temporal BTC/ETH: de 189/274 minutos en BASE
(condicional/permanente) a 546/972 en L05 y 313/510 en LC15. Los reintentos
de igual propósito bajan de 122/404 en BASE a 20/56 en L05 y 6/24 en LC15.
Su menor frecuencia debe leerse junto con la mayor espera y exposición, los
parciales y los fallos. Los ciclos completados permanecen en 9/15; renovaciones
y ciclos fallidos sí cambian. Fuentes: [actividad](tablas/actividad.csv),
[resumen de ejecución](tablas/ejecucion_resumen.csv) y
[catálogo completo de episodios](tablas/episodios_descubiertos.csv).

El capital utilizado medio diario de la condicional es 2.074,62 USDT en BASE
y varía entre 2.022,20 y 2.077,00 en las sensibilidades. En la permanente pasa
de 8.972,08 en BASE a valores entre 8.657,55 y 8.958,58. La utilización diaria
media permanece aproximadamente entre 19,53–19,83% y 80,63–82,77%,
respectivamente. Son resultados de cada trayectoria, con fondos y garantías
heredados, no escalados desde la referencia.

El máximo drawdown **diario** de BASE es −0,2062%/−0,4827%. Entre las variantes,
la caída diaria más profunda es −0,8990% en LC15 condicional y −1,1540% en
LC01 permanente. Los registros conservan cinco solicitudes preventivas por
margen en cada condicional y siete en cada permanente, sin fills de
liquidación. La deuda máxima observada en cierres diarios es cero; esta cifra
se refiere a esa frecuencia. Fuentes: [métricas](tablas/metricas.csv) y
[eventos](tablas/eventos.csv).

La ausencia de liquidaciones históricas no sustituye las pruebas sintéticas
de escalada y prioridad de liquidación. Los 91 casos locales seleccionados
incluyen 33.397 observaciones, con precios arrastrados, estimados y ausencias
identificados. Sus pérdidas transitorias describen esas ventanas; no son un
máximo intradía global. Al desaparecer el corto, el margen de ese contrato
queda ND. El [detalle de incidentes](incidentes.md) conserva la selección y
las fronteras originales, incluida la exposición del 24/03/2023.

H1 y la oportunidad de H3 conservan sus proyecciones y targets: se reutilizan
una sola vez las 10.224 observaciones H1 autenticadas. H2 es favorable en L01
para la muestra completa: CAGR condicional positivo y Sharpe 4,7413 frente
a 4,2051 en la permanente del mismo escenario. BASE y las otras cinco
variantes son no favorables en ese período. Esto no exige que la condicional
tenga mayor P&L. H3 mantiene el resultado contrario en el contraste original
2022–2023 frente a enero de 2024–agosto de 2026. Los resultados anuales, ND y
motivos permanecen en [H2](tablas/h2.csv), [H3](tablas/h3_resumen.csv) e
[invariancias](tablas/invariancias.csv).

No se ejecutaron shocks, trayectoria sin interrupción ni nuevos cálculos
SOFR. Esos resultados no pueden inferirse de estas seis sensibilidades.

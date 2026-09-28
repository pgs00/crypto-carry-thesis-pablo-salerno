# Protocolo previo: costos y capacidad

Fijado antes de resultados. Autoridad: encargo íntegro `encargo_usuario.md`.
BASE originales: run_ad71d751b20623006c195ff3 y run_dfea4b7ac1475668d5968c97.
Dos carteras alternativas por escenario; BTCUSDT/ETHUSDT, spot y USD-M,
intervalo UTC [2022-01-01,2026-09-01), sin reinicios ni liquidación terminal.

| Variante | Único cambio económico | Selección |
|---|---|---|
| C02 | cost_multiplier=2 | base_e3_total |
| C03 | cost_multiplier=3 | base_e3_total |
| S02 | slippage=0.0002 | base_e3_total |
| S05 | slippage=0.0005 | base_e3_total |
| P050 | max_volume_participation=0.005 | BASE |
| P025 | max_volume_participation=0.0025 | BASE |
| A050 | capital=50000 | BASE |
| A100 | capital=100000 | BASE |

Configuraciones derivadas exclusivamente de la efectiva BASE; el runner
rechaza cualquier diferencia extra. Capital BASE=10000; participación BASE=1%.
Mantener H168, half-life 24h, ventana 336h, precarga 360h, disponibilidad 60s,
basis inclusivo [0,0.005], target spot 30% por activo, aislado 2x, reglas/riesgo,
next_minute_vwap, joint_quantity, tiempos/ventanas/reintentos originales.

## Separación autorizada

`research_decision_fee_mode=base_e3_total` retorna Decimal('0.0034') sólo en
`cycle_cost`. Entrada condicional: forecast estrictamente superior a 34 pb;
renovación: forecast>0. Permanente omite ambos filtros de funding y conserva
los restantes. Los modos realized y base_e3 mantienen su semántica anterior.
No se congelan órdenes ni cantidades: sizing, precio estimado, comisiones,
caja, inventario y garantías usan las fricciones del escenario. C02/C03
escalan conjuntamente comisiones ordinarias y slippage, una sola vez.
El cargo especial de liquidación conserva regla/tasa; la comisión ordinaria
se registra separada. Slippage/tick ya están en precio y no se restan otra vez.
Diagnósticos del modo nuevo: componentes de selección suman 34 pb y los
campos `scenario_*` informan tarifas/deslizamiento realizados por separado.
H3 y estrategia consumen el mismo cycle_cost. No cambia el indicador histórico.

## Ejecución, recursos y puertas

A: autenticar todos los miembros de seis paquetes y los archivos de datos
consumidos; pruebas RED/GREEN y controles deterministas secuenciales sobre
código previo congelado. Comparar todos los cierres, ledger, fills, órdenes,
estados, forecast y oportunidades; metadatos del modo nuevo se excluyen sólo
de la proyección económica explícita. Medir tiempo/memoria y registrar comandos.
Congelar código/runner antes del lote; cambio económico posterior exige destinos
nuevos. B: costos/deslizamiento; C: participación; D: capital; E: consolidación.
Cada corrida debe conciliar cierres/períodos/ledger a 1E-8 USDT antes de interpretar.
Reanudación sólo por corrida completa autenticada e identidad exacta. Intentos
interrumpidos se conservan y reinician desde origen; nunca desde estado BASE.
Comenzar con una corrida; luego concurrencia máxima 2 sólo con RAM medida.

## Auditoría de ejecución

Preservar órdenes y eventos. Una fila de orden identifica estado terminal y
eventos intermedios; un fill parcial no es una orden adicional. Cantidad
solicitada y ejecutada bruta por orden; comisión spot base y cantidad recibida
neta separadas. Capacidad por (cartera, activo, mercado, window_start): sumar
fills brutos sujetos al límite, sin netear BUY/SELL; volumen una vez por clave.
Participación=q/volumen; utilización=q/(participación máxima*volumen). Volumen
elegible posterior sólo se usa para auditoría, nunca para mejorar sizing.
Minutos sin volumen o ausentes, cupo/step, reglas y fondos se distinguen según
evidencia; cuando registros no identifican una causa única, conservar ND o
causas compatibles explícitas. Forzosas del exchange mantienen excepción
original y se muestran aparte, sin extenderla a órdenes voluntarias.

Distribuciones por instrumento/período sobre claves con volumen>0 y fills
voluntarios; cuantiles empíricos sin ponderar por clave. Agregado de cartera:
distribución de fracciones por clave, peso uno por clave, no suma BTC+ETH.
Resúmenes por orden usan peso uno por orden. Cantidades sólo dentro de unidad.

Extremos prefijados por cada cartera: top cinco claves por utilización
descendente, desempate window_start, símbolo y mercado ascendentes; top cinco
episodios de exposición activa descubierta por duración descendente, desempate
inicio y símbolo ascendentes. Episodios se clasifican en trayectoria completa,
uniendo intervalos contiguos de exposición descubierta y excluyendo polvo de
actividad. Guardar catálogo completo; pertenencia a ambos grupos se identifica
por cruce temporal/instrumento, sin sumar registros repetidos.

## Resultados e hipótesis

Ocho períodos originales: full, 2022-2023, 2024+, años 2022/2023/2024/2025 y
enero-agosto 2026. Saldos heredados, CAGR365, Sharpe RF=0/ddof=1, volatilidad
y drawdown diarios, componentes y residual contable. Utilización diaria:
(spot valuado+garantía)/equity. Exposición corregida sobre trayectoria entera,
unión BTC/ETH; polvo valorado y con riesgo aunque no actividad. ND conserva motivo.
A050/A100 se recalculan y normalizan por capital propio, sin escala impuesta.
H1: probar misma proyección y reutilizar una sola evaluación BASE autenticada,
sin duplicar observaciones. H3: probar igualdad de inputs forecast/basis/reglas/
costo y agregado diario; reutilizar oportunidad BASE, recalcular contraste con
nuevos CAGR. H2: CAGR condicional definido, finito, positivo y Sharpe superior
a permanente del mismo escenario/período. H3 ambos caen=favorable, ambos
suben=contraria, demás evaluables=mixta, faltantes=no concluyente.

## Evidencia y límites

Reporte Markdown/HTML, CSV/Parquet y figuras PNG/SVG. Paquete nuevo con código,
configuraciones, fuentes pequeñas y ventanas de volumen; verificación offline
desde otra ruta y pruebas de corrupción aun renovando hashes. Constructor y
verificador comparten lógica de métricas/exposición: declararlo, sin presentarlo
como motor independiente. Datos masivos/corridas completas locales compartidos
en lectura. Estados técnico y económico separados, incluyendo insolvencia sin
fabricar días. Sensibilidad con velas 1m: no estimación empírica de spread, cola
o impacto, ni escalabilidad ilimitada. No nuevos análisis intradía o SOFR.
Se conservan todos los paquetes previos y la excepción histórica documentada
del inventario/config.py; esta extensión tiene su propio diff e identidad.

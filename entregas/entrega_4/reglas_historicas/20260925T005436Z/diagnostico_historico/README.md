# Diagnóstico histórico de exposición — versión técnica preliminar

Resultado ejecutado sobre registros originales BASE_E3; no es un backtest nuevo
ni una decisión de cargar tablas históricas. [Resultados](diagnostico_resultados.json),
[definición de cada columna](esquema_columnas.json) e [inventario leído](input_inventory.csv).

| run_id | Órdenes únicas | Fills | Órdenes sin proxy nocional | Cierres diarios |
|---|---:|---:|---:|---:|
| `run_ad71d751b20623006c195ff3` | 258 | 138 | 120 | 1704 |
| `run_dfea4b7ac1475668d5968c97` | 735 | 332 | 403 | 1704 |

`orders_baseline.csv` deduplica eventos submitted por order_id y concilia con
filas finales. Las cantidades conservan Decimal. El proxy nocional usa cantidad
solicitada por reference_price del primer fill; sin fill no se inventa precio.
No es una comprobación del precio medio que Binance usaba al aceptar la orden.

En `filter_candidates_summary.csv` hay 204 comparaciones (102 hechos por cartera).
No se detectan órdenes registradas fuera de los límites puntuales comparables.
`candidate_orders.csv` y `event_order_candidates.csv` conservan encabezados aunque
tengan cero filas. No se deduce ausencia de entradas que podrían aparecer con
filtros más permisivos. 24 comparaciones de componentes cero MARKET spot quedan
sin semántica de evaluación; no se ejecuta módulo por cero. Las banderas máximas
MARKET falsas se respetan; banderas desconocidas siguen desconocidas. No se
interpolan las capturas ni se les atribuye duración.

Los fact_id/source_id exactos de cada prueba están en las tablas; siguen las
observaciones SPOTI22/SPOTI23/SPOTI25 y FUTI22/FUTI22B/FUTI26/FUTI26B.

| run_id | Activo | Máximo nocional diario USDT | Cierres con short positivo |
|---|---|---:|---:|
| `run_ad71d751b20623006c195ff3` | BTCUSDT | 3665.91320000000 | 276 |
| `run_ad71d751b20623006c195ff3` | ETHUSDT | 3905.52310000000 | 468 |
| `run_dfea4b7ac1475668d5968c97` | BTCUSDT | 4162.46180000000 | 1668 |
| `run_dfea4b7ac1475668d5968c97` | ETHUSDT | 4079.94452000000 | 1608 |

`daily_positions_baseline.csv` deriva short*mark de los 1.704 cierres de cada
cartera y ambos activos (6.816 filas). No observa máximos de posición intradiarios.
`margin_candidates_daily.csv` tiene 32.160 comparaciones sobre cierres con short;
`margin_candidates_summary.csv` resume las 16 tablas relativas por cartera.
Todos esos nocionales seleccionan el primer tramo de cada tabla. Las tablas
BTC coinciden con el mantenimiento base en estas observaciones. Las tasas ETH
de 0,004 o 0,005 reducen mantenimiento frente al 0,0065 base; no producen P&L.
La reducción máxima candidata con 0,004 es 9,76380775 USDT (condicional) y
10,1998613 (permanente), fila `TIERS_MARG23_ETHUSDT_after` / fuente `MARG23`,
con deducción `TIERS_MARG23_ETHUSDT_after_DERIVED`. Ningún cierre observado tiene
saldo de margen menor o igual al candidato. No se infieren liquidaciones,
trayectorias nuevas ni ausencia de riesgo intradiario.

`tier_boundary_checks.csv` comprueba 177 techos de las 16 tablas: piso exclusivo,
techo inclusivo y continuidad analítica de la deducción. La deducción es derivada,
no publicada. No se suman stocks de mantenimiento a los costos ni al P&L.

`event_position_cohorts.csv` identifica 16 exposiciones de cartera/símbolo/evento
desde el ledger. Por ejemplo, en diciembre de 2023 hay short ETH de 1,306 en
condicional y 1,342 en permanente; después hay un fill de aumento en permanente
antes del cierre. Son filas `TIERS_MARG23_ETHUSDT_after` / `MARG23`, con los
run_id anteriores. El aviso preserva posiciones existentes, pero no resuelve
la política de ese aumento. Mayo de 2024 también tiene aumentos posteriores
en ambas carteras (`TIERS_MARG24_*_after` / `MARG24`). Las anclas de despliegues
aproximados sólo localizan exposición y no se transforman en vigencias exactas.

`promo_fill_boundaries.csv`, hecho `BTC_SPOT_ZERO`, fuentes `PROMO_START/PROMO_END`,
encuentra cero fills BTC spot condicionales y diez permanentes dentro del intervalo
según su timestamp registrado. Ningún fill BASE_E3 coincide con los extremos ni
ninguna ventana los cruza. Esto no comprueba las ventanas de las variantes nuevas.

Se contrastaron los miembros y fuentes del manifiesto sellado (incluidas A1–A3),
los 288 valores API contra sus rutas JSON originales y las deducciones contra
el registro. Se verificaron todos los output_hashes de cada corrida y su sello
de manifiesto. `input_inventory.csv` registra los bytes leídos y el chequeo de
conservación al finalizar. Este inventario no sustituye al verificador de publicación
ni certifica el motor o la continuidad de fuentes. No hubo cambios de índice,
commit, publicación externa ni modificación de evidencia original por este comando.

La segunda tanda sólo está propuesta en `docs/entrega_4/reglas_historicas/decisiones_integracion.md`.
No se ejecutó ninguna de sus políticas ni interpolaciones.

Reproducir requiere el paquete sellado, sus dependencias A1–A3, docs/research y
las dos carpetas de corridas originales bajo --runs-root. Usar una salida nueva:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/diagnose_historical_rules_exposure.py --root . --runs-root D:/Backtesting/outputs --output entregas/entrega_4/reglas_historicas/diagnostico_reproducido_nuevo
```

`--root`, `--evidence` y `--runs-root` permiten otra ubicación sin depender de HEAD.
El manifiesto local `manifest.json` protege los productos relativos a esta carpeta;
su hash esperado debe conservarse fuera del paquete al publicarlo. Verificación
de productos, offline y de sólo lectura:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/diagnose_historical_rules_exposure.py --verify-output RUTA_DIAGNOSTICO
```

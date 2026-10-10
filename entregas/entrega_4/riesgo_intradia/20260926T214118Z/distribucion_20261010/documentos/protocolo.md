# Protocolo previo de riesgo intradía y garantías

Estado: registrado antes de la reconstrucción completa y del cálculo de sus resultados. La auditoría de fuentes documenta las convenciones exactas del código congelado en el anexo de disponibilidad. Esta versión se sella mediante `protocolo_sello.json` antes de ejecutar la reconstrucción completa. Los diagnósticos de entradas no constituyen los resultados de riesgo de este bloque.

## Población y selección

BASE condicional run_ad71d751b20623006c195ff3 y permanente run_dfea4b7ac1475668d5968c97. Diagnóstico adicional MARGEN_2X condicional run_70383794701c4f0fc157b2ed y permanente run_3f5d9cce8ff1c2ba5447e3b6 si las mismas fuentes bastan. Intervalo continuo [2022-01-01,2026-09-01), UTC, 10.000 USDT iniciales, sin reiniciar cuentas. Los otros ocho resultados permanecen intactos y no se recalculan.

Antes de mirar resultados se fija: catálogo de TODOS los intervalos activos sin cobertura; detalle del 24/03/2023 con todo el día anterior y posterior; por cartera, peor caída desde pico de equity de toda la muestra y menor holgura aislada de mantenimiento mientras haya un corto. Ventanas de detalle del peor DD desde su pico hasta valle/recuperación; para mínimos de margen, día previo y posterior. Los criterios pueden seleccionar el mismo episodio. Empates: primer instante en el orden original. No se excluyen episodios que terminan con ganancia.

## Tiempo y estados

Unión ordenada de cierres de minuto disponibles, instantes financieros exactos y cierres diarios originales. No se presenta como tick-by-tick. Los eventos simultáneos siguen el orden persistido del ledger: antes del primer evento y después de cada movimiento; no se ordenan por nombre. Esos estados instantáneos tienen duración cero pero integran el riesgo inmediato. La última fila contable de un timestamp rige el intervalo siguiente. Las posiciones persistidas preservan su orden y memoria de residuos, con la función verificada de E3; se clasifica toda la trayectoria antes de cortar períodos.

Equity = caja spot + caja futuros + garantías + valor spot + UPnL futuros - deuda. UPnL corto = cantidad × (precio medio - mark). No se resta slippage otra vez ni se suma funding ya incluido en caja. La auditoría debe demostrar completitud de los movimientos antes de permitir arrastre de saldos. Se verifican todos los cierres originales y sus componentes, con tolerancia 1E-8 USDT; cualquier diferencia inexplicada bloquea interpretar nuevas métricas. Los datos financieros persistidos son Decimal; la vectorización se documenta y contrasta, sin redondear evidencia para imitar el PDF.

## Precios y cobertura

Valuación principal con política original: spot de referencia y mark de riesgo causal, con fuente, cierre, disponibilidad, edad y motivo de arrastre. Marcas aproximadas `futures_scaled` y proxies de funding son categorías distintas. Un mark no es precio ejecutable. Se informan observaciones no evaluables y precios obsoletos; conciliación contable no implica mercado fresco.

Diagnóstico separado durante interrupción spot del 24/03/2023: `S_proxy(t)=S(s)*F(t)/F(s)`, ancla fija anterior alineada válida y futuros ya cerrados disponibles. Posiciones, caja, decisiones y fills originales permanecen fijos. Se rotula `valoracion_proxy_hipotetica`; no sustituye una trayectoria sin suspensión. Sin ancla o futuros válidos: ND con razón. Al volver spot válido se vuelve a observar spot real. No hay precios de ejecución ni ventas hipotéticas inventadas ni combinación de extremos intravela no simultáneos.

## Drawdown y períodos

`DD(t)=equity(t)/max(capital inicial, equity(u), u<=t)-1`. El máximo incluye la observación actual. Equity no positivo se identifica y no se trata como estado seguro. Se muestran dos políticas de pico: acumulado de la trayectoria completa y reiniciado al saldo de entrada real del período. Se incluyen full, 2022, 2023, 2024, 2025, enero-agosto 2026 y los cortes originales pre/post 2024. Los cierres diarios originales están contenidos en la trayectoria intradía; a política y período iguales, el DD intradía no puede ser menor en magnitud. Se reportan pico, valle, recuperación, pérdidas USDT y puntos porcentuales; no dividir por DD diario cero. Caída desde inicio del día y desde máximo intradía son métricas distintas. Los huecos no desaparecen del denominador ni se llama máximo completamente observado a una serie con incertidumbre de precio.

## Incidentes y capital

Cada episodio activo sin cobertura conserva activo, run_id, ciclo/órdenes vinculados y clasificación respaldada por registros (secuencia normal, parcial/desarme, cierre demorado, corrección, interrupción documentada o causa no atribuible). Unión de tiempos de cartera, sin duplicar BTC/ETH. Medir unidades efectivas variables, exposición neta con signo/absoluta, pérdida transitoria y cambio de equity; atribución por activo separada del cambio total contemporáneo, sin atribución causal automática. Polvo sigue valuado pero separado de exposición activa. Control 24/03: 121 minutos esperados como comprobación, sin forzar cifras; control total 11.340/16.440 segundos BASE.

## Garantías

Mientras short>0 se reconstruyen notional, garantía, promedio, UPnL, saldo de margen, mantenimiento, holgura, ratio y distancia usando tramos y fórmulas congelados. MARGEN_2X duplica el importe completo (incluida deducción), mantiene apalancamiento. Short cero: mantenimiento cero y ratios/distancia ND. Saldo no positivo: inseguro, ratio ND explícito.

Se separan mantenimiento exigido, déficit hipotético `max(0,mantenimiento-saldo)`, y capital extra hipotético para satisfacer conjuntamente los umbrales preventivos originales. Se registran desigualdades estrictas: la igualdad puede seguir activando salida. Transferir caja a garantía no cambia equity. Necesidades se suman sólo en el mismo instante y se comparan una vez con caja realmente redistribuible menos compromisos de órdenes acreditables; no se usa garantía ajena ni se vende spot. Si los compromisos no pueden acreditarse, la disponibilidad neta y el faltante externo exactos se declaran ND. No sumar déficits por minuto ni máximos de activos de fechas distintas. Escenarios estáticos sobre estados originales, no aportes reales ni evitación probada de liquidaciones. Después del cierre del futuro del 24/03 el spot expuesto no genera mantenimiento del contrato ya cerrado.


Sea `q` la cantidad corta, `m` el mark, `B` el saldo de margen original y `M(n)` el importe de mantenimiento al nocional `n`, con sus tramos y multiplicador efectivos. Una transferencia adicional `x` debe cumplir simultáneamente:

- `x >= 0`.
- `x > M(q*m)/0.50 - B`, porque la igualdad en el ratio preventivo activa la salida.
- `x >= q*m*0.15 + M(q*m*1.15) - B`, para la distancia mínima a liquidación del 15%, evaluando también el tramo correspondiente al mark adverso.

Se informa el ínfimo `max(0, M(q*m)/0.50-B, q*m*0.15+M(q*m*1.15)-B)` y una bandera que indique si el ínfimo coincide con la frontera estricta del ratio y, por tanto, no alcanza por sí solo para cumplirla. No se inventa un quantum monetario ni se agrega un centavo arbitrario. Estas condiciones describen necesidades instantáneas hipotéticas sobre estados originales, no aportes realizados ni garantía de evitar toda liquidación, cargo o salida.

La disponibilidad neta y el faltante externo exactos son ND cuando los compromisos no se pueden acreditar. Un importe bruto de caja puede mostrarse por separado, rotulado como bruto y sin presentarlo como enteramente disponible. La auditoría de reservas todavía debe determinar qué compromisos pueden reconstruirse.

## Anualidad y cobertura del feedback

Reutilizar sin alterar PnL, retorno, CAGR, Sharpe, capital utilizado al cierre y H1/H2/H3 de las tablas corregidas. 2026 comprende ocho meses. Distinguir equity, capital desplegado, garantía y caja libre; no CAGR dividido por utilización como rendimiento comparable. Nueva tanda pequeña de retrasos/adversidad y benchmark remunerado se proponen como PENDIENTES, sin ejecutar ni elegir tasa/producto. Benchmark de todo el capital y de caja disponible serán distintos; exigir moneda, fuente, disponibilidad, costos, riesgo y garantías.

## Evidencia y aceptación

Serie completa comprimida local con hash; tablas/episodios/figuras y extractos en paquete compacto. Verificación compacta no afirma recomputar máximos de toda la muestra sin serie completa. Comandos con rutas explícitas para cada alcance, pruebas de corrupción y verificación trasladada de sólo lectura. Mantener originales e índice con hashes inicial/final. No hay PDF E3 disponible en el repositorio inspeccionado (sólo antecedentes E1/E2); no se afirma su lectura.

## Anexo: disponibilidad exacta de precios y funding

Fuente: `codigo_base/src/crypto_carry/strategy.py`, `models.py`, `events.py`, `data/normalize.py`, `data/funding_proxy.py` y sus equivalentes congelados en `codigo_ejecutado/`. La [auditoría de precios](../auditoria_precios/diagnostico_precios.md) conserva rutas, esquemas, hashes y la comprobación reproducible de los precios diarios.

La raíz local efectiva es `D:/Backtesting`. Se leen las entradas del manifiesto `data/minutes/2022_2026_continuous/derived_marks/futures_scaled/manifests/processed.json`; todas sus rutas son relativas a esa raíz. La carpeta derivada sustituye sólo tres particiones de marks y referencia las demás particiones originales. No se mezclan las sustituciones con la versión original de la misma partición.

Los tiempos Parquet están en nanosegundos UTC. Una vela normalizada se abre en `open_time` y su cierre se conoce en `end_time = available_at = open_time + 60 segundos`. Su propiedad de precio es `close`. La referencia original spot se renueva sólo cuando `base_volume>0`; se usa el último registro admisible con `available_at<=t`, arrastrando también su procedencia y disponibilidad. Un registro de volumen cero no renueva la edad del precio; un registro ausente tampoco. Los controles de frescura para entrada no eliminan la valoración del inventario al último precio conocido.

Para futuros se usa el mark de riesgo con `available_at<=t`, preservando fuente, clasificación oficial/aproximada y ancla. El mark oficial tiene `close_time = open_time + 59.999 segundos` y disponibilidad un milisegundo después. Los 15 marks `futures_scaled` mantienen sus excepciones originales. No son la misma excepción que `previous_closed_1m` de liquidación de funding.

El cierre diario original a `23:59:59.999999999 UTC` usa normalmente la vela abierta a las 23:58 y disponible a las 23:59. La vela de las 23:59 se publica a las 00:00 del día siguiente y no puede anticiparse. El final de muestra es exclusivo; también se conserva su snapshot terminal original a un nanosegundo antes del límite.

El reloj económico del funding es `funding_time`; `available_at` conserva la disponibilidad informativa, que está 60 segundos después en estas fuentes. Los timestamps con milisegundos no se redondean. En cada instante original se incorporan los datos disponibles, se liquida funding sobre el corto previo a fills simultáneos, se ejecutan fills comprometidos y luego controles. El registro ordenado del ledger conserva los estados pre/post.

Para la suspensión spot del 24/03/2023, las aperturas suspendidas son `[11:28,14:00) UTC`. Los registros abiertos entre 11:28 y 12:39 tienen volumen cero; entre 12:40 y 13:59 faltan registros. La última observación spot/perpetuo alineada válida es la vela de las 11:27, disponible a las 11:28: ésa es el ancla fija del proxy. El primer cierre de reapertura válido corresponde a la vela de las 14:00 y está disponible a las 14:01. Se conserva el precio original hasta entonces y se evalúa el proxy separado sólo con futuros disponibles; a las 14:01 se vuelve al spot observado. Esto distingue el hueco de valoración de la mera ausencia física de registros.

La devolución literal del profesor se conserva en `feedback_e3.md`. `matriz_cobertura_feedback.csv` distingue profesor, encargo, compromisos previos y decisiones metodológicas. Los controles numéricos, fórmulas específicas, elección del proxy y selección de episodios proceden del encargo y su implementación, no de una exigencia numérica atribuida al profesor. Este bloque no completa toda la Entrega 4.

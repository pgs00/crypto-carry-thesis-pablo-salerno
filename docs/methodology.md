# Metodología implementada

## Contrato temporal

Timestamps enteros UTC en nanosegundos. Evaluación base `[2022-01-01, 2026-09-01)`, preparación prevista desde 2020-08-11. No se reinicia capital ni posiciones el 01/01/2024. La muestra descargada y la demo tienen rangos distintos, registrados en sus propias configuraciones.

En cada timestamp: (1) incorporar todos los datos y reglas conocidos; (2) liquidar funding sobre el short anterior a los fills; (3) evaluar liquidación, deuda y riesgo; (4) gestionar timeouts, correcciones y secuencias; (5) actualizar señales disponibles, renovar y decidir con un equity común; (6) procesar fills elegibles. Una orden enviada en ese lote no puede utilizar ninguno de sus trades. La entrada se considera solamente en momentos de señal, no en cada tick.

Una tasa se liquida en `funding_time` y queda disponible para señales 60 segundos después (120/300 en sensibilidades). El último mark cerrado se conoce al terminar su minuto (`close_time + 1 ms` en la fuente Binance); nunca al abrirlo. Los cobros usan su `settlement_mark_price`, no el mark de riesgo. Los cambios efectivos de reglas activan timers aunque no coincidan con un trade.

## Pronóstico y costos

En un ancla `a`, se toman tasas con `a - 336h < t_i <= a` y un antecedente que permita medir el primer intervalo. La ventana debe ser íntegra y cada intervalo corroborado. Con `d_i` en horas y `w_i = 2^(-(a-t_i)/24h)`:

`forecast = 168 * sum(w_i * funding_rate_i) / sum(w_i * d_i)`.

`no_change = 168 * última_tasa / último_intervalo_horas`.

La vida media es temporal, no una cantidad de observaciones. El costo ex ante es `multiplicador * (2 fee_spot + 2 fee_futures + 4 slippage)`. Con 0,10%, 0,05% y 1 bp, resulta 0,34%. Se usan las reglas conocidas al decidir; no se anticipan tarifas de salida futuras. Costos 2x/3x afectan taker y slippage realizado/ex ante, sin multiplicar el cargo de liquidación.

## Carteras y ejecución

Cada estrategia empieza con 10.000 USDT propios. Una sola clase controla ambas; el flag de funding sólo cambia entrada (`forecast > costo`) y renovación (`forecast > 0`). El carry permanente elimina esas dos condiciones, conserva todos los demás controles.

Objetivo spot por activo = `0,30 * equity`; se incorpora polvo previo y se redondea el incremento hacia abajo. La compra descuenta comisión en base. El short cubre cantidad neta spot redondeada al step de Futures. Entrada: comprar spot → esperar 1 segundo desde fill → vender perpetuo. Salida: recomprar perpetuo → esperar 1 segundo → vender spot negociable.

Cada orden llena por el primer trade `envío < trade_time < deadline`, timeout de 30 segundos y fill total independiente del volumen de ese trade. El slippage es adverso al lado y el tick se redondea adversamente. En VWAP se observan trades de `(envío, envío+5s]`, se pondera por cantidad y se ejecuta recién al cerrar esa ventana; sin trades no hay precio ni fill. Los reintentos crean nuevas órdenes y conservan exposición/costos previos.

Antes de comprometer capital se reservan spot, fee Futures, garantía y open loss; al fill se vuelven a comprobar fondos y filtros. No se financia con deuda ni se usan reservas de otro activo. Se bloquean entradas y aumentos con cualquiera de los trades de más de 60 segundos. Las salidas y el margen continúan.

Tenencia de 168 horas desde completar el par, renovable en bloques iguales. No se aplica el filtro de basis de entrada a la renovación. Sólo se rebalancea al renovar y si `abs(valor_spot - 0,30 equity)/(0,30 equity) > 0,05`; la igualdad no rebalancea. Aumentos spot→perpetuo; reducciones perpetuo→spot. Sin órdenes no hay comisiones ni cambio de basis de referencia.

## Riesgo y deuda

`basis = último_trade_futures / último_trade_spot - 1`; entrada inclusiva `[0, 0,005]`. Al completar un par o ajuste se guarda el basis observado. En cierres de minuto se sale si aumenta al menos 0,02 frente a la referencia. Las correcciones de hedge no la modifican.

Garantía al aumentar short: `q * fill / 2 + max(0, q*(mark-fill))`. Precio medio ponderado por cantidad. `UPnL = q*(precio_medio-mark)`; `margin_balance = garantía + UPnL`; `maintenance = q*mark*tasa_tramo - deducción`. El precio de liquidación candidato es `(garantía + q*precio_medio + deducción)/(q*(1+tasa_tramo))`; debe pertenecer al tramo usado. Tramos insuficientes bloquean certificación.

Liquidación total si saldo no positivo o saldo <= mantenimiento. De otro modo, salida preventiva si `mantenimiento/saldo >= 0,50` o `(precio_liquidación-mark)/mark < 0,15`. La orden forzosa usa la misma primera operación posterior; conserva el cargo histórico y aplica fee ordinario sólo si la regla lo exige. Una liquidación ya disparada no se cancela por transferencias posteriores.

Descalce = `abs(spot_neto-short)/spot_neto`. Estrictamente >2% activa corrección sólo de Futures. Debe llegar a <=0,5% en 60 segundos o desarmar. Una secuencia normal entre patas no activa este detector, pero sí mantiene los otros riesgos. Short con spot cero es crítico. Inactividad real de >30 minutos en cualquier pata provoca salida; un archivo desconocido produce `incomplete_data`.

Funding = short anterior a fills × mark de cobro × tasa. Positivo entra a caja Futures y cancela deuda primero. Negativo usa caja Futures, garantía del mismo contrato y luego caja spot libre; el remanente es deuda, sin reponer automáticamente garantía. Otras obligaciones usan caja Futures, caja spot y garantía liberada; nunca garantía de otro activo ni ganancia spot no realizada. La deuda selecciona cierres BTC→ETH y se reevalúa tras cada realización.

## Contabilidad

`equity = efectivo_spot + efectivo_futures + garantías + inventario_spot * precio_spot + UPnL_futures - deuda`.

Se concilia cada movimiento y la atribución acumulada: P&L spot realizado/no realizado + P&L Futures realizado/no realizado + funding − fees − cargos de liquidación = equity − capital inicial. Slippage está dentro de precios y se presenta como diagnóstico, sin restarlo otra vez. Transferencias y constitución/liberación de garantía no crean P&L. La venta parcial libera garantía y costo spot proporcionalmente. El promedio Futures restante no cambia al reducir.

La insolvencia conserva equity negativo y obligaciones; no se trunca a cero. El final del período valúa posiciones abiertas, sin cierre ni comisión terminal, y no permite funding ni fills posteriores.

## Evaluación y salidas

H1 usa la suma de funding real en `(señal, señal+horizonte]`. Se excluyen horizontes que salgan de la muestra o cuyo calendario/antecedente/límite no pueda verificarse. Se comparan EWMA y no-change en las mismas observaciones por activo, luego con igual peso. Se reportan MAE, observaciones y exclusiones, por período completo y regímenes. Los horizontes solapados no son observaciones independientes.

Retornos diarios de equity a cierre UTC, capital inicial como referencia del primer retorno. CAGR usa duración calendario/365; Sharpe y volatilidad usan desviación muestral (`ddof=1`) y raíz de 365, RF cero. Se conserva retorno/pérdida observada aunque CAGR/Sharpe resulten nulos por equity no positivo. Con menos de dos retornos o volatilidad nula, Sharpe es nulo con motivo. Drawdown incorpora capital inicial y duración real sin reset en los cambios de régimen.

H2 es descriptivamente favorable sólo con CAGR condicional positivo, Sharpe superior al permanente y cobertura válida. Un prefijo se etiqueta como diagnóstico. H3 calcula cada minuto, independientemente de saldo, posición o cooldown: forecast si pasa funding/costo, basis y datos/operatividad; cero si datos completos pero no elegible. Cada día exige 1.440 minutos por ambos activos. Se promedian ceros y activos con igual peso. Datos desconocidos excluyen el día conjunto. H3 compara oportunidad y CAGR condicional de 2022–2023 frente a 2024+; sin cobertura suficiente es no concluyente. No se atribuye causalidad.

Los archivos de la corrida preservan decimales como strings y estadísticas como floats. El reporte y PNG/SVG se construyen sólo desde tablas guardadas; hashes y configuración permiten verificar/reproducir. Las pruebas y demo sintéticas validan software, nunca hipótesis históricas. Ver `decisions.md` para supuestos, integración, fallas y límites.

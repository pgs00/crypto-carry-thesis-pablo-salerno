# Decisiones y evidencia

La especificación es `sources/Prompt_Codex_Backtesting.md`. El usuario autorizó implementarla y confirmó VIP 0 fijo, sin BNB ni referidos, con promociones generales sólo documentadas. También fijó **20.000.000.000 bytes** como límite inicial y pidió validar una muestra antes de ampliar. El 18/09/2026 pidió descargar personalmente la historia completa en D: e inició esa descarga con `configs/download_full_d.toml`, cuyo límite separado es 800 GB. La muestra y `configs/base.toml` conservan el límite original.

## Criterio de fiabilidad para una posible prueba futura

El 18/09/2026 el usuario indicó que podría considerar una prueba con capital propio si los resultados fueran favorables. Se exige mantener trazabilidad, bloqueos por evidencia faltante, conciliación y resultados adversos visibles. La evaluación del software, la cobertura histórica y la preparación para operar se verifican por separado. Los límites de ejecución completa y mark por minuto requieren validación adicional antes de usar el estudio para esa decisión; condiciones y pendientes en [fiabilidad](fiabilidad.md). Este requisito no cambia los parámetros del baseline ni autoriza operaciones reales.

## Fuentes y almacenamiento

- Código, entorno, muestra y resultados existentes permanecen en la carpeta del proyecto en C:. La descarga completa del usuario usa la raíz `D:\Backtesting`, con aproximadamente 958 GB libres al iniciarla. El límite de datos cuenta crudos, Parquet, manifiestos y temporales bajo `data/`. Cada escritura del pipeline se controla antes de publicar; los Parquet se comprimen por lotes en memoria para comprobar su tamaño antes de escribir.
- La muestra comprende el 01/01/2024 UTC. Funding incluye ventana y antecedentes; marks incluye el día anterior para disponer de un minuto cerrado al iniciar. La descarga predeterminada siempre es `sample`; `--scope full` solicita la historia desde `history_start` y respeta el presupuesto del archivo de configuración elegido. La ampliación está siendo ejecutada por el usuario; su inicio no acredita una descarga terminada ni datos históricamente completos.
- Fuentes oficiales: [Binance Public Data](https://github.com/binance/binance-public-data), [Data Vision](https://data.binance.vision/), [API USD-M](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History). Las URLs exactas y hashes de cada objeto están en los manifiestos locales.
- No se retrotraen `exchangeInfo`, comisiones actuales ni tramos actuales. `data/rules/history.json` está vacío: faltan snapshots históricos completos y verificables. El perfil de tarifa confirmado identifica qué evidencia buscar; no demuestra una tarifa constante durante 2022–2026.
- Se detectaron discontinuidades de IDs dentro de los ZIP oficiales de Futures, aun verificando su checksum. La auditoría del 18/09/2026 concilia los conteos, cantidades, OHLC y volumen calculado de la muestra con velas oficiales; los saltos numéricos no prueban por sí solos pérdida de trades públicos. La causa de cada salto y la cobertura estricta siguen pendientes. Se documentó además una anomalía del campo `quote_qty` BTC, sin alterar el raw. Ver `research/README.md`.
- No se inventa el mark de cobro. La auditoría completa de la API del 18/09/2026 encontró 2.005 cobros por activo sin `markPrice` dentro de 2022–2026; el primer mark disponible fue el 31/10/2023 a las 08:00 UTC. Las respuestas originales y sus hashes quedaron guardados. Funding se contrasta con los timestamps, duración publicada y tasa del calendario Data Vision; una omisión compartida no demuestra un cambio de frecuencia.
- Los PDF de Entrega 1 y Entrega 2 disponibles en `../Informes` se leyeron como contexto. El segundo archivo no tiene el sufijo `(6)` de la referencia, por lo que no se afirma identidad. No estaban el DOCX de entregables ni la imagen de feedback. Se usó el texto autocontenido que la consigna permite.

## Integración Nautilus comprobada

Se fijó NautilusTrader **1.231.0**, Python **3.14** y el lock de dependencias. Las APIs se comprobaron contra la distribución instalada: `BacktestEngine.add_venue/add_data/run/end`, `SimulationModule.exchange`, `OrderMatchingEngine.fill_order`, `Strategy.subscribe_data`, `order_factory.limit`, `clock.set_time_alert_ns` y callbacks de fills. La documentación web `latest` puede describir otra versión.

El motor reproduce lotes completos por timestamp como `CustomData`. Gestiona órdenes, aceptaciones, cancelaciones, fills y posiciones nativas. Se usan órdenes límite nativas inertes como portadoras del ciclo de vida; no representan un precio límite económico. El adaptador deshabilita matching automático de trades/barras y, después de aplicar la elegibilidad del estudio, llama al matcher nativo para emitir exactamente el fill completo. El precio económico es el primer trade posterior más slippage y redondeo adverso, aunque la operación observada sea menor que la orden.

La cuenta nativa está congelada y las comisiones nativas son cero. Sólo el ledger del proyecto mueve dinero y funding. Esto evita dos mecanismos económicos simultáneos. La posición spot nativa bruta se concilia con `spot neto + comisiones históricas acumuladas en unidades base`; la posición Futures nativa se concilia con el short del ledger. El equity nativo no se presenta como resultado de la tesina. Se exige coincidencia de cantidad, precio y reloj en cada fill.

`manage_stop=False` evita liquidaciones terminales. Los timers no se pierden entre particiones. El checkpoint es JSON con hash, config, reglas, inputs y hash recursivo del código; reconstruye portadoras nativas sin nuevos movimientos del ledger. No usa pickle. Cambiar el código, inputs o reglas exige una corrida nueva, no reanudar la anterior.

## Resoluciones conservadoras

- Dinero y cantidades usan Decimal; la tolerancia contable es 1e-8 USDT y no amplía umbrales de riesgo. La precisión de las portadoras nativas es de 8 decimales; una divergencia visible falla, nunca redondea silenciosamente el ledger.
- Las reservas de ambos activos usan un snapshot común del equity y prioridad BTC→ETH. Para deuda se realiza primero BTC y se reevalúa antes de seleccionar ETH; las liquidaciones independientes siguen teniendo prioridad.
- Un intento fallido de primera pata de rebalanceo no borra el par: vuelve a HOLDING, libera la reserva y bloquea nuevas ampliaciones durante 24 horas desde el fallo. Una falla de segunda pata desarma todo. Se permite renovar la tenencia existente durante ese bloqueo si cumple sus controles.
- Una suspensión no transforma inventario en polvo. El cierre conserva su intención y vuelve a enviar cuando los filtros permiten negociar. Polvo significa únicamente cantidad inferior al incremento/mínimo o nocional mínimo; sigue valuado.
- El volumen de participación se congela al enviar cada orden en `[envío - 60 s, envío)`. No se usa volumen posterior al envío. Se registra el intento aunque no tenga fill. No se estima impacto de mercado.
- La estrategia se detiene ante datos indispensables desconocidos con exposición; conserva posición, deuda y último estado. El CLI impide una corrida histórica estricta si falla la validación previa. En ese caso genera un diagnóstico sin curva artificial de efectivo.
- Las sensibilidades son predefinidas, de una variable por vez, salvo horizonte/permanencia que cambian juntos. No se optimiza ni se reemplaza `configs/base.toml`. Si el baseline histórico no es evaluable, se registran los escenarios como incompletos sin correr una historia ficticia.

## Límites explícitos

USDT a la par de USD; transferencias instantáneas y gratuitas; efectivo y tasa libre de riesgo a cero; sin impuestos, insolvencia del exchange, ADL, liquidaciones parciales ni libro completo. Los fills son completos y no tienen restricciones de liquidez endógenas. Mark cerrado por minuto puede omitir extremos intraminuto. Estos supuestos limitan inferencias económicas y de escalabilidad.

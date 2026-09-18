# Comisiones históricas Binance: BTCUSDT / ETHUSDT

Investigación consultada el **2026-09-18**. Estado: **cobertura parcial, no apta todavía para certificar un backtest íntegro**. Ventana objetivo: `[2022-01-01T00:00:00Z, 2026-09-01T00:00:00Z)`; preparación desde 2020. Perfil: VIP0 fijo (denominado *Regular* en anuncios posteriores), sin pago de comisiones con BNB, sin referidos, sin programas de liquidez/taker ni cupones particulares. Se consideran operaciones ordinarias de libro spot y perpetuos USDT de Binance.com.

El archivo JSON contiguo es evidencia de investigación, **no un historial de reglas ejecutable**. No se modificó `data/rules/history.json`, código del simulador, descarga ni datos existentes.

## Resultado utilizable

- **BTCUSDT spot:** maker y taker cero en `[2022-07-08T14:00:00Z, 2023-03-22T00:00:00Z)`. Inicio y final están documentados por anuncios oficiales [S3] y [S5].
- **ETHUSDT spot:** la promoción del Merge de agosto/septiembre de 2022 **no aplica**: el par anunciado fue ETH/BUSD [S4]. No se encontró en esta revisión una promoción general de comisión cero para ETHUSDT.
- Las tablas históricas regulares de spot muestran **0,1000% maker / 0,1000% taker** en anuncios efectivos en 2021, 2022, 2023 y 2024 [S1, S2, S6, S7]. Son evidencia histórica concreta, pero una búsqueda sin resultados no certifica que no existieran otras promociones intermedias.
- **Perpetuos USDT:** los anuncios de 2019 y 2021 documentan **0,0200% maker / 0,0400% taker** [F1, S1]. Un artículo oficial referido expresamente a noviembre de 2025 indica **0,0200% / 0,0500%** [F2]. **Falta el anuncio o registro primario que establezca la fecha efectiva del cambio del taker de 0,04% a 0,05%.** No debe aplicarse la tarifa reciente retroactivamente ni inventarse una fecha de corte.

Las tasas son por ejecución sobre el importe negociado, no el costo de un viaje completo. Conversión a fracción: `0,1% = 0.001`; `0,02% = 0.0002`; `0,04% = 0.0004`; `0,05% = 0.0005`. Una orden limitada que ejecuta inmediatamente puede ser taker; el tipo de orden por sí solo no prueba maker [F4].

## Cronología de hechos y alcance de la evidencia

Las fechas de publicación se transcriben como las muestra Binance. Sus cabeceras no explicitan zona horaria; no se les asigna `Z` en el JSON. Las vigencias del cuerpo sí indican UTC y se normalizan con `Z`. Publicación, última edición y comienzo efectivo son campos distintos.

| ID | Publicación mostrada | Vigencia explícita UTC | Mercado / hecho | Maker / taker sin descuentos | Límite |
|---|---|---|---|---|---|
| F1 | 2019-12-18 09:51 | Desde 2019-12-20T08:00:00Z | Tabla base Binance Futures para Regular | 0,020% / 0,040% | Sin final verificado; ancla anterior a 2020, no prueba continuidad hasta 2026. |
| S1 | 2021-12-15 08:04 | Desde 2021-12-21T06:00:00Z | Tabla base spot y USD-M para Regular | Spot 0,1000% / 0,1000%; USD-M 0,0200% / 0,0400% | Separa USD-M de COIN-M. Nota de edición 2022-03-14: cambio de nombre VIP0 a Regular. |
| S2 | 2022-05-31 10:13 | Desde 2022-06-01T08:00:00Z | Cambio VIP4+; fila Regular spot permanece igual | Spot 0,1000% / 0,1000% | Declara Futures sin cambios; no publica nueva cifra Futures. |
| S3 | 2022-07-06 14:00 | Desde 2022-07-08T14:00:00Z | Promo general de 13 pares BTC spot, incluye BTC/USDT | 0% / 0% | Inicialmente hasta nuevo aviso; [S5] determina el final BTCUSDT. Edición 2023-03-23 lo confirma. |
| S4 | 2022-08-23 14:00 | `[2022-08-26T00:00:00Z, 2022-09-26T00:00:00Z)` | Promo ETH/BUSD spot | 0% / 0% | **Fuera de alcance de ETHUSDT**, aunque sea el mismo activo base. |
| S5 | 2023-03-15 06:10 | Desde 2023-03-22T00:00:00Z | BTC/USDT vuelve a las tarifas estándar del nivel VIP | Estándar; el anuncio no cuantifica la fila VIP0 | Última edición indicada 2023-11-22 afecta otros pares; no trasladar sus condiciones a BTCUSDT. |
| S6 | 2023-05-31 08:00 | Ajustes entre 2023-06-29T02:00:00Z y 2023-06-29T06:00:00Z | Cambio VIP3+; Regular spot permanece igual | Spot 0,1000% / 0,1000% | Futures sin cambios en este anuncio. No usar 02:00 como hora exacta de todos los cambios. |
| S7 | 2024-10-07 09:00 | Cambios completados antes de 2024-10-14T06:00:00Z | Nueva tabla VIP3–9; Regular spot | 0,1000% / 0,1000% | El texto no da hora única de inicio; columna promocional USDC no aplica a USDT. |
| F2 | 2025-11-14, sin hora | Referencia expresamente a noviembre de 2025; sin corte horario | Blog oficial sobre arbitraje spot/perpetuo, tarifas Regular Futures | 0,02% / 0,05% | Observación fechada, no anuncio del cambio. No se usa su frase ambigua sobre costo spot total. |
| F3 | 2026-02-02 06:00 | Promo TradFi `[2026-02-04T02:00:00Z, 2026-03-31T02:00:00Z)` | Descuento TradFi de 50% respecto al taker estándar USDT; fila Regular 0,025% | Base USDT taker **0,05% por inferencia aritmética** | Promo TradFi excluida del backtest BTC/ETH. Corrobora magnitud base, no fecha original de cambio. |

La aplicación candidata de spot sería tarifa base 0,001 en fracción, con la excepción BTCUSDT de [S3]+[S5]. Esa continuidad fuera de la promoción sigue siendo una **reconstrucción pendiente de revisión de cobertura**, no una serie íntegramente certificada. En Futures ni siquiera se puede cerrar todavía el corte 0,0004/0,0005.

## Fuentes primarias exactas

- **F1 — Binance Futures Fee Update – Improved Fee Structure & VIP Discounts:** <https://www.binance.com/en/support/announcement/detail/360037673592>. Lectura directa. La edición declarada de 2022-03-14 renombra VIP0; conserva 0,02%/0,04%.
- **S1 — Binance VIP Program Upgrade (2021-12-21):** <https://www.binance.com/en/support/announcement/detail/88ee9834fef947de96e01b77e888414e>. El buscador devolvió el artículo y sus tablas; la apertura inglesa redirigió al índice. Corroboración directa en traducción oficial: <https://www.binance.com/es/support/announcement/detail/88ee9834fef947de96e01b77e888414e>.
- **S2 — Binance VIP Program Upgrade: Enjoy VIP 9 Equivalent Spot Trading Fees:** <https://www.binance.com/en/support/announcement/detail/40669f3da342426c87b083b659673316>. Lectura directa; el beneficio VIP4+ no altera VIP0.
- **S3 — Binance Launches Zero-Fee Bitcoin Trading:** <https://www.binance.com/en/support/announcement/detail/10435147c55d4a40b64fcbf43cb46329>. Lectura directa; base y cotización del par son esenciales.
- **S4 — Binance Launches ETH/BUSD Zero-Fee Trading:** <https://www.binance.com/en/support/announcement/detail/5d8f9c0a68e24b82bff743a342dfa9b9>. Lectura directa; exclusión comprobada para ETHUSDT.
- **S5 — Updates on Zero-Fee Bitcoin Trading & BUSD Zero Maker Fee Promotion:** <https://www.binance.com/en/support/announcement/detail/be13a645cca643d28eab5b9b34f2dc36>. Lectura directa; BTC/USDT figura entre los pares que vuelven a tarifa estándar.
- **S6 — Binance VIP Program, Standard Referral and Affiliate Programs Update:** <https://www.binance.com/en/support/announcement/detail/28356ec3f2e241eeb8aa0d9c5c524df5>. Lectura directa; edición declarada 2023-06-15 ajustó el horario efectivo.
- **S7 — Binance Updates VIP Program for Spot and Margin Trading Fees for VIP 3 to 9 Users:** <https://www.binance.com/en/support/announcement/detail/024a848244a84511a70e6e6f60ba4c85>. Lectura directa.
- **F2 — What Is Binance Funding Rate Arbitrage Bot – And How to Use It:** <https://www.binance.com/en/blog/tech/3611863022773164727>. Lectura directa. Evidencia auxiliar de noviembre de 2025; no serie de tarifas.
- **F3 — Binance Futures Introduces Limited-Time 50% Trading Fee Discount for TradFi Perps (2026-02-04):** <https://www.binance.com/en/support/announcement/detail/48edba3e6d0d465faaf9576067270514>. Lectura directa; conserva notas de extensiones posteriores.
- **F4 — Binance Futures Fee Structure & Fee Calculations:** <https://www.binance.com/en/support/faq/detail/360033544231>. Página publicada 2019-09-09 13:39, edición visible 2026-05-01 11:51. Sus ejemplos actuales usan 0,02%/0,05%, pero la propia página los califica como tasas hipotéticas. **No fechar esas tasas en 2019 por la cabecera.**

## Promociones y cambios que no deben contaminar estas series

Se revisaron además fuentes que ilustran errores frecuentes de alcance:

| Fuente oficial | Publicación / vigencia UTC | Motivo de exclusión |
|---|---|---|
| [COIN-M 2023](https://www.binance.com/en/support/announcement/detail/f4433fc2964b4c92998132f433edff7c) | Publicación 2023-09-18 08:00; efectivo aproximadamente 2023-09-26T04:00:00Z | Cambio Regular maker de 0,01% a 0,02%, taker 0,05% constante; es COIN-M, no BTCUSDT/ETHUSDT USDT-M. |
| [BUSD-M 2022](https://www.binance.com/en/support/announcement/detail/f04be598f6c649c9add60b7d24e3f391) | Publicación 2022-10-19 09:05; desde 2022-11-01T00:00:00Z | Contratos BUSD, no USDT. |
| [Lanzamiento de futuros USDC](https://www.binance.com/en/support/announcement/detail/4ff3534898ab4ea09afb450a94f20afe) | Publicación 2023-12-28 09:50; promo `[2024-01-03T12:30:00Z, 2024-04-03T12:30:00Z)` | Descuento 10% para contratos USDC; no cambia BTCUSDT/ETHUSDT. |
| [Taker Program 2022](https://www.binance.com/en/support/announcement/detail/b724eb48c24c42dcb7b5083498019ad4) | Publicación 2022-10-14 10:40; desde 2022-11-01T00:00:00Z | Requiere solicitud y evaluación de volumen/ratio. No es descuento automático general VIP0. |
| [Liquidity Provider 2022](https://www.binance.com/en/support/announcement/detail/5d3a662d3ace4132a95e77f6ab0f5422) | Publicación 2022-07-20 08:57; criterios 2022-07-25T00:00:00Z; rebates 2022-08-02T04:00:00Z | Reglas especiales ETHUSDT corresponden a participantes del programa, no al perfil base. |

Binance Square contiene publicaciones de terceros incluso bajo `binance.com`; no se usaron como evidencia de tarifas. Tampoco se confundieron premios de torneos, Convert, P2P o descuentos de pares con otra stablecoin con el costo ordinario del libro de órdenes.

## Huecos y siguientes acciones

1. **Futures VIP0:** localizar la transición 0,04% a 0,05% con vigencia UTC; las fuentes encontradas no cierran esa fecha. No rellenar el intervalo desconocido desde una FAQ mutable o con la fecha de un blog.
2. **Spot 2025–2026 y cobertura de promociones:** las anclas de 2021–2024 son consistentes; falta un relevamiento exhaustivo de anuncios hasta el corte 2026-09-01. La ausencia de resultados de búsqueda no equivale a ausencia de cambios.
3. **Preparación spot 2020–2021:** falta una fuente tarifaria contemporánea anterior al anuncio de diciembre de 2021. Si el calentamiento solo calcula indicadores y nunca genera operaciones, ese hueco no genera costos simulados; debe quedar explícito en la configuración.
4. **Publicación y revisiones:** preservar metadatos y diferencias por edición. Se vio una redirección en la URL inglesa de S1 y tablas actualizadas posteriormente en otros anuncios. Un enlace vivo no es una captura histórica inmutable.
5. **Comprobación actual:** <https://www.binance.com/en/fee/futureFee> devolvió “No records found” en la extracción pública; no se obtuvo de allí una tabla actual verificable, y una tabla actual tampoco resolvería la historia.

Se puede continuar sin intervención del usuario con búsqueda de anuncios primarios, registro de evidencia y clasificación de intervalos desconocidos; preparar comprobaciones de fronteras de la promo BTC; y comparar explícitamente escenarios Futures taker 0,0004 y 0,0005 para medir sensibilidad. **Los escenarios no sustituyen la cronología real.**

Adoptar una tarifa constante, una fecha de transición supuesta o declarar cobertura íntegra sería una decisión metodológica adicional. No se tomó aquí. Otra vía futura es una respuesta documentada de Binance o estados históricos de cuenta que incluyan comisiones y nivel VIP, si se autorizara obtenerlos; no se contactó a terceros ni se accedió a cuentas.

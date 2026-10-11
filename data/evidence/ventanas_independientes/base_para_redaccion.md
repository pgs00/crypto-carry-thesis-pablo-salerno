# Base factual para la Entrega 3

## 1. Implementación

El motor compara dos reglas de carry sobre BTCUSDT y ETHUSDT: compra spot y venta del perpetuo lineal USD-M. Cada estrategia tiene caja, posiciones y garantías propias. El escenario principal es `vwap_joint`, seleccionado antes de sus resultados; las variantes ya ejecutadas quedan en el anexo técnico. Esta preparación reutiliza resultados persistidos y no ejecuta nuevas simulaciones.

Las corridas utilizaron Python 3.14.3, NautilusTrader 1.231.0, NumPy 2.3.5, pandas 2.3.3, PyArrow 25.0.1, Matplotlib 3.11.2 y httpx 0.28.1. NautilusTrader mantiene órdenes, fills y posiciones nativas. La política del proyecto controla el procesamiento temporal y la ejecución, y concilia los eventos con su propio registro contable Decimal. Las cuentas nativas están congeladas, el riesgo nativo se omite y sus comisiones son cero: la economía se registra en el ledger del proyecto. Esta integración no constituye una validación independiente de toda la lógica financiera.

Se utiliza la revisión corregida `revision_eb5ed744b30836a39fd694fa`, con las corridas `run_f4151cc97937f3704d77fb14` y `run_519a165818e2cadce24bc873`. Sus manifiestos, configuraciones y fuentes numéricas están incluidos en [evidencia](evidencia/execution_revision_report.md).

## 2. Metodología vigente

Las ventanas UTC son `[01/09/2022, 01/09/2023)` y `[01/09/2025, 01/09/2026)`. Cada una reinicia 10.000 USDT por estrategia, sin continuidad entre períodos. La precarga de funding cubre 360 horas y el antecedente necesario; sólo alimenta el pronóstico, cuya ventana efectiva es 336 horas. La EWMA tiene vida media de 24 horas, normaliza tasas por duración efectiva del intervalo y pronostica 168 horas. La señal se evalúa 60 segundos después del timestamp real del funding, conservando su fracción temporal.

La condicional entra si el pronóstico supera el costo de ciclo; renueva si supera cero. El costo configurado es `2×0,001 + 2×0,0005 + 4×0,0001 = 0,0034`: 0,34% o 34 puntos básicos. Se compara con funding acumulado en unidades decimales equivalentes. Son tarifas prescritas fijas, sin descuentos, no una reconstrucción histórica verificada. Ambas reglas conservan el basis inclusivo `[0; 0,005]`, tenencia y renovación de 168 horas. La permanente omite el filtro de funding, pero mantiene basis y demás controles: no permanece necesariamente invertida.

La observación utiliza cierres spot y perpetuo del mismo minuto, con actividad positiva y frescura máxima de 60 segundos. La ejecución utiliza el VWAP —volumen cotizado dividido por volumen base— de la primera ventana completa que comienza al enviar la orden o después, y registra el fill al finalizarla. Aplica slippage adverso de un punto básico y redondeo al tick. La participación agregada se limita al 1% del volumen por instrumento, minuto y cartera; puede haber fills parciales. El remanente vence tras esa única ventana. Los campos heredados de demora de un segundo, VWAP de cinco segundos y timeout de 120 segundos quedan serializados; esta política fija directamente el vencimiento al cierre de la ventana elegible.

El sizing conjunto busca previamente la mayor pareja factible, con objetivo neto spot del 30% del equity por activo, apalancamiento 2 y tolerancia de cobertura del 0,5%. Considera fees, pasos, fondos, margen y polvo existente. Compra spot antes de abrir futuros; desarma futuros antes de vender spot. Las garantías están segregadas por activo. Se preservan rebalanceo al 5%, corrección ante descalce mayor al 2%, salida por basis del 2%, controles de margen, inactividad de 30 minutos y enfriamiento de 24 horas.

El orden temporal es datos, funding sobre el short previo, fills comprometidos, riesgo y estado, vencimientos y reintentos, decisiones. La valuación usa el cierre spot y mark cerrado del perpetuo; el mark de cobro de funding es independiente. El riesgo se observa por minuto. Al terminar no se fuerza un cierre ni se descuentan comisiones hipotéticas.

## 3. Resultados principales

Las cuatro carteras abarcan 365 días completos. Retorno y CAGR coinciden por la duración anual. El Sharpe usa retornos diarios, volatilidad muestral y tasa libre de riesgo cero; el drawdown es diario y no acota pérdidas intradiarias.

| Ventana / estrategia | Equity final USDT | Retorno / CAGR | Sharpe | Drawdown diario | Aperturas / ciclos cerrados / fills |
|---|---:|---:|---:|---:|---:|
| 2022–2023 condicional | 10.073,64 | 0,7364% | 1,918 | −0,1224% | 1 / 1 / 18 |
| 2022–2023 permanente | 10.334,40 | 3,3440% | 4,110 | −0,1359% | 6 / 4 / 72 |
| 2025–2026 condicional | 10.000,00 | 0% | ND | 0% | 0 / 0 / 0 |
| 2025–2026 permanente | 10.008,60 | 0,0860% | 1,960 | −0,0095% | 1 / 0 / 2 |

ND corresponde a volatilidad nula, no a Sharpe cero. Los intentos de orden fallidos fueron 121, 240, 0 y 0, respectivamente; incluyen reintentos y no equivalen a aperturas fallidas. Los ciclos abiertos al corte conservan su P&L y funding.

El resultado temprano condicional combina 39,46 USDT por precios, 51,27 de funding y −17,10 de comisiones; el permanente, 107,09, 286,46 y −59,15. La permanente tardía registra 4,76, 8,31 y −4,47; la condicional tardía permanece en cero. No hubo cargos de liquidación. Spot y futuros se conservan separados en la tabla; el slippage ya está incorporado en sus precios.

El capital utilizado medio diario fue 842,51; 7.187,87; 0 y 137,11 USDT. El tiempo cubierto fue 1.627,85; 13.601,90; 0 y 255,95 horas-activo. Estas duraciones suman símbolos; polvo y exposición sin cobertura están separados. El capital utilizado es inventario spot valorizado más garantía de futuros, no una fracción invertida acotada por el capital inicial.

Fuentes: [resultados](tablas/resultados_principales.csv), [P&L](tablas/pnl_componentes.csv), [actividad](tablas/actividad_y_rechazos.csv) y [series diarias](datos/equity_diaria.csv).

## 4. Hipótesis

H1 presenta menor MAE de EWMA que del pronóstico sin cambio: 0,00073006 frente a 0,00098277 temprano, y 0,00043679 frente a 0,00067508 tardío. Cada comparación reúne 2.146 observaciones y excluye 44 por falta de horizonte realizado completo. Es evidencia descriptiva sobre errores de funding acumulado, sin prueba de significancia ni inferencia automática de rentabilidad.

H2 resulta contraria al criterio temprano: la condicional gana dinero, pero su Sharpe es inferior al permanente. En la ventana tardía es no concluyente porque no opera y su Sharpe es indefinido. H3 es favorable descriptivamente: la oportunidad media pasa de 0,0000166721 a cero y cae el CAGR condicional. La comparación utiliza ventanas independientes; no cubre continuamente 2024 ni identifica causalidad o compresión estructural de todo el mercado. Los criterios exactos están en [hipótesis](tablas/hipotesis.csv).

## 5. Problemas y limitaciones

La [matriz de cambios](tablas/cambios_metodologicos.csv) distingue el diseño de Entrega 2 de las decisiones posteriores: muestra, granularidad, alineación, ejecución, parciales, sizing, prioridad y supuestos. La auditoría verificó 4.380 observaciones de mercado y 8.760 decisiones, sin discrepancias bajo su tolerancia. Incluyó los tres casos de basis cero como elegibles. El defecto corregido afectaba el conteo de rechazos de funding de la permanente; el reporte se regeneró sin modificar operaciones ni resimular.

La mayoría de los basis observados en decisiones fueron negativos. Eso restringe entradas, pero no describe todos los minutos del año ni cotizaciones bid/ask ejecutables. El bajo número de operaciones limita la generalización.

El cambio de equity del 24/03/2023 fue 35,908875575 USDT para la condicional y 72,96391150798 para la permanente: 48,76517009% y 21,81941573% de sus respectivos beneficios anuales. Es comparación diaria/anual, no atribución causal a un fill ni resultado de eliminar el episodio. Los desarmes dejaron 121 minutos por activo sin cobertura, exponiendo inventario a movimientos direccionales.

Las 2.190 observaciones económicas únicas de funding temprano usan el mark causal del minuto cerrado anterior; las 2.190 tardías tienen mark exacto. El calentamiento agrega 92 observaciones por ventana y se informa aparte. Consumir una observación no implica un pago con cartera vacía. El proxy temprano carece de cota de error. Filtros, márgenes y cargos prescritos, ejecución VWAP, capacidad simulada y garantías segregadas limitan la interpretación. Conciliación y auditoría del basis no certifican todo el motor.

## 6. Próximos análisis

La Entrega 4 queda pendiente. Se propone estudiar exploratoriamente la sensibilidad económica del horizonte y del filtro de basis, manteniendo comparabilidad y registrando supuestos. Deberá considerar escasez de operaciones, concentración temporal, incertidumbre de ejecución y proxies. Este paquete conserva parámetros y no selecciona variantes por mayor retorno.

Todas las cifras remiten a [fuentes_de_cifras.csv](fuentes_de_cifras.csv); las definiciones y unidades están en [diccionario_campos.csv](diccionario_campos.csv).

# Cobertura ejecutada y pendiente

Se reconstruyeron por posprocesamiento las dos BASE y las dos MARGEN_2X en toda la muestra. La auditoría de cuentas y precios no encontró un registro indispensable faltante que justificara replay. Los cierres concilian y se conservaron las doce carteras originales, sus parámetros y las hipótesis publicadas.

| Tema | Estado y consecuencia |
| --- | --- |
| Precio spot contemporáneo durante la suspensión de marzo de 2023 | No observado: 72 velas de volumen cero y 80 registros ausentes. La valoración principal arrastra el último precio según la corrida; el proxy causal es hipotético y no habilita una venta. La conciliación no resuelve esa incertidumbre de mercado. |
| Marks de riesgo aproximados | Se conservan las 15 excepciones `futures_scaled` documentadas (BTC: 2; ETH: 13), identificadas por observación y origen. No se completa una cronología de reglas históricas. |
| Settlement marks de funding | Se conserva el tratamiento original `previous_closed_1m` para 2.005 observaciones por activo. Es una excepción distinta de los 15 marks de riesgo. No se cobra nuevamente el funding al valorar. |
| Fondos netos con órdenes pendientes | La reserva exacta no siempre puede derivarse de un precio persistido. La disponibilidad y el faltante externo exactos se declaran ND con motivo y cotas conservadoras. El déficit de mantenimiento observado es cero; las cotas preventivas no son aportes realizados. |
| Trayectoria intravela o ticks | Fuera de la evidencia disponible y del alcance. La serie usa cierres de minuto más eventos, sin combinar extremos spot/mark de una vela como si fueran simultáneos. |
| Verificación sin datos locales masivos | El paquete compacto conserva evidencia exportada y sus hashes. Para recomputar el máximo global hacen falta la serie completa, precios locales y estados de las corridas, suministrados explícitamente. |
| Escenario sin interrupción | Pendiente de nueva trayectoria: el proxy con posiciones y decisiones originales no sustituye ese compromiso previo. |
| Demoras de cierre y movimientos adversos | Tanda pequeña propuesta y calibración descriptiva entregadas en el reporte; simulaciones no ejecutadas. Se necesitan reglas de ejecución, controles y comparadores definidos antes de correr nuevas trayectorias. No hay probabilidades estimadas. |
| Alternativa remunerada de todo el capital | Pendiente. Requiere moneda, fuentes históricas, disponibilidad, costos, riesgos y reinversión definidos antes de elegir tasa o producto. |
| Remuneración sólo del efectivo libre | Pendiente y distinta del benchmark de todo el capital. Debe respetar compromisos y garantías; no se sumaron intereses al P&L base ni se modificó el Sharpe de H2. |
| PDF de la Entrega 3 presentada | No localizado entre los archivos disponibles del repositorio. Se utilizaron paquetes, metodología y código congelado; no se afirma haber leído ese PDF. |

El feedback literal recibido se conserva en `documentos/feedback_e3.md`. La matriz de cobertura identifica por separado las palabras del profesor, requisitos del encargo, compromisos previos y decisiones metodológicas. Este trabajo resuelve el bloque observado de riesgo y garantías; no declara completa toda la Entrega 4.

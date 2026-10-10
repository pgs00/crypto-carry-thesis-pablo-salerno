# Metodología de auditoría del basis

La auditoría contrasta el escenario histórico `vwap_joint` en las ventanas UTC
`[2022-09-01, 2023-09-01)` y `[2025-09-01, 2026-09-01)`, para BTCUSDT y ETHUSDT
spot frente a sus perpetuos lineales USD-M. No representa el período continuo
de la BASE vigente. Los [resultados y fuentes](../data/research/basis-audit-20260919/README.md)
identifican las corridas, la cobertura y sus límites.

El auditor separado lee las columnas originales de las velas de un minuto y
calcula `basis_raw = F / S - 1` con Decimal de 60 cifras. Compara por etapas
fuente original, precio normalizado, precio de señal y basis persistido.
Los cierres spot y perpetuo pertenecen al mismo intervalo ya disponible al
decidir. No incorporan slippage, comisiones, anualización ni el VWAP posterior
de ejecución. El signo del funding no determina el signo del basis.

Se normalizan a UTC los timestamps en milisegundos y microsegundos; se
distinguen apertura, cierre, fin exclusivo del minuto y disponibilidad.
Los controles rechazan duplicados, desalineación, precios futuros y fuentes
faltantes. La tolerancia numérica es `1e-12` en unidades decimales de basis;
todo cambio de clasificación se informa aunque sea menor que esa tolerancia.
Los umbrales operativos permanecen en `[0, 0.005]`, con ambos extremos incluidos.

Cada observación de mercado aparece una sola vez, separada de las decisiones
de ambas estrategias. La muestra determinista contiene 20 observaciones por
activo y ventana, 80 en total, con fechas distribuidas, extremos y proximidad
a cero. Los archivos conservan precios, timestamps, fuentes, diferencias,
clasificación y causas de discrepancia. La condición de funding de la cartera
permanente es diagnóstica y no integra sus rechazos operativos.

Los casos manuales de referencia son `S=100` con `F=99.95`, `100`, `100.5` y
`100.51`: basis `-0.0005`, `0`, `0.005` y `0.0051`, respectivamente. Sólo los
dos casos centrales son elegibles. Cero también integra el conteo elegible;
esas categorías no se suman como excluyentes.

La cobertura se refiere a instantes de evaluación, no a todos los minutos.
Validar el basis no demuestra rentabilidad ni corrección de todo el backtest.
La reproducción requiere las fuentes locales autenticadas y no modifica
parámetros económicos ni vuelve a simular las carteras.

# Control de identidad exacta: intento técnico inicial

El coordinador se detuvo el 01/10/2026 a las 00:37 UTC, después de los cuatro
controles técnicos y antes de cualquier SH_P90, SH_MAX o CF. No se interpretan
escenarios a partir de ese intento y no se reemplaza ninguna referencia BASE.

La comparación ordenada detectó únicamente dos celdas por estrategia en
`equity_daily.csv`, campo `BTCUSDT_spot_price`. El precio 68246.01000000 quedó
escrito como 68246.01000000000000000000000, y 104375.24000000 como
104375.2400000000000000000000. Las cuatro diferencias numéricas son cero.
Los otros diez artefactos de cada estrategia coinciden exactamente, incluidos
órdenes, fills, ledger, posiciones, funding, señales y oportunidad.

Evidencia: `discrepancia_CONTROL_CERO_20261001T003732.json` y
`diagnostico_discrepancia_cero_01.json`. No se relajó el comparador ni se
normalizaron los CSV para hacerlos pasar.

La causa es la multiplicación de una referencia spot antigua por un Decimal
igual a uno que conserva decimales de la fórmula de recuperación. La corrección
conserva directamente el MinuteBar original cuando el factor es uno. Mantiene
valor, fuente, disponibilidad y representación exacta. Con factor distinto de
uno, la fórmula permanece igual. El test rojo reproduce el caso durante una
suspensión; las treinta pruebas focalizadas posteriores pasan.

Se conserva el contrato inicial, su snapshot de código, las cuatro corridas y
sus logs. La nueva congelación identifica el cambio y vuelve a ejecutar los
cuatro controles: ninguna corrida de código anterior se presenta como control
del código nuevo. Sólo hay cuatro controles aceptados en la matriz final;
los cuatro intentos iniciales se contabilizan adicionalmente como historial
técnico, con sus resultados de compatibilidad y conciliación separados.

La revisión independiente de esta corrección no encontró hallazgos abiertos.
Los nombres de los nuevos informes de compatibilidad incorporan la identidad
de código para no sobrescribir el informe del primer intento. Esta modificación
administrativa no cambia las proyecciones comparadas ni las reglas del replay.

Magnitudes, calendario, recuperación de 60 minutos, anclas, volumen, parámetros,
muestra, referencias y aprobación permanecen idénticos. No se compararon
resultados económicos para elegir supuestos. No se borra ni mueve evidencia.

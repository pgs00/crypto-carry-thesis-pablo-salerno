# Protocolo previo del bloque 4

Se ejecutan doce
trayectorias continuas y se reutilizan dos BASE autenticadas. No se combinan
familias ni se elige una política ganadora.

| Escenario | Precio | Demora adicional s | Propósitos |
|---|---|---:|---|
| E_OHLC4 | OHLC4 | 0 | Ninguno demorado; incluye precio de liquidate |
| L01 | VWAP | 60 | Todos los del cliente |
| L05 | VWAP | 300 | Todos los del cliente |
| LC01 | VWAP | 60 | close_perp, close_spot |
| LC05 | VWAP | 300 | close_perp, close_spot |
| LC15 | VWAP | 900 | close_perp, close_spot |

Las configuraciones se derivan de las efectivas de run_ad71d751b20623006c195ff3
y run_dfea4b7ac1475668d5968c97. El costo de decisión conserva su modo BASE.
Muestra UTC [2022-01-01,2026-09-01), 10000 USDT, sin reinicios anuales.
`liquidate` tiene demora adicional cero; su spot posterior recibe la demora
que corresponda a `close_spot`. LC es una regla causal sobre todos los cierres
de cada trayectoria: no es la antigua selección retrospectiva por incidentes.

Se conserva submitted_at; eligible_at = submitted_at + delay_applied; ventana
única minute_window(eligible_at), con vencimiento y registro en su final. La
segunda pata y cada reintento tienen su propio envío. No se trasladan holding,
correction_deadline, cooldown ni riesgo. Funding se liquida antes del fill
simultáneo. Cancelación en el inicio exacto conserva la política BASE (inmediata);
estrictamente dentro de la ventana conserva el diferimiento original.

OHLC4 sólo cambia el precio de ejecución de la vela elegible ya cerrada. Sizing,
señales, marks y funding conservan sus referencias causales. Se exportan OHLC,
VWAP, volumen y precio utilizado, sin reescribir datos. Sin volumen/actividad
no hay fill. Una ausencia no explicada detiene la trayectoria.

Etapas: A autenticación, fixtures y compatibilidad; B OHLC4; C L01/L05;
D LC01/LC05/LC15; E consolidación, copia offline, preservación y matriz.
Primer replay secuencial; sólo después de medir recursos se permite hasta dos.
Las puertas exigen identidad, conciliación Decimal 1E-8 y auditoría de ejecución.

Los ocho períodos heredan saldos de cada trayectoria completa. Exposición sin
polvo y unión BTC/ETH usan los clasificadores corregidos. Drawdown principal
diario. H1 y oportunidad H3 se comprueban separadamente y se reutilizan cuando
hay cobertura; H2/H3 financieros se recalculan por escenario.

Incidentes: catálogo completo y cinco de mayor duración por cartera, desempate
inicio y activo; además 24/03/2023 cuando exista exposición. Valoración y margen
sólo en esas ventanas, frecuencia y cobertura explícitas, sin máximo intradía
global. Precios arrastrados o estimados conservan sus límites de ejecución.

Sin SOFR nuevo, shocks, contrafactual sin suspensión, Word/PDF, commit, push,
alteraciones del índice del usuario ni modificaciones de sellos previos.

Constructor y verificador podrán compartir helpers: se declara esa dependencia
y se agregan pruebas de adulteración con hashes renovados. El paquete compacto
contiene las fuentes necesarias para sus controles; controles masivos requieren
la ruta de datos explícita. Logs de verificación siempre fuera de entradas.

# Interfaz y validadores de la ejecución aprobada

`ScenarioBacktest` deriva del `GapAuditedBacktest` corregido. No se modifican
`strategy.py`, `execution.py`, `models.py`, `data/replay.py`, `data/validate.py`,
el calendario original ni el RuleBook. La configuración económica de cada
estrategia se carga desde su efectiva original autenticada. La especificación
externa y sus hashes distinguen los escenarios sin introducir defaults nuevos.

| Entrada o control | Tratamiento de la capa |
| --- | --- |
| Particiones, manifiesto semántico y reglas originales | Se recomputan las 1.731 identidades; la lectura original conserva cobertura, marcas y orden temporal. |
| SOFR, futuros, marks y funding | No se transforman. SOFR tampoco ingresa al carry. |
| Vela spot de shock | Mismos timestamps, volumen base y operaciones. OHLC y volumen cotizado multiplicados una vez por la envolvente aprobada. |
| Spot sin actividad o ausente en suspensión | No se crea evento ni volumen. La referencia de valoración usa el último cierre original positivo y el factor del último minuto terminado, conservando su disponibilidad antigua. |
| Frescura/señal | El motor sigue leyendo `closed_bars`. La actualización contable de una referencia antigua no crea una vela ni cambia sus timestamps. |
| Vela CF | Se reemplaza exactamente una clave spot al publicarse su minuto. OHLC/VWAP se derivan del futuro contemporáneo; volumen y operaciones vienen de la tabla aprobada. |
| Fuente futura ausente en CF | Falla explícita antes de consumir la vela hipotética, incluso dentro de la suspensión original. |
| Ancla CF | Se verifica al llegar la última vela completa anterior. No se usa la parcial ni la reapertura para ajustarla. |
| Calendario de cobertura | La excepción CF consiste en proporcionar únicamente las 306 claves aprobadas, no en borrar cierres globalmente. Fuera de ellas actúan los mismos validadores. |
| Ejecución | Mismo minuto comprometido, capacidad bruta compartida, secuencia de patas, ticks, fees, slippage, expiraciones y prioridad de liquidación. |
| Riesgo/finanzas | Funding precede fills simultáneos. El observador guarda cantidades, reservas y márgenes antes y después de fills; no mueve dinero ni decide órdenes. |
| H3 | Se recalcula en cada minuto del replay desde barras transformadas. Se guarda además un testigo detallado en ventanas y bordes, sin depender de posiciones. |
| Checkpoint | Especificación, factores, referencia original, ancla, observaciones y órdenes se serializan con el mecanismo existente; no hay RNG. |

Las fuentes intervenidas deben cumplir disponibilidad al cierre, OHLC positivo
y coherente, volumen/actividad consistentes y VWAP dentro del rango. Sólo los
productos/divisiones derivados admiten dos unidades del último decimal del
contexto original, para reconocer el redondeo aritmético; no se recortan datos.

La evidencia de ventanas distingue cuatro fases: estado anterior al nuevo
evento; datos nuevos y funding aplicados, antes de fills; después de fills;
y estado final después de riesgo/decisiones. Un margen que deja de existir
tras cerrar el corto se conserva como `null`, no como un requerimiento vigente.
Una excepción al medirlo se informa como diagnóstico y no sustituye el halt
de cobertura del motor.

El diario conserva registros original/derivado, hashes de cada registro,
fuente, fórmula, unidad y disponibilidad. El extracto de fuentes añade ruta
y SHA-256 de partición. La reproducción económica completa sigue requiriendo
las entradas masivas identificadas; una verificación offline del paquete no
se describirá como otro backtest de cuatro años y ocho meses.

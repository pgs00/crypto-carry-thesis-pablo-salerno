# Entradas y compatibilidad verificadas

Etapa A; no replay económico nuevo. Inspección iniciada el 30/09/2026 UTC en
`C:/Users/pablo/Documentos/UCEMA/Tesina/Backtesting`, rama `codex/crypto-carry`,
HEAD `65ff8c412366817c68bdf1f37ca62a1cbfcfea6e`. Coincide con la referencia del
encargo; no se cambió de commit. Árbol e índice inicialmente limpios. No se
encontraron AGENTS.md en los ancestros ni en el árbol inspeccionado. Python
3.14.3 del entorno `.venv`, datos masivos `D:/Backtesting`.

## Referencias autenticadas

Se leyeron íntegramente el encargo B5 y el texto de la consigna académica
`C:/Users/pablo/Downloads/Entregables - Track Finanzas Computacionales(2).docx`.
Se conserva su extracción y hash, sin afirmar revisión de maquetación. Se
revisaron metodología, matriz e historial, feedback E3, protocolo/cobertura
del riesgo intradía, catálogo/calibración, corrección de exposición/H2, fichas
BASE y controles/aprobación/cambio/pruebas del bloque 4. No se localizó un
documento independiente denominado encargo general de Entrega 4 entre las
fuentes inspeccionadas; se usaron el encargo B5, matriz y documentos de bloques.
No se afirma haber leído un PDF E3 ausente.

Nueve manifiestos previos se verificaron contra **todos sus miembros**:
reglas históricas, corrección de exposición/H2, riesgo intradía, retorno/capital,
SOFR final, B2, B3 y ambas versiones B4. Cero diferencias. La lista exacta de
rutas, SHA-256 y conteos está en [sellos de entrada](controles/sellos_entrada.json).
No se duplicaron estos paquetes en el candidato. Las referencias a SOFR como
pendiente dentro de documentos antiguos no sustituyen su versión final en la
matriz vigente.

Las **1.731 identidades de entradas** del manifiesto BASE fueron recalculadas
contra datos locales. `processed_manifest_semantics` es un hash de una proyección
JSON, no el nombre de un archivo: se recomputó con la exclusión original de
`source_manifest_sha256`; también se guarda el hash de bytes del manifiesto.
Las demás identidades se contrastaron con sus archivos. Ver
[entradas masivas](controles/entradas_masivas.json). Se autentican datos;
esta comprobación no reconstruye una historia completa de reglas del exchange.

## Reparación, identidad y conciliación

| Cartera | BASE preservada | Control corregido separado |
| --- | --- | --- |
| Condicional | run_ad71d751b20623006c195ff3 | run_d7c7cb5da666e22321598598 |
| Permanente | run_dfea4b7ac1475668d5968c97 | run_415276e8a8b5bb9101e2d13b |

Se contrastaron el índice/estados B4, manifiestos, outputs y código con las
corridas originales locales. Todos los archivos de código declarados por los
controles coinciden con el código actual. No se encontró una revisión posterior
documentada que sustituyera esas identidades. Se comprobaron configuraciones
efectivas y orden persistido, no sólo equity final.

Precisión del índice: `indice_corridas.json` de B4 enumera 14 resultados
económicos y no incluye los dos controles. Estos están indexados separadamente
en `controles_base/CONTROL_BASE__conditional.json` y
`CONTROL_BASE__permanent.json`, tanto en la carpeta de trabajo como en v2,
y en `evidencia_control/` del sello. El
[índice de referencias de etapa A](indice_referencias.json) los identifica
con esa procedencia, sin agregarlos ficticiamente al índice sellado anterior.

Los once artefactos por cartera son equity_daily, positions, fills, orders,
risk_events, ledger, funding_payments, signals, renewal_diagnostics,
forecast_evaluation y opportunity_daily. Igualdad exacta de sus proyecciones
económicas, sin reordenar ni redondear; sólo se excluyen `run_id` y `units`,
como en el control publicado. Las 22 comparaciones coinciden con ese control.

Además se recalculó ledger/caja/inventarios de las cuatro corridas. Cada una
vincula sus 1.704 cierres: condicional 2.372 filas ledger/3.800 posiciones;
permanente 10.159/4.128. Se aplica la tolerancia original `1E-8` USDT. Ver
[compatibilidad](controles/compatibilidad_recalculada.json),
[conciliación](controles/conciliacion_referencias.json) e
[identidades](controles/identidades_corridas.json).

También se recalcularon por separado las ecuaciones de equity y P&L acumulado
en los **6.816 cierres** de las cuatro referencias, desde las cantidades,
precios, costos, cash y componentes diarios. Residuo máximo de equity `1E-23`
y de P&L `9.3E-24` USDT, debajo de `1E-8`; slippage no se descuenta de nuevo.
Ver [control diario](controles/conciliacion_equity_pnl_diaria.json).

La aprobación UTF-8 preservada del bloque 4 autoriza priorizar `liquidate`
después de un parcial escalado, manteniendo el fill comprometido anterior.
Se revisó la guardia en `_timeout`, las ramas que podían restaurar HOLDING y
el diff congelado. Se ejecutaron de nuevo las pruebas de parcial comprometido
(demoras 0 y 300), corrección parcial y reducción sin fill: **4 passed**.
Esto verifica el comportamiento reparado y no autoriza los escenarios B5.

La igualdad BASE **no resuelve el alcance sobre B2/B3**. La matriz conserva
ese pendiente por separado; no se infiere inocuidad de la ausencia de fills
etiquetados liquidación y no se repiten esas variantes aquí.

## Calibración y cobertura

La recalibración desde `episodios.parquet` y el catálogo publicado reprodujo
466 filas (233 episodios × dos valoraciones), incluidos ceros y límites del
intervalo activo. Sus cuatro resúmenes coinciden exactamente. El candidato
conserva copias pequeñas de las dos tablas publicadas, con sus bytes originales,
las diferencias del proxy y el calendario propuesto. No se reestimó una
población para aumentar intensidades.

La interrupción se cotejó con `market_calendar.py`, documentación histórica,
las dos fuentes Binance citadas en el protocolo y las particiones locales.
Por activo: 72 velas de volumen cero y 80 ausentes durante el cierre completo;
la vela parcial anterior existe y la reapertura 14:00 se publica 14:01.
Los fills BASE acreditan exposición de 12:00 a 14:01.
La calibración CF verifica 2.880 minutos previos por activo, sin ausencias;
153 velas de futuros positivas por activo durante la intervención propuesta.

## Incidencias técnicas de la preparación

El primer auxiliar trató `processed_manifest_semantics` como ruta y se detuvo.
Se conservó su log, se rastreó `data/replay.py:input_hashes` y se corrigió sólo
el auxiliar. Los controles de sellos/BASE ya terminados se conservaron;
el reintento de entradas autenticó las 1.731 identidades. Una extracción
exploratoria de fills repitió el argumento `run_id`; se corrigió el diccionario
y se conservó el extracto final. Ningún fallo modificó las corridas.

La inspección inicial de volumen a 28 días se sustituyó antes de simular por
48 horas posteriores a la promoción BTC, por la discontinuidad de régimen.
El motivo y hashes de esa revisión descriptiva están en
[revisión de ventana](controles/revision_ventana_volumen.json). Ruff detectó
un import no utilizado en el auxiliar de inventario; se retiró y volvió a pasar.
Un comando extenso de guardado fue rechazado por la herramienta antes de
ejecutarse; se completó mediante escrituras acotadas y copia explícita de las
ocho cachés, sin borrar ni mover fuentes.

La [verificación final de etapa A](controles/verificacion_final_etapa_a.json)
documenta integridad, enlaces, tablas, comandos, preservación e índice.

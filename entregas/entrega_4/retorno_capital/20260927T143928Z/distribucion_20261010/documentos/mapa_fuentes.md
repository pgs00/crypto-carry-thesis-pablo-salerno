# Mapa de fuentes y decisiones metodológicas

Las rutas base se proporcionan explícitamente. `../fuentes.json` fija cada
archivo utilizado, bytes y SHA-256; `inventario_fuentes.csv` lo presenta como
tabla. `esquemas_fuentes.json` contiene filas, campos y tipos de los Parquet.
Los originales siguen en sus paquetes: no se copiaron las carteras completas.

| Dependencia | Fuente concreta | Uso |
| --- | --- | --- |
| parent | `corridas/<run_id>/run_manifest.json`, índice y configuración efectiva | Identidad original, parámetros exactos y contrato de la corrida |
| parent | `ledger.parquet` | Secuencia de movimientos, posiciones posteriores, efectivo, fees y funding |
| parent | `risk_events.parquet` | cycle_id, transición de entrada, apertura completa y primer cierre terminal; renovaciones no crean ciclo |
| parent | `orders.parquet`, `fills.parquet` | Órdenes enviadas, fills/parciales, propósito, order_id/fill_id/trade_id; ordinal original |
| parent | `positions.parquet`, `equity_daily.csv` | Control de estados y valoración de cierres originales |
| parent | `signals.parquet` | 10.224 evaluaciones `entry` por cartera, ancla, forecast/costo, estados de filtros, decisión registrada y precio causal en entrada |
| parent | `renewal_diagnostics.parquet` | 103/458 evaluaciones separadas con umbral cero; actual_outcome/decision ausentes no se inventan |
| correction | `comparacion/metricas_cartera_periodo.csv`, `diario_carteras.csv` | Finanzas, días, saldos heredados y capital utilizado sin recalcular trayectorias |
| correction | exposición, componentes, eventos, H1/H2/H3 e invariancias | Tiempo activo sin polvo y comparaciones conservadas |
| intraday | `evidencia/eventos_financieros.parquet` | Sólo precios en las fronteras de cierre de ciclos; estado original, sin proxy ni nueva serie intradía |
| e3 | `tablas/ciclos.csv` y código archivado de portfolio/ledger/strategy/diagnostics | Concordancia de identidad/semántica; inspección de sólo lectura del motor original |
| público | `../fuentes_publicas/` | SOFR y SGOV: documentos/datos originales, consultas, URL y hashes; únicamente propuesta |

Raíces originales:

- parent: `entregas/entrega_4/reglas_historicas/20260925T005436Z/`.
- correction: `entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/`.
- intraday: `entregas/entrega_4/riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z/`.
- e3: `Paquete de evidencia/`.

Se leyó `docs/methodology.md`, el feedback literal E3, reporte y cobertura
pendiente intradía, exposición/H2 vigentes y código actual y archivado pertinente.
La ausencia del PDF E3 no se reemplaza por una lectura supuesta.

## Convenciones de evidencia

`source_row` es ordinal físico de origen, base cero; no se renumera al filtrar
órdenes enviadas. Una evaluación se identifica por run/source/ordinal y conserva
activo, instante exacto, tipo y ancla. Se rechazan duplicados idénticos, no
empates legítimos de eventos distintos. En los archivos efectivos no hay
empates de activo/instante/tipo dentro de una cartera.

La clasificación conserva el orden de filtros declarado en cada registro.
Los 16 filtros de entrada incluyen posición, cooldown, pendientes, deuda,
cobertura, forecast, reglas, operatividad, mark, alineación, frescura, funding,
basis negativo, basis máximo, sizing y presupuesto. Renovación tiene cinco
filtros propios: holding, datos válidos, forecast, deuda y funding positivo.
`not_evaluable` no es cero ni fail. Un filtro no aplicado sigue visible.

Los enlaces temporales no se rotulan como causales. Una entrada se acredita
con evaluación aceptada + transición original + orden inicial única.
Los intentos fallidos conservan su order_id. Fills posteriores y acciones
autónomas sin evaluación del mismo instante conservan el enlace no reconciliado;
no se elimina esa población. Los conteos son de evaluaciones o acciones, nunca
porcentaje de tiempo elegible. Los archivos por período declaran sus denominadores.

En `fronteras_contables.csv`, cada estado contiene cantidades, costo heredado,
realizado y no realizado. Las variaciones fuera de ciclo se clasifican mediante
estado contable, no como diferencia libre para forzar una conciliación. El
100% del P&L queda atribuido a ciclo, polvo o estado plano explícitos, con
residuales comprobados a 1E-8. Un remanente nunca se vuelve a comprar por el
solo cambio de cycle_id. Los precios compactos usan su decimal representable
exportado y se cotejan contra cierres originales; no se eleva la tolerancia.

## Alcance de autenticación

La auditoría original aplicada al padre revisó 1.087 miembros, 12 corridas y
sus artefactos; ese chequeo de preservación no amplía los análisis económicos
de este bloque. La corrección verificó 96 filas financieras sin cambios, 48
evaluaciones H2 y 45.803 intervalos. E3 verificó 120 miembros. Intradía se
verificó en modalidad compacta: no se revalidaron máximos globales ni la serie
completa de precios por minuto. Los resultados y comandos actuales se guardan
en la carpeta externa de auditoría, sin alterar los sellos de las fuentes.

Los controles de publicación históricos tienen su alcance original. No se
modifican manifiestos para incluir código nuevo ni se afirma que un control
dependiente de un antiguo árbol Git certifique este nuevo paquete.

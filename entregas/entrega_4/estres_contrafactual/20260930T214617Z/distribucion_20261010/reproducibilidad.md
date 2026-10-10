# Reproducción y alcance de verificación del bloque 5

Esta carpeta es el único candidato editable durante el desarrollo. El estado
efectivo está en `indice_corridas.json` y `controles/postproceso_etapa_b.json`.
La aprobación económica y las nueve entradas aprobadas son inmutables desde
`aprobacion_recibida.json`; el motor y runner ejecutados se conservaron antes
de las corridas en el snapshot indicado por `code_snapshot` del contrato vigente
`protocolo_ejecucion.json`. `codigo_ejecutado/` y `protocolo_ejecucion_01.json`
preservan el primer intento técnico; `codigo_ejecutado_02/` identifica la
corrección de representación Decimal para factor uno. El historial está en
`intentos_tecnicos_previos.json` y `controles/incidente_control_cero.md`.

## Verificación compacta offline

La entrega final incluirá `herramientas/` con código de cálculo y verificación,
`pyproject.toml` y `uv.lock`. Requiere Python compatible con ese proyecto y sus
dependencias declaradas, incluidas PyArrow y NautilusTrader. No instala ni
descarga dependencias automáticamente. La prueba de portabilidad empleará
una copia real aislada y el entorno existente, con las versiones registradas.

Desde una copia de la entrega final:

```powershell
python -B herramientas/scripts/verify_stress_counterfactual.py . --output ../verificacion_bloque5.json
```

Antes del sello, la misma comprobación agrega `--unsealed`. `--partial` se usa
exclusivamente durante desarrollo: permite referencias/carteras terminadas,
pero no habilita declarar completa la matriz ni sellarla. Las auditorías del
paquete final se escriben fuera de su carpeta y no renuevan el manifiesto.

El verificador:

- Autentica la aprobación, sus archivos, el contrato congelado y las identidades
  de las BASE originales, referencias corregidas, controles y escenarios.
- Exige las rutas canónicas de la evidencia que realmente consume. Un escenario
  económico no puede etiquetarse como control para omitir su recomputación.
- Coteja los bytes exportados con los manifiestos originales. Descomprime
  `forecast_evaluation.csv.gz` en memoria y verifica el hash CSV original.
- Repite las once comparaciones económicas ordenadas por cada pareja de
  referencia/control, excluyendo sólo `run_id` y metadatos `units`.
- Recalcula balances, inventario, flujos, ocho períodos heredados, ejecución,
  cupos, fees, slippage y clasificaciones causales de órdenes/liquidaciones.
- Contrasta funding monetario contra cantidad anterior a fills simultáneos,
  tasa y mark de settlement consumidos; distingue fuentes invariantes de importes.
- Recompone por ecuaciones separadas los precios/volúmenes intervenidos y sus
  factores. Exige población, disponibilidad y originales correspondientes.
- Recalcula ventanas aprobadas y requiere todos sus cierres de minuto y testigos
  por activo. Rechaza omisiones aunque se actualicen contadores del journal.
- Recalcula atribución de valoración, garantías por fase y faltante simultáneo,
  cohortes H1, H2 y H3 diario desde agregados por activo. Los testigos H3 de las
  ventanas se comprueban también contra las barras fuente archivadas.
- Coteja tablas Parquet y CSV con esos cálculos, además del sello de bytes.

El constructor y el verificador **comparten lógica de reporte, ledger y
ejecución**. El auditor de fórmulas de intervención no llama a la transformación
usada por el replay. No se presenta este control como un segundo motor
económico independiente.

## Qué sólo se autentica en la entrega compacta

Los agregados minuto/día H3 fueron exportados por cada replay completo. Se
reagregan y cotejan diariamente; fuera de las ventanas con testigos no se
reconstruye toda la oportunidad minuto a minuto. Las barras originales
seleccionadas fueron extraídas tras recalcular los hashes de sus particiones.
La entrega compacta verifica sus identidades y ecuaciones, pero no demuestra
de nuevo pertenencia de cada fila a una partición masiva ausente. Los marks de
las observaciones de riesgo son evidencia persistida del replay autenticado;
no se presenta una segunda reconstrucción de toda la historia de marks.

La validez histórica de las fuentes, las reglas prescritas, los proxies y el
precio antiguo durante la suspensión conservan las limitaciones de BASE y del
protocolo. Un resultado matemáticamente conciliado no convierte supuestos en
datos oficiales.

## Repetición económica con datos masivos locales

El comando realmente empleado en el checkout es:

```powershell
.venv/Scripts/python.exe -B -u -X utf8 scripts/run_stress_counterfactual.py --candidate entregas/entrega_4/estres_contrafactual/20260930T214617Z/candidato --data-root D:/Backtesting --raw-root D:/Backtesting/outputs/estres_contrafactual/20260930T214617Z --all
```

El runner usa una secuencia serial cerrada: dos controles de capa apagada,
dos de shock cero, dos SH_P90, dos SH_MAX y dos CF_SIN_INTERRUPCION. No avanza
a economía sin los cuatro controles; revisa cada familia antes de la siguiente.
Reutiliza una corrida terminada sólo si coincide la identidad completa; una
corrida económica con otro código no se sustituye por igualdad de saldo.

El 01/10/2026 el usuario autorizó cambiar únicamente la coordinación para
aprovechar el hardware. La [coordinación histórica](protocolo_distribucion.md) usa
`coordinate_stress_counterfactual.py`, incluido en las herramientas, con
locks exclusivos por cartera y recursos medidos. Reutilizó los cuatro
controles aprobados y SH_P90 condicional; completó las otras cinco carteras
sin modificar el runner congelado ni el motor. La corrida SH_P90 permanente
que había quedado interrumpida, sin proceso activo ni checkpoint recuperable,
conserva su log y estado anterior. Las seis carteras completas tienen las
identidades del índice de corridas; los intentos incompletos no se cuentan
como resultados económicos adicionales.

El primer postproceso completo se detuvo al comparar filas de minutos
ausentes: su representación en memoria omitía columnas que Parquet guardaba
como nulas. La [corrección documentada](controles/incidente_postproceso_esquema_fuentes.json)
lee la representación persistida desde la primera llamada. Conserva
comparaciones exactas, `present=False`, precios nulos y hashes originales;
no requiere repetir el motor. Su prueba reprodujo el fallo antes del cambio
y luego pasaron 16 verificaciones focalizadas.

Reproducir desde cero requiere las 1.731 entradas de
`input_hashes_etapa_b.json`, las cuatro referencias autenticadas y las rutas
locales del índice. Se debe trabajar con las entradas aprobadas en una carpeta
editable exclusiva y una raíz de salidas nueva, nunca ejecutar un runner que
escriba estados dentro de la entrega sellada. La ausencia de datos masivos
no se oculta con sustituciones ni reconstrucciones inventadas.

## Preservación y alcance restante

No se borran, mueven ni archivan corridas o paquetes previos. No se realiza
commit, push ni cambio del índice Git. La propuesta de limpieza anterior no
es autorización de retiro. Bloque 6, revisión transversal y comprobación del
alcance de la reparación sobre variantes B2/B3 siguen pendientes y separados.

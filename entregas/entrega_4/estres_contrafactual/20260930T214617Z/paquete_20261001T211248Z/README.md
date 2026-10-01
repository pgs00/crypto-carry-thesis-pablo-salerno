# Bloque 5 — resultados y controles finales

Ambas familias fueron aprobadas expresamente; la respuesta está en
[aprobacion_recibida.json](aprobacion_recibida.json). Este es el único candidato
editable de origen; su copia de entrega se identifica mediante el manifiesto
final cuando está presente. Los controles se completaron antes de los
escenarios. La continuación posterior usó la coordinación concurrente
autorizada, conservando cada cartera íntegra en un proceso independiente.

El primer control de shock cero detectó una diferencia sólo de representación
Decimal en cuatro celdas. El [incidente y su corrección](controles/incidente_control_cero.md)
quedan registrados. Los cuatro controles pasaron bajo la identidad corregida,
con 44 comparaciones exactas: [puerta de controles](controles/puerta_controles_continuos_02.json).
Las seis carteras económicas y el postproceso terminaron. El estado de las
verificaciones y del cierre está en el [registro local](progreso_local.json).
La verificación portable pasó, con 14 corridas autenticadas, 66 cotejos exactos
y 48 tablas recalculadas. Las diez adulteraciones reales fueron rechazadas
por el verificador incluido. La revisión de contenido y las cuatro figuras
también pasaron. El cierre final queda autenticado por el manifiesto del
paquete y su comprobación externa.

El primer constructor de resultados detectó una diferencia de esquema entre
filas ausentes en memoria y sus columnas nulas persistidas en Parquet. Se
uniformó la lectura persistida, conservando comparaciones estrictas y los
extractos originales. [Causa, prueba y corrección](controles/incidente_postproceso_esquema_fuentes.json).
No fue necesario repetir ninguna de las seis carteras.

- [Seguimiento de ejecución y pruebas](seguimiento_etapa_b.md).
- [Reporte de resultados](reporte.md) y [versión HTML](reporte.html).
- [Índice de resultados incorporados](indice_corridas.json).
- [Contrato económico congelado](protocolo_ejecucion.json).
- [Alcance y comandos de reproducción](reproducibilidad.md).
- [Verificación portable](controles/qa_final/verificacion_portable.json) y
  [diez adulteraciones](controles/qa_final/pruebas_negativas.json).
- [Revisión final de contenido](controles/revision_final_contenido.json) y
  [figuras](controles/revision_visual_figuras.json).
- [Puerta de sellado y alcance de las comprobaciones](controles/puerta_sellado_final.json).

La ficha y el protocolo de etapa A conservan su redacción histórica pendiente;
su aprobación posterior no modifica esos bytes. Las siguientes comprobaciones
describen esa etapa preparatoria, anterior a los nuevos replays.

- [Ficha de decisión y aprobación por familia](ficha_decision.md).
- [Entradas, compatibilidad y controles realizados](entradas_compatibilidad.md).
- [Fórmulas y límites del protocolo](protocolo_tecnico.md).
- [Plan y presupuesto de ejecución posterior](plan_ejecucion.md).
- [Inventario de limpieza independiente, copia exacta de etapa A](fuentes/inventario_limpieza_etapa_a.md).
- [Identidad de la propuesta pendiente](identidad_propuesta.json).

Se verificaron nueve sellos previos y 1.731 identidades de entrada. Las dos
BASE corregidas igualan las once proyecciones económicas ordenadas de cada
original; las cuatro corridas concilian. La calibración original y proxy se
reprodujo exactamente desde la evidencia publicada. Se midieron las entradas
de la ventana contrafactual, sin simular carteras ni elegir por resultados.

La aprobación mantiene dos niveles spot y un contrafactual, todos con mercado
común para condicional/permanente. No se extiende a limpieza, B6, otros
capitales, caja remunerada o variantes previas.

## Reproducir los controles de etapa A

Desde la raíz del checkout, con Python y dependencias de `pyproject.toml` y
`uv.lock`, `-B` evita cachés en las fuentes. Estos comandos son descriptivos
y de autenticación: no ejecutan el motor.

```powershell
$out = 'C:/ruta/externa/nueva/etapa_a'
$tool = 'entregas/entrega_4/estres_contrafactual/20260930T214617Z/candidato/herramientas/auditar_etapa_a.py'
.venv/Scripts/python.exe -B -X utf8 $tool inputs --root . --data-root D:/Backtesting --out $out
.venv/Scripts/python.exe -B -X utf8 $tool calibration --root . --out $out --temp C:/ruta/externa/exclusiva/calibracion
.venv/Scripts/python.exe -B -X utf8 $tool market --root . --data-root D:/Backtesting --out $out
```

La autenticación masiva requiere `D:/Backtesting`; la recalibración usa sólo
el paquete compacto de riesgo y sus helpers del repositorio. El auxiliar
comparte lógica publicada para la máscara/calibración y la comparación BASE;
no se presenta como motor estadístico independiente. El inventario usa blobs
Git y consulta de referencia remota; sus respaldos/copia aislada son controles
de limpieza, no una migración ni una publicación de este candidato.

La verificación B4 aislada utilizó sus herramientas incluidas, desde otra ruta,
sin argumentos de datos masivos y sin HEAD/índice original en esa copia.
Esta etapa A **no se declara paquete autónomo offline**: sus dependencias
están identificadas por ruta/hash y se reutilizan, sin duplicarlas. La entrega
de etapa B acredita su propio alcance portable mediante las herramientas
incluidas y los controles finales enlazados arriba.

El estado histórico de etapa A está en su
[verificación final](controles/verificacion_final_etapa_a.json). La preservación
posterior a los replays consta en los controles de archivos versionados,
referencias y puerta de sellado. No hubo commit, push, cambio de índice,
borrado ni movimiento de archivos anteriores.

# Bloque 5 — etapa A preparada

**protocolo_preparado_pendiente_aprobacion**. Único candidato de presentación,
no sellado. No hay resultados de shocks ni de escenario sin interrupción.

- [Ficha de decisión y aprobación por familia](ficha_decision.md).
- [Entradas, compatibilidad y controles realizados](entradas_compatibilidad.md).
- [Fórmulas y límites del protocolo](protocolo_tecnico.md).
- [Plan y presupuesto de ejecución posterior](plan_ejecucion.md).
- [Inventario de limpieza independiente](../../../../../docs/entrega_4/inventario_limpieza_bloque5_20260930.md).
- [Identidad de la propuesta pendiente](identidad_propuesta.json).

Se verificaron nueve sellos previos y 1.731 identidades de entrada. Las dos
BASE corregidas igualan las once proyecciones económicas ordenadas de cada
original; las cuatro corridas concilian. La calibración original y proxy se
reprodujo exactamente desde la evidencia publicada. Se midieron las entradas
de la ventana contrafactual, sin simular carteras ni elegir por resultados.

La propuesta mantiene dos niveles spot y un contrafactual, todos con mercado
común para condicional/permanente. Una familia aprobada podrá avanzar mientras
la otra siga pendiente. No se extiende la aprobación a limpieza, B6, otros
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
final de etapa B deberá demostrar su propio alcance portable.

El estado del trabajo y del índice del usuario está en
[verificación final](controles/verificacion_final_etapa_a.json). No hubo commit,
push, cambio de índice, borrado ni movimiento de archivos anteriores.

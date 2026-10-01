# Continuación local del bloque 5: registro histórico del lanzamiento

Este documento conserva la situación y las estimaciones del lanzamiento de
las 14:08 UTC. No indica procesos activos actuales. Las seis carteras ya
terminaron; el estado vigente está en [progreso_local.json](progreso_local.json)
y los resultados en [reporte.md](reporte.md). La continuación de las 15:00 UTC
reutilizó las diez corridas completas y resolvió el incidente del constructor
sin repetirlas; sus controles y cierre constan en el registro vigente.

Adaptación del 01/10/2026, iniciada a las 14:01 UTC y lanzada a las 14:08 UTC.
No cambia el código económico, las entradas aprobadas ni sus identidades.
El runner congelado sigue ejecutando cada cartera completa; el auxiliar sólo
coordina procesos y sustituye su lock global por un lock exclusivo por cartera.

El coordinador local **PID 22752** (lanzador 29116) inició entonces las tareas.
El estado vigente, los PID de trabajadores, tiempos, memoria, errores y rutas
de logs están en [progreso_local.json](progreso_local.json). Sólo el coordinador
actualiza ese archivo y el índice de versiones. El bloqueo de proceso está
fuera del candidato; un segundo coordinador no puede adquirirlo.

Se autenticaron y reutilizaron cuatro controles y SH_P90 condicional. El
coordinador anterior ya no existía. Su SH_P90 permanente quedó interrumpido,
sin salida final ni checkpoint recuperable: se conserva ese intento y se
ejecuta uno nuevo. No se repite ninguna cartera terminada y verificada.

Hardware detectado: Ryzen 7 5800H, 8 núcleos físicos / 16 lógicos, 27,86 GiB
visibles para Windows. La RAM libre medida durante la preparación varió entre
15,7 y 17,4 GiB. Se iniciaron **dos trabajadores totales**, con objetivo cuatro
y máximo seis sólo si las mediciones lo permiten. Se reservan 6 GiB más el
crecimiento pendiente hasta 4 GiB por proceso. Los picos observados de las
cinco carteras completas fueron 2,82–3,23 GiB; el presupuesto no es un límite
duro del sistema operativo. Si empeora el avance agregado, se reducen futuros
lanzamientos; no se mata un trabajador activo. Cada nuevo proceso establece
OMP_NUM_THREADS, OPENBLAS_NUM_THREADS, MKL_NUM_THREADS y NUMEXPR_NUM_THREADS
en 1 antes de importar las bibliotecas. El entorno efectivo queda archivado.

El comando externo reproducible, desde PowerShell en la raíz del checkout, es:

```powershell
Set-Location 'C:\Users\pablo\Documentos\UCEMA\Tesina\Backtesting'
& .\.venv\Scripts\python.exe -B -u -X utf8 scripts/coordinate_stress_counterfactual.py --candidate entregas/entrega_4/estres_contrafactual/20260930T214617Z/candidato --data-root D:/Backtesting --raw-root D:/Backtesting/outputs/estres_contrafactual/20260930T214617Z
```

**El lanzamiento original fue un proceso local independiente.** Este comando
se conserva para reproducción; no hace falta repetirlo. Un lanzamiento
duplicado se rechaza; si encuentra otros
trabajadores sobrevivientes los conserva y no los duplica. Una vez terminados,
una continuación reutiliza sus salidas verificadas.

Sin llamadas al modelo, el proceso encadena los scripts existentes:
`build_stress_counterfactual.py`, `render_stress_counterfactual.py`,
`package_stress_counterfactual.py --snapshot` y
`tamper_stress_counterfactual.py`. Este último realiza la verificación integral
portable y los diez casos negativos en una única copia aislada. Las mutaciones
son seriales porque comparten esa copia; no se duplican paquetes para acelerar
artificialmente la verificación. No se repite la regresión completa por este
cambio de coordinación ni por texto.

Una etapa fallida detiene los pasos dependientes y conserva su error y logs.
Si todas pasan, el estado final del comando será
`verificado_pendiente_revision_final_y_sello`: aún requiere la revisión del
reporte y figuras reales, preservación final y la puerta de sellado existente.
No inventa esa revisión ni sella sin ella. El coordinador no solicita ni usa
un modelo para hacerla. El bloque no se declara terminado por lanzar procesos.

Tiempos reales ya observados: SH_P90 condicional 10,68 minutos; controles
completos 9,83–27,29 minutos por cartera, con cargas simultáneas distintas.
Para las cinco carteras pendientes, una planificación prudente con dos
trabajadores es 30–60 minutos de cálculo. La verificación integral de las seis
carteras todavía no está medida: reservar 20–40 minutos es una estimación,
no una medición. La revisión final del reporte y sellado requiere otros
10–15 minutos. Por ello **60 minutos totales no están acreditados** al lanzar.
Los tiempos efectivos de cada etapa quedan registrados en el progreso local.

No se realizó limpieza, commit, push ni modificación del índice Git. Se
conservó un único candidato editable. Este registro precede al cierre final.

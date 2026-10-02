# Entrega 4: índice vigente y reproducción

Índice único al **02/10/2026**. Los paquetes vigentes son los identificados en
la [matriz de avance](../../docs/entrega_4/matriz_avance.csv). El
[cierre técnico local](../../docs/entrega_4/cierre_publicacion_20261002/README.md)
conserva los controles actuales y el estado Git comprobado. Este cierre de
navegación y reproducibilidad no ejecuta carteras ni produce resultados nuevos.

La lectura conjunta está en la [síntesis integrable B6][b6-sintesis]. Conserva
H1 por horizonte y activo, H2 por escenario/período con ND y excepciones,
y H3 con sus regímenes originales. BASE total mantiene H2 `no_favorable` y
dirección descriptiva H3 `contraria`; esas etiquetas no se extienden a todos
los años o variantes. Las cuentas nuevas B6 no son cortes heredados de BASE.

## Paquetes vigentes

Cada fila enlaza el reporte, las tablas, el protocolo y la herramienta incluida
en su paquete. «Vigente» identifica la versión de lectura y comprobación;
no afirma una validación independiente de todo el motor ni una publicación nueva.

| Bloque y versión vigente | Reporte / tablas | Protocolo | Verificador y alcance | Límites de lectura |
|---|---|---|---|---|
| BASE y reglas: padre `20260925T005436Z` + corrección `20260926T204312Z` | [Reporte corregido][base-reporte] · [Tablas][base-tablas] | [Reglas][base-protocolo] · [Métricas corregidas][base-metricas] | [V2][base-verificador], requiere el padre completo | [Guía][base-guia]: reglas prescritas; no cronología certificada del exchange. |
| Riesgo intradía: `20260926T220400Z` | [Reporte][riesgo-reporte] · [Tablas][riesgo-tablas] | [Protocolo][riesgo-protocolo] | [Verificador][riesgo-verificador], compacto o completo con series/precios locales | [Límites][riesgo-guia]: BASE/MARGEN_2X; el compacto no reconstruye máximos globales. |
| B1 capital: `20260927T152732Z` | [Reporte][capital-reporte] · [Tablas][capital-tablas] | [Protocolo][capital-protocolo] | [Verificador][capital-verificador], compacto o con cuatro dependencias | [Guía][capital-guia]: concentración descriptiva; la ficha SOFR pendiente es histórica. |
| B1 SOFR aprobado: `20260927T162350Z` | [Reporte][sofr-reporte] · [Tablas][sofr-tablas] | [Protocolo][sofr-protocolo] · [Aprobación][sofr-aprobacion] | [Verificador][sofr-verificador], cuenta y dependencia B1 capital | [Límites][sofr-limites]: hipotética bruta USD, ACT/360, paridad nominal; no caja carry. |
| B2 señal/entradas: `20260927T185305Z` | [Reporte][b2-reporte] · [Tablas][b2-tablas] | [Protocolo][b2-protocolo] | [Verificador][b2-verificador], evidencia compacta | [Guía][b2-guia]: seis variantes aisladas; MAE comparable sólo dentro del mismo horizonte. |
| B3 costos/capacidad: `20260927T231610Z` | [Reporte][b3-reporte] · [Tablas][b3-tablas] | [Protocolo][b3-protocolo] | [Verificador][b3-verificador], contabilidad y ventanas incluidas | [Guía][b3-guia]: ocho variantes aisladas, selección a 34 pb; capacidad 1m sin impacto/cola. |
| B4 ejecución/demoras: `20260930T013915Z_v2` | [Reporte][b4-reporte] · [Tablas][b4-tablas] | [Protocolo][b4-protocolo] | [Verificador][b4-verificador], versión con prioridad de liquidación corregida | [Revisión v2][b4-limites]: seis variantes aisladas; LC global causal y ventanas intradía acotadas. |
| B5 estrés/contrafactual: `20261001T211248Z` | [Reporte][b5-reporte] · [Resultados][b5-tablas] | [Contrato ejecutado][b5-protocolo] · [Fórmulas][b5-formulas] | [Verificador][b5-verificador], controles, escenarios y testigos exportados | [Alcance][b5-limites]: recuperación impuesta y anclas fijas; no causalidad histórica identificada. |
| B6 estabilidad/incertidumbre: `paquete_final_verificado` | [Reporte][b6-reporte] · [Tablas][b6-tablas] · [Síntesis][b6-sintesis] | [Ejecución][b6-protocolo] · [Bootstrap][b6-bootstrap] | [Verificador][b6-verificador], finanzas, estadística y síntesis compactas | [Guía][b6-guia]: inicios retrospectivos, intervalos marginales y supuestos por año. |

El [diagnóstico dirigido B2/B3][b6-diagnostico] excluye la precondición del
defecto de prioridad de liquidación en las 28 variantes autenticadas. Su
alcance se limita a esas corridas y esa rama; no prueba equivalencia universal
entre motores. La síntesis B6 autentica selectivamente las fuentes reutilizadas
y conserva el alcance de los controles históricos previos.

## Vigente, histórico y pendiente

Los reportes y README dentro de paquetes sellados conservan su fecha, sus
comandos originales y expresiones como «local», «sin push», «candidato» o
«pendiente». Son registros históricos. Por ejemplo, la ficha B1 anterior a
SOFR sigue pendiente en sus bytes; la aprobación posterior está en B1 SOFR.
B5 conserva pendientes B6/B2-B3 posteriormente resueltos. El cierre técnico
externo y la matriz dan el estado actual sin reescribir esos documentos.

Las carpetas `candidato`, intentos parciales, exportaciones anteriores y B4
anterior a `v2` se preservan como antecedentes; no sustituyen las versiones
de la tabla. El informe padre de reglas se lee con la corrección de exposición
y H2. [E3 continua](../entrega_3/continua/README.md) conserva la referencia BASE;
las [ventanas independientes E3](../entrega_3/archivo/README.md) son históricas.

Las reglas históricas incompletas siguen siendo una limitación. La
[segunda tanda propuesta](../../docs/entrega_4/reglas_historicas/decisiones_integracion.md#segunda-tanda-propuesta--no-ejecutada)
permanece sin ejecutar. Las sensibilidades retrospectivas no constituyen
evidencia fuera de muestra.

La revisión académica favorable ya recibida se conserva; la revisión técnica
local se documenta en el registro externo. Resta la actualización mínima de
referencias del documento y el cierre de publicación (commit, push y
verificación de descarga), fuera de este cierre local.
La remuneración/reinversión de caja libre o garantías del carry permanece
fuera del alcance autorizado. La aprobación del comparador SOFR no autoriza
esa modificación. El [registro del cierre](../../docs/entrega_4/cierre_publicacion_20261002/README.md)
separa la revisión técnica local de cualquier commit, push o entrega académica.

## Reproduccion en tres niveles

### 1. Lectura, sin ejecutar código

Abrir los reportes Markdown/HTML, tablas CSV y protocolos enlazados arriba.
No requiere Python ni datos de mercado. Los índices de corridas y manifiestos
identifican las fuentes; leerlos no equivale a volver a verificarlas.

### 2. Verificación offline de evidencia compacta

Los comandos siguientes usan los verificadores congelados de cada paquete.
Requieren **Python 3.14** y las dependencias de [pyproject.toml](../../pyproject.toml)
y [uv.lock](../../uv.lock); el entorno local comprobado usa Python 3.14.3.
Preparar el entorno desde la raíz del checkout, antes de la verificación:

```powershell
uv sync --frozen --python 3.14.3
```

La preparación puede necesitar acceso a paquetes si no están instalados o
en caché. Los verificadores posteriores no requieren red ni `D:/Backtesting`.
No ejecutar `uv sync` dentro de un paquete sellado. Sus copias de código/lock
fijan la procedencia; el entorno reutilizado queda fuera de las evidencias.

Desde la **raíz del repositorio**, parametrizar ubicación y salida. La matriz
resuelve las rutas vigentes; si se trasladan paquetes, reemplazar sus valores
en `$paquetes` y `$padre`. Elegir siempre una carpeta de auditoría nueva y
externa a todos los paquetes; los JSON/logs son los únicos productos esperados.

```powershell
$repo = (Resolve-Path .).Path
$py = Join-Path $repo '.venv/Scripts/python.exe'
$paquetes = @{}
Import-Csv (Join-Path $repo 'docs/entrega_4/matriz_avance.csv') | ForEach-Object {
    if ($_.paquete_vigente) { $paquetes[$_.id] = Join-Path $repo $_.paquete_vigente }
}
$padre = Join-Path $repo 'entregas/entrega_4/reglas_historicas/20260925T005436Z'
$salida = Join-Path $repo ('.superpowers/e4_offline_' + (Get-Date -Format 'yyyyMMddTHHmmss'))
if (Test-Path -LiteralPath $salida) { throw 'Elegir una salida nueva' }
New-Item -ItemType Directory -Path $salida | Out-Null
```

Ejecutar cada línea por separado y comprobar su código de salida y JSON.
Una ayuda `--help` satisfactoria sólo valida la interfaz; no acredita el pase
del paquete. Los resultados efectivamente ejecutados en este cierre están
en el [registro externo](../../docs/entrega_4/cierre_publicacion_20261002/README.md).

```powershell
& $py -B -X utf8 "$($paquetes.BASE)/herramientas/verify_rules_sensitivity_correction.py" --package $paquetes.BASE --parent $padre --output "$salida/base.json"
& $py -B -X utf8 "$($paquetes.RIESGO)/herramientas/scripts/verify_intraday_risk.py" --scope compact --package $paquetes.RIESGO --parent $padre --correction $paquetes.BASE --output "$salida/riesgo.json"
& $py -B -X utf8 "$($paquetes.B1_CAPITAL)/herramientas/scripts/verify_return_capital.py" --package $paquetes.B1_CAPITAL --output "$salida/b1_capital.json"
& $py -B -X utf8 "$($paquetes.B1_SOFR)/herramientas/scripts/verify_sofr_benchmark.py" --package $paquetes.B1_SOFR --previous $paquetes.B1_CAPITAL --output "$salida/b1_sofr.json"
& $py -B -X utf8 "$($paquetes.B2)/herramientas/scripts/verify_signal_sensitivity.py" --package $paquetes.B2 --output "$salida/b2.json"
& $py -B -X utf8 "$($paquetes.B3)/herramientas/scripts/verify_cost_capacity.py" --package $paquetes.B3 --output "$salida/b3.json"
& $py -B -X utf8 "$($paquetes.B4)/herramientas/scripts/verify_execution_delays.py" --package $paquetes.B4 --output "$salida/b4.json"
& $py -B -X utf8 "$($paquetes.B5)/herramientas/scripts/verify_stress_counterfactual.py" $paquetes.B5 --output "$salida/b5.json"
& $py -B -I -X utf8 "$($paquetes.B6)/herramientas/scripts/verify_stability_uncertainty.py" --candidate $paquetes.B6 --output "$salida/b6.json" --forbid-root 'D:/Backtesting'
```

BASE requiere su padre completo. Riesgo autentica los linajes suministrados,
pero el modo compacto no recalcula extremos globales ni precios por minuto.
B1 capital, sin dependencias adicionales, comprueba el paquete interno; su
[guía][capital-guia] documenta el modo con padre, corrección, riesgo y E3.
SOFR recalcula la cuenta hipotética y autentica B1 capital. B2–B5 recomputan
lo declarado en cada guía desde extractos y agregados; no vuelven a leer
toda la historia de mercado. B6 vuelve a calcular también las estadísticas
del bootstrap desde inputs compactos, sin simular carteras. Las herramientas
comparten partes del posprocesamiento; imágenes verificadas por hash y tablas
de origen no equivalen a una inspección visual nueva.

Los manifiestos comprueban bytes y pertenencia al inventario, no autenticidad
histórica del exchange. Los sellos y sus sidecars nunca se renuevan para
hacer pasar una divergencia. Los controles de integridad binaria Git/exportación
de este cierre están separados de los cálculos en el registro externo.

`scripts.verify_repository_evidence` corresponde a la limpieza histórica del
20/09/2026 y exige hashes antiguos del código económico. Su fallo actual por
fuentes evolucionadas está registrado en el cierre; no es un control universal
de E4. Los verificadores por paquete de arriba fijan su propio alcance.

### 3. Fuentes masivas y replay del motor, fuera de este cierre

Volver a autenticar mercados o reconstruir todo el riesgo intradía exige las
fuentes locales indicadas por sus manifiestos, normalmente `D:/Backtesting`.
Los parámetros `--data-root`, `--series-root` o riesgo `--scope complete`
amplían la verificación y no implican necesariamente un replay económico.
No se confunden con el nivel compacto ni se ejecutan en este cierre.

Repetir carteras requiere además el snapshot económico, configuraciones,
dependencias y contratos exactos de cada bloque, junto con destinos nuevos.
La [guía de reglas](../../docs/entrega_4/reglas_historicas/reproduccion.md),
la [reproducción B5][b5-limites] y los protocolos de la tabla conservan los
requisitos y comandos históricos. Los runners pueden escribir estados:
nunca deben apuntar al paquete sellado. Este índice no ordena una nueva
tanda ni convierte una comprobación offline en reproducción del motor.

[base-reporte]: reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/comparacion/reporte.md
[base-tablas]: reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/comparacion
[base-protocolo]: reglas_historicas/20260925T005436Z/documentos/protocolo.md
[base-metricas]: reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/documentos/guia_metricas.md
[base-verificador]: reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/herramientas/verify_rules_sensitivity_correction.py
[base-guia]: reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/README.md
[riesgo-reporte]: riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z/reporte.md
[riesgo-tablas]: riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z/tablas
[riesgo-protocolo]: riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z/documentos/protocolo.md
[riesgo-verificador]: riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z/herramientas/scripts/verify_intraday_risk.py
[riesgo-guia]: riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z/README.md
[capital-reporte]: retorno_capital/20260927T143928Z/paquete_20260927T152732Z/reporte.md
[capital-tablas]: retorno_capital/20260927T143928Z/paquete_20260927T152732Z/tablas
[capital-protocolo]: retorno_capital/20260927T143928Z/paquete_20260927T152732Z/documentos/protocolo.md
[capital-verificador]: retorno_capital/20260927T143928Z/paquete_20260927T152732Z/herramientas/scripts/verify_return_capital.py
[capital-guia]: retorno_capital/20260927T143928Z/paquete_20260927T152732Z/README.md
[sofr-reporte]: retorno_capital/20260927T154653Z_sofr/paquete_20260927T162350Z/reporte.md
[sofr-tablas]: retorno_capital/20260927T154653Z_sofr/paquete_20260927T162350Z/tablas
[sofr-protocolo]: retorno_capital/20260927T154653Z_sofr/paquete_20260927T162350Z/documentos/protocolo.md
[sofr-aprobacion]: retorno_capital/20260927T154653Z_sofr/paquete_20260927T162350Z/documentos/aprobacion.md
[sofr-verificador]: retorno_capital/20260927T154653Z_sofr/paquete_20260927T162350Z/herramientas/scripts/verify_sofr_benchmark.py
[sofr-limites]: retorno_capital/20260927T154653Z_sofr/paquete_20260927T162350Z/documentos/limites_verificacion.md
[b2-reporte]: senal_entradas/20260927T170230Z/paquete_20260927T185305Z/reporte.md
[b2-tablas]: senal_entradas/20260927T170230Z/paquete_20260927T185305Z/tablas
[b2-protocolo]: senal_entradas/20260927T170230Z/paquete_20260927T185305Z/documentos/protocolo.md
[b2-verificador]: senal_entradas/20260927T170230Z/paquete_20260927T185305Z/herramientas/scripts/verify_signal_sensitivity.py
[b2-guia]: senal_entradas/20260927T170230Z/paquete_20260927T185305Z/README.md
[b3-reporte]: costos_capacidad/20260927T200204Z/paquete_20260927T231610Z/reporte.md
[b3-tablas]: costos_capacidad/20260927T200204Z/paquete_20260927T231610Z/tablas
[b3-protocolo]: costos_capacidad/20260927T200204Z/paquete_20260927T231610Z/documentos/protocolo.md
[b3-verificador]: costos_capacidad/20260927T200204Z/paquete_20260927T231610Z/herramientas/scripts/verify_cost_capacity.py
[b3-guia]: costos_capacidad/20260927T200204Z/paquete_20260927T231610Z/README.md
[b4-reporte]: ejecucion_demoras/20260929T221620Z/paquete_20260930T013915Z_v2/reporte.md
[b4-tablas]: ejecucion_demoras/20260929T221620Z/paquete_20260930T013915Z_v2/tablas
[b4-protocolo]: ejecucion_demoras/20260929T221620Z/paquete_20260930T013915Z_v2/documentos/protocolo.md
[b4-verificador]: ejecucion_demoras/20260929T221620Z/paquete_20260930T013915Z_v2/herramientas/scripts/verify_execution_delays.py
[b4-limites]: ejecucion_demoras/20260929T221620Z/paquete_20260930T013915Z_v2/documentos/revision_tecnica_paquete.md
[b5-reporte]: estres_contrafactual/20260930T214617Z/paquete_20261001T211248Z/reporte.md
[b5-tablas]: estres_contrafactual/20260930T214617Z/paquete_20261001T211248Z/resultados
[b5-protocolo]: estres_contrafactual/20260930T214617Z/paquete_20261001T211248Z/protocolo_ejecucion.json
[b5-formulas]: estres_contrafactual/20260930T214617Z/paquete_20261001T211248Z/protocolo_tecnico.md
[b5-verificador]: estres_contrafactual/20260930T214617Z/paquete_20261001T211248Z/herramientas/scripts/verify_stress_counterfactual.py
[b5-limites]: estres_contrafactual/20260930T214617Z/paquete_20261001T211248Z/reproducibilidad.md
[b6-reporte]: estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado/reporte.md
[b6-tablas]: estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado/tablas
[b6-sintesis]: estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado/sintesis.md
[b6-protocolo]: estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado/protocolo_ejecucion.json
[b6-bootstrap]: estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado/estadistica/protocolo.json
[b6-verificador]: estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado/herramientas/scripts/verify_stability_uncertainty.py
[b6-guia]: estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado/README.md
[b6-diagnostico]: estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado/tablas/diagnostico_b2_b3_corridas.csv

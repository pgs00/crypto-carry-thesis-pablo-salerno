# Etapa B: registro de ejecución

La aprobación expresa de ambas familias está en `aprobacion_recibida.json`.
Se autenticaron los nueve archivos de la identidad propuesta antes de escribir
este registro. Ficha, protocolo, calendario, magnitudes, anclas y volumen
permanecen congelados por esos hashes. Los documentos de etapa A conservan su
estado histórico pendiente; el registro nuevo acredita la decisión posterior.

## Reglas de trabajo

- Trabajo en la rama existente, con un solo candidato editable. La preferencia
  expresa de conservar un candidato y evitar duplicar paquetes prevalece sobre
  crear otro checkout completo por la guía de worktrees. No se modifica el índice.
- Se aplican ejecución de planes y pruebas antes de implementar. Las guías no
  autorizan sus pasos genéricos de commit, limpieza o archivado: están prohibidos
  por el usuario. Temporales propios fuera del árbol, sin enlaces a originales.
- Revisión final independiente de código, exigida por la guía de ejecución;
  implementación local sin delegar tareas que compartan estado.
- Una desviación de BASE bloquea la interpretación; no se sustituye comparador
  sin consultar. Un fallo técnico no cambia la especificación económica.
- No cambiar supuestos según resultados. Recuperación impuesta de 60 minutos,
  calendario fijo sin shocks automáticos a nuevas exposiciones y basis negativo
  constante del contrafactual deben conservarse y explicarse por separado.

## Secuencia y estado inicial (registro histórico)

1. Aprobación e identidades: registradas; HEAD actual conserva el commit de etapa A.
2. Inspección de interfaces y pruebas rojas: realizadas.
3. Adaptador opcional, pruebas verdes y regresión: realizadas; revisión material cerrada.
4. Código congelado; dos controles apagados y dos de shock cero: en ejecución serial.
5. SH_P90, SH_MAX y CF, dos estrategias cada uno, seriales: pendiente.
6. Conciliación, H1/H2/H3, ventanas de intervención y reporte: pendiente.
7. Verificador portable, ataques reales, revisión y sello único: pendiente.

La estimación aprobada de 6–10 horas corresponde a replay y controles, además
del desarrollo y revisión. No hay escenarios económicos nuevos ejecutados todavía.

## Pruebas y decisiones de implementación

- Regresión anterior a extensiones: `1037 passed, 48 skipped`, 307,44 s;
  las omisiones requieren variables que señalen paquetes históricos concretos.
- Pruebas rojas conservadas: `controles/tdd_unidades_rojo.txt`,
  `controles/tdd_integracion_rojo.txt`, `controles/tdd_contrato_rojo.txt`.
  Fallaron al importar los módulos todavía inexistentes; no fueron resultados
  económicos. Después se implementaron funciones y adaptador optativos.
- La primera comprobación encontró dos expectativas incorrectas del fixture:
  el fin 600 s es exclusivo (última apertura disponible 480 s), y el basis del
  motor calcula futuro/spot menos uno, con el redondeo Decimal de esa operación.
  Se corrigieron las expectativas a mano; no el protocolo ni sus parámetros.
- Un fixture de liquidación reconcilió con residuo −3,3E−25 USDT. La aserción
  se ajustó a la tolerancia original 1E−8, sin redondear movimientos ni precios.
- Las 31 pruebas nuevas pasaron. Cubren fronteras, máximo de solapamientos,
  unidades, actividad cero, suspensión, ancla, ausencia de anticipación de la
  reapertura, basis negativo, checkpoint de ambas capas, funding simultáneo,
  prioridad de liquidación y rechazo de una modificación de archivos aprobados.
- El test de integración nuevo se denomina `test_stress_counterfactual_native.py`
  para no colisionar con el módulo unitario durante la recolección de pytest.
  Sólo se renombró ese archivo recién creado, no una referencia anterior.
- `controles/fuentes_intervencion_etapa_b.json` autentica 14.656 claves fuente
  seleccionadas. Por nivel: 6.163 minutos BTC y 8.117 ETH; 80 ausencias por
  activo pertenecen al cierre documentado y no reciben velas operables.
  Las 306 velas CF son coherentes y tienen basis negativo. La dispersión de
  4–5E−28 observada en el cociente se debe al contexto Decimal 28 del motor,
  no a una variación del ancla económica constante.
- El validador exige rango OHLC/VWAP estricto en las fuentes. Para la vela
  derivada admite únicamente dos unidades del último decimal del contexto
  (multiplicación/división); no recorta precios ni tolera errores de fuente.
- Se usa la revisión independiente exigida por `requesting-code-review` al
  terminar la capa, antes de congelar corridas costosas; habrá revisión final
  del conjunto al completar las entregas. El revisor no modifica archivos.

## Inicio de los controles continuos

Código económico congelado:
`cb47486a847ffdce4309bc72d3d642b687cc3f925462d788685b139f9c9d461c`.
Identidad completa en `protocolo_ejecucion.json`. Desde este punto no se modifica
ningún archivo económico congelado mientras sus procesos están activos.

El revisor detectó una referencia reemplazable por un manifiesto autoconsistente
tras el preflight. Se agregó la revalidación de sus hashes fijados antes/después
del replay, en comparaciones y en reuso, con dos pruebas negativas reales.
Se incluyeron además las dependencias transitivas para importar el runner desde
una copia real aislada de sólo código: esa comprobación pasó sin importar módulos
del checkout original. Esto todavía no equivale a verificar el paquete final.

Regresión general: 1.068 aprobadas y 48 omisiones históricas. Tras agregar
observadores de fases y testigos H3, regresión de los componentes afectados:
75 aprobadas. Ruff general limpio. Evidencia en `controles/puerta_pruebas_etapa_b.json`.
Los testigos son lecturas y no cambian el orden funding → fills → riesgo.

Coordinador: `scripts/run_stress_counterfactual.py --all`, datos `D:/Backtesting`,
destino original de corridas `D:/Backtesting/outputs/estres_contrafactual/20260930T214617Z`.
Comienza CONTROL_APAGADO/conditional el 30/09/2026 23:22:53 UTC. Cada familia
requiere sus dos resultados íntegros; cada escenario económico exige primero
las 44 comparaciones exactas de los cuatro controles contra los corregidos.

## Primer control y desarrollo del postproceso

CONTROL_APAGADO completo en ambas estrategias. Condicional: 586,50 s de replay,
1.704 cierres, residuo máximo 1,1E-23 USDT; permanente: 1.812,70 s, 1.704 cierres,
residuo máximo 1,01E-23. Las 22 comparaciones ordenadas contra las referencias
corregidas pasaron. CONTROL_CERO comenzó el 01/10/2026 00:07 UTC. Aún no se
interpretó ni ejecutó un escenario económico en este punto.

La primera verificación parcial de exportaciones/BASE pasó: cinco corridas
incluidas, 33 comparaciones ordenadas (incluye originales contra corregidas)
y 31 tablas recalculadas. No es la verificación final ni un sello. Su salida
queda en controles/verificacion_parcial_01.txt. Se desarrollan diagnósticos
en scripts nuevos, sin modificar ningún archivo del contrato económico.

Revisión independiente del postproceso: se corrigieron la dependencia del
indicador H1 respecto del cache, rutas de evidencia no canónicas, clasificación
manipulable de escenarios como técnicos y ausencia de control de población de
testigos. Hay pruebas rojas/verdes y negativas con cambios de celdas/bytes.
Se agregó además contraste de fuentes de barras H3/valoración y funding con
cantidad previa a fills. Auditorías unitarias nuevas: 33 aprobadas en
controles/auditorias_postproceso_02.txt. Los tests de cobertura inicialmente
usaban un dict sin el encoding real; se corrigió ese fixture, no el contrato.

El 01/10/2026 00:08 UTC seguían intactos el hash de código económico
cb47486a847ffdce4309bc72d3d642b687cc3f925462d788685b139f9c9d461c
y el índice Git 650e0e68ef402d854d191d15fb40e6733c43c34e32708908bf92efb8e3e4751e.

## Regresión del postproceso

La regresión completa posterior pasó: 1.247 pruebas, 48 omisiones que requieren
paquetes históricos mediante variables de entorno, 298,52 s. Se conserva el
log y su hash en `controles/regresion_postproceso_completa_01.json`. Las pruebas
nativas de diagnósticos guardados pasaron con shocks y contrafactual; todavía
resta contrastarlas con cada corrida económica completa.

El contrato congelado y el índice Git volvieron a verificarse intactos. Se
agregaron reglas de atributos limitadas al bloque para preservar sus bytes en
un eventual checkout Git; esto no cambia el índice ni publica archivos.
El README del candidato ahora identifica la etapa B, manteniendo el contexto
de la etapa A y las fichas aprobadas sin reescribirlas.

La prueba portátil final utilizará herramientas incluidas y Python aislado
desde otra ruta. La misma copia real exclusiva se usará para adulteraciones
controladas, restaurando sus bytes entre casos y conservando cada evidencia
fuera de esa copia. No requiere duplicar un paquete por prueba ni tocar
las corridas originales.

## Segundo intento técnico, tras corregir identidad exacta

El primer coordinador se detuvo antes de SH_P90 por cuatro representaciones Decimal distintas de valores numéricamente idénticos. Incidente en `controles/incidente_control_cero.md`; contrato inicial `protocolo_ejecucion_01.json` y código `codigo_ejecutado/` preservados. Las cuatro corridas previas permanecen intactas y se identifican en `intentos_tecnicos_previos.json`.

La corrección conserva el MinuteBar original cuando el factor es uno. Regresión: 1.248 aprobadas, 48 omisiones históricas; 30 pruebas focalizadas y siete de verificador/runner aprobadas, Ruff limpio, revisión sin hallazgos. Nueva identidad `ac1a148ac22eaa6498cdf9e35d6a825f6d81ad29a015fc6d892b57f71ce8a998`, snapshot `codigo_ejecutado_02/`. El segundo coordinador vuelve a ejecutar los cuatro controles íntegros; no reutiliza controles de otro código ni cambia comparadores o supuestos.

## Postproceso y pruebas ampliadas

Se agregaron contrastes temporales de decisiones/emisiones/fills CF y componentes realizados del ledger por ventana, separados de valoración impuesta. Sus pruebas distinguen órdenes previas de fills posteriores y excluyen doble conteo de slippage/valoración. La revisión quedó sin hallazgos abiertos.

La prueba negativa ahora invoca el MISMO wrapper incluido y Python aislado para baseline y adulteraciones; los errores de importación/proceso/IO no cuentan como rechazo. Este diseño pasó revisión y tests, pero los diez ataques reales siguen pendientes de la matriz completa.

Regresión actual: 1.255 aprobadas, 48 omisiones históricas, 579,12 s; `controles/regresion_postproceso_completa_02.json`. Se reautenticaron 11.541 archivos inicialmente versionados: sólo cambiaron los cinco archivos de seguimiento previstos; el índice permanece igual. La matriz sólo cambió en B5, B5_SHOCKS y B5_CF.

## Controles aceptados de la segunda identidad

Los dos controles con capa apagada pasaron 22 comparaciones exactas. La verificación compacta parcial incorporó las cuatro referencias y esos dos controles: 44 comparaciones exactas y 36 tablas recalculadas (`controles/verificacion_parcial_04.json`).

El control de shock cero condicional `run_13e0d5ceea1478f9b76a3919` terminó el 01/10/2026 a las 01:50 UTC y pasó también sus once cotejos exactos (`controles/compatibilidad_cero_condicional_02.json`). La cartera permanente sigue en ejecución; aún no hay carteras económicas ejecutadas. La redacción del reporte aclara además que el salto cierre/cierre en las fronteras CF mezcla movimiento de mercado y cambio de fuente. No se modificó el motor ni ninguna entrada aprobada.

## Resultados completos y cierre del 01/10/2026

Los cuatro controles continuos de la identidad `ac1a148ac22e` pasaron sus 44
comparaciones exactas antes de las seis carteras económicas. Las seis terminaron
y se conservaron sus salidas. La coordinación concurrente posterior fue
autorizada por el usuario; no partió carteras por años ni activos. Un intento
SH_P90 permanente había quedado interrumpido sin checkpoint ni salida final;
se preservó y se reinició sólo esa tarea incompleta. Las cuatro corridas
técnicas del primer código también permanecen como antecedentes, sin mezclarse
con los cuatro controles aceptados.

El primer constructor se detuvo por la representación de columnas ausentes
frente a nulos del esquema Parquet. La corrección mínima relee ese esquema
persistido también en la primera extracción, conserva el contraste estricto y
no toca precios, poblaciones ni código económico. Hay una prueba roja y 16
pruebas focalizadas aprobadas; las seis carteras no se repitieron. Véase
`controles/incidente_postproceso_esquema_fuentes.json`.

El constructor completo terminó en 374,25 s y las figuras en 11,68 s. Hay ocho
carteras financieras, ocho períodos heredados y 48 tablas. La revisión de
contenido contrastó las 64 filas de métricas, H1/H2/H3, las ventanas de shocks,
garantías y fronteras CF; no dejó hallazgos críticos o importantes abiertos.
Las cuatro figuras se inspeccionaron visualmente. Se aclaró únicamente la
redacción del criterio H2 y se sincronizaron las herramientas incluidas, sin
alterar tablas ni gráficos.

La regresión completa vigente es de 1.255 aprobadas y 48 omisiones históricas,
complementada por las 16 pruebas del defecto de esquema posterior. No se
repitió la suite por ajustes de texto. La copia portable real usa Python
aislado y herramientas incluidas; no requiere el checkout ni los datos masivos.
Sus diez adulteraciones son independientes del contenido económico aprobado.
Los resultados y tiempos definitivos del cierre se incorporan en los controles
finales, sin reinterpretar los estados históricos de este registro.

La autenticación posterior a los replays verificó 11.541 archivos inicialmente
versionados, las cuatro referencias y los cuatro intentos técnicos previos;
no encontró pérdidas ni cambios ajenos al seguimiento autorizado. El índice
Git conservó su hash. Se mantiene un candidato, sin limpieza ni publicación.

La copia aislada pasó la verificación integral de 14 corridas, 66 comparaciones
exactas y 48 tablas. Los diez casos negativos fueron construidos con cambios
reales y rechazados por el mismo verificador incluido, sin contar fallos de
construcción, importación o proceso como rechazos. Evidencia compacta en
`controles/qa_final/`; los bytes adulterados permanecen en la ruta temporal
identificada en esos registros. Sólo la frase aclaratoria H2 y documentos de
seguimiento cambiaron después de esa copia; `documentos_incluidos_cierre.json`
acredita la sincronización y verificación de la redacción final sin repetir
los ataques ni las carteras.

El reloj de las pruebas incluye una suspensión registrada por Windows desde
12:13:50 hasta 18:00:50 hora local, con transición intermedia a hibernación.
No representa seis horas continuas de cómputo. Los eventos del sistema se
conservan en `controles/coordinacion_local/suspension_windows.json`. La última
adulteración, que recorre la verificación completa, duró 264,66 s tras la
reanudación. El sellado usa la puerta final y vuelve a verificar el candidato;
la comprobación de su copia sellada se guarda fuera de ella.

# Registro de ejecución del bloque 3

2026-09-27: encargo leído íntegramente. Rama codex/crypto-carry, HEAD
af9fc227915a340665fce2f917d810dec6507d12. Árbol e índice iniciales limpios.
Huellas iniciales y snapshot de código previo guardados antes de modificar src.
Regla de trabajo: ejecutar directamente el alcance autorizado y conservar
todos los intentos, fallos y correcciones. No hay commits ni staging.

## Referencia y extensión

- Se autenticaron seis paquetes previos y ambas BASE originales. Se cotejaron
  los 1.731 identificadores de entrada con los archivos y el manifiesto local.
- La extensión económica está limitada a config, costs, diagnostics y la
  declaración de supuestos. Identidad congelada:
  `aff0e047e4638219c5fba35959e160291802dcfad2269ecfc69a8f0e08495308`.
- Compatibilidad: doce comparaciones deterministas de código previo/nuevo,
  modos anteriores y BASE con selección fija; proyecciones económicas iguales.
  Los cuatro campos diagnósticos nuevos se excluyen explícitamente de esa
  proyección, sin excluir resultados, fills, ledger o estados.
- Pruebas antes del histórico: 1.033 aprobadas, 13 omitidas por requerir un
  paquete de integración del bloque 2. Este conteo no se suma con los de suites
  focalizadas. Fallos de fixtures y sus correcciones quedan en `pruebas/`.
- Recursos medidos primero sin concurrencia. Se habilitaron como máximo dos
  replays y un único escritor de materialización.

## Revisión técnica y ejecución

- Una revisión independiente de la extensión no encontró cambios económicos
  ajenos al encargo. Señaló cuatro protecciones de recuperación: identidad de
  estrategia/escenario, exclusión mutua por par, H3 por intento y autenticación
  de raíz/datos reales. Se incorporaron como revisión técnica 2, conservando
  protocolo y runner originales. La identidad económica permanece igual.
- Costos/deslizamiento se ejecutan primero. C02 ambas estrategias y C03
  condicional terminaron y conciliaron; las restantes siguen en ejecución.
  Los estados individuales y logs son la fuente vigente de este registro.
- El candidato parcial 01 se construyó con cinco carteras verificadas. Su
  verificador detectó una diferencia de serialización de listas en CSV
  (`episodios_descubiertos.states`); no es un residual financiero ni exige
  repetir el motor. Se conserva el candidato y el fallo; la corrección se
  probará y el siguiente candidato tendrá un destino nuevo.

## Límites mantenidos

El auditor no adjudica a volumen los faltantes que no puede separar entre
fondos, inventario y reservas. H1 se reutiliza una sola vez con igualdad de
proyecciones; H3 se recalcula con nuevos CAGR y oportunidad BASE autenticada.
No hay nuevas series intradía, remuneración de caja, Word/PDF ni publicación.

## Consolidación en desarrollo

- Candidato parcial 02 conservado tras detectar Decimal anidado no serializable
  en un nuevo resumen de inventario. Serialización canónica CSV/JSON corregida
  y cubierta por pruebas. Candidato parcial 03 pasó: siete carteras, 11.928
  cierres, 56 períodos, 3.227 órdenes y 1.537 fills. No se interpreta como matriz
  completa ni se sella un candidato parcial.
- Conciliación adicional de caja/deuda/inventario/garantías y enlaces de todos
  los cierres/estados pasó en siete carteras. Revisión independiente y alcance
  confirmado del contrato de participación: `controles/`.
- Protocolo técnico 3 conserva la identidad económica y admite reutilización
  autenticada de v1/v2. Prueba real C02/v1 desde v3: `RESUMED VERIFIED`, sin replay.
- Matriz global creada en `docs/entrega_4/matriz_avance.csv`, con historial.
  Los productos previos se leyeron para confirmar sus estados; la ejecución
  posterior SOFR sucede a notas antiguas de benchmark pendiente.
- Exportación con índice temporal detectó conversión de EOL. Se añadió sólo
  protección del nuevo directorio de evidencia; la repetición pasó y comprobó
  el hash intacto del índice del usuario, 3.633 archivos previos, seis sellos,
  dos BASE y 1.731 identidades de datos.
- La primera colección de regresión extendida detectó dos tests nuevos con el
  mismo nombre de módulo. Se renombró sólo el nuevo test de integración y se
  volvió a lanzar la suite. Las pruebas de corrupción del paquete final están
  preparadas; no se contabilizan como aprobadas hasta ejecutarlas con el sello.
- La continuación automática espera ocho corridas de costos completas, aplica
  su puerta contable y operativa y recién entonces inicia participación; la
  misma puerta separa participación de capital. Máximo dos replays históricos.
- Seguimiento de revisión: la última posición de cada instante ahora debe
  coincidir con el estado final del ledger. Pruebas negativa/positiva y nueve
  carteras históricas pasaron; no cambió su economía. Batería focalizada vigente:
  67 aprobadas. La copia Git del candidato parcial 03 pasó el verificador
  offline usando sólo sus herramientas, desde otra ruta y sin datos masivos.

## Puerta de costos superada

- Las ocho carteras C02/C03/S02/S05 terminaron con estado económico `complete`.
  `control_etapa_costos.json` acredita 1.704 cierres y ocho períodos por cartera,
  tarifas y selección, órdenes/fills/ledger y ventanas de volumen. Máximo
  residual de los períodos: 1,4E-23 USDT, frente a tolerancia 1E-8 sin cambios.
- El secuenciador inició P050 condicional/permanente después de esa puerta.
  P025 y capital siguen el mismo orden y controles; no se duplicó una corrida
  durante la interrupción de la conversación.
- Regresión extendida terminada: 1.061 aprobadas y 24 omitidas (13 requieren
  artefacto previo del bloque 2 y 11 el paquete final de este bloque). Las 11
  nuevas pruebas de corrupción se ejecutarán realmente después del sello.

## Puerta de participación superada

- P050/P025 en ambas estrategias terminaron con estado económico `complete`.
  Las cuatro pasaron `control_etapa_participacion.json`: 1.704 cierres y ocho
  períodos cada una, 1.992 órdenes, 1.067 fills y sus claves de volumen. Máximo
  residual de períodos 6E-24 USDT, sin ampliar la tolerancia original.
- El secuenciador inició A050 condicional/permanente después de esa puerta.
  A100 sigue dentro de la misma familia con máximo dos replays simultáneos.
- El candidato parcial 04 verificó diez carteras (dos BASE y ocho costos),
  17.040 cierres y 80 períodos, sin nuevo replay económico. Se mantienen como
  borradores los cuatro candidatos de desarrollo; el sello final exige 18.
- Batería focalizada posterior a la corrección de deltas: 68 aprobadas. Ruff
  pasó sobre fuente y archivos nuevos. Los logs y conteos, sin sumar suites
  solapadas, constan en `pruebas/resumen_verificacion_codigo_v2.json`.

## Preparación del paquete final

- Quince corridas nuevas terminaron; A100 permanente es la última activa.
- Para compactar sin quitar evidencia, sólo `forecast_evaluation.csv` se guarda
  en gzip sin pérdida. El catálogo diferencia bytes/hash incluidos y originales;
  el verificador reconstruye los bytes originales en memoria. Tres archivos
  históricos conservaron exactamente sus 10.224 filas y hashes. No se suman
  esas copias como nuevas observaciones de H1.
- Se cerró con prueba negativa la coexistencia ambigua CSV/gzip y se verifica
  la ruta exacta de cada transferencia comprimida. Batería focalizada actual:
  70 aprobadas; `ruff_final_08.log` aprobado. No cambió el motor histórico.

## Puerta de capital superada

- A050/A100, ambas estrategias, terminaron con estado económico `complete`.
  `control_etapa_capital.json` pasó después de sus cuatro materializaciones.
  Las 16 corridas nuevas tienen 1.704 cierres y ocho períodos conciliados por
  cartera, sin cambios de tolerancia. Ninguna fue descartada ni combinada.
- Se inicia la consolidación final de 18 resultados: 16 ejecutados y dos BASE
  originales reutilizadas y verificadas. Sello, pruebas negativas y portabilidad
  final se completan a continuación, con salidas externas al paquete.

## Revisión del primer candidato completo

- `paquete_20260927T225401Z` pasó la verificación consolidada con datos locales:
  18 carteras, 30.672 cierres, 144 períodos, 8.903 órdenes, 4.887 fills y claves
  de capacidad. Se conserva sin sello como candidato de desarrollo.
- La revisión detectó que una etiqueta de tramos vacíos decía «sin corto» aun
  cuando existía corto con mark ausente. Se corrigió a ND; sin pares evaluables
  tampoco se informa cero cambios. Se añadió una evaluación separada de los
  cierres diarios usando sus cantidades y marks autenticados, sin nueva serie
  intradía. Tests RED/GREEN comprueban el umbral de 50.000, mantenimiento,
  discontinuidades, plano y mark ausente. No cambia ningún resultado financiero.
- A050/A100 permanecen en el primer tramo en todos los cierres diarios con
  corto observados; no se infieren de ello máximos ni ausencia de cruces intradía.
- La leyenda de capital se reubicó para no tapar la curva A100. La síntesis
  identifica A100 como único H2 favorable de muestra completa y distingue ese
  criterio de superar el retorno de la permanente. Batería focalizada: 72
  aprobadas; Ruff aprobado. Se construye una nueva versión completa.

## Sello y exportación

- La versión `paquete_20260927T230722Z` pasó el verificador completo contra
  fuentes locales y las once alteraciones semánticas con hashes renovados.
  Su sello se conserva intacto. La exportación encontró dos detalles de formato:
  una línea vacía final en la revisión y el espacio de contexto del diff.
- Se creó `paquete_20260927T231610Z` como derivada explícita de presentación.
  Sus 876 miembros originales restantes son idénticos, incluidos código,
  tablas, gráficos y evidencia económica. `derivacion_final.json` conserva
  los dos diffs de hashes; no hubo nueva ejecución económica.
- Se agregó protección de whitespace para `.patch` exclusivamente dentro de
  la nueva evidencia, conservando el diff byte por byte. La línea vacía final
  sólo se retiró de la nueva versión. No se modificó ningún sello previo.
- `preservacion_exportacion_final_02.json` pasó: 3.633 archivos previos
  controlados, seis paquetes anteriores, dos BASE, 1.731 identidades de datos
  y exportación exacta de 882 archivos del paquete, sin cambiar el índice del
  usuario. La prueba offline usa esa exportación y sus herramientas incluidas.

## Cierre verificado

- Las once alteraciones con hashes renovados pasaron también sobre el sello
  definitivo: cinco casos y seis casos disjuntos, sin omitidos dentro de esa
  batería. La regresión extendida acredita 1.061 pases y 24 omisiones originales;
  once de ellas eran estas pruebas ahora ejecutadas. Las otras trece requieren
  el artefacto del bloque 2. Batería focalizada 72 pases; Ruff aprobado.
  No se suman los conteos de suites solapadas.
- El verificador offline de la exportación Git pasó desde una ruta externa,
  con herramientas incluidas, `PYTHONPATH` vacío y sin `--data-root`: 880 miembros,
  18 carteras, 30.672 cierres, 144 períodos, 8.903 órdenes, 4.887 fills y claves
  de capacidad. Recalculó desde ventanas incluidas; no leyó los datos masivos.
- SHA-256 del manifiesto definitivo:
  `db68d839aa5837db72314b4f3de5509ecff283cc34d13a36e3c4f9d30298e1fb`.
  Se comprobó nuevamente la integridad de ambas versiones selladas de este
  bloque después de las pruebas, sin archivos extra ni caché dentro del sello.
- Matriz global e historial actualizados: bloque 3 ejecutado; bloques 4–6 y
  revisión transversal pendientes. Los productos de riesgo, capital, SOFR y
  señal/entradas anteriores siguen preservados. Sin Word/PDF, commit, push ni
  cambios del índice del usuario.

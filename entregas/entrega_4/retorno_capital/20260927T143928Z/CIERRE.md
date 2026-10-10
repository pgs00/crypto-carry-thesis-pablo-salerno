# Bloque retorno y capital — entrega local verificada

Los enlaces actuales apuntan a la distribución documental `20261010` y su
[protocolo](distribucion_20261010/protocolo_distribucion.md). Los controles y
sellos siguientes describen el cierre original. El estado pendiente del
benchmark es histórico: la [comparación SOFR posterior](../20260927T154653Z_sofr/distribucion_20261010/README.md)
y el [PDF final](../../README.md) se consultan por separado.

Concentración por ciclos/días, restricciones de entrada e integración anual:
**ejecutado**. Investigación de la alternativa remunerada: **ejecutado**.
Comparación remunerada: **pendiente_aprobacion_benchmark**; no se calculó.

- [Reporte HTML](distribucion_20261010/reporte.html)
- [Reporte Markdown](distribucion_20261010/reporte.md)
- [Paquete verificable](distribucion_20261010/README.md)
- [Resumen anual y capital utilizado](distribucion_20261010/tablas/resumen_integrado.csv)
- [Propuesta SOFR y fuentes](distribucion_20261010/documentos/propuesta_benchmark.md)
- [Ficha concreta pendiente](distribucion_20261010/documentos/ficha_benchmark.json)
- [Verificación y reproducción](distribucion_20261010/README.md)

## Hallazgos comprobados

Muestra [01/01/2022,01/09/2026) UTC; 10.000 USDT iniciales por BASE.
2026 abarca exclusivamente enero–agosto. Las cifras financieras y de exposición
son las corregidas existentes, verificadas sin cambios.

| Medida, muestra completa | Condicional | Permanente |
| --- | ---: | ---: |
| P&L de cartera, USDT | 785,76 | 1.680,07 |
| Retorno | 7,86% | 16,80% |
| CAGR sobre 1.704 días | 1,63% | 3,38% |
| Capital utilizado medio al cierre, USDT | 2.074,62 | 8.972,08 |
| Utilización media diaria del patrimonio | 19,81% | 82,63% |
| Tiempo activo sin polvo | 28,32% | 98,21% |
| Ciclos originales | 10 | 20 |
| Top 3 ciclos positivos / G de ciclos | 52,40% | 42,27% |
| Top 10 días positivos / G diario | 15,42% | 8,79% |
| P&L fuera de ciclos, USDT | −0,000811 | 0,096487 |

G es la suma de ganancias positivas de la población indicada: el denominador
de ciclos difiere del diario y no representa capital. Se conservan pérdidas,
aperturas incompletas, ciclos abiertos, polvo y porcentajes sobre neto sin recorte.
Los 30 ciclos y las 3.408 jornadas concilian a la tolerancia original de 1E-8.

En cada cartera hay 10.224 evaluaciones de entrada. La partición de mercado
es: 480 pasan ambos filtros, 893 fallan sólo funding, 4 sólo basis, 8.846 ambos
y 1 no evaluable. El funding calculado en la permanente es descriptivo y no
actúa como rechazo aplicado. Las entradas efectivamente aceptadas y acreditadas
son 10/20. La condicional registra 7.952 decisiones funding_not_above_cost; la
permanente, 323 basis_outside_entry_range. Las renovaciones se estudian aparte.

La concentración, menor utilización y menos ciclos describen la referencia.
No prueban el rendimiento que habría resultado de quitar filtros o remunerar
su efectivo. H1, H2 corregida y H3 conservan sus definiciones y valores; H2
sigue no favorable a la condicional. No se reinterpretó el conteo de rechazos
como tiempo elegible, ni se rehizo el riesgo intradía.

## Evidencia del cierre histórico

- [173 pruebas pertinentes: stdout](auditorias/tests_final.log) y
  [comando exacto](auditorias/tests_final.json). Incluyen 37 del nuevo bloque
  y 136 de exposición, H2 y verificador de la corrección. Ruff pasó.
- [Verificación compacta](auditorias/verificacion_compacta.json): 93 miembros
  sellados, aritmética, ventanas, poblaciones, clasificaciones, reportes y
  datos de figuras comprobados.
- [Verificación completa portable](auditorias/verificacion_completa_portable.json):
  fuentes autenticadas, tablas recomputadas y ciclos E3 idénticos. Se ejecutó
  una copia idéntica fuera del repositorio, con dependencias explícitas y sin
  Git/HEAD. [Rutas, comandos y tiempos](auditorias/portabilidad.json).
- [37 pruebas desde la copia portable](auditorias/pruebas_portables.log),
  sin omisiones de pruebas históricas.
- [Manipulación física con hashes renovados](auditorias/manipulacion_con_sello_renovado.json):
  cambiar una frontera a cero en una copia descartable provoca rechazo semántico.
- [Presentación](auditorias/presentacion.json): cuatro PNG inspeccionados,
  31 enlaces locales resueltos y tablas Markdown consistentes. MD/HTML y CSV
  de figuras también se contrastan por el verificador.
- [Preservación](auditorias/preservacion_final.json): los 48 archivos protegidos
  de motor/configuraciones, los 1.463 miembros de los cuatro paquetes fuente,
  HEAD y los bytes del índice permanecen intactos. No hay paths staged.
- [ZIP](auditorias/zip_verificado.json): todos los miembros contrastados como
  bytes/hash contra la carpeta sellada; CRC e inventario exactos.
- [Vista publicada histórica](auditorias/vista_publicada_historica.json):
  `scripts.publish_thesis --verify` pasó, preservando 19 archivos y 11 tablas.

**Excepción preexistente del control general histórico:**
`scripts.verify_repository_evidence` termina con código 1 en
`Protected source changed: src/crypto_carry/config.py`. El manifiesto de limpieza
histórico ya era incompatible con el hash de ese archivo al comenzar este
encargo; su hash inicial y final es idéntico. Se preservaron el manifiesto y
el motor, sin intentar forzar un pase. [Prueba de preexistencia](auditorias/limite_control_historico.json)
y [salida íntegra](auditorias/control_repositorio_historico.log).
Este control no certifica el estado actual del repositorio ni el bloque nuevo;
las verificaciones explícitas del paquete y sus dependencias sí finalizaron.

El verificador completo comparte el código del posprocesamiento; no es otra
implementación independiente del motor. Las fuentes intradía se verificaron
en su modalidad compacta y por hashes finales; no se reconstruyeron millones
de observaciones. Las incertidumbres de precios/proxies originales se conservan.

SHA-256 del manifiesto del paquete:
`0163cf7622d929c06773700f50d13b2e808afee85a6cf85e48d45dcac03af12b`.

SHA-256 del ZIP:
`143f217aa0af5cf7afa7669281d50df388f291cff1d184ccf4e134c9c01a4b30`.

## Estado pendiente al cierre original y alcance

La ficha `SOFR_BRUTO_ACT360_USD_PARIDAD_USDT_20260927` recomienda una cuenta
hipotética bruta USD, ACT/360, con paridad nominal 1 USDT=1 USD. Se descargaron
1.166 observaciones públicas para acreditar cobertura, sin calcular retornos.
SGOV fue la única alternativa adicional examinada. Antes del cálculo aprobado
se deberán acreditar las 53 fechas de semana sin publicación contra calendarios
oficiales y ejecutar los controles de fronteras, saldos y SOFR Index indicados.

No se ejecutaron nuevos backtests ni se modificaron parámetros o paquetes
previos. La única modificación de un archivo preexistente es la regla acotada
de `.gitattributes` para conservar bytes de esta nueva evidencia. No hubo commit,
push ni cambios en el índice. Todo está preparado localmente, no publicado en
GitHub. El benchmark posterior irá en otra versión; no hay PDF final ni se
presenta este bloque como la Entrega 4 completa.

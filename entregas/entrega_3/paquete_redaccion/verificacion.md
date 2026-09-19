# Verificación de esta preparación

Fecha: 19/09/2026. Alcance: preparar un paquete de redacción a partir de artefactos
persistidos. No se descargaron datos de mercado, no se ejecutaron nuevos backtests,
no se optimizaron parámetros y no se modificaron los resultados originales.

## Identificación y conservación

Se verificó `revision_eb5ed744b30836a39fd694fa` mediante
`verify_execution_revision`: estado completo y hashes válidos de las diez corridas
de la matriz. Se comprobó el manifiesto de la auditoría
`basis_audit_afd512e8a542f331ffa9ac3f`, su sidecar y sus salidas; su revisión
corregida coincide con la utilizada. No se encontró una revisión posterior pertinente.
Las dos corridas principales corresponden a las ventanas y configuraciones indicadas
en el LEEME. Los identificadores y el resultado de verificación se conservan en
[fuentes_originales.json](fuentes_originales.json).

Ese registro contiene 101 archivos copiados, cada uno con ruta original, SHA-256
y tamaño. Los cuatro originales académicos se copiaron byte por byte, sin alterar
contenido ni autoría. Las vistas Markdown de los informes adaptan enlaces; sus
originales exactos quedan como TXT. Los artefactos voluminosos y los datos de
mercado siguen en sus ubicaciones originales, con hashes en los manifiestos.

Las instantáneas de código son las consultadas durante la preparación posterior
a la auditoría. `execution_revision.py` difiere del hash registrado al simular:
contiene la corrección posterior del conteo de rechazos, que sólo regeneró reportes.
Las otras catorce instantáneas Python coinciden con sus hashes en ambas corridas.
No se reescribieron los manifiestos antiguos para aparentar identidad de versiones.
Además, su texto genérico heredado `conventions.marks` menciona señales; el
`signal_price_model=closed_minute`, el código y la auditoría acreditan que el basis
actual usa cierres spot/perpetuo, no mark. Se preserva ese metadato original y
se documenta el alcance correcto en la base factual.

## Controles numéricos ejecutados

[verificaciones_numericas.csv](verificaciones_numericas.csv) registra **81 controles
aprobados**, con obtenido, esperado, diferencia y tolerancia. Se comprobaron:

- Las cuatro carteras `vwap_joint`, sus corridas y duración de 365 días.
- 365 fechas diarias únicas y consecutivas por cartera: **1.460 filas**, sin puntos
  inventados ni continuidad entre ventanas. Equity final idéntico al persistido.
- Las métricas desde las series: retorno, CAGR, volatilidad, Sharpe y drawdown.
  Las 19 comparaciones numéricas dieron diferencia cero bajo la misma convención
  binary64, con tolerancia de comprobación `1e−12`. El control restante reconoce
  Sharpe nulo por volatilidad nula en la condicional tardía.
- Conciliación Decimal entre equity final menos 10.000 y componentes. Residuos:
  temprano condicional `−1.2e−24`, temprano permanente `−2e−24`, tardío condicional
  `0`, tardío permanente `0` USDT. Máximo absoluto `2e−24`, inferior a la tolerancia
  contable vigente `1e−8` USDT. No se vuelve a restar slippage.
- Tarifas prescritas y costo de ciclo: `0,0034 = 0,34% = 34 bps`, contrastado con
  configuraciones y `research_assumptions.json`.
- H1 contra el resumen persistido, incluyendo MAE, observaciones y exclusiones.
- Exclusión del funding como rechazo operativo de la permanente. Sus diagnósticos
  teóricos quedan separados; los denominadores se derivan de la cobertura auditada.
- Basis cero incluido: ETH temprano tiene 3 casos cero y 86 positivos elegibles,
  de modo que el total inclusivo es 89. Los otros grupos también concilian.
- P&L diario del 24/03/2023 contra diferencia de equity de los cierres UTC: sin
  diferencia. Se calcularon fracciones con Decimal de precisión 60.

| Estrategia temprana | Cambio de equity del día (USDT) | Beneficio anual (USDT) | Fracción del beneficio anual |
|---|---:|---:|---:|
| Condicional | 35.908875575 | 73.63631770096690445460000 | 0.487651700901503490010949711566999854490405658814409658558080 |
| Permanente | 72.96391150798 | 334.39901597150466630770000 | 0.218194157348230699708004062670993900110681106824045415380003 |

Estas fracciones comparan un cambio diario con un beneficio anual positivo; no
atribuyen causalidad a un fill ni estiman un resultado sin el episodio.

Se generaron **1.229 entradas de trazabilidad** y un diccionario de **194 campos**.
La fuente de cifras identifica archivo, campo, corrida, filtro y transformación.
Las series completas se trazan mediante su selección de filas; no se transcriben
1.460 observaciones dentro del texto. Los cambios metodológicos y referencias
bibliográficas llevan su propia procedencia por fila.

## Pruebas ejecutadas ahora

Desde la raíz del proyecto, con el entorno existente:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/unit/test_execution_revision.py tests/unit/test_basis_audit.py tests/unit/test_minute_reporting.py -q
```

Resultado observado: **42 passed in 6.81s**, código de salida 0. Se reutilizaron
las pruebas pertinentes; no se añadió una batería de tests ni se repitió la suite
completa. Los resultados de pruebas de sesiones anteriores no se presentan como
ejecutados en esta preparación.

También se ejecutó Ruff sobre los scripts nuevos: se corrigió el orden de imports
y se aplicó formato. La comprobación posterior pasó. `git diff --check` pasó;
los cambios preexistentes del proyecto se conservaron sin revertirlos.

## Comandos de generación y reproducción ejecutados

```powershell
& '.\.venv\Scripts\python.exe' entregas/entrega_3/preparar_paquete.py
& '.\.venv\Scripts\python.exe' entregas/entrega_3/completar_evidencia.py
& '.\.venv\Scripts\python.exe' entregas/entrega_3/paquete_redaccion/scripts/reproducir.py
& '.\.venv\Scripts\python.exe' entregas/entrega_3/paquete_redaccion/scripts/diccionario.py
& '.\.venv\Scripts\python.exe' entregas/entrega_3/probar_portabilidad.py
```

La prueba de portabilidad copió el paquete a una carpeta aislada dentro del
proyecto y ejecutó los scripts con Python `-I`, añadiendo sólo la carpeta de
scripts de esa copia. No cargó el proyecto económico ni utilizó el disco D.
Los **18 archivos regenerados** —tablas numéricas, datos, trazas, controles,
diccionario y cuatro exportaciones gráficas— fueron idénticos por SHA-256.
El detalle de procesos y archivos está en [portabilidad.json](evidencia/portabilidad.json).
La matriz metodológica y bibliografía son documentos editoriales y no integran
esa cuenta de cálculos regenerados.

## Figuras y revisión independiente

Se abrieron e inspeccionaron visualmente los dos PNG finales. Títulos, leyendas,
unidades, fechas, notas y cuatro carteras son legibles, sin superposiciones ni
recortes. La equity muestra dos paneles separados, capital inicial y diferencia
de escalas. El P&L separa precios, funding, costos y neto, y conserva el cero tardío.
Los SVG corresponden a las mismas figuras; su estructura XML se verifica con
el script de integridad. No se afirma una inspección visual independiente en
un visor vectorial. Los PNG son de 300 dpi.

Una revisión independiente contrastó series, métricas, H1, H3, episodio, 56 filas
diagnósticas y los 101 hashes originales. Detectó ajustes de documentación:
vencimiento efectivo de una ventana, enlaces relativos del informe y descripción
del neto en las notas. Se corrigieron las copias de lectura. No encontró errores
económicos materiales ni necesidad de nuevas simulaciones.

## Alcance y límites de la evidencia

Esta preparación vuelve a verificar la integridad de la auditoría existente;
no repite el contraste de sus 96 ZIP originales ni simula nuevamente el mercado.
Sus 4.380 observaciones y 8.760 decisiones, muestra de 80 y hashes de fuentes
siguen documentados en el informe incluido. No se interpreta esa cobertura como
todos los minutos ni como bid/ask ejecutables.

La conciliación prueba consistencia contable de los artefactos; no certifica
el motor completo, los supuestos de tarifas/margen, proxies o realismo del fill.
El bajo número de operaciones, la concentración temporal y la exposición durante
desarmes siguen siendo limitaciones. Los tres originales académicos faltantes
se detallan en el LEEME; no se inventó su contenido ni se revisó externamente la
bibliografía. Los originales disponibles y parámetros económicos se conservaron.

## Integridad y cierre del paquete

El control de contenido portátil verificó los 101 hashes de fuentes, los enlaces
locales, ambos PNG a 300 dpi, ambos SVG como XML válido y cobertura del diccionario.
El script de cierre vuelve a comparar las fuentes con los originales, escribe el
manifiesto de todos los archivos entregados y verifica sus hashes antes de comprimir.
Después contrasta cada entrada del ZIP con el archivo del paquete y comprueba
la integridad del contenedor. Excluye cachés, entornos y datos de mercado.

```powershell
& '.\.venv\Scripts\python.exe' entregas/entrega_3/paquete_redaccion/scripts/verificar_paquete.py --sin-manifiesto
& '.\.venv\Scripts\python.exe' entregas/entrega_3/empaquetar.py
& '.\.venv\Scripts\python.exe' entregas/entrega_3/paquete_redaccion/scripts/verificar_paquete.py
```

El inventario final está en `manifiesto_paquete.json`; su hash figura en
`manifiesto_paquete.sha256`. Junto al ZIP se entrega también su SHA-256. Esos
archivos permiten detectar cambios posteriores sin acceder a las rutas originales.

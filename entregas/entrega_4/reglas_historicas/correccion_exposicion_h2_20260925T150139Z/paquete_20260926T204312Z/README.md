# Corrección de exposición y H2 — versión 2

Entrega técnica preliminar. Leer el [reporte corregido](comparacion/reporte.md),
la [tabla antes/después](comparacion/antes_despues.csv) y la
[guía de métricas](documentos/guia_metricas.md).

Se reutilizan doce carteras y sus run_id. No hay simulaciones nuevas. Este paquete
es derivado y depende explícitamente del paquete sellado `20260925T005436Z`.
SHA-256 de su manifiesto: `77f1cfcaf4fb13044dbcb3b242a2eb19749cf7e88806db023a08bbe4ec272057`. No se duplican corridas grandes.
Todos los miembros del padre se comprueban para la verificación completa.

## Verificar offline desde cualquier ruta

Con Python 3.14 y PyArrow del entorno del proyecto, indicar rutas absolutas o
relativas al directorio actual. Se puede mover tanto este paquete como el padre.

```powershell
python -B -X utf8 <correccion>/herramientas/verify_rules_sensitivity_correction.py `
  --package <correccion> --parent <paquete_padre> --output <auditoria_nueva_externa.json>
```

El resultado debe decir `passed`. La salida es opcional, debe ser nueva y quedar
fuera de ambos paquetes. El comando no depende de Git, rama, HEAD, índice, red,
datos masivos ni motor. PyArrow es indispensable para verificar contra Parquet;
no se omite semántica si falta. No usar `-S`, que elimina dependencias instaladas.
El código v2 verifica clasificación y agregación independientemente del constructor,
H2 completo y todos los valores/tablas preservados; también ejecuta el verificador
original del padre bajo su alcance histórico. v2 no acepta degradarse a v1.

Para comprobar sólo el padre con su herramienta original:

```powershell
python -I -S -B -X utf8 <paquete_padre>/herramientas/verify_rules_sensitivity_package.py `
  --package <paquete_padre>
```

## Regenerar exclusivamente el posprocesamiento

Se necesita además la carpeta original E3 `Paquete de evidencia`, para autenticar
y copiar el pequeño subconjunto editorial de referencia. Usar otro destino
inexistente, fuera del padre, E3 y cualquier paquete sellado:

```powershell
python -B -X utf8 <correccion>/herramientas/correct_rules_sensitivity_report.py `
  --source-package <paquete_padre> --destination <destino_nuevo> `
  --e3-reference <Paquete_de_evidencia>
```

Matplotlib se requiere para regenerar figuras. `--no-figures` omite las imágenes
nuevas pero conserva sus datos comprobables. El constructor sella el destino
solamente al finalizar; verificarlo después con el comando anterior. No cambia
fuentes, motor, configuraciones ni resultados económicos. Si falla antes del
sello, conservar el diagnóstico y elegir otro destino para el siguiente intento.

## Archivos y alcance

- `comparacion/exposicion_intervalos.csv`: intervalos completos por activo,
  cantidades/estado/clase y banderas brutas; permite auditar los cortes.
- `comparacion/exposicion_periodo.csv`: activos y unión de cartera para ocho períodos.
- `comparacion/h2.csv`: 48 comparaciones con CAGR, Sharpes, condiciones y motivos.
- `comparacion/antes_despues.csv`: 96 filas, doce carteras y ocho períodos.
- `comparacion/preservacion_financiera.csv`: comparación de cada valor no afectado.
- `comparacion/preservacion_tablas.csv`: hashes y comparación binaria de tablas/índice.
- `comparacion/episodio_2023_03_24.csv`: controles del episodio BASE de 121 minutos.
- `comparacion/procedencia_corridas.csv`: código económico original e identidad editorial.
- `referencia_e3/`: subconjunto autenticado de las tablas y del código original,
  sin copias grandes de datos ni simulaciones. No es el paquete E3 completo.
- `herramientas/`: versión congelada del posprocesador y verificadores.
- `pruebas/`: copia de las pruebas nuevas para trazabilidad; se ejecutan en el
  proyecto, donde también están los fixtures y paquetes originales referenciados.
- `procedencia.json` y `manifiesto_paquete.json`: entradas, padre y productos nuevos.
- `verificacion_construccion.json`: controles realizados durante la construcción;
  los certificados independientes posteriores son externos y no se incorporan al sello.

El informe padre conserva las afirmaciones originales como registro histórico.
Esta versión corrige explícitamente la atribución errónea del conteo con polvo a
E3 y completa H2. No modifica ni certifica una cronología completa de Binance.
La integridad de archivos no acredita autenticidad de fuentes, causalidad del
motor ni publicación GitHub. Esta corrección local no cambia el índice de Git.

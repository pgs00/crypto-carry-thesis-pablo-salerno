# Verificaciones y alcance de los resultados

Versión técnica preliminar. Los controles de contenido, conservación, aritmética y ejecución tienen alcances distintos. Los fallos se conservan; no se modificaron manifiestos anteriores para convertirlos en pases.

## Publicación histórica y referencia presentada

| Control ejecutado | Código | Resultado y evidencia |
| --- | ---: | --- |
| Verificador histórico original, únicamente sobre copia temporal preservada | 1 | Reproduce las exigencias de HEAD/índice de la sesión anterior. [Resumen](verificacion_publicacion/reproduccion_copia_preservada_resumen.json). No acredita corrupción documental ni modifica la auditoría original. |
| `verify_historical_rules_publication.py --root . --evidence data/research/historical-rules-followup-20260924T234206Z --temp-dir <TEMP>` | 0 | [Integridad y procedencia](verificacion_publicacion/verificacion_actual.json): 196 miembros, 52 fuentes, 345 hechos, 479 filas y diez pruebas negativas; Git contrasta 202 blobs publicados y 717 referencias protegidas entre los commits pertinentes. |
| Verificador de publicación sobre la exportación incluida | 0 | [Resultado](verificacion_fuentes_exportadas.json): mismos controles documentales, `git_status=unchecked` porque la exportación no contiene `.git`. |
| Auditoría previa de los dos BASE | 0 | [Archivo](verificacion_base_previa.json): código, configuración, dependencias y salidas exactos; rehash de 1.731 identificadores de entrada. No se usaron saldos redondeados como objetivos. |
| Reproducción real acotada con extensión apagada | 0 | [Comparación final](comparacion_extension_apagada_final.json): configuración, registros económicos, equity y conciliación exactos frente al código previo, para ambas carteras. Código congelado `314631c24b36bbee58eb55a9b17505af656de453b60d1496c067e6f30b33de97`. |
| `.venv/Scripts/python.exe -B -X utf8 -m scripts.publish_thesis --verify` | 0 | [Salida](verificaciones_finales/entrega3_final.txt) y [comando/timing](verificaciones_finales/entrega3_final.json): 19 archivos publicados, 11 tablas, 3.408 filas de equity y seis figuras; ZIP de origen con SHA-256 `48485e691f7ae4b479d25766ee46aeac199cf4ea022a36d01cde177e87770916`. |

Los benchmark previos [antes](benchmark_antes.json) y [después](benchmark_despues.json) se conservan. El benchmark final usa [el código congelado](benchmark_codigo_congelado.json) porque después del primer pase se precisaron metadatos de conocimiento y del contrafactual FUT4. No se cambió aritmética para igualar la base. La ventana acotada es `[2022-01-01, 2022-01-15)` y no se confunde con la muestra completa reutilizada.

## Pruebas y análisis estático

| Comando con el intérprete del proyecto | Código | Resultado |
| --- | ---: | --- |
| `python -B -X utf8 -m pytest -q -p no:cacheprovider` | 0 | **607 passed**, 172,20 s informados por pytest, sin advertencias. [Log completo](verificaciones_finales/pytest_entrega_final.txt), [comando y tiempo de proceso](verificaciones_finales/pytest_entrega_final.json). |
| `python -B -X utf8 -m ruff check src tests scripts entregas/entrega_3/archivo/empaquetar.py` | 0 | [All checks passed](verificaciones_finales/ruff_entrega_final.txt), [registro](verificaciones_finales/ruff_entrega_final.json). |
| Regresión focalizada del informe tras el ajuste final de la leyenda H3 | 0 | **32 passed**; [comando y salida](verificaciones_finales/comparacion_tests_final.json), [Ruff posterior](verificaciones_finales/comparacion_ruff_final.json). El ajuste visual ocurrió después del inicio de la suite completa; esta regresión identifica la versión visual final. |

Los 122 casos nuevos agregan: publicación histórica (29), diagnóstico de exposición (8), tarifas/ejecución (26), reporte y paquete portable (32), preparación de reproducción (19) y orquestación/autenticación del lanzador (8). La suite final incluye también los 485 casos anteriores. Se conservan los pases intermedios de 595 y [599 pruebas](verificaciones_finales/pytest_cierre.json). Los controles de reproducción rechazan versiones Python distintas y respuestas incompletas del auditor antes de crear un destino.

Se preservan los fallos iniciales relevantes de TDD: [tarifas](tdd_reglas_fallo_inicial.txt), [publicación](verificacion_publicacion/tdd_red.json) y [utilidad de reproducción](verificacion_publicacion/reproduccion_utilidad_tdd_red.json). Esos errores de colección antes de existir la función/módulo son resultados negativos esperados, no backtests fallidos. El primer pase completo de 567 pruebas tuvo un aviso de decodificación de un subproceso; se conserva su [log](pytest_completo.txt), la [corrección UTF-8](verificacion_publicacion/correccion_utf8_pruebas.json) y el pase final sin aviso. No se alteraron expectativas económicas para ocultar diferencias.

La aceptación cubre tasas cero, conversión de pb, tarifas realizadas independientes del filtro, exclusividad BTC spot, fronteras y ausencia de anticipación, funding antes de fills, unidades netas spot, conciliación nativa y comisiones únicas, mantenimiento y deducciones duplicados, strict mode y extensión apagada. Las pruebas del informe rechazan cifras/porcentajes/deltas adulterados, cobertura diaria incompleta, identidades equivocadas y transformaciones de unknown/ND en cero.

La [revisión independiente](verificaciones_finales/revision_independiente.md) encontró que el lanzador descartaba una trayectoria terminada como insolvente. El [RED de cuatro fallos](verificaciones_finales/runner_insolvencia_tdd_red.json) precede a la corrección; el [GREEN de 27 pruebas focalizadas](verificaciones_finales/runner_insolvencia_tdd_green.json), la suite completa y el [cierre de revisión](verificaciones_finales/revision_independiente_cierre.md) verifican el ajuste. Se aplicó después de finalizar las doce carteras, todas `complete`. El runner realmente ejecutado y sus manifiestos siguen intactos; el helper corregido para reproducciones futuras conserva el estado económico, el final de muestra y la conciliación. La [resolución](verificaciones_finales/runner_insolvencia_resolucion.json) identifica ambos hashes y los límites de la corrección.

## Control existente del repositorio: fallo actual y pase histórico

`python -B -X utf8 -m scripts.verify_repository_evidence` devuelve **1 en el árbol actual**: cinco módulos autorizados para Entrega 4 difieren de la instantánea de limpieza de Entrega 3. [Salida real](verificacion_repositorio_modulo.txt), [alcance y hashes](alcance_snapshot_repositorio.json). Este fallo no se presenta como pase y no se cambia el manifiesto sellado que lo detecta.

El mismo verificador original se ejecutó en un clon temporal independiente del commit publicado `894059e4ce318e51f25211d04be9f0202de90ae7`, importando el código del clon. Dio **0**. [Resumen/comando](verificacion_publicacion/auditoria_repositorio_resumen.json), [resultado](verificacion_publicacion/auditoria_repositorio_publicacion_resultado.json) y [comparación](verificacion_publicacion/auditoria_repositorio_comparacion.json). Contrasta la referencia antigua en su contexto correcto; no reproduce el índice físico de la sesión inicial ni certifica el código modificado mediante esa referencia. No requirió restaurar finales de línea en ese clon.

Se conserva además [un primer intento de invocación directa](verificacion_repositorio.txt), con código 1 por `ModuleNotFoundError`: ejecutar como módulo desde la raíz resuelve ese problema de importación y expone el fallo de alcance anterior. No se usa aquel error de invocación como evidencia de integridad.

## Diagnóstico histórico

El [resultado](diagnostico_historico/diagnostico_resultados.json) registra 338 entradas leídas y conservadas, 993 órdenes únicas, 6.816 observaciones diarias por activo, 204 comparaciones de filtros y 177 fronteras de tramos. Sus 14 productos inventariados verificaron por hash. El diagnóstico mantiene los 288 valores de capturas API, los estados documentales, las deducciones derivadas y las cohortes; no interpola continuidad ni ejecuta la segunda tanda.

## Tanda económica y preservación final

El [índice](indice_corridas.json) contiene diez trayectorias nuevas con exit 0 y dos BASE reutilizadas verificadas. El [cierre de la recuperación](registro_interrupcion/reanudacion_resultado.json) registra doce resultados y conserva todos los logs originales. Ninguna cartera resultó insolvente ni tuvo fills de liquidación. El informe reúne 96 períodos y 20.448 conciliaciones diarias; sus [tablas](comparacion/reporte.md) mantienen los comparadores, `run_id`, estados, ND y componentes.

La [auditoría final de datos](verificacion_final_datos.json), ejecutada después de terminar todos los replays mientras se guardaban los últimos artefactos, verificó nuevamente los 1.731 identificadores, Python/dependencias, los 98 archivos originales BASE y los cinco manifiestos fuente completos. No se reescribieron las marcas antiguas de validación de cada proceso.

El [auditor independiente de fills](verificaciones_finales/auditoria_fills.json) aprobó los **2.781 fills de las doce carteras**: tarifa prescrita por timestamp/mercado/símbolo, cargo único en ledger, unidades netas spot, divisa de comisión, ventana de 60 segundos, slippage y capacidad. [Comando/exit 0](verificaciones_finales/auditoria_fills_comando.json). Sus diez controles internos incluyen fronteras exactas; la auditoría de datos reales no inventa ejecuciones subminuto donde no las hubo.

La [preservación final](preservacion_final.json) verificó los 916 archivos seguidos: **910 sin cambios** y exactamente `.gitattributes` más los cinco módulos autorizados. Los 51 miembros de la instantánea, los 38 archivos del motor económico actual y los 49 archivos de cada BASE original conservaron sus hashes esperados. HEAD, rama, remoto e índice físico coinciden con el inventario inicial; el diff preparado permanece vacío.

El verificador portable se ejecuta con `-I -S -B`, sin importar el motor ni utilizar Git o datos masivos. Los resultados posteriores al sello y la prueba real de `--prepare-only` se guardan en un certificado separado del directorio sellado, para no modificar su manifiesto. La preparación comprueba datos y entorno; no ejecuta una segunda tanda ni certifica que ésta se haya reproducido.

La [copia candidata trasladada y sellada](verificaciones_finales/comparacion_candidata_portable.json) aprobó con exit 0: 12 corridas, 564 artefactos de corrida, 456 hashes de archivos de código, 20.448 conciliaciones diarias y 96 por período. El verificador no cambió sus bytes. Se conservaron también los 915 archivos originales de corridas, instantáneas, fuentes y comparación vigilados durante esa prueba. Ese sello pertenece sólo a la copia candidata; el sello final se aplica después de cerrar documentación e inventario.

## Recursos, comandos de reproducción y conservación

La medición acotada y el rehash previo permitieron ejecutar el lote con cuatro procesos independientes y escritura de artefactos serializada. [Observación de recursos durante el lote](recursos_durante_ejecucion.json) registra fecha, RAM y espacio; no se presenta como máximo de consumo ni medición anterior. Los datos se comparten por lectura, sin descargas ni copias por escenario.

Los comandos concretos de cada variante y sus códigos se conservan en `indice_corridas.json`; sus registros individuales están en `ejecuciones/` y stdout/stderr en `logs_corridas/`. Los verificadores y la utilidad de reproducción tienen instrucciones en [README](README.md) y [reproducción](documentos/reproduccion.md). La verificación offline del paquete no relee los datos masivos; la auditoría local del lote es independiente.

Tras una interrupción solicitada por el usuario, seis variantes completas y las dos BASE quedaron preservadas. Los cuatro procesos sin artefactos finales se reiniciaron después de [rehash y comprobación del entorno](verificaciones_finales/datos_antes_reanudacion.json). El código de salida del intento abortado no estaba disponible y queda nulo; no se inventa un código. El helper acotado `herramientas/reanudar_lote_interrumpido.py` comprueba los resultados completos y el código congelado, conserva el índice anterior y los logs, y lanza sólo los cuatro pares faltantes. Pasó Ruff; se agregó después de la suite general, sin cambios económicos. Sus comandos y salidas están en [lanzamiento](reanudacion_lanzamiento.json), `logs_reanudacion/` y `registro_interrupcion/`.

El [inventario inicial](estado_inicial.json) fija HEAD, rama, remoto, hash del índice y 916 archivos seguidos. El diff existente modifica sólo `.gitattributes` y cinco módulos; el [inventario exacto de nuevos/modificados](archivos_nuevos_modificados.csv), el [índice de comandos registrados](comandos_ejecutados.json) y la [auditoría de preservación](preservacion_final.json) acompañan el cierre. Ninguna prueba de aceptación escribe commits o índices en el repositorio del usuario: los cambios de historial para fixtures ocurren en repositorios temporales.

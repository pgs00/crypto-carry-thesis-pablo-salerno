# Cierre técnico local de E4 — 02/10/2026

**B6 reparado y verificado localmente desde blobs preparados en un índice
temporal. No se creó ni publicó un commit.** La entrega pública requiere
publicar los cambios autorizados y comprobar una descarga del commit resultante.
El PDF combinado no está disponible aquí; su actualización mínima de referencias
queda preparada en [trazabilidad del documento](trazabilidad_documento.md).

El [índice único E4](../../../entregas/entrega_4/README.md) orienta la lectura;
este registro acredita la reparación y delimita los controles de esta sesión.
El dictamen académico favorable recibido en el encargo no se sustituye por una
nueva evaluación académica ni se condiciona a nuevos documentos.

## Alcance ejecutado

- [x] Comprobar rama, HEAD, cambios previos y matriz vigente; reproducir el fallo.
- [x] Recuperar los bytes B6 autenticados y proteger su preparación en Git.
- [x] Exportar blobs preparados, verificar sin mercado y conservar certificados previos.
- [x] Medir redundancias y revisar consumidores; clasificar sin bajas inseguras.
- [x] Actualizar navegación y alcance del control histórico; verificar enlaces.
- [x] Preparar la trazabilidad documental, sin fabricar PDF, SHA ni publicación.

HEAD inicial y conservado: `f1f4857fe53ac02585f739f7927031ed029da172`, rama
`codex/crypto-carry`. Coincide con el corte de la revisión; no hubo trabajo
posterior que revertir. El árbol y el índice estaban limpios. No se encontraron
instrucciones `AGENTS.md` en el repositorio ni sus directorios ascendentes.
Se aplicó el encargo directamente, sin crear una rama o copiar toda la entrega.

## Reparación B6

Paquete: `entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado`.

La exportación binaria de HEAD mediante `git ls-tree` y `git cat-file --batch`
contenía exactamente los **662 miembros y los dos archivos de sello**: sin
faltantes ni extras. El manifiesto coincidía con su sidecar. De los miembros,
505 coincidían y 157 diferían. En esos 157, y sólo en ellos, la transformación
en memoria `LF → CRLF` recuperó simultáneamente el tamaño y SHA-256 esperado.
El [CSV por miembro](diagnostico_miembros_b6.csv), el [diagnóstico](diagnostico_b6.json)
y el [rechazo real del verificador](rechazo_head_b6.txt) conservan la prueba.

El primer rechazo fue `codigo_ejecutado/src/crypto_carry/execution_revision.py`:
58.428 bytes en HEAD frente a 59.854 originales; se reprodujeron los dos hashes
del hallazgo. La copia local ya tenía los 662 miembros originales exactos.
Se conservaron esos bytes como fuente autenticada y se reescribieron sin
alteración los 157 miembros para renovar la caché de estado de Git. No se
convirtieron globalmente los textos ni se regeneraron resultados.

Se agregó a `.gitattributes` **únicamente** la regla del paquete vigente:

```gitattributes
/entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado/** -text whitespace=cr-at-eol
```

El manifiesto principal no cambió. El sidecar principal se conserva exactamente
como blob de HEAD (65 bytes LF); sólo se retiró su CRLF agregado por el checkout
local. El [registro de restauración](restauracion_b6.json) distingue ese caso
de los 157 miembros sellados. Los sidecars internos que son miembros del sello
se recuperaron, cuando correspondía, contra sus propios hashes previstos.
No se recalculó ni renovó ningún sello y no se modificó la lógica del verificador.

Se creó un índice y una base de objetos **temporales**, fuera de `.git`, con
`GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY` y el almacén original como alternativo.
Tras `git read-tree HEAD`, se preparó `.gitattributes` y se forzó la relectura
del subárbol B6 exacto con `git add --renormalize -- <B6>`: con `-text` esto
preserva los bytes; no incluye otros paquetes. El resultado contiene **157
blobs B6 corregidos**, sin cambios del manifiesto ni del sidecar principal.
`git check-attr --cached -z --stdin text` confirmó `unset` en las 664 rutas;
`git diff --cached --check` terminó con código 0.

La [preparación B6](preparacion_b6.json) identifica el árbol temporal; su OID
**no es un commit**. Se reexportó desde esos blobs, no desde una copia del árbol
de trabajo. El verificador corrió en esa única carpeta temporal, fuera del
repositorio, con `--forbid-root` para el repositorio y `D:/Backtesting`.
La única excepción del control de acceso es el entorno Python reutilizado.

El [certificado nuevo](verificacion_b6_limpia.json) pasó el sello, los contratos,
finanzas de seis carteras, 51 intervalos de bootstrap y la síntesis con diagnóstico
de 28 variantes. No abrió las particiones masivas ni ejecutó el motor. La síntesis
autentica resúmenes históricos: no equivale a recalcular íntegramente B1–B5.
El [comando y duración](comando_b6.json) y su [salida](verificacion_b6_limpia.log)
permiten distinguir este control del certificado histórico conservado.

Manifiesto conservado: `8cca7f25e8d83f0e9b879574b1f06c77b8ca2a9aa6ae07fdd94baf80e73c829d`.

## Conservación y volumen

El [inventario único](inventario_conservacion.csv) y su [fundamento](inventario.md)
clasifican A–D, versiones vigentes y dependencias. **Cero bajas y cero movimientos**.
Los antecedentes se archivan lógicamente desde la guía, manteniendo todas sus rutas.
No se deduplicaron miembros sellados, configuraciones, snapshots, controles
negativos, fuentes ni registros de intentos.

El árbol Git inicial tiene **15.913 archivos y 5.538.635.736 bytes lógicos**.
Hay 2.940 grupos de blobs idénticos y 10.919 ocurrencias adicionales, que suman
3.180.783.433 bytes repetidos en el árbol expandido. Estas cifras no son tamaño
de `.git`, clon comprimido ni ahorro de transferencia. El estado final comparable
se mide desde el árbol preparado completo en [validación final](validacion_final.json).
No se incorporan bases de mercado, entornos, cachés, ZIP ni copias nuevas de paquetes.
La única exportación temporal B6 se usó para la comprobación exigida.

El cotejo antes/después conserva los SHA-256 de **14.399 archivos de evidencia
preexistentes fuera del B6 vigente**, incluidos los restantes paquetes y sus
sellos. El diff de `src/`, `scripts/`, `tests/`, `configs/`, `uv.lock` y
`pyproject.toml` está vacío. La revisión independiente del cierre no encontró
bloqueantes y corroboró los 662 miembros B6 y el sidecar principal.

## Controles ejecutados y alcance

Python **3.14.3**, uv **0.11.6**. Las versiones instaladas se cotejaron con el
`uv.lock` incluido en B6; [entorno](entorno.json). `uvloop` sólo corresponde a
plataformas distintas de Windows. No se instalaron ni actualizaron dependencias.

| Control | Resultado y límite |
|---|---|
| Exportación HEAD + verificador B6 | Falló, como se reprodujo: 157 miembros EOL; copia completa. |
| Bytes locales + exportación del índice temporal B6 | 662/662 exactos; 664 rutas protegidas, sello original. |
| Verificador autónomo B6 reparado | Aprobado con recálculos compactos y acceso a fuentes originales bloqueado. |
| `python -m scripts.publish_thesis --verify` | Aprobado: ZIP E3 original, 11 tablas, 3.408 filas diarias, 6 figuras y 19 archivos de presentación. |
| `pytest -q -p no:cacheprovider tests/unit/test_repository_evidence.py tests/unit/test_stability_delivery.py` | Aprobado: [19 pruebas existentes](pruebas_acotadas.txt); codificación y rechazos de adulteración/exportación, sin replay. |
| Nueve verificadores de la guía, `--help` | Interfaces aprobadas; no se presentan como nueve recálculos ejecutados. |
| `python -m scripts.verify_repository_evidence` | Falló en `verify_cleanup`: siete fuentes evolucionadas frente al registro del 20/09. Véase inventario; no se corrigieron sus hashes históricos. |
| `uv --cache-dir .uv-cache sync --locked --offline --dry-run --no-install-project` | Aprobado como simulación de entorno; sólo propuso omitir la instalación editable del proyecto. No se aplicó. |
| Enlaces activos, atributos, diff y conservación externa a B6 | Resultado detallado en validación final. |
| Suite completa, lint global, backtests B1–B6, nuevas sensibilidades | No ejecutados: no hay cambio de lógica económica ni necesidad para este defecto de publicación. |
| Commit nuevo y descarga pública reparada | No ejecutados: publicación no autorizada. |

El primer intento de uv usó su caché global y falló por acceso denegado; se
resolvió con la caché local ya excluida. Un primer control de atributos pasó
demasiadas rutas como argumentos y Windows devolvió error 206; se repitió
mediante entrada estándar NUL. Ninguno se cuenta como verificación aprobada.

Los comandos se ejecutaron desde la raíz, salvo B6 aislado (directorio temporal
registrado en el JSON). La guía E4 proporciona rutas parametrizables y salidas
externas. Los certificados históricos no se sobrescribieron con la fecha actual.

## Alcance del verificador histórico

`verify_repository_evidence.verify_cleanup` protege 309 archivos de la limpieza
del 20/09/2026, incluidos 36 del motor. Las siete divergencias posteriores
revalidadas son `config.py`, `costs.py`, `data/prescribed.py`, `diagnostics.py`,
`execution.py`, `reporting.py` y `strategy.py`, bajo `src/crypto_carry/`.
Su evolución para E4 no prueba que la limpieza histórica alterara el motor.
No se cambiaron hashes, tolerancias ni código para hacer pasar ese control.

El commit que incorporó el registro es `6eb6ac68679635596d8ef33d99bd3ffab64c29e1` (consultable con
`git log -- docs/repository_cleanup_manifest.json`). Cualquier ejecución histórica
debe identificar la revisión completa y usar su propio entorno y archivos.
Esta sesión no afirma haber ejecutado el control en esa revisión antigua.
El README vigente recomienda los verificadores autónomos por paquete.

## Pasos restantes de publicación y documento

1. Revisar el diff local. `git diff --ignore-space-at-eol -- <B6>` debe estar
   vacío; el CSV de diagnóstico y el manifiesto acreditan los bytes recuperados.
   El índice real queda sin cambios: la preparación comprobada fue temporal.
2. Con autorización expresa posterior, preparar sólo las rutas del cierre y
   B6, conservar `-text`, repetir el cotejo binario del índice real y crear
   el commit de **evidencia**. No hacer `git add .` ni incluir temporales.
3. Publicar ese commit por el flujo normal autorizado. Descargar desde su SHA
   real en una carpeta nueva y repetir el verificador incluido con Python 3.14
   y dependencias fijadas. Registrar ese control externo con su fecha y SHA.
   Hasta entonces, el defecto de la versión pública anterior no está resuelto
   públicamente aunque la reparación local esté comprobada.
4. Obtener el PDF combinado y su fuente; aplicar la [lista de sustituciones y
   comprobaciones](trazabilidad_documento.md) de sección 25/R1–R12. Verificar
   los destinos del commit ya publicado y preservar las 17 páginas E3. Registrar
   el documento en una revisión posterior para evitar referencias circulares.

**Dictamen:** cierre técnico local preparado para revisión y publicación. La
entrega pública completa queda condicionada al commit/push autorizado, su
descarga verificada y la trazabilidad del PDF combinado original.

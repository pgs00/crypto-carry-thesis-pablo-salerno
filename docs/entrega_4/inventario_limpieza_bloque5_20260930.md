# Inventario de limpieza para revisión del bloque 5

Diagnóstico del 30/09/2026. No se borró, movió ni comprimió como sustitución
ningún archivo anterior. La aprobación de escenarios B5 no autoriza limpieza.
Alcance acotado al árbol real del bloque 4; no es una reestructuración general.

La raíz de las rutas de esta tabla es
`entregas/entrega_4/ejecucion_demoras/20260929T221620Z/`.
Los JSON/CSV enlazados conservan cada ruta completa. No existe
`paquete_20260930T013915Z` sin sufijo.

| Ruta bajo esa raíz | Bytes | Archivos | Estado y acción sugerida |
| --- | ---: | ---: | --- |
| paquete_20260930T012056Z/ | 333.819.291 | 1.202 | Reemplazado, antecedente sellado: conservar ahora; archivable intacto después del control de procedencia descrito abajo. |
| paquete_20260930T013915Z_v2/ | 334.413.461 | 1.206 | Vigente: conservar en el árbol activo. |
| controles_base/ | 2.781 | 2 | Dependencia de identidad y ejecución: conservar. |
| controles/ | 453.264 | 83 | Dependencias de reparación, comparación y auditoría: conservar. |
| verificacion_final/ | 659.076 | 50 | Controles externos al sello: conservar. |
| intentos/ | 4.008.560 | 14 | Diagnósticos/procedencia de ejecución: conservar. |
| ejecuciones/ | 16.486 | 12 | Índices de corridas originales: conservar. |
| logs_corridas/ | 77.753 | 22 | Registros de ejecución, no temporales por defecto: conservar. |
| logs_originales_binarios/ | 1.526.650 | 57 | Evidencia binaria de logs: conservar. |
| pruebas/ | 872.575 | 70 | Evidencia de pruebas y fallos: conservar. |
| codigo_previo/ | 560.092 | 42 | Código de procedencia: conservar; separar sólo su caché. |
| codigo_ejecutado/ | 702.891 | 50 | Código de procedencia: conservar; separar sólo su caché. |

## Publicación y referencias entrantes

HEAD `65ff8c412366817c68bdf1f37ca62a1cbfcfea6e` fue contrastado con
`git ls-remote origin refs/heads/codex/crypto-carry`, que devuelve ese mismo
commit. Se leyeron los blobs con `git cat-file --batch` y se compararon sus
SHA-256 de bytes con los archivos locales: 1.202 archivos del anterior y
1.206 del vigente coinciden exactamente con contenido publicado recuperable
por ese commit. No se modificó el índice ni se hizo fetch/commit/push.
Esta constatación es de publicación previa; la etapa A nueva sigue local.

Ambos paquetes comparten 1.193 miembros sellados idénticos; siete cambiaron
y v2 agregó cuatro. La identidad económica no hace prescindible la ruta
anterior. V2 incluye `referencias/manifiesto_candidato_anterior.json`, su
sidecar y `documentos/comparacion_con_candidato_anterior.json`, con hash y
ruta original. Manifiesto previo:
`955205887cf139bc41fd1edcdf9e63a482d0b498d8998680890cd6273ccc5603`;
vigente: `88af2936e2dc243080abdf3909cc578c184778527eb847d6b021ce76d357335b`.

Referencias entrantes concretas al anterior:

- `paquete_20260930T013915Z_v2/documentos/revision_tecnica_paquete.md` y
  `documentos/comparacion_con_candidato_anterior.json` de v2.
- `controles/revision_tecnica_entrega.md`.
- `verificacion_final/fuentes_completas.json`, `sellos_finales_intactos.json`,
  `registro_candidato.json` y comandos de exportación/adulteraciones.

El barrido previo a esta propuesta enumera 14 archivos anteriores que mencionan
el nombre único del antecedente; este inventario agrega su propia referencia.
Para nombres genéricos como `controles` o `codigo_ejecutado`, el barrido registra
menciones candidatas; no se afirma que todas sean dependencias externas resueltas.

La matriz global y `entrega_verificada.md` señalan v2. Este último también
enlaza `verificacion_final/` y `pruebas/`. `controles_base/` fija los dos run_id
corregidos y sus rutas originales en D:. `ejecuciones/` e `intentos/` enlazan
corridas, diagnósticos H3 y protocolos. Los logs y código previo/ejecutado
documentan la reparación; no son temporales sólo porque existan copias selladas.

## Prueba sin el paquete anterior

Se creó una copia **real** exclusiva de v2 en
`C:/Users/pablo/AppData/Local/Temp/b5_20260930T214617Z_limpieza/v2`, sin el
antecedente, repositorio, HEAD o índice dentro de la copia, y sin argumento
de datos masivos. El verificador incluido terminó con exit 0 y recalculó las
14 carteras desde extractos; el control de enlaces Markdown de presentación
encontró cero destinos ausentes. No se copió todo el repositorio. La enumeración
y copia no recorrieron enlaces simbólicos/junctions.

Límite decisivo: el verificador autentica el informe preservado de comparación,
pero volver a obtener sus 1.200 comparaciones exige los bytes del antecedente.
La copia aislada por sí sola no acredita esa procedencia reproducible.
**No recomiendo retirar ahora la carpeta anterior.** Podría archivarse intacta,
con ubicación/hash/commit en un índice externo y un ensayo de recuperación y
comparación, antes de autorizar su retiro por ruta exacta. No se editarían por
eso documentos sellados ni se perdería el manifiesto anterior.

## Temporales regenerables

Se identificaron estas dos carpetas exactas como candidatas a eliminación
posterior, sujetas a autorización separada:

- `entregas/entrega_4/ejecucion_demoras/20260929T221620Z/codigo_previo/.ruff_cache/`.
- `entregas/entrega_4/ejecucion_demoras/20260929T221620Z/codigo_ejecutado/.ruff_cache/`.

Son ocho archivos locales, 4.996 bytes en total, no miembros de un sello ni
versionados. Se respaldaron mediante copias reales en
`D:/Backtesting/outputs/auditorias/b5_20260930T214617Z_respaldo_caches/`,
conservando las dos rutas relativas, y se verificaron byte por byte. Los
originales siguen en su lugar. El verificador y enlaces de v2 funcionaron
sin esas carpetas externas. No confundirlas con
`controles/cache_ruff_accidental/`, evidencia versionada que se conserva.

Las copias de prueba de esta etapa están fuera del árbol versionado y
registradas en sus controles; no son versiones de entrega. No se propone
retirar corridas, datos masivos u otros archivos sólo locales sin respaldo.
Retirar archivos activos no reduce necesariamente el historial Git. No se
propone LFS, Releases ni un servicio externo.

## Evidencia

- [Inventario exacto, publicación y referencias](../../entregas/entrega_4/estres_contrafactual/20260930T214617Z/candidato/controles/inventario_limpieza.json).
- [Tabla de tamaños](../../entregas/entrega_4/estres_contrafactual/20260930T214617Z/candidato/tablas/inventario_limpieza.csv).
- [Blobs y hashes publicados](../../entregas/entrega_4/estres_contrafactual/20260930T214617Z/candidato/controles/blobs_limpieza.json).
- [Comparación entre versiones](../../entregas/entrega_4/estres_contrafactual/20260930T214617Z/candidato/controles/comparacion_paquetes_b4.json).
- [Comando aislado](../../entregas/entrega_4/estres_contrafactual/20260930T214617Z/candidato/controles/aislamiento_limpieza.json), [resultado](../../entregas/entrega_4/estres_contrafactual/20260930T214617Z/candidato/controles/v2_sin_anterior.json) y [enlaces/procedencia](../../entregas/entrega_4/estres_contrafactual/20260930T214617Z/candidato/controles/enlaces_copia_aislada.json).
- [Respaldo comprobado de cachés](../../entregas/entrega_4/estres_contrafactual/20260930T214617Z/candidato/controles/respaldo_caches.json).

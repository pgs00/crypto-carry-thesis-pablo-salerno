# Trazabilidad documental pendiente de publicación

Fecha de comprobación local: 2026-10-02. El PDF combinado de Entregas 3 y 4 y su fuente editable **no se localizaron en las ubicaciones consultadas**. No se editó ni se verificó visualmente ese PDF. Esta nota prepara la actualización mínima de sus referencias cuando se disponga del original y exista el commit publicado de evidencia corregida; no asigna un SHA futuro ni declara publicado ese cierre.

## Búsqueda y límites

Se buscaron `Tesina_Entregas_3_y_4_Pablo_Salerno.pdf`, su variante `(1).pdf` y nombres alternativos mediante inventario de PDF, DOCX, DOC, ODT, TEX, QMD y TYP dentro de:

- `C:/Users/pablo/Documentos/UCEMA/Tesina/Backtesting`.
- `C:/Users/pablo/Documentos/UCEMA/Tesina`, incluida su carpeta `Informes`, únicamente en lectura.

La búsqueda incluyó archivos ocultos. Se excluyeron dependencias y metadatos de Git; una pasada también encontró sólo copias históricas de E1/E2 en `.superpowers` y PDF de iconos de Matplotlib en `.uv-cache`. `.pytest_cache` devolvió acceso denegado, por lo que no se afirma haber inspeccionado su contenido. No se buscó en todo el disco, Drive ni correo. No se identificó una herramienta específica con una lista de adjuntos locales de esta conversación.

En `../Informes` existe `Entrega 3 Crypto Carry Binance Pablo Salerno.docx`: su XML identifica **ENTREGA 3**, contiene las referencias bibliográficas de esa entrega, carece de los textos `Entrega 4` y `R12`, y declara 17 páginas en `docProps/app.xml`. El PDF del mismo nombre contiene 17 objetos `/Type /Page` y un `/Count 17`. Esta comprobación estructural no es una revisión visual del PDF ni del Word. Los archivos no se modificaron.

| Archivo encontrado | SHA-256 leído en esta revisión |
|---|---|
| `../Informes/Entrega 3 Crypto Carry Binance Pablo Salerno.pdf` | `547727a456a14aa6daeda3adbd63b819ab75728459764b4b3872ab8464a5ccb3` |
| `../Informes/Entrega 3 Crypto Carry Binance Pablo Salerno.docx` | `89b396eb4892e5dfc38a1c6386252d21a42b7c1bb4394c1fc5bb48a90dfd3be4` |

El documento solicitado tiene, según la especificación recibida, 31 páginas: E3 ocupa las páginas físicas 1–17; E4 comienza en la física 18, sección 14; la sección 25 está en la física 30, impresa 29, con R1–R12. Esos datos **provienen del encargo y no se corroboraron contra el archivo ausente**. La fuente E3 encontrada no se utiliza para reconstruir ni sustituir el documento combinado.

## Qué se puede fijar con evidencia local

El remoto configurado del repositorio es `https://github.com/pgs00/crypto-carry-thesis-pablo-salerno.git`. El HEAD observado durante esta revisión fue `f1f4857fe53ac02585f739f7927031ed029da172`; se registra sólo como estado inicial, no como nuevo commit de publicación ni como SHA leído dentro del PDF.

La [matriz de avance](../matriz_avance.csv) y el [índice de versiones B6](../../../entregas/entrega_4/estabilidad_incertidumbre/indice_versiones.json) identifican el paquete B6 vigente:

`entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado`

SHA-256 de su manifiesto local: `8cca7f25e8d83f0e9b879574b1f06c77b8ca2a9aa6ae07fdd94baf80e73c829d`.

Sus destinos concretos, existentes al leer esta nota, son:

- [README B6](../../../entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado/README.md).
- [Reporte B6](../../../entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado/reporte.md).
- [Síntesis B6](../../../entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado/sintesis.md).
- [Manifiesto B6](../../../entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado/manifiesto_paquete.json).
- [Certificado externo del cierre B6 original](../../../entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/controles_finales_corregidos/verificacion_offline.json).

El certificado original y los estados guardados del paquete describen su cierre histórico. La comprobación de los bytes de la futura exportación/publicación corregida debe citar su propio certificado externo; no reemplazar ni modificar el sello histórico para incorporar un estado posterior.

## R1–R12 sin correspondencia inventada

No se conocen el texto literal, las rutas ni las anotaciones de enlace de R1–R12 porque no está disponible la sección 25. Por tanto, **las doce correspondencias quedan pendientes de extracción del original**. La presencia de un identificador `R12` en `scripts/signal_sensitivity_docs.py` no resuelve esa correspondencia: pertenece a una matriz de requisitos R01–R20 del bloque B2.

La tabla siguiente ofrece destinos por tema comprobados localmente. **No asigna números R ni reemplaza la bibliografía del documento.** Al disponer de la sección 25, cada entrada debe cotejarse con el tema y archivo realmente citados antes de actualizar su destino.

| Tema local | Destino de referencia |
|---|---|
| BASE con exposición y H2 corregidas | [README del paquete de corrección](../../../entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z/README.md) |
| Riesgo intradía | [Reporte](../../../entregas/entrega_4/riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z/reporte.md) |
| B1 retorno y capital | [Reporte](../../../entregas/entrega_4/retorno_capital/20260927T143928Z/paquete_20260927T152732Z/reporte.md) |
| B1 comparación SOFR | [Reporte](../../../entregas/entrega_4/retorno_capital/20260927T154653Z_sofr/paquete_20260927T162350Z/reporte.md) |
| B2 señal y entrada | [Reporte](../../../entregas/entrega_4/senal_entradas/20260927T170230Z/paquete_20260927T185305Z/reporte.md) |
| B3 costos y capacidad | [Reporte](../../../entregas/entrega_4/costos_capacidad/20260927T200204Z/paquete_20260927T231610Z/reporte.md) |
| B4 ejecución y demoras | [Reporte](../../../entregas/entrega_4/ejecucion_demoras/20260929T221620Z/paquete_20260930T013915Z_v2/reporte.md) |
| B5 estrés y contrafáctico | [Reporte](../../../entregas/entrega_4/estres_contrafactual/20260930T214617Z/paquete_20261001T211248Z/reporte.md) |
| B6 estabilidad e incertidumbre | [Reporte](../../../entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado/reporte.md) |
| Diagnóstico dirigido de B2/B3 | [Corridas examinadas](../../../entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado/tablas/diagnostico_b2_b3_corridas.csv) |

## Secuencia concreta después del commit y push de evidencia

Estas operaciones son posteriores. Esta nota no ejecuta commit, push ni cambios del índice real.

1. **Fijar el commit de evidencia corregida.** Una vez creado y publicado mediante una acción autorizada, registrar su SHA completo de 40 caracteres y la rama remota. Confirmar que el árbol de ese commit contiene la corrección y los archivos citados, con los bytes comprobados por la verificación de exportación. No reutilizar automáticamente el HEAD inicial ni el hash del manifiesto como si fueran el SHA Git. Si después existe un commit documental, conservar por separado ambos identificadores.
2. **Recuperar y preservar el original.** Registrar rutas y SHA-256 del PDF combinado y su fuente editable, guardar una copia de trabajo y extraer el texto y los hipervínculos de la sección 25. Comprobar que el PDF efectivamente tiene 31 páginas, E3 1–17, E4 desde 18/sección 14 y sección 25 en física 30/impresa 29. Si no coincide, detener la sustitución automática y revisar la identidad del documento.
3. **Inventariar R1–R12.** Para cada R conservar etiqueta, título/texto literal, página, destino real del hipervínculo y ruta dentro del repositorio. Contrastar texto visible, relaciones de hipervínculos de la fuente y anotaciones `/URI` del PDF: que un texto muestre un SHA nuevo no garantiza que su enlace lo use. Distinguir referencias bibliográficas externas y referencias históricas de E3, que pueden tener destinos diferentes válidos.
4. **Cambiar sólo la trazabilidad aprobada de E4.** Actualizar la mención del commit de evidencia y los destinos de las referencias E4 que deban apuntar al cierre corregido. Usar URLs con el SHA completo: `https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/blob/SHA_EVIDENCIA/ruta/archivo` para archivos y `/tree/SHA_EVIDENCIA/ruta` para carpetas. `SHA_EVIDENCIA` es aquí una variable explicativa; no debe quedar en el documento entregado. No efectuar un reemplazo global de todos los SHA del documento ni tocar referencias históricas válidas de E3.
5. **Verificar los destinos publicados.** Para cada URL, comprobar primero que el archivo existe en el árbol del commit (`git cat-file -e SHA_EVIDENCIA:ruta/archivo`) y luego abrir el enlace público exacto tras el push. Comprobar el destino final y cualquier fragmento de sección; evitar un enlace que sólo redirija a la rama actual. Descargar el contenido raw del mismo SHA y contrastar su SHA-256 cuando la referencia dependa de bytes sellados. Registrar fecha UTC, URL final, estado HTTP y resultado. La existencia del objeto Git local o de una URL sintácticamente correcta no acredita publicación accesible.
6. **Exportar y revisar.** Renderizar la fuente y el PDF final. Revisar todas las páginas y, especialmente, las páginas 18, 30 y 31, con las tipografías y el motor de render originales cuando estén disponibles. Mantener 31 páginas y los mismos encabezados, tablas, cifras, saltos y numeración. Comparar E3 1–17 con el original mediante texto, vínculos y render de páginas al mismo tamaño/resolución; no basta comparar el tamaño total del PDF. Ante un cambio en E3, revertir la exportación o corregir el procedimiento hasta preservarla. Confirmar que sólo cambian los textos/destinos autorizados de E4.
7. **Cerrar el documento en un commit posterior.** Publicar el PDF y su fuente en una revisión posterior al commit de evidencia. El PDF cita el SHA de evidencia ya existente; el registro documental identifica además el SHA del PDF final. No intentar incluir en el propio documento el SHA del commit que a su vez contiene ese documento: eso crea una dependencia circular.

La comparación del documento debe dejar un registro por R1–R12 con destino anterior, destino nuevo y comprobación; los SHA del PDF y de la fuente finales; y el resultado de preservación de las 17 páginas E3. Ninguno de esos controles se da por ejecutado en ausencia del archivo combinado.

## Revisión independiente del generador de síntesis

Se revisaron en lectura `scripts/stability_uncertainty_synthesis.py`, los puntos de generación de `scripts/package_stability_uncertainty.py` y la documentación local de B6. No se ejecutó el generador ni se cambió su código. La corrección de exportación de Git puede conservar íntegramente sus resultados; no requiere regenerar la síntesis ni las cifras.

- `build()` escribe tablas, copia fuentes y produce `sintesis.md`; no debe usarse como comprobación de un paquete sellado. `verify()` reproduce las tablas y el relato desde copias autenticadas. El verificador integral separa además la comprobación financiera y estadística.
- La síntesis autentica selectivamente resúmenes y registros históricos y reutiliza la compatibilidad B5; no prueba de nuevo todos los cálculos históricos. El diagnóstico B2/B3 abarca las 28 variantes y excluye sus dos BASE reutilizadas. Su conclusión se limita a la precondición de la rama `liquidation_pending`; no acredita equivalencia universal entre motores ni historia certificada del exchange.
- `cached_history()` usa tamaño/mtime para reutilizar el inventario antes de rehashear fuentes cambiadas. Ese mecanismo es una optimización de construcción, no un control independiente de bytes publicados. Para el cierre se necesitan el sello, el verificador offline y la comprobación de los blobs exportados.
- Las filas B6 identifican `source_package="candidato_B6"`, y `sintesis_estado.json` guarda `published=false`, `word_pdf="pendiente"` y revisión académica pendiente. Son metadatos del momento de construcción; no contienen el futuro SHA Git ni autorizan convertir el paquete sellado en un registro vivo de publicación. La nota posterior y los enlaces del documento deben reflejar el estado nuevo sin reescribir esos archivos históricos.
- El generador no construye el documento combinado, su sección 25 ni el mapa R1–R12. No permite reconstruir por inferencia las referencias que no se han visto.

Identidad del código leído: `scripts/stability_uncertainty_synthesis.py`, SHA-256 `6daac4d904bfbefd275329215f8549cab701bad20815ed5b734260deded8d1bd`; `scripts/package_stability_uncertainty.py`, SHA-256 `6834f6f1dd582b7948eb35dfcf2276d4570308fed0b1e4e6dc439c3905bff4e2`.

Estado documental al terminar esta revisión: **instrucciones y destinos locales preparados; actualización del PDF/fuente, correspondencia R1–R12 y comprobación de enlaces publicados pendientes**.

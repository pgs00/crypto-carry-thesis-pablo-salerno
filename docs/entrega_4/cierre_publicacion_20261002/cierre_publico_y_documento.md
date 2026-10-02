# Cierre público y documental de E4, 02/10/2026

Esta nota registra comprobaciones posteriores a la sesión local del
[README histórico](README.md). El commit de evidencia publicado y examinado es
[`c0b432d8bff7fb86cf86a6bc0b28beffab225516`](https://github.com/pgs00/crypto-carry-thesis-pablo-salerno/commit/c0b432d8bff7fb86cf86a6bc0b28beffab225516),
en la rama `codex/crypto-carry`. El commit documental que contiene esta nota
es posterior: el PDF cita el commit de evidencia, no intenta citar su propio
commit futuro. Las menciones de publicación o documento pendientes en los
registros anteriores describen aquellas sesiones y se conservan.

## Publicación de la evidencia

Se descargaron los archivos del B6 vigente desde el commit indicado y se
ejecutó su control de integridad: **662 miembros conformes**, sin faltantes
ni archivos adicionales. El manifiesto original mantiene su SHA-256
`8cca7f25e8d83f0e9b879574b1f06c77b8ca2a9aa6ae07fdd94baf80e73c829d`.

La comparación con `f1f4857fe53ac02585f739f7927031ed029da172` identificó 157
archivos B6 modificados exclusivamente por la restitución de LF a CRLF.
Los 507 archivos restantes del directorio, incluidos manifiesto y sidecar,
mantuvieron su identidad Git. No cambió el contenido económico de código, configuraciones,
tablas de resultados ni parámetros. La publicación añadió 19 archivos de
documentación, sin bajas, y conservó los 14.399 archivos de evidencia
anteriores fuera del B6 vigente. Se comprobaron los 147 enlaces locales del
conjunto documental revisado y las 14 comparaciones de paquetes del inventario.

La organización distingue paquetes vigentes y antecedentes. No se eliminan
duplicados históricos, se renuevan sellos ni se ejecutan nuevos backtests.

## Verificación ejecutada y límite de portabilidad

La revisión posterior ejecutó los verificadores incluidos en el paquete
descargado, con **Python 3.14.3, NumPy 2.3.5 y PyArrow 25.0.1 en Linux**, en un
entorno aislado preparado con el lock congelado. El sello, contrato, componente
financiero y síntesis resultaron conformes. El componente financiero recalculó
las tablas desde insumos compactos y la síntesis autenticó 258 copias de fuentes.
Esto no equivale a reproducir el motor ni a releer las particiones masivas.

**El verificador integral oficial no obtuvo PASS en Linux.** Se detuvo en
`herramientas/scripts/stability_uncertainty_bootstrap.py`, función `verify_csv`
(líneas 780-782), porque compara los bytes del CSV recalculado. En
`tablas/bootstrap_intervalos.csv` difieren 26 celdas numéricas de 9 de las 51
filas, correspondientes a 13 límites repetidos en `finite_quantile_*`.
La diferencia absoluta máxima es `6.938893903907228e-18`, hasta cuatro ULP.
No cambian encabezados, identificadores, conteos, estados ni otros campos.
El CSV publicado coincide exactamente con la serialización del JSON publicado.

Los controles existentes de réplicas, semillas, puntos e intervalos JSON pasan
con su tolerancia declarada (`2e-11`); el CSV de puntos, la cobertura y el
registro de control escalar coinciden exactamente. El diagnóstico posterior
al aborto se realizó por separado y **no se presenta como un PASS integral**.
Las diferencias observadas no alteran las cifras mostradas, signos ni
conclusiones. Son compatibles con diferencias de aritmética flotante entre
entornos; no se aisló la primitiva que las origina.

Se conserva **Windows como entorno de referencia** de la ejecución integral
registrada en [el cierre local](verificacion_b6_limpia.json), cuya versión de
Python y dependencias están en [entorno.json](entorno.json). Esa ejecución
Windows es evidencia de la sesión local anterior, no una nueva ejecución
independiente de esta revisión. No se garantiza identidad textual del
recálculo entre sistemas operativos. No se modifican el comparador congelado,
las estadísticas ni los sellos para convertir el rechazo de Linux en éxito.

Los resultados comprobados, los límites de ejecución y el detalle de las
diferencias están en [verificacion_publicacion.json](verificacion_publicacion.json).

## PDF de entrega

El [PDF combinado final](../../../entregas/entrega_4/documento_final/Tesina_Entregas_3_y_4_Pablo_Salerno.pdf)
conserva las 31 páginas. El cambio visible se limita al SHA de la sección 25
(página física 30, numerada 29); los destinos de evidencia E4 R1-R12 apuntan
al mismo commit publicado, conservando sus rutas: se actualizaron 114
anotaciones de enlace y se conservaron otras 25. Las referencias históricas
de E3 y las fuentes externas se mantienen.

Se comprobó el texto, los enlaces y el render de las páginas contra el PDF
combinado recibido. Las páginas 1-17 de E3 se preservan sin cambios; esta
comparación no certifica por sí sola igualdad con una entrega E3 anterior
distinta del combinado recibido. Los hashes del original y del resultado,
el mapa de enlaces y los resultados de comparación se registran en el JSON
de verificación citado arriba.

No se dispuso de la fuente editable del documento combinado. La actualización
se aplicó directamente sobre el PDF, conservando sus recursos tipográficos;
no se reconstruyó ni se presentó como actualizada una fuente DOCX inexistente
en esta sesión. Una futura exportación desde otra fuente deberá conservar
esta trazabilidad para no reintroducir el commit anterior.

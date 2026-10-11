# Procedencia y autenticación

Los informes de lectura están en `results/<tema>/README.md`. Sus tablas,
figuras y fuentes pertenecen a los paquetes completos de `evidencia/`,
que conservan sus bytes, manifiestos, configuraciones efectivas e identidades
de corrida. La organización temática no combina experimentos.

[El catálogo del producto](producto.json) identifica cada paquete por su
manifiesto de distribución y registra las adaptaciones editoriales y sus originales.
Su alcance son los artefactos reorganizados y la documentación actual; los
snapshots de código se autentican dentro de cada paquete.
El control `python -B -X utf8 -m scripts.verify_product` comprueba esas
identidades, los miembros de cada paquete y los archivos documentales actuales.
Los verificadores científicos de la [guía de reproducción](../reproduction.md)
comprueban además los cálculos y las conciliaciones de su alcance específico.

[El mapa de rutas](rutas.json) permite localizar fuentes cuyo registro histórico
conserva una dirección anterior. Resolver una dirección no reemplaza la
comprobación de sus hashes. Los nombres de entregas, fechas y bloques que
permanecen dentro de snapshots, informes originales o certificados identifican
su contexto histórico; no son la navegación actual ni una certificación nueva.

El padre de reglas históricas se conserva completo en
[`data/evidence/reglas_historicas/`](../../data/evidence/reglas_historicas/):
la corrección de exposición y H2 autentica todos sus miembros. Las ventanas
independientes se conservan como un experimento distinto en
[`data/evidence/ventanas_independientes/`](../../data/evidence/ventanas_independientes/).
La fuente comprimida de las carteras continuas y su sidecar están en
[`data/evidence/`](../../data/evidence/). Estas dependencias compactas forman
parte del repositorio; la verificación no requiere respaldos privados.

Los controles históricos conservados mantienen sus fechas y alcances. Una
verificación actual produce una salida nueva fuera de los paquetes; no se
reutilizan certificados anteriores como aprobación de esta organización.

La [vista de carteras continuas](../../results/base/continuo/README.md) conserva
sus 12 tablas y 6 figuras originales. Su adaptación editorial del 11/10/2026
actualiza título y navegación con un manifiesto nuevo. El
[manifiesto anterior](../../results/base/continuo/procedencia/distribucion_20261010/manifest.json),
su sidecar y el README previo permanecen íntegros; `scripts.publish_thesis --verify`
autentica los 19 miembros originales y la adaptación.

Las menciones a devoluciones, autorizaciones y propuestas en los reportes
autenticados describen su contexto de elaboración. Los informes temáticos
presentan los experimentos ejecutados con sus métodos, resultados y límites;
las propuestas no ejecutadas no se presentan como resultados.

El [PDF de la tesina](../../Tesina_Pablo_Salerno.pdf), de 24 páginas, se exportó
desde el DOCX identificado en `Informes/`, fuera del repositorio. El PDF anterior
coincidía byte a byte con `Entrega 4 Crypto Carry Binance Pablo Salerno.pdf`
(SHA-256 `f98df37bee61164948e2b26537c6aadebf77335aa60b37ceace27ffa029ea3fb`);
su contenido, tablas y fórmulas corresponden al DOCX del mismo nombre.
La fuente corregida se conserva como `Informes/Tesina_Pablo_Salerno.docx`.
La edición actualiza portada, títulos, redacción, énfasis y navegación;
conserva las 16 tablas, las siete ecuaciones y las figuras de la fuente, e incluye
la declaración de asistencia de IA del proyecto. El catálogo distingue esta
exportación del PDF original respaldado.

`Informes/Whitepaper.pdf` (27 páginas) y `Informes/Executive_Briefing.pdf`
(3 páginas) son versiones distintas, disponibles únicamente como PDF en la
carpeta examinada. Se revisaron sus cifras y presentación; no se reconstruyeron
ni se sustituyeron por el DOCX de 24 páginas. Su edición requiere las fuentes
correspondientes. No forman parte de los archivos publicados en este repositorio.

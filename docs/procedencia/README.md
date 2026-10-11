# Procedencia y autenticación

Los informes de lectura están en `results/<tema>/README.md`. Sus tablas,
figuras y fuentes pertenecen a los paquetes completos de `evidencia/`,
que conservan sus bytes, manifiestos, configuraciones efectivas e identidades
de corrida. La organización temática no combina experimentos.

[El catálogo del producto](producto.json) identifica cada paquete por su
manifiesto original de distribución y registra las adaptaciones editoriales.
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

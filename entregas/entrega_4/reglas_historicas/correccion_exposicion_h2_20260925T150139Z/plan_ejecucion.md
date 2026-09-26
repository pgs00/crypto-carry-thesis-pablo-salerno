# Corrección de exposición y H2 — plan de ejecución

Fecha de inicio: 2026-09-25 UTC. Alcance autorizado: posprocesamiento de las doce
carteras existentes. No se ejecutan backtests, no se modifica el motor económico,
no se altera el índice de Git y no se escriben paquetes o certificados anteriores.

1. Conservar inventario binario inicial y diagnosticar ambos defectos mediante
   pruebas que fallen con el código original. Trazar las posiciones persistidas
   hasta el código y las tablas archivadas de la publicación continua E3.
2. Extraer dos auxiliares puros: H2 con CAGR positivo y comparabilidad explícita;
   exposición E3 con trayectoria completa, polvo heredado y unión temporal.
   Mantener resultados esperados literales e intervalos originales como controles.
3. Construir una entrega derivada v2 en un destino inexistente, con referencia
   verificable al manifiesto padre. Reutilizar los mismos run_id y copiar sin
   cambios las tablas financieras/H1/H3 no afectadas. Regenerar sólo exposición,
   H2, deltas operativos, figuras afectadas y documentación.
4. Verificar v2 independientemente: fuentes y productos, semántica de intervalos,
   agregación, H2 y preservación de valores financieros. Probar corrupciones en
   temporales, incluso después de recalcular sus sellos de prueba.
5. Ejecutar pruebas pertinentes, Ruff y verificadores originales con sus alcances;
   comprobar portabilidad fuera del árbol con ruta padre explícita; cerrar con
   inventario final y comandos/resultados reales en archivos nuevos.

Distribución independiente: auxiliar H2 y verificador v2; auditoría de linaje y
auxiliar de exposición; integración, constructor, reporte y controles finales.
Los scripts archivados y el manifiesto padre se conservan intactos.

Producto previsto: `paquete/` dentro de esta carpeta. Auditorías y resultados de
verificación se escriben fuera del producto sellado. La corrección se identifica
como `exposure_h2_v2`, separada de los hashes del código que ejecutó las carteras.

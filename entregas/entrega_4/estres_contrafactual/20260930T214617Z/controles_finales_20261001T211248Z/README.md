# Cierre del bloque 5

Estado: **completado**, 2026-10-01T21:24:10.315709+00:00. Las seis carteras económicas y cuatro controles terminaron; se preservan las cuatro referencias y los intentos iniciales. No quedan replays ni coordinadores de este cierre activos.

Entrega sellada: `entregas/entrega_4/estres_contrafactual/20260930T214617Z/paquete_20261001T211248Z`. SHA-256 del manifiesto: `091fe38bba57ad5be62275cabb03579b1c47f2d96784ed7c5e2ce6377467a8de`.

- [Verificación del sello](verificacion_sello.json): 14 corridas, 66 cotejos exactos y 48 tablas; Python aislado y herramientas de la propia entrega.
- [Comandos exactos y tiempos](estado_cierre.json): sellado 302,76 s; verificación final 288,39 s. Auditoría escrita fuera de la entrega.
- [Preservación y seguimiento](verificacion_preservacion_cierre.json): índice Git sin cambios; sólo tres filas B5 actualizadas; demás filas idénticas byte a byte.

Dentro de la entrega: `controles/qa_final/pruebas_negativas.json` acredita diez adulteraciones reales rechazadas; `controles/puerta_sellado_final.json` reúne regresión, controles y revisiones. La frase H2 aclarada después de la copia QA fue verificada con las herramientas incluidas, sin repetir carteras ni ataques por un cambio de texto.

La suspensión del equipo explica el intervalo largo de reloj de una prueba; los eventos quedan en el registro de coordinación. No se atribuye ese intervalo a cómputo continuo.

Un candidato editable conservado; una sola copia final sellada; sin limpieza, archivado de paquetes anteriores, commit, push ni cambios del índice. Bloque 6, revisión/redacción transversal y alcance de la reparación B2/B3 permanecen pendientes.

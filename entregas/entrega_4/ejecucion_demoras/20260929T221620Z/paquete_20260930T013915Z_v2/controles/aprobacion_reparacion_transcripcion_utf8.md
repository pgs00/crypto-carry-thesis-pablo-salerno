# Aprobación recibida: transcripción en UTF-8

Respuesta expresa del usuario en esta conversación:

> Sí: aplicar la reparación con identidad y controles separados.

La autorización se refiere a la reparación preexistente descrita en
[propuesta_reparacion_liquidacion.md](propuesta_reparacion_liquidacion.md):
priorizar el propósito `liquidate` al reintentar un cierre parcial ya escalado
a liquidación, sin añadir demora de cliente ni eliminar sus cargos. La guardia
también impide restaurar HOLDING desde corrección/rebalance mientras queda
corto por liquidar. La nueva orden conserva ventana y volumen BASE; el fill
comprometido anterior conserva su tratamiento original.

Las referencias selladas se preservan. Los dos controles BASE completos tienen
identidades separadas y se comparan a precisión original; no forman parte de
las doce variantes nuevas.

El [registro original congelado](aprobacion_reparacion.md) sufrió sustitución
de caracteres acentuados al escribirse mediante una tubería ASCII de PowerShell.
Se conserva sin modificar porque su hash integra el protocolo de ejecución:

`438656c9f7b97416d7f0e194b6520db7c8d89099971d7bea41e7ea8dd700595e`.

Esta transcripción recupera la respuesta del usuario desde el mensaje original
de la conversación. No amplía la autorización, no cambia el protocolo económico
y no implica una aprobación nueva.

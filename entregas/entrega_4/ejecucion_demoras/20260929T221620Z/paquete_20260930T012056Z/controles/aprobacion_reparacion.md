# Aprobaci?n recibida

El usuario respondi? a la pregunta sobre la reparaci?n preexistente:

> S?: aplicar la reparaci?n con identidad y controles separados.

Se preserva la prioridad de liquidaci?n al resolver el timeout de la orden comprometida. La guardia unificada cubre el reintento close_perp y evita que las ramas correct/rebalance restauren HOLDING mientras queda corto por liquidar. No cambia el fill comprometido ni convierte la liquidaci?n en instant?nea; la nueva orden liquidate conserva ventana y volumen BASE.

BASE sellada no se reemplaza. Se ejecutan controles BASE completos con el c?digo corregido y se comparan proyecciones a precisi?n ?ntegra. Los controles no integran las doce variantes.

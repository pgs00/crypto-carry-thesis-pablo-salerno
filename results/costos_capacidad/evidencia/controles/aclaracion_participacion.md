# Alcance de participación confirmado al inspeccionar el motor

El protocolo previo manda preservar las excepciones originales, si existen,
sin ampliarlas. En el contrato efectivamente ejecutado no se encontró una
vía autónoma de fills forzosos del exchange que omita `minute_capacity`.
Las órdenes con propósito `liquidate` usan la misma ventana/cupo del motor.
El auditor conserva ese contrato y separa el cargo específico de liquidación.

Por ello, la población de capacidad incluye todos los fills sujetos al cupo,
incluidos los que eventualmente lleven esa marca. La etiqueta de voluntarios
del protocolo previo se precisa aquí; no se crea ni elimina una excepción,
no se cambia el criterio de extremos ni se redefine la ejecución.

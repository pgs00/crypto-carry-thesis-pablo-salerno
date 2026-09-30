# Defecto preexistente: reintento de un cierre escalado a liquidación

Estado: propuesta separada, no aplicada. Revisión independiente del motor previo
y de la extensión con pruebas nativas; no es un resultado histórico.

Cuando `close_perp` ya tiene una ventana comprometida, una observación posterior
puede marcar `pair.liquidation_pending`. Si la ventana termina con un fill parcial,
`_timeout` reenvía el propósito de la orden antigua. El remanente conserva
`close_perp` y pierde la clasificación/cargo de liquidación. El defecto existe con
demora cero; la extensión de demora puede prolongar además el reintento.

Caso sintético LC05: envío t=240 s, ventana [540,600), disparador de liquidación
t=570, parcial al cierre t=600, remanente reenviado como close_perp hacia t=960.
La cronología BASE permite el fill comprometido t=600; la propuesta sólo reclasifica
el intento NUEVO como liquidate, con demora adicional cero y sus cargos originales.

Corrección propuesta en `_timeout`, rama de close_perp/liquidate/close_spot:

```python
purpose = (
    "liquidate"
    if order.market == "futures" and self.pairs[order.symbol].liquidation_pending
    else order.purpose
)
self._submit(order.symbol, order.market, order.side, quantity, purpose)
```

No cambia prioridad, volumen ni precio de la ventana comprometida. Se probará
primero con el fixture que falla, luego con regresión y compatibilidad. Requiere
identidad propia porque cambia la economía anterior. Las BASE originales y sus
sellos se conservarán; cualquier replay de control corregido se publicará como
control separado, y se medirá si el defecto se materializa en la muestra histórica.

La sección 4 del encargo exige: «Si encontrás un defecto económico preexistente
que exija cambiar la referencia, documentalo y pedí aprobación para esa parte
antes de mezclarlo con este bloque.» Hasta esa aprobación no se incorpora esta
reparación al código ejecutado.

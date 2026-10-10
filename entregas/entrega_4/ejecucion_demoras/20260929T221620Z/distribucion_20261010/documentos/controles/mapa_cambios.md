# Mapa de cambios autorizados

| Archivo | Cambio y contrato |
|---|---|
| src/crypto_carry/config.py | Tres opciones de investigación; validación explícita; las opciones apagadas no alteran la representación canónica ni el digest previo. |
| src/crypto_carry/execution.py | Referencia OHLC4 válida; clasificación de propósitos cliente/cierre/liquidación; metadatos de envío y elegibilidad. |
| src/crypto_carry/strategy.py | Ventana calculada desde elegibilidad, auditoría temporal y precio seleccionado; prioridad de liquidación reparada con aprobación expresa. |
| src/crypto_carry/reporting.py | Timestamps en nanosegundos, metadatos activos, unidades y convención declarada. |
| src/crypto_carry/data/prescribed.py | Declaración explícita de los supuestos de precio/demora del escenario. |

El diff exacto está en [extension_aplicada.patch](extension_aplicada.patch).
El código anterior y el ejecutado permanecen en sus respectivas carpetas del
paquete. El resto del motor no fue modificado. Las herramientas nuevas
`*execution_delays*.py` implementan preparación, ejecución por etapas, auditoría,
posprocesamiento, casos locales, verificación portable y preservación.

En el motor, los nuevos metadatos se conservan con el checkpoint. Generación es
la creación de la orden, coincidente con envío; no se usa esa etiqueta para
reescribir el timestamp de decisión. No cambia la cantidad al alcanzar
elegibilidad. No se alteran correction_deadline, holding, cooldown, reservas,
funding, margin calls, reglas de cantidades, participación ni fees BASE.

Única excepción económica preexistente aprobada: un intento que vence después
de escalar a liquidación mantiene la prioridad de liquidar el corto residual.
No vuelve a close_perp con demora cliente ni restaura HOLDING mediante una rama
de corrección/rebalanceo. El fill de una ventana ya comprometida mantiene su
propósito y cargos originales; el nuevo intento es liquidate. Sus controles
completos se ejecutan con identidades nuevas y conservan las BASE selladas.

Las mejoras posteriores a la congelación sólo afectan herramientas de auditoría,
informes y pruebas. El hash del motor y los archivos del runner permanecen
controlados antes y después de cada replay.

Ruff se ejecuta sobre `src scripts tests` con `pyproject.toml` explícito: pasa.
La exploración adicional de todo el árbol incluye snapshots históricos con
configuraciones locales de Ruff: 459 diagnósticos en archivos anteriores intactos
y una discrepancia de detección de imports en una copia congelada nueva. Esa
copia pasa al usar la configuración explícita del proyecto. No se reescriben
snapshots para satisfacer otro contexto de descubrimiento.

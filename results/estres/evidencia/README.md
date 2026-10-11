# B5: distribución documental del 10/10/2026

Esta distribución conserva la evidencia científica del paquete `paquete_20261001T211248Z`. Retira instrucciones al asistente, planes y estados de coordinación; su manifiesto tiene identidad propia. Las corridas, configuraciones, cifras, tablas, figuras, tolerancias y fuentes científicas permanecen idénticas a las autenticadas de origen.

- [Reporte](reporte.md) y [versión HTML](reporte.html).
- [Síntesis histórica](sintesis.md) e [índice de corridas](indice_corridas.json).
- [Protocolo científico congelado](protocolo_ejecucion.json).
- [Protocolo técnico y alcance de la distribución](protocolo_distribucion.md).
- [Procedencia y diferencias documentales](procedencia/derivacion.json).
- [Manifiesto original conservado](procedencia/manifiesto_original.json).

Los certificados y estados incluidos de origen mantienen su fecha y alcance: no acreditan por anticipado esta distribución. La nueva verificación identifica el SHA-256 del nuevo manifiesto y se guarda fuera del paquete. La adaptación del verificador sólo trata omisiones documentales explícitas; preserva íntegros los controles económicos y científicos.

## Verificación portable

Con Python compatible y las versiones fijadas en `herramientas/pyproject.toml` y `herramientas/uv.lock`, desde la raíz de esta distribución:

```powershell
python -B -I -X utf8 herramientas/scripts/verify_stress_counterfactual.py . --output ../verificacion_b5_distribucion.json
```

La comprobación utiliza las herramientas y fuentes compactas incluidas; no requiere Git, red ni `D:/Backtesting`. No ejecuta backtests. Recalcula los análisis a partir de la evidencia persistida, con los límites sobre fuentes masivas y lógica compartida descritos en el protocolo.

La ficha y el protocolo de etapa A conservan sus referencias históricas a aprobación pendiente. La aprobación efectiva permanece en [aprobacion_recibida.json](aprobacion_recibida.json); los posteriores estados de B6 y documento final se consultan en el índice actual de Entrega 4. [Reproducibilidad](reproducibilidad.md) describe el alcance científico y los comandos históricos de ejecución; las instrucciones de backtest allí conservadas no forman parte de esta comprobación compacta.

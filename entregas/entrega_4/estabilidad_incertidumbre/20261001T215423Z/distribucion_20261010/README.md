# B6: distribución documental del 10/10/2026

Esta distribución conserva la evidencia científica del paquete `paquete_final_verificado`. Retira instrucciones al asistente, planes y estados de coordinación; su manifiesto tiene identidad propia. Las corridas, configuraciones, cifras, tablas, figuras, tolerancias y fuentes científicas permanecen idénticas a las autenticadas de origen.

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
python -B -I -X utf8 herramientas/scripts/verify_stability_uncertainty.py --candidate . --output ../verificacion_b6_distribucion.json
```

La comprobación utiliza las herramientas y fuentes compactas incluidas; no requiere Git, red ni `D:/Backtesting`. No ejecuta backtests. Recalcula los análisis a partir de la evidencia persistida, con los límites sobre fuentes masivas y lógica compartida descritos en el protocolo.

## Estado histórico B6 y documento final

Las menciones a revisión transversal y Word/PDF pendientes en `sintesis.md`, `fuentes/sintesis_estado.json` y `matriz_cumplimiento.csv` corresponden al cierre histórico B6. Se conservan como evidencia reproducible, sin describir el estado actual del documento.

El PDF final está en `entregas/entrega_4/documento_final/Tesina_Entregas_3_y_4_Pablo_Salerno.pdf` dentro del repositorio. SHA-256: `f98df37bee61164948e2b26537c6aadebf77335aa60b37ceace27ffa029ea3fb`. El PDF queda fuera de este paquete compacto y de la verificación B6 histórica; su presencia no transforma aquellos controles en una revisión del documento final ni en constancia de publicación.

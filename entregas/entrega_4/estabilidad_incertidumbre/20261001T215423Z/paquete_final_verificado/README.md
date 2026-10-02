# B6: estabilidad temporal e incertidumbre

Este candidato mantiene cuatro cuentas nuevas I2023/I2024 y evidencia compacta de BASE continua.
El reporte distingue cuentas nuevas y tramos heredados; los inicios alternativos no son fuera de muestra.

- [Reporte](reporte.md) y [versión HTML](reporte.html).
- [Síntesis](sintesis.md), [cumplimiento](matriz_cumplimiento.csv) y [corridas](indice_corridas.json).
- [Protocolo previo](protocolo_ejecucion.json) y [encargo autorizado](fuentes/encargo_b6.md).
- [Recursos y tiempos](controles/recursos_y_tiempos.json).
- La certificación final independiente se escribe en `../controles_finales_corregidos/verificacion_offline.json`.

No se repitieron BASE ni B1-B5; no se ejecutó el motor en el bootstrap. Las 28/14/56 jornadas,
5.000 réplicas, semilla y estratificación anual son decisiones del estudio autorizadas en el encargo.
El paquete conserva los bytes de entradas compactas y el código compartido del cálculo/verificación.
Las particiones masivas de mercado y archivos de descarga quedan identificados en el inventario;
no se vuelven a leer offline. Se incluyen las ventanas mínimas necesarias para auditar fills.

Verificación autónoma con el intérprete fijado del proyecto (Python 3.14, versiones de `uv.lock`),
desde cualquier directorio, sin red ni D:/Backtesting:

```powershell
& 'C:/Users/pablo/Documentos/UCEMA/Tesina/Backtesting/.venv/Scripts/python.exe' -B -I -X utf8 '<paquete>/herramientas/scripts/verify_stability_uncertainty.py' --candidate '<paquete>' --output '<ruta externa>/verificacion.json'
```

El sello cubre cada archivo incluido. La verificación externa queda fuera del propio sello para no
crear una dependencia circular ni sobrescribirlo. Su JSON identifica el SHA-256 del manifiesto.
No se modificó el índice de Git ni se publicó el trabajo. Revisión transversal y Word/PDF pendientes.

La exportación corregida conserva `uv.lock` en ambos snapshots de código. El intento anterior, que falló antes del recálculo offline, permanece intacto y no vigente. El diagnóstico y la identidad de sus resultados están en `controles/reparacion_exportacion/diagnostico.json`.

# Distribución documental B2 — 2026-10-10

Derivada de `paquete_20260927T185305Z`. Esta distribución tiene manifiesto propio;
preserva ciencia, configuraciones, fuentes y resultados, y omite instrucciones
operativas de la conversación. No corresponde a una ejecución económica nueva.

[Protocolo descriptivo](protocolo_distribucion.md) ·
[Inventario de derivación](procedencia/derivacion.json) ·
[Manifiesto histórico de procedencia](procedencia/manifiesto_original.json)

El manifiesto histórico no verifica el nuevo paquete: la verificación actual
usa `manifiesto_paquete.json` más los controles científicos originales y
comprueba identidad de todos los miembros retenidos. Los registros y pendientes
del reporte/README histórico que sigue se refieren a su fecha, no al estado
global actual de E4. Las referencias a documentos retirados en registros
congelados son trazabilidad histórica, no instrucciones operativas vigentes.

Los comandos siguientes funcionan desde la distribución o desde una copia
limpia, con las dependencias del lock incluido y salida nueva fuera del sello.
El modo compacto usa sólo evidencia incluida, sin Git, red ni datos masivos.

---

# Bloque 2: evidencia de señal y entradas

Abrir [reporte.html](reporte.html) o [reporte.md](reporte.md). Doce nuevas simulaciones y dos BASE reutilizadas. Sin cambios del motor, referencias ni índice Git.

## Verificación portable offline

Con Python 3.14 y dependencias del lock incluido, ejecutar desde cualquier directorio:

```powershell
python -B -X utf8 <paquete>/herramientas/scripts/verify_signal_sensitivity.py --package <paquete> --output <auditoria_nueva.json>
python -B -X utf8 <paquete>/herramientas/scripts/verify_signal_sensitivity.py --package <paquete> --data-root <datos_locales> --output <auditoria_completa_nueva.json>
```

La salida es opcional, nueva y externa al paquete/datos. No se usa Git, HEAD, índice, red ni sesiones previas. El código incluido se carga antes que cualquier instalación editable. El modo compacto verifica sellos, configuración cerrada, fuentes incluidas, contabilidad diaria/período, exposición/ciclos/decisiones, H1 desde tasas/señales, H2 y H3 desde grupos con conteos/sumas, y datos de figuras. Con --data-root autentica inputs y reconstruye H3 desde velas locales. Los ficheros masivos no están duplicados en el paquete.

Las fuentes exactas incluidas se autentican contra los manifiestos originales; archivos de esos manifiestos que no se incluyen no se presentan como recalculados. Imágenes sólo se autentican por hash; sus tablas se verifican numéricamente. Hay lógica compartida con el constructor; H2 tiene además el validador independiente corregido. No es verificación independiente de todo el motor ni un replay económico.

Si un período heredara patrimonio no positivo, las métricas no definidas conservan ND y su motivo. `tablas/semantica_metricas.csv` documenta diferencias con los valores archivados del writer original, que permanecen intactos.

## Identidad y alcance

`evidencia/<run_id>` contiene un subconjunto exacto de las salidas originales. `fuentes/archivos_originales.csv` identifica cada transferencia binaria. `documentos/input_hashes.json` enlaza fuentes locales; `dependencias.json` enlaza los cinco paquetes anteriores sin duplicarlos. `herramientas` congela código económico y posprocesamiento; `codigo_referencia` conserva el código original de BASE. Las tasas consumidas de H1 están incluidas; los minutos H3 completos requieren datos locales.

`tablas/decisiones.parquet` conserva todas las celdas como texto exacto y usa compresión sin pérdida, para evitar un CSV repetitivo de más de 100 MiB. Puede leerse con `pyarrow.parquet.read_table`; no redondea decimales ni timestamps. Las métricas, grupos y demás tablas de lectura directa permanecen en CSV UTF-8. Los logs originales conservan sus bytes y, cuando corresponde, su BOM UTF-16.

Los comandos realmente ejecutados, tiempos, códigos de salida y registros de avance están en `ejecucion/etapa_H.json`, `etapa_V.json`, `etapa_B.json` y sus logs. El control de cada etapa autentica el protocolo congelado antes de continuar. La prueba global histórica de limpieza tiene una incompatibilidad de hash preexistente documentada en `documentos/control_historico_general.json`; no invalida por sí sola las fuentes de BASE ni acredita una validación integral del motor actual.

Los controles del candidato previos al sello se incluyen en `pruebas/`, con sus alcances y resultados reales. Las auditorías finales del paquete sellado, preservación y exportación binaria se guardan fuera del sello, en la carpeta de trabajo que lo contiene. No hay publicación Git realizada. En la fecha del paquete histórico no se generó PDF final.

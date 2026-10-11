# Reglas históricas: primera sensibilidad técnica preliminar

Avance acotado para Entrega 4, pendiente de comentarios del profesor. La comparación conserva la referencia presentada de Entrega 3 y separa evidencia histórica, supuestos experimentales y trayectorias ejecutadas. El estado individual y el `run_id` de cada cartera están en [indice_corridas.json](indice_corridas.json). Este trabajo permanece local, sin commit ni push.

La tanda terminó con diez trayectorias nuevas y dos BASE reutilizadas verificadas: doce resultados completos, sin insolvencias ni liquidaciones, 96 períodos y 20.448 conciliaciones diarias. H1 permanece invariante. Ninguna variante cambia la lectura descriptiva no favorable de H2 ni la contraria de H3. Las variantes DECISION aumentan el saldo condicional frente a sus REALIZADA, pero reducen su Sharpe; duplicar mantenimiento reduce los saldos de ambas carteras. Las cifras, comparadores y `run_id` están en el [reporte](comparacion/reporte.md), [métricas](comparacion/metricas_cartera_periodo.csv), [H2](comparacion/h2.csv) y [H3](comparacion/h3_regimen.csv).

## Lectura de la entrega

- [Reporte comparativo](comparacion/reporte.md): métricas, componentes, riesgo, H1/H2/H3 y deltas contra el comparador fijado. Los CSV conservan los valores sin redondear y las figuras muestran las trayectorias completas.
- [Protocolo previo](documentos/protocolo.md) y [sello previo](protocolo_previo.json): seis configuraciones, cinco variantes sin cruces automáticos, dos carteras independientes por configuración. El protocolo se fijó antes de observar resultados nuevos.
- [Matriz de integración](documentos/matriz_integracion.csv) y [decisiones](documentos/decisiones_integracion.md): traducción de los 345 hechos, con estados documentales y supuestos pendientes.
- [Diagnóstico de exposición histórica](diagnostico_historico/README.md): órdenes, posiciones, filtros y tablas de margen evaluados sobre BASE_E3; no representa una segunda tanda de backtests.
- [Cobertura pendiente](cobertura_pendiente.md): fechas, semántica de reglas y cohortes todavía sin acreditar, con `fact_id`/`source_id`.
- [Verificaciones ejecutadas](verificaciones.md), [resumen de cambios](cambios.md), [diff de código](cambios_codigo.patch) e [inventario exacto de archivos](archivos_nuevos_modificados.csv).
- [Guía de lectura de métricas](documentos/lectura_resultados.md), [verificación de publicación](documentos/verificacion_publicacion.md) y [reproducción de las corridas](documentos/reproduccion.md).

## Qué se preserva y qué se amplía

La investigación original está reproducida íntegramente bajo [evidencia_historica/](evidencia_historica/), junto con sus dependencias externas A1–A3. Incluye [registro](evidencia_historica/data/research/historical-rules-followup-20260924T234206Z/reglas_historicas.json), [fuentes](evidencia_historica/data/research/historical-rules-followup-20260924T234206Z/fuentes.json), extracciones y archivos recuperados. Sus fechas y hashes no se reemiten. No se agregaron fuentes externas en este encargo.

El verificador de publicación nuevo separa integridad documental, procedencia Git y auditoría archivada de la sesión original. Reutiliza las comprobaciones documentales del verificador sellado sin invocar su `main()`. La [reproducción del problema](verificacion_publicacion/reproduccion_copia_preservada_resumen.json) ocurrió en una copia temporal; el resultado histórico del repositorio no fue sobrescrito. Una exportación sin Git informa procedencia Git no comprobada.

La [auditoría previa de BASE_E3](verificacion_base_previa.json) contrasta código, configuración, dependencias, datos y salidas originales. La [regresión con extensión apagada](comparacion_extension_apagada_final.json) compara exactamente los registros económicos de una ventana real antes y después de la extensión, usando la versión final congelada. La implementación agrega dos opciones de investigación, separa tarifa realizada de costo de decisión y permite una carpeta de salida explícita; mantiene los valores predeterminados y la serialización de las configuraciones anteriores.

La promoción BTC spot usa únicamente el intervalo respaldado por `BTC_SPOT_ZERO`, fuentes `PROMO_START`/`PROMO_END`. Fuera de él, 10 pb spot sigue siendo un supuesto. FUT4 es un contrafactual constante; no identifica la fecha histórica del cambio de 4 a 5 pb. MARGEN_2X es estrés del importe de mantenimiento y conserva el apalancamiento inicial 2x. El [registro y las fuentes](cobertura_pendiente.md) conservan esas diferencias.

## Organización y procedencia técnica

| Carpeta o archivo | Contenido |
| --- | --- |
| `corridas/run_*` | Salidas completas de cada cartera: manifiesto, configuración efectiva, Parquet, CSV, gráficos y convenciones |
| `ejecuciones/`, `logs_corridas/`, `logs_reanudacion/`, `indice_corridas.json` | Comandos, estados, tiempos y códigos de salida de las variantes |
| `registro_interrupcion/` | Índice preservado y huellas de logs del intento interrumpido; recuperación de las cuatro salidas faltantes |
| `h3_minutos/`, `h3_procedencia.json` | Conteos y suma Decimal por activo/día; procedencia explícita de la reconstrucción de BASE |
| `comparacion/` | Tablas derivadas, conciliaciones y reporte reproducible |
| `codigo_base/` | Código aplicable a la referencia, contrastado con sus manifiestos |
| `codigo_ejecutado/` | Código, runner, configuraciones y protocolo congelados para la tanda |
| `herramientas/` | Constructor, verificadores, diagnóstico y utilidad de reproducción |
| `verificacion_publicacion/`, `verificaciones_finales/` | Resultados y logs reales de aceptación |

`corridas/` cumple la función de una carpeta nueva de `outputs/` y queda dentro de esta entrega para permitir su traslado íntegro. Los datos masivos se leen del árbol local `D:/Backtesting`, con la capa `data/minutes/2022_2026_continuous/derived_marks/futures_scaled`; no se copian por variante. Los dos BASE originales permanecen en `D:/Backtesting/outputs/` y sus copias se verifican por bytes.

Los manifiestos originales conservan la raíz y el contexto en que fueron creados. Los manifiestos nuevos identifican el código efectivamente ejecutado. La portabilidad de la verificación del informe no implica que se incluyan los datos masivos necesarios para simular de nuevo. La marca de rehash final en cada registro de proceso refleja su estado al terminar ese proceso; la auditoría posterior del lote queda en un archivo independiente, sin reescribir registros previos.

La [auditoría final de datos](verificacion_final_datos.json), el [control de preservación](preservacion_final.json) y la [auditoría independiente de fills](verificaciones_finales/auditoria_fills.json) conservan sus alcances separados. Los enlaces de una copia documental se adaptaron para lectura desde otra ruta; [este registro](documentos/adaptaciones_portables.json) identifica los seis destinos cambiados y conserva los hashes del documento fuente y la copia portable.

Una revisión posterior a las doce corridas corrigió el lanzador para conservar también trayectorias terminadas como insolventes. Ninguna cartera de esta tanda alcanzó ese estado. El runner realmente ejecutado permanece intacto en `codigo_ejecutado/`; el helper corregido está en `herramientas/` y se autentica antes de usarlo en reproducciones futuras. La [resolución y sus pruebas](verificaciones_finales/runner_insolvencia_resolucion.json) documentan ambas versiones; no se reescriben los manifiestos económicos anteriores.

Una interrupción de la sesión cerró los procesos cuando había seis variantes con artefactos completos, además de las dos BASE verificadas. Cuatro intentos no habían terminado de persistir sus salidas. Se conservaron todos sus logs y se volvió a comprobar datos, versiones y originales antes de ejecutar sólo esos cuatro pares. La [auditoría previa a la recuperación](verificaciones_finales/datos_antes_reanudacion.json) y el [registro de recuperación](registro_interrupcion/reanudacion_inicio.json) documentan esa distinción. Los avances parciales interrumpidos no se utilizan como resultados económicos ni como períodos sin operaciones.

## Comandos

Verificación del paquete terminado desde cualquier ruta, sin motor, Git, red ni dependencias instaladas:

```powershell
python -I -S -B <paquete>/herramientas/verify_rules_sensitivity_package.py --package <paquete>
```

Verificación documental de las fuentes incluidas:

```powershell
python -I -S -B <paquete>/herramientas/verify_historical_rules_publication.py `
  --root <paquete>/evidencia_historica `
  --evidence <paquete>/evidencia_historica/data/research/historical-rules-followup-20260924T234206Z `
  --temp-dir $env:TEMP
```

Para reproducir las trayectorias se necesita el entorno exacto y los datos externos. Desde la raíz del proyecto, elegir un destino todavía inexistente:

```powershell
.venv/Scripts/python.exe -B -X utf8 scripts/reproduce_historical_rules_sensitivity.py `
  --source-package entregas/entrega_4/reglas_historicas/20260925T005436Z `
  --destination D:/Backtesting/outputs/E4_reglas_reproduccion_nueva `
  --data-root D:/Backtesting --workers 2
```

Agregar `--prepare-only` comprueba las dependencias y prepara otra carpeta nueva sin ejecutar backtests. Los pasos y límites están en la guía de reproducción. Las corridas reproducidas y un segundo paquete editorial tienen estados distintos; la utilidad no sella automáticamente un informe nuevo.

La primera tanda es exploratoria sobre historia observada. Las limitaciones de `futures_scaled`, marcas/funding y ejecución de minuto siguen vigentes. No se ejecutó la segunda tanda propuesta, no se certifica una cronología completa y los controles de hashes no sustituyen una validación independiente de todo el motor.

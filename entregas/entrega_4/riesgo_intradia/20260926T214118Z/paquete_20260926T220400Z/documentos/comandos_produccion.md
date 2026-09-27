# Comandos y resultados de producción

Las rutas se expresan con variables para facilitar la lectura. Estos comandos identifican las operaciones ejecutadas; los registros JSON indicados conservan los argumentos, rutas y tiempos cuando los emite cada herramienta. Los destinos ya producidos no se deben reutilizar después del sello.

```powershell
$repo = 'C:/Users/pablo/Documentos/UCEMA/Tesina/Backtesting'
$py = "$repo/.venv/Scripts/python.exe"
$entrega = "$repo/entregas/entrega_4/riesgo_intradia/20260926T214118Z"
$paquete = "$entrega/paquete_20260926T220400Z"
$padre = "$repo/entregas/entrega_4/reglas_historicas/20260925T005436Z"
$correccion = "$repo/entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z"
$series = 'D:/Backtesting/outputs/riesgo_intradia_20260926T214118Z/completa'
$datos = 'D:/Backtesting'
```

## Entradas comprobadas

| Herramienta y argumentos | Resultado ejecutado | Registro |
| --- | --- | --- |
| `$padre/herramientas/verify_rules_sensitivity_package.py --package $padre` | Aprobado: 12 corridas, 564 artefactos, 20.448 cierres diarios, 96 períodos y 456 hashes de snapshots | `verificaciones_entradas/verificacion_padre_inicial.log` |
| `$correccion/herramientas/verify_rules_sensitivity_correction.py --package $correccion --parent $padre` | Aprobado: paquete de corrección y padre autenticados | `verificaciones_entradas/verificacion_correccion_inicial.json` |
| `Paquete de evidencia/verificar.py` | Aprobado, sin regenerar evidencia | `verificaciones_entradas/verificacion_e3_inicial.log` |
| `python -m scripts.publish_thesis --verify` | Aprobado; sólo se utilizó la modalidad de verificación | `verificaciones_entradas/verificacion_publicacion_e3_inicial.log` |
| `auditoria_precios/auditar_precios.py --package $padre --data-root $datos` | 344 particiones autenticadas, 27.264 precios diarios exactos; repetido desde otra ruta | `../auditoria_precios/resultado_auditoria_precios.json` y `resultado_desde_otra_ruta.json` |
| `auditoria_contable/auditar_cuentas.py` | 6.816 cierres de cuentas Decimal exactos y 128 fuentes preservadas | `../auditoria_contable/resultados.json`, cuyo registro documenta interfaz y alcance |

## Reconstrucción y tablas

Se probó primero el 23–25/03/2023 mediante el mismo constructor con `--start 2023-03-23T00:00:00Z --end 2023-03-26T00:00:00Z` y destinos piloto nuevos. Pasaron doce cierres; el bloque integrado duró 3,4989282 segundos. El benchmark y el log piloto están archivados en esta carpeta.

Comando de la reconstrucción completa, ejecutado desde la raíz del repositorio:

```powershell
& $py -B -u -X utf8 -m scripts.build_intraday_risk --parent $padre --output $paquete --series-root $series --data-root $datos
```

Resultado: exit 0, 9.851.104 observaciones, 224 particiones, 2.934.571.231 bytes y 237,0683603 segundos. Todos los 6.816 cierres concilian a la tolerancia original. Se conservan `../reconstruccion.json`, `../series_locales.json`, `reconstruccion_completa.log` y el código exacto ejecutado.

Agregación ejecutada sobre esas particiones:

```powershell
& $py -B -X utf8 -m scripts.intraday_risk_tables --package $paquete --series-root $series --parent $padre --correction $correccion
```

La primera exportación detectó un tipo Arrow `null` en un bloque vacío; no se descartó el error. Una prueba lo reprodujo y se fijó un esquema explícito. La revisión posterior corrigió los extremos de exposición. La regeneración final terminó con exit 0 (`tablas_revision_final.log`): 449 episodios, 128 comparaciones de DD, 6.816 días de riesgo y 13.632 filas diarias de margen por activo. H1/H2/H3 se copiaron como bytes originales.

Generación del reporte y figuras:

```powershell
& $py -B -X utf8 "$repo/scripts/intraday_risk_report.py" --package $paquete --series-root $series
```

`../generacion_reporte.json` conserva la última ejecución y sus hashes de entrada. `../revision_presentacion.json` registra las 13 figuras inspeccionadas, 69 enlaces válidos y las cuatro ventanas de garantías completas. La última corrección fue de cobertura visual; las tablas conservaron sus hashes.

## Pruebas y cierre

La ejecución general registrada en `../registros_pruebas/pytest_final.json` aprobó 859 pruebas. `ruff_final.json` registra Ruff sin observaciones sobre `src`, `scripts` y `tests`. Los logs RED/GREEN preservan los problemas reproducidos y sus correcciones; no se reinterpretan como ejecuciones aprobadas.

La anotación adicional de calidad de precios conserva su propio comando, procedencia y pruebas. Los controles posteriores a esa anotación se registran por separado en la carpeta de ejecución.

El cierre se ejecuta con `ejecutar_cierre.py`, fuera del paquete. Primero copia sólo el paquete compacto a una carpeta temporal, ejecuta las pruebas portables y la verificación compacta/completa sin `-B`, autentica las fuentes y comprueba que las entradas no cambien. Sólo si los bytes siguen coincidiendo se traslada el mismo manifiesto a la carpeta original. La verificación completa no ejecuta el motor económico. Sus resultados, salidas y códigos de retorno quedan fuera del sello, vinculados al SHA-256 del manifiesto verificado.

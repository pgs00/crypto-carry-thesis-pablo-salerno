# Retorno y capital: paquete local verificable

Distribución documental `20261010`. Consultar el reporte y las tablas indicados abajo. [Protocolo y procedencia de esta distribución](protocolo_distribucion.md). Los controles históricos incluidos no constituyen una verificación de esta nueva distribución.


Leer [reporte HTML](reporte.html), [reporte Markdown](reporte.md),
[protocolo](documentos/protocolo.md) y [ficha del benchmark](documentos/ficha_benchmark.json).
Concentración, restricciones e integración: ejecutado. Benchmark remunerado:
pendiente_aprobacion_benchmark. No se calcularon sus retornos ni se generó PDF final.

## Verificación portable

Python 3.14, PyArrow, NumPy y Matplotlib del entorno del proyecto. Desde cualquier
directorio, sin Git, HEAD, índice, motor, red ni datos masivos de mercado:

```powershell
& <python> -B -X utf8 <paquete>/herramientas/scripts/verify_return_capital.py --package <paquete>
& <python> -B -X utf8 <paquete>/herramientas/scripts/verify_return_capital.py --package <paquete> --parent <padre> --correction <correccion> --intraday <intradia_compacto> --e3 <evidencia_E3> --output <resultado_nuevo_externo.json>
```

La modalidad compacta verifica miembros, identidades algebraicas, fronteras,
atribuciones, clasificaciones y denominadores internos. La completa exige las
cuatro dependencias y comprueba sus fuentes contra los hashes fijados, vuelve
a derivar las tablas y conserva la identidad de ciclos E3. Comparte módulos de
posprocesamiento; no constituye una implementación independiente del motor.
No recalcula extremos intradía ni valida toda la historia de precios masiva.

`fuentes.json` e `inventario_fuentes.csv` enumeran los archivos indispensables.
Padre: manifiestos y archivos de las dos BASE. Corrección: tablas financieras,
exposición y H1/H2/H3. Intradía: manifiesto y precios de eventos financieros
exportados. E3: manifiesto, ciclos y código archivado de referencia. No se
copian las carteras ni millones de observaciones. El paquete sí incluye CSV
nuevos y subconjuntos BASE intactos, código/pruebas y originales públicos.

## Pruebas y reproducción

Para los fixtures pequeños, desde `<paquete>/herramientas`:

```powershell
& <python> -B -m pytest -p no:cacheprovider tests/unit
```

Las pruebas históricas requieren `RETURN_CAPITAL_PARENT`,
`RETURN_CAPITAL_CORRECTION` y `RETURN_CAPITAL_INTRADAY` con rutas explícitas;
sin ellas se declaran omitidas si no existen las rutas predeterminadas del
checkout. Una prueba omitida no certifica los resultados históricos.

Constructor (siempre destino inexistente, fuera de todas las entradas):

```powershell
& <python> -B -X utf8 <paquete>/herramientas/scripts/build_return_capital.py --output <destino_nuevo> --parent <padre> --correction <correccion> --intraday <intradia_compacto> --e3 <evidencia_E3> --documents <paquete>/documentos --research <paquete>/fuentes_publicas --tests-root <paquete>/herramientas/tests/unit
```

Las auditorías finales son externas al paquete y nombran el SHA-256 verificado.
El constructor rechaza sobrescritura; el verificador rechaza salida existente
o dentro de fuentes. Ningún comando importa crypto_carry ni ejecuta backtests.
Los comandos de construcción no realizan operaciones de Git.

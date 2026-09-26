# Corrección de exposición y H2 — entrega terminada el 26/09/2026

Se corrigió exclusivamente el posprocesamiento de las doce carteras existentes.
El reporte sigue siendo técnico preliminar, pendiente del feedback del profesor.
El trabajo comenzó el 25/09 y se completó el 26/09; la carpeta del producto y sus
manifiestos registran la fecha real de construcción.

## Productos

- [Reporte corregido](paquete_20260926T204312Z/comparacion/reporte.md).
- [Comparación antes/después: 96 filas](paquete_20260926T204312Z/comparacion/antes_despues.csv).
- [Exposición por período: 288 filas](paquete_20260926T204312Z/comparacion/exposicion_periodo.csv)
  e [intervalos auditables: 45.803 filas](paquete_20260926T204312Z/comparacion/exposicion_intervalos.csv).
- [H2 completo: 48 pares](paquete_20260926T204312Z/comparacion/h2.csv)
  y [cambios de veredicto](paquete_20260926T204312Z/comparacion/h2_cambios.csv).
- [Guía de métricas](paquete_20260926T204312Z/documentos/guia_metricas.md),
  [constructor/verificación y dependencias](paquete_20260926T204312Z/README.md),
  [procedencia](paquete_20260926T204312Z/procedencia.json) y
  [manifiesto nuevo](paquete_20260926T204312Z/manifiesto_paquete.json).

El producto contiene 59 archivos y 31.677.318 bytes, incluido el sello. No copia
las corridas grandes: requiere el padre `20260925T005436Z` íntegro por argumento.
El subconjunto E3 incluido autentica las tablas y el código editorial utilizados;
no se presenta como copia completa de E3.

## Resultados comprobados

La causa de exposición fue usar cantidades del ledger sin los estados persistidos
necesarios para distinguir polvo. Ahora se clasifica la trayectoria completa de
posiciones según E3, conservando el último estado persistido de cada timestamp y
la memoria de residuos antes de recortar períodos. La cartera integra uniones,
sin sumar dos veces posiciones simultáneas.

| BASE, muestra completa | Condicional | Permanente |
| --- | ---: | ---: |
| Tiempo invertido bruto previo, % | 77,797217331768… | 99,823862154408… |
| Tiempo activo comparable con E3, % | 28,317846896192… | 98,208341484090… |
| Tiempo activo, segundos exactos | 41.691.120 | 144.587.820 |
| Exposición activa sin cobertura, segundos | 11.340 | 16.440 |
| Sólo polvo, sin otro activo en posición, segundos | 72.846.300 | 2.378.460 |

Las fracciones exactas se expresan como segundos / 147.225.600. La comprobación
contra E3 tuvo cero diferencias en 3.710 intervalos condicionales, 3.913 permanentes
y 18 resúmenes. No hay discrepancia de nanosegundo terminal con el final exclusivo
correcto. Los 121 minutos del 24/03/2023 se conservan en los activos afectados y
en ambas uniones de cartera. Las otras diez carteras se clasificaron por sus
propias trayectorias; sus resultados figuran en el CSV comparativo.

H2 exige simultáneamente CAGR condicional finito y positivo y Sharpe condicional
finito superior al permanente, también finito, con ventana y cobertura comparables.
Resultado real: **43 no_favorable, 5 no_concluyente y cero cambios de veredicto**.
Se conservan booleanos desconocidos y motivos; no se exige Sharpe positivo ni
CAGR superior al permanente.

Se preservaron exactamente 5.568 celdas no afectadas de los 96 registros
cartera/período, más las once tablas financieras/H1/H3/eventos y el índice de
corridas en bytes. El polvo sigue valuado en equity y P&L. No cambian retornos,
CAGR, Sharpe, drawdown, utilización diaria, resultados financieros, H1 ni H3.

## Verificaciones ejecutadas

- [Suite completa final](controles/suite_completa_final.log): **751 pruebas aprobadas**.
- [Ruff](controles/ruff_final.log): sin errores en los scripts y pruebas de la corrección.
- [Verificación final v2](verificacion_final.json): pase; 12 corridas, 45.803 intervalos,
  288 resúmenes, 48 H2, 96 registros financieros y 1.089 archivos fuente.
- [Traslado y corrupción](portabilidad_corrupciones.json): se copiaron temporalmente
  la corrección y el padre a otra raíz, sin Git; el verificador empaquetado pasó.
  Ocho corrupciones deliberadas de límite, clase, duración de intervalo, duración
  agregada, condición H2, cifra comparativa, datos de figura y valor financiero
  fueron detectadas después de recalcular los sellos de prueba. Los temporales
  de esa auditoría se eliminaron; los manifiestos originales no cambiaron.
- [Publicación E3](controles/e3_publicacion_alcance_correcto.log): pase, 11 tablas,
  3.408 filas diarias y seis figuras; ZIP original sin cambios.
- [Paquete E3 original](controles/e3_paquete_original.log),
  [archivo E3 original](controles/e3_archivo_dependencias_correctas.log),
  [padre original](controles/padre_original.log) y
  [evidencia histórica incluida](controles/fuentes_historicas_ruta_correcta.log): pases
  con sus herramientas y alcances respectivos. El control del padre recalcula
  20.448 conciliaciones diarias y 96 por período; no acredita por sí solo v2.
- [Preservación final](preservacion_final.json): 2.033 archivos iniciales contrastados,
  2.029 idénticos y sólo cuatro archivos activos autorizados modificados.
  Permanecen iguales los 36 archivos del motor, 12 configuraciones, 294 archivos
  de E3 y 1.089 del padre. HEAD, rama e índice físico de Git son idénticos.
- [Revisión independiente](revision_independiente.md),
  [linaje exacto](auditoria_linaje/linaje_exposicion.md),
  [producto final y enlaces](revision_producto_final.json) y
  [entorno](entorno_verificacion.json).

Los [comandos exactos y códigos de salida](COMANDOS_Y_VERIFICACIONES.md) incluyen
también fallos esperados de las fases RED y los intentos corregidos. No se suman
pruebas repetidas para inflar el conteo final.

## Control histórico fuera de alcance y cobertura pendiente

`scripts.verify_repository_evidence` continúa fallando en el inventario antiguo
de limpieza: esperaba otro hash de `src/crypto_carry/config.py`. Se comprobó que
el hash actual es idéntico al inventario inicial de esta tarea. No se modificó
ese archivo ni se reescribió el inventario antiguo para forzar el pase. El
[diagnóstico](control_historico_alcance.json) distingue ese alcance histórico de
los controles específicos de publicación E3 y de paquetes, que sí pasaron.

Dos intentos iniciales se corrigieron: el argumento TEMP se había pasado como
literal y el verificador del antiguo archivo E3 se había invocado con `-S`, que
ocultaba Pillow. Los comandos corregidos pasan; no son bloqueos pendientes.

No quedan faltantes de metadatos para clasificar estas doce carteras. La cobertura
histórica parcial de reglas Binance continúa siendo una limitación del padre;
esta corrección no incorpora fuentes ni completa fechas desconocidas. El inventario
de preservación acredita los archivos locales del repositorio, no un PDF externo
que no forma parte del árbol inspeccionado. No se generó ni editó ningún PDF.

## Repetir la verificación desde otra ruta

Con Python 3.14 y PyArrow, rutas de corrección y padre explícitas:

```powershell
python -B -X utf8 <correccion>/herramientas/verify_rules_sensitivity_correction.py `
  --package <correccion> --parent <paquete_padre> --output <resultado_nuevo_externo.json>
```

Para regenerar sólo el reporte, elegir un destino inexistente y aportar la
referencia original E3; Matplotlib genera las figuras:

```powershell
python -B -X utf8 <correccion>/herramientas/correct_rules_sensitivity_report.py `
  --source-package <paquete_padre> --destination <destino_nuevo> `
  --e3-reference <carpeta_Paquete_de_evidencia>
```

La corrección local está sellada y verificada. No se ejecutaron backtests históricos,
descargas, commits, push ni cambios en el índice. Los casos sintéticos de la suite
no son resultados históricos. Los hashes del motor de las corridas siguen siendo
los originales; el posprocesador nuevo se identifica como `exposure_h2_v2`.

Manifiesto nuevo SHA-256:
`e735207869c08bbd0b9b04818c8855ecd9576bd979d3127b5ff108f61d3843ce`.

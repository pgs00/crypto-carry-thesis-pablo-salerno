# Distribución documental B4 — 2026-10-10

Derivada de `paquete_20260930T013915Z_v2`. Esta distribución tiene manifiesto propio;
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

Los comandos de verificación compacta funcionan desde la distribución o desde una copia
limpia, con las dependencias del lock incluido y salida nueva fuera del sello.
El modo compacto usa sólo evidencia incluida, sin Git, red ni datos masivos.

---

# Evidencia de ejecución y demoras

[Reporte](reporte.md) · [HTML](reporte.html) · [Síntesis](sintesis.md) · [Incidentes](incidentes.md)

Desde una copia limpia, offline y con Python y dependencias fijadas en
`herramientas/pyproject.toml` y `herramientas/uv.lock`:

```powershell
python -B -X utf8 herramientas/scripts/verify_execution_delays.py --package . --output ../auditoria_nueva.json
```

El destino es nuevo y externo. No necesita HEAD, índice Git ni la ruta del proyecto original.
Recalcula cierres/períodos, exposición, H2/H3, órdenes/fills/ledger, precios,
cronología, capacidad e incidentes desde los extractos incluidos. No hace replay.
H1 reutiliza una sola población BASE después de verificar proyecciones y targets.
Constructor y verificador comparten funciones; no constituyen motores independientes.

Para volver a autenticar y extraer las ventanas desde fuentes masivas locales,
agregar `--data-root D:/Backtesting`; ese control exige esos archivos.
El CSV forecast original está comprimido sin pérdida con tamaño y hash originales.
Las carteras completas permanecen en los destinos indicados por el índice.

Las suites de adulteración semántica incluidas conservan las pruebas y
mensajes esperados del paquete histórico original. Sus comandos corresponden
a aquel paquete, conservado en el respaldo externo, no a esta distribución.
La guardia adicional de preservación aquí rechaza primero cualquier byte
científico alterado, aun con hashes exteriores renovados; por ello el mensaje
puede anteceder al rechazo económico específico exigido por la suite original.
Las pruebas históricas permanecen intactas y no se declaran ejecutadas sobre
esta distribución. La verificación compacta vigente es el comando anterior.
Los controles actuales de integridad están en la suite viva del repositorio
`tests/unit/test_documentary_distribution.py` y en los certificados externos
identificados por el hash de cada distribución; incluyen omisión científica,
bytes cambiados y exclusiones arbitrarias con sellos renovados.

Los registros posteriores al sello, incluida la exportación binaria mediante
índice temporal aislado y la comprobación desde otra ruta, permanecen fuera
del paquete. No hay commit, push ni modificación del índice del usuario.

[Revision tecnica de esta version](documentos/revision_tecnica_paquete.md).

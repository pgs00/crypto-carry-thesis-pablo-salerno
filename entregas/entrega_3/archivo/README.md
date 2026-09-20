# Archivo histórico de la Entrega 3

Estos resultados corresponden a las **ventanas independientes**
01/09/2022–31/08/2023 y 01/09/2025–31/08/2026. Cada cartera comenzó cada ventana
con 10.000 USDT; no describen el período continuo vigente ni se concatenan con él.
Volver a la [entrega continua](../README.md).

| Evidencia | Alcance |
|---|---|
| [ZIP original](paquete_redaccion_entrega_3.zip) · [SHA-256](paquete_redaccion_entrega_3.zip.sha256) | Primera entrega, conservada como referencia de bytes y procedencia. |
| [ZIP v2](paquete_redaccion_entrega_3_v2.zip) · [SHA-256](paquete_redaccion_entrega_3_v2.zip.sha256) | Correcciones documentales y de preservación CRLF/LF; mismos parámetros y resultados. |
| [Paquete v2 consultable](paquete_redaccion/LEEME.md) | Sus 140 archivos coinciden con los miembros del ZIP v2. Se conserva por sus enlaces, fuentes y verificadores. |

Desde la raíz del repositorio, sin datos masivos ni nuevas simulaciones:

```powershell
& '.\.venv\Scripts\python.exe' entregas/entrega_3/archivo/paquete_redaccion/scripts/verificar_paquete.py
& '.\.venv\Scripts\python.exe' entregas/entrega_3/archivo/paquete_redaccion/scripts/reproducir.py --destino '.\.superpowers\entrega3_archivo_repro'
& '.\.venv\Scripts\python.exe' entregas/entrega_3/archivo/paquete_redaccion/scripts/diccionario.py --destino '.\.superpowers\entrega3_archivo_repro'
```

Los originales se movieron completos, sin cambiar sus manifiestos ni fuentes.
Las rutas de procedencia dentro de sus JSON describen la ubicación original al
capturarlos; no se sustituyen por rutas actuales para fabricar hashes nuevos.
Los comandos dentro de los documentos sellados registran las rutas usadas
entonces. Para verificar o regenerar sus tablas desde este checkout, usar los
comandos actualizados de arriba; no editar el paquete para cambiar ese registro.

El [preparador original](paquete_redaccion/scripts/preparar_paquete.py) es la copia
canónica del script antes duplicado en la raíz de Entrega 3. Para preparar otra
copia requiere las fuentes locales y un destino explícito nuevo; no debe usarse
para sobrescribir este archivo. [empaquetar.py](empaquetar.py) conserva la
comprobación de fuentes contra el ZIP original y rechaza sobrescribir un ZIP.

[completar_evidencia.py.txt](completar_evidencia.py.txt) y
[probar_portabilidad.py.txt](probar_portabilidad.py.txt) son snapshots byte a byte
de herramientas de preparación usadas entonces, no comandos vigentes. Se
conservan como texto porque modificaban el borrador del paquete.

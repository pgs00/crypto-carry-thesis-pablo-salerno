# Archivo histórico de la Entrega 3

Estos resultados corresponden a las **ventanas independientes**
01/09/2022–31/08/2023 y 01/09/2025–31/08/2026. Cada cartera comenzó cada ventana
con 10.000 USDT; no describen el período continuo vigente ni se concatenan con él.
Volver a la [entrega continua](../README.md).

| Evidencia | Alcance |
|---|---|
| [ZIP original](paquete_redaccion_entrega_3.zip) · [SHA-256](paquete_redaccion_entrega_3.zip.sha256) | Primera entrega, conservada como referencia de bytes y procedencia. |
| [ZIP v2](paquete_redaccion_entrega_3_v2.zip) · [SHA-256](paquete_redaccion_entrega_3_v2.zip.sha256) | Correcciones documentales y de preservación CRLF/LF; mismos parámetros y resultados. |
| Copia extraída v2 retirada | Sus 140 archivos se recuperan del ZIP v2 autenticado, sin alterar sus bytes. |

La [guía única de reproducción](../../../docs/reproduction.md#entrega-3-presentación-y-extracción-autenticada)
autentica y extrae los ZIP en carpetas externas nuevas, y publica el comando del
verificador incluido. El ZIP v2 contiene `paquete_redaccion/`; sus scripts
`verificar_paquete.py`, `reproducir.py` y `diccionario.py` se ejecutan desde esa
copia con destinos nuevos, sin datos masivos ni nuevas simulaciones para la
verificación y reproducción de tablas.

Los originales se movieron completos, sin cambiar sus manifiestos ni fuentes.
Las rutas de procedencia dentro de sus JSON describen la ubicación original al
capturarlos; no se sustituyen por rutas actuales para fabricar hashes nuevos.
Los comandos dentro de los documentos sellados registran las rutas usadas
entonces. Para verificar o regenerar sus tablas desde este checkout, usar la
guía de extracción anterior; no editar el paquete para cambiar ese registro.

El preparador original `paquete_redaccion/scripts/preparar_paquete.py`, incluido
en el ZIP v2, es la copia
canónica del script antes duplicado en la raíz de Entrega 3. Para preparar otra
copia requiere las fuentes locales y un destino explícito nuevo; no debe usarse
para sobrescribir este archivo. [empaquetar.py](empaquetar.py) conserva la
comprobación de fuentes contra el ZIP original y rechaza sobrescribir un ZIP.

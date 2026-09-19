# Paquete de redacción — Entrega 3

Preparado el 19/09/2026 para reunir implementación, metodología y resultados
preliminares. No es el informe académico maquetado ni la Entrega 4. Se utilizaron
corridas guardadas: no se cambió ningún parámetro ni se ejecutaron nuevos backtests.

## Orden de lectura

1. [Base factual breve](base_para_redaccion.md): seis secciones para redactar.
2. [Índice de integración](indice_integracion.md): Entrega 2 como base acumulativa,
   conservando Entrega 1 y una sola bibliografía.
3. [Cambios metodológicos](tablas/cambios_metodologicos.csv): diseño anterior,
   implementación utilizada, motivo, implicación y fuente.
4. [Resultados](tablas/resultados_principales.csv), [P&L](tablas/pnl_componentes.csv)
   y [hipótesis](tablas/hipotesis.csv); consultar las [dos figuras](figuras/notas_figuras.md).
5. [Verificación](verificacion.md), [fuentes de cifras](fuentes_de_cifras.csv),
   [diccionario](diccionario_campos.csv) y [convenciones](convenciones.md).

## Corridas y alcance

Principal: `vwap_joint` (`next_minute_vwap`, `joint_quantity`, `closed_minute`).
Reporte corregido: `revision_eb5ed744b30836a39fd694fa`, el último pertinente
identificado al preparar este paquete. Comparaciones económicas independientes:

| Ventana UTC, fin exclusivo | Corrida | Configuración efectiva |
|---|---|---|
| 2022-09-01 a 2023-09-01 | `run_f4151cc97937f3704d77fb14` | [TOML temprano](evidencia/corridas/run_f4151cc97937f3704d77fb14/effective_config.toml) |
| 2025-09-01 a 2026-09-01 | `run_519a165818e2cadce24bc873` | [TOML tardío](evidencia/corridas/run_519a165818e2cadce24bc873/effective_config.toml) |

Cada estrategia reinicia 10.000 USDT. No conectar ventanas ni interpretar la
permanente como inversión continua. Sus costos, sizing, ejecución, basis y riesgos
son compartidos; omite únicamente el filtro de funding de entrada y renovación.

## Inventario

| Ubicación | Contenido |
|---|---|
| `tablas/` | Resultados, P&L, hipótesis, actividad y rechazos, cambios metodológicos, auditoría de basis y episodio del 24/03/2023; cobertura de funding, parámetros y versiones. |
| `tablas/anexo_variantes_ejecucion.csv` | Veinte carteras de las variantes ya realizadas; antecedente técnico, no selección por rendimiento. |
| `datos/equity_diaria.csv` | 1.460 cierres diarios reales: 365 por cada cartera, con retornos y run_id. |
| `figuras/` | Sólo dos figuras principales; PNG a 300 dpi y SVG, con notas. |
| `antecedentes/` | DOCX y PDF originales de Entregas 1 y 2, copia byte por byte, bibliografía consolidada y párrafos fuente. |
| `evidencia/` | Reporte corregido y auditoría, tablas fuente, configuraciones y manifiestos de diez corridas; subconjunto numérico de las dos principales. |
| `evidencia/originales/` | Los dos informes originales conservados como TXT, sin alterar sus bytes. |
| `evidencia/procedencia/` | Especificaciones y documentación del proyecto preservadas como instantáneas de texto. |
| `evidencia/codigo/` | Código relevante para leer fórmulas y convenciones; no es un proyecto ejecutable completo. |
| `scripts/` | Reproducción de tablas/figuras/diccionario, verificador y snapshot de preparación. |
| `fuentes_originales.json` | Origen, hash y tamaño de cada archivo copiado; incluye resultado de la verificación de las corridas originales. |
| `manifiesto_paquete.json` y `.sha256` | Inventario y SHA-256 de todos los archivos entregados, excluyendo el propio manifiesto y su sidecar. |

Los enlaces de lectura son relativos. Las rutas originales presentes dentro de
manifiestos y documentos TXT registran procedencia; no se necesitan para abrir
el paquete ni reproducir tablas o figuras. Las vistas Markdown de los dos informes
sólo adaptan enlaces y añaden una nota; el original íntegro queda al lado, en TXT.

## Unidades, precisión y límites

CSV en UTF-8, coma como separador, punto decimal; USDT para dinero. Retornos,
basis y MAE están en proporciones. Tiempos UTC; horas-activo suman símbolos.
Los decimales no se redondean en las tablas. El Sharpe indefinido queda vacío con
motivo en resultados y se imprime ND en el texto. Los ceros observados permanecen
en cero. [Convenciones](convenciones.md) detalla métricas, rechazos y slippage.

Las reglas y tarifas son supuestos prescritos, no historia exacta reconstruida.
El funding temprano usa proxies causales de mark, con cobertura explícita en
[cobertura_funding.csv](tablas/cobertura_funding.csv). El calentamiento se separa
del período económico. No se garantiza ejecución real ni se certifica todo el
motor mediante una conciliación o la auditoría del basis.

## Reproducción del subconjunto entregado

Extraer el ZIP y situarse en su carpeta `paquete_redaccion`. Se probó con Python
3.14.3, NumPy 2.3.5 y Matplotlib 3.11.2. Las versiones originales completas están
en [versiones.csv](tablas/versiones.csv) y los manifiestos. Para una instalación
separada, si las dependencias todavía no están disponibles:

```powershell
python -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r '.\scripts\requirements.txt'
```

Con ese entorno, o con el Python del proyecto que ya posee las dependencias:

```powershell
python .\scripts\verificar_paquete.py
python .\scripts\reproducir.py --destino ..\reproduccion_entrega_3
python .\scripts\diccionario.py --destino ..\reproduccion_entrega_3
```

Al usar un entorno virtual, reemplazar `python` por su ejecutable como en el
primer bloque. `reproducir.py` verifica las fuentes y regenera las tablas numéricas,
series, trazas, controles y dos figuras. `diccionario.py` regenera el diccionario.
La matriz metodológica y la bibliografía son documentos editoriales contrastados
con los originales; no son cálculos económicos. Los scripts leen únicamente
archivos incluidos, no requieren conexión, API de Binance, NautilusTrader ni disco D.
Los comandos realmente ejecutados durante la preparación están en [verificacion.md](verificacion.md).

Reproducir el backtest completo sí requiere el proyecto, su entorno y sus datos
originales, excluidos del ZIP. `scripts/preparar_paquete.py` es el snapshot de
preparación para ese proyecto completo, no el comando de reproducción portátil.
Los manifiestos originales conservan hashes de entradas y salidas omitidas del
subconjunto; su ausencia aquí es deliberada y no invalida la lectura del paquete.

## Antecedentes y faltantes para la redacción

Se conservaron DOCX y PDF de Entrega 1 (Pablo Salerno y Facundo Rodriguez) y
Entrega 2 (Pablo Salerno). La lectura académica se hizo directamente sobre el
OOXML de los DOCX, con párrafos numerados en `antecedentes/parrafos_fuente.txt`.
La bibliografía reúne los registros de Entrega 2 y las referencias exclusivas
de Entrega 1, sin investigación externa ni referencias añadidas.

No se localizaron los originales de:

- `Entregables - Track Finanzas Computacionales(2).docx`, consigna académica.
- `Entrega 2 Crypto Carry Binance Pablo Salerno(6).pdf`, esa revisión exacta;
  sí se incluyeron el DOCX y PDF disponibles sin el sufijo `(6)`.
- `3cce414b-a788-41f0-bd6e-54b3bda4871b.png`, imagen del feedback.

Sólo existe su transcripción parcial en el prompt original conservado como
evidencia. No se afirma haber leído esos adjuntos ni que sean idénticos a las
versiones disponibles. El faltante limita el cotejo final de consigna, formato
y feedback académico; la preparación técnica y sus resultados están completos.

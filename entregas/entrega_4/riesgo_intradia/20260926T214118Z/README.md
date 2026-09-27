# Riesgo intradía, incidentes y garantías — ejecución 20260926T214118Z

Bloque ejecutado y verificado sobre las cuatro carteras existentes BASE/MARGEN_2X, condicional y permanente. Se resolvió por posprocesamiento: las fuentes locales permitieron reconstruir cuentas, precios y estados sin replay ni nuevos backtests. El paquete original de doce carteras, la corrección de exposición/H2 y la Entrega 3 permanecen intactos. Este trabajo no completa toda la Entrega 4.

## Productos

- [Reporte HTML](paquete_20260926T220400Z/reporte.html) y [Markdown](paquete_20260926T220400Z/reporte.md).
- [Catálogo completo de 449 episodios](paquete_20260926T220400Z/catalogo_completo.html), [tablas de drawdown](paquete_20260926T220400Z/tablas/drawdown_comparativo.csv), [garantías y liquidez](paquete_20260926T220400Z/tablas/garantias_periodo.csv), [resultados financieros por período](paquete_20260926T220400Z/tablas/metricas_reutilizadas.csv) e [índice de 13 figuras](paquete_20260926T220400Z/figuras/indice_figuras.csv).
- [Feedback literal](paquete_20260926T220400Z/documentos/feedback_e3.md), [protocolo previo sellado](paquete_20260926T220400Z/documentos/protocolo.md), [matriz de cobertura](paquete_20260926T220400Z/documentos/matriz_cobertura_feedback.csv) y [pendientes](paquete_20260926T220400Z/cobertura_pendiente.md).
- [Guía del paquete y comandos portables](paquete_20260926T220400Z/README.md), [comandos de producción](paquete_20260926T220400Z/documentos/comandos_produccion.md) y [registro de ejecución](registro_ejecucion.md).

## Hallazgos

La medida intradía usa la unión de cierres de minuto, instantes financieros y cierres diarios. Las cuentas conservan los estados originales y los empates PRE/POST; no es una serie de ticks. La tabla siguiente utiliza la valoración original, la muestra completa y el mismo capital inicial de 10.000 USDT.

| Cartera | DD diario | DD intradía | Diferencia en magnitud (pp) | Menor holgura aislada (USDT) | Máximo preventivo conjunto, ínfimo (USDT) |
| --- | ---: | ---: | ---: | ---: | ---: |
| BASE condicional | −0,2062% | −0,5689% | 0,3627 | 486,21 | 18,94 |
| BASE permanente | −0,4827% | −1,0081% | 0,5253 | 501,93 | 15,10 |
| MARGEN_2X condicional | −0,2383% | −0,5985% | 0,3602 | 491,07 | 11,10 |
| MARGEN_2X permanente | −0,4827% | −1,0081% | 0,5253 | 504,79 | 22,19 |

No aparecieron déficits de mantenimiento en estas valoraciones. Las necesidades preventivas son hipotéticas sobre los estados originales; no son aportes ejecutados. En algunos instantes no se puede acreditar la caja neta por compromisos de órdenes, por lo que el faltante externo exacto es ND y se presentan cotas. Las necesidades simultáneas comparten una sola caja y no se suman a través del tiempo.

Se confirmaron los 121 minutos descubiertos del 24/03/2023 en cada BASE y los totales de 11.340/16.440 segundos de la muestra. Durante esos 121 minutos los futuros afectados estaban cerrados: había riesgo de precio del spot, sin mantenimiento de esos cortos. En la BASE condicional la pérdida transitoria de valoración desde el inicio del episodio fue 43,27 USDT; el cambio al estado final fue −34,05 USDT. En la permanente, BTC/ETH simultáneos producen una sola duración de cartera y un cambio conjunto de −50,11 USDT, con pérdida transitoria de 61,72 USDT. Son P&L contemporáneos, sin atribución causal automática al incidente.

El pico que origina el peor DD de la condicional depende del spot retenido durante la suspensión. La contabilidad concilia, pero ese precio no acredita una cotización ejecutable contemporánea. El diagnóstico de valoración con proxy fijo y causal da −0,5313% de DD global para esa cartera; no reconstruye ventas posibles ni una trayectoria sin interrupción. El complemento de calidad identifica por referencia la causa del arrastre y conserva separadas las aproximaciones de marks y funding.

El reporte mantiene los años 2022–2025 y enero–agosto de 2026, junto con utilización de capital y tiempo activo sin polvo. En BASE condicional, el retorno fue 5,24% en 2024 y 0,31% en 2025; enero–agosto de 2026 conserva un P&L de −0,09 USDT, con polvo y sin actividad. El promedio 2024+ no se presenta como mejora sostenida. H1/H2/H3 y las cifras financieras originales no se recalcularon ni ajustaron a redondeos de PDF.

## Verificación ejecutada y sello

El cierre terminó con exit 0 el **2026-09-26 a las 22:57 UTC**. El paquete contiene 199 miembros inventariados (50.055.665 bytes antes del manifiesto). Identidad SHA-256:

`78cb03572c5940567852d0255d05a9f8a923f01df01fc0aa8b6cccef70f3b3bb`

| Control | Resultado y evidencia |
| --- | --- |
| Cierre completo | [cierre_ejecutado.json](cierre_ejecutado.json): todos los comandos, rutas, tiempos, exit codes y hashes de logs |
| Verificación completa desde otra ruta | [Resultado](verificacion_completa_reubicada.json), [comando](verificacion_completa_reubicada_comando.json) y [log](verificacion_completa_reubicada.log): 224 particiones y 9.851.104 observaciones reconstruidas, 342 archivos de precios autenticados, 128 DD y 449 episodios comprobados; 214,11 segundos |
| Conciliación diaria | 6.816 cierres, mayor residual 3,637978807091713e-12 USDT frente a 1E-8. La auditoría Decimal de cuentas obtuvo igualdad exacta |
| Calidad de precios | 2.457.592 claves compartidas, seis referencias por clave; unión exacta y razones causales verificadas sobre las fuentes de todos los bloques |
| Compacta final | [verificacion_compacta_final.json](verificacion_compacta_final.json): paquete original idéntico a la copia totalmente verificada, padre/corrección autenticados |
| Pruebas portables finales | [Log](pytest_paquete_reubicado.log) y [comando](pytest_paquete_reubicado_comando.json): **140 passed**, ejecutadas con las versiones finales archivadas fuera del checkout |
| Suite general | [Log](calidad_precios_suite_general.log) y [registro](calidad_precios_suite_general.json): **890 passed**. El verificador terminó un ajuste en paralelo; la prueba portable posterior incluye sus 61 casos finales |
| Ruff y whitespace | [Ruff final](ruff_cierre.log), [comando](ruff_cierre.json) y [git diff --check](git_diff_check_final.json): exit 0 |
| Sólo lectura y preservación | [preservacion_final.json](preservacion_final.json): 2.177 archivos previos sin cambios, 342 fuentes de precios y 224 particiones intactas, sin archivos nuevos en directorios protegidos, HEAD e índice idénticos |

La verificación se ejecutó sin `-B` para comprobar que el propio verificador evita bytecode. Sus salidas fueron externas; la copia y el paquete original conservaron todos sus bytes. La comprobación completa reutiliza las funciones archivadas de estados, grilla, precios y clasificación causal; contrasta además la aritmética contable y recalcula la reducción global de drawdown. No se atribuye independencia a todo el posprocesador.

Los resultados finales se conservan fuera del sello para poder verificar sin modificar el paquete. Primero se selló una copia temporal, se probó desde esa ruta y luego se trasladó exactamente el mismo manifiesto al contenido idéntico de esta entrega. No se cambió ningún manifiesto histórico.

La única modificación de un archivo previamente rastreado es `.gitattributes`, con reglas limitadas al nuevo árbol `riesgo_intradia` para preservar sus bytes en futuros checkouts. No hubo commit, push, cambios de índice, alteraciones del motor ni de configuraciones económicas.

## Datos locales y alcance pendiente

Las series completas ocupan 2.934.571.231 bytes comprimidos y permanecen en:

`D:/Backtesting/outputs/riesgo_intradia_20260926T214118Z/completa`

Su procedencia y hashes están en [series_locales.json](paquete_20260926T220400Z/series_locales.json). No se duplicó el paquete padre ni se incluyeron todas las fuentes masivas en el producto publicable. La verificación compacta por sí sola no recalcula el máximo global de la muestra: hacen falta esas series, los estados y los precios originales con rutas explícitas.

Persisten la incertidumbre del precio spot durante la interrupción, los compromisos cuya caja neta no es acreditable y la ausencia de observación intravela. Quedan pendientes la alternativa remunerada, las demoras/shocks propuestos y el escenario de nueva trayectoria sin interrupción. La valoración proxy no los sustituye. No se generó el PDF final ni se afirma haber leído un PDF E3 ausente.

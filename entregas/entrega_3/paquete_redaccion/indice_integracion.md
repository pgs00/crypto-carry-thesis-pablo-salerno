# Índice de integración académica

## Criterio general

La Entrega 2 es la base acumulativa porque ya reúne la idea, la motivación, las hipótesis, el research y el diseño previsto. La Entrega 1 se conserva como antecedente original y respaldo de procedencia, sin anexarla completa al cuerpo ni repetir su bibliografía. La Entrega 3 agrega la implementación efectiva, los cambios respecto del diseño, los resultados preliminares, sus límites y los próximos análisis. Este índice no propone un Whitepaper final ni presenta la Entrega 4 como terminada.

Las citas `E1-Pnnn` y `E2-Pnnn` remiten a [antecedentes/parrafos_fuente.txt](antecedentes/parrafos_fuente.txt), extraído directamente de los DOCX incluidos. La bibliografía única se encuentra en [antecedentes/bibliografia_consolidada.md](antecedentes/bibliografia_consolidada.md) y su versión tabular en [antecedentes/bibliografia_consolidada.csv](antecedentes/bibliografia_consolidada.csv).

## Estructura propuesta

1. **Idea y motivación.** Conservar la síntesis de la Entrega 2, secciones 1 y 2 (`E2-P013` a `E2-P017`). Mencionar la Entrega 1 como origen del planteo (`E1-P027` a `E1-P034`) sin reproducir ambos textos.
2. **Hipótesis.** Mantener H1, H2 y H3 de la Entrega 2 (`E2-P018` a `E2-P022`). La evaluación es descriptiva. El criterio más exigente de significancia de la Entrega 1 (`E1-P047` a `E1-P049`) queda como antecedente histórico, no como requisito vigente.
3. **Research y marco conceptual.** Conservar la sección 4 de la Entrega 2 (`E2-P023` a `E2-P030`). Usar una sola bibliografía consolidada y añadir únicamente las cuatro fuentes específicas de la Entrega 1 que no aparecen como registros equivalentes en la lista de la Entrega 2.
4. **Diseño previo a la implementación.** Resumir las secciones 7 y 8 de la Entrega 2 (`E2-P040` a `E2-P166`): muestra continua prevista, trades individuales, forecast, reglas de entrada y salida, garantías, costos, comparador permanente y criterios de evaluación. Presentarlo como diseño anterior, sin atribuirle decisiones posteriores.
5. **Implementación efectiva y cambios metodológicos.** Incorporar como sección nueva de la Entrega 3 las dos ventanas independientes, datos de un minuto, cierres alineados, `next_minute_vwap`, participación máxima del 1%, fills parciales, sizing conjunto, prioridad temporal vigente, NautilusTrader 1.231.0 y ledger propio. La trazabilidad está en [tablas/cambios_metodologicos.csv](tablas/cambios_metodologicos.csv).
6. **Resultados preliminares.** Incorporar como sección nueva de la Entrega 3 las cuatro carteras del escenario principal `vwap_joint`. Usar las tablas y figuras del paquete, distinguir aperturas de ciclos cerrados y conservar las variantes de ejecución en el anexo técnico.
7. **Evidencia sobre H1, H2 y H3.** Separar pronóstico, resultado económico y comparación entre ventanas. Presentar evidencia descriptiva, resultados contrarios o no concluyentes y límites de cobertura; no afirmar significancia, causalidad ni confirmación definitiva.
8. **Problemas y limitaciones.** Incorporar baja cantidad de operaciones, concentración temporal del resultado, aproximación de ejecución, proxies de mark, reglas y costos prescritos, garantías segregadas y exposición durante desarmes. Aclarar que “permanente” omite el filtro de funding, pero conserva basis y demás controles, por lo que puede permanecer inactiva.
9. **Próximos análisis.** Reservar para la Entrega 4 la sensibilidad económica del horizonte y del filtro de basis, junto con robustez y análisis crítico. Identificar esas tareas como pendientes y exploratorias.
10. **Anexos y trazabilidad.** Conservar originales, hashes, bibliografía por procedencia, configuraciones efectivas, supuestos, manifiestos, auditorías y la matriz de cambios. Los documentos ausentes deben registrarse como faltantes, no reconstruirse.

## Tratamiento del material existente

| Material | Tratamiento |
|---|---|
| Entrega 1 DOCX y PDF | Conservar intactos como antecedentes. Citar sólo cuando aporta procedencia o permite documentar la evolución del criterio. |
| Entrega 2 DOCX y PDF | Usar el DOCX como base acumulativa del texto posterior. No se afirma identidad con la revisión `(6)` citada pero no disponible. |
| Idea, motivación, hipótesis y research | Conservar desde la Entrega 2 y editar sólo para integrar transiciones o eliminar repeticiones. |
| Diseño de las secciones 7 y 8 de la Entrega 2 | Resumir como diseño previo y contrastar con la implementación efectiva. |
| Bibliografías de Entregas 1 y 2 | Sustituir por una sola lista consolidada con procedencia E1/E2. |
| Implementación, cambios, resultados y limitaciones | Incorporar como material nuevo de la Entrega 3. |
| Sensibilidades de horizonte y basis | Mantener como pendientes de la Entrega 4. |

## Faltantes académicos

No están incluidos los originales `Entregables - Track Finanzas Computacionales(2).docx`, `Entrega 2 Crypto Carry Binance Pablo Salerno(6).pdf` ni `3cce414b-a788-41f0-bd6e-54b3bda4871b.png`. El instructivo técnico sólo transcribe que la Entrega 3 cubre implementación y resultados preliminares, que la Entrega 4 cubre robustez y análisis crítico y que el feedback favorecía conservar comparabilidad entre estrategias. Esa transcripción no debe presentarse como lectura directa de los adjuntos.

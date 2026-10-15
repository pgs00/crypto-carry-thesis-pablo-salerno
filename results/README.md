# Resultados del estudio

La [tesina](../Tesina_Pablo_Salerno.pdf) y el
[Executive Briefing](../Executive_Briefing_Pablo_Salerno.pdf) presentan la
interpretación financiera. Las páginas siguientes resumen cada pregunta y
enlazan la evidencia completa, sin repetir todas sus tablas.

| Tema | Pregunta | Límite principal |
|---|---|---|
| [BASE](base/README.md) | ¿El filtro mejora el desempeño? | Caja sin remuneración; nueve ciclos cerrados de la condicional. |
| [Riesgo intradía](riesgo/README.md) | ¿Qué pérdidas transitorias y necesidades de garantías aparecen? | Los extremos globales por minuto requieren datos masivos. |
| [Capital](capital/README.md) | ¿Cuánto patrimonio se utiliza y dónde se concentra el resultado? | Descripción de las operaciones, sin resimular la eliminación de ciclos. |
| [Benchmark SOFR](benchmark_sofr/README.md) | ¿Se supera el costo de oportunidad del patrimonio completo? | Cuenta hipotética bruta en USD; no es la remuneración de caja del carry. |
| [Señal y entradas](senal/README.md) | ¿Qué cambia con horizonte, semivida y techo del basis? | Variantes aisladas; MAE comparable dentro del mismo horizonte. |
| [Costos y capacidad](costos_capacidad/README.md) | ¿Cómo afectan las fricciones y el tamaño? | Selección fija a 34 pb; capacidad estimada con velas de un minuto. |
| [Ejecución](ejecucion/README.md) | ¿Qué cambia con precios y demoras alternativos? | No reproduce toda la microestructura intradiaria. |
| [Estrés](estres/README.md) | ¿Qué ocurre ante shocks o una trayectoria sin interrupción? | Escenarios hipotéticos; no identifican causalidad histórica. |
| [Estabilidad](estabilidad/README.md) | ¿Qué depende del inicio de la muestra y de la incertidumbre? | Inicios retrospectivos e intervalos sujetos a sus supuestos. |
| [Complementos](complementaria/README.md) | ¿Qué aportan otros comparadores H1, H3 por año y caja SOFR? | Análisis exploratorios separados del caso base. |

Las [tablas y figuras continuas](base/continuo/README.md) son la referencia
para el desempeño total y anual. En BASE no se cumple H2; la dirección
descriptiva de H3 es contraria a la compresión preespecificada. Estas
conclusiones no se extrapolan a todos los períodos o variantes. Cada síntesis
conserva sus excepciones y resultados no definidos.

La remuneración de caja queda fuera de BASE y se explora por separado en el
complemento, sin reinvertir los intereses en nuevas posiciones. El benchmark
SOFR sigue siendo una cuenta alternativa sobre el patrimonio completo.

La [matriz de resultados](matriz_resultados.csv) identifica escenarios y
dependencias. Los [informes sellados](../docs/procedencia/README.md) conservan
sus tablas, configuraciones y fuentes; las
[ventanas independientes](../data/evidence/ventanas_independientes/LEEME.md)
son antecedentes con reinicios de capital, distintos de las cuentas continuas.
La [guía de reproducción](../docs/reproduction.md) reúne los comandos y el
alcance de las comprobaciones.

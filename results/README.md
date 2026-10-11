# Resultados del estudio

La [tesina final](../Tesina_Pablo_Salerno.pdf) presenta el estudio de carry
condicional y permanente. La [matriz de resultados](matriz_resultados.csv)
identifica escenarios, evidencia, dependencias y límites. Los identificadores
BASE_E3 y B1–B6 conservan el linaje de los experimentos; la navegación se
organiza por preguntas científicas.

En BASE total, H2 es `no_favorable` y la dirección descriptiva de H3 es
`contraria`. H1 depende del horizonte y activo; H2 conserva resultados por
escenario y período, ND y excepciones. Estas etiquetas no se extienden a
todos los años o variantes. Las cuentas nuevas de estabilidad no son cortes
heredados de BASE.

| Tema | Lectura y pregunta | Límite principal |
|---|---|---|
| [BASE](base/README.md) | [Tablas y figuras continuas](base/continuo/README.md), reglas prescritas y exposición/H2 corregidos | Reglas prescritas y observaciones parciales no certifican la historia completa del exchange. |
| [Riesgo intradía](riesgo/README.md) | Pérdidas transitorias y garantías de BASE/MARGEN_2X | La verificación compacta no reconstruye extremos globales por minuto. |
| [Capital](capital/README.md) | Capital utilizado, concentración y rechazos | Análisis descriptivo; no CAGR contrafáctico quitando mejores ciclos. |
| [Benchmark SOFR](benchmark_sofr/README.md) | Costo de oportunidad del capital completo | Cuenta hipotética bruta USD, ACT/360 y paridad nominal; no remuneración de caja carry. |
| [Señal y entradas](senal/README.md) | Horizonte/tenencia, semivida EWMA y techo del basis | Seis variantes aisladas; MAE comparable dentro del mismo horizonte. |
| [Costos y capacidad](costos_capacidad/README.md) | Fricciones, participación y capital inicial | Ocho variantes aisladas, selección a 34 pb; capacidad de velas 1m sin impacto ni colas. |
| [Ejecución](ejecucion/README.md) | Convención de precio y demoras | Seis variantes aisladas; LC causal global y casos intradía acotados. |
| [Estrés y contrafactual](estres/README.md) | Movimientos adversos y trayectoria hipotética sin interrupción | Recuperación impuesta y anclas fijas; no identifica causalidad histórica. |
| [Estabilidad e incertidumbre](estabilidad/README.md) | Fechas iniciales alternativas, bootstrap y evaluación conjunta | Inicios retrospectivos e intervalos marginales con supuestos por año. |

Cada tema conserva su evidencia en `evidencia/`, con tablas, figuras,
protocolos, herramientas y procedencia. La presentación de las
[carteras continuas](base/continuo/README.md) reúne sus tablas y figuras;
el [informe BASE](base/README.md) desarrolla la corrección de exposición/H2.
Las ventanas independientes son
[antecedentes científicos](../data/evidence/ventanas_independientes/LEEME.md).
Los protocolos conservan sus fechas y alcances originales.

El informe padre de reglas se lee junto con la corrección BASE. La
[segunda tanda propuesta](../docs/reglas_historicas/decisiones_integracion.md#segunda-tanda-propuesta--no-ejecutada)
permanece fuera de los resultados ejecutados. Las sensibilidades no se cruzan ni se adoptan en BASE
por rentabilidad. Remunerar o reinvertir caja y garantías del carry permanece
fuera del estudio; SOFR es una cuenta separada.

La [guía de reproducción](../docs/reproduction.md) contiene los nueve
verificadores compactos y los requisitos para datos masivos. BASE requiere
el [padre completo](../data/evidence/reglas_historicas/README.md); riesgo
requiere padre y corrección BASE; SOFR requiere capital. Capital puede
autenticar además esas dependencias, riesgo y la referencia continua extraída.
Las demás dependencias compactas se incluyen en sus evidencias temáticas.

Los certificados históricos conservan su alcance; no sustituyen la
comprobación del producto actual ni acreditan una nueva ejecución del motor.
Windows es el entorno de referencia. La comparación literal del CSV de
intervalos tuvo un fallo integral histórico en Linux, con diferencia máxima
`6.938893903907228e-18` y controles numéricos aprobados en esa comprobación.

```powershell
python -B -X utf8 -m scripts.verify_product
python -B -X utf8 -m scripts.verify_documentation
```

# Crypto carry condicional en Binance

Tesina de Pablo Salerno, Maestría en Finanzas, UCEMA.

- [Tesina final, PDF de 37 páginas](Tesina_Pablo_Salerno.pdf)
- [Executive Briefing, PDF de 2 páginas](Executive_Briefing_Pablo_Salerno.pdf)

El estudio compara dos carteras que compran BTC y ETH en el mercado spot y
venden futuros perpetuos USD-M. La condicional exige un pronóstico de funding
suficiente para entrar; la incondicional omite ese filtro. Ambas comparten
las restricciones de basis, ejecución, capital y riesgo. Cada cuenta parte de
10.000 USDT y se mantiene continua entre enero de 2022 y agosto de 2026.

El EWMA mejora el pronóstico, pero esa mejora no se traduce en una ventaja
consistente del filtro. En el caso base, sin remuneración de caja, el retorno
anual compuesto es 1,6335% para la condicional y 3,3825% para la incondicional.
Ambas quedan por debajo de una cuenta hipotética a SOFR (4,0928%). El Sharpe
publicado usa tasa libre de riesgo cero. Una sensibilidad separada de
remuneración de caja puede invertir el ranking; no acredita acceso efectivo
a SOFR ni vuelve a simular las operaciones.

## Recorrido de lectura

| Para consultar | Ubicación |
|---|---|
| Resultados principales y evolución anual | [Carteras continuas](results/base/continuo/README.md) |
| Riesgo, capital y sensibilidades | [Resultados por tema](results/README.md) |
| Reglas y supuestos del estudio | [Metodología](docs/methodology.md) |
| Comparadores H1, oportunidad anual H3 y caja SOFR | [Evidencia complementaria](results/complementaria/README.md) |
| Comprobar los archivos o reproducir los cálculos | [Guía de reproducción](docs/reproduction.md) |

## Código y evidencia

`src/crypto_carry/` contiene el motor. La configuración de referencia es
[`configs/reglas_historicas/BASE_E3.toml`](configs/reglas_historicas/BASE_E3.toml).
Los perfiles `configs/base.toml` y `configs/robustness.toml` son anteriores y
no reproducen la BASE de la tesina. Las fuentes masivas y corridas completas
requieren la preparación descrita en la guía; los paquetes compactos de
evidencia están incluidos.

Los informes breves enlazan las tablas, figuras e informes completos originales.
La [procedencia](docs/procedencia/README.md) documenta sus identidades y controles.

Se utilizó IA como asistente para desarrollar código, generar gráficos y tablas
y apoyar la revisión y edición. El análisis, la interpretación y las decisiones
finales corresponden al autor. La declaración completa figura en la tesina.

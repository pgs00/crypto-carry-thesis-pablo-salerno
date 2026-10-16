# Crypto carry condicional en Binance

Tesina de Pablo Salerno, Maestría en Finanzas, UCEMA.

- [Tesina final](Tesina_Pablo_Salerno.pdf)
- [Executive Briefing](Executive_Briefing_Pablo_Salerno.pdf)

El estudio compara dos carteras que compran BTC y ETH en spot y venden sus
futuros perpetuos USD-M. La condicional exige funding previsto suficiente para
entrar y renovar; la incondicional omite ese filtro. Cada cuenta comienza con
10.000 USDT y conserva sus saldos entre enero de 2022 y agosto de 2026.

El EWMA mejora el pronóstico, pero el filtro no obtiene una ventaja consistente.
Con caja sin remuneración, el CAGR es 1,6335% para la condicional y 3,3825% para
la incondicional, frente al 4,0928% de una cuenta SOFR hipotética. El Sharpe usa
tasa libre de riesgo cero. La sensibilidad de remuneración de caja puede
invertir el ranking. Los [supuestos y límites](docs/methodology.md#limitaciones)
delimitan estas conclusiones.

## Recorrido corto

| Para | Leer |
|---|---|
| Entender el resultado financiero | Tesina y [resultados por tema](results/README.md). |
| Conocer las reglas de las carteras | [Metodología](docs/methodology.md) y [configuración BASE](configs/reglas_historicas/BASE_E3.toml). |
| Ubicar tablas, series y unidades | [Diccionario de datos](docs/data_dictionary.md). |
| Comprobar las cifras publicadas | [Reproducción](docs/reproduction.md). |

Desde la raíz del repositorio:

```bash
uv sync --frozen --python 3.14.3
uv run python -m scripts.verify
uv run pytest -q
```

La verificación lee la evidencia incluida, recalcula las tablas y compara sus
valores al redondeo publicado. No necesita descargar datos de mercado.

## Mapa del código

| Parte | Archivos y función |
|---|---|
| Modelo económico | [`strategy.py`](src/crypto_carry/strategy.py) coordina decisiones; [`forecast.py`](src/crypto_carry/forecast.py) calcula el EWMA; [`portfolio.py`](src/crypto_carry/portfolio.py) dimensiona las posiciones; [`ledger.py`](src/crypto_carry/ledger.py) registra caja y P&L; [`margin.py`](src/crypto_carry/margin.py) controla garantías; [`execution.py`](src/crypto_carry/execution.py) simula las órdenes; [`evaluation.py`](src/crypto_carry/evaluation.py) evalúa las hipótesis. |
| Análisis de la evidencia | [`scripts/analysis/`](scripts/analysis/) reúne señal, costos, ejecución, riesgo, estrés, estabilidad, SOFR y capital. [`scripts/verify.py`](scripts/verify.py) ejecuta el recálculo y la comparación. |
| Infraestructura | [`nautilus_adapter.py`](src/crypto_carry/nautilus_adapter.py) integra NautilusTrader; [`data/replay.py`](src/crypto_carry/data/replay.py) ordena los datos preparados; [`reporting.py`](src/crypto_carry/reporting.py) guarda los resultados del motor. |

Los [datos de referencia](data/evidence/carteras_continuas.zip) y los informes
citados conservan sus rutas. Las versiones anteriores siguen disponibles en
el historial de Git, incluidos los commits enlazados desde la tesina.

Se utilizó IA como asistente para desarrollar código, generar gráficos y tablas
y apoyar la revisión y edición. El análisis, la interpretación y las decisiones
finales corresponden al autor. La declaración completa figura en la tesina.

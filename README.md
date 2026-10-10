# Crypto carry: backtesting de la tesina

¿Una cartera que filtra entradas y renovaciones por un pronóstico de funding
mejora el desempeño de una cartera de carry permanente? El estudio compara
compra spot y venta de perpetuos USD-M en **BTCUSDT y ETHUSDT**. La permanente
omite sólo el filtro de funding; comparte las reglas de basis, ejecución,
capital y riesgo.

El período vigente es **01/01/2022–31/08/2026 UTC**, continuo y sin reinicios
anuales, con 10.000 USDT iniciales por cartera. Usa velas de un minuto,
`next_minute_vwap`, sizing conjunto y `futures_scaled` para 15 marks ausentes.

**[Tesina final de Entrega 4 (PDF, 24 páginas)](entregas/entrega_4/documento_final/Tesina_Entregas_3_y_4_Pablo_Salerno.pdf)**

BASE total conserva H2 `no_favorable`: la condicional no supera el Sharpe de
la permanente. H3 es descriptivamente `contraria`: oportunidad y CAGR
condicional aumentan en el segundo tramo. Las excepciones por escenario/año
se conservan en los reportes; no se generalizan esas etiquetas a toda variante.
H1 registra MAE de 6,299 bps para EWMA frente a 8,703 bps para no-change,
con 10.180 observaciones válidas y 44 exclusiones.

| Cartera BASE | Equity final (USDT) | Retorno neto | CAGR | Sharpe | Drawdown diario |
|---|---:|---:|---:|---:|---:|
| Condicional | 10.785,76 | 7,8576 % | 1,6335 % | 4,9624 | −0,2062 % |
| Permanente | 11.680,07 | 16,8007 % | 3,3825 % | 6,5336 | −0,4827 % |

Los resultados usan reglas prescritas y aproximaciones explícitas. La
metodología conserva sus límites de ejecución, datos, margen e inferencia.

- [Metodología vigente](docs/methodology.md): contrato científico y limitaciones.
- [Resultados y paquetes vigentes E4](entregas/entrega_4/README.md): BASE, riesgo y bloques 1–6.
- [Guía única de reproducción](docs/reproduction.md): lectura, verificadores compactos, extracción E3 y datos masivos.
- [Resultados continuos E3](entregas/entrega_3/continua/README.md): tablas, figuras y corridas de referencia.
- [Recuperación de antecedentes](docs/repository_cleanup.md#recuperacion-de-antecedentes): Git, respaldo y rutas originales.

Desde la raíz del repositorio, preparar el entorno y comprobar la presentación E3:

```powershell
uv sync --frozen --python 3.14.3
& '.\.venv\Scripts\python.exe' -B -X utf8 -m scripts.publish_thesis --verify
& '.\.venv\Scripts\python.exe' -B -X utf8 -m scripts.verify_documentation
```

La [guía](docs/reproduction.md) publica los nueve comandos congelados E4 y
distingue su alcance de un replay económico. Los controles ejecutados durante
la simplificación local están en el [registro de verificaciones](docs/repository_cleanup.md#verificaciones).

`src/crypto_carry/` contiene el motor; las configuraciones efectivas de cada
corrida y paquete fijan los experimentos. `configs/base.toml` y
`configs/robustness.toml` son perfiles anteriores del CLI (`first_trade`),
conservados por sus usos y pruebas; no identifican la BASE vigente E4.
Las fuentes masivas, corridas completas, entornos y cachés permanecen locales.

El trabajo utilizó asistencia de IA en código, documentación y verificaciones.
Los [prompts conservados](docs/sources/) registran la procedencia; no son la
especificación vigente ni acreditan autoría personal de tareas concretas.

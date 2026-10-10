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

En BASE total la condicional no supera el Sharpe de la permanente (H2
`no_favorable`). Los reportes conservan las cifras, excepciones por escenario
y límites de interpretación de las tres hipótesis.

- [Metodología vigente](docs/methodology.md): contrato científico y limitaciones.
- [Resultados y paquetes vigentes E4](entregas/entrega_4/README.md): BASE, riesgo y bloques 1–6.
- [Guía única de reproducción](docs/reproduction.md): lectura, verificadores compactos, extracción E3 y datos masivos.
- [Resultados continuos E3](entregas/entrega_3/continua_distribucion_20261010/README.md): tablas, figuras y corridas de referencia.

Desde la raíz del repositorio, preparar el entorno y comprobar la presentación E3:

```powershell
uv --cache-dir .uv-cache sync --frozen --python 3.14.3
& '.\.venv\Scripts\python.exe' -B -X utf8 -m scripts.publish_thesis --verify
& '.\.venv\Scripts\python.exe' -B -X utf8 -m scripts.verify_documentation
```

La [guía](docs/reproduction.md) publica los nueve verificadores compactos E4,
las pruebas y los requisitos para reproducir el motor.

`src/crypto_carry/` contiene el motor; las configuraciones efectivas de cada
corrida y paquete fijan los experimentos. `configs/base.toml` y
`configs/robustness.toml` son perfiles anteriores del CLI (`first_trade`),
conservados por sus usos y pruebas; no identifican la BASE vigente E4.
Las fuentes masivas, corridas completas, entornos y cachés permanecen locales.

Las distribuciones documentales del 10/10/2026 de E3 continua y SOFR conservan
los datos, figuras y herramientas retenidos byte por byte, con manifiestos
propios. Los originales completos y sus hashes están fuera del repositorio en
`../Backtesting_antecedentes/distribucion_20261010/`. Los paquetes históricos
E3, BASE, riesgo y B1–B6 conservan documentos internos exigidos por sus
protocolos o cadenas de sellos; también el archivo local de auditoría del basis.
Esas excepciones preservan los controles y la procedencia originales.

El trabajo utilizó asistencia de IA mediante Codex en código, documentación y
verificaciones. El motor integra NautilusTrader; las fuentes de Binance y las
atribuciones académicas se conservan en la tesina y los paquetes de evidencia.

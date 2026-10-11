# Crypto carry: backtesting de la tesina

¿Una cartera que filtra entradas y renovaciones por un pronóstico de funding
mejora el desempeño de una cartera de carry permanente? El estudio compara
compra spot y venta de perpetuos USD-M en **BTCUSDT y ETHUSDT**. La permanente
omite sólo el filtro de funding; comparte las reglas de basis, ejecución,
capital y riesgo.

El período vigente es **01/01/2022–31/08/2026 UTC**, continuo y sin reinicios
anuales, con 10.000 USDT iniciales por cartera. Usa velas de un minuto,
`next_minute_vwap`, sizing conjunto y `futures_scaled` para 15 marks ausentes.

**[Tesina final (PDF, 24 páginas)](Tesina_Pablo_Salerno.pdf)**

El PDF conserva sus bytes originales y la etiqueta «TESINA · ENTREGA 4» de la
portada. No se dispone de una fuente editable final autenticada; el cambio de
nombre y ubicación no modifica su contenido.

En BASE total la condicional no supera el Sharpe de la permanente (H2
`no_favorable`). Los reportes conservan las cifras, excepciones por escenario
y límites de interpretación de las tres hipótesis.

- [Metodología vigente](docs/methodology.md): contrato científico y limitaciones.
- [Resultados por tema](results/README.md): BASE, riesgo, capital y sensibilidades.
- [Guía única de reproducción](docs/reproduction.md): lectura, verificadores compactos, referencia continua y datos masivos.
- [BASE y resultados continuos](results/base/README.md): tablas, figuras y corridas de referencia.

Desde la raíz del repositorio, preparar el entorno y comprobar el producto final:

```powershell
uv --cache-dir .uv-cache sync --frozen --python 3.14.3
& '.\.venv\Scripts\python.exe' -B -X utf8 -m scripts.verify_product
& '.\.venv\Scripts\python.exe' -B -X utf8 -m scripts.verify_documentation
```

La [guía](docs/reproduction.md) publica los nueve verificadores compactos,
las pruebas y los requisitos para reproducir el motor.

`src/crypto_carry/` contiene el motor; las configuraciones efectivas de cada
corrida y paquete fijan los experimentos. `configs/base.toml` y
`configs/robustness.toml` son perfiles anteriores del CLI (`first_trade`),
conservados por sus usos y pruebas; no identifican la BASE vigente.
Las fuentes masivas, corridas completas, entornos y cachés permanecen locales.

Las distribuciones conservan los datos, figuras y código de cálculo originales.
Las herramientas de empaquetado y verificación incorporan las adaptaciones
documentadas en la [guía de reproducción](docs/reproduction.md), que detalla
la procedencia, las dependencias y los alcances de cada comprobación.

El trabajo utilizó asistencia de IA mediante Codex en código, documentación y
verificaciones. El motor integra NautilusTrader; las fuentes de Binance y las
atribuciones académicas se conservan en la tesina y los paquetes de evidencia.

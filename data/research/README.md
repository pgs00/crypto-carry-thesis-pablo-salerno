# Evidencia e investigaciones

El estudio vigente es continuo: **01/01/2022–31/08/2026 UTC**. Sus
[resultados y figuras](../../entregas/entrega_3/continua/README.md) se publican
desde las corridas verificadas. Este índice clasifica las carpetas; una fecha
de investigación no es el rango del backtest ni una corrida adicional.

## Evidencia vigente

| Carpeta | Uso |
|---|---|
| [continuous-preparation-20260919](continuous-preparation-20260919/README.md) | Preparación, hashes originales y lista exacta de 15 minutos ausentes. |
| [continuous-marks-20260919](continuous-marks-20260919/README.md) | Resultados de ambas estrategias con `futures_scaled` y `last_official`, causalidad y riesgo durante los huecos. |
| [funding-price-sensitivity-20260920](funding-price-sensitivity-20260920/README.md) | Error del precio de funding, posiciones y escenarios ilustrativos P95; distinto de los 15 huecos de velas. |

## Antecedentes y fuentes conservadas

| Carpeta | Motivo de conservación |
|---|---|
| [basis-audit-20260919](basis-audit-20260919/README.md) | Auditoría de las ventanas independientes; su script tiene pruebas y respalda la clasificación de rechazos. |
| [minute-download-20260918](minute-download-20260918/annual-economic-audit.json) | Auditorías financieras, tiempos, recuperación de fuentes y contraste del episodio spot en las ventanas anteriores. |
| [research-scenario-20260918](research-scenario-20260918/funding-resolver-verification.json) | Pilotos y contraste trades/minutos. Sus manifiestos y scripts conservan rutas relativas de reproducción. |
| [funding-calendar-h1-20260918](funding-calendar-h1-20260918/independent-verification.json) | H1 preliminar y verificación independiente de calendario/forecast; no sustituye H1 de la entrega vigente. |
| [funding-proxy-audit-20260918](funding-proxy-audit-20260918/manifest.json) | Fuentes y hashes de la investigación original del proxy de funding. |
| [funding-20260918T132612Z](../../docs/research/funding_api_coverage.json) | Respuestas API originales y procedencia; referenciadas por los inventarios históricos. |
| [funding-followup-20260918](funding-followup-20260918/missing-economic-settlement-marks.json) | Las 4.010 observaciones sin precio oficial y los intentos documentados de recuperación. |
| [funding-provider-access-20260918](../../docs/research/funding_provider_access_20260918.md) | Exploración de proveedores y contraejemplos; no es una dependencia de acceso para reproducir el estudio actual. |
| [fee-archive-followup-20260918](fee-archive-followup-20260918/manifest.json) | Capturas originales con hashes; respaldan límites del conocimiento de tarifas históricas. |
| [trades-2024-01-01](trades-2024-01-01/BTCUSDT-kline-quote-discrepancy-api.json) | Procedencia del piloto de reconciliación. ZIP y checksums de mercado permanecen sólo locales. |

Se revisaron estas carpetas para la presentación. Se conservan las evidencias
únicas y las rutas usadas por scripts, pruebas o manifiestos; no se normalizan
sus originales ni se confunden exploraciones con resultados vigentes. El
[índice documental histórico](../../docs/research/README.md) explica las fuentes.
El [registro de limpieza](../../docs/repository_cleanup.md) enumera los movimientos
y la única copia de código eliminada tras comprobar su identidad.

Los ZIP, Parquet y checksums de mercado usados en investigación no se agregan
a Git. Los archivos locales existentes permanecen en disco; la evidencia
publicada conserva sus hashes y ubicación para quien disponga de las fuentes.

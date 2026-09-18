# Funding sin soporte: prueba cuantitativa de una aproximación

Fecha: 18/09/2026. **El mark exacto sigue faltando en 4.010 cobros, pero una aproximación con datos públicos tiene un impacto directo pequeño en el período donde pudimos contrastarla.** Esta evidencia permite proponer un escenario académico separado. No convierte el precio aproximado en un dato observado ni completa el backtest estricto.

## Datos obtenidos hoy

Se descargaron 114 archivos mensuales oficiales de mark de un minuto: BTCUSDT y ETHUSDT, diciembre de 2021 a agosto de 2026. El mes previo permite consultar el cierre anterior al primer cobro de 2022. Los ZIP suman **117.059.965 bytes**, con SHA-256 contrastado contra los `.CHECKSUM` oficiales. No se usaron claves, cuentas ni soporte. [Fuente y herramientas de descarga oficiales](https://github.com/binance/binance-public-data/tree/master/python).

Los archivos mensuales presentaban 10.095 minutos ausentes. Once archivos diarios oficiales recuperaron 10.080. Quedan **15 minutos ausentes**, también ausentes en cuatro consultas a `/fapi/v1/markPriceKlines`. Ninguno coincide con los minutos necesarios para este contraste de funding. No se rellenaron: limitan la cobertura de un eventual replay de riesgo durante todo el período.

Se conservaron archivos, respuestas, hashes y verificaciones en [el directorio de investigación](../../data/research/funding-proxy-audit-20260918/manifest.json). Los ZIP quedan locales y excluidos de Git. El [script de investigación](../../data/research/funding-proxy-audit-20260918/audit_probe.py) vuelve a comprobarlos y reproduce las tablas; no modifica la entrada operativa del proyecto.

## Contraste con cobros de precio conocido

Se tomaron todos los **6.214 eventos** con mark publicado en las respuestas oficiales previamente guardadas: 3.107 por activo, desde el 31/10/2023 a las 08:00 UTC hasta el cierre de agosto de 2026. Se conservaron los timestamps originales en milisegundos y se calcularon diferencias con `Decimal`.

Dos candidatos:

- **Cierre del minuto previo:** usa una observación anterior al cobro. Es el candidato recomendado para un modelo causal, con disponibilidad y prioridad de eventos explícitas.
- **Apertura del minuto del cobro:** control retrospectivo. El OHLC no indica cuándo ocurrió su primera actualización dentro del minuto; no se presupone disponible antes del cobro para decisiones o riesgo.

| Medida, BTC y ETH juntos | Cierre previo | Apertura del minuto |
|---|---:|---:|
| Cobros contrastados | 6.214 | 6.214 |
| Coincidencias exactas | 2.048 | 4.991 |
| Error absoluto medio de precio, bps | 0,20269 | 0,03524 |
| Percentil 95 del error de precio, bps | 1,04229 | 0,19992 |
| Mayor error de precio observado, bps | 10,22932 | 3,63864 |
| Suma de errores absolutos de funding, ejemplo normalizado en USDT | **0,034261** | **0,005958** |
| Mayor error de un cobro, mismo ejemplo, USDT | 0,000921 | 0,000191 |

Un punto básico es 0,01%. **El ejemplo normalizado mantiene 3.000 USDT de nocional por activo en cada cobro**, definiendo la cantidad de referencia como `3000 / mark_exacto`. No es la cantidad de las carteras simuladas ni su error final de patrimonio.

Para un short perpetuo de cantidad positiva `q`, tasa `r`, mark exacto `M` y aproximación `M_hat`:

```text
funding exacto = q × r × M
diferencia directa = q × r × (M_hat − M)
```

El error de precio se multiplica por la tasa de funding. No se aplica uno a uno al patrimonio. La tabla acumula valores absolutos, sin cancelar diferencias positivas y negativas. El efecto sobre una estrategia completa también puede pasar por caja, margen, sizing y decisiones posteriores; requiere repetir ambas trayectorias.

Hay **180 cobros conocidos cuyo mark queda fuera del high/low de su minuto**. Por eso el rango OHLC tampoco es una cota garantizada del mark interno. No se emplea como tal.

## Escenarios para el tramo sin mark exacto

Se obtuvieron cierre previo y apertura para los **4.010 eventos sin mark**. Son candidatos identificados; no observaciones del precio interno. La suma de tasas absolutas de esos eventos es 0,27742486 entre ambos activos.

Si se supusiera nocional de 3.000 USDT por activo en cada evento y un límite uniforme del error relativo del precio, la suma del error directo de funding quedaría acotada condicionalmente así:

| Límite supuesto del error del mark | Importe ilustrativo máximo acumulado, USDT |
|---|---:|
| 1 bp = 0,01% | 0,08323 |
| 10 bps = 0,10% | 0,83227 |
| 100 bps = 1,00% | 8,32275 |

**No se ha demostrado ninguno de esos límites para 2022–2023.** Son escenarios de sensibilidad, no intervalos de confianza ni garantías. Tampoco limitan el error total de una cartera cuyo nocional cambia o cuyas decisiones se alteran.

El diseño recomendado mantiene los marks exactos donde existen, etiqueta cada precio aproximado donde falta y repite la evaluación posterior usando exacto/aproximado sobre la misma ventana. En el período antiguo, repite perturbaciones adversas y favorables del precio estimado y compara decisiones, exposición y resultados. El escenario debe declarar que cambia el requisito de liquidación histórica exacta.

## Lo que esta prueba habilita y lo que sigue pendiente

La aproximación puede evaluarse sin soporte ni una API comercial. No hace falta descartar automáticamente la muestra 2022–2023 por este único campo. Sí hace falta autorizar y documentar el escenario, completar sus supuestos de reglas y validar el efecto en las dos carteras.

Siguen separados los problemas de ejecución, precios ausentes fuera de los cobros, comisiones y reglas históricas. Descargar velas no reconstruye operaciones individuales ni una demora de un segundo entre patas. Una evaluación por barras necesita reglas de ejecución propias y no se presentaría como el replay original.

Evidencia: [resumen verificable](funding_proxy_feasibility_20260918.json), [comparaciones por evento](../../data/research/funding-proxy-audit-20260918/comparison.json), [recuperación diaria](../../data/research/funding-proxy-audit-20260918/daily-gap-recovery-manifest.json), [consultas REST de huecos restantes](../../data/research/funding-proxy-audit-20260918/rest-gap-recovery-manifest.json). Los datos y reglas ejecutables permanecen separados de esta investigación.

## Otras ofertas de autoservicio revisadas

El [catálogo de CryptoDataDownload](https://api.cryptodatadownload.com/static/catalog/CDD_Data_Catalog.html) anuncia funding histórico y un mark calculado. Las dos rutas de funding/available allí indicadas, consultadas sin credenciales en `api.cryptodatadownload.com`, devolvieron 404; no se obtuvo una muestra antigua ni se acreditó procedencia del mark interno. No se recomienda comprar basándose solo en esa descripción. [CryptoHFTData](https://www.cryptohftdata.com/datasets/binance-funding-rate-data) publica inicio de historia Binance Futures en 2025-06-28 y un esquema de mensajes de mark/funding siguiente; no cubre el faltante 2022–2023. No se compró acceso ni se crearon cuentas.

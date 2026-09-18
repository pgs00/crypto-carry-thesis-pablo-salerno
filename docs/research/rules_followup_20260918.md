# Seguimiento de reglas históricas de Binance — 2026-09-18

Alcance: filtros Spot y perpetuos USD-M, tramos de margen y cargos de liquidación de BTCUSDT/ETHUSDT. Período económico `[2022-01-01, 2026-09-01)`; antecedentes de preparación desde 2020. Complementa [historical_market_rules.md](historical_market_rules.md) y [historical_market_rules.json](historical_market_rules.json). No trata comisiones ordinarias ni funding.

**Resultado: ninguna regla completa ni nueva cadena continua de vigencia para el período económico.** Se agregan una tabla oficial referida a enero de 2020, dos cambios de clearance de 2021, el anuncio del mínimo nocional USD-M de 2021 y una explicación de la base de liquidación en un blog fechado en 2022. El [JSON complementario](rules_followup_20260918.json) separa hechos confirmados parcialmente, explicación sin versión histórica recuperada y una pista de buscador. No es entrada para RuleBook.

## Período económico: qué aporta la nueva búsqueda

El blog oficial [Three Misconceptions About Liquidations in Binance Futures](https://www.binance.com/en/blog/futures/5845477141003990750), fechado **2022-12-23**, expresa el clearance como nocional de la posición multiplicado por la tasa de liquidación. No publica allí tasas para BTC/ETH ni define el precio que valora ese nocional. Por ello aporta una explicación sobre la **base nocional**, pero no cierra `execution_notional`, `mark_notional` ni una tasa histórica concreta. El cuerpo fue abierto hoy; no se obtuvo una versión archivada que pruebe que esa fórmula ya figuraba en la publicación original. No se asigna `known_from=2022-12-23`.

No se verificó un anuncio posterior que permita fijar **0.5% para BTC y 1% para ETH**, ni otra pareja de tasas, como válida durante 2022–2026. Tampoco se recuperó el cambio intermedio del primer cap ETH de 50,000 a 300,000 USDT señalado en el inventario anterior. Las búsquedas de tick/step/nocional volvieron a fuentes ya registradas o a contratos distintos; no produjeron una captura histórica completa de `exchangeInfo`.

## Antecedentes de preparación: no extrapolar a 2022

### Especificaciones referidas al 2020-01-01

El informe oficial [Overview of Binance Futures in 2019](https://www.binance.com/en/blog/all/421499824684900356), publicado con fecha **2020-01-16**, identifica su tabla 1 como datos al **2020-01-01**. La [imagen original](https://public.bnbstatic.com/image/cms/blog/20200113/39784528-f9cc-4388-aff4-5f6a872c60a9.png) fue descargada en memoria e inspeccionada visualmente:

| Perpetuo | Unidad contractual | Tick, USDT | Granularidad mínima, unidades contractuales | Margen inicial base | Mantenimiento base |
| --- | --- | --- | --- | --- | --- |
| BTC/USDT | 1 BTC | 0.01 | 0.001 | 0.8% | 0.4% |
| ETH/USDT | 1 ETH | 0.01 | 0.001 | 1.3% | 0.65% |

Es una tabla de especificaciones con fecha de referencia, no una respuesta de API. La granularidad no certifica los campos separados `LOT_SIZE`, `MARKET_LOT_SIZE`, `minQty` o `maxQty`. Los porcentajes base no incluyen límites de tramos ni deducciones. La fecha de referencia no especifica hora ni zona; no se convierte a medianoche UTC. No se establece continuidad posterior.

SHA-256 de la imagen obtenida: `7f3d37dceccf5fdf218f32a7fc7b150a1c55cf23c28df6bdfb4fa6fcc5f0cbc5` (42,069 bytes). Sólo se conserva el hash y la transcripción, no una copia local del activo.

### Cambios explícitos de cargos de liquidación

| Publicación mostrada, zona no declarada | Vigencia explícita UTC | BTCUSDT, antes → después | ETHUSDT, antes → después | Fuente |
| --- | --- | --- | --- | --- |
| 2021-01-11 04:58 | 2021-01-11 05:00 | 0.50% → 1.00% | 0.75% → 1.50% | [Lanzamiento BTCBUSD, apartado adicional USD-M](https://www.binance.com/en-PH/support/announcement/detail/3d974ead7acf447bab862e795ee832bb) |
| 2021-02-07 03:50 | 2021-02-07 04:00 | 1.00% → 2.00% | 1.50% → 3.00% | [Cambio de insurance clearance](https://www.binance.com/en/support/announcement/detail/aeeccb6d332a4e74a51c2ac05f9078e5) |

Ambos cuerpos fueron abiertos. Aunque el primer título trata BTCBUSD, su tabla adicional nombra **BTCUSDT y ETHUSDT USD-M**: no se trasladó una regla BUSD a USDT. El cambio de clearance de enero ocurre el día 11; el lanzamiento BTCBUSD del mismo anuncio ocurre el día 12 y no es la fecha de vigencia del cargo.

Estos anuncios contradicen la extensión constante de las tasas de noviembre de 2020 a toda la preparación. **No prueban persistencia ni dentro de los intervalos entre anuncios ni hasta enero de 2022.** No se verificaron la base de cálculo histórica ni el tratamiento de posiciones existentes en estos dos cambios. La publicación intradía UTC y la versión original del artículo siguen sin certificar.

### Mínimo nocional USD-M de 2021

El [anuncio de reglas USD-M](https://www.binance.com/en/support/announcement/detail/1d762daf60dd417f9d8a05d44b06a25c), publicado con etiqueta **2021-02-23 14:11**, fija el umbral de **5 USDT por orden** desde **2021-02-24 03:00:00 UTC** y exime las órdenes **Reduce-Only**. También advierte que ese umbral puede modificarse sin anuncio previo. No enumera campos API ni aporta un snapshot de cada símbolo. La exención documentada impide tratar el mínimo como universal para cualquier cierre; no se extrapola su persistencia al período económico.

## Pistas y vías que no cerraron evidencia

- El buscador expuso el [anuncio de clearance del 2021-06-10](https://www.binance.com/en/support/announcement/detail/6bd7a166980648469ab771b5835847c3) con un cambio BTCUSDT de 0.60% a 1.20%, efectivo a las 04:00 UTC, y publicación mostrada 02:21. **Queda como pista no promovida**: la apertura inglesa redirigió al índice; variantes regionales fallaron y una lectura HTTP directa devolvió `202` con cuerpo vacío. No se creó un evento confirmado con ese resultado de búsqueda.
- Las consultas CDX de Wayback para `fapi.binance.com/fapi/v1/exchangeInfo*` (2022–2026) y la FAQ `360033525271` (2022–2025) devolvieron **HTTP 503**. No se obtuvieron capturas; esto no demuestra que no existan.
- La ruta pública CMS `/bapi/composite/v1/public/cms/article/detail` ensayada devolvió **404**. No resolvió la zona horaria de publicación ni entregó versiones previas.
- El [anuncio de liquidación Margin de agosto de 2024](https://www.binance.com/en/support/announcement/detail/be7fc4800bd54aac8f77501300aeb728) corresponde a préstamo Spot Margin, no al perpetuo USD-M aislado; se excluyó. Asimismo, especificaciones de futuros trimestrales no certifican las del perpetuo aunque compartan BTC/ETH como subyacente.
- Publicaciones de usuarios en Binance Square y calculadoras de terceros no se adoptaron como reglas oficiales. Una página alojada en `binance.com` no es por sí sola una declaración de Binance.

## Faltantes que permanecen

1. Baseline completo y cambios de `exchangeInfo` para ambos mercados, incluidas banderas MARKET, min/max qty y límites por orden. No hay nueva evidencia suficiente de filtros Spot.
2. Cadena completa de tramos BTC/ETH del período económico, sus deducciones históricas publicadas y tratamiento de cohortes anteriores a los cambios.
3. Tasas de clearance BTC/ETH válidas en cada intervalo 2022–2026; precio de la base nocional, excepciones y comisiones concurrentes durante la liquidación.
4. Evidencia contemporánea para `known_from`, horas UTC de publicación y enmiendas. La fecha de un encabezado actual no certifica la disponibilidad histórica de su contenido.

Las siguientes vías útiles requieren capturas históricas de API con procedencia o versiones archivadas accesibles. Una API actual o una nueva búsqueda sin resultados no permiten llenar los faltantes. Este seguimiento sólo crea los dos archivos de investigación; no modifica datos, código, configuración, reglas ejecutables ni la descarga en curso.

# Propuesta pendiente: cuenta hipotética ligada a SOFR

Estado: **pendiente_aprobacion_benchmark**. No se calcularon capital, retorno,
P&L ni CAGR remunerados. La recomendación se elige por trazabilidad y alcance;
no se compararon rendimientos acumulados de candidatos para seleccionarla.

## Recomendación y alternativa examinada

Recomiendo una **cuenta hipotética bruta en USD que devenga SOFR realizada**,
con 10.000 USD iniciales y capitalización según la convención oficial de días.
No es una cuenta del New York Fed, un depósito accesible ni una remuneración
ofrecida por Binance. Permite medir un costo de oportunidad monetario transparente.
SOFR mide financiación overnight garantizada por Treasuries; su publicación
es pública. [Fuente primaria: descripción SOFR](https://www.newyorkfed.org/markets/reference-rates/sofr).

La única alternativa examinada fue **SGOV, iShares 0–3 Month Treasury Bond ETF**,
instrumento real USD iniciado el 26/05/2020. Su página informa NAV a las 16:00 ET,
distribuciones y retorno con reinversión; gastos vigentes 0,09%, ya descontados
en las medidas de desempeño del fondo. Esa cifra actual no acredita los gastos
de toda la historia. Comprar requiere intermediario, spread, comisiones y
reglas de acceso. No se acreditó acceso particular del inversor ni un mínimo
efectivo (fracciones dependen del intermediario). No se descargó ni autenticó
su serie diaria completa de retorno total/dividendos. Se descarta **para este
bloque**, por agregar decisiones de ejecución y acceso al comparador. Su precio
sin ajustar no sustituiría dividendos ni retorno total. No se concluye que rinda
más o menos que SOFR. [Fuente primaria del emisor](https://www.ishares.com/us/products/314116/ishares-0-3-month-treasury-bond-etf).

## Datos comprobados y archivos originales

La consulta pública exacta es
[NY Fed API: SOFR, 30/12/2021–01/09/2026](https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?startDate=2021-12-30&endDate=2026-09-01).
Se archivaron sus bytes en `fuentes_publicas/sofr_serie.json`: 1.166 registros,
fechas únicas, todos tipo SOFR, sin percentRate ausente, brecha máxima de cuatro
días calendario. Hay observación del 31/12/2021 para el comienzo en sábado;
31/08/2026 para el devengamiento final y 01/09/2026 para comprobar la frontera.
No se usará la tasa efectiva 01/09/2026 dentro de la muestra.

Campos: `effectiveDate` (fecha económica, no hora de publicación), `type`,
`percentRate` (% anual; convertir a fracción dividiendo por 100) y
`revisionIndicator`. Los percentiles/volumen se conservan como parte del
original pero no son tasas a invertir. No se emplearán promedios 30/90/180d
como si fueran rendimientos de cada día.

`fuentes_publicas/fuentes.json` conserva URL original/final, consulta UTC,
estado HTTP, tamaño, SHA-256 y cabeceras de fecha/modificación disponibles.
`cobertura_sofr.json` enumera observaciones de frontera y los **53 días de
semana sin publicación** detectados; no los codifica como tasa cero.

## Convención de devengamiento propuesta

La fuente define ACT/360, composición entre días hábiles y devengamiento simple
para los días inhábiles cubiertos por la tasa precedente. Una SOFR se publica
al día hábil siguiente; el índice lleva fecha valor de publicación. La política
prevé publicación alrededor de 08:00 ET y posibles revisiones del mismo día
alrededor de 14:30 ET. El calendario distingue cierre completo y cierre temprano.
La metodología consultada indica actualización 06/04/2026.
[Metodología vigente](https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates).
La publicación de promedios/índice comenzó el 02/03/2020.
[Comunicado fechado](https://www.newyorkfed.org/markets/opolicy/operating_policy_200302).

**Decisiones del estudio que se pide aprobar:**

- Intervalo exacto UTC [2022-01-01,2026-09-01), idéntico a BASE. Las fechas
  económicas de SOFR se mapean a días UTC como convención comparativa; no se
  afirma que un repo real se inicia o liquida a medianoche UTC.
- Para un bloque de tasa anual decimal r y n días calendario: factor
  `1 + r*n/360`. Capitalizar una vez al terminar el bloque, no cada sábado,
  domingo o feriado. Durante el bloque, saldo devengado = principal del bloque
  por `1 + r*d/360`, donde d son días transcurridos. El 29 de febrero cuenta
  como un día real; la base sigue siendo 360.
- Empezar el sábado 01/01/2022 con 10.000, sin interés del 31/12. Aplicar la tasa
  efectiva 31/12 exclusivamente al tramo 01/01–03/01 (dos días), conforme a la
  convención de comienzo inhábil. No mover el inicio al lunes ni simular una
  inversión anterior. El último bloque usa 31/08 hasta 01/09, sin interés posterior.
- Emparejar cada cierre carry `23:59:59.999999999` con el saldo remunerado al
  término de ese día calendario. Es una convención diaria explícita que absorbe
  el nanosegundo de representación; no agrega un día ni anticipa una tasa para
  operar. Las tasas realizadas publicadas después se usan retrospectivamente.
- Conservar principal, devengamiento pendiente y saldo al atravesar enero o los
  cortes H3. Un corte dentro de un bloque inhábil no capitaliza anticipadamente
  ni reinicia 10.000. Retornos de tramos se obtienen de sus saldos heredados.
- Usar la versión final del archivo consultado, incluidas revisiones indicadas;
  no afirmar reconstrucción de vintages disponibles en cada instante. Una
  fecha económica por sí sola no prueba disponibilidad ex ante.

## Moneda, costos, acceso y riesgos

Supuesto de comparabilidad: **1 USDT = 1 USD** durante toda la muestra,
sin costos de conversión, custodia, intermediación, impuestos ni spread
añadidos a esta referencia hipotética **bruta**. Son supuestos del estudio,
no costos netos verificados, ni convertibilidad garantizada. Se comparan
unidades nominales bajo esa paridad, sin equiparar riesgo de USDT, exchange,
repo, Tesoro o intermediario. No se ofrece una recomendación de inversión personal.

La cuenta sintética no tiene mínimo comercial ni contrato de acceso; los
10.000 son escala analítica. No mide precio de liquidación, pérdidas por spread,
liquidez de un producto o riesgo de contraparte. La suavidad de la trayectoria
contable no se presentará como ausencia de riesgo. No corresponde inventar
Sharpe o volatilidad cero. SGOV, si se eligiera otro día, requeriría otra ficha
con retorno total, dividendos, calendario bursátil y costos de acceso.

## Controles y pendientes concretos antes del cálculo

La historia descargada cubre las fronteras; aún falta contrastar los 53 días de
semana sin publicación con el calendario oficial y sus excepciones. No se
permitirá arrastrar una tasa sobre un día hábil cuyo dato falte. La ausencia
inexplicada detendrá el benchmark, sin alterar los diagnósticos terminados.
También se cotejará el resultado de composición en fronteras hábiles con el
SOFR Index oficial como control, tolerando únicamente su redondeo publicado;
esa serie aún no se descargó ni calculó. Estos son controles de la ejecución
posterior, no permisos para rellenar faltantes o modificar el método.

Después de aprobar esta ficha: pruebas de unidades, base de días, inicio
inhábil, feriados, bisiesto, revisiones, frontera final y saldos heredados;
luego cartera separada y curvas, P&L, retorno y CAGR sobre los mismos ocho
períodos. No habrá transferencias al carry, remuneración de su caja/garantías,
cambio del Sharpe RF=0 ni sustitución de la permanente en H2.

Decisión puntual solicitada: aprobar esta cuenta SOFR hipotética bruta,
ACT/360 y la paridad nominal USDT/USD, con el protocolo y controles anteriores.
La ejecución posterior irá en una nueva versión que enlace este paquete sellado.

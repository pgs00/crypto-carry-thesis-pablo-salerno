# Protocolo aprobado y controles antes del cálculo

La cuenta separada comienza el 01/01/2022 con 10.000 USD y termina el
01/09/2026 00:00 UTC. Se usa la serie SOFR del paquete previamente aprobado,
sin reemplazar su snapshot. La paridad nominal 1 USDT=1 USD permite comparar
unidades del estudio y no equipara riesgos ni garantiza convertibilidad.

## Calendario y fuentes

El calendario se deriva de las recomendaciones oficiales de SIFMA para
U.S. government securities, conservando la distinción cierre total/temprano.
Se leen secciones 2022–2025 del archivo histórico y 2026 de la página vigente.
La sección 2022 acredita 31/12/2021 como cierre temprano, no feriado completo.
El calendario no se infiere de la presencia/ausencia de tasas.

Los avisos del NY Fed prevalecen: 07/04/2023 y 03/04/2026 son excepciones sin
SOFR ni Index; 09/01/2025 conserva publicación pese al duelo nacional.
Para cada fecha entre 30/12/2021 y 01/09/2026 se registra su estado esperado,
fuente, presencia en SOFR y en Index. Un hábil sin tasa/Index, un registro en
inhábil, una fecha duplicada o tipo/campo inválido bloquea el cálculo.
No se impone un calendario bancario genérico ni se imputan ceros.

## Cuenta y cortes

Cada fecha hábil consecutiva delimita un bloque, aunque las tasas sean iguales.
Tasa anual decimal=percentRate/100; factor=1+r*n/360. Interés simple dentro
del bloque y capitalización al llegar al siguiente hábil. Los saldos diarios
incluyen principal de bloque más interés devengado, sin capitalización prematura.

El bloque fuente 31/12/2021–03/01/2022 tiene tres días, pero el bloque de la
cuenta comienza el sábado 01/01 y sólo devenga dos. Con SOFR 0,05% anual,
factor inicial=1+0,0005*2/360; interés sobre 10.000=1/36 USD. El cierre del
01/01 acumula 1/72 USD; el cierre del 02/01, 1/36. No se inventa un Index
oficial para el sábado ni se usa el cociente Index(03/01)/Index(31/12) como
rendimiento de esos dos días, porque ese cociente abarca tres días.

Un cierre carry 23:59:59.999999999 UTC se empareja con el saldo al término
del mismo día calendario, según la convención diaria aprobada. Se conserva
el origen de tasa y su fecha de publicación esperada al siguiente hábil;
se usa la tasa realizada retrospectivamente, no como señal disponible antes.
RevisionIndicator se preserva. Los originales son snapshots finales públicos,
no vintages históricos certificados ni horas reales de publicación capturadas.

En cada año/corte H3 se hereda saldo, principal y devengamiento pendiente.
Un corte dentro de un bloque no capitaliza ni reinicia 10.000. El 29 de febrero
cuenta como día real y el denominador de intereses sigue siendo 360.
P&L=saldo final−saldo inicial; retorno=saldo final/saldo inicial−1;
CAGR=(saldo final/saldo inicial)^(365/días)−1. **CAGR365 es distinto de ACT/360.**

## Contraste oficial, fijado antes de interpretar

Se verificará cada bloque hábil posterior al 03/01/2022 y cada composición
acumulada desde esa fecha hasta el 01/09/2026 con SOFR Index oficial. El
primer tramo inhábil se valida directamente por la fórmula anterior.

El Index publicado tiene ocho decimales. Para valores publicados x e y,
q=0,00000001 y e=q/2, el factor compatible con redondeo al más cercano está
en [(y−e)/(x+e), (y+e)/(x−e)]. La composición independiente debe caer en ese
intervalo. Se guardan ambos límites y el error frente a y/x. No se elige una
tolerancia a partir del error observado ni se altera la tolerancia monetaria
original de 1E-8. Aritmética Decimal a 50 dígitos, sin redondeo diario de caja.
El redondeo a centavos se aplica sólo para presentación, no para capitalizar.

## Comparación y límites

Se reutilizan literalmente métricas/diarios/H2 de las dos BASE verificadas.
Carry es neto de costos modelados; SOFR es una referencia hipotética bruta,
sin costos de FX, intermediación, custodia, impuestos o spread añadidos.
No se acredita producto disponible, cuenta del NY Fed, remuneración de exchange,
acceso contractual, equivalencia de riesgos ni rendimiento garantizado.

No se calcula un Sharpe remunerado ni se cambia RF=0 de H2. No se transfiere
dinero al carry ni se remunera su caja o garantías. No se recalculan ciclos,
restricciones, exposición ni riesgo intradía. La serie hipotética no mide
precios de liquidación: una trayectoria suave no demuestra ausencia de riesgo.

El nuevo sello enlaza el anterior por hash. Las auditorías finales son externas,
los CLI rechazan sobrescritura y se prueban desde una copia fuera del checkout.

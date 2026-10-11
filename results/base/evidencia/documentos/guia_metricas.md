# Guía de métricas corregidas

Todas las ventanas son `[inicio, final)` UTC. Los intervalos usan nanosegundos
enteros; segundos = (end_ns − start_ns) / 1000000000 con Decimal. Las fracciones
son duraciones / segundos calendario (0,01 = 1%). No se redondea antes de evaluar.

## Entrada y clasificación E3

`positions.parquet` contiene estados del ledger registrados en transiciones,
fills y cierres diarios; el serializador conserva su orden y añade los finales.
No se usa sólo el snapshot final ni una reconstrucción a partir de equity diaria.
La auditoría de linaje cruzó todos los cambios de cantidades con ledger y el último
estado de cada timestamp con los eventos: no faltan metadatos en las doce carteras.

Para cada símbolo, ordenar establemente por `time_ns`, tomar la última fila de
cada timestamp y clasificar primero toda la muestra. Estado inicial vacío conforme
al contrato de las corridas. Con spot S, corto Q, residuo conocido R y tolerancia
de cobertura persistida en la configuración:

1. `dust`: S > 0, Q = 0 y (`dust_spot` > 0, estado FLAT/COOLDOWN, o S ≤ R).
   Actualizar R = S; conservar R entre ciclos y cortes.
2. `covered`: no fue polvo, S > 0, Q > 0 y abs(S − Q) / S ≤ tolerancia.
3. `unhedged`: no fue polvo/cobertura y S > 0 o Q > 0.
4. `flat`: ambas cantidades vacías.

Un aumento de spot sobre el residuo conocido durante una nueva entrada sigue
activo; una posición cubierta con residuos sigue cubierta. Aperturas/cierres
parciales y cortos sin spot no desaparecen del indicador. Suspensión o falta de
volumen por sí solas no determinan polvo. No se usan reglas actuales ni umbrales
monetarios. Los campos imprescindibles faltantes ocasionan un error identificable.
La ausencia habitual de `dust_spot` en eventos no impide clasificar cuando están
disponibles el estado y la historia completa.

## Duraciones y particiones

Por activo: `covered + unhedged + dust + flat = calendar`.
`invested = covered + unhedged`. El polvo se excluye de ambos indicadores activos.

Por cartera se integran celdas temporales comunes, una sola vez cada celda:

| Columna de segundos | Definición |
| --- | --- |
| invested_seconds | Algún activo covered o unhedged |
| covered_seconds / any_covered_seconds | Algún activo covered |
| unhedged_seconds / any_unhedged_seconds | Algún activo unhedged |
| both_covered_seconds | BTC y ETH covered simultáneamente |
| dust_seconds | Algún activo dust, incluso si el otro está activo |
| dust_only_seconds | Hay polvo y ningún activo está activo |
| no_active_seconds / cash_or_dust_seconds | Ningún activo covered/unhedged |
| no_inventory_seconds / cash_seconds | Todos los activos flat, sin cantidades |
| raw_invested_seconds | Alguna cantidad spot/corto positiva, incluido polvo |
| raw_unhedged_seconds | Alguna posición bruta con descalce relativo > tolerancia |

`invested + no_active = calendar`; `no_active = dust_only + no_inventory`;
`raw_invested = invested + dust_only`. Las fracciones no exceden uno.
Los dos contadores any_covered y any_unhedged pueden solaparse entre activos,
por lo que no se suman como categorías excluyentes. `dust_seconds` tampoco se
suma al tiempo activo para obtener el bruto: se usa `dust_only_seconds`.
Por activo, dust_only coincide con dust y no_inventory con flat.

El alias heredado `cash_seconds` significa sólo ausencia de inventario; no
certifica composición patrimonial en efectivo. Residuos y su riesgo de precio
siguen en la contabilidad. Utilización diaria = (valor spot + collateral) / equity,
sin ningún ajuste por esta corrección. Slippage sigue siendo informativo y no se
resta dos veces. No se cambia ningún resultado financiero.

## H2

`favorable` requiere CAGR condicional finito > 0 y dos Sharpes finitos con
Sharpe condicional > permanente. `no_favorable` exige que los tres sean evaluables
y que falle alguna de esas dos condiciones. `no_concluyente` indica valores
faltantes/no finitos, cartera faltante, cobertura incompleta o ventanas distintas.
ND queda vacío con motivo; las condiciones que sí se conocen se conservan.
No se exige Sharpe positivo ni CAGR superior al permanente. Las parejas se
identifican por escenario, período y ventana; duplicados se rechazan.

CSV conserva punto decimal, coma delimitadora y UTF-8; segundos y razones son
Decimal. Los nombres `old_*` designan el informe padre; `raw_*`, el bruto separado;
las columnas operativas principales siguen la definición editorial de E3.

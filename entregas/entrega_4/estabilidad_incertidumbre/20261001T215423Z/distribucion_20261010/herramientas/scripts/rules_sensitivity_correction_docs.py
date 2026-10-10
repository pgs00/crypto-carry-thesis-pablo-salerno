"""Documents for the exposure/H2 derivative; no economic calculations or writes to sources."""

import csv
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal as D


def table(rows, columns):
    def cell(value):
        if value is None or value == "":
            return "ND"
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    lines.extend("| " + " | ".join(cell(row.get(c)) for c in columns) + " |" for row in rows)
    return "\n".join(lines)


def write_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(content.rstrip() + "\n")


def write_documents(destination, tables, parent_hash, e3_checks, figures):
    full = [r for r in tables["metricas_cartera_periodo"] if r["period"] == "full"]
    differences = [r for r in tables["antes_despues"] if r["period"] == "full"]
    h2 = tables["h2"]
    counts = Counter(r["verdict"] for r in h2)
    changes = [r for r in tables["h2_cambios"] if r["changed"]]
    base = [r for r in full if r["scenario"] == "BASE_E3"]
    compact = []
    for row in differences:
        compact.append(
            dict(
                scenario=row["scenario"],
                strategy=row["strategy"],
                bruto_pct=f"{D(str(row['raw_invested_fraction'])) * 100:.8f}",
                activo_E3_pct=f"{D(str(row['invested_fraction'])) * 100:.8f}",
                sin_cobertura_activa_s=row["unhedged_seconds"],
                solo_polvo_s=row["dust_only_seconds"],
                H2_antes=row["h2_before"],
                H2_ahora=row["h2_after"],
            )
        )
    financial = [
        dict(
            scenario=r["scenario"],
            strategy=r["strategy"],
            run_id=r["run_id"],
            equity_final=r["final_equity_usdt"],
            CAGR=r["cagr"],
            Sharpe=r["sharpe"],
            drawdown=r["max_drawdown"],
        )
        for r in full
    ]
    with (destination / "comparacion/h3_regimen.csv").open(encoding="utf-8", newline="") as handle:
        h3 = list(csv.DictReader(handle))
    h3_verdicts = sorted({r["h3_descriptive"] for r in h3})
    created = datetime.now(UTC).isoformat()
    figure = (
        "![Tiempo invertido y exposición sin cobertura](figuras/exposicion.png)\n"
        if figures
        else ""
    )
    report = f"""# Corrección de exposición y H2 de la primera sensibilidad de reglas

Versión técnica preliminar, pendiente del feedback del profesor. Generada {created}.
Corrección metodológica del reporte de doce carteras ya existentes; no es otra
sensibilidad ni una nueva ejecución económica. El paquete padre y la Entrega 3
presentada conservan todos sus bytes. Esta entrega nueva es local; no acredita
publicación de la corrección en GitHub.

## Qué se corrigió y por qué

El informe padre calculó exposición desde cantidades del ledger y contó cualquier
saldo positivo, incluidos residuos no negociables. Ese contador bruto no reproduce
el indicador editorial presentado en E3. El ledger a solas no conserva los estados
que E3 utiliza para distinguir polvo. Se recuperó la trayectoria completa de
`positions.parquet`, su orden persistido y el clasificador archivado de E3.

H2 se evaluaba únicamente por diferencia de Sharpe. Ahora exige conjuntamente
CAGR condicional definido, finito y estrictamente positivo, y Sharpe condicional
definido, finito y estrictamente superior al permanente del mismo escenario,
período y ventana comparable. No exige Sharpe positivo ni CAGR superior al permanente.
Las métricas se comparan sin redondear. El caso sintético CAGR −0,01 y Sharpes
−0,5 / −1 reproduce el defecto previo y ahora da `no_favorable`.

La corrección reemplaza la interpretación y las tablas de exposición/H2 de
`20260925T005436Z/comparacion/reporte.md`, `exposicion_periodo.csv`, `h2.csv` y
las columnas operativas de métricas/deltas. No reescribe esas fuentes selladas.
Las afirmaciones antiguas de que contar polvo coincidía con E3 quedan reemplazadas
por la definición de esta versión. Las notas «sin commit ni push» del informe
anterior describen aquella sesión, no el estado de publicación actual.

## Comparación de las doce carteras

Muestra completa `[2022-01-01, 2026-09-01)` UTC. Porcentajes sólo redondeados para
esta vista; segundos exactos y todos los cortes en [antes_despues.csv](antes_despues.csv).
Cada fila conserva el run_id original en ese CSV y en el registro de corridas.
Bruto y activo son uniones temporales de BTC y ETH, sin doble conteo.

{table(compact, list(compact[0]))}

{figure}

Se mantienen por separado el bruto con cualquier cantidad positiva, tiempo activo,
tiempo con algún residuo, tiempo únicamente con polvo y tiempo sin inventario.
«Sin posición activa» admite residuos y no equivale a efectivo puro. El contador
de algún activo cubierto puede solaparse con el de algún activo sin cobertura:
su suma no es el tiempo invertido. La [guía](../documentos/guia_metricas.md) explicita
particiones, unidades y fracciones.

## Equivalencia exacta con E3

{
        table(
            [
                dict(
                    strategy=r["strategy"],
                    invested_seconds=r["invested_seconds"],
                    calendar_seconds=r["calendar_seconds"],
                    porcentaje=D(str(r["invested_fraction"])) * 100,
                    unhedged_seconds=r["unhedged_seconds"],
                )
                for r in base
            ],
            ["strategy", "invested_seconds", "calendar_seconds", "porcentaje", "unhedged_seconds"],
        )
    }

{
        table(
            e3_checks,
            [
                "strategy",
                "intervals_checked",
                "summaries_checked",
                "exact",
                "terminal_difference_ns",
            ],
        )
    }

Los intervalos y segundos se contrastan contra las tablas archivadas de E3,
sin tolerancia numérica. Los porcentajes 28,32% y 98,21% son controles de redondeo,
no objetivos usados para clasificar. La fracción exacta es segundos activos /
147225600; los decimales se conservan con la precisión Decimal del posprocesamiento
original. El final exclusivo es `2026-09-01T00:00:00.000000000Z`; el snapshot
terminal ocurre un nanosegundo antes. No hay discrepancia terminal con E3.
Usar erróneamente el timestamp terminal como final exclusivo perdería 1 ns:
polvo/sin actividad en la condicional y cobertura/actividad en la permanente.

El [episodio del 24/03/2023](episodio_2023_03_24.csv) conserva 7260 segundos
(121 minutos) activos sin cobertura en ETH condicional y BTC/ETH permanente.
La unión de cartera es 7260 segundos en cada una. No se confunde este episodio
con toda la exposición sin cobertura de la muestra.

## H2 completo y datos no evaluables

Se evaluaron {len(h2)} pares, seis escenarios y ocho períodos: {dict(counts)}.
Cambiaron {len(changes)} veredictos respecto del padre. Las cifras completas,
ambos run_id, límites, CAGR condicional, Sharpes, diferencia, booleanos y motivos
figuran en [h2.csv](h2.csv); la comparación de todos los veredictos está en
[h2_cambios.csv](h2_cambios.csv).

{
        table(
            [r for r in h2 if r["period"] == "full"],
            [
                "scenario",
                "conditional_cagr",
                "conditional_sharpe",
                "permanent_sharpe",
                "cagr_positive",
                "sharpe_superior",
                "verdict",
                "reason",
            ],
        )
    }

Los casos no concluyentes son explícitos:

{
        table(
            [r for r in h2 if r["verdict"] == "no_concluyente"],
            [
                "scenario",
                "period",
                "conditional_cagr",
                "conditional_sharpe",
                "permanent_sharpe",
                "cagr_positive",
                "sharpe_superior",
                "reason",
            ],
        )
    }

`no_favorable` significa que, con los tres valores evaluables, no se cumplen
simultáneamente ambas condiciones; no implica automáticamente evidencia contraria.
`no_concluyente` conserva cada componente que sí puede evaluarse y registra
faltantes, métricas no finitas, cobertura incompleta o ventanas distintas.
Un booleano desconocido queda vacío en CSV, nunca se transforma en falso o cero.
Las claves duplicadas se rechazan. `full_baseline_coverage=False` de las corridas
prescritas no se interpreta como cobertura temporal incompleta: esa bandera exige
reglas históricas certificadas. Se comprueban fechas y registros diarios efectivos.

## Resultados financieros, H1 y H3 preservados

{table(financial, list(financial[0]))}

Los {len(tables["metricas_cartera_periodo"])} registros cartera/período conservan
literalmente todas las columnas no afectadas: equity, P&L y componentes, retornos,
CAGR, Sharpe, volatilidad, drawdown, utilización diaria, margen y eventos.
[preservacion_financiera.csv](preservacion_financiera.csv) compara los valores
antes/después; [preservacion_tablas.csv](preservacion_tablas.csv) compara bytes de
las tablas preservadas y del índice de corridas. Excluir polvo del tiempo operativo
no elimina unidades, valuación ni riesgo de precio de equity y P&L.

[H1 resumen](h1_resumen.csv), [H1 invariancia](h1_invariancia.csv),
[H3 diario](h3_diario.csv), [H3 invariancia](h3_invariancia.csv) y
[H3 por régimen](h3_regimen.csv) son copias binarias del padre, con sus valores
y procedencias originales. Los estados descriptivos H3 conservados son
{", ".join(h3_verdicts)}. No se reinterpretan como resultados fuera de muestra.
Los [deltas](deltas.csv) conservan las comparaciones financieras; sólo se actualizan
los indicadores operativos afectados y se agregan los diagnósticos de residuos.

## Evidencia, supuestos y límites

Evidencia: trayectorias, metadatos y resultados ejecutados conservados en el padre;
tablas y código editorial E3 autenticados en [referencia_e3](../referencia_e3/).
Supuestos: siguen vigentes las reglas prescritas, aproximaciones `futures_scaled`,
promoción observada y límites de ejecución de minuto del protocolo padre. FUT4
continúa siendo un supuesto constante, no una fecha histórica inferida.
Resultado ejecutado ahora: posprocesamiento, pruebas y verificaciones offline.
No se ejecutaron carteras ni se descargaron mercados/fuentes en esta corrección.

Las doce trayectorias contienen los metadatos necesarios; no hay intervalos con
clasificación pendiente. Una fuente que perdiera estado, cantidades o cobertura
se rechaza con su intervalo y símbolo; no se inventa un umbral monetario.
La investigación de reglas sigue parcial: esta corrección no agrega evidencia
para cerrar fechas históricas ni constituye una nueva tanda de sensibilidad.

## Procedencia y verificación

Manifiesto padre SHA-256: `{parent_hash}`.
[procedencia.json](../procedencia.json) fija entradas y versión `exposure_h2_v2`;
[procedencia_corridas.csv](procedencia_corridas.csv) separa el hash del motor
original de la identidad del posprocesador actual. El producto requiere el padre
íntegro por argumento; no es autocontenido. No necesita datos masivos de mercado,
Git, red ni el motor. La verificación v2 requiere PyArrow para leer las posiciones.

El [resultado de construcción](../verificacion_construccion.json) conserva las
comparaciones realizadas al construir. La verificación independiente se ejecuta
después del sello y guarda su resultado en una ruta nueva externa. Comprueba
semántica de H2, clasificación, duraciones, uniones, cuadros y preservación,
además de hashes. El verificador archivado del padre conserva su alcance v1;
su aprobación por sí sola no acredita esta corrección. Véanse los comandos y
dependencias en el [README](../README.md).
"""
    write_text(destination / "comparacion/reporte.md", report)
    write_text(
        destination / "documentos/guia_metricas.md",
        """# Guía de métricas corregidas

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
""",
    )
    write_text(
        destination / "README.md",
        f"""# Corrección de exposición y H2 — versión 2

Entrega técnica preliminar. Leer el [reporte corregido](comparacion/reporte.md),
la [tabla antes/después](comparacion/antes_despues.csv) y la
[guía de métricas](documentos/guia_metricas.md).

Se reutilizan doce carteras y sus run_id. No hay simulaciones nuevas. Este paquete
es derivado y depende explícitamente del paquete sellado `20260925T005436Z`.
SHA-256 de su manifiesto: `{parent_hash}`. No se duplican corridas grandes.
Todos los miembros del padre se comprueban para la verificación completa.

## Verificar offline desde cualquier ruta

Con Python 3.14 y PyArrow del entorno del proyecto, indicar rutas absolutas o
relativas al directorio actual. Se puede mover tanto este paquete como el padre.

```powershell
python -B -X utf8 <correccion>/herramientas/verify_rules_sensitivity_correction.py `
  --package <correccion> --parent <paquete_padre> --output <auditoria_nueva_externa.json>
```

El resultado debe decir `passed`. La salida es opcional, debe ser nueva y quedar
fuera de ambos paquetes. El comando no depende de Git, rama, HEAD, índice, red,
datos masivos ni motor. PyArrow es indispensable para verificar contra Parquet;
no se omite semántica si falta. No usar `-S`, que elimina dependencias instaladas.
El código v2 verifica clasificación y agregación independientemente del constructor,
H2 completo y todos los valores/tablas preservados; también ejecuta el verificador
original del padre bajo su alcance histórico. v2 no acepta degradarse a v1.

Para comprobar sólo el padre con su herramienta original:

```powershell
python -I -S -B -X utf8 <paquete_padre>/herramientas/verify_rules_sensitivity_package.py `
  --package <paquete_padre>
```

## Regenerar exclusivamente el posprocesamiento

Se necesita además la carpeta original E3 `Paquete de evidencia`, para autenticar
y copiar el pequeño subconjunto editorial de referencia. Usar otro destino
inexistente, fuera del padre, E3 y cualquier paquete sellado:

```powershell
python -B -X utf8 <correccion>/herramientas/correct_rules_sensitivity_report.py `
  --source-package <paquete_padre> --destination <destino_nuevo> `
  --e3-reference <Paquete_de_evidencia>
```

Matplotlib se requiere para regenerar figuras. `--no-figures` omite las imágenes
nuevas pero conserva sus datos comprobables. El constructor sella el destino
solamente al finalizar; verificarlo después con el comando anterior. No cambia
fuentes, motor, configuraciones ni resultados económicos. Si falla antes del
sello, conservar el diagnóstico y elegir otro destino para el siguiente intento.

## Archivos y alcance

- `comparacion/exposicion_intervalos.csv`: intervalos completos por activo,
  cantidades/estado/clase y banderas brutas; permite auditar los cortes.
- `comparacion/exposicion_periodo.csv`: activos y unión de cartera para ocho períodos.
- `comparacion/h2.csv`: 48 comparaciones con CAGR, Sharpes, condiciones y motivos.
- `comparacion/antes_despues.csv`: 96 filas, doce carteras y ocho períodos.
- `comparacion/preservacion_financiera.csv`: comparación de cada valor no afectado.
- `comparacion/preservacion_tablas.csv`: hashes y comparación binaria de tablas/índice.
- `comparacion/episodio_2023_03_24.csv`: controles del episodio BASE de 121 minutos.
- `comparacion/procedencia_corridas.csv`: código económico original e identidad editorial.
- `referencia_e3/`: subconjunto autenticado de las tablas y del código original,
  sin copias grandes de datos ni simulaciones. No es el paquete E3 completo.
- `herramientas/`: versión congelada del posprocesador y verificadores.
- `pruebas/`: copia de las pruebas nuevas para trazabilidad; se ejecutan en el
  proyecto, donde también están los fixtures y paquetes originales referenciados.
- `procedencia.json` y `manifiesto_paquete.json`: entradas, padre y productos nuevos.
- `verificacion_construccion.json`: controles realizados durante la construcción;
  los certificados independientes posteriores son externos y no se incorporan al sello.

El informe padre conserva las afirmaciones originales como registro histórico.
Esta versión corrige explícitamente la atribución errónea del conteo con polvo a
E3 y completa H2. No modifica ni certifica una cronología completa de Binance.
La integridad de archivos no acredita autenticidad de fuentes, causalidad del
motor ni publicación GitHub. Esta corrección local no cambia el índice de Git.
""",
    )

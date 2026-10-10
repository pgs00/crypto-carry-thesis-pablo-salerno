"""Audit previous-minute funding prices using immutable local continuous runs."""

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from decimal import Decimal as D
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from crypto_carry.config import Config, iso, timestamp
from crypto_carry.data.funding_proxy import MINUTE
from crypto_carry.data.replay import _records
from crypto_carry.models import Mark
from scripts.continuous_delivery.common import read_rows, sha256, write_json, write_rows
from scripts.funding_price_analysis import (
    BPS,
    event_impact,
    paired_proxy,
    positions_before,
    price_stats,
    relative_error_bps,
    scenario_totals,
)
from scripts.verify_continuous_marks import verify as verify_continuous

REPO = Path(__file__).resolve().parents[1]
STUDY = "continuous_marks_b417d512a416058238193c79"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
YEARS = tuple(str(year) for year in range(2022, 2027))
EXPECTED_COUNTS = {"exact": 6214, "previous_closed_1m": 4010}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def key(row):
    return row["symbol"], int(row.get("funding_time", row.get("time_ns", 0)))


def unique(rows):
    result = {key(row): row for row in rows}
    require(len(result) == len(rows), "Duplicate funding key")
    return result


def load_prices(root, runs, config, sources):
    """Cross-check raw API, normalized records, consumed records and mark candles."""
    processed_path = root / config.data_dir / "manifests/processed.json"
    processed = json.loads(processed_path.read_text(encoding="utf-8"))

    def remember(path):
        sources[path.relative_to(root).as_posix()] = sha256(path)

    remember(processed_path)
    audits = {}
    for strategy, run in runs.items():
        path = run / "funding_mark_audit.json"
        remember(path)
        consumed = json.loads(path.read_text(encoding="utf-8"))["consumed"]
        rows = [row for row in consumed if row["economic_window"]]
        require(
            Counter(row["settlement_mark_method"] for row in rows) == EXPECTED_COUNTS,
            "Unexpected exact/proxy funding counts",
        )
        audits[strategy] = unique(rows)
    reference = audits["conditional"]
    excluded = {"strategy", "funding_filter_enabled"}
    require(
        {k: {f: v for f, v in r.items() if f not in excluded} for k, r in reference.items()}
        == {
            k: {f: v for f, v in r.items() if f not in excluded}
            for k, r in audits["permanent"].items()
        },
        "Funding observations differ between saved portfolios",
    )
    records, raw_records = {}, {}
    start, end = timestamp(config.start), timestamp(config.end)
    for entry in processed["entries"]:
        if entry["dataset"] != "funding":
            continue
        path = root / entry["path"]
        remember(path)
        require(sources[entry["path"]] == entry["sha256"], "Funding partition hash mismatch")
        for record in _records(path, "funding"):
            if start <= record.funding_time < end:
                identity = (record.symbol, record.funding_time)
                require(identity not in records, "Duplicate normalized funding")
                records[identity] = record
        raw_path = root / entry["source_path"]
        remember(raw_path)
        require(
            sources[entry["source_path"]] == entry["source_sha256"], "Raw funding hash mismatch"
        )
        for row in json.loads(raw_path.read_text(encoding="utf-8")):
            t = int(row["fundingTime"]) * 1_000_000
            if start <= t < end:
                identity = (row["symbol"], t)
                require(identity not in raw_records, "Duplicate raw API funding")
                raw_records[identity] = row
    require(set(records) == set(reference) == set(raw_records), "Funding observation sets differ")
    wanted = defaultdict(set)
    for symbol, t in records:
        wanted[symbol].add(t // MINUTE * MINUTE - MINUTE)
    marks = {}
    for entry in processed["entries"]:
        if entry["dataset"] != "marks":
            continue
        needed = wanted[entry["symbol"]]
        times = [t for t in needed if entry["start"] <= t + MINUTE <= entry["end"]]
        if not times:
            continue
        path = root / entry["path"]
        remember(path)
        require(sources[entry["path"]] == entry["sha256"], "Mark partition hash mismatch")
        table = pq.ParquetFile(path).read()
        table = table.filter(
            pc.is_in(table["open_time"], value_set=pa.array(times, type=pa.int64()))
        )
        for row in table.to_pylist():
            identity = (row["symbol"], row["open_time"])
            require(identity not in marks, "Duplicate candidate mark")
            marks[identity] = Mark(
                **{
                    name: row[name]
                    for name in ("symbol", "open_time", "close_time", "available_at", "source_file")
                },
                **{name: D(row[name]) for name in ("open", "high", "low", "close")},
                estimation_method=row.get("estimation_method", "official"),
                anchor_open_time=row.get("anchor_open_time"),
            )
    output = []
    for identity, record in sorted(records.items()):
        raw, consumed = raw_records[identity], reference[identity]
        official = record.settlement_mark_price
        raw_price = D(raw["markPrice"]) if raw.get("markPrice") else None
        require(
            raw_price == official and D(raw["fundingRate"]) == record.funding_rate,
            "Raw API and normalized funding differ",
        )
        require(
            record.available_at == consumed["available_at"]
            and record.funding_rate == D(consumed["funding_rate"])
            and record.interval_hours == D(consumed["interval_hours"]),
            "Consumed funding rate, interval or availability changed",
        )
        mark = marks.get((record.symbol, record.funding_time // MINUTE * MINUTE - MINUTE))
        proxy_record = paired_proxy(record, mark, config)
        proxy = proxy_record.settlement_mark_price
        method = "exact" if official is not None else "previous_closed_1m"
        require(
            consumed["settlement_mark_method"] == method, "Official/proxy classification differs"
        )
        base = official if official is not None else proxy
        require(base == D(consumed["settlement_mark_price"]), "Consumed settlement price differs")
        if official is None:
            for name in (
                "settlement_mark_price",
                "settlement_mark_proxy_base",
                "settlement_mark_stress_bps",
            ):
                require(
                    D(consumed[name]) == getattr(proxy_record, name), "Saved proxy value differs"
                )
            for name in (
                "settlement_mark_source_file",
                "settlement_mark_close_time",
                "settlement_mark_available_at",
            ):
                require(
                    consumed[name] == getattr(proxy_record, name),
                    "Saved proxy timing/source differs",
                )
        output.append(
            dict(
                symbol=record.symbol,
                year=iso(record.funding_time)[:4],
                funding_time=record.funding_time,
                funding_time_utc=iso(record.funding_time),
                funding_rate=record.funding_rate,
                rate_available_at=record.available_at,
                interval_hours=record.interval_hours,
                price_method=method,
                official_price=official,
                previous_closed_mark_price=proxy,
                saved_price=base,
                relative_error_bps=relative_error_bps(proxy, official)
                if official is not None
                else None,
                mark_open_time=mark.open_time,
                mark_close_time=mark.close_time,
                mark_available_at=mark.available_at,
                mark_age_milliseconds=D(record.funding_time - mark.close_time) / 1_000_000,
                mark_estimation_method=mark.estimation_method,
                mark_anchor_open_time=mark.anchor_open_time,
                mark_source_file=mark.source_file,
                funding_source_file=record.source_file,
            )
        )
    return output


def price_summaries(prices):
    output = []
    for symbol in SYMBOLS:
        for year in (*YEARS, "all"):
            selected = [
                r for r in prices if r["symbol"] == symbol and (year == "all" or r["year"] == year)
            ]
            known = [r for r in selected if r["price_method"] == "exact"]
            output.append(
                dict(
                    symbol=symbol,
                    year=year,
                    price_observations=len(selected),
                    official_prices=len(known),
                    approximated_prices=len(selected) - len(known),
                    first_official_utc=min((r["funding_time_utc"] for r in known), default=None),
                    last_official_utc=max((r["funding_time_utc"] for r in known), default=None),
                    **price_stats([D(str(r["relative_error_bps"])) for r in known]),
                )
            )
    return output


def portfolio_events(prices, ledger, fills, payments, strategy, p95):
    """Validate every exposure, including absent payments, against two saved views."""
    before = positions_before(prices, ledger)
    paid = unique(payments)
    seen = set()
    output = []
    future_fills = defaultdict(list)
    for row in fills:
        if row["market"] == "futures":
            future_fills[row["symbol"]].append(row)
    for symbol in SYMBOLS:
        ordered = sorted(future_fills[symbol], key=lambda row: int(row["time_ns"]))
        index, short = 0, D(0)
        for observation in sorted(
            (r for r in prices if r["symbol"] == symbol), key=lambda r: r["funding_time"]
        ):
            t = observation["funding_time"]
            while index < len(ordered) and int(ordered[index]["time_ns"]) < t:
                fill = ordered[index]
                require(fill["side"] in {"BUY", "SELL"}, "Unknown futures fill side")
                short += D(fill["quantity"]) * (1 if fill["side"] == "SELL" else -1)
                index += 1
            position = before[symbol, t]
            require(short == position["short_before"], "Ledger and pre-settlement fills disagree")
            payment = paid.get((symbol, t))
            require((short > 0) == (payment is not None), "Missing or unexpected funding payment")
            if short == 0:
                continue
            impact = event_impact(
                short,
                observation["funding_rate"],
                observation["saved_price"],
                observation["previous_closed_mark_price"],
                observation["price_method"],
                p95[symbol],
            )
            require(
                D(payment["short"]) == short
                and D(payment["amount_usdt"]) == impact["base_funding_usdt"]
                and D(payment["funding"]) == impact["base_funding_usdt"],
                "Saved funding payment does not reconcile",
            )
            seen.add((symbol, t))
            output.append(
                dict(
                    strategy=strategy,
                    symbol=symbol,
                    year=observation["year"],
                    funding_time=t,
                    funding_time_utc=observation["funding_time_utc"],
                    price_method=observation["price_method"],
                    event_id=payment["event_id"],
                    **position,
                    p95_abs_bps=p95[symbol],
                    **impact,
                )
            )
    require(seen == set(paid), "Funding payment outside the validated observation universe")
    return sorted(output, key=lambda row: (row["funding_time"], row["symbol"]))


def economic_summaries(prices, events, capital):
    output = []
    for strategy in ("conditional", "permanent"):
        for symbol in (*SYMBOLS, "ALL"):
            for year in (*YEARS, "all"):

                def matches(row):
                    return (symbol == "ALL" or row["symbol"] == symbol) and (
                        year == "all" or row["year"] == year
                    )

                observations = [r for r in prices if matches(r)]
                selected = [r for r in events if r["strategy"] == strategy and matches(r)]
                known = [r for r in selected if r["price_method"] == "exact"]
                missing = [r for r in selected if r["price_method"] == "previous_closed_1m"]
                observed_delta = sum((r["known_proxy_delta_usdt"] for r in known), D(0))
                favorable = sum((r["favorable_delta_usdt"] for r in missing), D(0))
                adverse = sum((r["adverse_delta_usdt"] for r in missing), D(0))
                output.append(
                    dict(
                        strategy=strategy,
                        symbol=symbol,
                        year=year,
                        price_observations=len(observations),
                        official_price_observations=sum(
                            r["price_method"] == "exact" for r in observations
                        ),
                        approximated_price_observations=sum(
                            r["price_method"] == "previous_closed_1m" for r in observations
                        ),
                        open_position_events=len(selected),
                        official_open_position_events=len(known),
                        approximated_open_position_events=len(missing),
                        base_funding_usdt=sum((r["base_funding_usdt"] for r in selected), D(0)),
                        official_event_funding_usdt=sum(
                            (r["base_funding_usdt"] for r in known), D(0)
                        ),
                        approximated_event_funding_usdt=sum(
                            (r["base_funding_usdt"] for r in missing), D(0)
                        ),
                        observed_proxy_delta_usdt=observed_delta,
                        observed_absolute_deltas_usdt=sum(
                            (abs(r["known_proxy_delta_usdt"]) for r in known), D(0)
                        ),
                        observed_max_absolute_delta_usdt=max(
                            (abs(r["known_proxy_delta_usdt"]) for r in known), default=D(0)
                        ),
                        observed_delta_return_bps=observed_delta / capital * BPS,
                        favorable_delta_usdt=favorable,
                        adverse_delta_usdt=adverse,
                        favorable_delta_return_bps=favorable / capital * BPS,
                        adverse_delta_return_bps=adverse / capital * BPS,
                    )
                )
    return output


def report_text(stats, economics, scenarios, prices, verification):
    def number(value, places=6):
        return "—" if value is None else f"{D(str(value)):.{places}f}"

    price_lines = "\n".join(
        f"| {r['symbol']} | {r['year']} | {r['official_prices']} / {r['approximated_prices']} | "
        + " | ".join(
            number(r[field]) for field in ("bias_bps", "mae_bps", "p95_abs_bps", "max_abs_bps")
        )
        + " |"
        for r in stats
    )
    totals = [r for r in economics if r["year"] == "all" and r["symbol"] == "ALL"]
    economic_lines = "\n".join(
        f"| {r['strategy']} | {r['official_open_position_events']} / {r['approximated_open_position_events']} | "
        f"{number(r['official_event_funding_usdt'])} | {number(r['observed_proxy_delta_usdt'])} | "
        f"{number(r['observed_absolute_deltas_usdt'])} | {number(r['observed_delta_return_bps'])} |"
        for r in totals
    )
    scenario_lines = "\n".join(
        f"| {r['strategy']} | {r['scenario']} | {number(r['delta_usdt'])} | "
        f"{number(r['delta_return_bps'])} | {number(r['net_return'] * 100)}% |"
        for r in scenarios
    )
    pooled = {r["symbol"]: r for r in stats if r["year"] == "all"}
    overlaps = sum(r["mark_estimation_method"] != "official" for r in prices)
    first = min(r["funding_time_utc"] for r in prices if r["price_method"] == "exact")
    last_proxy = max(r["funding_time_utc"] for r in prices if r["price_method"] != "exact")
    return f"""# Efecto de aproximar el precio de liquidación del funding

Análisis de las carteras continuas **01/01/2022–31/08/2026 UTC**, método de marks
`futures_scaled`, capital inicial de 10.000 USDT por cartera. Se reutilizan las
corridas condicional `run_ad71d751b20623006c195ff3` y permanente
`run_dfea4b7ac1475668d5968c97`, sin replay ni cambios de parámetros.

## Validación de precios

Se verificaron **10.224 observaciones: 6.214 precios oficiales y 4.010 aproximados**,
5.112 por activo. Se contrastaron el JSON local de la API, el Parquet normalizado,
las observaciones consumidas por ambas carteras y los marks de un minuto.
El primer precio oficial es `{first}`; el último aproximado es `{last_proxy}`.
Las observaciones de calentamiento anteriores a 2022 no forman parte del análisis.

Se llamó al mismo `resolve_funding_mark` del motor sobre una copia de cada evento,
quitando sólo su precio de liquidación para forzar la comparación. Sea `b` el
timestamp del funding truncado al minuto: se usa la vela abierta en `b − 1 minuto`,
cerrada entre `b − 1 ms` y `b` (excluido), disponible entre `b` y el instante real
del funding, inclusive. Se mantienen sus desfases de milisegundos. Las 4.010
aproximaciones reproducen exactamente los precios y la procedencia guardados.

Error firmado = `10.000 × (precio_aproximado / precio_oficial − 1)`.
Un sesgo positivo significa sobreestimar el precio; no necesariamente el funding
recibido. MAE, P95 y máximo usan el **valor absoluto del error relativo**.
P95 interpola linealmente en el rango `(n − 1) × 0,95` de la muestra ordenada.
Cada observación tiene igual peso dentro del activo/año; no se pondera por exposición.
2026 comprende enero–agosto. Sin precio oficial se informa ausencia, no error cero.

| Activo | Año | Oficiales / aproximados | Sesgo (bps) | MAE (bps) | P95 absoluto (bps) | Máximo absoluto (bps) |
|---|---|---:|---:|---:|---:|---:|
{price_lines}

## Impacto económico observado en precios conocidos

Para un short de `q` unidades base, el funding recibido es `q × precio × tasa`.
La diferencia observada es `q × tasa × (aproximado − oficial)`: positiva mejora
el resultado de la cartera. Se reconstruye `q` con el ledger **estrictamente
anterior** a cada liquidación, se contrasta con los fills de futuros y se concilia
cada pago guardado. El funding precede a los fills con el mismo timestamp.
Las liquidaciones de funding son distintas de una liquidación forzosa por margen.

| Cartera | Eventos con posición: oficiales / aproximados | Funding oficial recibido (USDT) | Diferencia usando proxy (USDT) | Suma de diferencias absolutas (USDT) | Efecto sobre retorno total (bps) |
|---|---:|---:|---:|---:|---:|
{economic_lines}

Hay 6.214 comparaciones de precios conocidas para **cada cartera**, aun cuando
no tiene posición. Sólo los eventos con posición de la tabla generan flujos.
Los CSV desglosan también año y activo. La diferencia observada anterior no se
suma a los escenarios siguientes: éstos mantienen los precios oficiales vigentes.

## Sensibilidad de los 4.010 precios faltantes

Se usa el P95 absoluto agrupado por activo de **todas** sus observaciones oficiales:
BTC `{number(pooled["BTCUSDT"]["p95_abs_bps"], 9)} bps` y
ETH `{number(pooled["ETHUSDT"]["p95_abs_bps"], 9)} bps`. Con `h = P95 / 10.000`,
el precio favorable es `proxy × (1 + signo(tasa) × h)` y el desfavorable es
`proxy × (1 − signo(tasa) × h)`. Las posiciones son shorts; tasa cero no altera
el flujo. Se perturban sólo precios aproximados; los precios conocidos quedan
idénticos. La perturbación se centra en el proxy, no pretende recuperar el oficial.

| Cartera | Escenario | Diferencia acumulada (USDT) | Efecto sobre retorno total (bps) | Retorno total ajustado |
|---|---|---:|---:|---:|
{scenario_lines}

`Retorno ajustado = (equity final guardado + diferencia) / 10.000 − 1`.
Son efectos aditivos con posiciones originales: no hay reinversión ni carteras
reiniciadas por año. Un bp de retorno es 0,01 puntos porcentuales; con 10.000 USDT
de capital, 1 USDT equivale a 1 bp. Las diferencias por año son contribuciones al
retorno de la muestra completa, no retornos anuales recalculados.

**Son escenarios ilustrativos, no límites garantizados ni intervalos de confianza.**
No se conoce el error real de los precios ausentes. Extrapolar desde fines de
2023–2026 a 2022–2023 supone una estabilidad que no se puede verificar: pueden
cambiar volatilidad, liquidez, saltos y microestructura. P95 deja fuera errores
observados más extremos y no garantiza cobertura futura. La dirección favorable
o desfavorable se aplica a todos los flujos; no representa una trayectoria de
errores estimada. No incluye cambios de decisiones, tamaños, caja disponible,
margen ni liquidaciones que un replay con otros precios podría producir.

No se modifican tasas, horarios ni la capa de los **15 marks de velas faltantes**,
que es otro supuesto. De los cierres utilizados aquí, **{overlaps}** pertenecen a esa
capa estimada; el CSV identifica el método de cada vela. El contraste de precios
no valida la exactitud histórica de reglas, comisiones ni ejecución.

## Archivos y reproducción

- [Observaciones de precios](prices.csv): una fila por activo/liquidación, valores,
  error y tiempos/procedencia del mark. Los errores sin oficial quedan vacíos.
- [Resumen de precios](price_summary.csv): cobertura y errores por activo/año y
  `all`. Precios en USDT por unidad base; errores en bps.
- [Eventos con posición](funding_events.csv): cantidades base previas, pago original,
  diferencia conocida y escenarios; importes en USDT. No incluye eventos sin posición.
- [Impacto por cartera, activo y año](economic_summary.csv): conteos de precios y
  posiciones por separado; `ALL` suma BTC/ETH y `all` agrupa la muestra completa.
- [Escenarios de cartera](portfolio_scenarios.csv): equity, funding y retorno final;
  `net_return` es fracción, `delta_return_bps` bps y
  `delta_return_percentage_points` puntos porcentuales.
- [Verificación y fuentes](sources.json): {verification["source_files_verified"]} archivos
  de entrada verificados, hashes originales y controles. [Manifiesto](manifest.json)
  y `manifest.sha256` preservan los bytes de esta evidencia compacta.

Los CSV usan UTF-8, separador coma y punto decimal. El análisis conserva precisión
Decimal; las tablas de este README redondean a seis decimales. Se reutilizan
fuentes locales públicas de Binance; no se descargó ni incluyó data masiva.
Desde la raíz de Backtesting, con su entorno instalado, usar un **destino nuevo**:

```powershell
& '.\\.venv\\Scripts\\python.exe' -m scripts.analyze_funding_prices --root 'D:\\Backtesting' --output '.\\data\\research\\funding-price-sensitivity-reproduccion'
```

Para verificar hashes y recalcular las tablas a partir de los CSV compactos,
sin abrir los datos masivos:

```powershell
& '.\\.venv\\Scripts\\python.exe' -m scripts.analyze_funding_prices --verify '.\\data\\research\\funding-price-sensitivity-20260920'
```
"""


def verify_output(directory):
    """Reconcile compact evidence independently of the massive input directory."""
    manifest_path = directory / "manifest.json"
    require(
        sha256(manifest_path) == (directory / "manifest.sha256").read_text().strip(),
        "Output manifest hash mismatch",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, digest in manifest["files"].items():
        path = (directory / name).resolve()
        require(
            path.is_relative_to(directory.resolve()) and sha256(path) == digest,
            "Output hash mismatch: " + name,
        )
    prices = read_rows(directory / "prices.csv")
    require(
        Counter(r["price_method"] for r in prices) == EXPECTED_COUNTS, "Unexpected price counts"
    )
    indexed = unique(prices)
    for row in prices:
        t = int(row["funding_time"])
        boundary = t // MINUTE * MINUTE
        require(
            int(row["mark_open_time"]) == boundary - MINUTE
            and boundary - 1_000_000 <= int(row["mark_close_time"]) < boundary
            and boundary <= int(row["mark_available_at"]) <= t,
            "Noncausal proxy candle",
        )
        if row["price_method"] == "exact":
            require(
                relative_error_bps(D(row["previous_closed_mark_price"]), D(row["official_price"]))
                == D(row["relative_error_bps"]),
                "Incorrect relative price error",
            )
        else:
            require(
                not row["relative_error_bps"]
                and not row["official_price"]
                and D(row["saved_price"]) == D(row["previous_closed_mark_price"]),
                "Unknown official price was filled",
            )
    stats = price_summaries(prices)
    _compare_rows(read_rows(directory / "price_summary.csv"), stats)
    p95 = {r["symbol"]: r["p95_abs_bps"] for r in stats if r["year"] == "all"}
    events = read_rows(directory / "funding_events.csv")
    identities = {(r["strategy"], *key(r)) for r in events}
    require(len(identities) == len(events), "Duplicate economic event")
    for row in events:
        price = indexed[key(row)]
        require(
            D(row["short_before"]) > 0
            and int(row["prior_ledger_time_ns"]) < int(row["funding_time"]),
            "Invalid pre-settlement position",
        )
        expected = event_impact(
            D(row["short_before"]),
            D(price["funding_rate"]),
            D(price["saved_price"]),
            D(price["previous_closed_mark_price"]),
            price["price_method"],
            p95[row["symbol"]],
        )
        for name, value in expected.items():
            require(
                (not row[name]) if value is None else D(row[name]) == value,
                "Incorrect event cashflow: " + name,
            )
        row.update(expected)
    economics = economic_summaries(prices, events, D(manifest["capital_usdt"]))
    _compare_rows(read_rows(directory / "economic_summary.csv"), economics)
    scenarios = []
    for strategy, final in manifest["final_equity_usdt"].items():
        scenarios.extend(
            dict(strategy=strategy, **r)
            for r in scenario_totals(
                [e for e in events if e["strategy"] == strategy],
                D(manifest["capital_usdt"]),
                D(final),
            )
        )
    _compare_rows(read_rows(directory / "portfolio_scenarios.csv"), scenarios)
    return dict(
        status="verified",
        files=len(manifest["files"]),
        price_observations=len(prices),
        official_prices=6214,
        approximated_prices=4010,
        open_position_events=len(events),
    )


def _compare_rows(saved, expected):
    require(len(saved) == len(expected), "Summary length mismatch")
    for actual, row in zip(saved, expected, strict=True):
        for name, value in row.items():
            if value is None:
                equal = not actual[name]
            elif isinstance(value, (D, int)):
                equal = D(actual[name]) == value
            else:
                equal = actual[name] == str(value)
            require(equal, "Summary differs: " + name)


def analyze(root, output):
    require(not output.exists(), "Use a new output directory to preserve previous evidence")
    print("Verifying saved continuous runs and local source hashes...", flush=True)
    verification = verify_continuous(root, root / "outputs" / STUDY)
    index_path = root / "outputs" / STUDY / "study_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    runs = {
        r["strategy"]: root / r["path"] for r in index["runs"] if r["method"] == "futures_scaled"
    }
    manifests = {
        s: json.loads((p / "run_manifest.json").read_text(encoding="utf-8"))
        for s, p in runs.items()
    }
    config = Config.from_dict(manifests["conditional"]["config"])
    require(
        config == Config.from_dict(manifests["permanent"]["config"]), "Portfolio parameters differ"
    )
    require(config.mark_gap_method == "futures_scaled", "Unexpected existing mark-gap method")
    sources = {index_path.relative_to(root).as_posix(): sha256(index_path)}
    for manifest in manifests.values():
        for name, digest in manifest["code_files"].items():
            require(sha256(REPO / name) == digest, "Engine code differs from saved runs: " + name)
    print("Pairing all 10,224 funding events with causal closed-minute marks...", flush=True)
    prices = load_prices(root, runs, config, sources)
    stats = price_summaries(prices)
    p95 = {r["symbol"]: r["p95_abs_bps"] for r in stats if r["year"] == "all"}
    events, scenarios, finals = [], [], {}
    for strategy, run in runs.items():
        print("Reconciling original positions and funding: " + strategy, flush=True)
        data = {}
        for name in (
            "ledger.parquet",
            "fills.parquet",
            "funding_payments.parquet",
            "equity_daily.csv",
            "run_manifest.json",
            "run_manifest.sha256",
            "effective_config.toml",
        ):
            path = run / name
            sources[path.relative_to(root).as_posix()] = sha256(path)
            if path.suffix in {".parquet", ".csv"}:
                data[path.stem] = read_rows(path)
        actual = portfolio_events(
            prices, data["ledger"], data["fills"], data["funding_payments"], strategy, p95
        )
        events.extend(actual)
        finals[strategy] = D(data["equity_daily"][-1]["equity"])
        require(
            sum((r["base_funding_usdt"] for r in actual), D(0))
            == sum((D(r["amount_usdt"]) for r in data["funding_payments"]), D(0)),
            "Portfolio funding sum mismatch",
        )
        scenarios.extend(
            dict(strategy=strategy, **row)
            for row in scenario_totals(actual, config.capital, finals[strategy])
        )
    economics = economic_summaries(prices, events, config.capital)
    output.mkdir(parents=True)
    for name, rows in (
        ("prices", prices),
        ("price_summary", stats),
        ("funding_events", events),
        ("economic_summary", economics),
        ("portfolio_scenarios", scenarios),
    ):
        write_rows(output / (name + ".csv"), rows)
    for name, digest in sources.items():
        require(sha256(root / name) == digest, "Source changed during analysis: " + name)
    write_json(
        output / "sources.json",
        dict(
            study=STUDY,
            source_root="local --root argument",
            method="futures_scaled",
            runs={s: p.name for s, p in runs.items()},
            config=asdict(config),
            local_verification=verification,
            original_source_hashes=sources,
            analysis_code_hashes={
                p.relative_to(REPO).as_posix(): sha256(p)
                for p in (
                    Path(__file__),
                    REPO / "scripts/funding_price_analysis.py",
                    REPO / "scripts/continuous_delivery/common.py",
                )
            },
            checks=dict(
                raw_normalized_consumed_prices_agree=True,
                reconstructed_proxy_matches_all_4010=True,
                pre_settlement_ledger_matches_fills=True,
                every_saved_payment_reconciled=True,
                missing_or_extra_position_payments=0,
                estimated_mark_candles_used=sum(
                    r["mark_estimation_method"] != "official" for r in prices
                ),
            ),
        ),
    )
    (output / "README.md").write_text(
        report_text(stats, economics, scenarios, prices, verification),
        encoding="utf-8",
        newline="\n",
    )
    write_json(
        output / "manifest.json",
        dict(
            format_version=1,
            capital_usdt=config.capital,
            final_equity_usdt=finals,
            files={p.name: sha256(p) for p in sorted(output.iterdir()) if p.is_file()},
        ),
    )
    (output / "manifest.sha256").write_text(
        sha256(output / "manifest.json") + "\n", encoding="ascii", newline="\n"
    )
    print(json.dumps(verify_output(output), indent=2), flush=True)
    print("Report: " + str(output / "README.md"), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("D:/Backtesting"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_output(args.verify.resolve()), indent=2))
    else:
        if not args.output:
            parser.error("--output is required for a new analysis")
        analyze(args.root.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()

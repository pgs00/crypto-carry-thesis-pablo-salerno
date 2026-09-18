"""Research-only feasibility probe; not an input loader or a backtest.

Run from the repository root after downloading the manifest archives.
No operational data, rules or configuration are changed.
"""

import calendar
import csv
import hashlib
import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from decimal import Decimal as D
from itertools import chain
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path("data/research/funding-proxy-audit-20260918")


def read_json(path):
    return Path(path).read_text(encoding="utf-8")


def read_archive(entry):
    path = Path(entry["file"])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    assert entry["sha256"] == entry["official_sha256"]
    with zipfile.ZipFile(path) as archive:
        assert len(archive.namelist()) == 1
        with archive.open(archive.namelist()[0]) as binary:
            reader = csv.reader(io.TextIOWrapper(binary, encoding="utf-8"))
            first = next(reader)
            if first[0] == "open_time":
                rows = reader
            else:
                assert first[0].isdigit(), (path, "unknown schema", first)
                rows = chain([first], reader)
            yield from rows


manifest = json.loads(read_json(OUT / "manifest.json"))
daily = json.loads(read_json(OUT / "daily-gap-recovery-manifest.json"))
assert not manifest["errors"]
funding = []
funding_sources = []
start = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
end = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)
for path in sorted(Path("data/research/funding-20260918T132612Z").glob("page-*.json")):
    raw = path.read_bytes()
    funding_sources.append({"file": path.as_posix(), "sha256": hashlib.sha256(raw).hexdigest()})
    funding.extend(row for row in json.loads(raw) if start <= row["fundingTime"] < end)
assert len(funding) == 10224
needed = {s: set() for s in ("BTCUSDT", "ETHUSDT")}
for row in funding:
    minute = row["fundingTime"] // 60000 * 60000
    needed[row["symbol"]].update((minute - 60000, minute))
marks = {s: {} for s in needed}
missing = {}
checks = []
conflicts = []


def retain(entry, row):
    symbol = entry["symbol"]
    stamp = int(row[0])
    assert int(row[6]) == stamp + 59999
    if stamp not in needed[symbol]:
        return
    values = {key: row[i] for key, i in (("open", 1), ("high", 2), ("low", 3), ("close", 4))}
    prices = {key: D(value) for key, value in values.items()}
    assert 0 < prices["low"] <= min(prices["open"], prices["close"])
    assert max(prices["open"], prices["close"]) <= prices["high"]
    previous = marks[symbol].get(stamp)
    if previous:
        if any(D(previous[key]) != prices[key] for key in prices):
            conflicts.append({"symbol": symbol, "time": stamp, "old": previous, "new": values})
        return
    marks[symbol][stamp] = {**values, "close_time_ms": int(row[6]), "source": entry["file"]}


for entry in manifest["entries"]:
    year, month = map(int, entry["month"].split("-"))
    first = int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp() * 1000)
    count = calendar.monthrange(year, month)[1] * 1440
    expected = set(range(first, first + count * 60000, 60000))
    seen = set()
    for row in read_archive(entry):
        stamp = int(row[0])
        assert stamp in expected and stamp not in seen, (entry["file"], stamp)
        seen.add(stamp)
        retain(entry, row)
    key = (entry["symbol"], entry["month"])
    missing[key] = expected - seen
    checks.append({"symbol": key[0], "month": key[1], "rows": len(seen),
                   "expected_rows": count, "missing_before_daily": len(missing[key]),
                   "sha256": entry["sha256"]})

for entry in daily:
    if entry["status"] != 200:
        continue
    key = (entry["symbol"], entry["day"][:7])
    for row in read_archive(entry):
        missing[key].discard(int(row[0]))
        retain(entry, row)
for check in checks:
    remaining = sorted(missing[(check["symbol"], check["month"])])
    check["missing_after_daily"] = len(remaining)
    check["remaining_missing_open_times_ms"] = remaining
assert not conflicts, conflicts
unavailable = {s: sorted(needed[s] - marks[s].keys()) for s in needed}
assert not any(unavailable.values()), unavailable

results = []
for event in sorted(funding, key=lambda r: (r["symbol"], r["fundingTime"])):
    symbol = event["symbol"]
    minute = event["fundingTime"] // 60000 * 60000
    previous, current = marks[symbol][minute - 60000], marks[symbol][minute]
    exact = D(event["markPrice"]) if event.get("markPrice") else None
    row = {"symbol": symbol, "funding_time_ms": event["fundingTime"],
           "funding_rate": event["fundingRate"], "settlement_mark_price": event.get("markPrice") or None,
           "previous_close": previous["close"], "previous_close_time_ms": previous["close_time_ms"],
           "minute_open": current["open"], "current_minute_low": current["low"],
           "current_minute_high": current["high"], "previous_source": previous["source"],
           "current_source": current["source"], "comparisons": {}}
    if exact is not None:
        for method, value in (("previous_close", previous["close"]), ("minute_open", current["open"])):
            error = D(value) / exact - 1
            cash = D(3000) * D(event["fundingRate"]) * error
            row["comparisons"][method] = {
                "signed_price_error_bps": str(error * 10000),
                "absolute_price_error_bps": str(abs(error) * 10000),
                "signed_funding_error_3000_notional_usdt": str(cash),
                "absolute_funding_error_3000_notional_usdt": str(abs(cash)),
                "exact_match": D(value) == exact,
            }
        row["exact_mark_within_current_minute_range"] = D(current["low"]) <= exact <= D(current["high"])
    results.append(row)

summary, stress = [], []
for symbol in ("BTCUSDT", "ETHUSDT", "BOTH"):
    selected = [r for r in results if symbol == "BOTH" or r["symbol"] == symbol]
    known = [r for r in selected if r["settlement_mark_price"] is not None]
    unknown = [r for r in selected if r["settlement_mark_price"] is None]
    for method in ("previous_close", "minute_open"):
        values = [r["comparisons"][method] for r in known]
        errors = np.array([float(v["absolute_price_error_bps"]) for v in values])
        cash = [D(v["absolute_funding_error_3000_notional_usdt"]) for v in values]
        worst = known[int(errors.argmax())]
        summary.append({
            "symbol": symbol, "method": method, "known_count": len(known), "unknown_count": len(unknown),
            "exact_count": sum(v["exact_match"] for v in values),
            "mean_absolute_price_error_bps": float(errors.mean()),
            "median_absolute_price_error_bps": float(np.median(errors)),
            "p95_absolute_price_error_bps": float(np.quantile(errors, .95)),
            "p99_absolute_price_error_bps": float(np.quantile(errors, .99)),
            "max_absolute_price_error_bps": float(errors.max()),
            "max_price_error_event": {k: worst[k] for k in ("symbol", "funding_time_ms", "settlement_mark_price", "previous_close", "minute_open")},
            "sum_absolute_funding_error_3000_notional_usdt": str(sum(cash, D(0))),
            "sum_signed_funding_error_3000_notional_usdt": str(sum((D(v["signed_funding_error_3000_notional_usdt"]) for v in values), D(0))),
            "max_absolute_funding_error_3000_notional_usdt": str(max(cash)),
            "known_marks_outside_current_minute_range": sum(not r["exact_mark_within_current_minute_range"] for r in known),
        })
    total = sum((abs(D(row["funding_rate"])) for row in unknown), D(0))
    stress.append({"symbol": symbol, "missing_count": len(unknown), "sum_absolute_funding_rates": str(total),
                   "notional_per_symbol_per_event_usdt": "3000",
                   "assumed_uniform_upper_bound_price_error_bps_to_direct_error_bound_usdt": {
                       str(b): str(D(3000) * total * D(b) / 10000) for b in (1, 10, 100)}})

report = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "purpose": "Feasibility only; candidate proxies are not imputed to operational inputs",
    "cash_error_convention": "q*r*M for short perpetual funding; illustration q=3000/M_exact at each known event, not actual strategy quantities. Absolute sums ignore path changes. Unknown-period error is not guaranteed.",
    "price_error": "(proxy/exact-1)*10000 bps; Decimal before float summary quantiles",
    "summary": summary, "missing_period_conditional_stress": stress,
    "funding_sources": funding_sources, "archive_checks": checks,
    "daily_recovery_manifest": (OUT / "daily-gap-recovery-manifest.json").as_posix(), "rows": results,
}
(OUT / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
Path("docs/research/funding_proxy_feasibility_20260918.json").write_text(
    json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2), encoding="utf-8")
print(json.dumps({"archives": len(checks), "selected_events": len(results),
                  "missing_minutes_before_daily": sum(c["missing_before_daily"] for c in checks),
                  "missing_minutes_after_daily": sum(c["missing_after_daily"] for c in checks),
                  "summary": summary, "stress": stress}, indent=2))

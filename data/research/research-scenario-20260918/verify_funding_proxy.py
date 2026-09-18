"""Exercise the production resolver against all missing economic settlement marks.

Reads hash-checked original public API pages and official mark archives. This
validates proxy availability, not exchange rules or full replay data coverage.
"""

import csv
import hashlib
import io
import json
import zipfile
from collections import Counter, defaultdict
from decimal import Decimal as D
from pathlib import Path

from crypto_carry.config import HOUR, SECOND, Config, timestamp
from crypto_carry.data.funding_proxy import MINUTE, resolve_funding_mark
from crypto_carry.models import Funding, Mark

OUT = Path("data/research/research-scenario-20260918")
AUDIT = Path("data/research/funding-proxy-audit-20260918")
config = Config.load("configs/research.toml")
comparison = json.loads((AUDIT / "comparison.json").read_text(encoding="utf-8"))
sources = []


def checked(entry):
    path = Path(entry["file"])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == entry["sha256"], path
    if "official_sha256" in entry:
        assert digest == entry["official_sha256"]
        checksum = path.with_name(path.name + ".CHECKSUM")
        assert hashlib.sha256(checksum.read_bytes()).hexdigest() == entry["checksum_file_sha256"]
        assert checksum.read_text().split()[0] == digest
    sources.append({"path": path.as_posix(), "sha256": digest})
    return path


raw = []
for entry in comparison["funding_sources"]:
    path = checked(entry)
    raw.extend((row, path.as_posix()) for row in json.loads(path.read_text(encoding="utf-8")))
last = {}
funding = []
for row, source in sorted(raw, key=lambda item: (item[0]["symbol"], item[0]["fundingTime"])):
    symbol, at = row["symbol"], int(row["fundingTime"]) * 1_000_000
    prior = last.get(symbol)
    last[symbol] = at
    if not timestamp(config.start) <= at < timestamp(config.end):
        continue
    assert prior is not None and prior < at
    funding.append(
        Funding(
            symbol,
            at,
            at + 60 * SECOND,
            D(row["fundingRate"]),
            D(at - prior) / HOUR,
            D(row["markPrice"]) if row.get("markPrice") else None,
            source,
        )
    )

needed = defaultdict(set)
for row in comparison["rows"]:
    if row["settlement_mark_price"] is None:
        needed[row["previous_source"]].add(int(row["previous_close_time_ms"]) - 59999)
catalog = json.loads((AUDIT / "manifest.json").read_text(encoding="utf-8"))["entries"]
catalog += json.loads((AUDIT / "daily-gap-recovery-manifest.json").read_text(encoding="utf-8"))
by_path = {entry["file"]: entry for entry in catalog}
marks = {}
for path_name, stamps in needed.items():
    entry = by_path[path_name]
    path = checked(entry)
    found = set()
    with zipfile.ZipFile(path) as archive:
        assert len(archive.namelist()) == 1
        with archive.open(archive.namelist()[0]) as stream:
            for row in csv.reader(io.TextIOWrapper(stream, encoding="utf-8")):
                if not row[0].isdigit() or int(row[0]) not in stamps:
                    continue
                at = int(row[0]) * 1_000_000
                assert int(row[6]) * 1_000_000 == at + MINUTE - 1_000_000
                mark = Mark(
                    entry["symbol"],
                    at,
                    int(row[6]) * 1_000_000,
                    at + MINUTE,
                    D(row[1]),
                    D(row[2]),
                    D(row[3]),
                    D(row[4]),
                    path_name,
                )
                marks[(mark.symbol, at + MINUTE)] = mark
                found.add(int(row[0]))
    assert found == stamps, (path, stamps - found)

counts = Counter()
resolved_rows = []
for event in funding:
    candidate = marks.get((event.symbol, event.funding_time // MINUTE * MINUTE))
    resolved = resolve_funding_mark(event, candidate, config)
    assert resolved.settlement_mark_price is not None
    if event.settlement_mark_price is not None:
        assert resolved is event
    else:
        assert candidate is not None
        assert resolved.settlement_mark_price == candidate.close
        resolved_rows.append(
            {
                "symbol": event.symbol,
                "funding_time": event.funding_time,
                "mark": str(resolved.settlement_mark_price),
                "source_file": resolved.settlement_mark_source_file,
                "available_at": resolved.settlement_mark_available_at,
            }
        )
    counts[f"{event.symbol}:{resolved.settlement_mark_method}"] += 1
assert len(funding) == 10224 and len(resolved_rows) == 4010
summary = {
    "purpose": "Production resolver availability verification; no exact-mark or full replay certification",
    "events": len(funding),
    "preserved_exact": len(funding) - len(resolved_rows),
    "resolved_previous_closed_1m": len(resolved_rows),
    "counts": dict(counts),
    "sources": sources,
    "resolved": resolved_rows,
}
(OUT / "funding-resolver-verification.json").write_text(
    json.dumps(summary, indent=2), encoding="utf-8"
)
print(json.dumps({k: v for k, v in summary.items() if k not in {"sources", "resolved"}}))

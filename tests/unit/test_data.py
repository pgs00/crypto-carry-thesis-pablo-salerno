from __future__ import annotations

import hashlib
import json
import zipfile
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from crypto_carry.config import HOUR, SECOND, Config, timestamp
from crypto_carry.data import download, normalize, replay
from crypto_carry.data.rules import RuleBook, synthetic_rules
from crypto_carry.data.validate import validate_data
from crypto_carry.models import Funding, Mark, Trade


class FakeResponse:
    def __init__(
        self, *, json_value=None, content: bytes = b"", status_code: int = 200, headers=None
    ):
        self._json_value = json_value
        self.content = content
        self.status_code = status_code
        self.headers = headers or {"content-length": str(len(content))}

    def json(self):
        return self._json_value

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_bytes(self):
        yield self.content


class FundingClient:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.params = []

    def get(self, _url, *, params=None, **_kwargs):
        self.params.append(dict(params))
        return FakeResponse(json_value=next(self.pages))


def test_source_timestamp_uses_spot_microseconds_only_from_2025():
    spot_2025_us = 1_735_689_600_123_456
    futures_2025_ms = 1_735_689_600_123

    assert normalize.source_timestamp_ns(spot_2025_us, "spot", "2025-01-01") == (
        1_735_689_600_123_456_000
    )
    assert normalize.source_timestamp_ns(futures_2025_ms, "futures", "2025-01-01") == (
        1_735_689_600_123_000_000
    )


def test_identical_duplicates_are_counted_but_conflicts_fail():
    identical = [
        {"trade_id": "7", "price": "100", "quantity": "1"},
        {"trade_id": "7", "price": "100", "quantity": "1"},
    ]
    rows, duplicate_count = normalize.deduplicate_rows(identical, ("trade_id",))
    assert rows == [identical[0]]
    assert duplicate_count == 1

    with pytest.raises(ValueError, match="Conflicting duplicate"):
        normalize.deduplicate_rows(
            [identical[0], {"trade_id": "7", "price": "101", "quantity": "1"}],
            ("trade_id",),
        )


def test_download_rejects_budget_before_constructing_http_client(tmp_path, monkeypatch):
    called = False

    def forbidden_client(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("network client must not be created")

    monkeypatch.setattr(download.httpx, "Client", forbidden_client)
    config = Config(data_budget_bytes=1)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "existing.bin").write_bytes(b"xx")

    with pytest.raises(download.DataBudgetExceeded):
        download.download(config, tmp_path)
    assert called is False


def test_funding_pagination_advances_one_millisecond_without_overlap():
    client = FundingClient(
        [
            [
                {"symbol": "BTCUSDT", "fundingTime": 1000, "fundingRate": "0.1", "markPrice": "10"},
                {"symbol": "BTCUSDT", "fundingTime": 2000, "fundingRate": "0.2", "markPrice": "11"},
            ],
            [{"symbol": "BTCUSDT", "fundingTime": 3000, "fundingRate": "0.3", "markPrice": "12"}],
        ]
    )

    rows = download.fetch_funding_pages(client, "BTCUSDT", 0, 4000, limit=2)

    assert [row["fundingTime"] for row in rows] == [1000, 2000, 3000]
    assert [params["startTime"] for params in client.params] == [0, 2001]


def test_funding_api_conflicting_duplicates_are_not_silently_discarded():
    client = FundingClient(
        [
            [
                {"fundingTime": 1000, "fundingRate": ".001", "markPrice": "100"},
                {"fundingTime": 1000, "fundingRate": "-.25", "markPrice": "100"},
            ]
        ]
    )
    with pytest.raises(ValueError, match="Conflicting funding"):
        download.fetch_funding_pages(client, "BTCUSDT", 0, 2000)


def test_matching_omissions_in_both_sources_do_not_verify_a_wrong_interval():
    rows = [
        {"fundingTime": 0, "fundingRate": ".001", "markPrice": "100"},
        {"fundingTime": 16 * 3600000, "fundingRate": ".001", "markPrice": "100"},
    ]
    records = normalize.funding_records(
        rows,
        symbol="BTCUSDT",
        source_file="fixture",
        expected_times_ms={0, 16 * 3600000},
        expected_intervals={0: Decimal(8), 16 * 3600000: Decimal(8)},
    )
    assert records[-1].interval_verified is False


def test_real_interval_change_has_independent_calendar_evidence():
    rows = [
        {"fundingTime": 0, "fundingRate": ".001", "markPrice": "100"},
        {"fundingTime": 4 * 3600000, "fundingRate": ".001", "markPrice": "100"},
    ]
    records = normalize.funding_records(
        rows,
        symbol="BTCUSDT",
        source_file="fixture",
        expected_times_ms={0, 4 * 3600000},
        expected_intervals={0: Decimal(8), 4 * 3600000: Decimal(4)},
    )
    assert records[-1].interval_verified is True


def test_published_hourly_schedule_allows_settlement_milliseconds_without_rounding_effective_interval():
    rows = [
        {"fundingTime": 0, "fundingRate": ".001", "markPrice": "100"},
        {"fundingTime": 8 * 3600000 + 1, "fundingRate": ".001", "markPrice": "100"},
    ]
    records = normalize.funding_records(
        rows,
        symbol="BTCUSDT",
        source_file="fixture",
        expected_times_ms={0, 8 * 3600000 + 1},
        expected_intervals={0: Decimal(8), 8 * 3600000 + 1: Decimal(8)},
    )
    assert records[-1].interval_verified
    assert records[-1].interval_hours == Decimal(28_800_001) / Decimal(3_600_000)


def test_verified_raw_cache_does_not_redownload(tmp_path):
    destination = tmp_path / "archive.zip"
    with zipfile.ZipFile(destination, "w") as archive:
        archive.writestr("sample.csv", "id,price\n1,100\n")
    checksum = hashlib.sha256(destination.read_bytes()).hexdigest()

    class NoNetwork:
        def get(self, *_args, **_kwargs):
            raise AssertionError("verified cache must not use network")

    result = download.download_verified_archive(
        NoNetwork(),
        "https://data.binance.vision/archive.zip",
        destination,
        expected_sha256=checksum,
        budget_limit=1_000,
        data_root=tmp_path,
    )

    assert result["status"] == "cached"
    assert result["sha256"] == checksum


def _rule_record(*, evidence_status="verified", valid_from=0, valid_to=None, known_from=0):
    return {
        "symbol": "BTCUSDT",
        "market": "spot",
        "rule_type": "market",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "known_from": known_from,
        "source_url": "https://example.invalid/dated-evidence",
        "source_publication_time": known_from,
        "retrieved_at": known_from,
        "evidence_status": evidence_status,
        "values": {
            "step": "0.001",
            "tick": "0.01",
            "min_qty": "0.001",
            "max_qty": "1000",
            "min_notional": "5",
            "max_notional": "10000000",
            "taker_fee": "0.001",
            "tiers": [],
            "liquidation_fee": "0",
            "liquidation_regular_fee": True,
            "liquidation_fee_basis": "execution_notional",
            "operational": True,
        },
    }


def test_rulebook_requires_validity_knowledge_and_verified_evidence():
    book = RuleBook([_rule_record(valid_from=100, valid_to=300, known_from=200)])
    assert book.get("BTCUSDT", "spot", 199) is None
    assert book.get("BTCUSDT", "spot", 200) is not None
    assert book.get("BTCUSDT", "spot", 300) is None

    current = RuleBook(
        [_rule_record(evidence_status="current_snapshot", valid_from=500, known_from=500)]
    )
    assert current.get("BTCUSDT", "spot", 499) is None
    assert current.get("BTCUSDT", "spot", 500) is not None

    synthetic = RuleBook([_rule_record(evidence_status="synthetic")])
    assert synthetic.get("BTCUSDT", "spot", 100) is None
    assert (
        RuleBook([_rule_record(evidence_status="synthetic")], allow_synthetic=True).get(
            "BTCUSDT", "spot", 100
        )
        is not None
    )


def test_rulebook_rejects_overlapping_snapshots_and_reports_boundaries():
    with pytest.raises(ValueError, match="Overlapping market-rule"):
        RuleBook([_rule_record(valid_from=0, valid_to=200), _rule_record(valid_from=100)])

    book = RuleBook([_rule_record(valid_from=100, valid_to=300, known_from=200)])
    assert book.transition_times(50, 350) == [100, 200, 300]


def test_missing_funding_is_not_reclassified_as_a_long_interval():
    rows = [
        {"fundingTime": 0, "fundingRate": "0.0001", "markPrice": "100"},
        {"fundingTime": 16 * 3600 * 1000, "fundingRate": "0.0002", "markPrice": "101"},
    ]
    records = normalize.funding_records(
        rows,
        symbol="BTCUSDT",
        source_file="funding.json",
        expected_times_ms={0, 8 * 3600 * 1000, 16 * 3600 * 1000},
    )

    assert records[1].interval_hours == Decimal(16)
    assert records[1].interval_verified is False


def _write_complete_sample_manifest(root: Path, config: Config, *, omit: str | None = None):
    from datetime import datetime, timezone

    data_dir = root / "data"
    manifests = data_dir / "manifests"
    processed = data_dir / "processed"
    manifests.mkdir(parents=True)
    processed.mkdir(parents=True)
    start = timestamp(config.sample_start)
    end = timestamp(config.sample_end)
    funding_start = start - (config.window_hours + 24) * HOUR
    entries = []
    calendar_entries = []
    for symbol in config.symbols:
        months = {}
        for funding_time in range(funding_start - 32 * 24 * HOUR, end + 32 * 24 * HOUR, 8 * HOUR):
            month = datetime.fromtimestamp(funding_time // SECOND, timezone.utc).strftime("%Y-%m")
            months.setdefault(month, []).append(f"{funding_time // 1_000_000},8,0.001\n")
        for month, calendar_rows in months.items():
            path = data_dir / "raw" / f"{symbol}-fundingRate-{month}.zip"
            path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(
                    f"{symbol}-fundingRate-{month}.csv",
                    "calc_time,funding_interval_hours,last_funding_rate\n" + "".join(calendar_rows),
                )
            calendar_entries.append(
                {
                    "dataset": "funding_calendar",
                    "symbol": symbol,
                    "market": "futures",
                    "path": str(path.relative_to(root)).replace("\\", "/"),
                    "start": f"{month}-01T00:00:00Z",
                    "end": None,
                    "status": "downloaded",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        for dataset, market in (
            ("trades", "spot"),
            ("trades", "futures"),
            ("marks", "futures"),
            ("funding", "futures"),
        ):
            key = f"{dataset}:{symbol}:{market}"
            if key == omit:
                continue
            path = processed / f"{dataset}-{symbol}-{market}.parquet"
            if dataset == "trades":
                parquet_rows = [
                    {
                        "symbol": symbol,
                        "market": market,
                        "trade_id": "1",
                        "event_time": start,
                        "available_at": start,
                        "price": "100",
                        "quantity": "1",
                        "source_file": "fixture.zip",
                    }
                ]
            elif dataset == "marks":
                parquet_rows = [
                    {
                        "symbol": symbol,
                        "open_time": minute - 60 * SECOND,
                        "close_time": minute - 1,
                        "available_at": minute,
                        "open": "100",
                        "high": "101",
                        "low": "99",
                        "close": "100",
                        "source_file": "fixture.zip",
                    }
                    for minute in range(start, end, 60 * SECOND)
                ]
            else:
                parquet_rows = [
                    {
                        "symbol": symbol,
                        "funding_time": funding_time,
                        "available_at": funding_time + 60 * SECOND,
                        "funding_rate": "0.001",
                        "interval_hours": "8",
                        "settlement_mark_price": "100",
                        "source_file": "fixture.json",
                        "interval_verified": True,
                    }
                    for funding_time in range(funding_start - 8 * HOUR, end, 8 * HOUR)
                ]
            pq.write_table(pa.Table.from_pylist(parquet_rows), path)
            time_field = {
                "trades": "event_time",
                "marks": "available_at",
                "funding": "funding_time",
            }[dataset]
            entries.append(
                {
                    "dataset": dataset,
                    "date": config.sample_start[:10] if dataset != "funding" else "all",
                    "symbol": symbol,
                    "market": market,
                    "path": str(path.relative_to(root)).replace("\\", "/"),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size,
                    "rows": len(parquet_rows),
                    "start": parquet_rows[0][time_field],
                    "end": parquet_rows[-1][time_field],
                    "schema": {},
                    "duplicate_count": 0,
                    "conflict_count": 0,
                    "complete": True,
                    "trade_id_continuous": True if dataset == "trades" else None,
                    "minute_coverage_complete": True if dataset == "marks" else None,
                    "funding_calendar_complete": True if dataset == "funding" else None,
                    "settlement_marks_complete": True if dataset == "funding" else None,
                }
            )
    (manifests / "processed.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")
    (manifests / "download.json").write_text(
        json.dumps({"entries": calendar_entries}), encoding="utf-8"
    )
    rules_path = root / config.rules_file
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    rules = []
    for symbol in config.symbols:
        for market in ("spot", "futures"):
            record = _rule_record(valid_from=start, valid_to=end, known_from=start)
            record["symbol"] = symbol
            record["market"] = market
            rules.append(record)
    rules_path.write_text(json.dumps({"records": rules}), encoding="utf-8")


def test_validation_distinguishes_complete_sample_from_unknown_file(tmp_path):
    config = Config()
    _write_complete_sample_manifest(tmp_path, config)
    complete = validate_data(config, tmp_path, scope="sample")
    assert complete["status"] == "complete", complete["issues"]
    assert complete["full_baseline_coverage"] is False

    other = tmp_path / "unknown"
    _write_complete_sample_manifest(other, config, omit="trades:ETHUSDT:spot")
    unknown = validate_data(config, other, scope="sample")
    assert unknown["status"] == "incomplete_data"
    assert any("missing processed file" in issue for issue in unknown["issues"])


def test_validation_rejects_a_hash_valid_parquet_with_the_wrong_schema(tmp_path):
    config = Config()
    _write_complete_sample_manifest(tmp_path, config)
    manifest_path = tmp_path / "data" / "manifests" / "processed.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = next(item for item in manifest["entries"] if item["dataset"] == "marks")
    path = tmp_path / entry["path"]
    pq.write_table(pa.Table.from_pylist([{"unexpected": 1}]), path)
    entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_data(config, tmp_path, scope="sample")

    assert result["status"] == "incomplete_data"
    assert any("schema mismatch" in issue for issue in result["issues"])


def test_validation_checks_requested_days_and_interior_rule_gaps(tmp_path):
    config = Config()
    _write_complete_sample_manifest(tmp_path, config)
    end = timestamp(config.sample_end)
    start = timestamp(config.sample_start)
    path = tmp_path / config.rules_file
    payload = json.loads(path.read_text(encoding="utf-8"))
    first = payload["records"][0]
    first["valid_to"] = start + HOUR
    later = dict(first, valid_from=start + 2 * HOUR, valid_to=end)
    payload["records"].append(later)
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_data(config, tmp_path)
    assert any("rule coverage gap" in issue for issue in result["issues"])
    result = validate_data(config.changed(sample_end="2024-01-03T00:00:00Z"), tmp_path)
    assert any("missing archive date" in issue for issue in result["issues"])


def test_operational_retrieval_timestamp_does_not_change_input_identity(tmp_path):
    config = Config()
    _write_complete_sample_manifest(tmp_path, config)
    first = replay.input_hashes(tmp_path, config)
    path = tmp_path / "data/manifests/processed.json"
    content = json.loads(path.read_text(encoding="utf-8"))
    content["source_manifest_sha256"] = "different-fetch-time-but-identical-raw-inputs"
    path.write_text(json.dumps(content), encoding="utf-8")
    assert replay.input_hashes(tmp_path, config) == first
    content["entries"][0]["complete"] = False
    path.write_text(json.dumps(content), encoding="utf-8")
    assert replay.input_hashes(tmp_path, config) != first


def test_synthetic_rules_are_explicit_and_support_large_demo_aum():
    book = synthetic_rules(Config())
    rule = book.get("BTCUSDT", "futures", timestamp("2024-01-01T00:00:00Z"))
    assert rule is not None
    assert rule.taker_fee == Decimal("0.0005")
    assert rule.max_notional >= Decimal(1000000)


def test_replay_merges_datasets_and_includes_prior_observations(tmp_path):
    root = tmp_path
    processed = root / "data" / "processed"
    manifests = root / "data" / "manifests"
    processed.mkdir(parents=True)
    manifests.mkdir(parents=True)
    start = timestamp("2024-01-01T00:00:00Z")
    trade_path = processed / "trades.parquet"
    funding_path = processed / "funding.parquet"
    mark_path = processed / "marks.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "symbol": "BTCUSDT",
                    "market": "spot",
                    "trade_id": "1",
                    "event_time": start - SECOND,
                    "available_at": start - SECOND,
                    "price": "99",
                    "quantity": "1",
                    "source_file": "x",
                },
                {
                    "symbol": "BTCUSDT",
                    "market": "spot",
                    "trade_id": "2",
                    "event_time": start + SECOND,
                    "available_at": start + SECOND,
                    "price": "100",
                    "quantity": "1",
                    "source_file": "x",
                },
            ]
        ),
        trade_path,
    )
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "symbol": "BTCUSDT",
                    "funding_time": start - HOUR,
                    "available_at": start - HOUR + 60 * SECOND,
                    "funding_rate": "0.001",
                    "interval_hours": "8",
                    "settlement_mark_price": "100",
                    "source_file": "f",
                    "interval_verified": True,
                }
            ]
        ),
        funding_path,
    )
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "symbol": "BTCUSDT",
                    "open_time": start - 60 * SECOND,
                    "close_time": start - 1,
                    "available_at": start + 999_999,
                    "open": "99",
                    "high": "101",
                    "low": "98",
                    "close": "100",
                    "source_file": "m",
                }
            ]
        ),
        mark_path,
    )
    entries = [
        {
            "dataset": "trades",
            "symbol": "BTCUSDT",
            "market": "spot",
            "path": str(trade_path.relative_to(root)).replace("\\", "/"),
        },
        {
            "dataset": "funding",
            "symbol": "BTCUSDT",
            "market": "futures",
            "path": str(funding_path.relative_to(root)).replace("\\", "/"),
        },
        {
            "dataset": "marks",
            "symbol": "BTCUSDT",
            "market": "futures",
            "path": str(mark_path.relative_to(root)).replace("\\", "/"),
        },
    ]
    (manifests / "processed.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")

    records = list(replay.iter_records(root, start, start + 2 * SECOND, warmup_hours=1))

    assert [type(record) for record in records] == [Funding, Trade, Mark, Trade]
    assert records[1].trade_id == "1"
    assert records[-1].trade_id == "2"

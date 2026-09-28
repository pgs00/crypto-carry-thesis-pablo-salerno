import csv
from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path

import pytest

from crypto_carry.config import Config, timestamp

MINUTE = 60_000_000_000
T = timestamp("2024-08-12T10:02:00Z")


def inputs():
    def mark(t, close):
        return dict(
            symbol="BTCUSDT",
            open_time=t,
            close_time=t + MINUTE - 1_000_000,
            available_at=t + MINUTE,
            open=close,
            high=close,
            low=close,
            close=close,
            source_file="official-mark.zip",
        )

    def future(t, close):
        return dict(
            symbol="BTCUSDT",
            market="futures",
            open_time=t,
            end_time=t + MINUTE,
            available_at=t + MINUTE,
            open="100",
            high="120",
            low="90",
            close=close,
            base_volume="10",
            quote_volume="1000",
            trade_count=3,
            source_file="official-futures.zip",
        )

    marks = {T - MINUTE: mark(T - MINUTE, "101"), T + 2 * MINUTE: mark(T + 2 * MINUTE, "999")}
    bars = {t: future(t, p) for t, p in [(T - MINUTE, "100"), (T, "110"), (T + MINUTE, "120")]}
    return marks, bars


def test_strict_is_default_and_cannot_opt_in_outside_research():
    assert getattr(Config(), "mark_gap_method", None) == "strict"
    with pytest.raises(ValueError, match="research"):
        Config(mark_gap_method="futures_scaled")


def test_documented_allowlist_matches_original_evidence():
    from crypto_carry.data.mark_gaps import APPROVED_MINUTES

    path = (
        Path(__file__).parents[2]
        / "data/research/continuous-preparation-20260919/unresolved_mark_minutes.csv"
    )
    with path.open(newline="", encoding="utf-8") as stream:
        documented = {(r["symbol"], timestamp(r["open_time"])) for r in csv.DictReader(stream)}
    assert APPROVED_MINUTES == documented
    assert len(documented) == 15


@pytest.mark.parametrize(
    "method,closes", [("futures_scaled", ["111.10", "121.20"]), ("last_official", ["101", "101"])]
)
def test_consecutive_gap_uses_one_official_anchor_and_next_minute_availability(method, closes):
    from crypto_carry.data.mark_gaps import estimate_gap

    marks, bars = inputs()
    originals = deepcopy((marks, bars))
    rows, audit = estimate_gap("BTCUSDT", [T, T + MINUTE], marks, bars, method)
    assert [D(r["close"]) for r in rows] == list(map(D, closes))
    assert [r["available_at"] for r in rows] == [T + MINUTE, T + 2 * MINUTE]
    assert [r["anchor_open_time"] for r in audit] == [T - MINUTE, T - MINUTE]
    assert all(r["estimation_method"] == method for r in rows)
    assert (marks, bars) == originals
    if method == "futures_scaled":
        assert {k: D(rows[0][k]) for k in ("open", "high", "low")} == {
            "open": D("101"),
            "high": D("121.2"),
            "low": D("90.9"),
        }
    else:
        assert all(D(r[k]) == 101 for r in rows for k in ("open", "high", "low", "close"))


def test_future_official_values_do_not_affect_estimates():
    from crypto_carry.data.mark_gaps import estimate_gap

    marks, bars = inputs()
    before = estimate_gap("BTCUSDT", [T, T + MINUTE], marks, bars, "futures_scaled")
    marks[T + 2 * MINUTE]["close"] = "0.01"
    bars[T + 3 * MINUTE] = dict(bars[T], open_time=T + 3 * MINUTE, close="50000")
    assert estimate_gap("BTCUSDT", [T, T + MINUTE], marks, bars, "futures_scaled") == before


@pytest.mark.parametrize(
    "damage",
    [
        "anchor_mark",
        "anchor_future",
        "missing_future",
        "early_future",
        "late_anchor",
        "estimated_anchor",
        "bad_price",
        "extra_gap",
        "official_exists",
    ],
)
def test_unavailable_inputs_and_extra_gaps_keep_block(damage):
    from crypto_carry.data.mark_gaps import estimate_gap

    marks, bars = inputs()
    missing = [T, T + MINUTE]
    if damage == "anchor_mark":
        del marks[T - MINUTE]
    elif damage == "anchor_future":
        del bars[T - MINUTE]
    elif damage == "missing_future":
        del bars[T]
    elif damage == "early_future":
        bars[T]["available_at"] = T
    elif damage == "late_anchor":
        marks[T - MINUTE]["available_at"] = T + 2 * MINUTE
    elif damage == "estimated_anchor":
        marks[T - MINUTE]["estimation_method"] = "last_official"
    elif damage == "bad_price":
        bars[T]["close"] = "0"
    elif damage == "extra_gap":
        missing.append(T + 2 * MINUTE)
    elif damage == "official_exists":
        marks[T] = dict(marks[T - MINUTE], open_time=T)
    with pytest.raises(ValueError):
        estimate_gap("BTCUSDT", missing, marks, bars, "futures_scaled")


def test_constant_method_does_not_require_unused_future_data():
    from crypto_carry.data.mark_gaps import estimate_gap

    marks, _ = inputs()
    rows, _ = estimate_gap("BTCUSDT", [T, T + MINUTE], marks, {}, "last_official")
    assert [D(r["close"]) for r in rows] == [101, 101]


def source_fixture(tmp_path):
    import hashlib
    import json
    from collections import defaultdict

    import pyarrow as pa
    import pyarrow.parquet as pq

    from crypto_carry.config import iso
    from crypto_carry.data.mark_gaps import APPROVED_MINUTES

    config = Config(
        analysis_mode="prescribed_research",
        fee_profile="prescribed_fixed_no_discounts",
        execution_model="next_minute_vwap",
        data_dir="original",
    )
    groups = defaultdict(list)
    for symbol, t in APPROVED_MINUTES:
        groups[symbol, iso(t)[:7]].append(t)
    entries = []
    for (symbol, month), missing in sorted(groups.items()):
        times = range(min(missing) - MINUTE, max(missing) + 2 * MINUTE, MINUTE)
        for dataset in ("marks", "minute_bars"):
            rows = []
            for t in times:
                if dataset == "marks" and t in missing:
                    continue
                row = dict(
                    symbol=symbol,
                    open_time=t,
                    available_at=t + MINUTE,
                    open="100",
                    high="100",
                    low="100",
                    close="100",
                    source_file="original.zip",
                )
                if dataset == "marks":
                    row["close_time"] = t + MINUTE - 1_000_000
                else:
                    row.update(
                        market="futures",
                        end_time=t + MINUTE,
                        base_volume="10",
                        quote_volume="1000",
                        trade_count=3,
                    )
                rows.append(row)
            path = tmp_path / f"original/{symbol}-{month}-{dataset}.parquet"
            path.parent.mkdir(exist_ok=True)
            table = pa.Table.from_pylist(rows)
            pq.write_table(table, path)
            entries.append(
                dict(
                    dataset=dataset,
                    symbol=symbol,
                    market="futures",
                    date=month,
                    path=path.relative_to(tmp_path).as_posix(),
                    rows=len(rows),
                    start=min(times) + MINUTE,
                    end=max(times) + MINUTE,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    complete=dataset != "marks",
                    minute_coverage_complete=dataset != "marks",
                    schema={f.name: str(f.type) for f in table.schema},
                )
            )
    manifests = tmp_path / "original/manifests"
    manifests.mkdir()
    (manifests / "processed.json").write_text(
        json.dumps(dict(kind="minute_market_data", entries=entries, errors=[]))
    )
    (manifests / "download.json").write_text('{"entries": []}')
    return config


def test_derived_layer_is_immutable_recomputable_and_requires_explicit_opt_in(tmp_path):
    import json

    from crypto_carry.data.mark_gaps import prepare_mark_gaps, verify_mark_derivation
    from crypto_carry.data.replay import iter_records
    from crypto_carry.data.validate import validate_data
    from crypto_carry.models import Mark

    config = source_fixture(tmp_path)
    originals = {p: p.read_bytes() for p in (tmp_path / "original").rglob("*") if p.is_file()}
    derived = prepare_mark_gaps(config, tmp_path, "futures_scaled")
    manifest = json.loads((tmp_path / derived.data_dir / "manifests/processed.json").read_text())
    assert len(verify_mark_derivation(derived, tmp_path, manifest)) == 15
    assert prepare_mark_gaps(config, tmp_path, "futures_scaled") == derived
    assert all(p.read_bytes() == content for p, content in originals.items())
    strict = derived.changed(mark_gap_method="strict")
    quality = validate_data(strict, tmp_path, "full")
    assert any("Strict validation refuses" in issue for issue in quality["issues"])
    with pytest.raises(ValueError, match="Strict"):
        list(
            iter_records(
                tmp_path,
                T,
                T + 3 * MINUTE,
                data_dir=derived.data_dir,
                execution_model="next_minute_vwap",
            )
        )
    records = list(
        iter_records(
            tmp_path,
            T,
            T + 3 * MINUTE,
            data_dir=derived.data_dir,
            execution_model="next_minute_vwap",
            mark_gap_method="futures_scaled",
        )
    )
    estimates = [
        r for r in records if isinstance(r, Mark) and r.source_file.startswith("estimated:")
    ]
    assert len(estimates) == 4
    assert min(r.available_at for r in estimates) == T + MINUTE
    assert all(r.estimation_method == "futures_scaled" for r in estimates)


def test_extra_missing_original_minute_is_rejected_even_with_updated_hash(tmp_path):
    import hashlib
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    from crypto_carry.data.mark_gaps import prepare_mark_gaps

    config = source_fixture(tmp_path)
    path = tmp_path / config.data_dir / "manifests/processed.json"
    manifest = json.loads(path.read_text())
    entry = next(
        e
        for e in manifest["entries"]
        if e["symbol"] == "ETHUSDT" and e["date"] == "2022-07" and e["dataset"] == "marks"
    )
    part = tmp_path / entry["path"]
    rows = pq.ParquetFile(part).read().to_pylist()
    rows = [r for r in rows if r["open_time"] != timestamp("2022-07-12T13:00:00Z")]
    pq.write_table(pa.Table.from_pylist(rows), part)
    entry.update(sha256=hashlib.sha256(part.read_bytes()).hexdigest(), rows=len(rows))
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="allowlist"):
        prepare_mark_gaps(config, tmp_path, "futures_scaled")


def test_changed_non_mark_input_cannot_hide_in_derived_manifest(tmp_path):
    import json

    from crypto_carry.data.mark_gaps import prepare_mark_gaps, verify_mark_derivation

    config = source_fixture(tmp_path)
    derived = prepare_mark_gaps(config, tmp_path, "last_official")
    manifest = json.loads((tmp_path / derived.data_dir / "manifests/processed.json").read_text())
    next(e for e in manifest["entries"] if e["dataset"] == "minute_bars")["rows"] -= 1
    with pytest.raises(ValueError, match="Non-estimated"):
        verify_mark_derivation(derived, tmp_path, manifest)


def test_normalization_cannot_overwrite_an_estimated_layer(tmp_path):
    from crypto_carry.data.normalize import normalize

    config = Config(
        analysis_mode="prescribed_research",
        fee_profile="prescribed_fixed_no_discounts",
        execution_model="next_minute_vwap",
        mark_gap_method="futures_scaled",
    )
    with pytest.raises(ValueError, match="derived"):
        normalize(config, tmp_path)

"""Semantic corruption must fail even after legitimately recomputing hashes."""

import csv
import hashlib
import json
from copy import deepcopy
from decimal import Decimal as D

import pytest

from scripts import verify_rules_sensitivity_correction as verify


def positions():
    return [
        dict(time_ns=0, symbol="BTCUSDT", spot="1", short="0", state="FLAT",
             dust_spot="1", collateral="0"),
        dict(time_ns=0, symbol="ETHUSDT", spot="2", short="2", state="OPEN",
             dust_spot="0", collateral="1"),
    ]


def interval_rows():
    return [
        dict(symbol="BTCUSDT", start_ns=0, end_ns=10_000_000_000,
             start_utc="1970-01-01T00:00:00.000000000Z",
             end_exclusive_utc="1970-01-01T00:00:10.000000000Z", seconds="10",
             exposure="dust", spot="1", short="0", state="FLAT", collateral_usdt="0",
             raw_invested=True, raw_unhedged=True),
        dict(symbol="ETHUSDT", start_ns=0, end_ns=10_000_000_000,
             start_utc="1970-01-01T00:00:00.000000000Z",
             end_exclusive_utc="1970-01-01T00:00:10.000000000Z", seconds="10",
             exposure="covered", spot="2", short="2", state="OPEN", collateral_usdt="1",
             raw_invested=True, raw_unhedged=False),
    ]


def seal(root):
    members = [dict(path=p.relative_to(root).as_posix(), size=p.stat().st_size,
                    sha256=hashlib.sha256(p.read_bytes()).hexdigest())
               for p in root.rglob("*") if p.is_file() and p.name not in {
                   "manifiesto_paquete.json", "manifiesto_paquete.sha256"}]
    path = root / "manifiesto_paquete.json"
    path.write_text(json.dumps(dict(schema=verify.SCHEMA, members=members)), encoding="utf-8")
    (root / "manifiesto_paquete.sha256").write_text(
        hashlib.sha256(path.read_bytes()).hexdigest() + "  manifiesto_paquete.json\n",
        encoding="utf-8")


def test_source_classification_and_portfolio_union_are_independent():
    rows = interval_rows()
    verify.check_interval_rows(rows, positions(), 0, 10_000_000_000, D("0.005"))
    summary = verify.aggregate_intervals(rows, [("full", 0, 10_000_000_000)])
    portfolio = next(row for row in summary if row["symbol"] == "PORTFOLIO")
    assert portfolio["invested_seconds"] == D("10")
    assert portfolio["dust_seconds"] == D("10")
    assert portfolio["dust_only_seconds"] == D("0")
    assert portfolio["unhedged_seconds"] == D("0")
    assert portfolio["raw_unhedged_seconds"] == D("10")
    assert portfolio["no_active_seconds"] == D("0")


@pytest.mark.parametrize("field,value", [
    ("start_ns", 1), ("end_ns", 9_000_000_000), ("seconds", "9"),
    ("exposure", "unhedged"), ("raw_invested", False), ("spot", "2"),
])
def test_rehashed_interval_corruption_is_detected(tmp_path, field, value):
    rows = interval_rows()
    rows[0][field] = value
    target = tmp_path / "exposicion_intervalos.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    seal(tmp_path)
    verify.check_manifest(tmp_path, verify.SCHEMA)
    with pytest.raises(ValueError):
        verify.check_interval_rows(verify.read_csv(target), positions(), 0, 10_000_000_000,
                                   D("0.005"))


def test_all_nonexposure_financial_fields_preserved_exactly():
    before = [dict(scenario="BASE_E3", strategy="conditional", run_id="x", period="full",
                   cagr="0.01000", sharpe="2", invested_seconds="9", invested_fraction=".9")]
    after = deepcopy(before)
    after[0].update(invested_seconds="1", invested_fraction=".1")
    verify.check_financial_preservation(after, before)
    after[0]["cagr"] = "0.01"
    with pytest.raises(ValueError, match="cagr"):
        verify.check_financial_preservation(after, before)


def test_manifest_rejects_unlisted_files_and_path_escape(tmp_path):
    (tmp_path / "kept.txt").write_text("evidence", encoding="utf-8")
    seal(tmp_path)
    (tmp_path / "unlisted.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(ValueError, match="unlisted"):
        verify.check_manifest(tmp_path, verify.SCHEMA)
    with pytest.raises(ValueError, match="path"):
        verify.safe_path(tmp_path, "../outside")


def test_summary_detects_duration_and_fraction_corruption():
    expected = verify.aggregate_intervals(interval_rows(), [("full", 0, 10_000_000_000)])
    actual = deepcopy(expected)
    actual[-1]["invested_seconds"] = D("11")
    with pytest.raises(ValueError):
        verify.check_summaries(actual, expected)


def test_output_cannot_overwrite_or_write_inside_either_package(tmp_path):
    parent, package = tmp_path / "parent", tmp_path / "package"
    parent.mkdir()
    package.mkdir()
    for output in (parent / "audit.json", package / "audit.json"):
        with pytest.raises(ValueError):
            verify.check_output(output, package, parent)
    existing = tmp_path / "audit.json"
    existing.write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError):
        verify.check_output(existing, package, parent)


def test_audit_output_cannot_enter_another_sealed_reference(tmp_path):
    reference = tmp_path / "e3"
    reference.mkdir()
    (reference / "manifest.json").write_text("{}", encoding="utf-8")
    (reference / "manifest.sha256").write_text("sealed", encoding="utf-8")
    with pytest.raises(ValueError, match="sealed"):
        verify.check_output(reference / "nested/audit.json", tmp_path / "v2", tmp_path / "v1")


@pytest.mark.parametrize("changed", [
    {"symbol": "UNKNOWN"}, {"time_ns": None}, {"spot": None},
    {"short": "NaN"}, {"state": ""}, {"collateral": "-1"},
])
def test_missing_or_invalid_source_metadata_is_not_silently_classified(changed):
    source = positions()
    source[0].update(changed)
    with pytest.raises((ValueError, TypeError)):
        verify._reconstruct(source, 0, 10_000_000_000, D("0.005"), verify.SYMBOLS)


@pytest.mark.parametrize("field,value", [
    ("seconds", "11"), ("exposure", "UNKNOWN"), ("start_ns", 1),
    ("end_ns", 9_000_000_000), ("raw_invested", False),
])
def test_union_rejects_invalid_intervals_instead_of_filling_the_calendar(field, value):
    rows = interval_rows()
    rows[0][field] = value
    with pytest.raises(ValueError):
        verify.aggregate_intervals(rows, [("full", 0, 10_000_000_000)])


def test_union_rejects_overlapping_trajectories_and_empty_periods():
    rows = interval_rows()
    with pytest.raises(ValueError):
        verify.aggregate_intervals(rows + [dict(rows[0])], [("full", 0, 10_000_000_000)])
    with pytest.raises(ValueError):
        verify.aggregate_intervals(rows, [("empty", 0, 0)])


def test_summary_identity_is_checked_even_when_numeric_values_match():
    expected = [dict(scenario="BASE_E3", strategy="conditional", run_id="c",
                     period="full", symbol="PORTFOLIO", invested_seconds=D("10"))]
    observed = [dict(expected[0], scenario="FUT4_DECISION")]
    with pytest.raises(ValueError, match="scenario"):
        verify.check_summaries(observed, expected)


def test_classification_preserves_dust_history_event_order_and_exclusive_end():
    source = [
        dict(time_ns=-2, symbol="BTCUSDT", spot=".2", short="0", state="FLAT"),
        dict(time_ns=-1, symbol="BTCUSDT", spot=".2", short="0", state="OPENING"),
        dict(time_ns=2, symbol="BTCUSDT", spot="1.2", short="1", state="OPENING"),
        dict(time_ns=2, symbol="BTCUSDT", spot="1.2", short="1.2", state="OPEN"),
        dict(time_ns=5, symbol="BTCUSDT", spot="1.2", short=".7", state="CLOSING"),
        dict(time_ns=7, symbol="BTCUSDT", spot="0", short=".2", state="FLAT"),
        dict(time_ns=9, symbol="BTCUSDT", spot="0", short="0", state="FLAT"),
        dict(time_ns=10, symbol="BTCUSDT", spot="7", short="7", state="OPEN"),
    ]
    rows = verify._reconstruct(source, 0, 10, D(".005"), ("BTCUSDT",))
    assert [(r["start_ns"], r["end_ns"], r["exposure"]) for r in rows] == [
        (0, 2, "dust"), (2, 5, "covered"), (5, 7, "unhedged"),
        (7, 9, "unhedged"), (9, 10, "flat"),
    ]
    assert sum(r["seconds"] for r in rows) == D("0.000000010")
    cut = verify.aggregate_intervals(rows, [("cut", 1, 8)], ("BTCUSDT",))[-1]
    assert cut["invested_seconds"] == D("0.000000006")
    assert cut["dust_only_seconds"] == D("0.000000001")
    assert cut["unhedged_seconds"] == D("0.000000003")


def h2_fixture():
    common = dict(scenario="BASE_E3", period="full", coverage_complete=True,
                  start_utc="2022-01-01T00:00:00Z", end_exclusive_utc="2023-01-01T00:00:00Z")
    metrics = [dict(common, strategy="conditional", run_id="c", cagr="-.01", sharpe="-.5"),
               dict(common, strategy="permanent", run_id="p", cagr="-.02", sharpe="-1")]
    h2 = dict(scenario="BASE_E3", period="full", conditional_run_id="c", permanent_run_id="p",
              conditional_cagr="-.01", conditional_sharpe="-.5", permanent_sharpe="-1",
              sharpe_difference=".5", cagr_positive=False, sharpe_superior=True,
              verdict="no_favorable", reason="cagr_not_positive")
    for field in ("start_utc", "end_exclusive_utc"):
        h2[field] = common[field]
        h2["conditional_" + field] = common[field]
        h2["permanent_" + field] = common[field]
    return metrics, [h2]


def write_rows(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.parametrize("changes", [
    {"cagr_positive": True, "verdict": "favorable",
     "reason": "cagr_positive_and_sharpe_superior"},
    {"verdict": "favorable", "reason": "sharpe_superior"},
    {"sharpe_superior": False}, {"sharpe_difference": ".6"},
])
def test_rehashed_h2_cannot_support_negative_cagr_despite_superior_sharpe(tmp_path, changes):
    metrics, rows = h2_fixture()
    verify.validate_h2_rows(rows, metrics)
    rows[0].update(changes)
    path = tmp_path / "h2.csv"
    write_rows(path, rows)
    seal(tmp_path)
    verify.check_manifest(tmp_path, verify.SCHEMA)
    with pytest.raises(ValueError, match="H2"):
        verify.validate_h2_rows(verify.read_csv(path), metrics)


@pytest.mark.parametrize("field", ["invested_seconds", "invested_fraction"])
def test_rehashed_summary_corruption_is_detected(tmp_path, field):
    expected = [dict(period="full", symbol="PORTFOLIO", invested_seconds=D("10"),
                     invested_fraction=D("1"))]
    rows = [dict(expected[0], **{field: "11"})]
    path = tmp_path / "summary.csv"
    write_rows(path, rows)
    seal(tmp_path)
    verify.check_manifest(tmp_path, verify.SCHEMA)
    with pytest.raises(ValueError, match="summary"):
        verify.check_summaries(verify.read_csv(path), expected)


def test_rehashed_financial_change_is_detected(tmp_path):
    metrics, _ = h2_fixture()
    changed = deepcopy(metrics)
    changed[0]["cagr"] = ".01"
    path = tmp_path / "metrics.csv"
    write_rows(path, changed)
    seal(tmp_path)
    verify.check_manifest(tmp_path, verify.SCHEMA)
    with pytest.raises(ValueError, match="cagr"):
        verify.check_financial_preservation(verify.read_csv(path), [
            {key: str(value) for key, value in row.items()} for row in metrics])


def test_v2_cannot_request_legacy_schema_compatibility(tmp_path):
    (tmp_path / "kept.txt").write_text("evidence", encoding="utf-8")
    seal(tmp_path)
    path = tmp_path / "manifiesto_paquete.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["schema"] = verify.KNOWN_PARENT_SCHEMA
    path.write_text(json.dumps(record), encoding="utf-8")
    (tmp_path / "manifiesto_paquete.sha256").write_text(verify.sha256(path), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported schema"):
        verify.check_manifest(tmp_path, verify.SCHEMA)


def record(root, relative):
    path = root / relative
    return dict(path=relative, size=path.stat().st_size, sha256=verify.sha256(path))


def provenance_fixture(tmp_path):
    parent, package = tmp_path / "parent", tmp_path / "package"
    parent.mkdir()
    package.mkdir()
    (parent / "source.csv").write_text("parent inputs", encoding="utf-8")
    parent_manifest = dict(schema=verify.KNOWN_PARENT_SCHEMA,
                           members=[record(parent, "source.csv")])
    (parent / "manifiesto_paquete.json").write_text(json.dumps(parent_manifest), encoding="utf-8")
    parent_hash = verify.sha256(parent / "manifiesto_paquete.json")
    (parent / "manifiesto_paquete.sha256").write_text(parent_hash, encoding="utf-8")
    tools = ["correct_rules_sensitivity_report.py", "rules_sensitivity_correction_docs.py",
             "rules_sensitivity_exposure.py", "rules_sensitivity_h2.py",
             "verify_rules_sensitivity_package.py", "verify_rules_sensitivity_correction.py"]
    for name in tools:
        path = package / "herramientas" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("# archived postprocessor\n", encoding="utf-8")
    reference = package / "referencia_e3"
    names = ["tablas/exposicion_intervalos.csv", "tablas/tiempo_invertido.csv",
             "tablas/episodio_2023_03_24_exposicion.csv",
             "codigo/scripts/continuous_delivery/portfolio.py",
             "codigo/scripts/continuous_delivery/common.py",
             "codigo/scripts/continuous_delivery/build.py",
             "codigo/src/crypto_carry/strategy.py", "codigo/src/crypto_carry/reporting.py"]
    for name in names:
        path = reference / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("preserved E3 reference\n", encoding="utf-8")
    (reference / "manifest.json").write_text(json.dumps(dict(
        file_hashes={name: verify.sha256(reference / name) for name in names})), encoding="utf-8")
    (reference / "manifest.sha256").write_text(verify.sha256(reference / "manifest.json"),
                                               encoding="utf-8")
    proof = dict(schema=verify.SCHEMA, parent_schema=verify.KNOWN_PARENT_SCHEMA,
                 parent_manifest_sha256=parent_hash, postprocessor_version="exposure_h2_v2",
                 parent_argument_required=True, engine_reexecution=False,
                 source_files=[record(parent, name) for name in (
                     "source.csv", "manifiesto_paquete.json", "manifiesto_paquete.sha256")],
                 postprocessor_files=[record(package, "herramientas/" + name) for name in tools],
                 e3_reference_files=[record(reference, name) for name in (
                     *names, "manifest.json", "manifest.sha256")])
    manifest = dict(schema=verify.SCHEMA, parent_manifest_sha256=parent_hash,
                    postprocessor_version="exposure_h2_v2")
    return parent, package, proof, manifest


@pytest.mark.parametrize("field", ["source_files", "postprocessor_files", "e3_reference_files"])
def test_v2_rejects_omitted_mandatory_provenance_even_with_valid_remaining_hashes(tmp_path, field):
    parent, package, proof, manifest = provenance_fixture(tmp_path)
    proof[field].pop()
    (package / "procedencia.json").write_text(json.dumps(proof), encoding="utf-8")
    with pytest.raises(ValueError, match="provenance"):
        verify._check_provenance(package, parent, manifest)


def test_reference_cannot_rehash_an_e3_source_against_its_preserved_manifest(tmp_path):
    parent, package, proof, manifest = provenance_fixture(tmp_path)
    relative = "tablas/tiempo_invertido.csv"
    reference = package / "referencia_e3"
    (reference / relative).write_text("changed historical value", encoding="utf-8")
    proof["e3_reference_files"] = [
        record(reference, row["path"]) for row in proof["e3_reference_files"]]
    (package / "procedencia.json").write_text(json.dumps(proof), encoding="utf-8")
    with pytest.raises(ValueError, match="E3"):
        verify._check_provenance(package, parent, manifest)


def test_complete_provenance_is_accepted_without_repo_or_head(tmp_path):
    parent, package, proof, manifest = provenance_fixture(tmp_path)
    (package / "procedencia.json").write_text(json.dumps(proof), encoding="utf-8")
    assert verify._check_provenance(package, parent, manifest) == proof


@pytest.mark.parametrize("field,value", [
    ("engine_code_hash", "new-postprocessor-hash"), ("run_manifest_sha256", "wrong"),
    ("positions_rows", 3), ("status", "ejecutado"), ("engine_status", "insolvent"),
    ("postprocessor_version", "v1"), ("strategy", "permanent"),
])
def test_run_provenance_binds_economic_code_and_new_postprocessor_separately(field, value):
    expected = [dict(scenario="BASE_E3", strategy="conditional", run_id="c",
                     status="reutilizado_verificado", engine_status="complete",
                     engine_code_hash="original-engine", run_manifest_sha256="sealed-run",
                     positions_rows=2, postprocessor_version="exposure_h2_v2")]
    changed = [dict(expected[0], **{field: value})]
    with pytest.raises(ValueError, match="provenance"):
        verify.check_run_provenance(changed, changed, expected)


def test_run_provenance_uses_explicit_contract_instead_of_parent_index_shape():
    expected = [dict(scenario="BASE_E3", strategy="conditional", run_id="c",
                     status="reutilizado_verificado", engine_status="complete",
                     engine_code_hash="original-engine", run_manifest_sha256="sealed-run",
                     positions_rows=2, postprocessor_version="exposure_h2_v2")]
    csv_rows = [{key: str(value) for key, value in row.items()} for row in expected]
    verify.check_run_provenance(expected, csv_rows, expected)


def test_archived_parent_verifier_does_not_write_bytecode(tmp_path):
    path = tmp_path / "herramientas/verify_rules_sensitivity_package.py"
    path.parent.mkdir()
    path.write_text("def verify_package(package):\n    return {'status': 'passed'}\n", encoding="utf-8")
    module = verify._archived_verifier(tmp_path)
    assert module.verify_package(tmp_path) == {"status": "passed"}
    assert [p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()] == [
        "herramientas/verify_rules_sensitivity_package.py"]


def e3_equivalence_fixture(tmp_path):
    intervals, summaries, episodes = [], [], []
    old_intervals, old_summaries, old_episodes = [], [], []
    for strategy, run_id in (("conditional", "c"), ("permanent", "p")):
        identity = dict(scenario="BASE_E3", strategy=strategy, run_id=run_id)
        for row in interval_rows():
            intervals.append(dict(identity, **row))
            original = {key: value for key, value in row.items() if not key.startswith("raw_")}
            old_intervals.append(dict(original, strategy=strategy, source_run_id=run_id))
        for period in ("full", "2022-2023", "2024+", "2023-03-24"):
            for symbol in ("BTCUSDT", "ETHUSDT", "PORTFOLIO"):
                active = symbol != "BTCUSDT"
                row = dict(identity, period=period, symbol=symbol, calendar_seconds="10",
                           invested_seconds="10" if active else "0", unhedged_seconds="0",
                           covered_seconds="10" if active else "0", no_inventory_seconds="0",
                           no_active_seconds="0" if active else "10", both_covered_seconds="0",
                           dust_seconds="10" if symbol != "ETHUSDT" else "0")
                old = dict(period="2024-2026-08" if period == "2024+" else period,
                           symbol=symbol, covered_seconds="", unhedged_seconds="", dust_seconds="",
                           flat_seconds="", invested_seconds=row["invested_seconds"],
                           calendar_seconds="10", strategy=strategy, source_run_id=run_id,
                           any_unhedged_seconds="", any_covered_seconds="",
                           both_covered_seconds="", cash_or_dust_seconds="")
                if symbol == "PORTFOLIO":
                    old.update(any_unhedged_seconds="0", any_covered_seconds="10",
                               both_covered_seconds="0", cash_or_dust_seconds="0")
                else:
                    old.update(covered_seconds=row["covered_seconds"], unhedged_seconds="0",
                               dust_seconds=row["dust_seconds"], flat_seconds="0")
                (episodes if period == "2023-03-24" else summaries).append(row)
                (old_episodes if period == "2023-03-24" else old_summaries).append(old)
    directory = tmp_path / "referencia_e3/tablas"
    write_rows(directory / "exposicion_intervalos.csv", old_intervals)
    write_rows(directory / "tiempo_invertido.csv", old_summaries)
    write_rows(directory / "episodio_2023_03_24_exposicion.csv", old_episodes)
    return intervals, summaries, episodes


def test_e3_comparison_checks_exact_intervals_seconds_and_original_run_ids(tmp_path):
    intervals, summaries, episodes = e3_equivalence_fixture(tmp_path)
    result = verify.check_e3_equivalence(tmp_path, intervals, summaries, episodes)
    assert result == [
        dict(strategy="conditional", intervals_checked=2, summaries_checked=9,
             episode_rows_checked=3, exact=True, terminal_difference_ns=0),
        dict(strategy="permanent", intervals_checked=2, summaries_checked=9,
             episode_rows_checked=3, exact=True, terminal_difference_ns=0),
    ]


@pytest.mark.parametrize("table,field,value", [
    ("interval", "end_ns", 9_999_999_999), ("interval", "seconds", "9.999999999"),
    ("interval", "exposure", "unhedged"), ("interval", "run_id", "new-base"),
    ("summary", "invested_seconds", ".000000001"),
    ("summary", "run_id", "new-base"), ("episode", "unhedged_seconds", "1"),
])
def test_e3_rejects_even_one_nanosecond_or_identity_difference(tmp_path, table, field, value):
    intervals, summaries, episodes = e3_equivalence_fixture(tmp_path)
    {"interval": intervals, "summary": summaries, "episode": episodes}[table][0][field] = value
    with pytest.raises(ValueError, match="E3"):
        verify.check_e3_equivalence(tmp_path, intervals, summaries, episodes)


def derived_tables_fixture(tmp_path):
    parent, package = tmp_path / "parent", tmp_path / "package"
    parent.mkdir()
    package.mkdir()
    identity_keys = ("scenario", "strategy", "run_id", "period")
    source, h2 = h2_fixture()
    before, after, summaries, changes, preservation = [], [], [], [], []
    for item in source:
        original = {key: str(value) for key, value in item.items()}
        original.update(invested_seconds="10", unhedged_seconds="10", invested_fraction="1")
        identity = {key: original[key] for key in identity_keys}
        durations = dict(invested_seconds=D(10), unhedged_seconds=D(0), invested_fraction=D(1),
                         raw_invested_seconds=D(10), raw_unhedged_seconds=D(10),
                         raw_invested_fraction=D(1), covered_seconds=D(10), dust_seconds=D(10),
                         dust_only_seconds=D(0), no_active_seconds=D(0),
                         no_inventory_seconds=D(0), calendar_seconds=D(10))
        before.append(original)
        after.append(dict(original, **durations))
        summaries.append(dict(identity, symbol="PORTFOLIO", **durations))
        changes.append(dict(identity, start_utc=original["start_utc"],
                            end_exclusive_utc=original["end_exclusive_utc"], old_invested_seconds="10",
                            old_unhedged_seconds="10", old_invested_fraction="1", **durations,
                            delta_invested_seconds="0", delta_unhedged_seconds="-10",
                            h2_before="favorable", h2_after="no_favorable", h2_changed=True))
        preservation.extend(dict(identity, metric=key, value_before=value, value_after=value,
                                  unchanged=True) for key, value in original.items()
                            if key not in verify.EXPOSURE_FIELDS)
    write_rows(parent / "comparacion/h2.csv", [dict(scenario="BASE_E3", period="full",
                                                    verdict="favorable")])
    write_rows(package / "comparacion/antes_despues.csv", changes)
    write_rows(package / "comparacion/figuras/exposicion_datos.csv", changes)
    write_rows(package / "comparacion/h2_cambios.csv", [dict(
        scenario="BASE_E3", period="full", conditional_run_id="c", permanent_run_id="p",
        verdict_before="favorable", verdict_after="no_favorable", changed=True)])
    write_rows(package / "comparacion/preservacion_financiera.csv", preservation)
    preserved = []
    for name in (*("comparacion/" + n for n in verify.PRESERVED_TABLES), "indice_corridas.json"):
        for root in (parent, package):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"exact economic evidence\n")
        preserved.append(dict(path=name, parent_sha256=verify.sha256(parent / name),
                              corrected_sha256=verify.sha256(package / name), equal_bytes=True))
    write_rows(package / "comparacion/preservacion_tablas.csv", preserved)
    write_rows(package / "comparacion/episodio_2023_03_24.csv", [], (*identity_keys, "symbol"))
    for root in (parent, package):
        write_rows(root / "comparacion/deltas.csv", [], ("scenario", "strategy", "period", "metric"))
    return package, parent, after, before, h2, summaries, []


def test_derived_tables_match_independent_values_without_importing_builder(tmp_path):
    verify.check_derived_tables(*derived_tables_fixture(tmp_path))


@pytest.mark.parametrize("table,field,value", [
    ("antes_despues.csv", "old_invested_seconds", "9"),
    ("antes_despues.csv", "invested_fraction", ".9"),
    ("antes_despues.csv", "delta_unhedged_seconds", "0"),
    ("antes_despues.csv", "h2_after", "favorable"),
    ("figuras/exposicion_datos.csv", "raw_unhedged_seconds", "9"),
    ("preservacion_financiera.csv", "value_after", "changed"),
    ("h2_cambios.csv", "verdict_after", "favorable"),
])
def test_rehashed_before_after_figure_and_preservation_corruption_is_detected(
    tmp_path, table, field, value
):
    args = derived_tables_fixture(tmp_path)
    package = args[0]
    path = package / "comparacion" / table
    rows = verify.read_csv(path)
    rows[0][field] = value
    write_rows(path, rows)
    seal(package)
    verify.check_manifest(package, verify.SCHEMA)
    with pytest.raises(ValueError):
        verify.check_derived_tables(*args)

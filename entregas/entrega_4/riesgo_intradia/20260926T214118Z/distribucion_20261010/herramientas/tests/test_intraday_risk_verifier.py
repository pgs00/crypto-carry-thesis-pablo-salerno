"""Independent arithmetic, rehashed corruption and read-only verifier behavior."""

import csv
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest


def verifier():
    return importlib.import_module("scripts.verify_intraday_risk")


def csv_file(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def seal(root):
    module = verifier()
    files = [
        dict(path=p.relative_to(root).as_posix(), bytes=p.stat().st_size, sha256=module.sha256(p))
        for p in root.rglob("*")
        if p.is_file() and p.name not in {"manifiesto_paquete.json", "manifiesto_paquete.sha256"}
    ]
    path = root / "manifiesto_paquete.json"
    path.write_text(
        json.dumps(
            dict(
                schema="intraday_risk_package_v1",
                files=files,
                parent_manifest_sha256="0" * 64,
                correction_manifest_sha256="1" * 64,
                full_series_in_compact_package=False,
            )
        ),
        encoding="utf-8",
    )
    (root / "manifiesto_paquete.sha256").write_text(module.sha256(path), encoding="utf-8")


def dd_row():
    row = dict(
        scenario="BASE_E3",
        strategy="conditional",
        run_id="c",
        period="full",
        peak_policy="period_reset",
        valuation="original_reconstructed",
        start_utc="2022-01-01T00:00:00Z",
        end_exclusive_utc="2023-01-01T00:00:00Z",
        extra_drawdown_pp=20,
        extra_peak_to_trough_loss_usdt=20,
        daily_zero_dd=True,
        nested_daily_check=True,
    )
    for prefix, peak, trough, drawdown, loss in (
        ("daily", 101, 101, 0, 0),
        ("intraday", 100, 80, -0.2, 20),
    ):
        row.update(
            {
                f"{prefix}_peak_equity": peak,
                f"{prefix}_trough_equity": trough,
                f"{prefix}_drawdown": drawdown,
                f"{prefix}_loss_usdt": loss,
                f"{prefix}_peak_time_ns": 1,
                f"{prefix}_trough_time_ns": 2,
                f"{prefix}_recovery_time_ns": 3,
                f"{prefix}_complete": True,
                f"{prefix}_missing_observations": 0,
                f"{prefix}_reason": "",
            }
        )
    return row


def test_literal_drawdown_arithmetic_does_not_claim_complete_series_recomputation():
    assert verifier().check_drawdown_rows([dd_row()]) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("intraday_drawdown", -0.1),
        ("intraday_loss_usdt", 10),
        ("intraday_peak_equity", 90),
        ("extra_drawdown_pp", 10),
        ("extra_peak_to_trough_loss_usdt", 0),
        ("daily_zero_dd", False),
        ("intraday_recovery_time_ns", 0),
        ("intraday_missing_observations", 1),
    ],
)
def test_rehashed_drawdown_corruption_still_fails(tmp_path, field, value):
    row = dict(dd_row(), **{field: value})
    path = tmp_path / "drawdown.csv"
    csv_file(path, [row])
    seal(tmp_path)
    verifier().verify_manifest(tmp_path)
    with pytest.raises(ValueError):
        verifier().check_drawdown_rows(verifier().read_csv(path))


def episode_fixture():
    common = dict(scenario="BASE_E3", strategy="conditional", run_id="c")
    intervals = [
        dict(
            common,
            symbol="BTCUSDT",
            start_ns=a,
            end_ns=b,
            seconds=(b - a) / 1e9,
            exposure=state,
            state=engine,
        )
        for a, b, state, engine in (
            (0, 1_000_000_000, "flat", "FLAT"),
            (1_000_000_000, 2_000_000_000, "unhedged", "OPENING"),
            (2_000_000_000, 3_000_000_000, "unhedged", "CLOSING"),
            (3_000_000_000, 4_000_000_000, "dust", "FLAT"),
        )
    ]
    intervals.append(
        dict(
            common,
            symbol="ETHUSDT",
            start_ns=0,
            end_ns=4_000_000_000,
            seconds=4,
            exposure="flat",
            state="FLAT",
        )
    )
    episodes = [
        dict(
            common,
            symbol="BTCUSDT",
            episode_id="c_BTC_001",
            cycle_id="a",
            start_ns=1_000_000_000,
            end_ns=3_000_000_000,
            seconds=2,
            states="CLOSING;OPENING",
            start_post_equity_usdt=100,
            end_post_equity_usdt=101,
            portfolio_change_usdt=1,
            worst_portfolio_change_usdt=-20,
        )
    ]
    return intervals, episodes


def test_episode_catalog_covers_all_unhedged_time_without_counting_dust():
    intervals, episodes = episode_fixture()
    assert verifier().check_episode_catalog(intervals, episodes, 0, 4_000_000_000) == 1


@pytest.mark.parametrize(
    "field,value",
    [("seconds", 1), ("end_ns", 4_000_000_000), ("portfolio_change_usdt", 0), ("states", "FLAT")],
)
def test_rehashed_episode_corruption_fails(tmp_path, field, value):
    intervals, episodes = episode_fixture()
    episodes[0][field] = value
    path = tmp_path / "episodes.csv"
    csv_file(path, episodes)
    seal(tmp_path)
    verifier().verify_manifest(tmp_path)
    with pytest.raises(ValueError):
        verifier().check_episode_catalog(intervals, verifier().read_csv(path), 0, 4_000_000_000)


def test_missing_episode_duplicate_episode_and_split_same_cycle_are_rejected():
    intervals, episodes = episode_fixture()
    for changed in (
        [],
        episodes * 2,
        [
            dict(episodes[0], end_ns=2_000_000_000, seconds=1, states="OPENING"),
            dict(
                episodes[0], episode_id="two", start_ns=2_000_000_000, seconds=1, states="CLOSING"
            ),
        ],
    ):
        with pytest.raises(ValueError):
            verifier().check_episode_catalog(intervals, changed, 0, 4_000_000_000)


def margin_fixture():
    values = dict(
        run_id=np.array(["c", "c"]),
        time_ns=np.array([0, 1_000_000_000]),
        sequence=np.array([0, 0]),
        phase=np.array([0, 0]),
        state_index=np.array([0, 1]),
        free_spot_usdt=np.array([0.0, 0.0]),
        free_futures_usdt=np.array([0.0, 0.0]),
        debt_usdt=np.array([0.0, 0.0]),
        free_cash_usdt=np.array([0.0, 0.0]),
        equity_usdt=np.array([120.0, 120.0]),
        equity_proxy_usdt=np.array([120.0, 120.0]),
        maintenance_need_joint_usdt=np.array([0.0, 0.0]),
        preventive_need_joint_infimum_usdt=np.array([0.0, 7.006]),
        preventive_joint_strict=np.array([False, False]),
        reservations_reserved_cash=np.array([0.0, 0.0]),
        reservations_available_known=np.array([True, True]),
        reservations_reason=np.array(["verified_no_reservation"] * 2, dtype=object),
        redistributable_cash_usdt=np.array([0.0, 0.0]),
    )
    for symbol in ("BTCUSDT", "ETHUSDT"):
        active = symbol == "BTCUSDT"
        fields = dict(
            spot=[1, 1] if active else [0, 0],
            short=[1, 1] if active else [0, 0],
            average=[100, 100],
            collateral=[20, 20] if active else [0, 0],
            spot_price=[100, 110],
            spot_proxy=[100, 110],
            mark_price=[100, 110],
            notional_usdt=[100, 110] if active else [0, 0],
            margin_balance_usdt=[20, 10] if active else [0, 0],
            maintenance_usdt=[0.4, 0.44] if active else [0, 0],
            headroom_usdt=[19.6, 9.56] if active else [0, 0],
            margin_ratio=[0.02, 0.044] if active else [np.nan, np.nan],
            liquidation_price=[120 / 1.004] * 2 if active else [np.nan, np.nan],
            liquidation_distance=[(120 / 1.004 - 100) / 100, (120 / 1.004 - 110) / 110]
            if active
            else [np.nan, np.nan],
            preventive_topup_infimum_usdt=[0, 7.006] if active else [0, 0],
            maintenance_shortfall_usdt=[0, 0],
            preventive_topup_strict=[False, False],
            net_exposure_usdt=[0, 0],
        )
        values.update({f"{symbol}_{key}": np.asarray(value) for key, value in fields.items()})
    for prefix, amount in (("maintenance", [0, 0]), ("preventive", [0, 7.006])):
        for suffix in (
            "external_deficit_usdt",
            "external_lower_bound_usdt",
            "external_upper_bound_usdt",
        ):
            values[f"{prefix}_{suffix}"] = np.asarray(amount, dtype=float)
    return values


def test_compact_equity_and_margin_arithmetic_is_independent():
    assert verifier().check_evidence_columns(margin_fixture(), "run_id") == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("equity_usdt", 121),
        ("BTCUSDT_margin_balance_usdt", 21),
        ("BTCUSDT_headroom_usdt", 20),
        ("BTCUSDT_margin_ratio", 0.01),
        ("ETHUSDT_maintenance_usdt", 1),
        ("ETHUSDT_margin_ratio", 0),
        ("preventive_need_joint_infimum_usdt", 9),
        ("redistributable_cash_usdt", 1),
        ("BTCUSDT_liquidation_distance", 0.5),
        ("BTCUSDT_net_exposure_usdt", 100),
    ],
)
def test_rehashed_margin_parquet_corruption_is_detected(tmp_path, field, value):
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows = margin_fixture()
    rows[field][0] = value
    path = tmp_path / "margin.parquet"
    pq.write_table(pa.table(rows), path)
    seal(tmp_path)
    verifier().verify_manifest(tmp_path)
    with pytest.raises(ValueError):
        verifier().check_evidence_columns(verifier().read_arrays(path), "run_id")


def test_chronological_phase_order_cannot_be_rearranged():
    rows = margin_fixture()
    rows["time_ns"] = np.array([0, 0])
    rows["phase"] = np.array([2, 1])
    rows["sequence"] = np.array([1, 0])
    with pytest.raises(ValueError, match="order|phase|sequence"):
        verifier().check_evidence_columns(rows, "run_id")


def test_daily_reconciliation_preserves_existing_monetary_tolerance():
    rows = [
        dict(
            run_id="c",
            time_ns=86_399_999_999_999,
            original_equity="100",
            reconstructed_equity="100.000000001",
            residual_usdt=".000000001",
            ok=True,
        )
    ]
    assert verifier().check_reconciliations(rows) == 1
    rows[0].update(reconstructed_equity="100.00000002", residual_usdt=".00000002")
    with pytest.raises(ValueError):
        verifier().check_reconciliations(rows)


def test_reused_financial_metrics_are_exact_and_complete():
    rows = [
        dict(
            scenario="BASE_E3",
            strategy="conditional",
            run_id="c",
            period="2025",
            cagr=".001000",
            sharpe=".2",
            net_pnl_usdt="10.123456789",
        )
    ]
    verifier().check_reused_metrics(rows, rows)
    with pytest.raises(ValueError):
        verifier().check_reused_metrics([dict(rows[0], cagr=".001")], rows)


def test_paths_extras_and_cache_members_are_rejected(tmp_path):
    (tmp_path / "kept.txt").write_text("evidence", encoding="utf-8")
    seal(tmp_path)
    verifier().verify_manifest(tmp_path)
    for name in ("../escape", "C:/outside", "a\\b"):
        with pytest.raises(ValueError):
            verifier().safe_path(tmp_path, name)
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__/cached.pyc").write_bytes(b"cache")
    seal(tmp_path)
    with pytest.raises(ValueError, match="cache"):
        verifier().verify_manifest(tmp_path)


def test_relocated_cli_without_bytecode_flag_is_read_only_on_failure(tmp_path):
    tools = tmp_path / "package/herramientas"
    tools.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1] / "scripts/verify_intraday_risk.py"
    shutil.copyfile(source, tools / source.name)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = subprocess.run(
        [
            sys.executable,
            str(tools / source.name),
            "--package",
            str(tools.parent),
            "--scope",
            "compact",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "failed"
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after


def test_output_must_be_new_and_external_to_all_sealed_inputs(tmp_path):
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        verifier().check_output(tmp_path / "audit/result.json", [tmp_path / "child"])


def test_complete_scope_requires_explicit_dependencies_without_recorded_path_fallback(tmp_path):
    (tmp_path / "data.txt").write_text("placeholder", encoding="utf-8")
    seal(tmp_path)
    with pytest.raises(ValueError, match="requires.*parent.*correction.*series.*data"):
        verifier().verify_package(tmp_path, scope="complete")


def test_compact_cannot_omit_required_semantic_evidence_by_rehashing(tmp_path):
    (tmp_path / "data.txt").write_text("placeholder", encoding="utf-8")
    seal(tmp_path)
    with pytest.raises(ValueError, match="missing mandatory"):
        verifier().verify_package(tmp_path, scope="compact")


def test_complete_drawdown_recomputes_the_nadir_instead_of_trusting_peak_cells():
    row = dd_row()
    row.update(
        start_utc="1970-01-01T00:00:00Z",
        end_exclusive_utc="1970-01-01T00:00:00.000000004Z",
        intraday_peak_time_ns=0,
        daily_peak_time_ns=3,
        daily_trough_time_ns=3,
    )
    run = dict(
        identity={key: row[key] for key in ("scenario", "strategy", "run_id")},
        config=dict(capital="100", start="1970-01-01T00:00:00Z"),
        daily=[dict(time_ns=3, equity="101")],
    )
    metric = dict(
        run_id="c",
        period="full",
        starting_equity_usdt="100",
        start_utc=row["start_utc"],
        end_exclusive_utc=row["end_exclusive_utc"],
    )
    eq = dict(
        time_ns=np.array([1, 2, 3]),
        equity_usdt=np.array([100.0, 80.0, 101.0]),
        equity_proxy_usdt=np.array([100.0, 80.0, 101.0]),
    )
    verifier().check_full_drawdowns([row], [run], [metric], {"c": eq})
    # Both export arithmetic and its fabricated endpoints agree, but the full
    # series still contains the actual 80-USDT trough.
    row.update(
        intraday_trough_equity=90,
        intraday_drawdown=-0.1,
        intraday_loss_usdt=10,
        extra_drawdown_pp=10,
        extra_peak_to_trough_loss_usdt=10,
    )
    verifier().check_drawdown_rows([row])
    with pytest.raises(ValueError):
        verifier().check_full_drawdowns([row], [run], [metric], {"c": eq})


def test_csv_temporal_keys_match_native_integers_without_float_rounding():
    verifier()._compare_rows(
        [{"time_ns": "1700000000000000001", "amount": "1.25"}],
        [{"time_ns": 1700000000000000001, "amount": 1.25}],
        ("time_ns",),
        "literal clock",
    )
    with pytest.raises(ValueError):
        verifier()._compare_rows(
            [{"time_ns": "1700000000000000000", "amount": "1.25"}],
            [{"time_ns": 1700000000000000001, "amount": 1.25}],
            ("time_ns",),
            "changed clock",
        )


def test_debt_reduces_redistributable_cash_before_joint_requirements():
    values = margin_fixture()
    values["free_spot_usdt"][:] = 10
    values["free_cash_usdt"][:] = 10
    values["debt_usdt"][:] = 8
    values["equity_usdt"][:] = 122
    values["equity_proxy_usdt"][:] = 122
    values["redistributable_cash_usdt"][:] = 2
    for suffix in (
        "external_deficit_usdt",
        "external_lower_bound_usdt",
        "external_upper_bound_usdt",
    ):
        values[f"preventive_{suffix}"][:] = [0, 5.006]
    assert verifier().check_evidence_columns(values, "run_id") == 2
    values["redistributable_cash_usdt"][:] = 10
    with pytest.raises(ValueError):
        verifier().check_evidence_columns(values, "run_id")


def test_episode_active_extrema_include_intermediate_other_asset_posts_and_exclude_new_inventory():
    values = dict(
        episode_id=np.array(["e"] * 5),
        time_ns=np.array([1, 2, 2, 2, 2]),
        phase=np.array([2, 1, 2, 2, 2]),
        equity_usdt=np.array([100.0, 90.0, 80.0, 40.0, 30.0]),
        equity_proxy_usdt=np.array([100.0, 91.0, 81.0, 41.0, 31.0]),
        BTCUSDT_asset_pnl_usdt=np.array([10.0, 9.0, 9.0, 1.0, 0.0]),
        BTCUSDT_spot=np.array([1.0, 1.0, 1.0, 0.0, 2.0]),
        BTCUSDT_short=np.array([0.0, 0.0, 0.0, 1.0, 2.0]),
        BTCUSDT_net_exposure_usdt=np.array([10.0, 9.0, 9.0, -100.0, 0.0]),
        BTCUSDT_spot_age_ns=np.array([0, 2, 2, 100, 200]),
    )
    row = dict(
        episode_id="e",
        symbol="BTCUSDT",
        start_ns=1,
        end_ns=2,
        start_post_equity_usdt=100,
        end_post_equity_usdt=30,
        portfolio_change_usdt=-70,
        worst_portfolio_change_usdt=-20,
        asset_change_usdt=-10,
        worst_asset_change_usdt=-1,
        worst_proxy_portfolio_change_usdt=-19,
        maximum_spot_quantity=1,
        maximum_short_quantity=0,
        maximum_signed_net_exposure_usdt=10,
        minimum_signed_net_exposure_usdt=9,
        maximum_absolute_net_exposure_usdt=10,
        maximum_spot_age_seconds=2e-9,
    )
    verifier()._episode_values(values, [row])
    with pytest.raises(ValueError):
        verifier()._episode_values(values, [dict(row, worst_portfolio_change_usdt=-70)])


def test_compact_evidence_must_match_original_reconstruction_even_if_equity_arithmetic_agrees():
    source = margin_fixture()
    compact = {key: value.copy() for key, value in source.items()}
    verifier().check_series_evidence(compact, source, np.arange(2), "fixture")
    compact["free_spot_usdt"] += 5
    compact["free_cash_usdt"] += 5
    compact["redistributable_cash_usdt"] += 5
    compact["equity_usdt"] += 5
    compact["equity_proxy_usdt"] += 5
    for suffix in (
        "external_deficit_usdt",
        "external_lower_bound_usdt",
        "external_upper_bound_usdt",
    ):
        compact[f"preventive_{suffix}"][:] = [0, 2.006]
    verifier().check_evidence_columns(compact, "run_id")
    with pytest.raises(ValueError):
        verifier().check_series_evidence(compact, source, np.arange(2), "fixture")


def test_complete_evidence_checks_exact_sequence_coverage_and_missing_rows():
    source = margin_fixture()
    source["time_ns"][:] = 0
    source["sequence"][:] = [0, 1]
    compact = {key: value[:1].copy() for key, value in source.items()}
    with pytest.raises(ValueError, match="coverage"):
        verifier().check_series_evidence(compact, source, np.arange(2), "missing post")
    compact["sequence"][0] = 2
    with pytest.raises(ValueError, match="coverage|clock"):
        verifier().check_series_evidence(compact, source, np.arange(1), "false clock")


def test_extreme_point_margin_fields_and_drawdown_timing_are_checked():
    source = margin_fixture()
    row = {key: value[0] for key, value in source.items()}
    row.update(
        scenario="BASE_E3",
        strategy="conditional",
        label="worst_equity_drawdown",
        timestamp_utc="1970-01-01T00:00:00Z",
    )
    dd = dict(dd_row(), intraday_trough_time_ns=0, intraday_trough_equity=120)
    assert verifier().check_extreme_points([row], [dd], []) == 1
    with pytest.raises(ValueError):
        verifier().check_extreme_points([dict(row, BTCUSDT_headroom_usdt=18)], [dd], [])
    with pytest.raises(ValueError):
        verifier().check_extreme_points([row], [dict(dd, intraday_trough_time_ns=1)], [])


def test_unknown_reservations_preserve_nd_and_hypothetical_bounds_with_a_reason():
    values = margin_fixture()
    values["reservations_available_known"][:] = False
    values["reservations_reason"][:] = "intermediate_order_state_unobservable"
    values["redistributable_cash_usdt"][:] = np.nan
    values["preventive_external_deficit_usdt"][1] = np.nan
    assert verifier().check_evidence_columns(values, "run_id") == 2
    values["reservations_reason"][:] = ""
    with pytest.raises(ValueError, match="reason"):
        verifier().check_evidence_columns(values, "run_id")


def test_nonpositive_margin_balance_cannot_be_reported_with_a_safe_ratio():
    values = margin_fixture()
    values["BTCUSDT_collateral"][0] = 0
    values["BTCUSDT_margin_balance_usdt"][0] = 0
    values["BTCUSDT_headroom_usdt"][0] = -0.4
    values["BTCUSDT_margin_ratio"][0] = 0
    values["equity_usdt"][0] = 100
    values["equity_proxy_usdt"][0] = 100
    with pytest.raises(ValueError, match="ratio"):
        verifier().check_evidence_columns(values, "run_id")


def test_episode_groups_use_last_physical_cycle_at_tied_event_time():
    intervals, episodes = episode_fixture()
    run = dict(
        identity={key: episodes[0][key] for key in verifier().IDENTITY},
        intervals=intervals,
        events=[
            dict(time_ns=0, symbol="BTCUSDT", cycle_id="z"),
            dict(time_ns=0, symbol="BTCUSDT", cycle_id="a"),
        ],
    )
    verifier().check_source_episode_groups(episodes, [run])
    with pytest.raises(ValueError, match="cycle|group"):
        verifier().check_source_episode_groups([dict(episodes[0], cycle_id="z")], [run])


def test_price_quality_clock_is_the_exact_union_of_portfolio_observations():
    observations = np.array([10, 20, 20, 30], dtype=np.int64)
    assert verifier().check_quality_clock(np.array([10, 20, 30]), observations, exact=True) == 3
    for corrupted in ([10, 30], [10, 20, 20, 30], [10, 20, 25, 30]):
        with pytest.raises(ValueError, match="quality.*clock|quality.*coverage"):
            verifier().check_quality_clock(np.array(corrupted), observations, exact=True)
    with pytest.raises(ValueError):
        verifier().check_quality_clock(np.array([10.0, 20.0, 30.0]), observations, exact=True)


def test_compact_price_quality_covers_each_exported_observation_without_claiming_union():
    quality = np.array([10, 20, 30, 40])
    assert verifier().check_quality_clock(quality, np.array([20, 20, 40]), exact=False) == 4
    with pytest.raises(ValueError):
        verifier().check_quality_clock(quality, np.array([15]), exact=False)


def quality_fixture():
    return dict(
        time_ns=np.array([10, 20, 30], dtype=np.int64),
        **{
            f"{symbol}_{source}_reason_code": np.array([0, 1, 2], dtype=np.uint8)
            for symbol in ("BTCUSDT", "ETHUSDT")
            for source in ("spot", "mark", "futures")
        },
    )


def test_price_quality_columns_are_strict_and_cover_declared_bounds():
    assert verifier().check_quality_values(quality_fixture(), 10, 31) == 3
    for field, value in (
        ("time_ns", np.array([10, 20, 30], dtype=float)),
        ("BTCUSDT_spot_reason_code", np.array([0, 1, 2], dtype=np.int64)),
    ):
        with pytest.raises(ValueError):
            verifier().check_quality_values(dict(quality_fixture(), **{field: value}), 10, 31)
    missing = quality_fixture()
    del missing["ETHUSDT_futures_reason_code"]
    with pytest.raises(ValueError):
        verifier().check_quality_values(missing, 10, 31)
    with pytest.raises(ValueError):
        verifier().check_quality_values(quality_fixture(), 10, 32)


@pytest.mark.parametrize(
    "field,code",
    [
        ("BTCUSDT_spot_reason_code", 6),
        ("ETHUSDT_mark_reason_code", 3),
        ("BTCUSDT_mark_reason_code", 5),
    ],
)
def test_rehashed_unknown_or_inapplicable_price_reason_is_rejected(tmp_path, field, code):
    import pyarrow as pa
    import pyarrow.parquet as pq

    values = quality_fixture()
    values[field][1] = code
    path = tmp_path / "calidad_precios.parquet"
    pq.write_table(pa.table(values), path)
    seal(tmp_path)
    verifier().verify_manifest(tmp_path)
    with pytest.raises(ValueError, match="quality.*code"):
        verifier().check_quality_values(verifier().read_arrays(path), 10, 31)


def quality_metadata_fixture(root):
    import pyarrow as pa
    import pyarrow.parquet as pq

    values = quality_fixture()
    tools = root / "herramientas/scripts"
    tools.mkdir(parents=True)
    for name in ("intraday_risk_price_quality.py", "intraday_risk_sources.py"):
        (tools / name).write_text("# literal fixture\n", encoding="utf-8")
    series = dict(
        entries=[
            dict(
                run_id="c",
                path="c/1970-01.parquet",
                sha256="a" * 64,
                rows=4,
                start_ns=10,
                end_exclusive_ns=31,
            )
        ]
    )
    prices = dict(
        manifest_path="external/processed.json",
        manifest_sha256="b" * 64,
        entries=[dict(source_id=0, sha256="c" * 64)],
    )
    for name, content in (("series_locales.json", series), ("fuentes_precios.json", prices)):
        (root / name).write_text(json.dumps(content), encoding="utf-8")
    (root / "evidencia").mkdir()
    parquet = root / "evidencia/calidad_precios.parquet"
    pq.write_table(pa.table(values), parquet)
    reasons = [
        "causal_current",
        "no_causal_valid_reference",
        "carried_expected_minute_absent",
        "carried_zero_volume_omitted",
        "carried_invalid_price_omitted",
        "carried_invalid_volume_omitted",
    ]
    references = [key.removesuffix("_reason_code") for key in values if key != "time_ns"]
    meta = dict(
        schema_version=1,
        row_count=3,
        columns={key: "int64" if key == "time_ns" else "uint8" for key in values},
        reason_dictionary={
            str(code): dict(name=name, description="Literal reason " + name)
            for code, name in enumerate(reasons)
        },
        join_contract=dict(
            key=["time_ns"],
            cardinality="many_series_observations_to_one_price_quality_row",
            series_manifest="series_locales.json",
            phase_independent=True,
            references=references,
            existing_observation_provenance="existing availability and source id fields",
            coverage_definition="Every physical row joins to exactly one annotation key.",
        ),
        coverage=[
            dict(
                run_id="c",
                path="c/1970-01.parquet",
                sha256="a" * 64,
                rows=4,
                unique_timestamps=3,
                matched_observations=4,
                missing_observations=0,
            )
        ],
        monthly_counts=[
            dict(
                month="1970-01",
                start_ns=10,
                end_exclusive_ns=31,
                row_count=3,
                first_time_ns=10,
                last_time_ns=30,
                reference_counts={
                    key: {str(i): int(i < 3) for i in range(6)} for key in references
                },
            )
        ],
        provenance=dict(
            series_manifest=dict(
                path="series_locales.json", sha256=verifier().sha256(root / "series_locales.json")
            ),
            price_sources=dict(
                path="fuentes_precios.json", sha256=verifier().sha256(root / "fuentes_precios.json")
            ),
            processed_manifest=dict(path=prices["manifest_path"], sha256=prices["manifest_sha256"]),
            script=dict(
                path="herramientas/scripts/intraday_risk_price_quality.py",
                sha256=verifier().sha256(tools / "intraday_risk_price_quality.py"),
            ),
            reader_script=dict(
                path="herramientas/scripts/intraday_risk_sources.py",
                sha256=verifier().sha256(tools / "intraday_risk_sources.py"),
            ),
            source_partitions=dict(
                count=1, all_manifest_hashes_match=True, sha256_by_source_id={"0": "c" * 64}
            ),
            series_partitions=dict(count=1, all_manifest_hashes_match=True),
            run_ids=["c"],
        ),
        parquet=dict(
            path="evidencia/calidad_precios.parquet",
            sha256=verifier().sha256(parquet),
            bytes=parquet.stat().st_size,
        ),
    )
    return values, meta, series, prices, dict(start_ns=10, end_exclusive_ns=31)


def test_price_quality_metadata_authenticates_tools_counts_and_join_contract(tmp_path):
    assert verifier().check_quality_metadata(tmp_path, *quality_metadata_fixture(tmp_path)) == 3


@pytest.mark.parametrize(
    "change", ["row_count", "dictionary", "join", "monthly_counts", "coverage", "script", "source"]
)
def test_rehashed_quality_metadata_cannot_forge_codes_counts_or_provenance(tmp_path, change):
    values, meta, series, prices, reconstruction = quality_metadata_fixture(tmp_path)
    if change == "row_count":
        meta["row_count"] = 2
    elif change == "dictionary":
        meta["reason_dictionary"]["2"]["name"] = "causal_current"
    elif change == "join":
        meta["join_contract"]["phase_independent"] = False
    elif change == "monthly_counts":
        meta["monthly_counts"][0]["reference_counts"]["BTCUSDT_spot"]["0"] = 3
    elif change == "coverage":
        meta["coverage"][0]["matched_observations"] = 3
    elif change == "script":
        meta["provenance"]["script"]["sha256"] = "d" * 64
    else:
        meta["provenance"]["source_partitions"]["sha256_by_source_id"]["0"] = "d" * 64
    (tmp_path / "evidencia/calidad_precios.json").write_text(json.dumps(meta), encoding="utf-8")
    seal(tmp_path)
    verifier().verify_manifest(tmp_path)
    with pytest.raises(ValueError, match="quality"):
        verifier().check_quality_metadata(tmp_path, values, meta, series, prices, reconstruction)


def test_complete_quality_links_exact_union_and_calls_explicit_causal_helper():
    calls = []
    prices = {
        (symbol, source): {"identity": (symbol, source)}
        for symbol in ("BTCUSDT", "ETHUSDT")
        for source in ("spot", "mark", "futures")
    }

    def literal_classifier(source, times, *, require_volume):
        calls.append((source["identity"], require_volume))
        np.testing.assert_array_equal(times, [10, 20, 30])
        return np.array([0, 1, 2], dtype=np.uint8)

    assert (
        verifier().check_quality_block(
            quality_fixture(),
            prices,
            np.array([10, 20, 20, 30]),
            10,
            31,
            classifier=literal_classifier,
        )
        == 3
    )
    assert set(calls) == {(key, key[1] != "mark") for key in prices}
    with pytest.raises(ValueError, match="quality.*coverage"):
        verifier().check_quality_block(
            quality_fixture(), prices, np.array([10, 30]), 10, 31, classifier=literal_classifier
        )


def test_rehashed_valid_reason_codes_with_unchanged_counts_fail_source_comparison(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    values = quality_fixture()
    values["BTCUSDT_spot_reason_code"] = np.array([2, 1, 0], dtype=np.uint8)
    path = tmp_path / "calidad_precios.parquet"
    pq.write_table(pa.table(values), path)
    seal(tmp_path)
    verifier().verify_manifest(tmp_path)
    verifier().check_quality_values(values, 10, 31)
    with pytest.raises(ValueError, match="quality"):
        verifier().check_quality_block(
            values,
            {("BTCUSDT", "spot"): {}},
            np.array([10, 20, 30]),
            10,
            31,
            classifier=lambda *args, **kwargs: np.array([0, 1, 2], dtype=np.uint8),
        )


def test_complete_quality_uses_real_helper_and_ignores_volume_only_for_marks():
    from scripts.intraday_risk_price_quality import quality_codes

    minute = 60_000_000_000
    values = dict(time_ns=np.array([0, minute, 2 * minute], dtype=np.int64))
    prices = {}
    for symbol in ("BTCUSDT", "ETHUSDT"):
        for source in ("spot", "mark", "futures"):
            prices[symbol, source] = dict(
                available_at=np.array([0, minute, 2 * minute]),
                close=np.array([100.0, 200.0, 300.0]),
                base_volume=np.array([1.0, 0.0, 2.0]),
            )
            values[f"{symbol}_{source}_reason_code"] = np.array(
                [0, 0, 0] if source == "mark" else [0, 3, 0], dtype=np.uint8
            )
    assert (
        verifier().check_quality_block(
            values,
            prices,
            np.array([0, minute, minute, 2 * minute]),
            0,
            2 * minute + 1,
            classifier=quality_codes,
        )
        == 3
    )
    values["BTCUSDT_spot_reason_code"][1] = 0
    with pytest.raises(ValueError, match="price quality"):
        verifier().check_quality_block(
            values,
            prices,
            np.array([0, minute, 2 * minute]),
            0,
            2 * minute + 1,
            classifier=quality_codes,
        )

"""B6 statistical contracts: literal fixtures catch weighting, gaps and RNG drift."""

from concurrent.futures import ProcessPoolExecutor
from importlib import import_module
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest


def module():
    path = Path(__file__).parents[2] / "scripts/stability_uncertainty_bootstrap.py"
    assert path.is_file(), "The B6 bootstrap implementation is missing"
    return import_module("scripts.stability_uncertainty_bootstrap")


def fixture_data():
    # MAE pooled by valid observations differs from the unweighted daily MAE.
    return {
        "date": np.array(["2022-01-01", "2022-01-02", "2024-01-01", "2024-01-02"]),
        "return_conditional": np.array([0.1, -0.1, 0.02, 0.0], dtype=np.float64),
        "return_permanent": np.array([0.1, -0.1, 0.01, 0.0], dtype=np.float64),
        "opportunity_bps": np.array([1.0, 3.0, 5.0, 7.0], dtype=np.float64),
        "h1_ewma_BTCUSDT": np.array([1.0, 27.0, 1.0, 3.0]),
        "h1_no_change_BTCUSDT": np.array([2.0, 9.0, 2.0, 2.0]),
        "h1_count_BTCUSDT": np.array([1, 9, 1, 1], dtype=np.int64),
        "h1_ewma_ETHUSDT": np.array([4.0, 8.0, 2.0, 4.0]),
        "h1_no_change_ETHUSDT": np.array([2.0, 4.0, 1.0, 3.0]),
        "h1_count_ETHUSDT": np.array([1, 2, 1, 1], dtype=np.int64),
    }


def fixture_periods():
    return {
        "full": np.array([0, 1, 2, 3]),
        "2022-2023": np.array([0, 1]),
        "2024+": np.array([2, 3]),
    }


def small_source_fixture():
    daily, h1, opportunity = [], [], []
    for i, date in enumerate(("2022-01-01", "2022-01-02")):
        day = int(np.datetime64(date, "ns").astype(np.int64))
        for strategy in ("conditional", "permanent"):
            daily.append(
                dict(
                    strategy=strategy,
                    run_id=f"fixture_{strategy}",
                    date=date,
                    time_ns=day + 86400000000000 - 1,
                    equity_usdt=str(10100 + 101 * i),
                    starting_equity_usdt=str(10000 + 100 * i),
                    partial_day=False,
                )
            )
        for symbol in ("BTCUSDT", "ETHUSDT"):
            h1.append(
                dict(
                    symbol=symbol,
                    time_ns=day + 60000000000,
                    horizon_end=day + 60000000000 + 168 * 3600000000000,
                    horizon_valid=i == 0,
                    absolute_error_ewma="0.0001" if i == 0 else None,
                    absolute_error_no_change="0.0002" if i == 0 else None,
                    reason="" if i == 0 else "horizon_outside_sample",
                )
            )
        opportunity.append(
            dict(
                date=date,
                time_ns=day + 86400000000000 - 1,
                opportunity="0.0001",
                eligible_fraction="0.25",
                complete=True,
                reason="",
            )
        )
    return daily, h1, opportunity


def draw_fixture(ids):
    b = module()
    strata = b.make_strata(
        np.array(
            ["2022-12-30", "2022-12-31", "2023-01-01", "2023-01-02", "2023-01-04", "2023-01-05"]
        )
    )
    return b.draw_indices(strata, 14, ids)[0]


def statistics_fixture(ids):
    b = module()
    data = fixture_data()
    indices, _ = b.draw_indices(b.make_strata(data["date"]), 14, ids)
    return b.batch_statistics(data, indices, fixture_periods())


def test_h1_counts_and_equal_asset_weights_are_preserved():
    b = module()
    result = b.batch_statistics(fixture_data(), np.array([[0, 1, 2, 3]]), fixture_periods())
    # BTC: (1+27 -2-9)/10 = 1.7; ETH: (4+8-2-4)/3=2; equal weight=1.85.
    assert result["h1_mae_delta_bps__2022-2023__BTCUSDT"][0] == pytest.approx(1.7)
    assert result["h1_mae_delta_bps__2022-2023__EQUAL_WEIGHT"][0] == pytest.approx(1.85)


def test_compounds_ddof_and_joint_pairing():
    b = module()
    result = b.batch_statistics(fixture_data(), np.array([[0, 1, 2, 3]]), fixture_periods())
    assert result["h2_conditional_cagr__2022-2023__PORTFOLIO"][0] == pytest.approx(
        0.99 ** (365 / 2) - 1, abs=2e-14
    )
    assert result["h2_sharpe_delta__2022-2023__PORTFOLIO"][0] == 0.0
    assert result["h3_opportunity_delta_bps__contrast__PORTFOLIO"][0] == 4.0
    assert result["h2_sharpe_delta__2024+__PORTFOLIO"][0] == pytest.approx(0, abs=1e-14)


def test_circular_blocks_never_cross_year_or_true_gap():
    b = module()
    dates = np.array(
        ["2022-12-30", "2022-12-31", "2023-01-01", "2023-01-02", "2023-01-04", "2023-01-05"]
    )
    strata = b.make_strata(dates)
    assert [(s["first"], s["stop"]) for s in strata] == [(0, 2), (2, 4), (4, 6)]
    indices, seeds = b.draw_indices(strata, 14, [0, 1, 7])
    assert indices.shape == (3, 6)
    assert len(seeds) == 9
    for lower, upper in [(0, 2), (2, 4), (4, 6)]:
        assert np.all((indices[:, lower:upper] >= lower) & (indices[:, lower:upper] < upper))
        assert np.all(indices[:, lower] != indices[:, lower + 1])


def test_unknown_day_is_retained_and_splits_both_adjacent_spans():
    b = module()
    strata = b.make_strata(
        np.array(["2022-01-01", "2022-01-02", "2022-01-03"]), np.array([True, False, True])
    )
    assert [(s["first"], s["stop"]) for s in strata] == [(0, 1), (1, 2), (2, 3)]
    assert np.array_equal(b.draw_indices(strata, 28, [0, 8])[0], [[0, 1, 2], [0, 1, 2]])
    data = fixture_data()
    data["return_conditional"][1] = np.nan
    result = b.batch_statistics(data, np.array([[0, 1, 2, 3]]), fixture_periods())
    assert np.isnan(result["h2_conditional_cagr__full__PORTFOLIO"][0])


def test_scalar_vectorized_and_serial_parallel_identity():
    b = module()
    data = fixture_data()
    strata = b.make_strata(data["date"])
    indices, _ = b.draw_indices(strata, 14, [0, 7, 13])
    vectorized = b.batch_statistics(data, indices, fixture_periods())
    for row, index in enumerate(indices):
        scalar = b.scalar_statistics(data, index, fixture_periods())
        for name in scalar:
            assert vectorized[name][row] == pytest.approx(scalar[name], abs=2e-11, nan_ok=True)
    serial = draw_fixture([0, 7, 13, 29])
    serial_statistics = statistics_fixture([0, 7, 13, 29])
    with ProcessPoolExecutor(max_workers=2) as executor:
        parallel = list(executor.map(draw_fixture, ([13, 29], [0, 7])))
        parallel_statistics = list(executor.map(statistics_fixture, ([13, 29], [0, 7])))
    assert np.array_equal(serial, np.concatenate([parallel[1], parallel[0]]))
    for name, values in serial_statistics.items():
        assert np.array_equal(
            values,
            np.concatenate([parallel_statistics[1][name], parallel_statistics[0][name]]),
            equal_nan=True,
        )


def test_degenerate_sharpe_stays_nd_without_replacements():
    b = module()
    data = fixture_data()
    data["return_conditional"][:] = 0
    result = b.batch_statistics(data, np.array([[0, 1, 2, 3]]), fixture_periods())
    assert result["h2_conditional_cagr__full__PORTFOLIO"][0] == 0
    assert np.isnan(result["h2_sharpe_delta__full__PORTFOLIO"][0])
    summary = b.summarize_distribution(np.array([1.0] * 94 + [np.nan] * 6))
    assert summary["n_replicates"] == 100
    assert summary["valid_replicates"] == 94
    assert summary["interval_low"] is None
    assert summary["interval_status"] == "ND_less_than_95_percent_evaluable"
    assert summary["finite_quantile_low"] == 1.0
    assert summary["finite_quantile_status"] == "conditional_on_evaluability"
    edge = b.summarize_distribution(np.array([1.0] * 95 + [np.nan] * 5))
    assert edge["interval_low"] == 1.0
    assert edge["interval_status"] == "conditional_on_evaluability"


def test_h1_no_valid_targets_and_missing_regime_are_nd():
    b = module()
    data = fixture_data()
    data["h1_count_BTCUSDT"][:] = 0
    data["h1_ewma_BTCUSDT"][:] = 0
    data["h1_no_change_BTCUSDT"][:] = 0
    periods = fixture_periods()
    periods["2022-2023"] = np.array([], dtype=np.int64)
    result = b.batch_statistics(data, np.array([[0, 1, 2, 3]]), periods)
    assert np.isnan(result["h1_mae_delta_bps__full__EQUAL_WEIGHT"][0])
    assert np.isnan(result["h3_opportunity_delta_bps__contrast__PORTFOLIO"][0])


def test_h1_end_horizon_exclusions_are_not_unknown_cash_days():
    b = module()
    daily, h1, opportunity = small_source_fixture()
    compact = b.compact_sources(daily, h1, opportunity)
    row = compact.to_pylist()[-1]
    assert row["h1_count_BTCUSDT"] == 0
    assert row["h1_horizon_excluded_BTCUSDT"] == 1
    assert row["joint_known"] is True
    assert row["return_conditional"] == pytest.approx(0.01)


@pytest.mark.parametrize("mutation", ["count_type", "count_value", "return_value", "protocol"])
def test_verifier_rejects_actual_input_or_type_tampering(tmp_path, mutation):
    b = module()
    # A small, fully verified fixture avoids a full 15,000-replica run per negative test.
    daily, h1, opportunity = small_source_fixture()
    b.write_compact_inputs(tmp_path, daily, h1, opportunity)
    b.verify_inputs(tmp_path)
    path = tmp_path / "estadistica/diario_base.parquet"
    if mutation == "protocol":
        protocol = tmp_path / "estadistica/protocolo.json"
        protocol.write_text(protocol.read_text("utf8").replace("20261001", "20261002"), "utf8")
    else:
        table = pq.read_table(path)
        name = "return_conditional" if mutation == "return_value" else "h1_count_BTCUSDT"
        values = table[name].to_pylist()
        if mutation == "count_type":
            array = pa.array([float(x) for x in values], type=pa.float64())
        else:
            values[0] += 1
            array = pa.array(values, type=table[name].type)
        table = table.set_column(table.column_names.index(name), name, array)
        pq.write_table(table, path)
    with pytest.raises(ValueError):
        b.verify_inputs(tmp_path)


def test_reject_duplicate_axis_and_unauthorized_block():
    b = module()
    with pytest.raises(ValueError):
        b.make_strata(np.array(["2022-01-01", "2022-01-01"]))
    with pytest.raises(ValueError):
        b.draw_indices(b.make_strata(np.array(["2022-01-01"])), 7, [0])


def test_replica_verifier_rejects_equal_numbers_with_changed_id_type(tmp_path):
    b = module()
    expected = [dict(replica_id=1, effect=1.25)]
    path = tmp_path / "replicas.parquet"
    pq.write_table(pa.Table.from_pylist(expected), path)
    b.verify_replica_table(path, expected)
    pq.write_table(pa.Table.from_pylist([dict(replica_id=1.0, effect=1.25)]), path)
    with pytest.raises(ValueError, match="types changed"):
        b.verify_replica_table(path, expected)


def test_csv_verifier_rejects_actual_edited_effect(tmp_path):
    b = module()
    expected = [dict(metric="h1_mae_delta_bps", point_estimate=-2.0)]
    path = tmp_path / "bootstrap_puntos.csv"
    b.write_rows(path, expected)
    b.verify_csv(path, expected)
    path.write_bytes(path.read_bytes().replace(b"-2.0", b"2.0"))
    with pytest.raises(ValueError, match="CSV differs"):
        b.verify_csv(path, expected)


def test_unknown_source_boolean_is_not_treated_as_verified_false():
    b = module()
    daily, h1, opportunity = small_source_fixture()
    daily[0]["partial_day"] = None
    with pytest.raises(ValueError, match="boolean"):
        b.compact_sources(daily, h1, opportunity)

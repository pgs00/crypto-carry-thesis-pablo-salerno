"""Verifier contracts: semantic tampering must fail even after rehashing."""

import os
from pathlib import Path

import pytest

from scripts.return_capital.verification import check_tables, new_destination

ROOT = Path(__file__).resolve().parents[2]


def test_constructor_rejects_existing_destination_and_protected_descendants(tmp_path):
    with pytest.raises(ValueError, match="exist"):
        new_destination(tmp_path, [])
    with pytest.raises(ValueError, match="protected"):
        new_destination(tmp_path / "new", [tmp_path])


@pytest.fixture(scope="module")
def historical_tables():
    from scripts.return_capital.tables import derive

    inputs = [
        Path(os.environ.get(key, ROOT / default))
        for key, default in (
            ("RETURN_CAPITAL_PARENT", "entregas/entrega_4/reglas_historicas/20260925T005436Z"),
            (
                "RETURN_CAPITAL_CORRECTION",
                "entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z",
            ),
            (
                "RETURN_CAPITAL_INTRADAY",
                "entregas/entrega_4/riesgo_intradia/20260926T214118Z/distribucion_20261010",
            ),
        )
    ]
    if not all(p.is_dir() for p in inputs):
        pytest.skip("Historical tests require explicit RETURN_CAPITAL source paths")
    return derive(*inputs)


def test_historical_relationships_reconcile(historical_tables):
    result = check_tables(historical_tables)
    assert result["portfolio_days"] == 3408
    assert result["cycles"] == 30
    assert result["evaluations"] == 21009


@pytest.mark.parametrize(
    "table,field,value",
    [
        ("atribuciones_segmentos", "net_pnl_usdt", "100"),
        ("atribuciones_segmentos", "start_ns", "0"),
        ("concentracion_ciclos", "G_usdt", "999999"),
        ("grupos_excluyentes", "denominator", "7"),
        ("decisiones_clasificadas", "market_cell", "both_pass"),
        ("resumen_integrado", "net_pnl_usdt", "999"),
        ("grupos_excluyentes", "start_ns", "0"),
        ("grupos_excluyentes", "fraction", "999"),
        ("motivos_simultaneos", "fraction", "999"),
        ("motivos_simultaneos", "order_position", "999"),
        ("conteo_ciclos_periodo", "cycles_participating", "999"),
        ("acciones_y_enlaces", "evaluation_id", "invented-evaluation"),
        ("emparejamiento", "paired_unique", "999"),
    ],
)
def test_semantic_tampering_fails(historical_tables, table, field, value):
    changed = dict(historical_tables)
    changed[table] = [dict(r) for r in historical_tables[table]]
    changed[table][0][field] = value
    with pytest.raises(ValueError):
        check_tables(changed)


def test_losing_cycle_cannot_disappear(historical_tables):
    changed = dict(historical_tables)
    changed["ciclos_vida"] = historical_tables["ciclos_vida"][1:]
    with pytest.raises(ValueError, match="cycle population"):
        check_tables(changed)


def test_manifest_detects_modified_bytes(tmp_path):
    from scripts.return_capital.common import sha256, write_json
    from scripts.return_capital.verification import check_manifest

    payload = tmp_path / "data.csv"
    payload.write_bytes(b"value\n10\n")
    manifest = tmp_path / "manifiesto_paquete.json"
    write_json(
        manifest,
        {
            "members": [
                {"path": "data.csv", "bytes": payload.stat().st_size, "sha256": sha256(payload)}
            ]
        },
    )
    (tmp_path / "manifiesto_paquete.sha256").write_text(sha256(manifest), encoding="ascii")
    check_manifest(tmp_path)
    payload.write_bytes(b"value\n11\n")
    with pytest.raises(ValueError, match="Member hash mismatch"):
        check_manifest(tmp_path)


def test_source_ordinal_is_preserved_in_classified_records(historical_tables):
    rows = historical_tables["decisiones_clasificadas"]
    assert rows[0]["source_row"] == 0
    assert rows[0]["decision_kind"] == "entry"

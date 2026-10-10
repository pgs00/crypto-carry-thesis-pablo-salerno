"""Changing a derived cell and refreshing its hash cannot forge its formula."""

from copy import deepcopy
from decimal import Decimal as D

import pytest

from scripts.stress_counterfactual_audit import audit_intervention, record_digest

M = 60_000_000_000


def fixture():
    original = dict(symbol="BTCUSDT", market="spot", open_time=0, end_time=M,
                    available_at=M, open="100", high="110", low="90", close="105",
                    base_volume="10", quote_volume="1020", trade_count=5, source_file="raw")
    modified = dict(original, open="90.0", high="99.0", low="81.0", close="94.5",
                    quote_volume="918.0", source_file="scenario:SH_FIXTURE|raw")
    row = dict(scenario="SH_FIXTURE", kind="shock", symbol="BTCUSDT", open_time=0,
               available_at=M, factor=D(".9"), original=original, modified=modified,
               source_record=original, original_record_sha256=record_digest(original),
               modified_record_sha256=record_digest(modified),
               source_record_sha256=record_digest(original))
    spec = dict(id="SH_FIXTURE", kind="shock", magnitudes={"BTCUSDT": D(".1")},
                episodes=[("BTCUSDT", 0, M)])
    sources = {("BTCUSDT", "spot", 0): dict(original, present=True)}
    return spec, sources, row


def test_exact_source_transformation_passes_independent_row_check():
    spec, sources, row = fixture()
    assert audit_intervention(spec, sources, row)["passed"]


@pytest.mark.parametrize("field,value", [("close", "95"), ("base_volume", "11"),
                                        ("available_at", M - 1), ("source_file", "official")])
def test_changed_cell_fails_even_with_new_record_checksum(field, value):
    spec, sources, row = fixture()
    original = deepcopy(row["modified"])
    row["modified"][field] = value
    row["modified_record_sha256"] = record_digest(row["modified"])
    assert row["modified"] != original
    with pytest.raises(ValueError, match="transformation"):
        audit_intervention(spec, sources, row)


def test_forged_original_source_cannot_be_hidden_by_refreshing_both_record_hashes():
    spec, sources, row = fixture()
    row["original"] = dict(row["original"], close="109")
    row["source_record"] = row["original"]
    row["original_record_sha256"] = record_digest(row["original"])
    row["source_record_sha256"] = record_digest(row["original"])
    with pytest.raises(ValueError, match="source"):
        audit_intervention(spec, sources, row)

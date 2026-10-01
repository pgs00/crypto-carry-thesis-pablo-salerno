"""Authenticate approval and translate its exact inputs, without selecting returns."""

import csv
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path

from crypto_carry.config import timestamp
from crypto_carry.data.stress_counterfactual import MINUTE, RECOVERY

SCENARIOS = ("SH_P90", "SH_MAX", "CF_SIN_INTERRUPCION")
CONTROLS = ("CONTROL_APAGADO", "CONTROL_CERO")
STRATEGIES = ("conditional", "permanent")
BASES = {"conditional": "run_ad71d751b20623006c195ff3",
         "permanent": "run_dfea4b7ac1475668d5968c97"}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def authenticate_approval(candidate):
    approval = read(candidate / "aprobacion_recibida.json")
    if approval["status"] != "aprobado":
        raise ValueError("Scenario is not approved")
    if digest(candidate / "identidad_propuesta.json") != approval["proposal_identity_sha256"]:
        raise ValueError("The approved proposal identity changed")
    identity = read(candidate / "identidad_propuesta.json")
    if approval["approved_files_sha256"] != identity["sha256"]:
        raise ValueError("The approved file list changed")
    for name, expected in approval["approved_files_sha256"].items():
        if digest(candidate / name) != expected:
            raise ValueError("An approved file changed: " + name)
    return approval


def authenticated_references(candidate, data):
    """Recheck declared identities; self-consistent replacement is not approval."""
    references = read(candidate / "indice_referencias.json")["references"]
    for ref in references:
        original = data / "outputs" / BASES[ref["strategy"]]
        corrected = Path(ref["original_control_path"])
        for directory, expected in ((original, ref["original_manifest_sha256"]),
                                    (corrected, ref["control_manifest_sha256"])):
            if digest(directory / "run_manifest.json") != expected:
                raise ValueError("Preserved reference identity changed: " + str(directory))
    return references


def load_spec(candidate, scenario):
    if scenario not in SCENARIOS + CONTROLS:
        raise ValueError("Unknown closed-matrix scenario")
    approval = authenticate_approval(candidate)
    required = "SH_P90" if scenario == "CONTROL_CERO" else scenario
    if required not in approval["families"] and scenario != "CONTROL_APAGADO":
        raise ValueError("Family is not approved: " + scenario)
    if scenario == "CONTROL_APAGADO":
        return dict(id=scenario, kind="off")
    proposal = read(candidate / "protocolo_propuesto.json")
    if scenario != "CF_SIN_INTERRUPCION":
        shock = proposal["shocks"]
        if shock["recovery_minutes"] * MINUTE != RECOVERY:
            raise ValueError("Recovery differs from approved implementation")
        magnitudes = {s: D(v) for s, v in shock["magnitudes_fraction"][required].items()}
        if scenario == "CONTROL_CERO":
            magnitudes = dict.fromkeys(magnitudes, D(0))
        episodes = []
        for row in rows(candidate / shock["schedule"]):
            start, end = int(row["base_start_ns"]), int(row["base_end_ns"])
            first = ((start + MINUTE - 1) // MINUTE) * MINUTE
            last = max(first + MINUTE, ((end + MINUTE - 1) // MINUTE) * MINUTE)
            if (first, last, last + RECOVERY) != tuple(int(row[n]) for n in (
                    "first_bar_open_ns", "plateau_end_open_ns", "recovery_end_open_ns")):
                raise ValueError("Approved calendar boundaries do not match its formula")
            episodes.append((row["symbol"], start, end))
        return dict(id=scenario, kind="shock", magnitudes=magnitudes, episodes=episodes)
    cf = proposal["counterfactual"]
    start, end = map(timestamp, cf["bar_opens"])
    anchors = {s: {m: D(p) for m, p in values.items()}
               for s, values in cf["anchor_prices"].items()}
    volumes = {}
    for row in rows(candidate / cf["volume_table"]):
        key = row["symbol"], timestamp(row["open_utc"])
        if key in volumes:
            raise ValueError("Duplicate approved volume minute")
        volumes[key] = D(row["median_base_volume"]), int(row["synthetic_trade_count"])
    wanted = {(s, t) for s in cf["symbols"] for t in range(start, end, MINUTE)}
    if set(volumes) != wanted or len(volumes) != 2 * cf["synthetic_bars_per_symbol"]:
        raise ValueError("Approved synthetic volume coverage is incomplete")
    if timestamp(cf["anchor_open"]) != start - MINUTE or timestamp(cf["anchor_available"]) != start:
        raise ValueError("Anchor must be the last full preclosure minute")
    return dict(id=scenario, kind="counterfactual", start=start, end=end,
                anchors=anchors, volumes=volumes)

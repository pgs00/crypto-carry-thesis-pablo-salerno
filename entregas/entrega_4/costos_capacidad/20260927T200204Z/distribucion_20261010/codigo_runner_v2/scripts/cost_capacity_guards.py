"""Technical recovery guards; no portfolio or selection semantics."""

from pathlib import Path

from crypto_carry.data.replay import input_hashes
from scripts.return_capital.common import read_json
from scripts.run_historical_rules_sensitivity import export_h3
from scripts.signal_sensitivity import validate_identity


def validate_resume(state, manifest, config, code, inputs, scenario, strategy):
    validate_identity(manifest, config, code, inputs)
    if state.get("scenario") != scenario or manifest.get("label") != "E4-costos-capacidad-"+scenario:
        raise ValueError("Resume scenario identity mismatch")
    if state.get("strategy") != strategy or manifest.get("strategies") != [dict(
            strategy=strategy, funding_filter_enabled=strategy == "conditional")]:
        raise ValueError("Resume strategy identity mismatch")


def verify_input_root(package, data_root, config):
    wanted_root = Path(read_json(package / "preservacion_previa.json")["data_root"]).resolve()
    if data_root.resolve() != wanted_root:
        raise ValueError("Execution data root differs from authenticated root")
    actual = input_hashes(data_root, config)
    if actual != read_json(package / "input_hashes.json"):
        raise ValueError("Execution input bytes or manifest semantics changed")
    return actual


def export_attempt_h3(package, attempt, run_id, scenario, strategy, opportunities):
    target = package / "intentos" / attempt
    target.mkdir(parents=True, exist_ok=False)
    export_h3(target, run_id, scenario, strategy, opportunities)
    return target / "h3_minutos" / f"{run_id}.csv"

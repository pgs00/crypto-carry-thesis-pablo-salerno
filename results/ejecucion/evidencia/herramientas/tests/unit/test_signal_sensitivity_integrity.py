import hashlib
import json
from copy import deepcopy

import pytest


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def test_manifest_binds_strategy_status_and_computed_identifier():
    from scripts.signal_sensitivity_integrity import validate_run_identity

    identity = dict(config={}, code_hash="abc", input_hashes={},
                    strategies=[dict(strategy="conditional", funding_filter_enabled=True)],
                    data_kind="historical_assumptions", label="E4-senal-H072")
    manifest = dict(identity, run_id="run_"+digest(identity)[:24], status="complete", artifacts_complete=True)
    item = dict(scenario="H072", strategy="conditional", status="ejecutado",
                run_id=manifest["run_id"], engine_status="complete")
    validate_run_identity(item, manifest)
    for key, value in [("strategy", "permanent"), ("engine_status", "insolvent"),
                       ("status", "reutilizado_verificado"), ("run_id", "run_wrong")]:
        with pytest.raises(ValueError):
            validate_run_identity(dict(item, **{key: value}), manifest)
    broken = deepcopy(manifest)
    broken["strategies"][0]["funding_filter_enabled"] = False
    with pytest.raises(ValueError):
        validate_run_identity(item, broken)


def test_protocol_enforces_predeclared_engine_runner_and_documents(tmp_path):
    from scripts.signal_sensitivity_integrity import economic_identity, validate_protocol

    code, docs = tmp_path/"code", tmp_path/"docs"
    (code/"src").mkdir(parents=True)
    docs.mkdir()
    engine, runner, document = code/"src/core.py", code/"runner.py", docs/"protocol.md"
    engine.write_bytes(b"engine original")
    runner.write_bytes(b"runner original")
    document.write_bytes(b"protocol original")
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    protocol = dict(engine_code_hash=economic_identity(code),
                    project_files={"runner.py": sha(runner)},
                    package_files={"protocol.md": sha(document)})
    validate_protocol(protocol, code, docs)
    for path in (engine, runner, document):
        original = path.read_bytes()
        path.write_bytes(original+b"changed")
        with pytest.raises(ValueError):
            validate_protocol(protocol, code, docs)
        path.write_bytes(original)


def test_destination_cannot_overlap_immutable_source(tmp_path):
    from scripts.signal_sensitivity_integrity import reject_overlaps

    protected = tmp_path/"original_run"
    for target in (protected, protected/"new_package", tmp_path):
        with pytest.raises(ValueError, match="overlap"):
            reject_overlaps(target, [protected])
    reject_overlaps(tmp_path/"new_package", [protected])

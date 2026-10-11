"""Stage gate: accounting, selection, fills/ledger and authenticated gross volume."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crypto_carry.config import Config  # noqa: E402
from crypto_carry.reporting import verify_run  # noqa: E402
from scripts.cost_capacity_incomplete import financial_for_run  # noqa: E402
from scripts.cost_capacity_ledger import audit_ledger  # noqa: E402
from scripts.execution_delays import BASES, STAGES, validate_variant  # noqa: E402
from scripts.execution_delays_audit import audit_execution  # noqa: E402
from scripts.execution_delays_report import validate_selection  # noqa: E402
from scripts.execution_delays_sources import extract_windows  # noqa: E402
from scripts.return_capital.common import parquet, read_csv, read_json, write_json  # noqa: E402


def audit_one(run, data, inputs):
    config = Config.load(run/"effective_config.toml")
    check = verify_run(run)
    if not check["valid"]:
        raise ValueError(check)
    daily, _, periods = financial_for_run(run, config)
    validate_selection(parquet(run/"signals.parquet"), config)
    orders = parquet(run/"orders.parquet")
    windows = extract_windows(data, config, orders, inputs)
    execution = audit_execution(config, orders, parquet(run/"fills.parquet"),
                                parquet(run/"ledger.parquet"), windows,
                                risk_events=parquet(run/'risk_events.parquet'))
    linked = audit_ledger(config, parquet(run/"ledger.parquet"), read_csv(run/"equity_daily.csv"),
                          parquet(run/"positions.parquet"))
    return dict(passed=True, run_id=run.name, raw_check=check, daily_closes=len(daily),
        periods=len(periods), max_daily_residual=str(max((abs(r["reconciliation_residual_usdt"]) for r in daily), default=0)),
        max_period_residual=str(max((abs(r["reconciliation_residual_usdt"]) for r in periods if r["reconciliation_residual_usdt"] is not None), default=0)),
        orders=len(execution["ordenes"]), fills=len(execution["fills_conciliados"]),
        capacity_keys=len(execution["capacidad"]), source_windows=len(windows), ledger_link=linked), windows, execution


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", required=True, type=Path)
    p.add_argument("--data-root", required=True, type=Path)
    p.add_argument("--stage", choices=tuple(STAGES), required=True)
    a = p.parse_args()
    base = Config.load(a.data_root/"outputs"/BASES["conditional"]/"effective_config.toml")
    results = []
    for scenario in STAGES[a.stage]:
        for strategy in BASES:
            state = read_json(a.work/"ejecuciones"/f"{scenario}__{strategy}.json")
            if state["status"] != "ejecutado":
                raise ValueError("Unfinished stage portfolio")
            run = Path(state["path"])
            validate_variant(base, scenario, Config.load(run/"effective_config.toml"))
            result, windows, execution = audit_one(run, a.data_root, read_json(a.work/"input_hashes.json"))
            write_json(a.work/"auditoria_corridas"/run.name/"ventanas.json", windows)
            write_json(a.work/"auditoria_corridas"/run.name/"ejecucion.json", execution)
            results.append(dict(result, scenario=scenario, strategy=strategy))
            print(scenario, strategy, result, flush=True)
    write_json(a.work/f"control_etapa_{a.stage}.json", dict(passed=True, runs=results))

# Trazabilidad de requisitos

Fuente contractual: `sources/Prompt_Codex_Backtesting.md`, secciones indicadas. Las pruebas son offline; fuentes públicas y muestra se verifican aparte. `complete` en una demo no certifica cobertura histórica.

| Requisito | Fuente | Implementación | Evidencia automatizada | Salida |
|---|---|---|---|---|
| Config base, fechas, Decimal, paths y 20 GB | §§2–4 + decisión usuario | config.py, download.py, normalize.py | test_config, test_data | effective_config.toml, manifests |
| Nautilus real, full fill, sin cierre terminal | §2 | nautilus_adapter.py | test_native_adapter; test_two_legs; test_integral_native | orders/fills, run_summary |
| Un solo código para dos carteras | §§2,7 | strategy.Backtest, flag | test_equal_filter_disabled; test_demo | tablas por strategy |
| Trades individuales, UTC ms/us, sin agregados | §4 | data/normalize.py | test_source_timestamp | Parquet trades |
| Descarga/reanudación/checksum/budget | §4 | data/download.py | test_download_rejects_budget; test_verified_raw_cache; paginación/conflictos | download.json |
| Duplicados, gaps, intervalos reales | §§4,5 | normalize.py, validate.py | test_identical_duplicates; missing_funding; matching_omissions; real_interval_change | processed.json, coverage.json |
| Reglas por vigencia/conocimiento | §4 | data/rules.py | test_rulebook; test_validation_checks_requested_days_and_interior_rule_gaps | history.json, quality report |
| EWMA temporal/antecedente/no-change | §5 | forecast.py | test_finance: constante, pesos, borde, gap | signals, forecast_evaluation |
| Costo ilustrativo 0,34%, multipliers | §§5,11 | costs.py | test_finance; test_transaction_cost_multiplier | signals, ledger, robustez |
| Equity y transferencias, fee spot neta | §§8,9 | ledger.py | test_finance; test_spot_purchase_can_use_free_futures_cash | ledger, pnl_components |
| Funding único sobre posición previa | §§6,8 | strategy.py, ledger.py | test_funding_before_fill; test_two_funding_sources; integral | funding_payments |
| Deadline estricto, secuencia, VWAP | §§6,7,11 | execution.py, strategy.py | test_execution; test_two_legs; second_leg_timeout | orders/fills/risk_events |
| Renovación positiva bajo costo, sin nuevos fills | §7 | _renew | test_renewal_uses_positive_forecast | risk_events/ledger |
| Sizing/desvío estricto 5%, reducción | §8 | portfolio.py, _renew | test_finance; test_sizing_can_reduce; test_rebalance_reduces | positions/fills |
| Falla primera/segunda pata y conservación de exposición | §§7,8 | strategy.py | second_leg_timeout; failed_first_rebalance_leg | risk_events/positions |
| Basis inclusivo/ampliación2pp y referencia | §7 | risk.py, strategy.py | test_finance; risk_precedes_renewal; hedge_trigger | signals/risk_events |
| Frescura vs inactividad vs datos desconocidos | §§4,7 | _fresh/_risk, validate.py | opening_trade_must_recheck; actual_inactivity; missing_data | quality/risk_events |
| Suspensión y reintento de salida | §7 | _finish_close, retry phase | suspension_retains_close; suspended_spot_inventory | risk_events/positions |
| Hedge >2%, <=0,5% a60s; sólo perpetuo | §7 | _correct/_risk | hedge_trigger_strict; correction_deadline | orders/risk_events |
| Tramos, open loss, parcial, liquidación | §8 | margin.py, ledger.py | test_finance; accounting_tolerance_does_not_widen; liquidation_debt | ledger/positions |
| Waterfall/deuda BTC→ETH/insolvencia | §§8,9 | ledger.py, _debt_close | debt_realizes_btc_first; liquidation_debt | ledger/debt/metrics |
| Sin look-ahead, particiones y checkpoints | §§4,6,12 | events.py, replay.py, checkpoint | future_mutation; chunk_boundaries; test_checkpoint | hashes/checkpoints |
| H1 misma muestra y horizontes válidos | §10 | evaluation.py | test_h1_target | forecast_evaluation,h1_summary |
| H2 métricas calendario/ddof1/undefined | §10 | evaluation.py, reporting.py | test_metrics_include_initial_capital | metrics/report |
| H3 1.440 minutos con ceros/igual peso | §10 | _opportunity, evaluation.py | test_h3_keeps_zero_minutes; test_demo | opportunity_daily/regime_comparison |
| Robustez predefinida, baseline intacto | §11 | robustness.py | test_robustness_is_predefined | config por corrida, robustness_summary |
| Participación previa/AUM | §11 | _submit, reporting/robustness.py | test_two_legs (ventana al envío), test_reporting | execution_summary, escenarios AUM |
| Manifiestos, estados, no overwrite, reportes desde tablas | §12 | reporting.py | test_reporting | outputs/run_id/* |
| CLI, instalación y demo | §15 | cli.py, __main__.py | test_cli, test_demo + comandos registrados | README, progress |

La lista de pruebas exacta y completa se obtiene con `uv run pytest --collect-only -q`. Los informes de tareas conservan evidencia intermedia; `progress.md` identifica la verificación final y las limitaciones vigentes.

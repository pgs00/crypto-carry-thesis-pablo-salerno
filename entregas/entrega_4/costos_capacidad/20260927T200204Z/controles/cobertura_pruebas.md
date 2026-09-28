# Cobertura de los trece controles del encargo

Los archivos de `pruebas/` conservan salidas reales, incluidos fallos y
correcciones. Una suite focalizada puede estar incluida en la general: no se
suman sus conteos. Los tests del sello final requieren `COST_CAPACITY_PACKAGE`;
su omisión en una ejecución sin ese argumento no se presenta como pase.

| Control | Evidencia reproducible |
| --- | --- |
| 1. Matriz exacta y modos previos | `test_closed_matrix_rejects_crosses_and_preserves_every_other_field`; configuraciones efectivas y protocolo previo |
| 2. Selección fija y acoplamiento antiguo | `test_legacy_coupling_is_preserved`, `test_fixed_selection_leaves_execution_costs_live`; controles previo/nuevo en doce comparaciones |
| 3. Entrada estricta, renovación y permanente | `test_diagnostic_strict_entry_boundary`, `test_new_cost_mode_preserves_renewal_contract`; integración por dos estrategias |
| 4. Slippage, multiplicador y tick | precios 100,02/99,98; 100,03/99,97; 100,05/99,95 y tick adverso en `test_cost_capacity.py` |
| 5. Spot bruto/neto, comisión base y caja | `test_spot_base_fee_numeric_contract_and_liquidation_charge_unscaled`; `test_ledger_audit_reconciles_base_fee_and_gross_cash` |
| 6. Liquidación específica no multiplicada | mismo test de contrato y pruebas históricas de ledger/estrategia; fee ordinaria separada |
| 7. Cupo restante, step y volumen cero | `test_shared_capacity_rounds_remaining_budget_and_zero_volume`; auditoría con dos órdenes .3+.2 sobre cupo .5 |
| 8. Claves, parciales, reintentos y ventana | `test_cost_capacity_audit.py`; integración nativa de las 16 combinaciones; vínculos orden/fill/ledger; no imputación de volumen ausente |
| 9. Trayectoria de A050/A100 | `test_scenario_fees_capacity_and_portfolio_reconcile`, fixtures de joint sizing y filtros; series históricas nuevas y tramos persistidos |
| 10. H1/H3 estables, H2/H3 financieros nuevos | igualdad de proyecciones/targets/agregados en `invariancias.csv`; contratos H2/H3 recalculados sobre cada período |
| 11. Funding, parciales, garantías, años y polvo | suites existentes `test_finance*`, `test_next_minute_vwap`, `test_strategy`, `test_return_capital_accounting`, `test_rules_sensitivity_exposure`; fixtures de insolvencia/cobertura incompleta |
| 12. Conciliación original | puertas por etapa y verificador: 1E-8 USDT para dinero; cantidades y tarifas exactas; no tolerancia ampliada |
| 13. Corrupción, sólo lectura y portabilidad | tests de integración del sello con once alteraciones y hashes renovados; ejecución desde exportación Git en otra ruta |

No se crean fills de liquidación históricos para aumentar cobertura: los
fixtures prueban ese contrato y las tablas informan lo efectivamente ocurrido.
Los casos extremos se eligen por el protocolo previo, sin optimizar selección.

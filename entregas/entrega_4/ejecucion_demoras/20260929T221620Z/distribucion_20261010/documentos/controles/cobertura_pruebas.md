# Cobertura de pruebas del bloque 4

Las rutas se expresan respecto de la raíz del paquete final. Las pruebas de
código se incluyen bajo `herramientas/tests/`. Los fixtures sintéticos son
controles técnicos; no constituyen observaciones históricas.

| Requisito de la sección 7 | Evidencia de código y ejecución |
|---|---|
| 1. Matriz cerrada y diferencias autorizadas | `test_matrix_is_closed_and_derived_without_other_economic_changes`; seis configuraciones congeladas; validación del runner y verificador |
| 2. Defaults, identidad y modos de costo anteriores | `test_defaults_preserve_base_canonical_and_digest`; controles deterministas old/current; regresión general; dos controles BASE completos con once artefactos en orden persistido |
| 3. OHLC4=101 frente a VWAP=102; close/sizing independientes | `test_ohlc4_has_its_own_reference_without_mutating_close_or_volumes`; `test_ohlc4_fill_is_distinct_from_unchanged_closed_signal_and_future_sizing` |
| 4. Velas inválidas, actividad, disponibilidad y ausencia | Unitarios de precio; `test_invalid_ohlc_in_delayed_vwap_halts_before_any_inventory_mutation`; fixtures previos y controles de ventana/fuente del auditor |
| 5. Nanosegundos y ventana única | `test_eligibility_and_single_window_nanosecond_boundaries`; metadatos por orden y comparación independiente con minuto elegible |
| 6. Propósitos, segunda pata y reintentos | `test_purpose_classification_excludes_liquidations`; `test_each_opening_leg_receives_delay_and_preserves_submitted_time`; `test_close_only_delays_both_close_legs_but_not_opening`; reintento parcial escalado a liquidación |
| 7. Cancelaciones, reservas y plazo preventivo | `test_cancellation_boundaries_follow_base_policy_during_delay`; `test_delayed_correction_cannot_extend_preventive_deadline`; validación del ciclo de vida y snapshots pendientes |
| 8. Funding/riesgo simultáneo y liquidación | `test_funding_keeps_charging_waiting_short_including_fill_boundary`; `test_liquidation_displaces_waiting_preventive_close_without_client_delay`; casos de corrección/reducción parcial o sin fill después de liquidación |
| 9. Parciales, cupo bruto compartido y secuencia | Fixtures de ejecución existentes en regresión; auditor de cada fill por instrumento/mercado/minuto; `test_renumbering_fills_cannot_change_original_ledger_order` |
| 10. Final exclusivo, estados heredados, polvo y checkpoint | `test_checkpoint_pending_delay_and_exclusive_end_preserve_inventory`; clasificadores/conciliaciones previos en regresión; pruebas locales de polvo y final−1 ns |
| 11. H1/H3 frente a economía de cartera | `test_execution_options_preserve_market_opportunity_and_forecast_inputs`; `test_per_asset_opportunity_cannot_change_under_complete_execution_variant`; proyecciones/targets y agregados diarios por activo; H2/H3 recalculados por escenario |
| 12. Adulteraciones con hashes renovados | `test_semantic_corruption_with_renewed_hashes`, sobre copias descartables del paquete final: precio, demora, propósito causal, ventana, cantidad, volumen, fees, secuencia, cancelación, vencimiento, metadata, finanzas, H2/H3, ledger, incidentes, Parquet, controles BASE y catálogo |

Además se prueban fronteras locales por índice de ledger, funding anterior al
fill final, movimientos de otro activo posteriores a la apertura, ausencia de
valoración inicial (ND), margen sólo con corto, calendario y exportación de
columnas mixtas mark/spot. El catálogo del 24/03 conserva polvo con riesgo de
precio sin computarlo como tiempo activo.

La revisión independiente y sus reproducciones están en
`controles/revision_independiente.md`. Se conservan logs RED y GREEN; no se
borra un fallo inicial ni se cuenta una omisión como aprobación. Las suites
solapadas no se suman. Los controles finales sobre el sello y la exportación
binaria se registran en destinos externos con identidad del paquete.

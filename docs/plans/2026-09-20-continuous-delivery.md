# Continuous delivery evidence plan

The user's request is the approved specification: export a compact ZIP for
Entrega 3 using the two saved `futures_scaled` portfolios over
`[2022-01-01, 2026-09-01)` UTC, including full-period and regime cuts at
`2024-01-01`. No strategy replay, parameter changes, commits or pushes.

1. Add independently tested postprocessing in `scripts/continuous_delivery/`.
   Derive daily and regime P&L from persisted cumulative components, preserving
   incoming equity at each cut. Build cycle/activity and interval exposure
   evidence, separating dust, covered carry, unhedged inventory and cash.
   Export daily capital deployed as spot market value plus isolated collateral.
2. Recompute H1 from local funding and saved causal forecasts, checking forecasts
   against the duration-aware implementation and labels against saved H1. Use
   signal-time cohorts, one global horizon boundary, identical paired samples,
   explicit exclusions and equal BTC/ETH weighting.
3. Calculate H3 once from market data, never portfolio state. At each UTC minute,
   use only closed aligned bars, the last available forecast, current prescribed
   fees/rules and the verified mark layer. Known missing minutes during the
   documented spot closure mean non-operational zero; unknown required data makes
   the asset/day incomplete. Average all 1,440 minutes then both assets equally.
   Publish daily asset totals, forecast-group sufficient statistics and a fixed
   audit sample instead of millions of market rows.
4. Export signal filter states, first-rejection counts and ignored funding
   diagnostics for the permanent comparator. Reconstruct March 24 from actual
   orders, fills, positions and ledger, including daily P&L and exact exposure
   intervals. Do not present removal of an episode as another backtest.
5. Package CSVs, brief Spanish README, definitions/units, source hashes,
   reproducible scripts and the existing mark-sensitivity evidence. Preserve
   source files and original manifests byte-for-byte. Add a standalone verifier,
   verify the extracted ZIP, and run pytest/Ruff. Keep Binance bulk data local.

Review focus: millisecond funding availability at minute boundaries; future
funding used only as H1 labels; invalid minutes distinguished from valid zeros;
regime boundaries carry existing equity/positions; simultaneous rejections do
not count funding as an applied filter for permanent carry.

Validation fixtures: H3 BTC eligible for 720 minutes at 0.004 and ETH zero gives
0.001; one unknown required minute excludes the joint day; a forecast available
one millisecond after a boundary cannot affect that boundary; different H1
sample counts still receive equal asset weights; an interval crossing 2024 is
clipped across regimes without creating a new opening; spot dust does not count
as active uncovered carry; P&L components reconcile daily and across regimes.

## Execution record

Completed with postprocessing only; no changes to `src/`, configurations or
saved runs. The package is
`entregas/entrega_3/paquete_actualizacion_entrega_3_continua.zip` (9,640,333 bytes),
SHA-256 `48485e691f7ae4b479d25766ee46aeac199cf4ea022a36d01cde177e87770916`.

- The source verifier checked 1,735 local files and all four continuous runs.
- Recomputed all 10,224 forecasts and checked saved labels/exclusions. H1 has
  10,180 valid paired observations and 44 exclusions. H3 covers all 1,704 days;
  the maximum difference from the saved series is below 8e-17.
- The independent review checked 23,316 sampled H3 minutes, eight exported
  source-evidence tables, source bytes/hashes, activity and the outage episode.
  It found two issues, fixed with regression tests: close requests without a
  cycle ID now attach by asset and active interval; the March 2023 P&L share
  stays empty for a regime that does not contain that day. No important or
  critical review findings remain.
- Extracted the final ZIP into a fresh directory on C: and ran its standalone
  verifier in isolated Python mode. It verified 120 hashed files, 23 local
  links, 3,408 daily financial rows, 10,224 H1 observations, 3,408 H3 asset-days
  and 1,704 joint H3 days, without reading the massive market datasets.
- Full pytest: 466 passed, including 11 new postprocessing regression tests.
  Ruff and formatting checks passed for the new modules and tests.

The README distinguishes full and regime returns, daily drawdown, funding-rate
units, capital utilization, overlapping H1 targets and descriptive H3 evidence.
The sensitivity evidence and source manifests/configurations retain their
original bytes. No commit or push was made.

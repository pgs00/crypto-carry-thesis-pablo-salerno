# Funding settlement price analysis plan

The user supplied the analysis specification and authorized implementation in
the existing workspace. This is postprocessing of the two continuous
`futures_scaled` portfolios, not a new replay or a change to economic rules.

1. Verify saved run/input hashes and all 10,224 in-period funding observations
   against the local normalized funding and raw API JSON. Require 6,214 exact
   prices and 4,010 previous-minute proxies. Retain nanosecond timestamps.
2. Extract only the preceding closed mark candle for every event. Call the
   existing `resolve_funding_mark` on an immutable copy with its exact price
   removed, using the original configuration with zero stress. Verify every
   existing proxy against the resulting price and provenance. Preserve the
   `futures_scaled` layer and report any overlap with its 15 estimated candles.
3. Measure signed relative error as 10,000 * (proxy / official - 1). Report
   signed mean, absolute mean, linearly interpolated absolute P95 and absolute
   maximum by asset/year and pooled asset. Years without official prices have
   missing statistics, never zero errors.
4. Reconstruct pre-settlement short quantities from ledger snapshots strictly
   earlier than each funding timestamp, independently cross-check with futures
   fills and saved funding payments. Same-time fills follow settlement.
   Compare actual funding q * rate * official with q * rate * proxy only on
   officially priced observations; distinguish all prices from open positions.
5. For missing prices only, perturb proxy by (1 +/- sign(rate) * asset_P95/10000).
   Keep original positions fixed. Favorable cashflow deltas must be nonnegative;
   adverse deltas nonpositive. Exact observations remain unchanged. Convert
   accumulated USDT differences to return using original 10,000 USDT capital.
6. Write a brief Spanish report, compact observation/event CSVs and grouped
   tables, source/output hashes and reproduction instructions. Do not overwrite
   prior evidence. Add focused tests for timing, error units/denominator/P95,
   zero exposure, same-time fills, both funding signs and official-only masking.
   Run the analysis, independent review, full pytest and Ruff.

Files: `scripts/funding_price_analysis.py` for pure calculations;
`scripts/analyze_funding_prices.py` for local input validation, output and CLI;
`tests/unit/test_funding_price_analysis.py`; generated compact evidence under
`data/research/funding-price-sensitivity-20260920/`.

Limitations to report: unknown actual errors on the missing interval; later
observations need not represent earlier volatility, liquidity or exchange
microstructure; symmetric relative-price perturbations are illustrative, not
coverage bounds; fixed positions exclude altered decisions, sizing, margin,
liquidation and compounding. This is distinct from the 15 mark-candle gaps.

## Execution record

- Implemented pure calculations and a separate read-only local analysis CLI.
  The initial new-test run failed because the module did not yet exist; all
  14 focused tests passed after implementation. Full pytest: 480 passed.
- Verified 1,735 source files and the original four runs. All 10,224 raw,
  normalized and consumed observations agree; all 4,010 proxies reproduce
  the saved values and provenance. None of their preceding candles overlaps
  the 15 separately estimated mark candles.
- Reconstructed every pre-settlement quantity independently from ledger and
  futures fills: 2,234 conditional payments and 9,827 permanent payments
  reconcile exactly. Signed funding-rate cases remain in the sample.
- Pooled absolute P95: BTC 0.938774559 bps; ETH 1.135601894 bps.
  Observed known-price funding differences: +0.0002286548695892450 USDT
  conditional and +0.0005146549307988964 USDT permanent. Missing-only scenarios
  change funding by +/-0.005969644474237589 and +/-0.07433930275850364 USDT.
- Independent read-only review recomputed all grouped errors with NumPy,
  matched all payment rows and independently summed the missing-only scenarios.
  No Important or Critical findings. The two maximum-error minute closes were
  also directly checked against their original Binance ZIP members.
- Reviewer exclusions stand: external historical truth and the validity of
  the unchanged engine are outside this fixed-position local-data analysis;
  extrapolation and decision/margin limitations are explicit in the report.
  Parent verified full pytest/Ruff and original-source integrity.

The final compact evidence directory contains five CSVs, README, source hashes
and a checksummed output manifest. It preserves earlier outputs. The new evidence
and analysis scripts have byte-preserving Git attributes. No commit or push.

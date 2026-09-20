# Continuous mark-gap sensitivity

Implement the user's approved specification without changing economic parameters.

1. Pin the 15 documented asset/minute pairs; test fixed official anchors, closed-bar
   availability, scaled OHLC, constant sensitivity, missing inputs and extra gaps.
2. Add a strict-by-default configuration option. Build immutable derived manifests
   and replacement mark partitions, referencing unchanged original price/funding
   partitions. Recompute and verify derivations before validation/replay.
3. Record risk checks at anchors, estimated minutes and first official recovery,
   including positions, isolated margin, thresholds and actual decisions.
4. Test the integration and run pytest/Ruff. Execute one uninterrupted portfolio
   per strategy and method over [2022-01-01, 2026-09-01) UTC, with progress output.
5. Verify immutable run artifacts and accounting; publish a compact comparison,
   detailed gap evidence and reproduction instructions. Keep bulk data on D:,
   previous evidence intact, and make no commit or push.

Primary method: future OHLC multiplied by last official mark close / simultaneous
future close. Hold the official anchor throughout consecutive missing minutes.
Sensitivity: all estimated OHLC equal the last official mark close. Both methods
publish at the missing candle's next minute and keep the existing funding proxy.
Neither method is selected using realized performance.

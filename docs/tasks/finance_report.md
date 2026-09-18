# Financial domain implementation report

## Scope

Implemented the bounded financial layer specified in `docs/tasks/finance.md`:

- `src/crypto_carry/forecast.py`
- `src/crypto_carry/costs.py`
- `src/crypto_carry/margin.py`
- `src/crypto_carry/ledger.py`
- `src/crypto_carry/portfolio.py`
- `tests/unit/test_finance.py`

No changes were made to `config.py`, `models.py`, strategy, data, Nautilus, or engine code.

## Implementation details

### Forecast

- Added the exact public `Forecast` dataclass and `forecast`/`weight` functions.
- Uses Decimal half-life weights and normalizes rates by verified actual interval duration.
- Requires an anchor observation, an antecedent that covers the lower window boundary,
  positive verified intervals, exact timestamp/declared-interval continuity, and availability
  no later than the decision time.
- Excludes a settlement exactly at the 336-hour lower boundary from the weighted sum while
  retaining it as the first interval's antecedent.
- Returns an invalid result with a visible reason instead of filling or silently accepting
  incomplete history.

### Costs and portfolio sizing

- Added floor-to-step quantity handling and adverse tick rounding: ceiling for buys and floor
  for sells, with the rounding amount returned separately.
- Added inclusive quantity/notional validation and exact cycle-cost calculation.
- Added dust-aware total target sizing, strict rebalance threshold, hedge error including the
  zero-spot cases, and a conservative required-cash forecast.
- Required cash includes rounded adverse spot execution, the net spot units left after the
  base-asset fee, the corresponding stepped short, raw adverse futures execution without
  speculative future tick rounding, futures fee, isolated collateral, and open loss.

### Margin

- Maintenance uses the tier containing current mark notional, with inclusive boundaries.
- Liquidation price is solved against every tier and accepted only when its own liquidation
  notional belongs to that tier. Missing applicable tier evidence raises `ValueError`.
- Margin state reports the requested seven keys and avoids division by zero. Maintenance
  equality liquidates using the configured Decimal tolerance. The 15% preventive-distance
  boundary remains strict, as specified in prompt section 7.

### Ledger

- Added exact-Decimal position and account state, equity valuation, fills, funding,
  spot-to-futures transfers, event persistence, deduplication, and reconciliation.
- Spot buy fees are deducted once in base units. Net units receive a fill-price cost basis;
  the fee is attributed separately, which makes current-value reconciliation exact without
  double charging cash.
- Futures increases reserve ordinary fee, isolated collateral, and open loss atomically.
  Unaffordable voluntary increases leave state unchanged and never create negative cash.
- Futures reductions release collateral proportionally, preserve the remaining average, and
  recognize realized P&L and configured fees. Liquidation charges use the configured execution
  or mark basis, include the ordinary fee only when the rule requires it, and are idempotent.
- Negative funding consumes free futures cash, same-contract collateral, free spot cash, then
  debt. Other realized obligations use futures cash, spot cash, then released collateral.
  Incoming cash and leftover released collateral repay existing debt first.
- Identical fill/funding/transfer retries return `False`; a conflicting event with the same
  derived ID raises `ValueError`. Because `Funding` has no explicit ID field, its stable event
  ID is `symbol + funding_time`.
- Every applied fill, funding, and transfer asserts its exact scalar equity movement at the
  event reference/mark within `Config.accounting_tolerance`. Reconciliation independently
  verifies reported equity/P&L against realized and unrealized attribution; it never inserts a
  balancing plug.

## Test-first evidence

The first finance test run occurred before the production modules existed:

```text
.venv/Scripts/python.exe -m pytest tests/unit/test_finance.py -q
ERROR tests/unit/test_finance.py
ModuleNotFoundError: No module named 'crypto_carry.costs'
```

Subsequent focused red/green checks caught and fixed two boundary/accounting cases:

- A liquidation price at an exact algebraic boundary differed by one Decimal context unit;
  the conservative equality check now uses the configured accounting tolerance.
- A preventive liquidation distance exactly equal to 15% initially returned `True`; the
  regression test failed, and the comparison is now the required strict `< 0.15`.
- Leftover collateral from a close initially became free futures cash while old debt remained;
  the regression test failed, and released cash now repays debt before becoming free.
- Transfer rows initially reported zero in `amount_usdt`; the regression test failed, and the
  persisted row now reports the transferred amount while the accounting movement remains zero.

The final focused suite covers variable-duration constant-hourly forecasts, half-life weights,
the exact lower boundary, gaps/unverified/unavailable history, adverse execution rounding,
cycle cost, inclusive quantity boundaries, tier crossing, equality liquidation, spot base fees,
absolute-spread price P&L (0 and -1), positive and negative funding, waterfall debt, insolvency,
transfer neutrality, partial collateral release, debt repayment, fill/funding deduplication,
atomic unaffordable fills, liquidation fee idempotence, sizing, rebalancing, hedging, and required
cash.

```text
.venv/Scripts/python.exe -m pytest tests/unit/test_finance.py tests/unit/test_config.py -q
22 passed in 0.04s
```

After adding the strict-distance, insolvency, released-collateral debt, and transfer-row
regressions, the final finance-only result was:

```text
.venv/Scripts/python.exe -m pytest tests/unit/test_finance.py -q
20 passed in 0.09s
```

Lint verification:

```text
.venv/Scripts/python.exe -m ruff check src/crypto_carry/forecast.py \
  src/crypto_carry/costs.py src/crypto_carry/ledger.py \
  src/crypto_carry/margin.py src/crypto_carry/portfolio.py \
  tests/unit/test_finance.py
All checks passed!
```

The repository-wide pytest command was also attempted. At that point it stopped during
collection because the independently owned `crypto_carry.strategy` module had not yet been
created. The error was unrelated to these finance modules:

```text
tests/integration/test_strategy.py:6: ModuleNotFoundError: No module named 'crypto_carry.strategy'
```

## Integration notes

- Public interfaces match `docs/tasks/finance.md`; no adjustment is requested from the root
  integrator.
- Callers should pass symbol-specific funding history to `forecast`.
- `Fill.fee_rate` is treated as the effective historical ordinary fee; the supplied
  `MarketRule` controls liquidation fee basis/rate and whether a liquidation also pays the
  ordinary fee.
- A total spot target can contain pre-existing dust smaller than the current step. The new
  incremental order is what is floored to the current step, so dust remains valued and is not
  repurchased or erased.

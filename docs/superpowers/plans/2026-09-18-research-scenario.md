# Approved research scenario implementation

**Goal:** Run the existing individual-trade backtest with observed prices, causal funding proxies only where exact settlement marks are absent, and explicitly prescribed exchange rules. Keep strict historical validation available and unchanged in meaning.

**Spec:** `docs/sources/Prompt_Codex_Backtesting.md`, amended by the user's approval on 2026-09-18 of the methodology in `docs/research/methodology_two_days_20260918.md`.

**Architecture:** An opt-in `Config.analysis_mode = "prescribed_research"` selects a versioned prescribed rulebook. A single causal funding helper is shared by preflight validation and the economic engine. Reports preserve both the observed input and each substituted settlement mark; source Parquet files remain immutable. Existing CLI and robustness commands select this mode through configuration.

**Tech:** Python, Decimal, PyArrow, NautilusTrader, pytest, existing immutable report manifests.

## Global constraints

- Keep the economic window 2022-01-01 through before 2026-09-01, individual trades, one-second leg delay, both strategies, shared accounting logic and all risk controls.
- Strict historical mode remains the default. Prescribed rules must never be accepted by its rulebook.
- Keep exact funding marks. Missing economic settlement marks require the immediately preceding closed one-minute mark, available by the actual funding timestamp. No future candle, interpolation, stale fallback, or missing-rate substitution.
- Missing funding marks before the economic start do not affect cash; their observed funding rates and independently verified intervals remain required.
- Funding proxy stress is signed in basis points: positive worsens the cash flow of a short (`proxy * (1 - sign(rate) * bps / 10000)`), negative improves it. Stress only substituted marks, identically for both strategies.
- Do not relax trade completeness, hashes, independent funding calendars, closed-mark coverage or accounting checks.
- Record prescribed rules as assumptions declared in 2026, never as knowledge available historically. Preserve explicit provenance and reproducible hashes.
- Do not touch the active D: downloader, commit, push, contact support, or introduce a different execution-data granularity.

## Task 1: Configuration and prescribed rulebook

Files: `config.py`, `data/rules.py`, new `data/prescribed.py`, `configs/research.toml`, tests.

Add `analysis_mode` (`strict_historical` default, `prescribed_research` opt-in), Decimal `funding_proxy_stress_bps=0`, `research_futures_taker_fee=0.0005`, `research_maintenance_multiplier=1`, `research_liquidation_fee=0.0125`. Validate finite values, mode, stress magnitude less than 10000, nonnegative fees below one, positive maintenance multiplier, and reject nondefault research knobs in strict mode. Research configuration uses `fee_profile="prescribed_fixed_no_discounts"`.

Add `prescribed_rules(config)` and `research_assumptions(config)` in `data/prescribed.py`. The latter returns a JSON-serializable versioned declaration with all rule records and methodology. RuleBook gains explicit `allow_prescribed=False`; status `prescribed` is selected only with this opt-in and uses model applicability rather than historical known-from. Real declaration time is 2026-09-18; no fake historical publication date. Include `allow_prescribed` in checkpoint rule hashing (root integration task).

Prescribed fixed fees: spot 0.001; futures configurable default 0.0005; no discounts/promotions. Spot BTC step/minqty 0.00001, ETH 0.0001; ticks 0.01; maxqty BTC 128.52621715, ETH 3277.54882761; minnotional 10, maxnotional 9000000. Futures step/minqty 0.001; BTC tick 0.1, maxqty 120, minnotional 100; ETH tick 0.01, maxqty 2000, minnotional 20; maxnotional 100000000. First maintenance tier 0..50000 rate BTC 0.004, ETH 0.0065; second 50000..100000000 rate 0.01; continuous deductions 300 and 175 respectively. Multiply rates AND deductions by maintenance multiplier. Liquidation charged on execution notional plus regular taker, prescribed explicitly. Operational availability assumed true; observed market-data coverage still required. Provenance anchors: local public-rules research; values are model constraints, not a certified exchange reconstruction.

First write failing tests proving strict rejection, explicit opt-in, complete fixed table, continuous tier stress and invalid config rejection; then implement and run targeted tests.

## Task 2: Causal funding helper and engine integration

Files: new `data/funding_proxy.py`, `models.py`, `strategy.py`, focused tests.

Public helper: `resolve_funding_mark(record: Funding, mark: Mark | None, config: Config) -> Funding`. Strict mode returns unchanged. Research mode preserves every valid exact mark. Missing warmup marks remain absent (no cash flow before start). Missing economic marks require candidate symbol match, one-minute candle open exactly `floor(funding_time/minute)*minute-minute`, valid positive close, close before funding time, available_at <= funding_time, no malformed timing. Raise ValueError with actionable event identity when absent/invalid; never silently skip.

Extend Funding with defaulted provenance fields `settlement_mark_method="exact"`, `settlement_mark_source_file=""`, `settlement_mark_close_time=None`, `settlement_mark_available_at=None`, `settlement_mark_proxy_base=None`, `settlement_mark_stress_bps=Decimal(0)`. Keep source_file as original funding source. Missing warmup method `not_required_before_start`; proxy method `previous_closed_1m`.

Use the helper in Backtest before duplicate economics/settlement processing, selecting the latest causal mark including marks in the same timestamp group (Funding sorts before Mark). Record resulting Funding in all_funding; do not mutate raw data. Include explicit allow_prescribed in checkpoint rules identity.

First tests: exact unchanged, same-timestamp antecedent accepted, future/current/stale/wrong-symbol rejected, signed stress for positive and negative funding, warmup no cash, actual engine ledger charged once and correct proxy at simultaneous candle boundary. Run targeted tests.

## Task 3: Validation and CLI integration

Files: `data/validate.py`, `cli.py`, tests.

Select prescribed_rules when opted in. Funding validation uses resolve_funding_mark for economic events and reads only needed one-minute candidate rows from hash/schema-verified mark partitions. Scope sample must use sample economic start, not full config start. Keep all other data-integrity gates. Quality has distinct analysis mode/data kind, assumptions and per-event proxy evidence. Full strict baseline certification remains false for research mode.

Backtest CLI uses the selected rulebook and `data_kind="historical_assumptions"`; normal strict/demo behavior preserved. No external rule-file copy needed on D because versioned prescribed rules live in the code and are snapshotted in each run.

Tests: strict still rejects absent marks/rules; research only resolves covered causal marks, cannot waive missing trades/marks/hashes/calendar; sample warmup correct; CLI chooses distinct report type.

## Task 4: Reporting and sensitivities

Files: `reporting.py`, `robustness.py`, tests.

Accept `historical_assumptions`, clearly label reports and figures as observed prices with prescribed assumptions, never synthetic or historically certified. Save research_assumptions.json and funding mark audit (including exact and substituted records) under output hashes. Expose approximation counts and explicit limitations. Existing reports/checksums/regeneration must work.

Add predeclared research sensitivities alongside existing scenarios: funding_proxy_stress_bps +10/-10, futures fee 0.0004, maintenance multiplier 2, liquidation fee 0.03. Existing cost 2x/3x remain. All use same helper, rulebook and validation as baseline.

Tests: immutable provenance, report label, regeneration, research mode selection and one-factor config differences; exact marks not stressed.

## Task 5: Verification, pilot and handoff

Run all tests and Ruff. Try a real-data sample validation and pilot; if an unrelated source integrity gate fails, preserve the failure and report it explicitly. Do not call fabricated/fixture results historical. Measure real replay if feasible on a valid bounded observed sample. Document PowerShell commands for validation, pilot, full run, and selected sensitivities using D: root plus absolute research config. Document remaining source gaps and that processing/replay runtime is separate from download runtime. Do not claim a completed full-window backtest without actual results.

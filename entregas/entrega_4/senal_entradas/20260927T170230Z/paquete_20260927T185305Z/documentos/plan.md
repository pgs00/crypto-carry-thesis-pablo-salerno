# Signal and entry sensitivity implementation plan

> Execution: superpowers:executing-plans, inline, task by task. The user's explicit
> instruction authorizes the closed matrix and forbids commits/index changes;
> no additional planning approval or worktree mutation is required.

**Goal:** Execute twelve independent new portfolios and produce verified evidence.
**Architecture:** New scripts outside src reuse GapAuditedBacktest/iter_records/write_run,
existing Decimal financial reconstruction, corrected exposure/H2 and entry diagnostics.
Compact package snapshots those tools and sufficient evidence; large runs remain local.
**Tech stack:** Existing Python 3.14 environment, pandas/pyarrow/Decimal/matplotlib/pytest/Ruff.
**Spec:** encargo_usuario.md and protocolo.md in this directory.

## Constraints and review focus

No economic code changes; no old artifact edits; 1E-8 USDT tolerance; exact six-way diff.
Review horizons near final boundary, subminute funding availability, terminal dust,
inherited yearly state, semantic corruption even with refreshed hashes. Their tests
belong respectively to tasks 1, 1, 3, 3, 4. Decisions and deviations go in progreso.md.

## Task 1: preflight, configuration, tests and compatibility

- [ ] Capture Git/index, hashes of original files and data, authenticate source seals.
- [ ] Create tests/unit/test_signal_sensitivity.py before scripts/signal_sensitivity.py.
- [ ] Run RED for matrix/diff guard, then implement minimal six-scenario derivation.
- [ ] Exercise existing forecast, evaluation, basis, renewal, risk and accounting tests.
- [ ] Freeze protocol/configs/code; compare deterministic control with original runner.

Interfaces: scenario_configs(base), validate_variant(base, scenario, candidate),
simulate(config, data_root, strategy, inputs); no engine changes.

## Task 2: sequential dimensions and resumable run records

- [ ] Implement scripts/run_signal_sensitivity.py using immutable local run destinations.
- [ ] Tests reject mixed params and stale resume identities; write independent states/logs.
- [ ] Execute H072/H336, reconcile; V012/V048, reconcile; B025/B100, reconcile.
- [ ] Authenticate original BASE and preserve its identifiers; do not resimulate blindly.

Interfaces: indice_corridas.json, one record per scenario/strategy, compact H3 aggregates,
original run tables/manifest at explicit local dependency paths.

## Task 3: reproducible postprocessing and report

- [ ] Add tests for inherited financials, dust/union, H1 units and H3 unknowns.
- [ ] Implement scripts/signal_sensitivity_report.py and reuse corrected existing methods.
- [ ] Daily/per-period financials, exposure, cycles/actions/decisions, H1/H2/H3 and deltas.
- [ ] Report MD/HTML with annual capital context, curves, invariances and limitations.

## Task 4: independent checks, portable package and preservation

- [ ] Implement scripts/verify_signal_sensitivity.py with numerical/identity checks.
- [ ] Corrupt configuration/H1/H2/H3/period/metrics in temporary copies, refresh hashes;
      each must still fail. Check verifier is read-only and relocated execution passes.
- [ ] Freeze snapshots, manifest/checksum and requirement matrix with concrete evidence.
- [ ] Run relevant and full tests, Ruff, source and per-run reconciliation checks.
- [ ] Review the complete change; scope-limited .gitattributes and isolated index export.
- [ ] Rehash protected files/data and user index; report actual outcomes and commands.

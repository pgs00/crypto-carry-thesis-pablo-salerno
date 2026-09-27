# Execution ledger — plan: plan.md

- 2026-09-27T17:02:30Z: Read full user specification. Git clean, branch codex/crypto-carry,
  HEAD 70b03969afed2637ae6819acc5c0c439dbdac1f0. Index SHA256
  d1a7ea6f7d66832fa2a8d19a778c706735108079cb05bbb7a32f1fcfa3f66ecc.
- Data/root for original portfolios verified at D:/Backtesting. Engine identity
  314631c24b36bbee58eb55a9b17505af656de453b60d1496c067e6f30b33de97 matches
  previous rules batch; defaults and source untouched. Environment Python 3.14.3.
- Pre-flight interfaces: runner consumes Config derived from original; reporter consumes
  persisted raw runs; verifier consumes package and explicit dependencies. No conflict.
- Task 1 in progress: preservation and existing-contract audit.

- Task 1 complete: five source seals authenticated; all original input hashes match; 147 stage-A tests passed; 4 route controls and archived January digests match exactly. Runner frozen in protocolo_previo.json.
- Task 2 in progress: stage H, two workers, serialized writer. No economic source changes.
- Test fixture ruling: EWMA ratio checked at 26 decimal places due to existing Decimal context rounding; money tolerance remains 1E-8, no engine change.

- 2026-09-27T17:52:43.412644+00:00: Stage H complete, 4 portfolios / 6816 daily closes / 32 periods reconciled. Guard companion passed frozen engine/runner identity and original sources. Stage V launched with the same frozen runner and 2 workers.
- Read-only review found 6 evidence/reporting safeguards, reproduced and corrected with tests: per-period residual tolerance, manifest label/status identity, predeclared engine identity, unique H3 asset-days, insolvency ND semantics, protected output paths. Engine and frozen runner unchanged. Reviewer recheck found no remaining Important issues.
- Additional actual H072/H336 expiry-risk tests: initial test assumed exactly two close_requested diagnostics; existing engine repeats risk requests after first closure. Corrected test to assert first request at each actual expiry, no renewal, exact eight fills and zero remaining short. No economic-code change. The original failed log is retained, followed by a separate green log.
- Full regression: 986 passed, 13 actual-package tests deferred until candidate exists. Extended horizon/risk clocks: 8 passed. Ruff src/scripts/tests passed. Historical cleanup check fails on a pre-existing config.py hash difference; current bytes equal pre-task bytes; historical manifest untouched.
- New preservation audit first encountered the existing intraday seal using files rather than members. Added support for that documented schema; no source/economic changes; failure log retained.
- Delivery tool review: direct CLI import path corrected and tested; output guard now rejects any prior sealed ancestor before audit. Synthetic isolated Git export retained CRLF and binary bytes and preserved a pre-existing temporary index. Fixture initially lacked cr-at-eol whitespace allowance; matched the actual scoped attributes. Guard group: 12 tests passed; Ruff full src/scripts/tests passed after import formatting.
- 2026-09-27T18:23:43.284377+00:00: Stage V complete: 4 portfolios, 6816 daily closes and 32 periods reconciled; predeclared engine and runner still equal. Stage B launched, same two workers and serialized writer. V012 permanent economic histories match BASE exactly; V048 final equity also matches, full-table invariance remains a final package check.
- H1 historical V012/V048 reconstructed: both targets and no-change exactly equal BASE; 10180 valid observations each. Compacted only the large derived decisions table into lossless Parquet string cells; exact nanosecond/Decimal round-trip test passed. Raw runs untouched.

La revisi?n final del reporte detect? una s?ntesis interpretativa insuficiente. Se a?adi? una conclusi?n calculada desde tablas, con diferencias H2/H3, actividad/capital y separaci?n de invariancia econ?mica frente a H3. RED esperado por funci?n ausente; GREEN de reporte/verificador: 8 pruebas. Ruff pas? tras el ajuste. El motor y el runner congelado permanecen intactos.

2026-09-27T18:53:05.079141+00:00: Etapa B terminada y auditada: cuatro carteras completas, 6.816 cierres y 32 per?odos conciliados a 1E-8; sin cambios del motor ni reinicios. Se inicia la consolidaci?n de 12 nuevas carteras y las dos BASE autenticadas.

2026-09-27T19:08:42.284621+00:00: Candidato construido. Verificaci?n con datos locales PASS: 14 carteras, 23.856 cierres, 112 per?odos, 168 filas resumen H1 y 56 H3. Exportaci?n temporal Git PASS, ?ndice original intacto. Verificaci?n portable offline en proceso aislado PASS: s?lo c?digo incluido y 469 archivos sin modificaci?n. Pruebas de corrupci?n todav?a en curso; el candidato permanece sin sello.

2026-09-27T19:10:49.958592+00:00: Pruebas sobre el paquete real: 13 PASS, incluidas 11 corrupciones sem?nticas con hashes renovados. Regresi?n previa: 994 PASS y 13 casos entonces pendientes, ahora ejecutados; ajuste final de conclusi?n: 8 PASS; Ruff PASS. Se agregan comprobantes anteriores al sello, sin modificar resultados ni c?digo. Matriz del bloque 2 cumplida; no se declara terminada toda E4. Auditor?a final del sello/exportaci?n a?n externa y posterior.

2026-09-27T19:18:59.682954+00:00: CIERRE DEL BLOQUE 2. Paquete sellado y exportaci?n final verificados num?ricamente offline: 498 miembros, 500 archivos exactos, sin escrituras al paquete y usando s?lo c?digo incluido. ?ndice Git original intacto y diff preparado vac?o; sin commit/push. validacion_final.json re?ne alcance y comprobantes. No se declara completa toda E4.

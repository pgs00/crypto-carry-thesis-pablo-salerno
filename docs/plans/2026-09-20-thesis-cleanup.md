# Thesis repository presentation cleanup

User-authorized scope: present the saved continuous portfolios over
`[2022-01-01, 2026-09-01)` UTC; keep engine, parameters, prior results and local
Binance files unchanged. Do not replay, commit, push or rewrite history.

1. Snapshot tracked-file hashes and compare the historical expanded package
   with the original v2 ZIP before any move/deletion. Completed: all 140 members
   match; the outer `preparar_paquete.py` duplicates its packaged copy (6,858 bytes).
2. Move the independent-window packages into `entregas/entrega_3/archivo/`, keeping
   source bytes and relative package structure. Remove only the proven duplicate
   script, redirect its consumers, and retain obsolete one-off tooling as source
   snapshots. Keep the integrity helper executable and update its test path.
3. Publish a compact continuous view with source-identical summary CSVs, a daily
   equity projection and deterministic figures derived from the current ZIP.
   Include a manifest, reproduction command and a verifier; no Binance inputs.
4. Rewrite README/methodology/progress consistently. Identify historical windows,
   explorations and pilots through archive/index documents. Preserve the pilot
   quality report as a byte-identical archive; keep executable input manifests
   in place with explicit scope documentation. Retain the 15-mark and funding
   sensitivity evidence in their existing paths.
5. Inventory exploratory research and its retention reasons instead of removing
   provenance dependencies. Extend ignore rules for local research market files;
   do not delete or upload them. Repair affected navigation and Git attributes.
6. Run package/provenance/link/figure checks, existing pytest and Ruff, and obtain
   a read-only review. Record moved, removed and retained files with hashes.

Presentation figures: daily equity/drawdown, full-period P&L composition and H1/H3
comparison. Main metrics and period cuts retain original values; H3 uses the full
eligible forecast, no cost subtraction. Older independent windows remain readable
in the archive and are not concatenated into continuous results.

Completed on 2026-09-20. The preservation verifier, existing suite plus five
encoding regression cases (485 passed), Ruff and deterministic publication
round-trip all pass. Independent review completed; its encoding finding was
fixed and rechecked. See [cleanup record](../repository_cleanup.md) for the
inventory and validation evidence. No annual replay, commit or push was performed.

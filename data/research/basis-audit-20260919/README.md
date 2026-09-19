# Auditoría del basis — 19/09/2026

Se ejecutó el [instructivo del usuario](../../../docs/sources/Prompt_Codex_Auditoria_Basis.md)
sobre el escenario `vwap_joint` de las dos ventanas anuales. El basis negativo
quedó confirmado en las velas originales, con cobertura de 4.380/4.380
observaciones únicas, 96 ZIP y 8.760 decisiones de estrategia.

| Ventana | Activo | Basis negativo | Cero | Elegible [0;0,005] |
|---|---|---:|---:|---:|
| 2022–2023 | BTCUSDT | 1.044 | 0 | 51 |
| 2022–2023 | ETHUSDT | 1.006 | 3 | 89 |
| 2025–2026 | BTCUSDT | 1.090 | 0 | 5 |
| 2025–2026 | ETHUSDT | 1.095 | 0 | 0 |

Cada fila tiene 1.095 observaciones. Cero está incluido en elegible: no se suman
esas dos columnas como categorías excluyentes. Ningún basis superó 0,005.
Las cifras describen instantes de decisión, no todos los minutos del año.

Se corrigió sólo el reporte: una condición de funding incumplida de la
permanente estaba rotulada y agregada como rechazo aunque esa estrategia omite
el filtro. Ahora se informa como `diagnostic_fail_not_applied`, fuera de la
unión de rechazos. Las decisiones reales, operaciones y resultados no cambian.

- [Reporte completo](../../../outputs/basis_audit_afd512e8a542f331ffa9ac3f/basis_audit_report.md).
- [Todas las observaciones](../../../outputs/basis_audit_afd512e8a542f331ffa9ac3f/basis_audit_all.csv).
- [80 observaciones de muestra](../../../outputs/basis_audit_afd512e8a542f331ffa9ac3f/basis_audit_sample.csv).
- [Estadísticas por ventana y activo](../../../outputs/basis_audit_afd512e8a542f331ffa9ac3f/basis_audit_summary.csv).
- [Manifiesto y checksums](../../../outputs/basis_audit_afd512e8a542f331ffa9ac3f/basis_audit_manifest.json).
- [Comparación económica con presentación corregida](D:/Backtesting/outputs/revision_eb5ed744b30836a39fd694fa/execution_revision_report.md).

## Reproducir

Desde la raíz de `Backtesting`, con los datos locales de D: disponibles:

```powershell
& '.\.venv\Scripts\python.exe' data/research/basis-audit-20260919/verify_basis.py `
  --root 'D:\Backtesting' `
  --revision revision_dcf7d66e69aaf51cea4590ff `
  --corrected-revision revision_eb5ed744b30836a39fd694fa
```

El comando vuelve a leer las fuentes, contrasta los resultados, verifica hashes
y conserva las auditorías ya existentes. Los nuevos artefactos quedan en
`outputs/basis_audit_<identificador>/` dentro del proyecto; esa carpeta está
excluida de Git por la regla existente. Para compartir la evidencia hay que
incluir esa carpeta además del código del auditor.

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/unit/test_basis_audit.py tests/unit/test_execution_revision.py -q --tb=short
```

El auditor no importa funciones del motor. Lee CSV originales con `csv` y
`zipfile`, precios normalizados con PyArrow y calcula `F/S-1` con Decimal de 60
cifras. La tolerancia es `1e-12`; un cambio de clasificación siempre se señala,
aunque su diferencia numérica sea menor. Las pruebas cubren ejemplos manuales,
límites inclusivos, ms/us, causalidad, desalineación, faltantes y duplicados.

Validar el basis no valida por sí solo la rentabilidad ni todo el backtest.

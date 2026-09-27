# Bloque 2 terminado: se?al y selecci?n de entradas

[Reporte HTML](paquete_20260927T185305Z/reporte.html) ? [Reporte Markdown](paquete_20260927T185305Z/reporte.md) ? [Validaci?n final](validacion_final.json) ? [Matriz de requisitos](paquete_20260927T185305Z/matriz_requisitos.csv)

Se ejecutaron H072, H336, V012, V048, B025 y B100, cada una en condicional y permanente: doce carteras nuevas, sin cruces. Las dos BASE se reutilizaron despu?s de autenticar su configuraci?n, c?digo y fuentes. Los catorce estados econ?micos son `complete`. La muestra continua es [2022-01-01,2026-09-01), con 10.000 USDT iniciales, sin reinicios anuales.

En la muestra completa, H2 sigue `no_favorable` y H3 `contraria` en las seis variantes. H336 cambia H2 a favorable en 2023 y 2024; el reporte conserva todos los a?os y cortes. V012 eleva el MAE EWMA de 6,298978 a 6,745373 pb/168 h y V048 lo reduce a 6,170673; ambas permanentes conservan exactamente su econom?a BASE. EWMA mantiene menor MAE agregado que no-change en cada horizonte, sin que eso permita comparar directamente MAE de 72/168/336 horas.

La condicional H072 obtiene 487,80 USDT de P&L y utiliza en promedio diario 11,7509% del patrimonio; H336 obtiene 1.223,15 USDT y utiliza 47,8552%, frente a 785,76 USDT y 19,8068% de BASE. Son cambios conjuntos de pron?stico, tenencia, actividad y capital, sin identificaci?n causal aislada ni selecci?n de un par?metro ganador.

B025/B100 mantienen exactamente la econom?a de ambas estrategias, pero modifican H3 en 13 y 5 d?as, respectivamente. No se forzaron diferencias ni se confundi? la poblaci?n de decisiones con los minutos de mercado.

## Evidencia y controles

- [?ndice de catorce corridas](paquete_20260927T185305Z/indice_corridas.json), con los run_id y las doce ejecuciones nuevas; comandos y logs en `paquete_20260927T185305Z/ejecucion/`.
- [M?tricas de ocho per?odos](paquete_20260927T185305Z/tablas/metricas.csv), [deltas](paquete_20260927T185305Z/tablas/deltas.csv), [invariancias](paquete_20260927T185305Z/tablas/invariancias.csv) y [evidencia diaria](paquete_20260927T185305Z/tablas/diario.csv).
- 23.856 cierres y 112 per?odos conciliados a 1E-8 USDT. Exposici?n y H2 usan los m?todos corregidos; los nuevos drawdowns y extremos de garant?as est?n rotulados como diarios.
- Regresi?n: 994 pases y 13 casos entonces omitidos por falta del paquete. Esos 13 casos luego se ejecutaron y pasaron, incluidas 11 corrupciones sem?nticas con hashes renovados. Tras la ?ltima mejora del reporte, 8 pruebas focalizadas pasaron. Estos conteos se solapan y no se suman.
- Ruff `src scripts tests`: PASS. [Comprobantes anteriores al sello](paquete_20260927T185305Z/pruebas/validaciones_pre_sello.json).
- [Verificaci?n con datos locales](verificacion_candidato_datos.json): autentica 1.731 inputs y reconstruye H3 contra los minutos. [Verificaci?n final portable](verificacion_portable_final.json): recalcula desde la evidencia incluida en otra ruta, offline, con c?digo incluido y 500 archivos sin modificaci?n.
- [Preservaci?n y exportaci?n final](preservacion_exportacion_final.json): paquetes anteriores, 98 archivos originales BASE, c?digo congelado e ?ndice del usuario preservados; los nuevos bytes exportados coinciden. [Estado Git](estado_git_final.json): sin commit/push ni cambios preparados; el ?nico archivo previamente versionado modificado es `.gitattributes`, con reglas limitadas a esta evidencia.

Sello SHA-256: `f03624b6bdb40a3c9dfb31705a9c5c3552308200a953f9f5e80cce2137140095`. [Manifiesto](paquete_20260927T185305Z/manifiesto_paquete.json) ? [Checksum](paquete_20260927T185305Z/manifiesto_paquete.sha256).

## Repetir la verificaci?n

Con Python 3.14 y dependencias del lock incluido, se puede ejecutar desde cualquier directorio el script incluido; la salida debe ser nueva y externa al paquete. Los comandos concretos del proceso portable y su directorio constan en [control_portable_final.json](control_portable_final.json).

```powershell
python -B -X utf8 <paquete>/herramientas/scripts/verify_signal_sensitivity.py --package <paquete> --output <auditoria_nueva.json>
python -B -X utf8 <paquete>/herramientas/scripts/verify_signal_sensitivity.py --package <paquete> --data-root D:/Backtesting --output <auditoria_datos_nueva.json>
```

Constructor y verificador comparten helpers: no se afirma independencia integral ni un replay del motor al verificar. Los archivos masivos siguen en D:/Backtesting y no se duplican por escenario dentro del paquete compacto.

El [control hist?rico general](paquete_20260927T185305Z/documentos/control_historico_general.json) conserva un fallo preexistente: espera un hash anterior de `src/crypto_carry/config.py`. El archivo actual coincide con el registro anterior al bloque. No se alter? el manifiesto antiguo ni se cont? ese control como aprobado. No quedan escenarios bloqueados en este bloque; no se declara completa toda Entrega 4. No se reh?zo SOFR, concentraci?n ni riesgo intrad?a, ni se gener? PDF final.

# Bloque 2 terminado: señal y selección de entradas

Lectura vigente: distribución documental `20261010`, con
[protocolo e identidad propios](distribucion_20261010/protocolo_distribucion.md).
Los controles, conteos de archivos y sello citados corresponden al cierre
original y no certifican por sí mismos esta distribución.

[Reporte HTML](distribucion_20261010/reporte.html) · [Reporte Markdown](distribucion_20261010/reporte.md) · [Validación final](validacion_final.json) · [Matriz de requisitos](distribucion_20261010/matriz_requisitos.csv)

Se ejecutaron H072, H336, V012, V048, B025 y B100, cada una en condicional y permanente: doce carteras nuevas, sin cruces. Las dos BASE se reutilizaron después de autenticar su configuración, código y fuentes. Los catorce estados económicos son `complete`. La muestra continua es [2022-01-01,2026-09-01), con 10.000 USDT iniciales, sin reinicios anuales.

En la muestra completa, H2 sigue `no_favorable` y H3 `contraria` en las seis variantes. H336 cambia H2 a favorable en 2023 y 2024; el reporte conserva todos los años y cortes. V012 eleva el MAE EWMA de 6,298978 a 6,745373 pb/168 h y V048 lo reduce a 6,170673; ambas permanentes conservan exactamente su economía BASE. EWMA mantiene menor MAE agregado que no-change en cada horizonte, sin que eso permita comparar directamente MAE de 72/168/336 horas.

La condicional H072 obtiene 487,80 USDT de P&L y utiliza en promedio diario 11,7509% del patrimonio; H336 obtiene 1.223,15 USDT y utiliza 47,8552%, frente a 785,76 USDT y 19,8068% de BASE. Son cambios conjuntos de pronóstico, tenencia, actividad y capital, sin identificación causal aislada ni selección de un parámetro ganador.

B025/B100 mantienen exactamente la economía de ambas estrategias, pero modifican H3 en 13 y 5 días, respectivamente. No se forzaron diferencias ni se confundió la población de decisiones con los minutos de mercado.

## Evidencia y controles

- [índice de catorce corridas](distribucion_20261010/indice_corridas.json), con los run_id y las doce ejecuciones nuevas; comandos y logs en `distribucion_20261010/ejecucion/`.
- [Métricas de ocho períodos](distribucion_20261010/tablas/metricas.csv), [deltas](distribucion_20261010/tablas/deltas.csv), [invariancias](distribucion_20261010/tablas/invariancias.csv) y [evidencia diaria](distribucion_20261010/tablas/diario.csv).
- 23.856 cierres y 112 períodos conciliados a 1E-8 USDT. Exposición y H2 usan los métodos corregidos; los nuevos drawdowns y extremos de garantías están rotulados como diarios.
- Regresión: 994 pases y 13 casos entonces omitidos por falta del paquete. Esos 13 casos luego se ejecutaron y pasaron, incluidas 11 corrupciones semánticas con hashes renovados. Tras la última mejora del reporte, 8 pruebas focalizadas pasaron. Estos conteos se solapan y no se suman.
- Ruff `src scripts tests`: PASS. [Comprobantes anteriores al sello](distribucion_20261010/pruebas/validaciones_pre_sello.json).
- [Verificación con datos locales](verificacion_candidato_datos.json): autentica 1.731 inputs y reconstruye H3 contra los minutos. [Verificación final portable](verificacion_portable_final.json): recalcula desde la evidencia incluida en otra ruta, offline, con código incluido y 500 archivos sin modificación.
- [Preservación y exportación final](preservacion_exportacion_final.json): paquetes anteriores, 98 archivos originales BASE, código congelado e índice del usuario preservados; los nuevos bytes exportados coinciden. [Estado Git](estado_git_final.json): sin commit/push ni cambios preparados; el único archivo previamente versionado modificado es `.gitattributes`, con reglas limitadas a esta evidencia.

Sello original SHA-256: `f03624b6bdb40a3c9dfb31705a9c5c3552308200a953f9f5e80cce2137140095`.
Identidad de la distribución actual: [manifiesto](distribucion_20261010/manifiesto_paquete.json)
y [checksum](distribucion_20261010/manifiesto_paquete.sha256).

## Repetir la verificación

Con Python 3.14 y dependencias del lock incluido, se puede ejecutar desde cualquier directorio el script incluido; la salida debe ser nueva y externa al paquete. Los comandos concretos del proceso portable y su directorio constan en [control_portable_final.json](control_portable_final.json).

```powershell
python -B -X utf8 <paquete>/herramientas/scripts/verify_signal_sensitivity.py --package <paquete> --output <auditoria_nueva.json>
python -B -X utf8 <paquete>/herramientas/scripts/verify_signal_sensitivity.py --package <paquete> --data-root D:/Backtesting --output <auditoria_datos_nueva.json>
```

Constructor y verificador comparten helpers: no se afirma independencia integral ni un replay del motor al verificar. Los archivos masivos siguen en D:/Backtesting y no se duplican por escenario dentro del paquete compacto.

El [control histórico general](distribucion_20261010/documentos/control_historico_general.json) conserva un fallo preexistente: espera un hash anterior de `src/crypto_carry/config.py`. El archivo actual coincide con el registro anterior al bloque. No se alteró el manifiesto antiguo ni se contó ese control como aprobado. No quedan escenarios bloqueados en este bloque; no se declara completa toda Entrega 4. No se rehízo SOFR, concentración ni riesgo intradía, ni se generó PDF final.

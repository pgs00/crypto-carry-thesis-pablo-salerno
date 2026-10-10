# Auditoría de ejecución del bloque 3

Matriz de 18 resultados: 16 trayectorias nuevas y dos referencias reutilizadas.

| Escenario | Cartera | Estado técnico | Estado económico | Run ID | Replay s | Total s | RAM pico GiB | Cierres | Residual diario máx. |
|---|---|---|---|---|---|---|---|---|---|
| BASE_E3 | conditional | reutilizado_verificado | complete | run_ad71d751b20623006c195ff3 | ND | ND | no nuevo replay | referencia | referencia |
| BASE_E3 | permanent | reutilizado_verificado | complete | run_dfea4b7ac1475668d5968c97 | ND | ND | no nuevo replay | referencia | referencia |
| C02 | conditional | ejecutado | complete | run_f7473a5631a2b3c8d6a8a38b | 553.31 | 617.21 | 2.813 | 1704 | 1.3E-24 |
| C02 | permanent | ejecutado | complete | run_ee33680946eec3de1f7e7257 | 821.17 | 886.11 | 2.840 | 1704 | 1.1E-23 |
| C03 | conditional | ejecutado | complete | run_a0ed2769328f20cec70e1730 | 544.92 | 606.64 | 2.814 | 1704 | 3.0E-24 |
| C03 | permanent | ejecutado | complete | run_bf973138c8fc39e40edc6aec | 820.22 | 883.21 | 2.832 | 1704 | 1.0E-23 |
| S02 | conditional | ejecutado | complete | run_c1d79e4939c0e3701ad86502 | 545.36 | 607.84 | 2.854 | 1704 | 1E-24 |
| S02 | permanent | ejecutado | complete | run_34c912c4b25808961d018bce | 999.08 | 1095.20 | 2.826 | 1704 | 1.1E-23 |
| S05 | conditional | ejecutado | complete | run_5d468c6eb4e33916e6c3c91e | 654.40 | 721.94 | 2.808 | 1704 | 1.1E-23 |
| S05 | permanent | ejecutado | complete | run_bfda1ca3a742fbc7002aefc5 | 1836.95 | 1989.89 | 2.835 | 1704 | 1.05E-23 |
| P050 | conditional | ejecutado | complete | run_0bf8ede3c7b7c8f038888a67 | 1189.91 | 1271.63 | 2.859 | 1704 | 1.0E-23 |
| P050 | permanent | ejecutado | complete | run_42614245ad3f090a4da31f8d | 1580.33 | 1659.99 | 2.834 | 1704 | 1.02E-23 |
| P025 | conditional | ejecutado | complete | run_d946c24cbcf58f0bdb0c7cbe | 631.16 | 707.01 | 2.800 | 1704 | 1.0E-24 |
| P025 | permanent | ejecutado | complete | run_dc400ae8f255b3c15916429e | 910.89 | 974.24 | 2.839 | 1704 | 1.10E-23 |
| A050 | conditional | ejecutado | complete | run_6017a8482dabe20305435f89 | 610.38 | 689.76 | 2.808 | 1704 | 1.7E-23 |
| A050 | permanent | ejecutado | complete | run_30970a364f24039caa24b1cd | 1122.27 | 1205.92 | 2.823 | 1704 | 1.5E-23 |
| A100 | conditional | ejecutado | complete | run_9c2e9a8d6f595f052d58ad96 | 618.91 | 714.35 | 2.859 | 1704 | 1.03E-22 |
| A100 | permanent | ejecutado | complete | run_e38a5243e0d8dcf1317822c9 | 874.47 | 937.12 | 2.828 | 1704 | 1.00E-22 |

Tiempo total comprende replay, espera por el escritor y materialización. RAM es el máximo del proceso registrado por Windows; no representa la suma de procesos ni una estimación. Se midió primero una ventana secuencial y se usó un máximo de dos replays, con un solo escritor de resultados.

Identidades, configuración, horas UTC, intentos, destinos, comandos, logs y protocolos: [índice](indice_corridas.json) y carpeta `ejecucion/`. Las puertas `control_etapa_*` exigen conciliación financiera, selección, orden/fill/ledger y volumen antes de avanzar a la familia siguiente.

El código económico conserva una sola identidad en las 16 variantes. Los protocolos técnicos v1/v2/v3 documentan mejoras de recuperación sin cambiar precios, tarifas, sizing ni reglas. Reanudar una corrida terminada exige configuración, estrategia, escenario, datos y código compatibles y todos sus artefactos originales válidos. Un intento incompleto no se retoma desde estado BASE.

El auditor reconstruye caja, deuda, inventario neto y garantías; enlaza cada cierre y la última posición efectiva de cada timestamp con el ledger. Los snapshots intermedios pueden representar estados previos al movimiento. El buffer original de pérdida de apertura se conserva como registro autenticado; no se reconstruye una nueva serie de marks intradía.

Las pruebas, incluidos fallos y correcciones, se conservan en `pruebas/`; [cobertura del encargo](controles/cobertura_pruebas.md) y [revisión independiente](controles/revision_independiente.md). Los conteos de suites solapadas no se suman. Los resultados de la comprobación final del sello, exportación y copia offline se guardan externamente para no modificar el paquete sellado.

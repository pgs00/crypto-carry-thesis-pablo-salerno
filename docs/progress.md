# Avance y evidencia — 19/09/2026

## Auditoría del basis

La [auditoría independiente](../outputs/basis_audit_afd512e8a542f331ffa9ac3f/basis_audit_report.md)
confirmó las 4.380 observaciones de mercado contra 96 ZIP originales: cero
discrepancias en precios, intervalos, disponibilidad y clasificación. Se revisaron
8.760 decisiones sin duplicar observaciones de mercado. El basis tardío es
negativo en 1.090/1.095 casos BTC y 1.095/1.095 ETH; el máximo error decimal es
aproximadamente `4,971e-28`, frente a la tolerancia fija `1e-12`.

Se demostró y corrigió un defecto de presentación: funding omitido por la
permanente se contaba como rechazo simultáneo. El
[informe corregido](D:/Backtesting/outputs/revision_eb5ed744b30836a39fd694fa/execution_revision_report.md)
se regeneró desde las mismas diez corridas, sin volver a simular ni alterar
resultados económicos. El anterior permanece conservado. **414 pruebas pasaron**
en 41,04 s. [Auditor, alcance y reproducción](../data/research/basis-audit-20260919/README.md).

## Revisión vigente de ejecución

Se implementó y ejecutó el [instructivo de ajuste 1m](sources/Prompt_Codex_Ajuste_Backtesting_1m.md).
El [informe de la revisión](D:/Backtesting/outputs/revision_eb5ed744b30836a39fd694fa/execution_revision_report.md)
es la comparación vigente: cinco escenarios, dos ventanas y dos carteras por
escenario. Las ocho corridas nuevas y las dos referencias conservadas tienen
estado `complete`; las referencias originales no se sobrescribieron.

El principal, fijado antes de observar resultados, es `vwap_joint`: VWAP del
siguiente minuto elegible, fill al cierre, capacidad del 1%, parciales y sizing
conjunto. `alignment_only` separa el cambio de observación del resto del contrato.
Cada cartera comienza con 10.000 USDT, sin arrastrar posiciones entre ventanas.

| Ventana | Cartera principal | Equity final USDT | Retorno | Sharpe | DD diario | Fills |
|---|---|---:|---:|---:|---:|---:|
| 01/09/2022–31/08/2023 | Condicional | 10.073,6363 | 0,7364 % | 1,9182 | −0,1224 % | 18 |
| 01/09/2022–31/08/2023 | Permanente | 10.334,3990 | 3,3440 % | 4,1101 | −0,1359 % | 72 |
| 01/09/2025–31/08/2026 | Condicional | 10.000,0000 | 0 % | Indefinido | 0 % | 0 |
| 01/09/2025–31/08/2026 | Permanente | 10.008,5990 | 0,0860 % | 1,9603 | −0,0095 % | 2 |

En la ventana temprana, la condicional sólo abre carry completo en ETH: BTC
rechaza sus 1.095 evaluaciones por funding. Hay una apertura parcial fallida
que se desarma y un ciclo completo posterior. La permanente logra seis aperturas
completas entre ambos activos: cuatro ciclos cerrados y dos todavía abiertos al
corte. En la tardía, la condicional rechaza las 2.190 evaluaciones por funding
insuficiente. La permanente tiene una apertura BTC, con cobertura viable gracias
al sizing conjunto, y permanece invertida al corte. ETH rechaza sus 1.095
evaluaciones por basis negativo. Los cierres terminales no se inventan.

H1 conserva menor MAE del EWMA en ambas ventanas, sobre 2.146 observaciones
comparables y 44 exclusiones por ventana. H2 es contraria al criterio en la
temprana y no concluyente en la tardía, donde falta Sharpe condicional. H3 muestra
menor oportunidad y CAGR condicional en la ventana tardía, con 365 días válidos
en cada una. Son resultados descriptivos de ventanas independientes.

El 24/03/2023 sigue dentro de la muestra. En el principal, el cierre de futuros
se registra a las 12:00 y el spot a las 14:01 UTC: 121 minutos sin cobertura por
activo. El cambio diario de equity condicional es 35,9089 USDT, frente a 64,8580
de la referencia. Para ETH, los fills principales de cierre son 1.746,83 USDT
en futuros y 1.770,96 en spot. El informe compara BTC y ETH por separado y conserva
órdenes, precios fuente, volúmenes, funding, fees y ledger; no se restó el episodio
para fabricar otro backtest anual.

### Verificación y procedencia

- **398 pruebas aprobadas** en 41,50 s; Ruff check y format --check limpios.
- Matriz piloto real completa en `[2023-01-14,2023-01-16)` y
  `[2026-08-21,2026-08-23)`, con calentamiento y carteras independientes. Son
  comprobaciones de software elegidas por actividad conocida de la referencia,
  no calibración de parámetros ni evidencia anual adicional.
- [Auditoría económica independiente](../data/research/minute-download-20260918/execution-revision-audit.json):
  diez corridas y **520 fills**, caja, inventario, fees y funding reconstruidos
  sin importar el ledger del motor. Los VWAP se contrastaron directamente con
  los ZIP originales: 76 comprobaciones en total, contando las repeticiones
  entre corridas que comparten fuentes. No hubo discrepancias; máximo residuo de caja de aproximadamente
  `2,413e-24` USDT, frente a la tolerancia `1e-8`.
- No hubo descargas adicionales. Se recuperaron OHLC y ambos volúmenes desde
  la caché; se agregaron 260.960.966 bytes de Parquet compartido. La medición
  posterior de las dos carpetas de datos fue 956.984.856 bytes.
- Código de las simulaciones nuevas:
  `4e78e13aa1618137f790a0253c43355b31fe184eaa9bfdac12b61ad6d2a129ac`.
  Después se corrigió únicamente la presentación de precios de cierre por activo
  y se añadió regeneración de la comparación desde sus tablas verificadas. El
  informe registra por separado su versión y la de cada simulación: no se
  modificaron fills, equity ni configuraciones para esa regeneración.
- Los scripts privados, snapshots de código y registro de tiempos permanecen
  en `.superpowers/execution-revision/`; la auditoría reproducible se publica
  en [verify_execution_revision.py](../data/research/minute-download-20260918/verify_execution_revision.py).

Para verificar y regenerar la comparación guardada, sin repetir simulaciones:

```powershell
& '.\.venv\Scripts\python.exe' -m crypto_carry --root 'D:\Backtesting' report --run-id revision_dcf7d66e69aaf51cea4590ff
```

El comando para ejecutar de nuevo toda la matriz está en el [README](../README.md#reproducir-la-comparación).
Las reglas históricas prescritas, el proxy de mark temprano y las limitaciones
de ejecución siguen explícitos; `complete` describe la corrida bajo esos
supuestos, no una reconstrucción exacta del mercado.

## Referencia anterior — 18/09/2026

### Estado de la referencia anterior

Se aprobaron dos ventanas de doce meses con modelo por minuto, para apuntar a
terminar en 48 horas. El [protocolo](escenario_investigacion.md) fija las fechas,
supuestos y pendientes; la [guía de descarga](descarga_d.md) contiene el comando.

- **Descarga terminada:** ambas ventanas informan `download_complete`, 106/106
  archivos/respuestas cada una, sin errores: 208 ZIP más cuatro respuestas de
  funding. Se incorporaron seis ZIP diarios oficiales para completar los marks.
  Ambas ventanas pasaron la cobertura anual. Crudos, Parquet y manifiestos
  ocupan aproximadamente 643 MB en D:; el usuario eliminó los datos masivos viejos.
- **Motor por minuto implementado:** eventos de precio y volumen separados,
  fills posteriores, vencimiento de 120 segundos, conciliación nativa y
  reanudación entre patas. Ambas corridas anuales terminaron con cobertura completa.
- **Piloto de trades:** diez minutos del 01/01/2024, seis fills nativos por
  cartera y conciliación exacta. Se conservan los cuatro ZIP originales y las
  auditorías; el día completo no está certificado por discontinuidades de IDs.
- **Contraste por minuto:** conserva seis fills y diferencia contable cero;
  equity final de 9.988,4700 frente a 9.985,5135 USDT con trades. El control
  con trades y timeout de 120 segundos no altera el resultado original.
- **Pilotos de 14 días:** ambas ventanas terminan sin órdenes, por los filtros
  de funding/costo y base. El piloto 2022 tarda 22,23 segundos incluyendo
  validación e informes, con pico de 868 MB. La prueba sintética adicional
  verifica una renovación a las 168 horas de simulación y funding cobrado.
- **Funding y reglas:** escenario de supuestos aprobados implementado; fuentes
  originales conservadas. En la ventana 2022–2023 se usaron 2.190 proxies de
  cobro y en 2025–2026, 2.190 marks exactos; el calentamiento se cuenta aparte.

## Resultados base

El [informe comparativo final](D:/Backtesting/outputs/study_655500e757a0c745e8332605/report.md)
reúne las cuatro carteras, hipótesis, siete sensibilidades por ventana y la
discusión crítica de ejecución. Su carpeta incluye CSV, JSON y el gráfico de
costos en PNG/SVG, con inventario y hashes verificados.

Cada fila parte de 10.000 USDT. Son precios observados con reglas y ejecución
prescritas; no una reconstrucción exacta del mercado histórico.

| Ventana | Cartera | Equity final USDT | Retorno neto | Fills |
|---|---|---:|---:|---:|
| 2022–2023 | Condicional | 10.111,8155 | 1,1182 % | 16 |
| 2022–2023 | Permanente | 10.205,4397 | 2,0544 % | 82 |
| 2025–2026 | Condicional | 10.000,0000 | 0 % | 0 |
| 2025–2026 | Permanente | 9.979,6703 | −0,2033 % | 8 |

Corridas verificadas, 43 archivos cada una:
`D:\Backtesting\outputs\run_8fb22fa8b377466cff981b99` y
`D:\Backtesting\outputs\run_0cb21afbec7cdba1e5848df6`.
Tardaron 310,14 y 268,14 segundos, con picos de memoria de aproximadamente
1,63 GB. Los fills económicos coinciden con los nativos. Los residuos contables
máximos observados al cierre son del orden de 10⁻²⁴ USDT, inferiores a la
tolerancia predefinida de 10⁻⁸ USDT.

La cartera permanente mantiene los filtros de base y riesgo; su nombre no
significa exposición continua. En 2025–2026 la condicional no operó, por lo que
su Sharpe es indefinido y ese cero no acredita un rendimiento de inversión.
Las dos aperturas de BTC de la permanente en esa ventana se deshicieron al
superar la tolerancia de desbalance del 0,5 % por el redondeo de cantidades
al paso permitido del contrato; no generaron cobros de funding.
Las siete sensibilidades priorizadas por ventana terminaron con estado
`complete`: 14 escenarios adicionales, ambos tipos de cartera en cada uno.
Se verificaron los dos índices y todos sus artefactos vinculados, sin
discrepancias: `robustness-25034b88ecfa92b9` (2022–2023) y
`robustness-c252528c4dd8d7a3` (2025–2026), dentro de `D:\Backtesting\outputs`.

En 2022–2023, costos dobles y triples dejan a la condicional sin operaciones;
la permanente obtiene 1,4747 % y 0,5430 %, respectivamente. Con futuros a
0,04 %, los retornos son 1,4677 % y 2,3437 %. Ninguna de estas variantes
respalda una ventaja del filtro frente a la permanente. El resultado no
monótono de costos de 2025–2026 se explica por cambios de cantidades y
aceptación de la cobertura; no compara una trayectoria de operaciones fija.

H1 muestra menor error descriptivo del EWMA en ambas ventanas. H2 es contrario
al criterio predefinido en 2022–2023 y no concluyente en 2025–2026, donde la
condicional no opera. La oportunidad media y el CAGR condicional son menores
en la ventana tardía; es una comparación de ventanas independientes, sin
atribución causal. Las demás sensibilidades del motor —AUM, slippage aislado,
demoras y parámetros del pronóstico— no se ejecutaron en este conjunto.

La revisión de la curva identificó una concentración relevante: el 24/03/2023,
durante la suspensión spot, el cambio diario de equity fue de 64,8580 USDT
para la condicional y 66,4975 para la permanente. Representa el 58,0 % y
32,4 % de sus respectivas ganancias finales. El cierre de futuros a las
11:59 dejó spot sin cobertura hasta las 14:00, tras 60 órdenes vencidas por
cartera. La auditoría reconstruye los 121 minutos de exposición direccional.

El [contraste con trades del episodio](../data/research/minute-download-20260918/outage-trades-validation.json)
confirma la referencia spot de 1.789,51 USDT a las 14:00:00.059. El precio
cambió 32 milisegundos después; el VWAP de los primeros cinco segundos fue
1.780,5749 USDT. Hay volumen observado y continuidad de IDs en las ventanas
cortas, pero no evidencia de prioridad en cola ni de que una orden real pudiera
enviarse y mantenerse durante la suspensión. Es un diagnóstico de sensibilidad
de ejecución: no modifica el baseline ni recalcula una rentabilidad anual.

## Evidencia que se conserva

- [Preparación de la descarga](../data/research/minute-download-20260918/preparation.json).
- [Recuperación de fuentes diarias](../data/research/minute-download-20260918/source-repair-audit.json).
- [Cobertura de ambas ventanas y conteos de funding](../data/research/minute-download-20260918/annual-data-validation.json).
- [Contraste de ejecución](../data/research/research-scenario-20260918/tick-minute-comparison.json).
- [Tiempo y memoria del piloto](../data/research/minute-download-20260918/runtime-2022-pilot.json).
- [Tiempo y memoria anual 2022–2023](../data/research/minute-download-20260918/runtime-2022-annual.json).
- [Tiempo y memoria anual 2025–2026](../data/research/minute-download-20260918/runtime-2025-annual.json).
- [Auditoría financiera independiente de las cuatro carteras](../data/research/minute-download-20260918/annual-economic-audit.json): equity final reconstruido, 106 fills contrastados con sus precios fuente, comisiones, redondeo adverso y tiempos de orden.
- [Trades del cierre durante la suspensión](../data/research/minute-download-20260918/outage-trades-validation.json): dos ZIP oficiales adicionales, 49,14 MB, conservados en D: para verificar el episodio que concentra la ganancia.
- [Verificación del piloto](../data/research/research-scenario-20260918/pilot-artifact-verification.json).
- [Auditoría de proxies](../data/research/research-scenario-20260918/funding-resolver-verification.json).
- [H1 preliminar, horizonte original](research/funding_h1_preliminary_20260918.md).
- [Fuentes y auditorías históricas](research/README.md).

La limpieza retiró las configuraciones de descarga masiva y de ventanas de
trades, el comando `prepare-window`, las proyecciones de plazos descartadas y
los borradores internos de implementación. Se consolidaron las guías.
La muestra, las fuentes que respaldan reglas/proxies, las pruebas del motor
y las salidas de validación se conservaron.

La última suite completa ejecutada pasó **302 pruebas** y Ruff. La revisión
independiente comprobó cobertura, causalidad, checkpoints, reglas de ejecución
y procedencia de los suplementos. Los scripts de auditoría se ejecutaron y
contrastaron de nuevo con la evidencia guardada; Ruff también aprobó esos
scripts. El código y el lock de dependencias conservan la identidad usada en
todos los escenarios. Las pruebas sintéticas permanecen separadas de los
resultados económicos con supuestos.

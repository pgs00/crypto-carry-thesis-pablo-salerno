# Escenario con precios observados y supuestos prescritos

Implementado el 18/09/2026 con aprobación del usuario. La ventana principal sigue siendo **2022-01-01 hasta antes de 2026-09-01**, BTCUSDT y ETHUSDT. Se conservan trades individuales, la espera de un segundo entre patas, ambas carteras y los controles de riesgo. No hace falta una API privada ni contactar soporte para ejecutar este escenario.

`configs/research.toml` habilita el escenario con el presupuesto inicial de 20 GB. `configs/research_full_d.toml` utiliza los mismos parámetros económicos y el presupuesto de 800 GB ya autorizado para los datos en D:. El modo original `strict_historical` sigue siendo el predeterminado de `configs/base.toml` y requiere reglas y marks históricos completos.

## Qué aproximaciones se aplican

- Se conserva cada mark de cobro exacto disponible. Si falta durante la ventana económica, se usa exclusivamente el cierre de la vela de mark de un minuto inmediatamente anterior, disponible al timestamp de cobro. Un candidato ausente, atrasado, futuro o inválido bloquea la corrida. Los originales no se sobrescriben.
- Los marks de funding ausentes en el calentamiento permanecen ausentes: antes del inicio no hay posición ni cobro. Se siguen exigiendo tasas, intervalos y calendario independiente verificados.
- Comisiones constantes: spot taker **0,10 %** y perpetuos taker **0,05 %**, sin BNB, referidos ni promociones. Slippage **1 bp por orden**. Es un modelo de costos prescrito; no afirma reconstruir las promociones ni todas las tarifas históricas VIP 0.
- Filtros, mantenimiento y cargos de liquidación se fijan como restricciones del modelo. La tabla completa y su declaración fechada en 2026 se guardan en `research_assumptions.json` dentro de cada corrida. BTC usa tick de futuros 0,1 y ETH 0,01; los mínimos de nocional prescritos son 10 USDT spot, 100 BTC futuros y 20 ETH futuros. El modelo aplica esos filtros también a reducciones; no reconstruye exenciones históricas.
- Mantenimiento: primer tramo hasta 50.000 USDT, BTC 0,4 % y ETH 0,65 %; segundo tramo hasta 100 millones, 1 % con deducciones continuas de 300 y 175 USDT. Liquidación: cargo prescrito de **1,25 % del nocional ejecutado más taker**. No son una certificación de las reglas de Binance.

Cada informe lleva `data_kind = "historical_assumptions"`. Incluye hashes, configuración efectiva, reglas prescritas y `funding_mark_audit.json`: observaciones validadas, observaciones consumidas por cada cartera, marks exactos, proxies y calentamiento sin mark requerido. Consumir una observación no implica haber mantenido una posición ni haber recibido un pago.

## Verificaciones realizadas

El resolver de producción se contrastó con las páginas API y los ZIP oficiales previamente descargados, volviendo a verificar sus hashes: **10.224 eventos económicos**, **6.214 marks exactos conservados** y **4.010 proxies causales resueltos**, 2.005 por activo. La evidencia está en `data/research/research-scenario-20260918/funding-resolver-verification.json`; esto prueba disponibilidad del proxy, no su igualdad con el mark de cobro ausente.

El piloto usa el intervalo fijado de antemano **2024-01-01 00:00–00:10 UTC**: 61.393 trades reales por cartera, 20 velas de mark entre los dos activos y calentamiento de funding. Se verificaron los hashes de origen y la continuidad efectiva de los IDs dentro del tramo, sin cambiar los datos de origen. Ambas carteras terminaron con seis fills nativos cada una y diferencia contable cero. La medición aislada del replay fue aproximadamente 3,3 y 3,0 segundos; la primera ejecución completa con informes tardó 11,35 segundos en este equipo. Diez minutos no validan una tenencia de 168 horas, rentabilidad, ni el tiempo y memoria de la historia completa.

El piloto de enero de 2024 utiliza marks de funding exactos. El camino de proxies se verificó por separado con todos los eventos ausentes y con pruebas de cobro, signos de stress, ausencia de anticipación y reanudación de checkpoints.

La batería completa pasó **235 pruebas**; Ruff comprobó código y formato. También se ejecutaron las dos carteras en los ocho escenarios del piloto (base más siete sensibilidades), se verificaron los hashes de sus artefactos y se regeneró el informe base sin diferencias. El detalle está en `data/research/research-scenario-20260918/pilot-artifact-verification.json`. Las sensibilidades de proxies y liquidación no validan su impacto económico en esta muestra corta: no hay marks de cobro ausentes ni liquidaciones en el tramo.

Reproducción del piloto local, desde el proyecto en C: y con la muestra original presente:

```powershell
& '.\.venv\Scripts\python.exe' data/research/research-scenario-20260918/prepare_pilot.py
& '.\.venv\Scripts\python.exe' -u -m crypto_carry backtest --config data/research/research-scenario-20260918/pilot.toml
& '.\.venv\Scripts\python.exe' data/research/research-scenario-20260918/verify_funding_proxy.py
```

## Cuando termine la descarga en D:

No iniciar otra descarga mientras la actual siga activa. Primero debe existir el manifiesto final de descarga; después, la normalización lee directamente los ZIP y produce Parquet/ZSTD. Conservar ZIP y Parquet consume espacio adicional.

```powershell
Set-Location 'C:\Users\pablo\Documentos\UCEMA\Tesina\Backtesting'
$configInvestigacion = (Resolve-Path '.\configs\research_full_d.toml').Path

# Normalizar y validar toda la ventana económica y el calentamiento requerido.
& '.\.venv\Scripts\python.exe' -u -m crypto_carry --root 'D:\Backtesting' validate-data --config $configInvestigacion --scope full
```

Continuar cuando el comando devuelva `status: complete`; ante `incomplete_data`, leer `D:\Backtesting\data\manifests\data_quality_report.md`. La aprobación de aproximaciones no elimina errores de hashes, calendarios, trades o cobertura de marks. `preflight` es sólo una comprobación de preparación de la descarga original y puede señalar archivos de 2020–2021 que no pertenecen a la ventana económica; no sustituye esta validación.

```powershell
# Ejecuta ambas carteras con la misma mecánica y conserva sus informes.
& '.\.venv\Scripts\python.exe' -u -m crypto_carry --root 'D:\Backtesting' backtest --config $configInvestigacion --strategy both
```

Para verificar nuevamente sin repetir la normalización, agregar `--skip-normalize` al comando `validate-data`. El comando `backtest` vuelve a validar sus inputs; nunca habilita una corrida incompleta con un flag de excepción.

## Sensibilidades predefinidas

El signo positivo del stress de funding empeora el flujo de un short: `proxy × (1 − signo(tasa) × bps / 10000)`. El negativo lo mejora. Sólo se modifican marks sustituidos; ambas carteras usan la misma regla. ±10 bps es un escenario de sensibilidad, **no una cota garantizada del error**.

```powershell
& '.\.venv\Scripts\python.exe' -u -m crypto_carry --root 'D:\Backtesting' robustness --config $configInvestigacion --scenario cost-2 --scenario cost-3 --scenario funding-proxy-plus-10 --scenario funding-proxy-minus-10 --scenario futures-fee-0p0004 --scenario maintenance-2 --scenario liquidation-fee-0p03
```

Este comando incluye el caso base y corre ambas carteras en cada escenario. Cada sensibilidad cambia un factor; duplicar mantenimiento duplica tasas y deducciones, conservando continuidad. El escenario de liquidación usa 3 %. Si no hay liquidaciones o proxies en un tramo, esas sensibilidades pueden no producir diferencias; eso no prueba que el supuesto sea irrelevante en toda la historia. No elegir retrospectivamente la variante más rentable como nuevo resultado principal.

## Qué falta para cerrar el backtesting de la tesis

1. **Completar descarga, normalización y validación de la ventana completa.** La existencia de los archivos no basta para certificar su contenido.
2. **Resolver las incidencias restantes de datos.** La muestra completa del 01/01/2024 todavía marca discontinuidades de IDs en futuros de ambos activos. El piloto no las ignora: utiliza otro alcance explícito con continuidad comprobada. La auditoría de marks también encontró 15 minutos sin recuperar en las fuentes consultadas (BTC: 2 el 12/08/2024; ETH: 10 el 12/07/2022, 1 el 13/07/2022 y 2 el 12/08/2024). Ninguno afecta los 4.010 proxies anteriores, pero la cobertura de riesgo por minuto debe resolverse antes de una corrida completa. No se imputaron velas de riesgo ni se aprobaron huecos de operaciones.
3. **Ejecutar una muestra más amplia, de al menos una semana**, con cobros reales, renovaciones y cierres, y medir tiempo y memoria. Descargar todo en un día no asegura procesarlo y simular todos los escenarios en ese mismo plazo.
4. **Correr las dos carteras y las sensibilidades**, revisar conciliación, órdenes rechazadas, exposición sin cobertura, margen, liquidaciones y resultados por período. Congelar el caso base antes de ajustes posteriores y distinguir esos ajustes como exploratorios.
5. **Cerrar tablas, gráficos y redacción metodológica.** El H1 sobre tasas ya se calculó por separado; H2/H3 económicos dependen de las corridas de cartera completas. Este escenario permite estudiar el modelo con supuestos declarados, pero no valida por sí solo invertir capital real.

No queda pendiente una confirmación para los supuestos implementados. Cualquier cambio de granularidad de ejecución, tratamiento de huecos de riesgo o recorte de la ventana principal sería una decisión metodológica adicional.

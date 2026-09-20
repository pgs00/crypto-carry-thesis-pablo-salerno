# Cartera continua y sensibilidad de marks

Esta extensión conserva el modelo `next_minute_vwap`, sizing conjunto, señales
con velas cerradas y los parámetros económicos actuales. Ejecuta cuatro carteras
independientes: condicional y permanente, cada una con los dos métodos siguientes,
desde el **01/01/2022 hasta el 31/08/2026 UTC**. Cada cartera comienza con
10.000 USDT y continúa sin reiniciar capital ni posiciones al cambiar de año.
Las corridas y el paquete de las ventanas anuales anteriores se conservan.

Las cuatro carteras ya terminaron: consultar el
[reporte continuo con evidencia verificada](../data/research/continuous-marks-20260919/README.md).
El estudio local es `continuous_marks_b417d512a416058238193c79`.

## Opción explícita

`mark_gap_method = "strict"` es el valor predeterminado. La validación original
continúa bloqueada por los [15 minutos documentados](../data/research/continuous-preparation-20260919/unresolved_mark_minutes.csv).
La lista está fijada en código y contrastada con ese CSV mediante una prueba;
editar el CSV no autoriza nuevos rellenos.

- **`futures_scaled` (principal, fijado antes de observar resultados):**
  `mark_close[t] = futures_close[t] × mark_close[s] / futures_close[s]`.
  `s` es el último minuto oficial anterior al hueco. Se mantiene el mismo
  ancla durante todos sus minutos consecutivos. Los OHLC se escalan por ese
  factor; no se agrega nuevamente el basis.
- **`last_official` (sensibilidad):** todos los OHLC estimados mantienen
  constante el cierre oficial de `s` durante el mismo hueco.

Los timestamps documentados son aperturas. La estimación de la vela de `t`
está disponible en `t + 1 minuto`, cuando cierra el futuro necesario. El ancla
también debe ser oficial y estar cerrada. No se consultan precios posteriores.
Si falta un dato necesario, hay otra omisión, contradicción o hash incorrecto,
se conserva el bloqueo. Para el método constante no se necesita el futuro para
calcular el mark, pero la validación del motor sigue exigiendo los precios de
ejecución completos.

La aproximación de funding `previous_closed_1m` permanece igual: estos 15 huecos
son una cuestión distinta de los 2.005 marks de cobro ausentes por activo.

## Ejecutar las cuatro carteras

Con la descarga continua ya normalizada, desde la raíz del repositorio:

```powershell
$configContinuo = (Resolve-Path '.\configs\download_minutes_2022_2026_d.toml').Path
& '.\.venv\Scripts\python.exe' -u -m crypto_carry --root 'D:\Backtesting' continuous-mark-study --config $configContinuo
```

El comando valida los originales en una copia separada de sus manifiestos,
prepara y verifica ambas capas derivadas y ejecuta una cartera a la vez.
Durante cada replay imprime aproximadamente cada 30 segundos su porcentaje,
fecha UTC alcanzada y cantidad de fills. La validación previa y la generación
de informes tienen sus propios mensajes de etapa, sin porcentaje temporal.

Las capas se guardan bajo
`data/minutes/2022_2026_continuous/derived_marks/<método>` dentro del root local.
Sólo se crean tres particiones nuevas de mark por método; las otras 797 entradas
del manifiesto referencian los originales. No se duplican todos los precios y
funding. Cada fila estimada indica método, ancla y fuente derivada, y
`manifests/mark_gap_audit.json` incluye los valores fuente y los hashes.

La cobertura operativa se informa como `complete` acompañada de
`coverage_kind = "completed_with_approximations"`; no se certifica como
reconstrucción histórica exacta. El validador recalcula las 15 estimaciones y
contrasta todas las filas restantes de las particiones afectadas con el original.
Un replay sin la opción explícita rechaza estas capas.

El estudio se guarda en `outputs/continuous_marks_<id>/mark_gap_report.md` y
las cuatro corridas en carpetas inmutables `outputs/run_<id>`. El índice permite
reutilizar carteras terminadas y verificadas al repetir el mismo comando con
el mismo código, datos y parámetros. Una cartera interrumpida antes de guardar
su resultado debe volver a ejecutarse; no se inventa un cierre parcial.

## Preparar o validar un método por separado

```powershell
& '.\.venv\Scripts\python.exe' -m crypto_carry --root 'D:\Backtesting' prepare-mark-gaps --config $configContinuo --method futures_scaled
$configMarks = 'D:\Backtesting\data\minutes\2022_2026_continuous\derived_marks\futures_scaled\manifests\effective_config.toml'
& '.\.venv\Scripts\python.exe' -m crypto_carry --root 'D:\Backtesting' validate-data --config $configMarks --scope full --skip-normalize
```

Para la sensibilidad usar `last_official` en ambos lugares. El preparador no
ejecuta backtests ni certifica por sí solo toda la cobertura. No normalizar otra
vez sobre una capa derivada: se utiliza `--skip-normalize`.

## Evidencia y límites

- `comparison.csv` y `period_metrics.csv`: rentabilidad y drawdown diario,
  totales y por régimen/año de las mismas carteras continuas.
- `gap_risk_checks.csv`: posiciones antes de cada control, colateral, balance,
  mantenimiento, ratio, precio y distancia a liquidación, estado antes/después
  y eventos realmente emitidos. Incluye el ancla y el primer mark recuperado.
- `gap_positions_summary.csv`: posiciones y controles agrupados por hueco,
  método y estrategia.
- `method_differences.json`: contraste de fills, señales, equity diario,
  eventos de riesgo y observaciones de funding entre métodos.
- `study_manifest.json` y su SHA-256: integridad del estudio y referencias a
  las cuatro corridas, con sus manifiestos originales y configuración efectiva.

Para verificar los archivos originales, recalcular las aproximaciones, contrastar
los parámetros de las cuatro carteras, recomputar retorno/drawdown desde equity
diario y comprobar las posiciones y el funding, sin repetir los backtests:

```powershell
& '.\.venv\Scripts\python.exe' '.\scripts\verify_continuous_marks.py' --root 'D:\Backtesting' --study 'D:\Backtesting\outputs\continuous_marks_<id>'
```

El identificador concreto aparece al finalizar la ejecución y en su índice.
Con `--portfolio-output <archivo-nuevo.csv>` se exportan además las posiciones
de ambos activos en los 13 instantes UTC distintos con algún mark faltante.
Se reconstruyen desde el ledger guardado y los marks disponibles, y se contrastan
con los controles registrados durante el replay para los activos afectados.
El CSV distingue los marks oficiales de los estimados y conserva los saldos
residuales de spot aun cuando el short sea cero. `--output <archivo.json>` guarda
el resultado del verificador; usar destinos nuevos para conservar la evidencia.

El método principal supone constante la relación mark/futuro durante el hueco.
El alternativo mantiene el mark inmóvil. Ambos pueden alterar la valoración y
el cruce de umbrales de margen; ninguno recupera el mark oficial desconocido.
Se mantienen los controles preventivos y de liquidación existentes, evaluados
con marks cerrados. El OHLC estimado no aporta un recorrido intraminuto.
El drawdown principal usa equity diario, conforme a las corridas previas.
Las reglas y comisiones prescritas mantienen sus limitaciones anteriores.
No se elige entre métodos según cuál produzca mayor rentabilidad.

Los datos masivos siguen locales y excluidos de Git. Esta extensión no modifica
el paquete sellado de la Entrega 3 ni su evidencia histórica.

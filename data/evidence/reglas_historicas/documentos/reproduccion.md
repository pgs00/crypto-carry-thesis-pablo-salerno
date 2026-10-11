# Reproducción de la tanda desde un paquete sellado

La utilidad `scripts/reproduce_historical_rules_sensitivity.py` prepara y, salvo
`--prepare-only`, ejecuta el launcher autenticado del paquete fuente. Está validada
con fixtures y `--help`; no se ejecutó una segunda tanda real durante su creación.

Requiere Python y las dependencias exactas de la auditoría BASE_E3. Se compara
`platform.python_version()` (incluida la revisión patch) con el campo `python`
del manifiesto de **cada** BASE, y se registran las versiones en la auditoría
fresca. Un exit 0 del subprocess no basta: sus indicadores de igualdad de datos,
dependencias y Python deben ser explícitamente `true`. Además son
indispensables, fuera del paquete portable:

- El árbol de datos originales, procesados y manifiestos bajo `--data-root`, con
  los hashes de `verificacion_base_previa.json`; incluye
  `data/minutes/2022_2026_continuous/derived_marks/futures_scaled` y sus antecedentes.
- Ambas corridas completas en `--data-root/outputs/run_ad71d751b20623006c195ff3`
  y `--data-root/outputs/run_dfea4b7ac1475668d5968c97`.
- El paquete fuente terminado y sellado mediante `manifiesto_paquete.json` y
  `manifiesto_paquete.sha256`, con su verificador en
  `herramientas/verify_rules_sensitivity_package.py`, `codigo_base/` y
  `codigo_ejecutado/` completos.

Verificar offline el informe portable no aporta esos datos masivos ni permite
reconstruirlos. La utilidad no descarga datos y no los duplica por escenario.
No admite omitir la comprobación del paquete, reanudar un destino previo ni
sobrescribir archivos. El padre del destino debe existir y el destino debe estar
fuera del paquete fuente.

Una comprobación completa que sólo prepara una carpeta nueva, sin backtests:

```powershell
.venv/Scripts/python.exe -B -X utf8 scripts/reproduce_historical_rules_sensitivity.py `
  --source-package entregas/entrega_4/reglas_historicas/20260925T005436Z `
  --destination D:/Backtesting/outputs/E4_reglas_preparacion_nueva `
  --data-root D:/Backtesting --workers 2 --prepare-only
```

Para volver a ejecutar las diez variantes/carteras y reutilizar las dos bases,
seleccionar **otra carpeta que todavía no exista** y omitir `--prepare-only`:

```powershell
.venv/Scripts/python.exe -B -X utf8 scripts/reproduce_historical_rules_sensitivity.py `
  --source-package entregas/entrega_4/reglas_historicas/20260925T005436Z `
  --destination D:/Backtesting/outputs/E4_reglas_reproduccion_nueva `
  --data-root D:/Backtesting --workers 2
```

Ambos comandos rechazan un paquete todavía abierto. Se ofrecen como comandos
para usar después del sellado; no certifican una reproducción ya ejecutada.
`--workers` acepta 1–4; los datos son compartidos, mientras cada proceso mantiene
su cartera y resultados independientes.

Antes de crear destino se ejecuta el verificador portable, se recalculan los
hashes de entrada mediante `input_hashes` del motor congelado, se verifica el
entorno y se contrastan los originales BASE y su `code_files` con `codigo_base`.
Los imports de configuración, replay y reporting deben resolver a
`codigo_ejecutado/src`; no se usa inadvertidamente el motor actual del checkout.

Sólo se copian los cuatro prerequisitos que exige el runner: protocolo,
auditoría BASE previa, comparación con extensión apagada y resultado de
publicación histórica. Sus bytes, fechas y procedencia internas permanecen
intactos. `reproduccion_preparacion.json` agrega la comprobación nueva de datos,
dependencias y fuentes, junto con el comando exacto y su `PYTHONPATH`.
Se prefiere `herramientas/run_historical_rules_sensitivity.py`, incluido y
autenticado por SHA256 en el manifiesto. Si ese helper está presente pero no
autenticado, la preparación falla. Sólo si está ausente se selecciona el
fallback `codigo_ejecutado/scripts/run_historical_rules_sensitivity.py`, también
autenticado. La auditoría registra ruta, SHA256 y selección en `runner_identity`.
Ambos se lanzan con `-B -X utf8`, cwd `codigo_ejecutado` y su `src` en PYTHONPATH;
el motor y las configuraciones proceden del mismo snapshot congelado.

La tanda entregada usó el launcher original conservado en `codigo_ejecutado`.
Una revisión posterior corrigió el launcher raíz y el helper de `herramientas`
para guardar también trayectorias `insolvent` que alcanzan `end-1`, manteniendo
la conciliación y su estado real. El launcher original sólo admitía `complete`.
No hubo corridas reales insolventes en esta tanda: el cambio posterior se validó
con dobles controlados de orquestación y no modifica sus resultados publicados.
El helper corregido resuelve el proyecto desde el módulo Config importado,
permitiendo su ubicación fuera del snapshot sin alterar éste. El fallback
identificado conserva el comportamiento original; para reproducir el soporte
corregido debe estar presente el helper autenticado.

La ejecución completa deja `reproduccion_ejecucion.json` con su código de salida;
un código distinto de cero se conserva como fallo. La carpeta nueva contiene
corridas y evidencia de ejecución: esta utilidad no genera automáticamente el
informe comparativo ni sella un segundo paquete editorial. Esos pasos corresponden
a las herramientas de informe y verificación del paquete fuente.

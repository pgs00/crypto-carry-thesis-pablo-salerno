# Riesgo intradía: plan de ejecución

**Objetivo:** reconstruir y conciliar riesgo de las dos BASE y, si las mismas fuentes alcanzan, las dos MARGEN_2X, sin nuevas trayectorias económicas.

**Arquitectura:** módulos de posprocesamiento separados para fuentes/estados, aritmética, construcción de evidencia y presentación/verificación. Estado contable Decimal en eventos; cálculo vectorizado por bloques de precios, con conciliación al límite monetario original de 1E-8 USDT. Las series completas comprimidas serán locales; el paquete compacto distinguirá expresamente el alcance de su verificación.

**Tecnología:** Python del proyecto, PyArrow/NumPy, CSV/JSON/Parquet, Matplotlib, HTML sin dependencias remotas.

**Especificación:** [encargo íntegro](encargo_original.md), [protocolo](protocolo.md).

## Restricciones globales

No modificar motor, carteras, configuraciones, snapshots o paquetes previos. No commit, push ni índice. No descargas de precios. No replay salvo carencia indispensable demostrada y documentada antes. No reimplementar H2/exposición; reutilizar semántica y tablas verificadas. Las entradas tienen huellas iniciales en estado_inicial.json.

## Trabajo y archivos

- [ ] Auditar registros y precios locales, verificar paquetes de entrada y fijar protocolo antes de resultados nuevos.
- [ ] `scripts/intraday_risk_math.py`, `tests/test_intraday_risk_math.py`: valuación, drawdown con pico inicial, márgenes/transferencias/necesidades simultáneas y proxy causal. Pruebas manuales independientes primero (100 → 80 → 101; aporte interno; cortos pareados; umbrales).
- [ ] `scripts/intraday_risk_sources.py`, `tests/test_intraday_risk_sources.py`: estados pre/post en orden físico, precios disponibles y huellas, conciliación diaria y disponibilidad de efectivo. Medir ventana corta antes de muestra completa.
- [ ] `scripts/build_intraday_risk.py`: reconstrucción mensual compartiendo precios para cuatro carteras, serie local completa y tablas de riesgo/episodios; sólo proceder si conciliaciones no tienen diferencias inexplicadas.
- [ ] `scripts/intraday_risk_report.py`: resumen anual reutilizado, Markdown/HTML y figuras; especificar origen y clase de cada cifra.
- [ ] `scripts/verify_intraday_risk.py`, `tests/test_intraday_risk_verifier.py`: integridad/aritmética compacta separada de reconstrucción completa local; corrupción y copia trasladada de sólo lectura.
- [ ] Revisión independiente final, pruebas pertinentes, Ruff y preservación de todas las entradas e índice. Registrar comandos y límites reales.

## Interfaces

Fuentes producen grilla ordenada `(time_ns, sequence)` y arrays de saldos/posiciones/precios con disponibilidad y antigüedad. Aritmética devuelve patrimonio, DD y métricas de margen con ND explícitos. Constructor produce series Parquet locales, tablas CSV, procedencia y conciliaciones. Verificador compacto autentica esas tablas y reproduce su aritmética; verificador completo vuelve a leer estados/precios de rutas explícitas y contrasta la serie/métricas. Presentación consume únicamente tablas verificadas.

## Focos de revisión

Orden pre/post simultáneo y datos recién disponibles; cierres diarios un nanosegundo antes del límite; saldo de margen no positivo y umbrales estrictos; caja comprometida compartida; DD con huecos/precios arrastrados y separación del proxy de suspensión. Cada foco tendrá prueba de comportamiento, no búsquedas de texto.


La fuente spot se actualiza sólo con volumen positivo y disponibilidad causal; el mark de riesgo conserva su fuente y método. Un cierre diario a `23:59:59.999999999` usa normalmente la vela de las 23:58 disponible a las 23:59. No se adelanta la vela de las 23:59. La auditoría del ledger debe acreditar los compromisos antes de declarar caja neta redistribuible; si no puede hacerlo, la disponibilidad neta y el faltante externo exactos quedan ND.

La necesidad preventiva informa el ínfimo y una bandera de frontera estricta: `x > M(q*m)/0.50-B` y `x >= q*m*0.15+M(q*m*1.15)-B`, además de `x>=0`. No se inventa un quantum de transferencia para esconder la desigualdad estricta.

## Decisiones operativas

Se ejecuta el encargo ya autorizado, sin pedir otra aprobación de un plan. Se trabaja en la rama actual, sin worktree ni commits porque el usuario prohíbe cambios de índice y exige conservar la evidencia. Las habilidades de planificación y TDD se aplican a la implementación; sus pasos genéricos de commit no se ejecutan.

Sólo el protocolo se sella antes de la reconstrucción completa mediante SHA256 y timestamp UTC. El plan, el feedback y la [matriz de cobertura](matriz_cobertura_feedback.csv) describen alcance y estado de trabajo. La comparación remunerada y las nuevas trayectorias hipotéticas permanecen pendientes.

"""Generate a field-level dictionary for the portable presentation tables."""

import argparse
import csv
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
DEFINITIONS = {}


def define(names, unit, description):
    for name in names.split():
        DEFINITIONS[name] = (unit, description)


define(
    "ventana window",
    "identificador",
    "early=2022–2023; late=2025–2026; early_vs_late=comparación independiente.",
)
define(
    "estrategia strategy",
    "identificador",
    "conditional=condicional; permanent=permanente; COMMON=serie común; conditional_vs_permanent=comparación.",
)
define("run_id", "identificador", "Corrida persistida; no identifica una simulación nueva.")
define(
    "simbolo symbol activos_cerrados",
    "identificador",
    "BTCUSDT o ETHUSDT; PORTFOLIO=suma de activos; listas separadas por punto y coma.",
)
define(
    "inicio_utc start fin_exclusivo_utc end instante_utc fecha_utc",
    "UTC",
    "Fecha ISO 8601; inicio inclusivo y fin exclusivo; instante diario conserva nanosegundos.",
)
define(
    "time_ns",
    "nanosegundos UTC",
    "Timestamp entero desde Unix epoch; no convertir a punto flotante.",
)
define(
    "capital_inicial_usdt capital_usdt",
    "USDT",
    "Capital inicial independiente por estrategia y ventana.",
)
define(
    "equity_final_usdt final_equity_usdt equity_usdt",
    "USDT",
    "Patrimonio valorizado; incluye posiciones abiertas, sin cierre terminal ni fees hipotéticos.",
)
define(
    "retorno_neto net_return",
    "proporción",
    "Equity final/capital inicial−1. Binary64 persistido; 1 equivale a 100%.",
)
define(
    "cagr early_conditional_cagr late_conditional_cagr",
    "proporción/año",
    "Crecimiento anual compuesto, año de 365 días; dos ventanas independientes de 365 días.",
)
define(
    "sharpe conditional_sharpe permanent_sharpe",
    "razón",
    "Media de retornos diarios/desvío muestral(ddof=1)×raíz(365); tasa libre de riesgo cero; vacío si indefinido.",
)
define(
    "drawdown_diario max_drawdown",
    "proporción con signo",
    "Mínimo equity/máximo acumulado−1, incluyendo capital inicial. No es drawdown intradiario.",
)
define(
    "aperturas_completas openings",
    "aperturas",
    "Transiciones opening_complete: carry plenamente abierto; no equivale a intentos ni ciclos cerrados.",
)
define(
    "ciclos_cerrados complete_cycles",
    "ciclos",
    "Carry abierto completamente y luego cerrado; excluye posiciones abiertas al corte.",
)
define(
    "intentos_orden_fallidos failed_attempts",
    "órdenes/intentos",
    "Máximo entre órdenes expired/rejected/timeout y eventos attempt_failed; incluye reintentos de cierre.",
)
define(
    "aperturas_fallidas failed_cycles",
    "ciclos fallidos",
    "Intentos de apertura desarmados sin llegar a carry completo.",
)
define(
    "intentos_apertura opening_attempts",
    "intentos",
    "Aperturas iniciadas, incluidas las que fallaron antes de completar ambas patas.",
)
define(
    "fills native_fills",
    "fills",
    "Eventos de ejecución; un fill no es un ciclo. native_fills cuenta eventos de NautilusTrader.",
)
define(
    "fills_parciales partial_fills",
    "fills",
    "Eventos que ejecutaron menos que la cantidad solicitada.",
)
define(
    "orders ordenes_cierre",
    "órdenes",
    "Órdenes enviadas; ordenes_cierre restringe a desarmes del episodio.",
)
define(
    "closes",
    "intentos de cierre",
    "Eventos de inicio de cierre del resumen de ejecución, no necesariamente ciclos completados.",
)
define(
    "cagr_motivo_nulo sharpe_motivo_nulo motivo_fraccion_no_aplicable",
    "texto",
    "Razón de un dato indefinido; vacío cuando corresponde un valor. ND se usa sólo en la presentación.",
)
define(
    "spot_usdt spot_pnl_usdt",
    "USDT",
    "P&L spot con signo, incluye valorización del inventario; comisiones separadas.",
)
define(
    "futuros_usdt futures_pnl_usdt",
    "USDT",
    "P&L de futuros realizado más no realizado al mark de cierre, con signo.",
)
define("funding_usdt", "USDT", "Funding neto cobrado o pagado; signo positivo representa ingreso.")
define("comisiones_usdt fees_usdt", "USDT", "Comisiones con signo en P&L/anexo: costo negativo.")
define(
    "fees_costo_positivo_usdt",
    "USDT",
    "Magnitud positiva del costo de comisiones sólo en la tabla del episodio.",
)
define(
    "liquidaciones_usdt liquidation_fees_usdt",
    "USDT",
    "Cargo de liquidación con signo; cero si no hubo cargo.",
)
define(
    "slippage_informativo_usdt slippage_informational_usdt",
    "USDT",
    "Atribución informativa del slippage ya contenido en los precios; no restar otra vez.",
)
define(
    "slippage_resta_adicional",
    "booleano",
    "False: no se resta un segundo cargo de slippage al sumar componentes; sí está incluido en precios.",
)
define("precios_usdt", "USDT", "P&L spot más futuros. No se interpreta como funding ni basis puro.")
define(
    "neto_componentes_usdt",
    "USDT",
    "Spot+futuros+funding+comisiones+liquidaciones, sin segunda resta del slippage.",
)
define(
    "beneficio_equity_usdt beneficio_anual_usdt",
    "USDT",
    "Equity final menos capital inicial, conservando precisión Decimal.",
)
define(
    "residuo_conciliacion_usdt reconciliation_residual_usdt",
    "USDT",
    "Equity final−capital inicial−suma de componentes. Tolerancia contable 1e−8 USDT.",
)
define(
    "cambio_equity_diario_usdt",
    "USDT",
    "Equity al cierre UTC del 24/03/2023 menos cierre del día anterior.",
)
define(
    "fraccion_beneficio_anual",
    "proporción",
    "Cambio de equity diario/beneficio anual, Decimal 60; vacío si beneficio anual no positivo; no es atribución causal.",
)
define(
    "minutos_activo_sin_cobertura",
    "minutos-activo",
    "Suma por símbolo de segundos sin cobertura/60; 242 puede representar 121 por cada uno de dos activos.",
)
define(
    "cierres_futuros_utc cierres_spot_utc",
    "UTC",
    "Timestamp del fill de cierre por activo, formato símbolo=ISO8601; pares separados por punto y coma.",
)
define(
    "precios_futuros_usdt precios_spot_usdt",
    "USDT/unidad de activo",
    "Precio de fill por activo, pares símbolo=precio separados por punto y coma.",
)
define(
    "retorno_diario_decimal",
    "proporción/día",
    "Equity_t/equity_anterior−1, Decimal 60. Primer denominador=capital inicial.",
)
define(
    "retorno_diario_metricas",
    "proporción/día",
    "Mismo cociente en binary64, convención de las métricas persistidas; diferencias de representación no se ocultan.",
)
define(
    "capital_deployed_daily_avg_usdt capital_deployed_daily_max_usdt",
    "USDT",
    "Media o máximo de cortes diarios de spot valorizado+garantía segregada, sumados por activo; puede superar el capital inicial.",
)
define(
    "covered_asset_seconds unhedged_asset_seconds dust_asset_seconds",
    "segundos-activo",
    "Duración acumulada por símbolo: carry cubierto, exposición sin cobertura o sólo polvo residual, respectivamente.",
)
define("tipo", "categoría", "exposición o diagnóstico.")
define(
    "medida",
    "identificador",
    "Medida de exposición o código de filtro; ver convenciones.md para alcance y denominadores.",
)
define(
    "valor",
    "según unidad o parámetro",
    "Valor original o derivación indicada por medida/parámetro; nunca convertir vacío en cero.",
)
define(
    "unidad unidad_denominador",
    "texto",
    "Unidad explícita del numerador o denominador; horas-activo suma los símbolos.",
)
define(
    "denominador",
    "evaluaciones",
    "Observaciones de entrada por activo y estrategia, 1095 por ventana, derivadas del resumen de auditoría; vacío para exposición.",
)
define(
    "alcance",
    "categoría",
    "simultaneous_filter_states, sequential_first_rejection o theoretical_not_applied; los grupos no se suman entre sí.",
)
define("periodo", "categoría", "económico o calentamiento; el calentamiento no genera P&L.")
define(
    "metodo",
    "categoría",
    "exact=mark de settlement observado; previous_closed_1m=proxy causal; not_required_before_start=calentamiento sin mark necesario.",
)
define(
    "eventos_unicos",
    "observaciones de mercado",
    "Deduplicación por (symbol,funding_time) entre estrategias; no significa cantidad de pagos.",
)
define(
    "parametro",
    "identificador",
    "Nombre de la configuración efectiva; se conservan también campos heredados inactivos para el escenario.",
)
define(
    "herramienta version",
    "texto",
    "Herramienta y versión registrada por la corrida, no supuesta a partir del entorno actual.",
)
define(
    "hypothesis",
    "identificador",
    "H1=error de pronóstico; H2=CAGR y Sharpe; H3=oportunidad y rendimiento entre ventanas.",
)
define(
    "measure",
    "identificador",
    "forecast_mae; conditional_cagr_and_relative_sharpe; opportunity_mean.",
)
define(
    "value",
    "proporción",
    "H1=MAE EWMA; H2=CAGR condicional; H3=oportunidad media tardía. Funding y MAE son acumulados al horizonte de 168h.",
)
define(
    "comparator",
    "proporción",
    "H1=MAE sin cambio; H2=CAGR permanente; H3=oportunidad media temprana.",
)
define(
    "criterion result",
    "texto",
    "Criterio vigente y evaluación descriptiva: favorable, contraria o no_concluyente; no es test de significancia.",
)
define(
    "observations",
    "observaciones",
    "Basis: pares de mercado únicos; H1: señales válidas agregadas; H2: días; H3: días temprano/tardío.",
)
define(
    "excluded",
    "observaciones",
    "H1: señales fuera del horizonte completo; H3: días excluidos temprano/tardío; vacío si no aplica.",
)
define(
    "early_valid_days",
    "días",
    "Días válidos tempranos para H3; cobertura tardía figura en observations.",
)
define(
    "period",
    "categoría",
    "full=ventana completa; independent_365_day_windows=H3 entre ventanas independientes.",
)
define(
    "scenario",
    "identificador",
    "vwap_joint principal; las otras variantes son antecedentes, no una selección por rendimiento.",
)
define("status", "categoría", "Estado de la corrida; complete en el subconjunto utilizado.")
define(
    "original_source_covered evaluated verified",
    "observaciones",
    "Casos con fuente original, evaluados y verificados bajo la tolerancia de auditoría, respectivamente.",
)
define(
    "discrepancies decision_discrepancies source_to_normalized_discrepancies normalized_to_signal_discrepancies classification_discrepancies",
    "discrepancias",
    "Conteos por tipo de contraste de la auditoría existente; cero significa sin discrepancias bajo su tolerancia.",
)
define(
    "max_absolute_error",
    "basis decimal",
    "Máxima diferencia absoluta en la cadena original/normalizado/señal/decisión; tolerancia 1e−12.",
)
define(
    "nonzero_rounding_differences",
    "comparaciones",
    "Diferencias no nulas dentro de tolerancia entre representaciones; varias por observación, no discrepancias económicas.",
)
define(
    "minimum median maximum",
    "basis decimal",
    "Distribución (perpetuo−spot)/spot en los instantes de decisión auditados.",
)
define(
    "negative zero positive_eligible eligible_inclusive above_max",
    "observaciones",
    "Basis <0, =0, (0;0.005], [0;0.005], >0.005, respectivamente; cero sí es elegible.",
)
define(
    "id cambio diseño_anterior implementacion_utilizada motivo implicacion fuente_verificable",
    "texto",
    "Matriz de cambios: identifica diseño anterior, implementación posterior, motivo, consecuencia y fuentes relativas verificables.",
)
define(
    "id_cifra archivo_presentado seleccion_presentada campo_presentado valor_original archivo_fuente campo_fuente filtro_fuente calculo",
    "trazabilidad",
    "Identificador, destino, selección, valor, origen, campo y fórmula de la cifra; rutas relativas a la raíz del paquete.",
)
define(
    "control contexto obtenido esperado diferencia tolerancia aprobado",
    "control",
    "Comparación reproducida; diferencia absoluta y tolerancia en unidades del campo; aprobado=True sólo si diferencia<=tolerancia.",
)
define(
    "referencia url procedencia_entrega_2 procedencia_entrega_1 nota_consolidacion",
    "texto bibliográfico",
    "Referencia heredada y párrafo E1/E2; no se verificó ni amplió bibliografía mediante investigación externa.",
)


def generate(destination):
    rows = []
    paths = sorted((PACKAGE / "tablas").glob("*.csv")) + [
        PACKAGE / "datos/equity_diaria.csv",
        PACKAGE / "fuentes_de_cifras.csv",
        PACKAGE / "verificaciones_numericas.csv",
        PACKAGE / "antecedentes/bibliografia_consolidada.csv",
    ]
    for path in paths:
        with path.open(encoding="utf-8", newline="") as stream:
            fields = next(csv.reader(stream))
        for field in fields:
            unit, description = DEFINITIONS[field]
            rows.append(
                dict(
                    archivo=path.relative_to(PACKAGE).as_posix(),
                    campo=field,
                    unidad=unit,
                    definicion=description,
                )
            )
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / "diccionario_campos.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["archivo", "campo", "unidad", "definicion"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Dictionary: {len(rows)} fields")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destino", type=Path, default=PACKAGE)
    generate(parser.parse_args().destino)

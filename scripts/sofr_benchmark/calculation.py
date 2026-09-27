"""Approved, finite SOFR postprocessing; no strategy or engine imports."""

from datetime import date
from decimal import Decimal as D
from decimal import localcontext
from pathlib import Path

from scripts.return_capital.common import close, number, read_csv, read_json, sha256, truth

from .accrual import build_account, index_checks
from .calendar import calendar_rows, parse_sifma, validate_coverage
from .comparison import align_daily, compare_periods

PREVIOUS_HASH = "0163cf7622d929c06773700f50d13b2e808afee85a6cf85e48d45dcac03af12b"
PROPOSAL_HASH = "4fbb43c952d8e53a31a023ffbfc112fecbc93e0368c7c2835061fcfdf2e0e312"
CONTRACT = dict(
    status="aprobado",
    proposal_id="SOFR_BRUTO_ACT360_USD_PARIDAD_USDT_20260927",
    original_proposal_sha256=PROPOSAL_HASH,
    original_package_manifest_sha256=PREVIOUS_HASH,
    capital="10000",
    currency="USD",
    USDT_USD_nominal_parity="1",
    accrual_day_basis=360,
    cagr_day_basis=365,
    start_inclusive="2022-01-01",
    end_exclusive="2026-09-01",
    index_rounding_quantum="0.00000001",
    decimal_precision=50,
    monetary_tolerance="1E-8",
)
COPY_TABLES = ("metricas_reutilizadas.csv", "diario_reutilizado.csv", "h2_reutilizado.csv")
EXCEPTIONS = {
    "2023-04-07": (False, "nyfed_excepcion_2023.html", None),
    "2026-04-03": (False, "nyfed_excepcion_2026.html", None),
    "2025-01-09": (True, "nyfed_carter_2025.html", "early_close"),
}


def authenticate_inputs(research, documents, reused, source_manifest=None):
    approval = read_json(documents / "aprobacion.json")
    if any(approval.get(k) != v for k, v in CONTRACT.items()):
        raise ValueError("Approval differs from the authorized contract")
    if sha256(documents / "origen_ficha_benchmark.json") != PROPOSAL_HASH:
        raise ValueError("Original proposal hash mismatch")
    prior_manifest = source_manifest or reused / "manifiesto_previo.json"
    if sha256(prior_manifest) != PREVIOUS_HASH:
        raise ValueError("Prior sealed manifest hash mismatch")
    prior = {r["path"]: r for r in read_json(prior_manifest)["members"]}
    for original, copy in [("tablas/" + name, reused / name) for name in COPY_TABLES] + [
        ("fuentes_publicas/sofr_serie.json", research / "sofr_serie.json"),
        ("fuentes_publicas/sofr_metodologia.html", research / "sofr_metodologia.html"),
        ("documentos/propuesta_benchmark.md", documents / "origen_propuesta_benchmark.md"),
    ]:
        if sha256(copy) != prior[original]["sha256"]:
            raise ValueError("Reused original has changed: " + original)
    registry = read_json(research / "fuentes.json")
    expected = {
        "sifma_archivo.html",
        "sifma_2026.html",
        "sofr_serie.json",
        "index_serie.json",
        "sofr_metodologia.html",
        "api_documentacion.html",
        *[v[1] for v in EXCEPTIONS.values()],
    }
    if len(registry) != len(expected) or {r["file"] for r in registry} != expected:
        raise ValueError("Unexpected public source inventory")
    for source in registry:
        path = research / source["file"]
        if (
            source["status_code"] != 200
            or path.stat().st_size != source["bytes"]
            or sha256(path) != source["sha256"]
        ):
            raise ValueError("Public source bytes differ from capture: " + source["file"])
    exceptions = read_json(research / "excepciones.json")
    if (
        len(exceptions) != len(EXCEPTIONS)
        or {
            r["date"]: (truth(r["is_business_day"]), r["source_file"], r.get("sifma_status"))
            for r in exceptions
        }
        != EXCEPTIONS
    ):
        raise ValueError("NY Fed exception extraction differs from reviewed notices")
    return approval


def derive(research, documents, reused, source_manifest=None):
    research, documents, reused = map(Path, (research, documents, reused))
    approval = authenticate_inputs(research, documents, reused, source_manifest)
    holidays = parse_sifma(
        (research / "sifma_archivo.html").read_text(encoding="utf-8"), "sifma_archivo.html"
    )
    holidays += parse_sifma(
        (research / "sifma_2026.html").read_text(encoding="utf-8"), "sifma_2026.html", current=True
    )
    calendar = calendar_rows(
        holidays, read_json(research / "excepciones.json"), date(2021, 12, 30), date(2026, 9, 1)
    )
    rates, indexes = [
        read_json(research / (n + "_serie.json"))["refRates"] for n in ("sofr", "index")
    ]
    coverage = validate_coverage(
        calendar, rates, indexes
    )  # Fail before calculating financial outputs.
    start, end = [date.fromisoformat(approval[k]) for k in ("start_inclusive", "end_exclusive")]
    blocks, daily = build_account(rates, calendar, start, end, approval["capital"])
    with localcontext(prec=50):
        initial = blocks[0]
        if (
            initial["rate_effective_date"],
            initial["accrual_days"],
            initial["source_days"],
            initial["accrual_end_exclusive"],
        ) != ("2021-12-31", 2, 3, "2022-01-03"):
            raise ValueError("Initial block dates differ from approval")
        if number(initial["percentRate"]) != D("0.05"):
            raise ValueError("Initial approved observed SOFR rate has changed")
        direct = D(10000) * D("0.0005") * 2 / 360
        initial_error = initial["interest_usd"] - direct
        if abs(initial_error) > D("1E-40"):
            raise ValueError("Initial two-day direct interest check failed")
        checks = index_checks(rates, calendar, indexes, date(2022, 1, 3), end)
        if abs(
            daily[-1]["balance_close"] / initial["balance_end"] - checks[-1]["calculated_factor"]
        ) > D("1E-40"):
            raise ValueError("Account after initial block differs from checked composition")
        for a, b in zip(daily, daily[1:]):
            close(a["balance_close"], b["balance_open"], "inherited daily balance")
        close(
            sum((r["interest_usd"] for r in daily), D(0)),
            daily[-1]["balance_close"] - 10000,
            "daily interest sum",
        )
    metrics, carry = [read_csv(reused / name) for name in COPY_TABLES[:2]]
    comparison, differences = compare_periods(daily, metrics)
    expected_periods = {"full", "2022-2023", "2024+", "2022", "2023", "2024", "2025", "2026"}
    if len(metrics) != 16 or {r["period"] for r in metrics} != expected_periods:
        raise ValueError("The eight approved comparison periods have changed")
    aligned = align_daily(daily, carry)
    benchmark = [r for r in comparison if r["portfolio"] == "sofr"]
    years = sorted([r for r in benchmark if r["period"].isdigit()], key=lambda r: r["period"])
    for a, b in zip(years, years[1:]):
        close(a["closing_balance"], b["opening_balance"], "inherited annual balance")
    close(
        sum((r["pnl"] for r in years), D(0)),
        daily[-1]["balance_close"] - 10000,
        "annual interest sum",
    )
    absent = [r for r in coverage if r["weekday"] < 5 and not r["is_business_day"]]
    initial_control = [
        dict(
            source_start=initial["source_start"],
            source_end=initial["source_end"],
            accrual_start=initial["accrual_start"],
            accrual_end_exclusive=initial["accrual_end_exclusive"],
            source_days=3,
            account_days=2,
            percentRate=initial["percentRate"],
            direct_formula="10000*(0.05/100)*2/360 = 1/36 USD",
            expected_interest_usd=direct,
            actual_interest_usd=initial["interest_usd"],
            arithmetic_error_usd=initial_error,
            saturday_official_index_used=False,
            passed=True,
        )
    ]
    tables = dict(
        calendario_sifma=holidays,
        calendario_verificado=coverage,
        dias_semana_sin_observacion=absent,
        bloques_sofr=blocks,
        cartera_sofr_diaria=daily,
        control_bloque_inicial=initial_control,
        control_sofr_index=checks,
        comparacion_periodos=comparison,
        diferencias_periodos=differences,
        metricas_sofr_periodos=benchmark,
        saldos_alineados=aligned,
    )
    audit = dict(
        status="passed",
        calendar_days=len(calendar),
        observed_business_dates=len(rates),
        unexplained_missing_dates=0,
        absent_weekdays=len(absent),
        sifma_full_close_weekdays=sum(r["sifma_status"] == "full_close" for r in absent),
        nyfed_nonpublication_exceptions=sum(r["nyfed_exception"] for r in absent),
        account_days=len(daily),
        business_blocks=len(blocks),
        index_checks=len(checks),
        index_anchor="2022-01-03",
        index_end="2026-09-01",
        index_quantum="0.00000001",
        index_tolerance="joint intervals from published eight-decimal rounding; not widened",
        initial_interest_exact_fraction="1/36 USD",
        decimal_precision=50,
        monetary_tolerance="1E-8",
        formula_arithmetic_tolerance="1E-40",
        comparison_rows=len(comparison),
        difference_rows=len(differences),
        carry_metrics_recalculated=False,
        engine_executed=False,
        prior_diagnostics_repeated=False,
        carry_cash_or_collateral_remunerated=False,
        h2_changed=False,
        carry_sharpe_rf=0,
        benchmark_sharpe_calculated=False,
    )
    return tables, audit

"""Maintain one unsealed global matrix, archiving each prior revision."""

import argparse
import csv
import shutil
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E4 = "entregas/entrega_4/"


def update(status, package):
    folder = ROOT/"docs/entrega_4"
    destination = folder/"matriz_avance.csv"
    history = folder/"historial_avance"
    history.mkdir(exist_ok=True)
    token = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    if destination.exists():
        shutil.copyfile(destination, history/f"{token}_anterior.csv")
    parent = E4+"reglas_historicas/20260925T005436Z"
    correction = E4+"reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z"
    intraday = E4+"riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z"
    capital = E4+"retorno_capital/20260927T143928Z/paquete_20260927T152732Z"
    sofr = E4+"retorno_capital/20260927T154653Z_sofr/paquete_20260927T162350Z"
    signal = E4+"senal_entradas/20260927T170230Z/paquete_20260927T185305Z"
    rows = [
        ("BASE", "Referencia continua, reglas prescritas y exposición/H2 corregidos", "compromiso metodológico; corrección de definición", "antecedente", "ejecutado", correction,
         correction+"/README.md; "+parent+"/manifiesto_paquete.json", "Reglas prescritas no equivalen a historia certificada del exchange; incompatibilidad previa de inventario/config documentada"),
        ("RIESGO", "Pérdidas transitorias y necesidades de garantías", "feedback E3, párrafo 2; decisiones experimentales del protocolo", "riesgo intradía previo", "ejecutado", intraday,
         intraday+"/reporte.md; "+intraday+"/documentos/feedback_e3.md", "Cuatro carteras previas; referencias spot antiguas y proxy separados; no reconstruido para bloque 3"),
        ("B1_CAPITAL", "Retorno con capital utilizado, concentración y rechazos", "feedback E3, párrafo 3; decisiones experimentales de concentración", "1", "ejecutado", capital,
         capital+"/reporte.md", "Sólo BASE; concentración descriptiva, sin CAGR contrafáctico quitando mejores ciclos"),
        ("B1_SOFR", "Comparador remunerado de todo el capital", "feedback E3, párrafo 3; cuenta y convenciones aprobadas por usuario", "1", "ejecutado", sofr,
         sofr+"/reporte.md; "+sofr+"/documentos/aprobacion.md", "Hipotética bruta USD, ACT/360 y paridad nominal USDT/USD; no remuneración de caja carry"),
        ("B2", "Horizonte/tenencia, vida media EWMA y techo del basis", "decisión experimental del encargo bloque 2", "2", "ejecutado", signal,
         signal+"/reporte.md; "+signal+"/indice_corridas.json", "Seis variantes sin cruces; no selección de ganador ni adopción en bloque 3"),
        ("B3", "Fricciones, participación y capital inicial con selección a 34 pb", "encargo explícito del usuario; decisión experimental, no parámetros exigidos por profesor", "3", status, package,
         package+("/reporte.md; "+package+"/manifiesto_paquete.json" if status=="ejecutado" else "/progreso.md"), "Ocho variantes por dos estrategias; capacidad con velas 1m, drawdown diario; no estimación de impacto/cola ni escalabilidad ilimitada"),
        ("B4", "Convención de ejecución y demoras", "compromiso de esquema de trabajo, encargo bloque 3 sección 10", "4", "pendiente", "",
         E4+"costos_capacidad/20260927T200204Z/encargo_usuario.md", "Coordinar latencia general y demora exclusiva de cierres sin duplicar escenarios"),
        ("B5", "Movimientos adversos y trayectoria hipotética sin interrupción", "feedback E3 y compromiso experimental; supuestos aún por aprobar", "5", "pendiente", "", "", "Requiere aprobar supuestos antes de ejecutar; proxy no es precio ejecutable observado"),
        ("B6", "Fechas iniciales alternativas, incertidumbre y evaluación conjunta", "compromiso de esquema de trabajo; decisión experimental futura", "6", "pendiente", "", "", "No inferir probabilidades o significancia de las sensibilidades actuales"),
        ("REVISION", "Revisión transversal de versiones/definiciones y redacción final", "compromiso del usuario y preparación de entrega académica", "transversal", "pendiente", "", "", "No es otra sensibilidad; Word/PDF se difieren hasta terminar y revisar análisis"),
        ("CAJA", "Remunerar o reinvertir caja libre y garantías del carry", "restricción explícita del alcance acordado", "fuera de alcance", "no_autorizado", "", "", "Distinto de la cuenta SOFR sobre capital completo; no ejecutar por inferencia"),
    ]
    columns = ["id", "requisito_pregunta", "origen", "bloque", "estado", "paquete_vigente", "evidencia", "limitacion"]
    with destination.open("w", encoding="utf8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns+["actualizado_utc", "publicacion"])
        writer.writerows([list(r)+[datetime.now(UTC).isoformat(), "local; no commit/push de bloque 3"] for r in rows])
    log = history/"cambios.md"
    with log.open("a", encoding="utf8") as stream:
        stream.write(f"\n- {token}: bloque 3 `{status}`, referencia `{package}`. "
                     "Estados previos contrastados con productos y manifiestos. "
                     "SOFR ejecutada sucede a notas históricas que la indicaban pendiente; los sellos se conservan.\n")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", choices=("en_ejecucion", "ejecutado"), required=True)
    parser.add_argument("--package", required=True)
    args = parser.parse_args()
    print(update(args.status, args.package))

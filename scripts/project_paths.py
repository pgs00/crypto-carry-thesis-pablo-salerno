"""Resolve recorded historical locations through the explicit thematic move map.

Only address resolution changes. Callers must still authenticate source bytes.
The embedded map also keeps newly exported tooling usable without repository docs.
"""

from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_ROOT = "C:/Users/pablo/Documentos/UCEMA/Tesina/Backtesting"
PATH_MOVES = {'configs/entrega_4/costos_capacidad': 'configs/costos_capacidad',
 'configs/entrega_4/ejecucion_demoras': 'configs/ejecucion',
 'configs/entrega_4/estabilidad_incertidumbre': 'configs/estabilidad',
 'configs/entrega_4/estres_contrafactual': 'configs/estres',
 'configs/entrega_4/reglas_historicas': 'configs/reglas_historicas',
 'configs/entrega_4/senal_entradas': 'configs/senal',
 'docs/entrega_4/matriz_avance.csv': 'results/matriz_resultados.csv',
 'docs/entrega_4/reglas_historicas': 'docs/reglas_historicas',
 'entregas/entrega_3/archivo/distribucion_20261010': 'data/evidence/ventanas_independientes',
 'entregas/entrega_3/archivo/empaquetar.py': 'scripts/package_independent_windows.py',
 'entregas/entrega_3/continua_distribucion_20261010': 'results/base/continuo',
 'entregas/entrega_3/continua_distribucion_20261010/README.md': 'results/base/continuo/procedencia/distribucion_20261010/README.md',
 'entregas/entrega_3/continua_distribucion_20261010/manifest.json': 'results/base/continuo/procedencia/distribucion_20261010/manifest.json',
 'entregas/entrega_3/continua_distribucion_20261010/manifest.sha256': 'results/base/continuo/procedencia/distribucion_20261010/manifest.sha256',
 'entregas/entrega_3/paquete_actualizacion_entrega_3_continua.zip': 'data/evidence/carteras_continuas.zip',
 'entregas/entrega_3/paquete_actualizacion_entrega_3_continua.zip.sha256': 'data/evidence/carteras_continuas.zip.sha256',
 'entregas/entrega_4/costos_capacidad/20260927T200204Z/distribucion_20261010': 'results/costos_capacidad/evidencia',
 'entregas/entrega_4/costos_capacidad/20260927T200204Z/paquete_20260927T231610Z': 'results/costos_capacidad/evidencia',
 'entregas/entrega_4/documento_final/Tesina_Entregas_3_y_4_Pablo_Salerno.pdf': 'Tesina_Pablo_Salerno.pdf',
 'entregas/entrega_4/ejecucion_demoras/20260929T221620Z/distribucion_20261010': 'results/ejecucion/evidencia',
 'entregas/entrega_4/ejecucion_demoras/20260929T221620Z/paquete_20260930T013915Z_v2': 'results/ejecucion/evidencia',
 'entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/controles_finales_corregidos': 'data/evidence/controles_historicos/estabilidad',
 'entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/distribucion_20261010': 'results/estabilidad/evidencia',
 'entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado': 'results/estabilidad/evidencia',
 'entregas/entrega_4/estres_contrafactual/20260930T214617Z/controles_finales_20261001T211248Z': 'data/evidence/controles_historicos/estres',
 'entregas/entrega_4/estres_contrafactual/20260930T214617Z/distribucion_20261010': 'results/estres/evidencia',
 'entregas/entrega_4/estres_contrafactual/20260930T214617Z/paquete_20261001T211248Z': 'results/estres/evidencia',
 'entregas/entrega_4/reglas_historicas/20260925T005436Z': 'data/evidence/reglas_historicas',
 'entregas/entrega_4/reglas_historicas/correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z': 'results/base/evidencia',
 'entregas/entrega_4/retorno_capital/20260927T143928Z/distribucion_20261010': 'results/capital/evidencia',
 'entregas/entrega_4/retorno_capital/20260927T143928Z/paquete_20260927T152732Z': 'results/capital/evidencia',
 'entregas/entrega_4/retorno_capital/20260927T154653Z_sofr/distribucion_20261010': 'results/benchmark_sofr/evidencia',
 'entregas/entrega_4/retorno_capital/20260927T154653Z_sofr/paquete_20260927T162350Z': 'results/benchmark_sofr/evidencia',
 'entregas/entrega_4/riesgo_intradia/20260926T214118Z/distribucion_20261010': 'results/riesgo/evidencia',
 'entregas/entrega_4/riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z': 'results/riesgo/evidencia',
 'entregas/entrega_4/senal_entradas/20260927T170230Z/autenticacion_referencias.json': 'results/senal/evidencia/documentos/autenticacion_referencias.json',
 'entregas/entrega_4/senal_entradas/20260927T170230Z/distribucion_20261010': 'results/senal/evidencia',
 'entregas/entrega_4/senal_entradas/20260927T170230Z/input_hashes.json': 'results/senal/evidencia/documentos/input_hashes.json',
 'entregas/entrega_4/senal_entradas/20260927T170230Z/paquete_20260927T185305Z': 'results/senal/evidencia'}


def resolve_recorded_path(value, project=None):
    """Resolve a mapped repository location; leave external data paths untouched."""
    project = ROOT if project is None else Path(project)
    text = str(value).replace("\\", "/")
    if text.startswith("//?/"):
        text = text[4:]
    relative = text
    for prefix in (str(project).replace("\\", "/").rstrip("/"), HISTORICAL_ROOT):
        if text.casefold().startswith(prefix.casefold() + "/"):
            relative = text[len(prefix) + 1:]
            break
    for old, new in sorted(PATH_MOVES.items(), key=lambda row: -len(row[0])):
        if relative == old or relative.startswith(old + "/"):
            suffix = relative[len(old):].lstrip("/")
            if ".." in PurePosixPath(suffix).parts:
                raise ValueError("Historical path escapes its mapped source")
            return project / new / suffix if suffix else project / new
    return Path(value)

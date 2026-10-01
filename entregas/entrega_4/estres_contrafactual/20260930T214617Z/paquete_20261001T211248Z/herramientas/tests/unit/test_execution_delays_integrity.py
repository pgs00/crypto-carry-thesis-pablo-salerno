"""Trust anchors and exact coverage of separately executed BASE controls."""

import pytest

from scripts.execution_delays import BASES
from scripts.return_capital.common import write_json


def test_base_hash_cannot_be_replaced_by_a_renewed_index_hash(tmp_path):
    from scripts.verify_execution_delays import verify_preserved_base
    write_json(tmp_path/'documentos/verificacion_base_previa.json',dict(runs=[
        dict(strategy='conditional',run_id=BASES['conditional'],manifest_sha256='original')]))
    verify_preserved_base(tmp_path,'conditional',BASES['conditional'],'original')
    with pytest.raises(ValueError,match='Preserved BASE'):
        verify_preserved_base(tmp_path,'conditional',BASES['conditional'],'renewed')


def test_two_copies_of_one_control_do_not_cover_both_strategies(tmp_path):
    from scripts.verify_execution_delays import verify_controls
    write_json(tmp_path/'documentos/control_compatibilidad_base_completa.json',
        dict(passed=True,comparisons=[dict(strategy='conditional')]*2))
    with pytest.raises(ValueError,match='control strategy coverage'):
        verify_controls(tmp_path,None,{}, {})


def test_control_equality_preserves_order_of_simultaneous_economic_events():
    from scripts.check_execution_delays_base import ordered_economic_digest
    rows=[dict(time_ns=1,event_id='funding',value='-40',run_id='old'),
          dict(time_ns=1,event_id='fill',value='100',run_id='old')]
    same=[dict(r,run_id='new') for r in rows]
    assert ordered_economic_digest(rows)==ordered_economic_digest(same)
    assert ordered_economic_digest(rows)!=ordered_economic_digest(rows[::-1])


@pytest.mark.parametrize('mutation',['missing','duplicate','label','path'])
def test_original_transfer_catalog_requires_exact_population_and_labels(mutation):
    from scripts.build_execution_delays import FILES
    from scripts.verify_execution_delays import validate_transfer_population
    runs=[dict(run_id='fixture',path='evidencia/fixture')]
    rows=[dict(run_id='fixture',source_name=n,
        package_path='evidencia/fixture/'+n+('.gz' if n=='forecast_evaluation.csv' else ''),
        transfer='lossless_gzip' if n=='forecast_evaluation.csv' else 'exact_bytes') for n in FILES]
    validate_transfer_population(rows,runs)
    if mutation=='missing':
        rows.pop()
    elif mutation=='duplicate':
        rows[-1]=rows[0]
    elif mutation=='label':
        rows[0]['source_name']='fiction'
    else:
        rows[0]['package_path']='evidencia/other/metrics.json'
    with pytest.raises(ValueError,match='transfer catalog'):
        validate_transfer_population(rows,runs)


@pytest.mark.parametrize('missing',['h1_observaciones.csv','h1_resumen.csv'])
def test_reused_hypotheses_require_all_original_members(tmp_path,missing):
    from scripts.return_capital.common import sha256
    from scripts.verify_execution_delays import verify_reused_hypotheses
    folder=tmp_path/'hipotesis_base'
    folder.mkdir()
    (folder/'h1_observaciones.csv').write_text('symbol,value\nBTCUSDT,1\nETHUSDT,2\n',encoding='utf8')
    (folder/'h1_resumen.csv').write_text('period,observations\nfull,2\n',encoding='utf8')
    (folder/'h3_diario.csv').write_text('day,opportunities\n1,2\n',encoding='utf8')
    original=tmp_path/'referencias/manifiesto_bloque2.json'
    write_json(original,dict(members=[dict(path='hipotesis/BASE_E3/'+p.name,sha256=sha256(p))
                                      for p in folder.iterdir()]))
    write_json(tmp_path/'documentos/autenticacion_referencias.json',
               [dict(dependency='block2',manifest_sha256=sha256(original))])
    assert verify_reused_hypotheses(tmp_path)==2
    (folder/missing).unlink()
    with pytest.raises(ValueError,match='Reused H1/H3 population'):
        verify_reused_hypotheses(tmp_path)

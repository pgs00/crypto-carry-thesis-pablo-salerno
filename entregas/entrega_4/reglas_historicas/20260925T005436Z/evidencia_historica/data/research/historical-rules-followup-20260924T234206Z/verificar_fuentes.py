"""Auditoría offline del paquete; sólo escribe resultados dentro de esta carpeta.

No ejecuta backtests, no importa crypto_carry y no modifica el índice de Git.
Dependencias: biblioteca estándar de Python. --self-test usa copias temporales.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from copy import deepcopy
import csv
import datetime as dt
from decimal import Decimal
from email.utils import parsedate_to_datetime
from functools import lru_cache
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

B=Path(__file__).resolve().parent
ROOT=B.parents[2]
STATUSES={'intervalo_respaldado','evento_respaldado','observacion_puntual','derivado','supuesto','contradictorio','pendiente','fuera_de_alcance'}
BACKED={'intervalo_respaldado','evento_respaldado','observacion_puntual','derivado'}

def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def read(p): return json.loads(p.read_text(encoding='utf-8'))
@lru_cache(maxsize=16)
def read_evidence(p):
    # Las fuentes se validan por hash antes de las pruebas. Ninguna prueba altera estas copias.
    return read(p)
def save(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def instant(x): return dt.datetime.fromisoformat(x.replace('Z','+00:00'))
def decimal(x): return Decimal(str(x))
def path_at(s): return (ROOT if s['local_base']=='repository' else B)/s['local_file']
def git(*args):
    r=subprocess.run(['git','--no-optional-locks',*args],cwd=ROOT,capture_output=True,check=True)
    return r.stdout.decode('utf-8').strip()

class Html(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.scripts=[]; self.text=[]; self.tables=[]; self.script=None; self.skip=0; self.table=None; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='script': self.script=''
        if tag in ['style','noscript']: self.skip+=1
        if tag=='table': self.table=[]
        if tag=='tr' and self.table is not None: self.row=[]
        if tag in ['td','th'] and self.row is not None: self.cell=''
    def handle_data(self,data):
        if self.script is not None: self.script+=data
        elif not self.skip: self.text.append(data)
        if self.cell is not None: self.cell+=data+' '
    def handle_endtag(self,tag):
        if tag=='script' and self.script is not None: self.scripts.append(self.script); self.script=None
        if tag in ['style','noscript']: self.skip=max(0,self.skip-1)
        if tag in ['td','th'] and self.cell is not None: self.row.append(' '.join(self.cell.split())); self.cell=None
        if tag=='tr' and self.row is not None: self.table.append(self.row); self.row=None
        if tag=='table' and self.table is not None: self.tables.append(self.table); self.table=None

def parse_html(p):
    parser=Html(); parser.feed(p.read_text(encoding='utf-8')); return parser

def fee_anchor(s):
    return fee_anchor_cached(s['id'],str(path_at(s)))

@lru_cache(maxsize=16)
def fee_anchor_cached(sid,filename):
    p=Path(filename); h=parse_html(p)
    if sid=='A1':
        for script in h.scripts:
            try: d=json.loads(script,parse_float=Decimal)
            except (ValueError,TypeError): continue
            try: rows=d['pageData']['redux']['ssrStore']['futureFee']
            except (KeyError,TypeError): continue
            row=next(r for r in rows if r['level']==0)
            assert row['makerCommission']==Decimal('.0002') and row['busdTakerCommission']==Decimal('.0003')
            return Decimal(row['takerCommission'])
        raise AssertionError('SSR futureFee level=0 no encontrado')
    if sid=='SPOT26':
        for table in h.tables:
            headers=table[0]
            if 'Maker / Taker' not in headers: continue
            i=headers.index('Maker / Taker')
            for row in table[1:]:
                if row and row[0]=='Regular User':
                    nums=re.findall(r'([0-9.]+)\s*%',row[i]); assert len(nums)==2,(row,nums)
                    return Decimal(nums[1])/100
        raise AssertionError('Sin fila Regular User y columna Maker / Taker estándar')
    text=' '.join(' '.join(h.text).split())
    start=re.search(r'How to calculate commission of USD.?.?-margined contracts\?',text,re.I)
    if not start:
        start=re.search(r'How to calculate.*?USD[^?]*contracts\?',text,re.I)
    assert start,'Sección USD-M no encontrada '+sid
    section=text[start.end():]
    m=re.search(r'(?:taker commission|taker fee):?\s*([0-9.]+)%',section,re.I); assert m,'Taker de sección USD-M no encontrado'
    rate=Decimal(m[1])/100
    assert 'BTCUSDT' in section
    expected=Decimal(10104)*rate
    assert str(expected.normalize()) in section or format(expected,'f') in section,(sid,expected)
    assert Decimal(11104)*Decimal('.0002')==Decimal('2.2208') and '2.2208' in section
    return rate

def validate_facts(doc,sources,check_proofs=True):
    errors=[]; fs=doc['facts']; byid={f['id']:f for f in fs}
    def check(ok,code,fid):
        if not ok: errors.append(code+': '+fid)
    check(len(fs)==len(byid),'duplicate_id','registry')
    for f in fs:
        fid=f['id']; status=f.get('status'); t=f.get('temporal',{}); sids=f.get('source_ids',[])
        check(status in STATUSES,'invalid_status',fid)
        required={'id','symbol','market','profile','parameter','value_original','value_normalized','unit','status','temporal','knowledge','applicability','source_ids','locator','proof'}
        check(required.issubset(f),'missing_fields',fid)
        check(all(s in sources for s in sids),'missing_source',fid)
        for k,v in t.items():
            if k.endswith('_utc') and v is not None:
                try: check(v.endswith('Z') and instant(v).utcoffset()==dt.timedelta(0),'invalid_utc',fid)
                except Exception: check(False,'invalid_utc',fid)
        for a,z in [('valid_from_utc','valid_to_exclusive_utc'),('earliest_utc','latest_utc')]:
            if t.get(a) and t.get(z): check(instant(t[a])<instant(t[z]),'inverted_interval',fid)
        if status=='intervalo_respaldado':
            check(t.get('kind')=='exact_interval' and t.get('valid_from_utc') and t.get('valid_to_exclusive_utc') and t.get('continuity_proven'),'false_interval',fid)
        else:
            check(not t.get('valid_from_utc') and not t.get('valid_to_exclusive_utc') and not t.get('continuity_proven'),'unjustified_continuity',fid)
        if t.get('kind')=='exact_event': check(bool(t.get('effective_at_utc')) and not t.get('earliest_utc') and not t.get('latest_utc'),'false_exact_time',fid)
        if t.get('kind') in ['deadline','approximate_rollout']: check(not t.get('effective_at_utc') and bool(t.get('latest_utc')),'uncertain_window_collapsed',fid)
        if t.get('kind')=='capture':
            check(t.get('observed_at_utc') in [sources[s].get('capture_utc') for s in sids],'capture_mismatch',fid)
            check(not t.get('effective_at_utc'),'capture_as_effective',fid)
        if status in BACKED:
            check(bool(sids) and bool(f['locator']) and bool(f['proof']),'untraceable_fact',fid)
            for sid in sids:
                if sid not in sources: continue
                s=sources[sid]; scope=s['evidence_scope']
                check(s['usable_for_facts'],'source_without_usable_data',fid)
                check(f['market'] in scope['markets'] and f['symbol'] in scope['symbols'] and f['profile']['vip'] in scope['vip'] and f['profile']['special_program']==scope['special_program'],'scope_mismatch',fid)
            check(f['profile']['exchange']=='Binance.com' and not f['profile']['bnb_discount'] and not f['profile']['referral'],'profile_mismatch',fid)
        if f['knowledge'].get('known_from_utc'):
            # Este paquete no ha acreditado primera disponibilidad exacta para ninguna regla.
            check(False,'unproven_known_from',fid)
            for sid in sids:
                pub=sources[sid].get('publication_original')
                if pub: check(f['knowledge']['known_from_utc'][:10]>=pub[:10],'publication_after_claimed_knowledge',fid)
        if status=='pendiente': check(f['value_normalized'] is None,'unknown_as_number',fid)
        if 'conversion' in f:
            cv=f['conversion']; v=decimal(f['value_normalized'])
            check(decimal(cv['percent'])==v*100 and decimal(cv['basis_points'])==v*10000,'rate_conversion',fid)
        if status in BACKED and check_proofs:
            try:
                proof=f['proof']; kind=proof['kind']; s=sources[sids[0]]
                if kind=='json_path':
                    raw=read_evidence(path_at(s)); value=raw
                    for part in proof['path']: value=value[part]
                    check(type(value)==type(f['value_original']) and value==f['value_original'],'raw_value_changed',fid)
                    check(value==f['value_normalized'] if isinstance(value,bool) or f['unit']=='enum' else decimal(value)==decimal(f['value_normalized']),'normalization_error',fid)
                    sym=raw['symbols'][proof['path'][1]]
                    check(sym['symbol']==f['symbol'] and sym['quoteAsset']=='USDT','symbol_mismatch',fid)
                    if f['market']=='futures_usdm_perpetual': check(sym.get('contractType')=='PERPETUAL' and sym.get('marginAsset')=='USDT','contract_mismatch',fid)
                    if f['unit'] not in ['boolean','enum'] and decimal(value)==0: check(f.get('zero_semantics') is not None,'unlabelled_zero',fid)
                elif kind=='fee_anchor':
                    check(s['id']==proof['anchor'],'fee_anchor_source_mismatch',fid)
                    check(fee_anchor(s)==decimal(f['value_normalized']),'fee_value_mismatch',fid)
                elif kind=='text_tokens':
                    text='\n'.join(path_at(sources[x]).read_text(encoding='utf-8') for x in sids)
                    for token in proof['tokens']: check(token in text,'missing_text_token '+token,fid)
                elif kind=='margin_table':
                    text=path_at(s).read_text(encoding='utf-8'); lines=dict((int(n),v) for n,v in re.findall(r'^L(\d+): (.*)$',text,re.M)); prev=None
                    for row in f['value_normalized']:
                        cells=[c.strip() for c in lines[row['source_line']].split('|')]
                        offset=0 if proof['side']=='before' else 3
                        if len(cells)==4: cells=([None]*3+cells[1:]) if cells[0] in ['NA','N/A'] else cells[:3]+[None]*3
                        original=row['original']
                        check(cells[offset:offset+3]==[original['leverage'],original['position'],original['rate_percent']],'wrong_table_column',fid)
                        floor,cap=re.fullmatch(r'([\d,]+) < Position ≤ ([\d,]+)',original['position']).groups()
                        check(decimal(floor.replace(',',''))==decimal(row['floor_usdt']) and decimal(cap.replace(',',''))==decimal(row['cap_usdt']),'tier_bounds',fid)
                        check(decimal(row['floor_usdt'])<decimal(row['cap_usdt']) and not row['floor_inclusive'] and row['cap_inclusive'],'tier_semantics',fid)
                        check(decimal(original['rate_percent'].rstrip('%'))/100==decimal(row['maintenance_rate']),'tier_rate_conversion',fid)
                        check(row['maximum_initial_leverage']==max(map(int,re.findall(r'\d+',original['leverage']))),'leverage_parse',fid)
                        check(row['maintenance_amount_published'] is None,'derived_as_published',fid)
                        if prev is not None: check(decimal(prev)==decimal(row['floor_usdt']),'noncontiguous_tiers',fid)
                        else: check(decimal(row['floor_usdt'])==0,'missing_first_tier',fid)
                        prev=row['cap_usdt']
                    check(f['value_original']==[r['original'] for r in f['value_normalized']],'tier_original_mismatch',fid)
                elif kind=='derived_tiers':
                    parent=byid[proof['input_fact_id']]; accum=Decimal(0); previous=Decimal(0); expected=[]
                    for row in parent['value_normalized']:
                        accum+=decimal(row['floor_usdt'])*(decimal(row['maintenance_rate'])-previous); previous=decimal(row['maintenance_rate']); expected.append(accum)
                    check(list(map(decimal,f['value_normalized']))==expected and status=='derivado','derived_deduction',fid)
                else: check(False,'unknown_proof_kind',fid)
                if status=='evento_respaldado':
                    text=path_at(s).read_text(encoding='utf-8')
                    if s['id'] in ['MINSPOT23','MINFUT23']:
                        check('by 2023-' in text and t['kind']=='deadline' and t['earliest_utc'] is None,'deadline_promoted_to_exact',fid)
                    if s['id'] in ['MINBTC26','MARG24','MARGBTC25','MARGAUG25']:
                        check('approximately' in text and t['kind']=='approximate_rollout','rollout_promoted_to_exact',fid)
            except Exception as exc: check(False,'proof_error '+str(exc),fid)
    # Detectar versiones incompatibles del mismo parámetro con intervalos garantizados superpuestos.
    groups=defaultdict(list)
    for f in fs:
        if f['status']=='intervalo_respaldado': groups[(f['symbol'],f['market'],f['parameter'],json.dumps(f['profile'],sort_keys=True))].append(f)
    for group in groups.values():
        for i,a in enumerate(group):
            for b in group[i+1:]:
                ta,tb=a['temporal'],b['temporal']
                if max(ta['valid_from_utc'],tb['valid_from_utc'])<min(ta['valid_to_exclusive_utc'],tb['valid_to_exclusive_utc']): check(a['value_normalized']==b['value_normalized'],'contradictory_overlap',a['id']+' '+b['id'])
    return errors

def union_seconds(intervals):
    merged=[]
    for a,z in sorted(intervals):
        if merged and a<=merged[-1][1]: merged[-1]=(merged[-1][0],max(z,merged[-1][1]))
        else: merged.append((a,z))
    return sum(int((instant(z)-instant(a)).total_seconds()) for a,z in merged)

def validate_coverage(doc,rows):
    errors=[]; groups=defaultdict(list); byid={f['id']:f for f in doc['facts']}; start=doc['scope']['start_utc']; end=doc['scope']['end_exclusive_utc']
    for r in rows:
        key=(r['symbol'],r['market'],r['parameter'])
        if r['status']=='intervalo_respaldado':
            f=byid.get(r['fact_ids']); a,z=r['start_utc'],r['end_utc']
            if not f or f['status']!='intervalo_respaldado' or a!=f['temporal']['valid_from_utc'] or z!=f['temporal']['valid_to_exclusive_utc']: errors.append('coverage_unbacked_interval')
            if not start<=a<z<=end: errors.append('coverage_outside_window')
            if int(r['counted_seconds'])!=int((instant(z)-instant(a)).total_seconds()): errors.append('coverage_duration')
            groups[key].append((a,z))
        elif int(r['counted_seconds'])!=0: errors.append('coverage_point_counted_as_days')
        if r['fact_ids'] and r['fact_ids'] not in byid: errors.append('coverage_unknown_fact')
        if r['start_utc'] and r['end_utc'] and r['start_utc']>=r['end_utc']: errors.append('coverage_inverted')
    metrics=[]
    for key,intervals in groups.items():
        seconds=union_seconds(intervals)
        raw=sum(int(r['counted_seconds']) for r in rows if (r['symbol'],r['market'],r['parameter'])==key)
        if raw!=seconds: errors.append('coverage_double_count')
        metrics.append(dict(symbol=key[0],market=key[1],parameter=key[2],covered_seconds_union=seconds,covered_days_decimal=str(Decimal(seconds)/86400),criterion='unión de intervalos explícitos finitos; observaciones/eventos/supuestos aportan cero'))
    return errors,metrics

def protected_errors(root,entries):
    errors=[]
    for f in entries:
        p=root/f['path']
        if not p.exists() or p.stat().st_size!=f['bytes'] or sha(p)!=f['sha256']: errors.append('protected_file_changed: '+f['path'])
    return errors

def self_tests(doc,sources):
    results=[]
    with tempfile.TemporaryDirectory(prefix='verificacion_temporal_',dir=B) as tmp:
        temp=Path(tmp).resolve(); assert temp.is_relative_to(B.resolve())
        def trial(name,mutate,want):
            copied=deepcopy(doc); ss=deepcopy(sources); mutate(copied,ss)
            save(temp/'reglas.json',copied); save(temp/'fuentes.json',ss)
            errors=validate_facts(read(temp/'reglas.json'),read(temp/'fuentes.json'))
            results.append(dict(test=name,passed=any(want in e for e in errors),expected_error=want,detected_errors=errors))
        def fact(d,name): return next(f for f in d['facts'] if f['id']==name)
        trial('mezcla VIP0 con VIP1',lambda d,s:fact(d,'FEE_A1_BTCUSDT')['profile'].update(vip='VIP1'),'scope_mismatch')
        trial('mezcla futuros con spot',lambda d,s:fact(d,'FEE_A1_BTCUSDT').update(market='spot'),'scope_mismatch')
        trial('ventana incierta promovida a instante',lambda d,s:fact(d,'EVENT_MINBTC26_BTCUSDT')['temporal'].update(kind='exact_event',effective_at_utc='2026-04-14T06:30:00Z',earliest_utc=None,latest_utc=None),'rollout_promoted_to_exact')
        trial('publicación posterior igualada a conocimiento de vigencia',lambda d,s:fact(d,'TIERS_MARG23_BTCUSDT_after')['knowledge'].update(known_from_utc='2023-12-24T09:35:00Z'),'publication_after_claimed_knowledge')
        trial('captura sin tabla usada como tarifa',lambda d,s:fact(d,'FEE_SPOT26_BTCUSDT').update(source_ids=['SPOT25']),'source_without_usable_data')
        trial('cero desconocido inventado',lambda d,s:fact(d,'PENDING_FEE_DATE_BTCUSDT').update(value_normalized='0'),'unknown_as_number')
        trial('porcentaje mal convertido',lambda d,s:fact(d,'FEE_A1_BTCUSDT').update(value_normalized='0.04'),'rate_conversion')
        trial('intervalo invertido',lambda d,s:fact(d,'BTC_SPOT_ZERO')['temporal'].update(valid_to_exclusive_utc='2022-01-01T00:00:00Z'),'inverted_interval')
        def overlap(d,s):
            f=deepcopy(fact(d,'BTC_SPOT_ZERO')); f.update(id='CONTRADICTORY_TEST',value_original='0.1%',value_normalized='0.001',conversion=dict(percent='0.1',basis_points='10')); d['facts'].append(f)
        trial('solapamiento contradictorio',overlap,'contradictory_overlap')
        entries=read(B/'estado_inicial.json')['protected_files']; protected=entries[0]
        target=temp/protected['path']; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes((ROOT/protected['path']).read_bytes()+b'\nTEST ALTERATION\n')
        errors=protected_errors(temp,[protected]); results.append(dict(test='alteración de copia de archivo protegido',passed=bool(errors),expected_error='protected_file_changed',detected_errors=errors))
        rows=list(csv.DictReader((B/'cobertura.csv').open(encoding='utf-8',newline=''))); rows.append(deepcopy(next(r for r in rows if r['status']=='intervalo_respaldado')))
        save(temp/'cobertura_duplicada.json',rows); errors,_=validate_coverage(doc,read(temp/'cobertura_duplicada.json'))
        results.append(dict(test='cobertura duplicada',passed='coverage_double_count' in errors,expected_error='coverage_double_count',detected_errors=errors))
    return results

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--self-test',action='store_true'); parser.add_argument('--write-manifest',action='store_true'); args=parser.parse_args()
    # El manifiesto no se auto-hashea; el resultado incluye su hash. No se recatalogan fuentes para ocultar una alteración.
    excluded={'manifest.json','verificacion_resultados.json','verificacion_resultados.txt'}
    if args.write_manifest:
        files=[dict(path=p.relative_to(B).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(B.rglob('*')) if p.is_file() and p.name not in excluded and '__pycache__' not in p.parts]
        save(B/'manifest.json',dict(schema='byte_manifest_v1',generated_at_utc=now(),hash_algorithm='SHA-256',representation='bytes locales exactos',exclusions=sorted(excluded),files=files))
    errors=[]; checks=[]
    doc=read(B/'reglas_historicas.json'); source_doc=read(B/'fuentes.json'); sources={s['id']:s for s in source_doc['sources']}
    if len(sources)!=len(source_doc['sources']): errors.append('duplicate_source_id')
    manifest=read(B/'manifest.json')
    for m in manifest['files']:
        p=B/m['path']
        if not p.is_file() or p.stat().st_size!=m['bytes'] or sha(p)!=m['sha256']: errors.append('manifest_mismatch: '+m['path'])
    actual={p.relative_to(B).as_posix() for p in B.rglob('*') if p.is_file() and p.name not in excluded and '__pycache__' not in p.parts}
    if actual!={f['path'] for f in manifest['files']}: errors.append('manifest_file_set_mismatch')
    checks.append(dict(name='manifiesto de archivos nuevos',count=len(manifest['files'])))
    for s in sources.values():
        p=path_at(s)
        if not p.is_file() or p.stat().st_size!=s['bytes'] or sha(p)!=s['sha256']: errors.append('source_hash_mismatch: '+s['id'])
        if s.get('metadata_file'):
            m=read(B/s['metadata_file']); headers={k.lower():v for k,v in m['headers'].items()}
            if s['sha256']!=m['sha256'] or s['final_url']!=m['final_url']: errors.append('source_metadata_mismatch: '+s['id'])
            if s['capture_utc']:
                captured=parsedate_to_datetime(headers['memento-datetime']).isoformat().replace('+00:00','Z')
                stamp=re.search(r'/web/(\d{14})',s['final_url']).group(1)
                if captured!=s['capture_utc'] or instant(captured).strftime('%Y%m%d%H%M%S')!=stamp: errors.append('memento_url_mismatch: '+s['id'])
            if m.get('extraction'):
                ex=m['extraction']
                if sha(B/ex['text_path'])!=ex['text_sha256']: errors.append('text_extraction_mismatch: '+s['id'])
        if s['type']=='archive_index':
            index=read(p)
            if not all(isinstance(row,list) and len(row)==5 for row in index): errors.append('cdx_unhandled_pagination: '+s['id'])
    checks.append(dict(name='fuentes y capturas reales, incluidos hashes de texto extraído',count=len(sources)))
    errors+=validate_facts(doc,sources)
    checks.append(dict(name='esquema, alcance, prueba contra fuente y temporalidad',count=len(doc['facts'])))
    with (B/'cobertura.csv').open(encoding='utf-8',newline='') as f: coverage=list(csv.DictReader(f))
    coverage_errors,metrics=validate_coverage(doc,coverage); errors+=coverage_errors
    checks.append(dict(name='cobertura por unión sin días imputados a puntos',count=len(coverage)))
    baseline=read(B/'estado_inicial.json'); errors+=protected_errors(ROOT,baseline['protected_files'])
    index_path=Path(git('rev-parse','--git-path','index')); index_path=index_path if index_path.is_absolute() else ROOT/index_path
    if sha(index_path)!=baseline['git_index_sha256']: errors.append('git_index_changed')
    if git('rev-parse','HEAD')!=baseline['head']: errors.append('git_head_changed')
    if git('branch','--show-current')!=baseline['branch']: errors.append('git_branch_changed')
    checks.append(dict(name='archivos protegidos, índice, HEAD y rama',count=len(baseline['protected_files'])))
    rel=B.relative_to(ROOT).as_posix()
    paths=[rel+'/'+m['path'] for m in manifest['files']]+[rel+'/'+p for p in excluded]
    r=subprocess.run(['git','--no-optional-locks','check-attr','-z','--stdin','text','whitespace'],cwd=ROOT,input=('\0'.join(paths)+'\0').encode('utf-8'),capture_output=True,check=True)
    attrs=r.stdout.decode('utf-8').split('\0'); attrs=attrs[:-1] if attrs[-1]=='' else attrs
    for i in range(0,len(attrs),3):
        p,k,v=attrs[i:i+3]
        if v!=('unset' if k=='text' else 'cr-at-eol'): errors.append('incorrect_git_attribute: '+p+' '+k+'='+v)
    checks.append(dict(name='atributos efectivos -text y whitespace=cr-at-eol',count=len(paths)))
    tests=self_tests(doc,sources) if args.self_test else []
    errors+=['negative_test_failed: '+t['test'] for t in tests if not t['passed']]
    result=dict(checked_at_utc=now(),python=sys.version,command=' '.join(sys.argv),passed=not errors,errors=errors,checks=checks,negative_tests=tests,coverage=metrics,manifest_sha256=sha(B/'manifest.json'),git_status=git('status','--short'),index_unchanged=sha(index_path)==baseline['git_index_sha256'],head=git('rev-parse','HEAD'),interpretation_limit='Hash conserva bytes; las pruebas documentales no certifican continuidad ni primera publicación. Segunda revisión por el mismo agente registrada por separado.')
    save(B/'verificacion_resultados.json',result)
    (B/'verificacion_resultados.txt').write_text(('PASS' if result['passed'] else 'FAIL')+'\n'+'\n'.join(errors)+'\n'+json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result['passed'] else 1

if __name__=='__main__': sys.exit(main())

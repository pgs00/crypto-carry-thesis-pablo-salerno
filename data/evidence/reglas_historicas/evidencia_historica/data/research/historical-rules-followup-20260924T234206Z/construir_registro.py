"""Extracción documental local, acotada a las fuentes seleccionadas. No importa el motor."""
from __future__ import annotations
import csv
import datetime as dt
from decimal import Decimal
from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import re
from collections import defaultdict

B = Path(__file__).resolve().parent
ROOT = B.parents[2]
START, END = '2022-01-01T00:00:00Z', '2026-09-01T00:00:00Z'
FUT, SPOT = 'futures_usdm_perpetual', 'spot'
SYMS = ['BTCUSDT', 'ETHUSDT']
PROFILE = dict(exchange='Binance.com', vip='Regular/VIP0', bnb_discount=False, referral=False, special_program=False, execution='taker')

def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def save(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dec(v): return format(Decimal(str(v)).normalize(), 'f')
def utc_email(v): return parsedate_to_datetime(v).isoformat().replace('+00:00', 'Z') if v else None
def iso(t): return dt.datetime.fromisoformat(t.replace('Z', '+00:00'))

def main():
    sources, facts, articles, logs = {}, [], {}, []
    generated = now()
    # Descriptores: identidad documental y alcance de las filas seleccionadas, no historia completa.
    definitions = [
        ('PROMO_START','10435147c55d4a40b64fcbf43cb46329',['W003'],SPOT,SYMS,'2022-07-06 14:00',['2022-07-08','2023-03-23']),
        ('PROMO_END','be13a645cca643d28eab5b9b34f2dc36',['W003','W017'],SPOT,SYMS,'2023-03-15 06:10',['2023-05-04','2023-11-22']),
        ('MARG22','56ba139dd19249acb4f9470c3d98020d',['W006'],FUT,['ETHUSDT'],'2022-09-13 03:05',[]),
        ('MARG23','d75c5ca94f704e96a6a4e55ffddfd65d',['W006'],FUT,SYMS,'2024-01-02 13:50',[]),
        ('MARG24','aa735cd2d8bd4e7bb092179cf086e486',['W008'],FUT,SYMS,'2024-05-27 06:00',[]),
        ('MARGBTC25','e778988edec446038ad536bcb0c8d460',['W008'],FUT,['BTCUSDT'],'2025-06-14 14:08',[]),
        ('MARGAUG25','8e428625ebeb4cc7ae8678026846095c',['W008','W017'],FUT,SYMS,'2025-08-17 03:31',['2025-08-18','2025-08-25']),
        ('MINFUT23','e4384cba297a4bd2a154be644d5d76f9',['W010'],FUT,SYMS,'2023-10-27 12:40',['2023-10-30']),
        ('MINSPOT23','c4706c73b805423a8d36be948e297603',['W010'],SPOT,SYMS,'2023-08-24 02:05',[]),
        ('MINBTC26','10999fd17dc045de801c0c78ab29e6fc',['W010'],FUT,['BTCUSDT'],'2026-04-09 06:14',[]),
        ('TICK22','81e6795b0bae49828cbd52479094a987',['W015'],FUT,['BTCUSDT'],'2021-12-31 06:45',[]),
        ('STEP21','6925d618ab6b47e2936cc4614eaad64b',['W015','W016','W017'],SPOT,SYMS,'2021-08-12 15:57',[]),
        ('FAQ_LIQ','98488a516eb84e3eb34605683dffd554',['W012','W013'],FUT,SYMS,'2024-05-29 14:55',['2026-01-05 05:00']),
        ('DOC_FUT','market-data',['W013'],FUT,SYMS,None,[]),
        ('OUT_VIP1','4f379b9ab6314eff8fe02babfe255825',['W012'],FUT,SYMS,'2026-03-18 08:00',['2026-09-10 03:53']),
        ('OUT_TAKER','143cee3a83944c4da2b1a53f302f45f0',['W015'],FUT,SYMS,'2023-10-18 04:00',[]),
        ('OUT_BTCU','fe2b0d2853004943aba45f2e87a4081c',['W015'],SPOT,['BTCU'],'2026-04-10 09:00',[]),
    ]
    for sid, needle, wids, market, symbols, pub, updates in definitions:
        parts, refs, dates = [], [], []
        for wid in wids:
            r = read(B/'originales'/f'{wid}_web.json')
            for chunk in r['response'].split('-'*80):
                chunk=chunk.strip()
                if not chunk or needle not in chunk.splitlines()[0] or not re.search(r'Source: (open|find)\(', chunk): continue
                if 'L' not in chunk: continue
                parts.append(chunk); refs.append(f'originales/{wid}_web.json'); dates.append(r['queried_at_utc'])
        assert parts, sid
        text='\n\n'.join(parts)+'\n'
        target=B/'extraidos'/f'{sid}_web.txt'; target.write_text(text,encoding='utf-8',newline='\n')
        url=re.search(r'\((https?://[^\n]+)\)\n',parts[0]).group(1)
        sources[sid]=dict(id=sid,publisher='Binance',title=parts[0].splitlines()[0].rsplit(' (http',1)[0],type='official_current_web_text',original_url=url,final_url=url,publisher_url=url,publication_original=pub,publication_utc=None,publication_timezone='no acreditada en encabezado',updates_original=updates,updates_utc=None,capture_utc=None,queried_at_utc=min(dates),last_consulted_at_utc=max(dates),http_status=None,local_file=f'extraidos/{sid}_web.txt',local_base='package',bytes=target.stat().st_size,sha256=sha(target),hash_representation='UTF-8 de extracción textual web.run; NO bytes HTML/HTTP originales',raw_tool_records=sorted(set(refs)),original_http_copy_available=False,online_only_original=True,usable_for_facts=True,table_recovered=(' | ' in text),evidence_scope=dict(markets=[market],symbols=symbols,vip=['VIP1','VIP2'] if sid=='OUT_VIP1' else ['Regular/VIP0'],special_program=(sid=='OUT_TAKER')),regional_note='Versión pública del mismo ID en Binance.com; el cuerpo describe el mercado indicado. Locales no son fuentes independientes ni acreditan acceso de una cuenta/región. No es Binance.US.',historical_original_version_verified=False)
        articles[sid]=text
    legacy=read(ROOT/'data/research/fee-archive-followup-20260918/manifest.json')
    for m in legacy:
        sid=m['source_id']; p=ROOT/m['path']
        assert sha(p)==m['sha256_decoded_html_utf8'] and p.stat().st_size==m['bytes_decoded_html_utf8']
        sources[sid]=dict(id=sid,publisher='Binance vía Internet Archive',title='Futures fees: tabla Regular USDT' if sid=='A1' else 'Binance Futures Fee Structure & Fee Calculations',type='legacy_archived_official_html',original_url=m['source_url'],final_url=m['source_url'],publisher_url=m['source_url'].split('id_/',1)[1],publication_original={'A1':None,'A2':'2020-06-11 07:01','A3':'2019-09-09 13:39'}[sid],publication_utc=None,updates_original=[],capture_utc=utc_email(m['memento_datetime']),queried_at_utc=generated,previous_retrieval_utc=m['retrieved_at'],http_status=None,local_file=m['path'],local_base='repository',bytes=p.stat().st_size,sha256=sha(p),hash_representation='HTML decodificado y recodificado UTF-8 en antecedente; no bytes de transporte',original_http_copy_available=False,online_only_original=False,usable_for_facts=True,table_recovered=sid=='A1',evidence_scope=dict(markets=[FUT],symbols=SYMS if sid=='A1' else ['BTCUSDT'],vip=['Regular/VIP0'],special_program=False),historical_original_version_verified=True)
    usable_api=['SPOTI22','SPOTI23','SPOTI25','FUTI22','FUTI22B','FUTI26','FUTI26B']
    for mp in sorted((B/'originales').glob('*.meta.json')):
        m=read(mp); sid=m['id']; headers={k.lower():v for k,v in m['headers'].items()}
        capture=utc_email(headers.get('memento-datetime'))
        isapi=sid in usable_api; good=sid in usable_api+['A4','SPOT26','DOCSPOTRAW','CDXDOC']
        market=SPOT if sid.startswith('SPOT') or sid=='DOCSPOTRAW' else FUT
        typ='historical_api_snapshot' if isapi else 'archive_index' if sid.startswith('CDX_') else 'archived_official_html' if sid in ['A4','SPOT26'] else 'official_documentation_current' if sid=='DOCSPOTRAW' else 'retrieval_only'
        s=dict(id=sid,publisher='Binance' if good and sid!='CDXDOC' else 'Internet Archive' if sid.startswith('CDX') else 'Kripto Akadémia' if sid=='LEAD_OCT' else 'ver URL',title=(m.get('extraction') or {}).get('title') or ('exchangeInfo '+market if isapi else sid),type=typ,original_url=m['original_url'],final_url=m['final_url'],publisher_url=m['final_url'].split('id_/',1)[-1],publication_original='2019-09-09 13:39' if sid=='A4' else None,publication_utc=None,updates_original=[],capture_utc=capture,queried_at_utc=m['requested_at_utc'],retrieved_at_utc=m['retrieved_at_utc'],http_status=m['http_status'],local_file=m['file'],local_base='package',bytes=m['bytes'],sha256=m['sha256'],hash_representation=m['hash_representation'],automatic_decompression=m['automatic_decompression'],metadata_file=mp.relative_to(B).as_posix(),redirects=m['redirects'],original_http_copy_available=True,online_only_original=False,usable_for_facts=good and sid!='CDXDOC',table_recovered=sid=='SPOT26',evidence_scope=dict(markets=[market],symbols=['BTCUSDT'] if sid=='A4' else SYMS,vip=['Regular/VIP0'],special_program=False),historical_original_version_verified=bool(capture and good),exclusion_reason=None if good else 'Índice/pista o respuesta sin datos objetivo; no prueba una regla ni ausencia de promociones')
        if sid=='A4':
            # La etiqueta se verifica de nuevo en el texto de esta captura, no por la FAQ actual.
            txt=(B/'extraidos/A4.txt').read_text(encoding='utf-8')
            match=re.search(r'\b20\d\d-\d\d-\d\d \d\d:\d\d\b',txt); s['publication_original']=match.group(0) if match else None
        if sid=='FUTI23': s['exclusion_reason']='Replay redirige a 2024-01-08 y devuelve HTTP 451: no exchangeInfo utilizable, aunque CDX listaba 200 en otra fecha.'
        if sid in ['SPOT25','SPOT25B','PROMO25','PROMO26']: s['exclusion_reason']='HTML recuperado sin tabla de tarifas/promociones objetivo. No records found o plantilla sin pares no demuestra ausencia de promociones.'
        if sid.startswith('CDX_'):
            d=read(B/m['file']); s['cdx_row_count']=max(0,len(d)-1); s['cdx_no_resume_key_returned']=all(isinstance(row,list) and len(row)==5 for row in d)
            s['cdx_scope_note']='Resultado íntegro de esta URL/rango sin collapse; no inventario exhaustivo de todo Binance.'
        sources[sid]=s

    def temporal(kind='unknown', **kw):
        return dict(kind=kind,valid_from_utc=None,valid_to_exclusive_utc=None,effective_at_utc=None,earliest_utc=None,latest_utc=None,observed_at_utc=None,continuity_proven=False,**kw)
    def add(fid,symbol,market,param,original,normalized,unit,sids,locator,status='observacion_puntual',time=None,app=None,proof=None,**kw):
        ss=[sources[s] for s in sids]; captures=[s['capture_utc'] for s in ss if s['capture_utc']]
        f=dict(id=fid,symbol=symbol,market=market,profile=PROFILE.copy(),parameter=param,value_original=original,value_normalized=normalized,unit=unit,status=status,temporal=time or temporal(),knowledge=dict(known_from_utc=None,document_observed_at_utc=min(captures) if captures else None,consulted_at_utc=min(s['queried_at_utc'] for s in ss) if ss else generated,publication_labels=[s['publication_original'] for s in ss if s['publication_original']],publication_timezone_unknown=True,note='Captura acredita contenido observado, no inicio operativo ni primera publicación. Versión actual no prueba disponibilidad histórica de todas sus enmiendas.'),applicability=app or dict(orders=None,existing_orders_affected=None,existing_positions_affected=None,position_increases=None),source_ids=sids,locator=locator,proof=proof,**kw)
        facts.append(f); return f
    for sid in usable_api:
        d=read(B/'originales'/f'{sid}.body'); capture=sources[sid]['capture_utc']; market=SPOT if sid.startswith('SPOT') else FUT
        selected=[]
        for i,symbol in enumerate(d['symbols']):
            if symbol['symbol'] not in SYMS: continue
            assert symbol['quoteAsset']=='USDT'
            if market==FUT: assert symbol['contractType']=='PERPETUAL' and symbol['marginAsset']=='USDT'
            selected.append(dict(json_path=f'$.symbols[{i}]',value=symbol))
            for j,flt in enumerate(symbol['filters']):
                name=flt['filterType']
                # Todos los filtros presentes, sin confundir conteos con máximos de cantidad/nocional.
                for field,value in flt.items():
                    if field=='filterType': continue
                    path=['symbols',i,'filters',j,field]
                    categorical=field=='positionControlSide'
                    unit='enum' if categorical else 'boolean' if isinstance(value,bool) else 'minutes' if field=='avgPriceMins' else symbol['baseAsset'] if field in ['minQty','maxQty','stepSize','maxPosition'] else 'USDT' if field in ['minPrice','maxPrice','tickSize','minNotional','maxNotional','notional'] else 'dimensionless'
                    norm=value if categorical or isinstance(value,bool) else dec(value)
                    t=temporal('capture'); t['observed_at_utc']=capture
                    app=dict(orders='MARKET' if name=='MARKET_LOT_SIZE' else 'ver filtro y banderas',filter_type=name,flags={k:v for k,v in flt.items() if k.startswith('apply') or k=='avgPriceMins'},existing_orders_affected=None,existing_positions_affected=None,position_increases=None,semantic_reference='DOCSPOTRAW' if market==SPOT else 'DOC_FUT',historical_semantic_version_verified=False)
                    zero='published_zero_not_unknown; desactivación histórica de MARKET_LOT_SIZE.stepSize no documentada aquí; no ejecutar módulo/división por cero' if not categorical and not isinstance(value,bool) and Decimal(str(value))==0 else None
                    add(f'{sid}_{symbol["symbol"]}_{name}_{field}',symbol['symbol'],market,f'{name}.{field}',value,norm,unit,[sid],f'$.symbols[{i}].filters[{j}].{field}',time=t,app=app,proof=dict(kind='json_path',path=path),zero_semantics=zero)
            if market==FUT:
                for field in ['liquidationFee','marketTakeBound','triggerProtect']:
                    t=temporal('capture'); t['observed_at_utc']=capture
                    add(f'{sid}_{symbol["symbol"]}_{field}',symbol['symbol'],market,field,symbol[field],dec(symbol[field]),'fraction',[sid],f'$.symbols[{i}].{field}',time=t,proof=dict(kind='json_path',path=['symbols',i,field]),conversion=dict(percent=dec(Decimal(symbol[field])*100),basis_points=dec(Decimal(symbol[field])*10000)))
        sources[sid]['serverTime_original_ms']=d.get('serverTime')
        sources[sid]['serverTime_utc']=dt.datetime.fromtimestamp(d['serverTime']/1000,dt.timezone.utc).isoformat().replace('+00:00','Z') if 'serverTime' in d else None
        sources[sid]['serverTime_is_effective_date']=False
        save(B/'extraidos'/f'{sid}_seleccion.json',dict(source_id=sid,capture_utc=capture,serverTime=d.get('serverTime'),symbols=selected))

    for sid,value in [('A1','0.04%'),('A2','0.040%'),('A4','0.040%'),('A3','0.05%'),('SPOT26','0.100%')]:
        syms=SYMS if sid in ['A1','SPOT26'] else ['BTCUSDT']; market=SPOT if sid=='SPOT26' else FUT
        for symbol in syms:
            t=temporal('capture'); t['observed_at_utc']=sources[sid]['capture_utc']
            loc='Regular / USDT / sin BNB; SSR $.pageData.redux.ssrStore.futureFee[level=0].takerCommission' if sid=='A1' else 'Regular / Maker-Taker estándar; columna taker (no BNB, no USDC)' if sid=='SPOT26' else 'Ejemplo USD-M: BTCUSDT taker y cálculo de comisión; no COIN-M'
            add(f'FEE_{sid}_{symbol}',symbol,market,'taker_fee_base',value,dec(Decimal(value.rstrip('%'))/100),'fraction',[sid],loc,time=t,proof=dict(kind='fee_anchor',anchor=sid),conversion=dict(percent=dec(value.rstrip('%')),basis_points=dec(Decimal(value.rstrip('%'))*100)),app=dict(orders='taker',discounts='ninguno',promotion_membership_verified=False,example_only=sid in ['A2','A3','A4']))
    t=temporal('exact_interval'); t.update(valid_from_utc='2022-07-08T14:00:00Z',valid_to_exclusive_utc='2023-03-22T00:00:00Z',continuity_proven=True)
    add('BTC_SPOT_ZERO','BTCUSDT',SPOT,'taker_fee','0%','0','fraction',['PROMO_START','PROMO_END'],'PROMO_START anuncio/13 pares y all users; PROMO_END fila BTC/USDT, fechas explícitas UTC',status='intervalo_respaldado',time=t,app=dict(orders='taker spot BTCUSDT; programa general',existing_orders_affected=None,existing_positions_affected=None,position_increases=None,volume_excluded_from_vip=True),proof=dict(kind='text_tokens',tokens=['2022-07-08 14:00 (UTC)','2023-03-22 00:00 (UTC)','BTC/USDT']),conversion=dict(percent='0',basis_points='0'),zero_semantics='tarifa publicada cero; no desconocido')
    events=[
        ('TICK22','BTCUSDT',FUT,'PRICE_FILTER.tickSize','0.01','0.1','USDT','exact_event','2022-02-15T03:30:00Z',None),
        ('STEP21','BTCUSDT',SPOT,'LOT_SIZE.stepSize','0.000001','0.00001','BTC','exact_event','2021-08-26T06:00:00Z',None),
        ('STEP21','ETHUSDT',SPOT,'LOT_SIZE.stepSize','0.00001','0.0001','ETH','exact_event','2021-08-26T06:00:00Z',None),
        ('MINSPOT23','BTCUSDT',SPOT,'minimum_order_notional','10','5','USDT','deadline',None,'2023-08-31T03:00:00Z'),
        ('MINSPOT23','ETHUSDT',SPOT,'minimum_order_notional','10','5','USDT','deadline',None,'2023-08-31T03:00:00Z'),
        ('MINFUT23','BTCUSDT',FUT,'minimum_order_notional','5','100','USDT','deadline',None,'2023-11-02T10:00:00Z'),
        ('MINFUT23','ETHUSDT',FUT,'minimum_order_notional','5','20','USDT','deadline',None,'2023-11-02T10:00:00Z'),
        ('MINBTC26','BTCUSDT',FUT,'minimum_order_notional','100','50','USDT','approximate_rollout','2026-04-14T06:30:00Z','2026-04-14T10:30:00Z'),
    ]
    for sid,symbol,market,param,before,after,unit,kind,start,end in events:
        t=temporal(kind)
        if kind=='exact_event': t['effective_at_utc']=start
        else: t.update(earliest_utc=start,latest_utc=end)
        t['label_original']={'deadline':'by; extremo inferior no acreditado','approximate_rollout':'inicio anunciado y duración aproximada; no deadline rígido','exact_event':'instante explícito UTC'}[kind]
        row='USDT  | 10 USDT  | 5 USDT' if sid=='MINSPOT23' else symbol
        add(f'EVENT_{sid}_{symbol}',symbol,market,param,dict(before=before,after=after),dict(before=dec(before),after=dec(after)),unit,[sid],f'Fila {row}; encabezados Before/After y párrafo temporal',status='evento_respaldado',time=t,app=dict(orders='nuevas órdenes; tipo concreto/banderas no especificados por este anuncio' if 'MIN' in sid else 'órdenes con cantidad/precio',existing_orders_affected=False,existing_positions_affected=None,position_increases=None,grid_exception='Futures Grid expira si no cumple mínimo; enmienda 2023-10-30' if sid=='MINFUT23' else None),proof=dict(kind='text_tokens',tokens=[symbol] if sid!='MINSPOT23' else ['USDT','10 USDT','5 USDT']),preperiod=sid=='STEP21')

    specs=[('MARG22','ETHUSDT',25,34,'2022-09-13T07:00:00Z',None,True),('MARG23','BTCUSDT',27,36,'2023-12-24T09:35:00Z',None,False),('MARG23','ETHUSDT',40,50,'2023-12-24T09:35:00Z',None,False),('MARG24','BTCUSDT',25,36,'2024-05-28T10:30:00Z','2024-05-28T11:00:00Z',False),('MARG24','ETHUSDT',40,51,'2024-05-28T10:30:00Z','2024-05-28T11:00:00Z',False),('MARGBTC25','BTCUSDT',40,51,'2025-06-17T06:30:00Z','2025-06-17T07:30:00Z',True),('MARGAUG25','BTCUSDT',52,63,'2025-08-19T06:30:00Z','2025-08-19T07:30:00Z',True),('MARGAUG25','ETHUSDT',67,78,'2025-08-19T06:30:00Z','2025-08-19T07:30:00Z',True)]
    extracted_tables=[]
    for sid,symbol,lo,hi,start,end,affected in specs:
        lines={int(n):v for n,v in re.findall(r'^L(\d+): (.*)$',articles[sid],re.M)}
        # Una sola versión de filas para este bloque; la segunda consulta de MARGAUG25 contiene sólo enmiendas.
        for side in ['before','after']:
            rows=[]
            for n in range(lo,hi+1):
                raw=lines[n]; cells=[c.strip() for c in raw.split('|')]
                if len(cells)==4:
                    if cells[0] in ['NA','N/A']: cells=[None,None,None]+cells[1:]
                    elif cells[-1] in ['NA','N/A']: cells=cells[:3]+[None,None,None]
                assert len(cells)==6,(sid,n,cells)
                cells=cells[:3] if side=='before' else cells[3:]
                if cells[0] is None: continue
                lev,pos,rate=cells
                match=re.fullmatch(r'([\d,]+) < Position ≤ ([\d,]+)',pos); assert match,(sid,pos)
                rows.append(dict(floor_usdt=dec(match[1].replace(',','')),cap_usdt=dec(match[2].replace(',','')),floor_inclusive=False,cap_inclusive=True,maintenance_rate=dec(Decimal(rate.rstrip('%'))/100),maximum_initial_leverage=max(map(int,re.findall(r'\d+',lev))),maintenance_amount_published=None,original=dict(leverage=lev,position=pos,rate_percent=rate),source_line=n,side=side))
            fid=f'TIERS_{sid}_{symbol}_{side}'
            t=temporal('relative_before' if side=='before' else 'approximate_rollout' if end else 'exact_event')
            if side=='before': t.update(reference_event_utc=start,note='Antes del evento según el anuncio; comienzo y duración desconocidos.')
            elif end: t.update(earliest_utc=start,latest_utc=end,label_original='within approximately; no instante atómico ni fin garantizado')
            else: t['effective_at_utc']=start
            f=add(fid,symbol,FUT,'maintenance_tiers',[r['original'] for r in rows],rows,'USDT / fraction / leverage',[sid],f'Bloque {symbol}; {side}; líneas {lo}-{hi}; encabezados leverage, notional, maintenance',status='observacion_puntual' if side=='before' else 'evento_respaldado',time=t,app=dict(orders=None,existing_orders_affected=None,existing_positions_affected=affected,position_increases=None,margin_mode='regla de contratos USD-M; no se traslada sección Portfolio Margin',new_account_limit='más de 125x no disponible primeros 30 días; aclaración publicada 2025-08-25, sin vigencia anterior inferida' if sid=='MARGAUG25' else None),proof=dict(kind='margin_table',line_start=lo,line_end=hi,side=side),announcement_published_after_effective=(sid=='MARG23'))
            extracted_tables.append(dict(fact_id=fid,source_id=sid,symbol=symbol,side=side,rows=rows))
            deduction=Decimal(0); previous=Decimal(0); amounts=[]
            for r in rows:
                deduction+=Decimal(r['floor_usdt'])*(Decimal(r['maintenance_rate'])-previous); amounts.append(dec(deduction)); previous=Decimal(r['maintenance_rate'])
            add(fid+'_DERIVED',symbol,FUT,'maintenance_deduction_derived',None,amounts,'USDT',[sid],fid,status='derivado',time=t,proof=dict(kind='derived_tiers',input_fact_id=fid),derivation=dict(formula='D_0=0; D_i=D_(i-1)+floor_i*(rate_i-rate_(i-1)); MM(N)=N*rate_i-D_i',assumptions=['continuidad entre tramos','deducción inicial cero','no es cum publicado ni cargo histórico acreditado']))
    save(B/'extraidos/tablas_margen.json',extracted_tables)
    # Semántica publicada actualmente; la fecha de publicación antigua no se traslada al cuerpo enmendado.
    for symbol in SYMS:
        add('LIQ_BASIS_'+symbol,symbol,FUT,'liquidation_fee_basis','Number of Contracts * Trade Price','execution_notional','formula',['FAQ_LIQ'],'Insurance Clearance fee calculation, USD-M; líneas 94-106',time=temporal('current_document'),proof=dict(kind='text_tokens',tokens=['Insurance Clearance Fee = Notional Value * Fee Rate','Notional Value = Number of Contracts * Trade Price']),app=dict(orders='liquidación forzada',bankrupt_position_exception=True,simultaneous_regular_trading_fee=None,historical_version_verified=False))
        add('PENDING_FEE_DATE_'+symbol,symbol,FUT,'taker_fee_change_effective_date',None,None,'UTC unknown',['A1','A3','A4'],'No anuncio operativo localizado; capturas no cierran intervalo operativo',status='pendiente',time=temporal(),gap='Falta fuente primaria que vincule Regular USDT-M 0.04%→0.05% con inicio efectivo y alcance.')
        add('SENSITIVITY_FEE_'+symbol,symbol,FUT,'taker_fee_sensitivity',None,['0.0004','0.0005'],'fraction',['A1','A3'],'Diseño posterior, no ejecutado',status='supuesto',time=temporal(),proposal='Comparar 4 y 5 pb y barrer fechas de transición como escenarios, incluidas fuera del corredor documental; no estimación de fecha histórica.')
    for sid,param,val,why in [('OUT_VIP1','taker_fee_change','0.04% -> 0.05%','VIP1, no Regular/VIP0'),('OUT_TAKER','taker_program_discount','up to 25%','programa con solicitud y volumen mínimo; no tarifa general ni cuota de volumen convertida en tarifa'),('OUT_BTCU','taker_fee','0%','BTC/U = United Stables, no BTC/USDT')]:
        add('EXCLUDE_'+sid,'BTCU' if sid=='OUT_BTCU' else 'BTCUSDT',SPOT if sid=='OUT_BTCU' else FUT,param,val,None,'not applicable',[sid],why,status='fuera_de_alcance',exclusion_reason=why)
    # Cobertura: únicamente intervalos finitos explícitos suman tiempo; puntos y eventos no rellenan días.
    required=['taker_fee','taker_fee_base','LOT_SIZE.stepSize','LOT_SIZE.minQty','LOT_SIZE.maxQty','MARKET_LOT_SIZE.stepSize','MARKET_LOT_SIZE.minQty','MARKET_LOT_SIZE.maxQty','PRICE_FILTER.tickSize','PRICE_FILTER.minPrice','PRICE_FILTER.maxPrice','minimum_order_notional','maximum_order_notional']
    keys={(f['symbol'],f['market'],f['parameter']) for f in facts if f['status']!='fuera_de_alcance'}
    for sym in SYMS:
        for market in [SPOT,FUT]:
            keys.update((sym,market,p) for p in required)
            if market==FUT: keys.update((sym,market,p) for p in ['maintenance_tiers','maintenance_amount_published','liquidationFee','liquidation_fee_basis','liquidation_regular_fee'])
    coverage=[]
    for f in facts:
        if f['status']=='fuera_de_alcance': continue
        t=f['temporal']; seconds=0
        if f['status']=='intervalo_respaldado': seconds=int((iso(t['valid_to_exclusive_utc'])-iso(t['valid_from_utc'])).total_seconds())
        coverage.append(dict(symbol=f['symbol'],market=f['market'],parameter=f['parameter'],status=f['status'],kind=t['kind'],start_utc=t['valid_from_utc'] or t['effective_at_utc'] or t['earliest_utc'] or '',end_utc=t['valid_to_exclusive_utc'] or t['latest_utc'] or '',observed_at_utc=t['observed_at_utc'] or '',fact_ids=f['id'],source_ids=';'.join(f['source_ids']),counted_seconds=str(seconds),note=t.get('note') or t.get('label_original') or 'Sin continuidad presumida; null no es vigencia infinita.'))
    for sym,market,param in sorted(keys):
        cuts=[(START,END)]
        for row in coverage:
            if (row['symbol'],row['market'],row['parameter'])!=(sym,market,param) or row['status']!='intervalo_respaldado': continue
            a,z=row['start_utc'],row['end_utc']; new=[]
            for left,right in cuts:
                if z<=left or a>=right: new.append((left,right))
                else:
                    if left<a: new.append((left,a))
                    if z<right: new.append((z,right))
            cuts=new
        for a,z in cuts:
            coverage.append(dict(symbol=sym,market=market,parameter=param,status='pendiente',kind='gap_continuity',start_utc=a,end_utc=z,observed_at_utc='',fact_ids='',source_ids='',counted_seconds='0',note='Continuidad no certificada. Puede contener observaciones o eventos de duración cero; no significa desconocer todos los valores puntuales.'))
    with (B/'cobertura.csv').open('w',encoding='utf-8',newline='') as out:
        w=csv.DictWriter(out,fieldnames=list(coverage[0])); w.writeheader(); w.writerows(coverage)
    save(B/'reglas_historicas.json',dict(schema='historical_documentary_facts_v1',generated_at_utc=generated,scope=dict(start_utc=START,end_exclusive_utc=END,symbols=SYMS,markets=[SPOT,FUT],profile=PROFILE,spot_credit=False,futures_margin='isolated',chosen_leverage=2),loadable_by_rulebook=False,continuity_default=False,null_valid_to_means='unknown, never infinite',status_definitions=dict(intervalo_respaldado='intervalo finito explícito y alcance definido',evento_respaldado='cambio anunciado, exacto/deadline/rollout según temporal.kind; no duración continua',observacion_puntual='captura o tabla relativa sin continuidad',derivado='cálculo etiquetado, no dato publicado',supuesto='escenario propuesto sin ejecución',contradictorio='diferencia no resuelta para misma regla y alcance',pendiente='evidencia insuficiente',fuera_de_alcance='mercado, perfil, par u objeto distinto'),facts=facts))
    save(B/'fuentes.json',dict(schema='historical_sources_v1',generated_at_utc=generated,sources=list(sources.values())))
    for wp in sorted((B/'originales').glob('W*_web.json')):
        r=read(wp)
        for operation,items in r['request'].items():
            if operation=='response_length': continue
            if not isinstance(items,list): items=[items]
            for item in items:
                target=item.get('ref_id') if isinstance(item,dict) else None
                chunks=[c for c in r['response'].split('-'*80) if target and (target in c.strip().split('\n')[0] or re.search(r'"ref_id"\s*:\s*"'+re.escape(target)+r'"',c))]
                failed=[c for c in chunks if 'Internal Error' in c or 'No matching text found' in c or re.search(r'Redirected to URL: https://www.binance.com/[^\s;]+/announcement;',c)]
                failure='Una apertura/find devolvió error o índice sin artículo; ver respuesta conservada. No demuestra ausencia de evidencia.' if failed else None
                logs.append(dict(query_or_url=item,queried_at_utc=r['queried_at_utc'],timestamp_semantics='registrado al recibir respuesta web, no timestamp de captura histórica',tool='web.run '+operation,result='respuesta completa conservada en '+wp.relative_to(B).as_posix(),failure=failure,individual_result_association='URL/ref_id cotejado' if chunks else 'respuesta agrupada; no se adjudican snippets a una consulta individual',inclusion_exclusion='Sólo documentos abiertos con filas/cuerpo pertinentes respaldan hechos. Search, Square, índices y terceros son pistas. Ver fuentes.json para decisión por fuente.',record=wp.relative_to(B).as_posix()))
    for line in (B/'descargas.jsonl').read_text(encoding='utf-8').splitlines():
        r=json.loads(line)
        if r['phase']=='result':
            sid=r['id']; r['inclusion_exclusion']=sources.get(sid,{}).get('exclusion_reason') or 'Copia preservada; alcance en fuentes.json'
        logs.append(r)
    with (B/'busquedas.jsonl').open('w',encoding='utf-8',newline='\n') as out:
        for r in logs: out.write(json.dumps(r,ensure_ascii=False)+'\n')
    save(B/'resumen_extraccion.json',dict(generated_at_utc=generated,sources=len(sources),facts=len(facts),coverage_rows=len(coverage),api_snapshots=usable_api,margin_tables=len(extracted_tables),margin_rows_before=sum(len(t['rows']) for t in extracted_tables if t['side']=='before'),margin_rows_after=sum(len(t['rows']) for t in extracted_tables if t['side']=='after'),status_counts={s:sum(f['status']==s for f in facts) for s in sorted({f['status'] for f in facts})}))
    print(json.dumps(read(B/'resumen_extraccion.json'),ensure_ascii=False))

if __name__=='__main__': main()

"""Descarga publica acotada; solo escribe dentro de este paquete nuevo."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import time
import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

def log(data):
    with (BASE / 'descargas.jsonl').open('a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(data, ensure_ascii=False) + '\n')

def extract(source_id, body):
    soup = BeautifulSoup(body, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else None
    tables = []
    for ti, table in enumerate(soup.find_all('table')):
        rows = []
        for ri, row in enumerate(table.find_all('tr')):
            rows.append({'row_index': ri, 'cells': [dict(text=c.get_text(' ', strip=True), rowspan=int(c.get('rowspan', 1)), colspan=int(c.get('colspan', 1)), tag=c.name) for c in row.find_all(['td', 'th'], recursive=False)]})
        tables.append({'table_index': ti, 'rows': rows})
    embedded = []
    for si, script in enumerate(soup.find_all('script')):
        if script.get('type') in ['application/json', 'application/ld+json'] or script.get('id') in ['__NEXT_DATA__', '__APP_DATA']:
            try:
                embedded.append({'script_index': si, 'id': script.get('id'), 'type': script.get('type'), 'value': json.loads(script.get_text())})
            except (ValueError, TypeError):
                pass
    for node in soup(['script', 'style', 'noscript']):
        node.decompose()
    text = soup.get_text('\n', strip=True)
    text_file = BASE / 'extraidos' / (source_id + '.txt')
    text_file.write_text(text, encoding='utf-8', newline='\n')
    write_json(BASE / 'extraidos' / (source_id + '_tablas.json'), tables)
    if embedded:
        write_json(BASE / 'extraidos' / (source_id + '_embedded.json'), embedded)
    return {'title': title, 'text_path': str(text_file.relative_to(BASE)).replace('\\', '/'), 'text_sha256': digest(text_file.read_bytes()), 'table_count': len(tables), 'text_chars': len(text), 'contains_no_records_found': 'No records found' in text, 'embedded_json_count': len(embedded)}

def fetch(source_id, url, attempts=1):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', source_id):
        raise ValueError('Invalid source id')
    if (BASE / 'originales' / (source_id + '.meta.json')).exists():
        raise ValueError('No overwrite: ' + source_id)
    for attempt in range(1, min(attempts, 3) + 1):
        started = now()
        log({'phase': 'request', 'id': source_id, 'query_or_url': url, 'queried_at_utc': started, 'tool': 'terminal requests.get', 'attempt': attempt, 'timeout_connect_read_seconds': [8, 22]})
        try:
            response = requests.get(url, timeout=(8, 22), headers={'User-Agent': 'HistoricalSourceResearch/1.0 (public read-only)', 'Accept-Encoding': 'gzip, deflate'})
            body = response.content
            file = BASE / 'originales' / (source_id + '.body')
            file.write_bytes(body)
            headers = {k: v for k, v in response.headers.items() if k.lower() != 'set-cookie'}
            metadata = {'id': source_id, 'original_url': url, 'final_url': response.url, 'requested_at_utc': started, 'retrieved_at_utc': now(), 'http_status': response.status_code, 'headers': headers, 'redirects': [{'url': h.url, 'status': h.status_code, 'location': h.headers.get('Location')} for h in response.history], 'file': file.relative_to(BASE).as_posix(), 'bytes': len(body), 'sha256': digest(body), 'hash_representation': 'requests.Response.content bytes exactly saved; automatic HTTP content decompression by requests if Content-Encoding is set; not raw wire/chunk bytes', 'automatic_decompression': bool(response.headers.get('Content-Encoding')), 'extraction': extract(source_id, body) if body else None, 'attempt': attempt}
            write_json(BASE / 'originales' / (source_id + '.meta.json'), metadata)
            log({'phase': 'result', 'id': source_id, 'query_or_url': url, 'queried_at_utc': now(), 'tool': 'terminal requests.get', 'result': 'HTTP ' + str(response.status_code), 'bytes': len(body), 'failure': response.status_code >= 400 or not body, 'inclusion_reason': 'preserved retrieval; semantic suitability requires review', 'metadata': 'originales/' + source_id + '.meta.json'})
            return metadata
        except requests.RequestException as exc:
            log({'phase': 'result', 'id': source_id, 'query_or_url': url, 'queried_at_utc': now(), 'tool': 'terminal requests.get', 'result': None, 'failure': str(exc), 'attempt': attempt, 'exclusion_reason': 'technical failure, not evidence of absence'})
            if attempt == min(attempts, 3):
                return {'id': source_id, 'error': str(exc)}
            time.sleep(2 ** attempt)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('id', nargs='?')
    parser.add_argument('url', nargs='?')
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--attempts', type=int, default=1)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding='utf-8')) if args.plan else [{'id': args.id, 'url': args.url}]
    for item in plan:
        result = fetch(item['id'], item['url'], args.attempts)
        print(json.dumps({k: v for k, v in result.items() if k not in ['headers', 'redirects']}, ensure_ascii=False), flush=True)

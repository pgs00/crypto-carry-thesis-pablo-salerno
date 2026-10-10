"""UTF-8, local document links and raster validity, with external audit outputs."""

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]

from scripts.return_capital.common import read_json, sha256, write_json  # noqa: E402
from scripts.signal_sensitivity_integrity import (  # noqa: E402
    reject_overlaps,
    reject_sealed_ancestor,
)


def normalize_logs(work):
    for folder in ('ejecuciones','controles_base'):
        for p in (work/folder).glob('*.json'):
            if '__prior_' not in p.name and read_json(p).get('status')=='en_ejecucion':
                raise ValueError('Cannot normalize logs while a replay is active')
    records=[]
    for folder in ('pruebas','logs_corridas','controles'):
        for p in (work/folder).rglob('*.txt'):
            raw=p.read_bytes()
            if not raw.startswith((b'\xff\xfe',b'\xfe\xff')):
                raw.decode('utf8')
                continue
            before=sha256(p)
            backup=work/'logs_originales_binarios'/(p.relative_to(work).as_posix()+'.bin')
            if backup.exists():
                raise FileExistsError(backup)
            backup.parent.mkdir(parents=True,exist_ok=True)
            backup.write_bytes(raw)
            p.write_bytes(raw.decode('utf16').encode('utf8'))
            records.append(dict(path=p.relative_to(work).as_posix(),original_sha256=before,
                utf8_sha256=sha256(p),original_bytes_path=backup.relative_to(work).as_posix(),
                source_encoding='PowerShell UTF-16 BOM',target_encoding='UTF-8',text_preserved=True))
    write_json(work/'controles/normalizacion_logs_utf8.json',dict(records=records))
    return len(records)


def verify(package):
    from PIL import Image

    suffixes={'.md','.html','.csv','.json','.toml','.txt','.py','.svg','.sha256','.lock','.patch'}
    checked=[]
    for p in package.rglob('*'):
        if p.is_file() and p.suffix in suffixes:
            text=p.read_bytes().decode('utf8')
            if '\x00' in text or '\ufffd' in text:
                raise ValueError('Invalid text encoding: '+str(p))
            checked.append(p.relative_to(package).as_posix())
    links=[]
    for p in package.glob('*.md'):
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',p.read_text(encoding='utf8')):
            target=target.strip('<>')
            if target.startswith(('https://','http://','#','mailto:')):
                continue
            resolved=(p.parent/unquote(target.split('#')[0])).resolve()
            if not resolved.is_relative_to(package.resolve()) or not resolved.exists():
                raise ValueError('Broken or nonportable document link: '+p.name+' → '+target)
            links.append(dict(document=p.name,target=target))
    images=[]
    for p in (package/'figuras').glob('*.png'):
        with Image.open(p) as im:
            width,height=im.size
            im.verify()
        if min(width,height)<400:
            raise ValueError('Insufficient figure dimensions')
        images.append(dict(path=p.relative_to(package).as_posix(),width=width,height=height))
    return dict(passed=True,utf8_files=len(checked),links=links,images=images,
                scope='encoding, portable document targets and image decoding; visual review is separate')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--normalize-work',type=Path)
    p.add_argument('--package',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.normalize_work:
        reject_sealed_ancestor(a.normalize_work)
        print('Converted completed logs:',normalize_logs(a.normalize_work.resolve()))
    else:
        if not a.package or not a.output:
            p.error('--package and --output required')
        reject_sealed_ancestor(a.output)
        reject_overlaps(a.output,[a.package])
        if a.output.exists():
            raise FileExistsError(a.output)
        write_json(a.output,verify(a.package.resolve()))
        print('Artifact checks passed')

"""Verify the portable evidence and package without accessing original drives."""

import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

from PIL import Image

PACKAGE = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sin-manifiesto", action="store_true")
    args = parser.parse_args()
    sources = json.loads((PACKAGE / "fuentes_originales.json").read_text(encoding="utf-8"))
    for item in sources["files"]:
        assert digest(PACKAGE / item["archivo"]) == item["sha256"], item["archivo"]
    files = 0
    if not args.sin_manifiesto:
        path = PACKAGE / "manifiesto_paquete.json"
        assert digest(path) == (PACKAGE / "manifiesto_paquete.sha256").read_text().strip()
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for item in manifest["archivos"]:
            assert digest(PACKAGE / item["archivo"]) == item["sha256"], item["archivo"]
        files = len(manifest["archivos"])
    links = 0
    for path in PACKAGE.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert "\ufffd" not in text, path
        for match in re.finditer(r"\]\((<[^>]+>|[^\s)]+)\)", text):
            target = match.group(1).strip("<>")
            if target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            assert not re.match(r"[A-Za-z]:", target), (path, target)
            target = unquote(target.split("#", 1)[0])
            assert (path.parent / target).is_file(), (path, target)
            links += 1
    pngs = sorted((PACKAGE / "figuras").glob("*.png"))
    svgs = sorted((PACKAGE / "figuras").glob("*.svg"))
    assert len(pngs) == len(svgs) == 2
    for path in pngs:
        with Image.open(path) as image:
            assert all(abs(dpi - 300) < 0.01 for dpi in image.info["dpi"])
            image.verify()
    for path in svgs:
        assert ET.parse(path).getroot().tag.endswith("svg")
    with (PACKAGE / "diccionario_campos.csv").open(encoding="utf-8", newline="") as stream:
        dictionary = list(csv.DictReader(stream))
    documented = {(row["archivo"], row["campo"]) for row in dictionary}
    for path in list((PACKAGE / "tablas").glob("*.csv")) + list((PACKAGE / "datos").glob("*.csv")):
        with path.open(encoding="utf-8", newline="") as stream:
            for field in next(csv.reader(stream)):
                assert (path.relative_to(PACKAGE).as_posix(), field) in documented, (path, field)
    print(
        json.dumps(
            dict(
                fuentes_verificadas=len(sources["files"]),
                archivos_manifiesto=files,
                enlaces_locales_validos=links,
                png_300dpi=2,
                svg_validos=2,
                campos_documentados=len(dictionary),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

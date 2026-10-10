"""Check encoding and local links in an explicit list of active documentation."""

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CURRENT_DOCS = (
    "README.md",
    "docs/methodology.md",
    "docs/basis_audit_methodology.md",
    "docs/reproduction.md",
    "docs/continuous_mark_gaps.md",
    "docs/research/README.md",
    "docs/descarga_d.md",
    "docs/data_dictionary.md",
    "docs/escenario_investigacion.md",
    "entregas/entrega_3/README.md",
    "entregas/entrega_3/archivo/README.md",
    "entregas/entrega_3/continua_distribucion_20261010/README.md",
    "entregas/entrega_4/retorno_capital/20260927T154653Z_sofr/distribucion_20261010/README.md",
    "entregas/entrega_4/README.md",
    "docs/entrega_4/reglas_historicas/lectura_resultados.md",
    "docs/entrega_4/reglas_historicas/reproduccion.md",
    "docs/entrega_4/reglas_historicas/protocolo.md",
    "docs/entrega_4/reglas_historicas/decisiones_integracion.md",
    "docs/entrega_4/reglas_historicas/verificacion_publicacion.md",
    "entregas/entrega_4/costos_capacidad/20260927T200204Z/README.md",
    "data/research/README.md",
    "data/research/basis-audit-20260919/README.md",
    "data/manifests/README.md",
    "data/manifests/data_quality_report.md",
)
DESTINATION = r"(<[^>]+>|[^\s)]+)"
DIRECT = re.compile(r"!?\[[^\]\n]*\]\(\s*" + DESTINATION + r'(?:\s+["\'][^\n]*?["\'])?\s*\)')
DEFINITION = re.compile(r"^ {0,3}\[([^\]]+)\]:\s*" + DESTINATION, re.M)
REFERENCE = re.compile(r"!?\[([^\]\n]+)\]\[([^\]\n]*)\]")


def require(value, message):
    if not value:
        raise ValueError(message)


def check_document_encoding(content, name):
    """Detect replacement bytes in prose and formulas without rejecting URL queries."""
    prose = re.sub(r"https?://[^\s>)]+", "", content)
    damaged = re.search(r"\w\?\w|(?<!\w)\?(?=\w)|(?<=\s)\?(?=\s)", prose)
    require("\ufffd" not in content and not damaged, "Encoding damage in " + name)


def without_fences(content):
    return re.sub(r"^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?^ {0,3}\1[^\n]*$", "", content,
                  flags=re.M | re.S)


def heading_anchors(content):
    counts, anchors = {}, set()
    for heading in re.findall(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", without_fences(content), re.M):
        heading = DIRECT.sub(lambda m: re.search(r"\[([^\]]*)\]", m.group()).group(1), heading)
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        index = counts.get(slug, 0)
        counts[slug] = index + 1
        anchors.add(slug if index == 0 else f"{slug}-{index}")
    return anchors


def local_targets(content, name):
    content = re.sub(r"`+[^`\n]*`+", "", without_fences(content))
    def label(value):
        return " ".join(value.lower().split())

    definitions = {label(m.group(1)): m.group(2) for m in DEFINITION.finditer(content)}
    targets = list(definitions.values())
    content = DEFINITION.sub("", content)
    targets.extend(m.group(1) for m in DIRECT.finditer(content))
    content = DIRECT.sub("", content)
    for match in REFERENCE.finditer(content):
        reference = label(match.group(2) or match.group(1))
        require(reference in definitions, f"Missing reference in {name}: {reference}")
    content = REFERENCE.sub("", content)
    # Shortcut references resolve only when a matching definition exists.
    for match in re.finditer(r"!?\[([^\]\n]+)\]", content):
        reference = label(match.group(1))
        if reference in definitions:
            targets.append(definitions[reference])
    return targets


def check_links(root=None, documents=None):
    """Frozen snapshots are excluded by selection; links may target files or directories."""
    root = ROOT if root is None else Path(root)
    documents = CURRENT_DOCS if documents is None else documents
    checked = 0
    for name in documents:
        path = root / name
        require(path.is_file(), "Missing active document: " + name)
        content = path.read_text(encoding="utf-8")
        check_document_encoding(content, name)
        for raw in local_targets(content, name):
            target = raw.strip("<>")
            require(not re.match(r"[a-zA-Z]:", target), "Drive-specific link in " + name)
            parts = urlsplit(target)
            if parts.scheme or parts.netloc:
                continue
            relative, fragment = unquote(parts.path), unquote(parts.fragment)
            destination = (path.parent / relative).resolve() if relative else path
            require(destination.exists(), f"Broken link in {name}: {target}")
            if fragment and destination.suffix.lower() == ".md" and destination.is_file():
                require(fragment in heading_anchors(destination.read_text(encoding="utf-8")),
                        f"Broken heading in {name}: {target}")
            checked += 1
    return checked


def main():
    print(json.dumps(dict(status="verified", documents=len(CURRENT_DOCS),
                         local_links=check_links()), indent=2))


if __name__ == "__main__":
    main()

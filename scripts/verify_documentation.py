"""Check encoding and local links throughout the retained Markdown documents."""

import json
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
}


def markdown_documents(root):
    """Discover repository documentation without scanning environments or caches."""
    documents = []
    for directory, folders, files in os.walk(root):
        folders[:] = sorted(name for name in folders if name not in IGNORED_DIRECTORIES)
        documents.extend(
            (Path(directory) / name).relative_to(root).as_posix()
            for name in files
            if name.lower().endswith(".md")
        )
    return sorted(documents)


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
    return re.sub(
        r"^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?^ {0,3}\1[^\n]*$", "", content, flags=re.M | re.S
    )


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
    """Links may target files, directories, or headings in Markdown documents."""
    root = ROOT if root is None else Path(root)
    documents = markdown_documents(root) if documents is None else documents
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
                require(
                    fragment in heading_anchors(destination.read_text(encoding="utf-8")),
                    f"Broken heading in {name}: {target}",
                )
            checked += 1
    return checked


def main():
    documents = markdown_documents(ROOT)
    print(
        json.dumps(
            dict(
                status="verified",
                documents=len(documents),
                local_links=check_links(documents=documents),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

"""Current documentation checks do not need historical evidence or backtests."""

import pytest

from scripts import verify_documentation as verifier


def test_direct_image_directory_and_encoded_markdown_heading_links(tmp_path):
    (tmp_path / "folder").mkdir()
    (tmp_path / "chart.png").write_bytes(b"image fixture")
    (tmp_path / "target file.md").write_text(
        "# Reproducción: `BASE_E3`\n# Repeated\n# Repeated\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(
        "# Local\n[Direct](target%20file.md#reproducci%C3%B3n-base_e3)\n"
        "![Image](chart.png)\n[Directory](folder/)\n[Duplicate](target%20file.md#repeated-1)\n"
        "[Self](#local) [External](https://example.org/missing#anchor)\n",
        encoding="utf-8",
    )
    assert verifier.check_links(tmp_path, ("README.md",)) == 5


@pytest.mark.parametrize("target,message", [
    ("missing.md", "Broken link"), ("target.md#missing", "Broken heading"),
    ("missing.png", "Broken link"), ("C:/specific.md", "Drive-specific"),
])
def test_missing_files_images_anchors_and_drive_links_fail(tmp_path, target, message):
    (tmp_path / "target.md").write_text("# Exists\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(f"[Link]({target})\n", encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        verifier.check_links(tmp_path, ("README.md",))


def test_reference_definitions_full_collapsed_and_shortcut_links(tmp_path):
    (tmp_path / "target.md").write_text("# Referencia\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        '[Named][Source Ref] [source ref][] [source ref]\n'
        '[Source Ref]: <target.md#referencia> "Title"\n', encoding="utf-8"
    )
    assert verifier.check_links(tmp_path, ("README.md",)) >= 1


@pytest.mark.parametrize("content,message", [
    ("[Named][absent]\n", "Missing reference"),
    ("[Named][ref]\n[ref]: absent.md\n", "Broken link"),
    ("[Named][ref]\n[ref]: target.md#absent\n", "Broken heading"),
])
def test_reference_failures_are_reported(tmp_path, content, message):
    (tmp_path / "target.md").write_text("# Exists\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        verifier.check_links(tmp_path, ("README.md",))


def test_encoding_and_missing_active_document_fail(tmp_path):
    with pytest.raises(ValueError, match="Missing active document"):
        verifier.check_links(tmp_path, ("README.md",))
    (tmp_path / "README.md").write_text("# Reproducci?n\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Encoding damage"):
        verifier.check_links(tmp_path, ("README.md",))


def test_frozen_documents_and_code_examples_are_outside_active_checks(tmp_path):
    (tmp_path / "frozen.md").write_text("[Old](missing.md)\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        '```markdown\n[Example](missing.md)\n```\n`[Inline](absent.md)`\n', encoding="utf-8"
    )
    assert verifier.check_links(tmp_path, ("README.md",)) == 0

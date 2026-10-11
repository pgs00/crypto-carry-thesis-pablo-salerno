"""The editorial view cannot replace authenticated scientific or historical bytes."""

import json
import re
import shutil
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

from scripts import publish_thesis as publisher


@pytest.fixture
def view(tmp_path):
    return shutil.copytree(publisher.PUBLISHED, tmp_path / "continuous")


def reseal(view, mutate=None):
    manifest = json.loads((view / "manifest.json").read_bytes())
    if mutate is not None:
        mutate(manifest)
    content = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    (view / "manifest.json").write_bytes(content)
    (view / "manifest.sha256").write_bytes((publisher.digest(content) + "\n").encode())


def test_unlisted_file_is_rejected(view):
    (view / "unlisted.txt").write_bytes(b"unexpected")
    with pytest.raises(ValueError, match="membership"):
        publisher.verify(view)


@pytest.mark.parametrize("name", [
    "figuras/hipotesis.svg", "tablas/resultados_periodos.csv", "tablas/equity_diario.csv",
])
def test_resealing_scientific_files_does_not_change_historical_identity(view, name):
    (view / name).write_bytes((view / name).read_bytes() + b"\n<!-- changed -->\n")
    reseal(view, lambda manifest: manifest["file_hashes"].update(
        {name: publisher.digest((view / name).read_bytes())}
    ))
    with pytest.raises(ValueError, match="Historical member"):
        publisher.verify(view)


def test_current_view_authenticates_every_original_member(view):
    result = publisher.verify(view)
    assert result["editorial_derivation"]["original_members_verified"] == 19
    assert result["editorial_derivation"]["preserved_tables_and_figures"] == 18
    assert result["published_files"] == 22


@pytest.mark.parametrize("name,message", [
    ("README.md", "Historical member"),
    ("manifest.json", "Historical manifest identity"),
    ("manifest.sha256", "Historical manifest sidecar"),
])
def test_resealing_historical_snapshot_cannot_replace_originals(view, name, message):
    relative = f"{publisher.HISTORICAL_VIEW}/{name}"
    (view / relative).write_bytes((view / relative).read_bytes() + b"\n")
    reseal(view, lambda manifest: manifest["file_hashes"].update(
        {relative: publisher.digest((view / relative).read_bytes())}
    ))
    with pytest.raises(ValueError, match=message):
        publisher.verify(view)


def test_resealing_an_unapproved_readme_change_fails(view):
    readme = view / "README.md"
    readme.write_bytes(readme.read_bytes().replace(b"10785.76", b"99999.99"))
    reseal(view, lambda manifest: manifest["file_hashes"].update(
        {"README.md": publisher.digest(readme.read_bytes())}
    ))
    with pytest.raises(ValueError, match="Unauthorized editorial README"):
        publisher.verify(view)


def test_source_identity_cannot_be_rewritten_and_resealed(view):
    reseal(view, lambda manifest: manifest.update(generator_sha256="0" * 64))
    with pytest.raises(ValueError, match="Historical source or generator"):
        publisher.verify(view)


def test_editorial_policy_cannot_be_removed_and_resealed(view):
    reseal(view, lambda manifest: manifest.pop("distribution"))
    with pytest.raises(ValueError, match="Unknown editorial derivation"):
        publisher.verify(view)


def remove_snapshot(view, drop_policy):
    historical = view / publisher.HISTORICAL_VIEW
    for name in ("README.md", "manifest.json", "manifest.sha256"):
        (historical / name).unlink()
    historical.rmdir()
    historical.parent.rmdir()

    def update(manifest):
        manifest["file_hashes"] = {k: v for k, v in manifest["file_hashes"].items()
                                   if not k.startswith(publisher.HISTORICAL_VIEW + "/")}
        if drop_policy:
            manifest.pop("distribution")
            manifest.pop("distribution_revision")

    reseal(view, update)


def test_identifiable_copy_cannot_drop_entire_derivation_and_reseal(view):
    remove_snapshot(view, drop_policy=True)
    with pytest.raises(ValueError, match="Unknown editorial derivation"):
        publisher.verify(view)


def test_public_destination_requires_editorial_provenance(view, monkeypatch):
    remove_snapshot(view, drop_policy=True)
    reseal(view, lambda manifest: manifest.update(
        generator_sha256=publisher.digest(Path(publisher.__file__).read_bytes())
    ))
    monkeypatch.setattr(publisher, "PUBLISHED", view)
    with pytest.raises(ValueError, match="Unknown editorial derivation"):
        publisher.verify(view)


def test_missing_snapshot_with_retained_descriptor_fails(view):
    remove_snapshot(view, drop_policy=False)
    with pytest.raises(ValueError, match="Historical snapshot is missing"):
        publisher.verify(view)


def test_disguised_copy_cannot_drop_provenance_and_reseal_a_changed_readme(view):
    remove_snapshot(view, drop_policy=True)
    readme = view / "README.md"
    readme.write_bytes(readme.read_bytes().replace(b"10785.76", b"99999.99"))

    def camouflage(manifest):
        manifest["generator_sha256"] = publisher.digest(Path(publisher.__file__).read_bytes())
        manifest["file_hashes"]["README.md"] = publisher.digest(readme.read_bytes())

    reseal(view, camouflage)
    with pytest.raises(ValueError, match="Regenerated README"):
        publisher.verify(view)


@pytest.fixture(scope="module")
def generated_source(tmp_path_factory):
    destination = tmp_path_factory.mktemp("generated_source") / "continuous"
    publisher.publish(destination)
    return destination


@pytest.fixture
def generated_view(generated_source, tmp_path):
    destination = shutil.copytree(generated_source, tmp_path / "continuous")
    files, _ = publisher.load_source()
    # Links in a fresh report are relative to its destination.
    (destination / "README.md").write_text(
        publisher.readme(files, destination), encoding="utf-8", newline="\n"
    )
    reseal(destination, lambda manifest: manifest["file_hashes"].update(
        {"README.md": publisher.digest((destination / "README.md").read_bytes())}
    ))
    return destination


@pytest.mark.parametrize("name", ["figuras/hipotesis.svg", "figuras/equity_drawdown.png"])
def test_regenerated_figure_cannot_be_changed_and_resealed(generated_view, name):
    path = generated_view / name
    if path.suffix == ".svg":
        path.write_bytes(path.read_bytes() + b"\n<!-- changed -->\n")
    else:
        shutil.copyfile(generated_view / "figuras/hipotesis.png", path)
    reseal(generated_view, lambda manifest: manifest["file_hashes"].update(
        {name: publisher.digest(path.read_bytes())}
    ))
    with pytest.raises(ValueError, match="Regenerated figure"):
        publisher.verify(generated_view)


def test_regenerated_view_cannot_drop_a_figure_and_reseal(generated_view):
    name = "figuras/hipotesis.svg"
    (generated_view / name).unlink()
    reseal(generated_view, lambda manifest: manifest["file_hashes"].pop(name))
    with pytest.raises(ValueError, match="Regenerated manifest membership"):
        publisher.verify(generated_view)


def test_generated_view_links_resolve_from_its_destination(generated_source):
    content = (generated_source / "README.md").read_text(encoding="utf-8")
    for link in re.findall(r"\]\(([^)]+)\)", content):
        parts = urlsplit(link)
        if parts.scheme == "file":
            path = Path(unquote(parts.path).lstrip("/"))
        else:
            assert not parts.scheme, link
            path = generated_source / unquote(parts.path)
        assert path.resolve().is_file(), link
    assert publisher.verify(generated_source)["status"] == "verified"


def test_generated_figures_ignore_ambient_plot_settings(tmp_path):
    files, _ = publisher.load_source()
    normal = tmp_path / "normal"
    changed = tmp_path / "changed"
    publisher.figures(files, normal)
    with publisher.plt.rc_context({"axes.facecolor": "pink", "lines.marker": "o"}):
        publisher.figures(files, changed)
        assert publisher.plt.rcParams["axes.facecolor"] == "pink"
        assert publisher.plt.rcParams["lines.marker"] == "o"
    assert {p.name for p in normal.iterdir()} == {p.name for p in changed.iterdir()}
    for path in normal.iterdir():
        assert path.read_bytes() == (changed / path.name).read_bytes(), path.name

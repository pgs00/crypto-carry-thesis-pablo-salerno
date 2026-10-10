"""Archive an already verified documentary distribution without resealing it."""

import argparse
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent / "distribucion_20261010"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def deliver(package, target):
    package, target = Path(package).resolve(), Path(target).resolve()
    sidecar = target.with_suffix(target.suffix + ".sha256")
    if target.exists() or sidecar.exists() or target.is_relative_to(package):
        raise ValueError("Choose a new archive outside the source distribution")
    subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(package / "scripts/verificar_paquete.py")],
        check=True,
    )
    members = sorted(p for p in package.rglob("*") if p.is_file())
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in members:
            archive.write(path, package.name + "/" + path.relative_to(package).as_posix())
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(members):
            raise ValueError("Archive inventory or CRC differs")
        for path in members:
            name = package.name + "/" + path.relative_to(package).as_posix()
            if hashlib.sha256(archive.read(name)).hexdigest() != digest(path):
                raise ValueError("Archive member changed: " + name)
    sidecar.write_text(digest(target) + "\n", encoding="ascii")
    print(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=PACKAGE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    deliver(args.package, args.output)

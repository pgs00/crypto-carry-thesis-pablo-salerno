"""Inventario de lectura; copia real aislada de v2, sin borrar ni mover originales."""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

from auditar_etapa_a import read, regular_files, save, sha, table

sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--isolated", type=Path, required=True)
    args = parser.parse_args()
    root, out, isolated = args.root.resolve(), args.out.resolve(), args.isolated.resolve()
    assert not isolated.is_relative_to(root)
    isolated.mkdir(parents=True, exist_ok=False)
    base = root / "entregas/entrega_4/ejecucion_demoras/20260929T221620Z"
    old, current = "paquete_20260930T012056Z", "paquete_20260930T013915Z_v2"
    names = [old, current, "controles_base", "controles", "verificacion_final", "intentos",
             "ejecuciones", "logs_corridas", "logs_originales_binarios", "pruebas",
             "codigo_previo", "codigo_ejecutado"]
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", PYTHONDONTWRITEBYTECODE="1")
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], env=env).decode().strip()
    remote = subprocess.check_output(["git", "-C", str(root), "ls-remote", "origin",
                                      "refs/heads/codex/crypto-carry"], env=env).decode().strip()
    assert remote.split()[0] == head, "No se acredita publicacion actual"
    tracked = {}
    tree = subprocess.check_output(["git", "-C", str(root), "ls-tree", "-r", "-z", head,
                                    "--", base.relative_to(root).as_posix()], env=env)
    for record in tree.split(b"\0"):
        if record:
            meta, path = record.split(b"\t", 1)
            mode, kind, oid = meta.decode().split()
            if kind == "blob":
                tracked[path.decode()] = oid
    process = subprocess.Popen(["git", "-C", str(root), "cat-file", "--batch"], env=env,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    inventory, details = [], []
    for name in names:
        folder = base / name
        files = list(regular_files(folder))
        matching, different, local = 0, [], []
        for path in files:
            rel = path.relative_to(root).as_posix()
            oid = tracked.get(rel)
            if oid is None:
                local.append(rel)
                continue
            process.stdin.write((oid + "\n").encode())
            process.stdin.flush()
            header = process.stdout.readline().decode().split()
            content = process.stdout.read(int(header[2]))
            assert process.stdout.read(1) == b"\n"
            digest = hashlib.sha256(content).hexdigest()
            same = sha(path) == digest
            matching += same
            if not same:
                different.append(rel)
            details.append(dict(path=rel, git_blob=oid, bytes_sha256=digest, working_equal=same))
        result = subprocess.run(["rg", "-l", "-F", name, "docs", "entregas/entrega_4",
                                 "-g", "*.md", "-g", "*.json", "-g", "*.csv"], cwd=root,
                                  capture_output=True, env=env)
        assert result.returncode in (0, 1), result.stderr
        refs = [r.replace("\\", "/") for r in result.stdout.decode().splitlines()
                if not r.replace("\\", "/").startswith(folder.relative_to(root).as_posix()+"/")
                and "/estres_contrafactual/" not in r.replace("\\", "/")]
        inventory.append(dict(path=folder.relative_to(root).as_posix(), files=len(files),
            bytes=sum(p.stat().st_size for p in files), exact_published_blobs=matching,
            different_files=different, local_files=local, incoming_references=refs,
            publication_commit=head, publication_ref=remote))
        print(name, len(files), inventory[-1]["bytes"], "blobs", matching,
              "locales", len(local), "refs", len(refs), flush=True)
    process.stdin.close()
    assert process.wait() == 0
    save(out / "controles/inventario_limpieza.json", inventory)
    save(out / "controles/blobs_limpieza.json", details)
    old_manifest, new_manifest = read(base/old/"manifiesto_paquete.json"), read(base/current/"manifiesto_paquete.json")
    old_map = {r["path"]:r["sha256"] for r in old_manifest["members"]}
    new_map = {r["path"]:r["sha256"] for r in new_manifest["members"]}
    comparison = dict(previous_manifest_sha256=sha(base/old/"manifiesto_paquete.json"),
        current_manifest_sha256=sha(base/current/"manifiesto_paquete.json"),
        identical=sum(old_map[k]==new_map.get(k) for k in old_map),
        changed=[k for k in old_map if new_map.get(k)!=old_map[k]],
        added=[k for k in new_map if k not in old_map],
        unsuffixed_exists=(base/"paquete_20260930T013915Z").exists())
    save(out / "controles/comparacion_paquetes_b4.json", comparison)
    target = isolated / "v2"
    for source in regular_files(base/current):
        dest = target / source.relative_to(base/current)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        assert sha(source) == sha(dest)
    command = [sys.executable, "-B", "-X", "utf8",
               str(target/"herramientas/scripts/verify_execution_delays.py"),
               "--package", str(target), "--output", str(isolated/"control_v2_sin_anterior.json")]
    with (isolated/"verificacion.log").open("wb") as log:
        result = subprocess.run(command, cwd=target, env=env, stdout=log, stderr=subprocess.STDOUT)
    save(out/"controles/aislamiento_limpieza.json", dict(command=command, exit_code=result.returncode,
        isolated=str(isolated), copy_is_real=True, previous_package_present=False,
        original_repository_present=False, git_index_present=False, massive_data_argument=False,
        scope="verificador compacto; procedencia y enlaces se evalúan por separado"))
    shutil.copyfile(isolated/"verificacion.log", out/"controles/limpieza_verificacion.log")
    if (isolated/"control_v2_sin_anterior.json").exists():
        shutil.copyfile(isolated/"control_v2_sin_anterior.json", out/"controles/v2_sin_anterior.json")
    assert result.returncode == 0, "Verificacion compacta aislada fallo"
    # Audita enlaces locales de los documentos del paquete. No inventa redirecciones.
    import re
    from urllib.parse import unquote

    missing = []
    for doc in target.rglob("*.md"):
        if any(p in {"herramientas", "codigo_previo", "codigo_ejecutado", "codigo_referencia_base"}
               for p in doc.relative_to(target).parts):
            continue
        for link in re.findall(r"\]\(([^\s)]+)(?:\s+[^)]*)?\)", doc.read_text(encoding="utf-8-sig")):
            if "://" in link or link.startswith("#"):
                continue
            path = (doc.parent / unquote(link.split("#")[0])).resolve()
            if not path.exists():
                missing.append(dict(document=doc.relative_to(target).as_posix(), target=link,
                                    resolved=str(path), outside_package=not path.is_relative_to(target)))
    save(out / "controles/enlaces_copia_aislada.json", dict(missing=missing,
         absolute_historical_paths="registradas en comparacion y controles; no se reescriben",
         provenance_recalculation_without_old_package=False,
         explanation="v2 autentica la comparacion preservada; recalcular sus 1200 filas exige el paquete anterior o un archivo intacto recuperado"))
    table(out/"tablas/inventario_limpieza.csv", [dict(path=r["path"],bytes=r["bytes"],files=r["files"],
        published_exact=r["exact_published_blobs"],local=len(r["local_files"]),
        differing=len(r["different_files"]),incoming_references=len(r["incoming_references"])) for r in inventory])
    print("Verificador aislado",result.returncode,"enlaces ausentes",len(missing),flush=True)


if __name__ == "__main__":
    main()

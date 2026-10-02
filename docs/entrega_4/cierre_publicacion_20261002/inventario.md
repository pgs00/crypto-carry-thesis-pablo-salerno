# Inventario de conservación — 02/10/2026

**Cero bajas, movimientos o compresiones sustitutivas en A–D.** El
[CSV breve](inventario_conservacion.csv), de 39 registros, identifica los 14
paquetes, diferencias propias de C/D, equivalencias gzip y siete fuentes fuera
del registro histórico. Incluye rutas, tamaños, copia vigente, consumidores,
decisión y fundamento. Las filas tienen alcances distintos: no se suman entre sí.

La medición `before` usa exclusivamente el árbol Git inicial
`f1f4857fe53ac02585f739f7927031ed029da172`: incluye todas sus rutas de blobs,
excluye archivos no versionados, datos externos y metadatos de `.git`.

| Medida del árbol inicial completo | Cantidad |
| --- | ---: |
| Archivos / bytes lógicos por ruta | 15.913 / 5.538.635.736 |
| Blobs distintos / bytes lógicos distintos | 4.994 / 2.357.852.303 |
| Grupos de blobs repetidos | 2.940 |
| Ocurrencias / ocurrencias adicionales a una por grupo | 13.859 / 10.919 |
| Bytes de todas las ocurrencias repetidas | 4.430.720.824 |
| Bytes adicionales a una ocurrencia por grupo | 3.180.783.433 |

Son tamaños lógicos sin compresión, **no tamaño de `.git`, transferencia remota
ni ahorro realizable**. Git ya identifica los bytes repetidos mediante un mismo
OID. La reparación local del vigente B6 y los documentos nuevos se miden aparte;
no cambian este corte ni acreditan publicación.

**A — costos/capacidad.** Se conservan los cuatro parciales, el candidato completo
`225401Z` y el sello anterior `230722Z`, frente al vigente `231610Z`. Documentan
fallos de serialización, evolución de herramientas y la corrección de «sin corto»
con mark ausente a ND; tampoco se conserva cero cambios donde no hay pares
evaluables. La derivación del vigente referencia expresamente el sello previo.
Los 29 forecast CSV de los parciales coinciden exactamente con la descompresión
de diez gzip distintos del vigente. Los catálogos y verificadores anteriores
consumen las rutas originales. El parcial 02 quedó sin catálogo/verificador
propios: sus archivos conservan el intento incompleto; no se acreditó ausencia
de dependencias. La equivalencia gzip por sí sola no autoriza ninguna baja.

**B — ejecución/demoras.** El paquete anterior tiene 1.193 archivos idénticos,
nueve distintos y cuatro ausentes frente a v2. Los nueve incluyen siete miembros
y manifiesto/sidecar, consistente con el
[inventario previo](../inventario_limpieza_bloque5_20260930.md). V2 autentica el
manifiesto anterior; reproducir su comparación requiere los bytes del antecedente.
Se conserva aunque el vigente pueda verificarse de forma autónoma.

**C — estrés/contrafactual.** El candidato tiene 1.143 archivos idénticos y 37
distintos; 36 diferencias son sólo CRLF/LF, comprobadas en memoria sin modificar
archivos. `progreso_local.json` conserva el cierre posterior `completado`, frente
al snapshot `sellado_y_verificacion_final` del vigente. Sólo manifiesto y sidecar
faltan en el candidato. Se preservan ambos momentos y los bytes originales.

**D — estabilidad/incertidumbre.** El candidato conserva dos notas posteriores
al sello (`continuacion_local.md`, `plan_ejecucion.md`) y ocho rutas propias:
progreso, stdout/stderr del coordinador, un log `finalize__…` y cuatro locks de
ejecución. El exportador los excluye del sello por su función de estado mutable;
eso no demuestra que sean prescindibles en la historia. El intento `paquete_final`
omitió ambos `uv.lock`; el vigente agregó esos dos archivos, cinco registros de
reparación y el reparador. Cambiaron README, exportador, pruebas y los dos archivos
de sello. `estado_intentos.json` preserva expresamente el intento fallido.

Se contrastaron búsquedas directas con consumidores dinámicos: `build_cost_capacity`
copia configuraciones, `codigo_runner_v*`, controles y etapas; su verificador
consume catálogos y hashes exactos/gzip. `package_stress_counterfactual.seal`
copia y manifiesta el candidato mediante `rglob`; preparador/coordinador usan
esa raíz para contratos y progreso. `copy_final` de B6 excluye estados definidos
y valida ambos snapshots; su reparador lee y preserva el sello previo. Los
índices, cierres, manifiestos y registros se contrastaron con esas rutas. La
decisión no depende sólo de ausencia de menciones literales.

La omisión histórica de **`uv.lock`** es distinta del problema **CRLF/LF en Git**
de este cierre. La comprobación binaria del HEAD inicial leyó 2.487 blobs únicos,
1.011.018.402 bytes: los cinco sellos A–C verifican membresía, sidecars y todos
sus hashes. D tiene 156 desajustes sobre 654 miembros en el intento histórico y
157 sobre 662 en el vigente; ambos sidecars coinciden con su manifiesto. Véanse
el [resumen inicial](sellos_head_inicial.json) y el
[diagnóstico del vigente](diagnostico_miembros_b6.csv). **El intento histórico
no se repara ni normaliza.** La reparación autorizada del vigente se certifica
en los controles específicos del cierre.

El control existente `python -m scripts.verify_repository_evidence` terminó
**exit 1** en `verify_cleanup`: `Protected source changed: src/crypto_carry/config.py`.
La auditoría completa confirma 309 `unchanged_files`, 36 rutas `src/` y siete
fuentes fuera de sus hashes: config, costs, data/prescribed, diagnostics,
execution, reporting y strategy. Sus hashes observados/esperados están en el CSV.
El [registro histórico](../../repository_cleanup_manifest.json) corresponde al
commit `183496c486d333a0bec6bc086f15369376668192`, anterior al corte actual; no
se cambiaron sus hashes ni se debilitó el validador. No es una aprobación del
control ni un diagnóstico de enlaces rotos. Se entrega el
[stderr exacto](verificador_historico_stderr.txt), SHA-256
`0e6842019d18ee34eae8fdf77eb541d12052e6193f7473fa84d1adfdb8dbeb92`.

El cálculo exhaustivo se conserva como auxiliar fuera del sello en
`%TEMP%/cierre_publicacion_20261002_inventario/`: inventario completo, diferencias,
equivalencias gzip, `seals_head_before.json`, salida del control y
`verify_cleanup_actual.json`. El CSV entregado evita replicar ese volumen.

Reproducción de tamaños, grupos repetidos y comparaciones de los 14 paquetes,
desde la raíz, sin escribir archivos ni ejecutar el motor:

```powershell
@'
import collections, csv, subprocess
from pathlib import Path
head = "f1f4857fe53ac02585f739f7927031ed029da172"
tree = {}
for record in subprocess.check_output(["git", "ls-tree", "-r", "-l", "-z", head]).split(b"\0"):
    if record:
        meta, path = record.split(b"\t", 1)
        mode, kind, oid, size = meta.decode().split()
        tree[path.decode()] = (oid, int(size))
groups = collections.defaultdict(list)
for path, (oid, size) in tree.items():
    groups[oid].append(path)
dup = [paths for paths in groups.values() if len(paths) > 1]
assert len(tree) == 15913 and sum(v[1] for v in tree.values()) == 5538635736
assert len(groups) == 4994 and len(dup) == 2940
assert sum(tree[p[0]][1] for p in groups.values()) == 2357852303
assert sum(map(len, dup)) == 13859
assert sum(tree[p[0]][1]*len(p) for p in dup) == 4430720824
assert sum(tree[p[0]][1]*(len(p)-1) for p in dup) == 3180783433
path = Path("docs/entrega_4/cierre_publicacion_20261002/inventario_conservacion.csv")
for row in csv.DictReader(path.open(encoding="utf-8", newline="")):
    if row["tipo"] != "paquete":
        continue
    prefix, target = row["ruta"] + "/", row["copia_canonica"] + "/"
    a = {p[len(prefix):]: v for p,v in tree.items() if p.startswith(prefix)}
    b = {p[len(target):]: v for p,v in tree.items() if p.startswith(target)}
    assert len(a) == int(row["archivos"])
    assert sum(v[1] for v in a.values()) == int(row["bytes_logicos_git"])
    assert sum(p in b and v[0] == b[p][0] for p,v in a.items()) == int(row["identicos_misma_ruta"])
    assert sum(p in b and v[0] != b[p][0] for p,v in a.items()) == int(row["distintos_misma_ruta"])
    assert len(a.keys()-b.keys()) == int(row["solo_historico"])
    assert len(b.keys()-a.keys()) == int(row["solo_vigente"])
print("Inventario Git inicial y comparaciones: OK")
'@ | .\.venv\Scripts\python.exe -
```

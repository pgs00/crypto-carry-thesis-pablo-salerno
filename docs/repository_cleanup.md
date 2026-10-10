# Simplificación local del repositorio — 10/10/2026

Simplificación implementada y verificada localmente, sin commit ni publicación.
Recuperación completa comprobada y nueve verificadores compactos aprobados
antes y después de la retirada.

La rama inicial es `codex/crypto-carry`, commit
`57215943a5711352ba9cec89a2003039b0154eec`, con árbol limpio y **15.935 archivos
versionados presentes**. La navegación principal reúne [README](../README.md),
[metodología](methodology.md), [reproducción](reproduction.md) e
[índice E4](../entregas/entrega_4/README.md). Se conservan las limitaciones y
resultados adversos del estudio; los perfiles antiguos y prompts quedan
identificados como antecedentes.

El motor, configuraciones experimentales, datos originales, resultados, PDF,
paquetes vigentes y dependencias se preservan byte a byte. No se descargaron
mercados ni se ejecutaron nuevas carteras. No se modificaron rama, HEAD ni índice.
La reducción afecta al árbol visible; el historial Git permanece intacto.

El árbol conserva **8.231 archivos versionables presentes**: 8.227 ya
versionados y cuatro nuevos. Se retiraron 7.708 versionados y 109 cachés;
8.201 archivos retenidos mantienen sus bytes iniciales y 26 documentos,
scripts o tests fueron adaptados. La reducción neta de archivos es **48,35 %**.
Los inventarios completos quedan fuera del repositorio.

E3 conserva `--e3-reference <carpeta>` y usa extracción autenticada explícita;
su test lee el ZIP conservando las aserciones económicas. B5 toma su fixture
del paquete vigente. B3 deja de copiar el script de progreso archivado.
`scripts/verify_documentation.py` reutiliza el control de codificación y
verifica navegación vigente. No hay nuevas dependencias. README, metodología,
guía de reproducción e índice E4 concentran la navegación; decisiones y
trazabilidad distinguen las carteras continuas de los contratos anuales.

## Recuperacion de antecedentes

Respaldo externo canónico:
`C:\Users\pablo\Documentos\UCEMA\Tesina\Backtesting_antecedentes\limpieza_20261010\bytes_git`.
Su `README.md` y `recovery_inventory.csv` identifican cada ruta, tamaño, SHA-256
Git/local y fuente de recuperación. `initial_inventory.csv` conserva los
15.935 hashes iniciales; `initial_state.json`, HEAD, rama y hash del índice.

`git_antecedentes.zip` contiene **7.708 archivos** del commit citado,
exportados sin conversión EOL y contrastados uno por uno con sus blobs Git.
`variantes_locales.zip` conserva **367 variantes locales** (352 históricas E4
más 15 documentales/de herramientas) y **109 cachés ignoradas**. De los 7.817
archivos físicos, 7.341 se recuperan idénticos sólo desde Git; 367 necesitan la
variante local para reproducir los bytes retirados, y 109 existen únicamente
en el respaldo. La restauración combinada se comparó por inventario, tamaño
y SHA-256 antes de retirar material.

`recovery_verified.json` registra los hashes de ambos ZIP y el resultado;
`restauracion_comprobada/` contiene el árbol recuperado. El directorio padre
conserva el diagnóstico del primer `git archive`, que aplicaba conversión EOL;
usar **bytes_git** para la recuperación canónica. El ZIP
`fuentes_editables_iniciales.zip` conserva también los documentos, scripts y
tests anteriores a las adaptaciones; `fuente_adicional_basis_README.md`
preserva el README de basis antes de corregir sus enlaces a la extracción E3.

| Grupo | Rutas originales recuperables desde el commit | Archivos Git |
|---|---|---:|
| B3 anteriores | Bajo `entregas/entrega_4/costos_capacidad/20260927T200204Z/`: `candidato_parcial_01/` a `candidato_parcial_04/`, `paquete_20260927T225401Z/`, `paquete_20260927T230722Z/` | 3.699 |
| B4 anterior | `entregas/entrega_4/ejecucion_demoras/20260929T221620Z/paquete_20260930T012056Z/` | 1.202 |
| B5 candidato | `entregas/entrega_4/estres_contrafactual/20260930T214617Z/candidato/` | 1.180 |
| B6 anteriores | Bajo `entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/`: `candidato/` y `paquete_final/` | 1.326 |
| E3 extraída | `Paquete de evidencia/` y `entregas/entrega_3/archivo/paquete_redaccion/` | 262 |
| Administración | `docs/plans/`, `docs/entrega_4/historial_avance/`, `docs/entrega_4/cierre_publicacion_20261002/`, `docs/entrega_4/plan_b6_estabilidad_incertidumbre.md`, `docs/entrega_4/inventario_limpieza_bloque5_20260930.md`, `docs/progress.md`, `docs/repository_cleanup_manifest.json` | 35 |
| Herramientas concluidas | Bajo `scripts/`: `cost_capacity_progress.py`, `execution_delays_progress.py`, `repair_stability_uncertainty_package.py`, `verify_repository_evidence.py` | 4 |

La lista literal completa está en `retirement_roots.json` del respaldo. Para
recuperar sólo una versión Git sin cambiar el checkout, elegir una ruta de la
tabla y un ZIP nuevo:

```powershell
$archivoGit = Join-Path $env:TEMP ('antecedente_' + [guid]::NewGuid().ToString('N') + '.zip')
git -c core.autocrlf=false -c core.eol=lf archive --format=zip --output=$archivoGit `
  57215943a5711352ba9cec89a2003039b0154eec -- docs/plans
```

Para restaurar exactamente todo lo retirado, incluidas variantes y cachés,
desde la raíz del repositorio:

```powershell
$respaldo = 'C:\Users\pablo\Documentos\UCEMA\Tesina\Backtesting_antecedentes\limpieza_20261010\bytes_git'
$destino = Join-Path $env:TEMP ('tesina_antecedentes_' + [guid]::NewGuid().ToString('N'))
& '.\.venv\Scripts\python.exe' -B -X utf8 "$respaldo/restore_antecedentes.py" $destino
```

El restaurador exige destino nuevo fuera del repositorio/respaldo, comprueba
checksums y CRC, aplica Git más variantes y verifica los 7.817 archivos. No
sobrescribe el checkout. Conservar el respaldo: Git por sí solo no contiene
las variantes locales y cachés. No se necesita tag ni acceso a GitHub.
El comando publicado se probó además después de la retirada en otro temporal
nuevo: recuperación de los 7.817 archivos aprobada, código 0.

Los ZIP originales E3 y sus checksums siguen en el repositorio. La
[guía](reproduction.md#entrega-3-presentación-y-extracción-autenticada) explica
la extracción bajo demanda; sus 122/140 miembros coinciden con las copias
retiradas. Las seis cachés adicionales se preservan externamente.

Las reparaciones B6 requieren candidatos y versiones fallidas restaurados.
`Start-B6.ps1` conserva su destino histórico: restaurar ese contexto aislado o
proporcionar `-Candidate` explícito. Las auditorías E3 que exigen `Paquete de
evidencia/`, empaquetadores antiguos y controles ligados al estado Git de
entonces requieren un snapshot histórico aislado y sus fuentes originales.
No ejecutarlos en paquetes sellados ni presentarlos como controles del estado
actual. Los scripts de progreso podían volver etapas terminadas a pendiente;
sus copias congeladas siguen intactas en los paquetes.

El cierre del 02/10 y sus hashes del PDF corresponden a la versión anterior
de 31 páginas; el vigente tiene 24. Las versiones anteriores de metodología,
decisiones, trazabilidad y de este registro siguen en el commit y respaldo.
Los prompts continúan accesibles como procedencia; el de basis tiene un
consumidor real y se conserva en su ruta.

## Verificaciones

Referencia inicial ejecutada en Windows, Python 3.14.3 y dependencias
instaladas de `uv.lock`. Los nueve comandos congelados están en la
[guía](reproduction.md#2-verificación-offline-de-evidencia-compacta).

| Control | Antes | Después |
|---|---|---|
| BASE + padre, riesgo compacto, B1 capital/SOFR, B2–B6 | 9/9, código 0 | 9/9, código 0 |
| Pruebas acotadas | 104 aprobadas | 125 aprobadas: incluye las 104 y controles afectados |
| `python -m scripts.publish_thesis --verify` | Aprobado | Aprobado |
| ZIP E3 continuo / histórico v2 extraídos | Ambos aprobados | Ambos aprobados; 122/140 miembros preservados |
| Navegación vigente y Ruff acotado | Referencia previa archivada | 21 documentos / 241 enlaces válidos; Ruff aprobado |
| Inventario y bytes conservados | 15.935 hashes registrados | Sin cambios fuera de las 26 adaptaciones y 7.708 retiradas autorizadas |
| Recuperación combinada | 7.817 archivos exactos | Restaurador publicado aprobado sobre destino nuevo |
| Verificador de limpieza histórica | Fallo previo por hash de `src/crypto_carry/config.py` | Archivado con su contexto; no reejecutado |

El grupo adicional inicial aprobó ocho pruebas y omitió 11 de integración B3
sin `COST_CAPACITY_PACKAGE`. Las omitidas se ejecutaron después
con `COST_CAPACITY_PACKAGE` apuntando al paquete vigente: **11 aprobadas**.
Ese control adicional ocurrió durante la limpieza y se registra separado de
la referencia preedición.

Comandos completos, tiempos, códigos de salida y stdout/stderr se guardan en
`validaciones/` del respaldo canónico: `baseline/` y `after/` para la comparación,
`e3_baseline/` y `e3_after/`, `final_checks/`, y `closeout/` para los controles
posteriores a la última corrección documental. `final_audit.json` y
`final_inventory.csv` identifican los bytes finales; `active_dependencies.json`
clasifica las referencias históricas restantes. La revisión independiente
de consumidores y documentación no encontró hallazgos pendientes.
El verificador histórico exige hashes de la limpieza del 20/09: se conserva
con su contexto, sin cambiar el motor para hacerlo pasar.

El primer control documental tras la retirada encontró enlaces del README de
basis a la extracción E3 antigua. Se corrigieron hacia el ZIP y su extracción
autenticada; el control posterior aprobó. Las referencias restantes a rutas
retiradas pertenecen a recuperación, snapshots, fixtures o herramientas
históricas con restauración previa documentada; ningún import activo depende
de los cuatro scripts archivados.

El temporal predeterminado de pytest produjo `PermissionError` durante el
análisis previo. Se usa `-p no:cacheprovider` y `--basetemp` nuevo bajo
`.superpowers/cleanup_20261010/`, fuera de paquetes. Los logs se conservan
externamente y los temporales creados para esta limpieza se retiran al cerrar.

El antecedente B6 Linux sigue sin PASS integral por comparación literal CSV,
con diferencia máxima `6.938893903907228e-18`. No se cambian tolerancias; el
pase Windows actual no resuelve por inferencia la limitación Linux. No se
reabrieron fuentes masivas ni se repitieron experimentos. Verificar hashes de
figuras/PDF no constituye una revisión visual ni una aprobación académica.

## Revisión antes de commit

Revisar documentación, consumidores, lista de retiradas y disponibilidad del
respaldo externo. Conservar ZIP E3 y paquetes vigentes completos, incluido el
padre de reglas. Revisar rutas explícitas antes de preparar cambios; no usar
`git add .`. Revisar los 26 archivos modificados, cuatro nuevos y 7.708
retirados; el índice conserva sus **15.935 entradas** hasta que el usuario
decida prepararlo. SHA-256 del índice antes/después:
`c7fe8e0c22c2498e85d14d22a0320055b527f974cc8d76b2676f09d8a2c8fb10`.
No se creó commit, tag, rama ni publicación.

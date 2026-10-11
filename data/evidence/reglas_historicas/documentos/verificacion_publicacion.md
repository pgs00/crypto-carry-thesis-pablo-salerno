# Verificación de publicación — versión técnica preliminar

El comando nuevo verifica offline el paquete histórico publicado en
`894059e4ce318e51f25211d04be9f0202de90ae7`, con antecedente
`80feefc45872d2c48c33f3fbc3ebc9eb402eee6a`. Un desarrollo posterior puede cambiar
HEAD, rama, índice y motor. Ninguno de esos estados actuales debe coincidir con la
sesión de investigación para conservar la validez documental del paquete.

Desde la raíz del repositorio, en PowerShell:

```powershell
.venv/Scripts/python.exe -B scripts/verify_historical_rules_publication.py `
  --root . `
  --evidence data/research/historical-rules-followup-20260924T234206Z `
  --temp-dir $env:TEMP
```

Se imprime JSON; código de salida 0 significa que los controles ejecutados
aprobaron, y 1 indica un fallo. Los argumentos inválidos terminan con código 2.
`--output <archivo.json>` guarda además una copia mediante creación exclusiva:
debe ser una ruta nueva, con directorio padre existente, fuera de la evidencia.
Jamás sobrescribe resultados. `--temp-dir` debe existir y estar fuera del paquete;
las pruebas negativas actuales trabajan en memoria y no crean temporales.

## Tres resultados separados

1. `documentary_integrity`: comprueba los 196 miembros del manifiesto, tamaños y
   hashes, 52 fuentes, metadatos y extracciones, 345 hechos, 479 filas de cobertura
   y diez pruebas negativas. Incluye fuentes externas A1–A3. Reutiliza directamente
   `validate_facts`, `validate_coverage` y sus auxiliares originales; mantiene
   Decimal, anclas de tarifas, alcance VIP/mercado, filas de margen, deducciones,
   temporalidad y unión de intervalos. Agrega rechazo de rutas inseguras y filas
   duplicadas de cobertura incluso si cuentan cero días.
2. `provenance`: fija en el código el SHA-256 esperado del manifiesto y del
   verificador original. Cuando están disponibles los commits de referencia en
   Git local, compara los identificadores de los blobs publicados con los bytes
   de los 199 archivos del paquete y las tres dependencias externas. Para los 717
   archivos protegidos anteriores compara los blobs **entre padre y publicación**;
   no exige que los archivos actuales del motor sigan iguales. Git se consulta
   sin bloqueos opcionales, reemplazos de objetos ni recuperación de objetos por
   red. Sin `.git`, sin Git instalado o sin los commits locales, declara
   `git_status=unchecked` y explica la limitación. La integridad de contenido
   puede aprobar sin afirmar una comprobación de procedencia Git inexistente.
3. `original_session_audit`: preserva la fecha, resultado, HEAD e identificador
   del índice registrados originalmente. Los dos archivos de resultados también
   tienen hashes esperados fijos. Se informa siempre `reproduced=false`: no se
   recrea, recalcula ni certifica el índice físico de aquella sesión.

El verificador histórico sólo se compila después de comprobar su SHA-256 fijo,
con un nombre de módulo diferente de `__main__`. No se llama a su `main()` ni a
su `self_tests()` que escriben dentro del paquete; no se reemplaza texto de su
código. La carga no genera `__pycache__`. El comando y las funciones documentales
usan exclusivamente la biblioteca estándar, sin importar el motor de trading.
Las excepciones de datos o Git se convierten en **fallos explícitos**, nunca en
un aprobado. Las rutas se validan antes de abrirlas, incluidas referencias de
fuentes, metadatos, extracciones y registros web; se rechazan escapes mediante
`..`, rutas absolutas, unidades Windows y enlaces/junctions fuera de la raíz.

## Exportación y finales de línea

Una exportación mínima completa necesita:

- `scripts/verify_historical_rules_publication.py`;
- íntegro `data/research/historical-rules-followup-20260924T234206Z/`;
- `data/research/fee-archive-followup-20260918/A1.html`, `A2.html` y `A3.html`.

Puede ubicarse bajo otra raíz. No requiere datos de mercado ni resultados de
backtests. Para comprobar procedencia Git también necesita los objetos de ambos
commits. El comando no ejecuta fetch ni otras operaciones de red.

La exportación debe conservar **bytes**, no sólo texto equivalente. En Windows,
un checkout con `core.autocrlf=true` puede transformar las dependencias externas
A1–A3, aunque el paquete sellado tenga sus propios atributos. Ese caso falla por
un motivo real de integridad. Para un clon temporal nuevo, se usó checkout con
`git -c core.autocrlf=false checkout <referencia>`, sin modificar configuración
global. No se normalizan ni se reemiten hashes del paquete anterior.

## Evidencia de reproducción y aceptación

Los registros de ejecución se conservan bajo
`entregas/entrega_4/reglas_historicas/20260925T005436Z/verificacion_publicacion/`.
`tdd_red.*` registra el fallo previo a la implementación. Las reproducciones
exploratorias documentan los efectos de CRLF; la reproducción aislada final es
`reproduccion_copia_preservada_resumen.json`: utiliza un clon temporal y copia
los 717 archivos protegidos tras cotejar sus hashes originales, conservando
los bytes locales mixtos LF/CRLF. El verificador original vuelve a escribir
resultados **sólo en esa copia temporal** y rechaza el HEAD/índice posteriores.
La auditoría original del repositorio permanece intacta.

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_historical_rules_publication.py -q
.venv/Scripts/python.exe -m ruff check scripts/verify_historical_rules_publication.py tests/unit/test_historical_rules_publication.py
```

La aceptación cubre exportación relocalizada, commit posterior y modificación
legítima del código en un repositorio temporal, mutaciones de fuentes/registro/
extracciones/miembros, ausencia de A2, hash del manifiesto incorrecto, rutas
inseguras, carga de script adulterado, cobertura duplicada y los rechazos
financieros/documentales originales. Compara además los errores obtenidos por
llamadas directas a las funciones selladas con los del comando nuevo. Los tests
comprueban bytes de evidencia, resultados, HEAD e índice antes y después; los
únicos commits de prueba se producen en clones temporales. No hay commit ni
publicación de estos cambios en el repositorio del usuario.

Ejecución registrada: **29 pruebas aprobadas en 240,38 segundos**, sin omisiones;
Ruff aprobado, ambos con código 0. `verificacion_actual.json` registra el aprobado
documental y de procedencia sobre el repositorio real. El control de preservación
confirma 202 archivos de evidencia sin cambios, índice y HEAD intactos, y ausencia
de importaciones de `crypto_carry`. Windows no habilita symlinks de archivos para
este usuario; la prueba de escape usa un junction de directorio real y también
aprueba.

Un aprobado acredita los controles descritos: no certifica primera publicación,
continuidad histórica, interpretación financiera independiente ni todo el motor.
Esta guía corresponde a una versión técnica preliminar, con feedback docente
pendiente.

# Alcance de los controles

La suite SOFR cubre esta cuenta y comparación. No se ejecuta la suite general,
el motor ni los diagnósticos ya terminados. Compacto recalcula el postprocesamiento
SOFR desde los originales incluidos y autentica las copias carry contra el
manifiesto anterior. Con dependencia explícita también comprueba todos los bytes
del sello anterior. No es una nueva auditoría independiente del backtest.

El cierre verifica además hashes de los paquetes históricos, motor/configuración
y código previo protegido, así como HEAD e índice. Comparar hashes de fuentes
es preservación, no repetir su análisis económico.

Existe una incompatibilidad histórica ya documentada en la entrega previa:
`scripts.verify_repository_evidence` compara `src/crypto_carry/config.py` con
un manifiesto antiguo cuyo hash esperado es
`48e33a37be674afb309f7aa145c99cefaabcf1e3a1273bed11d729ad49ad7b36`.
El archivo actual, tanto al inicio de este encargo como antes del sello, tiene
`e04aba786423696e5bdba811600402ef465b97bf8ac06147b7a9c74f7b069dd5`.
No se vuelve a ejecutar ese control histórico como certificación del paquete
SOFR, ni se modifica el motor o aquel manifiesto para forzar su aprobación.
La evidencia original de ese límite permanece en la carpeta de auditoría previa.

No se afirma que la publicación histórica en GitHub incluya esta entrega. Esta
versión queda local, sin commit/push y sin cambios al índice. Las tres figuras
son representaciones estáticas PNG/SVG; sus datos y bytes quedan autenticados,
y la inspección visual se documenta separadamente.

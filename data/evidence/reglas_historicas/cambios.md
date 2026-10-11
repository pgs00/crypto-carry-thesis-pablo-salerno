# Cambios implementados y protección de antecedentes

El [diff completo de archivos existentes](cambios_codigo.patch) contiene 90 líneas agregadas y seis eliminadas: 81 agregadas/seis eliminadas en cinco módulos, más nueve líneas de atributos Git. No se cambian el verificador histórico, sus registros, los manifiestos sellados, las configuraciones originales ni los productos de Entrega 3.

| Archivo existente | Cambio y propósito | Líneas + / − |
| --- | --- | ---: |
| `src/crypto_carry/config.py` | Dos opciones opt-in de investigación y validación de sus valores. Omitir sus valores predeterminados al serializar conserva los diccionarios y hashes de configuración anteriores. | 12 / 0 |
| `src/crypto_carry/costs.py` | Separar la comisión efectivamente cobrada del costo estimado por el filtro. Delimitar la promoción BTC spot y mantener el costo fijo cuando lo prescribe el protocolo. | 20 / 2 |
| `src/crypto_carry/data/prescribed.py` | Dividir únicamente el intervalo BTC spot cuando se activa la promoción; registrar fuente y conocimiento experimental. Conservar los controles del RuleBook. | 42 / 1 |
| `src/crypto_carry/strategy.py` | Consultar la tarifa realizada con el inicio de la ventana VWAP y conservar el momento de contabilización. El resto de ejecución, funding y ledger se mantiene. | 4 / 2 |
| `src/crypto_carry/reporting.py` | Admitir un destino nuevo para las salidas, manteniendo la raíz original de lectura de datos y manifiestos. | 3 / 1 |
| `.gitattributes` | Preservar bytes de A1–A3 y de las carpetas nuevas de configuraciones, documentación y entrega. Sin cambiar configuración global, renormalizar ni preparar archivos. | 9 / 0 |

El mantenimiento estresado usa la opción existente que multiplica tasas y deducciones. Las pruebas comprueban `MM_estres(N)=2*MM_base(N)` en fronteras; la configuración conserva apalancamiento 2x. No se modifica ese módulo ni se instala una cronología de margen.

Los archivos nuevos se enumeran individualmente en [archivos_nuevos_modificados.csv](archivos_nuevos_modificados.csv). Incluyen las seis configuraciones, protocolo y matriz previos, verificadores externos al paquete histórico, runner y benchmark, constructor de reporte, auditor de fills, utilidad de reproducción, pruebas, documentación y artefactos completos del lote.

La conservación de la referencia y los cambios de desarrollo tienen comprobaciones separadas. [codigo_base_manifest.json](codigo_base_manifest.json) autentica la reconstrucción del código aplicable a BASE mediante los hashes originales; [codigo_ejecutado_manifest.json](codigo_ejecutado_manifest.json) conserva la instantánea de la tanda. Los nuevos scripts de análisis y verificación están también en `herramientas/` y quedan cubiertos por el manifiesto final.

Las verificaciones de comportamiento se documentan en [verificaciones.md](verificaciones.md). La suite de cierre tiene 607 pruebas aprobadas, incluidas ocho nuevas de orquestación y autenticación; las 32 del informe se ejecutaron además tras el ajuste final de la leyenda H3. El auditor auxiliar de fills es postprocesamiento independiente, tiene diez comprobaciones aritméticas internas y aprobó los 2.781 fills reales. No modifica el motor congelado ni los datos de las corridas.

Después de ejecutar las doce carteras se corrigió el runner nuevo para conservar resultados terminados como insolventes y localizar el proyecto desde el Config importado. El reproductor autentica el helper seleccionado y registra su hash. Es una corrección de orquestación, sin cambios en los cinco módulos económicos ni en resultados: el runner usado realmente queda intacto dentro de `codigo_ejecutado`, y la revisión posterior vive en `herramientas`. La [resolución](verificaciones_finales/runner_insolvencia_resolucion.json) conserva ambos hashes, pruebas y alcance.

El listado de Git y las huellas de preservación distinguen árbol de trabajo, índice físico y HEAD. Estos cambios quedan preparados en archivos locales; no se hizo commit, push ni modificación del índice del repositorio del usuario.

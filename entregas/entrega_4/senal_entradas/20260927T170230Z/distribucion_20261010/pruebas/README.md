# Comprobantes anteriores al sello

Los registros corresponden a esta ejecuci?n. La regresi?n dio 994 pases y 13 omisiones por falta del candidato; esas 13 pruebas se ejecutaron luego y pasaron. No se suman esos conteos con los pases focalizados, que se solapan.

El ajuste final de la conclusi?n tuvo 8 pruebas focalizadas y Ruff pas?. Se incluyen el RED esperado de esa funci?n ausente, su GREEN y el registro de fallos/correcciones del desarrollo. Las salidas hist?ricas originales de otros fallos permanecen en la carpeta de trabajo.

La verificaci?n con datos locales autentic? los 1.731 inputs y reconstruy? H3 de todos los escenarios. La copia Git aislada anterior al sello verific? el n?cleo num?rico offline, en otro directorio y proceso Python aislado; se comprobaron el origen de los m?dulos incluidos y 469 archivos antes/despu?s. Usa el Python 3.14 y las dependencias instaladas de este entorno; no se afirma una reinstalaci?n nueva del lock.

Estos comprobantes preceden a su propia incorporaci?n y al sello final. El inventario exacto del paquete sellado y su nueva exportaci?n se verifican despu?s, en auditor?as externas para evitar autorreferencia. Constructor y verificador comparten helpers, seg?n README.

Algunos logs originales tienen BOM UTF-16 de PowerShell; se conservan sus bytes. Los documentos y tablas del paquete son UTF-8. El fallo del control hist?rico general est? documentado en documentos/control_historico_general.json y no se cuenta como pase.

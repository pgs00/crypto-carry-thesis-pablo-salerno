# Cuenta SOFR aprobada: evidencia reproducible

Abrir [reporte.html](reporte.html) o [reporte.md](reporte.md). Esta versión
ejecuta exclusivamente la comparación remunerada aprobada. No recalcula los
diagnósticos previos ni el motor. Conserva ACT/360 para intereses y CAGR365.

## Archivos y cadena de evidencia

`tablas/cartera_sofr_diaria.csv` contiene 1.704 cierres: saldo inicial/final,
principal, interés pendiente, capitalización y origen de tasa. La cuenta es USD
hipotética bruta; `interest_usd` no es P&L neto de costos de un inversor real.
`bloques_sofr.csv` delimita cada par de hábiles consecutivos incluso a igual tasa.
`comparacion_periodos.csv` tiene 24 filas (tres cuentas por ocho períodos).
`diferencias_periodos.csv` tiene 16 filas carry menos SOFR. `pnl` usa la moneda
de la fila; las diferencias nominales requieren la paridad aprobada 1 USDT=1 USD.
`net_return` es el nombre común heredado: para SOFR representa retorno bruto.
En SOFR, Sharpe y capital desplegado quedan vacíos por no calcularse/no aplicar;
no son ceros. `sharpe_reason` mantiene los motivos de ND del carry.

`reutilizado` incluye tres CSV carry idénticos al paquete anterior y su manifiesto
original autenticado. `dependencia_previa.json` enlaza el sello anterior. La
ficha pendiente se conserva como documento histórico; `documentos/aprobacion.*`
registra la autorización posterior. `fuentes_publicas` contiene bytes originales,
URLs, fechas de consulta y hashes. `excepciones.json` es extracción documentada,
no descarga original. Las figuras PNG/SVG tienen sus CSV en `figuras/fuentes`.

## Verificación compacta y con la dependencia anterior

Con Python 3.14 y Matplotlib/Numpy/pytest para construir y probar; el verificador usa la biblioteca
estándar. Rutas absolutas o relativas al directorio actual, sin red ni repositorio:

```powershell
& <python> -B -X utf8 <paquete>/herramientas/scripts/verify_sofr_benchmark.py --package <paquete> --output <auditoria_nueva.json>
& <python> -B -X utf8 <paquete>/herramientas/scripts/verify_sofr_benchmark.py --package <paquete> --previous <paquete_previo> --output <auditoria_completa_nueva.json>
```

Ambos modos autentican el sello, aprobación, snapshot SOFR y copias originales,
reconstruyen el calendario y calculan cuenta/períodos/contrastes Index, informe y
fuentes de figuras. El modo con `--previous` también autentica todos los miembros
del paquete anterior, sin ejecutar sus diagnósticos. El código de postprocesamiento
es compartido entre constructor y verificador; no es una validación independiente
del motor. Las imágenes se autentican por hash y sus datos se contrastan; no se
afirma que el verificador hace inspección visual. Esa inspección se documenta
en las auditorías de entrega externas al sello.

## Construcción nueva y pruebas

```powershell
& <python> -B -X utf8 <paquete>/herramientas/scripts/build_sofr_benchmark.py --output <destino_inexistente> --previous <paquete_previo> --documents <paquete>/documentos --research <paquete>/fuentes_publicas --tests-root <paquete>/herramientas/tests/unit
```

Para ejecutar todos los tests incluidos desde `<paquete>/herramientas`, establecer
`SOFR_INPUTS=<paquete>` y `SOFR_PREVIOUS=<paquete_previo>` y ejecutar:

```powershell
& <python> -B -X utf8 -m pytest -q -p no:cacheprovider tests/unit
```

Sin esas entradas explícitas y fuera del checkout se omiten las pruebas históricas
de paquete; las omitidas no certifican la comparación. Los tests pequeños cubren
calendario, días de igual tasa, inicio inhábil, feriados, bisiesto, fin excluyente,
saldos heredados, CAGR365 y redondeo Index. Las pruebas de paquete alteran copias
temporales y comprueban rechazos incluso si se actualizan sus hashes.

Los CLI rechazan sobrescritura y destinos dentro de las entradas protegidas.
Use `-B` para no crear caches dentro del sello. Se archivan solamente los helpers
IO/formato HTML previos y código nuevo; no se importa `crypto_carry` ni se ejecuta
concentración, restricciones, exposición o riesgo intradía. No hay commit ni push.
Las auditorías posteriores al sellado son externas y nombran el hash verificado.

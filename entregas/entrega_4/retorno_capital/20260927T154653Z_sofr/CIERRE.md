# Comparación SOFR aprobada: entrega cerrada

Versión nueva: **paquete_20260927T162350Z**. Cuenta hipotética bruta USD con
10.000 iniciales, ACT/360, paridad nominal 1 USDT=1 USD y CAGR anualizado a
365 días. Intervalo [01/01/2022, 01/09/2026) UTC, con 1.704 días y saldos heredados.

[Reporte HTML](paquete_20260927T162350Z/reporte.html) ·
[Reporte Markdown](paquete_20260927T162350Z/reporte.md) ·
[Paquete ZIP](paquete_20260927T162350Z.zip) ·
[SHA-256 del ZIP](paquete_20260927T162350Z.zip.sha256) ·
[Reproducción](paquete_20260927T162350Z/README.md)

| Cuenta independiente | Saldo final | P&L | Retorno acumulado | CAGR365 |
| --- | ---: | ---: | ---: | ---: |
| Carry condicional neto de costos modelados, USDT | 10.785,76 | 785,76 | 7,858% | 1,633% |
| Carry permanente neto de costos modelados, USDT | 11.680,07 | 1.680,07 | 16,801% | 3,382% |
| SOFR hipotética bruta, USD | 12.059,50 | 2.059,50 | 20,595% | 4,093% |

Las diferencias de P&L carry menos SOFR son −1.273,74 y −379,43 unidades
nominales, respectivamente. No son una estimación del interés recuperable de
caja o garantías. La cuenta SOFR no acredita acceso real, igualdad de riesgos,
convertibilidad garantizada ni rentabilidad futura. Los costos excluidos de la
referencia bruta no equivalen a costos nulos verificados para un inversor.

## Tablas y figuras

- [Comparación de ocho períodos](paquete_20260927T162350Z/tablas/comparacion_periodos.csv): 24 filas.
- [Diferencias por período](paquete_20260927T162350Z/tablas/diferencias_periodos.csv): 16 filas.
- [Cartera SOFR diaria](paquete_20260927T162350Z/tablas/cartera_sofr_diaria.csv): 1.704 cierres con principal e interés pendiente.
- [Bloques entre hábiles consecutivos](paquete_20260927T162350Z/tablas/bloques_sofr.csv): 1.164 bloques, sin agrupar tasas iguales.
- [Calendario completo](paquete_20260927T162350Z/tablas/calendario_verificado.csv) y [53 ausencias justificadas](paquete_20260927T162350Z/tablas/dias_semana_sin_observacion.csv).
- [Control inicial](paquete_20260927T162350Z/tablas/control_bloque_inicial.csv) y [contrastes Index](paquete_20260927T162350Z/tablas/control_sofr_index.csv).
- [Capital](paquete_20260927T162350Z/figuras/capital.png), [resultados anuales](paquete_20260927T162350Z/figuras/resultados_anuales.png) y [control Index](paquete_20260927T162350Z/figuras/control_index.png), también en SVG y con CSV de datos.

Los resultados anuales y el capital utilizado vigente están integrados en el
reporte. 2026 abarca enero–agosto. H2 y sus cifras originales se conservan, con
Sharpe RF=0 y ND donde corresponde. No se calculó un Sharpe SOFR. Los diagnósticos
de concentración, entrada, exposición y riesgo no se repitieron.

## Controles ejecutados y evidencia

1. Calendario SIFMA histórico/2026 y excepciones NY Fed: las 53 ausencias de
   semana son 51 cierres completos y dos excepciones, sin faltantes inexplicados.
   El cierre temprano por Carter 09/01/2025 se documenta desde el aviso NY Fed,
   conservando por separado el estado extraído de la página anual SIFMA.
2. Bloque inicial 01/01–03/01/2022: interés directo 1/36 USD, sin inventar Index
   para sábado y sin devengar 31/12. Después, 2.326 controles de bloque/acumulado
   compatibles con límites derivados de ocho decimales, sin ampliarlos.
3. [34 pruebas finales](auditorias/tests_revision_final.json), sin omisiones.
   [Ruff aprobado](auditorias/ruff_final.json). Nueve pruebas de manipulación
   actualizan hashes en copias y aun así obtienen rechazos reales.
4. [Verificación compacta](auditorias/verificacion_compacta.json) y
   [con dependencia previa](auditorias/verificacion_completa_portable.json),
   ejecutadas desde copia fuera del checkout y sin PYTHONPATH del proyecto.
   [Las 34 pruebas archivadas también pasan](auditorias/comando_tests_portables.json).
   [Los 74 archivos de la copia permanecen idénticos](auditorias/portabilidad.json).
5. [Inspección de tres figuras y 18 enlaces locales](auditorias/presentacion.json).
   PNG/SVG y fuentes CSV sellados. No se afirma QA mediante captura de navegador.
6. [ZIP cotejado byte a byte](auditorias/zip_verificado.json): 74 archivos,
   2.216.971 bytes comprimidos, sin errores de integridad.
7. [Preservación final](auditorias/preservacion_final.json): 62 archivos protegidos,
   1.556 miembros de cinco sellos anteriores y HEAD/índice sin cambios.
   No se alteraron motor, configuraciones ni paquetes sellados. La modificación
   de `.gitattributes` y los archivos del análisis previo ya existían al inicio
   de este turno y permanecen iguales.

La [revisión independiente](paquete_20260927T162350Z/documentos/revision_independiente.md)
no encontró defectos en el cálculo. Se corrigió su observación sobre el metadato
Carter con una prueba roja y luego verde, sin modificar resultados financieros.
El revisor no certificó portabilidad ni preservación final: esos controles
corresponden a las auditorías ejecutadas por el autor enlazadas arriba.

## Identidad, límites y estado de publicación

Manifiesto nuevo (72 miembros más manifiesto y sidecar):
`4769f6c6a80e6fa4b4fd4a4e7c45b94fb10b3773bc3cbbebd36b117f73c938c9`.

ZIP:
`55079fc5b11763e9f5bf2888ad5be6cce156b7f1c94b08cb206f56d2bbfd0f8b`.

Sello previo enlazado:
`0163cf7622d929c06773700f50d13b2e808afee85a6cf85e48d45dcac03af12b`.

Índice Git preservado:
`eb64db20ee17ac7c0a0a079d0105665ed254d983e8b21687e864bdc0388e0026`.

La suite ejecutada es la nueva de SOFR, no la general del motor. Los verificadores
comparten postprocesamiento y se complementan con fixtures exactos y el Index
externo. Se autentican las fuentes históricas sin repetir sus análisis. El control
general histórico mantiene la incompatibilidad previa del hash de config.py,
documentada en [límites de verificación](paquete_20260927T162350Z/documentos/limites_verificacion.md);
no se modificó ese archivo ni su manifiesto para forzar una aprobación.

Entrega local, sin commit, push ni cambios al índice. No se ejecutaron nuevos
backtests, no se remunera caja/garantías carry y no quedan aprobaciones pendientes
para este comparador. Las auditorías posteriores al sello están fuera de él para
conservar sus bytes. El plan interno refleja el momento previo al sellado; este
cierre acredita las verificaciones posteriores.

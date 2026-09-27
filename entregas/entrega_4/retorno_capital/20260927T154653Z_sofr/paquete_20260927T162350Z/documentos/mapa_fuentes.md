# Mapa de fuentes y lectura

La aprobación se registra en `aprobacion.md` y su contrato fijo en `aprobacion.json`.
La ficha original sigue marcada pendiente porque conserva sus bytes históricos;
la autorización posterior es la que habilita esta versión.

El manifiesto anterior conservado en `reutilizado/manifiesto_previo.json` tiene
SHA-256 `0163cf7622d929c06773700f50d13b2e808afee85a6cf85e48d45dcac03af12b`.
Autentica las tres tablas carry, el snapshot SOFR y la metodología reutilizados.
El verificador completo lee todos sus miembros sin ejecutar diagnósticos anteriores.

| Fuente original | Función y distinción temporal |
| --- | --- |
| `sifma_archivo.html` | Recomendaciones U.S. 2022–2025, incluido 31/12/2021. Archivo consultado hoy, no captura contemporánea de cada feriado. Conserva texto y ordinal de extracción. |
| `sifma_2026.html` | Recomendaciones U.S. 2026. Cierre total distinto de cierre temprano. |
| `nyfed_excepcion_2023.html` | Aviso fechado 08/03/2023 para la excepción económica/publicación 07/04/2023. |
| `nyfed_excepcion_2026.html` | Aviso fechado 12/03/2026 para la excepción 03/04/2026. |
| `nyfed_carter_2025.html` | Aviso fechado 02/01/2025: conserva publicación ON/FOR 09/01/2025. |
| `sofr_serie.json` | Snapshot original aprobado: 1.166 tasas entre 30/12/2021 y 01/09/2026. effectiveDate es fecha económica; percentRate es porcentaje anual. |
| `index_serie.json` | 1.166 Index oficiales, fecha valor hábil y precisión de ocho decimales. Promedios 30/90/180d archivados pero no usados como rendimientos diarios. |
| `sofr_metodologia.html` | Método ACT/360, publicación, comienzo inhábil y redondeo. La página indica actualización 06/04/2026; no se presenta como copia histórica de cada vintage. |

`fuentes_publicas/fuentes.json` registra URL solicitada/final, consulta UTC,
HTTP, bytes, hash y cabeceras disponibles. HTTP Date no sustituye la consulta ni
la fecha económica/publicación. `excepciones.json` es una extracción humana
explícita de tres avisos, no una descarga original ni una regla bancaria genérica.

El calendario se construye con SIFMA y los avisos antes de mirar la población de
tasas/Index. `calendario_verificado.csv` muestra cada fecha y su presencia esperada
y observada. `dias_semana_sin_observacion.csv` enumera las 53 ausencias justificadas.
Ejemplos relevantes: 10/11/2023 es hábil; 03/07/2026 es cierre completo SIFMA;
no se sustituye este calendario por NYSE ni por feriados bancarios federales.

Para 09/01/2025, el aviso NY Fed confirma el cierre temprano de SIFMA que el
archivo anual consultado no enumera. `sifma_status` conserva el estado histórico
consolidado `early_close`; `calendar_page_status` preserva el estado derivado sólo
de la página SIFMA (`ordinary_weekday`). Ambos mantienen SOFR como día hábil.

`rate_source_row` y los ordinales SOFR/Index son posiciones base cero en refRates
del JSON original, que se preserva sin ordenar sus bytes. Las tablas nuevas
ordenan fechas para componer. `rate_publication_date_expected` representa la
fecha hábil esperada, no una hora de publicación observada ni disponibilidad
ex ante certificada. `revisionIndicator` se conserva sin reconstruir vintages.

La convención aprobada permite saldo devengado diario sin reinvertir dentro del
bloque. Campos `block_principal`, `pending_interest_after_close` y
`principal_after_close` permiten auditar los cortes de año y H3. La tasa 01/09/2026
se conserva para comprobar cobertura de frontera, pero no genera interés.

Se reutilizan common.py y helpers de formato de report.py del análisis anterior.
Ninguna función de concentración, restricciones o exposición se ejecuta. No se
importa crypto_carry. Las pruebas y verificadores sólo calculan esta comparación.

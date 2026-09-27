# Registro de ejecución por etapas

Etapa 1: autenticación del sello previo y registro inicial de HEAD, índice,
motor, configuraciones y código previo. Fuentes públicas archivadas y calendario
independiente: 53 ausencias de días de semana = 51 cierres SIFMA + 2 excepciones
NY Fed; cero faltantes inexplicados. Tests de calendario: 8 casos verdes después
de observar 8 fallos NotImplementedError en los contratos pendientes.

Etapa 2: composición ACT/360, días de igual tasa, cortes, bisiesto y CAGR365.
8 tests adicionales verdes. Se corrigieron errores sintácticos de fixtures antes
de observar los fallos por implementación ausente. El fixture de año nuevo usa
el feriado real. El caso de corrupción Index se eligió fuera del intervalo
matemático de redondeo antes de correr el histórico; no se ampliaron tolerancias.
El interés inicial es 1/36 USD, error aritmético del orden de 1E-46; 2.326 controles
Index posteriores compatibles con sus intervalos publicados.

Etapa 3: 5 pruebas de integración observadas rojas y luego verdes, junto a las
16 previas: 21/21. Ocho períodos, 24 filas comparativas, 16 diferencias nominales.
Los originales carry no se recalculan; H2 se conserva byte a byte. El interés SOFR
usa campos USD propios para no confundirlo con P&L neto USDT.

Etapa 4: constructor, informe, figuras y verificador implementados. Pruebas de
paquete escritas antes de implementar el constructor: 11 errores esperados de
setup NotImplementedError, no once rechazos de manipulación ya verificados.
Corrida posterior: 32/32 pruebas aprobadas en 35,97 s; nueve manipulaciones
re-selladas efectivamente rechazadas, modos compacto/completo y protección de
destino comprobados. Ruff pasó después de aplicar formato e imports a código
nuevo. Los controles no repiten los diagnósticos de carry.

Etapa 5: revisión independiente de solo lectura recibida. Se añadió un caso
explícito para verificar la conservación de revisionIndicator, la tasa final y
la fecha de publicación esperada. La auditoría final identifica la última suite,
la copia portable, inspección visual, cotejo ZIP y preservación Git/binaria.

Resolución de revisión: se corrigió el estado SIFMA para Carter 09/01/2025,
conservando `calendar_page_status` y documentando el aviso NY Fed. Test de
regresión: rojo por estado incorrecto, luego verde. Ninguna tasa, fecha hábil
ni fórmula cambia. La prueba de revisiones también pasó. Sin hallazgos diferidos.

Suite posterior completa de este alcance: **34/34**, 39,22 s, sin omisiones.
El resultado crudo y el comando están en la auditoría externa
`tests_revision_final.json`. Ruff final aprobado. Antes del sello, 62 archivos
protegidos y los bytes del índice coinciden con el registro inicial.

Este documento se copia antes del sellado. Los actos posteriores (ZIP, copia
portable, inspección final y preservación al cierre) se registran fuera del
paquete en `CIERRE.md` y auditorías que citan su hash; no se reabre el sello para
insertar una afirmación de verificación sobre sí mismo.

Decisión de ejecución: se mantiene el trabajo local autorizado y no se usa el
flujo de commits/limpieza de skills, porque el usuario prohibió commit, push y
cambios de índice. No se borra el registro de trabajo. Se ejecutan las pruebas
del nuevo postprocesamiento; no la suite general que podría repetir backtests o
diagnósticos fuera de alcance. Las evidencias finales van fuera del nuevo sello.

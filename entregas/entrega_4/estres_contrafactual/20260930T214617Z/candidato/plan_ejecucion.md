# Plan breve de ejecución después de aprobación

Estado: no iniciado. Sólo se implementará la familia expresamente aprobada.
La [ficha de decisión](ficha_decision.md) y el [protocolo técnico](protocolo_tecnico.md)
son la especificación material. Se usará la guía de planes de Superpowers
para traducirla a pruebas y extensiones concretas, respetando la única puerta
metodológica solicitada y la prohibición de commit/push/índice.

## Secuencia y archivos previstos

1. Guardar respuesta literal, fecha y familias aprobadas, más los SHA-256 de
   ficha/protocolo/tablas en un registro nuevo. Fijar el protocolo de ejecución
   antes de correr. No convertir el estado pendiente en una aprobación implícita.
2. Crear primero pruebas en `tests/unit/test_stress_counterfactual.py` y
   `tests/integration/test_stress_counterfactual.py` (rutas propuestas).
   Verificar sus fallos antes de implementar. Fixtures de fronteras, unidades,
   ventanas ya comprometidas, cierre spot y liquidación con remanente.
3. Implementar un adaptador optativo pequeño en
   `src/crypto_carry/data/stress_counterfactual.py` y runner/auditorías en
   `scripts/`, con configs derivadas de cada efectiva original bajo
   `configs/entrega_4/estres_contrafactual/20260930T214617Z/`.
   No hay archivos de escenarios ejecutables creados durante etapa A.
4. Probar dos carteras completas con capa apagada frente a los controles
   corregidos autenticados. Si se ejecuta shocks, agregar dos controles completos
   de magnitud cero. Si sólo se aprueba CF, bastan las dos apagadas y fixtures
   CF apagado: los controles de shock cero esperan a la aprobación de shocks.
5. Ejecutar serialmente SH_P90 (dos estrategias), conciliar; SH_MAX (dos),
   conciliar; o CF (dos), conciliar, según familias autorizadas. Conservar
   estados fallido/incompleto/insolvente/ejecutado y run_id distintos. No usar
   resultados parciales para cambiar el protocolo. Una discrepancia BASE
   bloquea interpretación y requiere consulta antes de sustituir comparadores.
6. Recalcular métricas de ocho períodos; oportunidad H3 sobre mercado común;
   autenticar H1 antes de reutilizar. Diagnósticos intradía sólo en ventanas
   intervenidas y bordes, sin una nueva reconstrucción intradía global.
7. Completar tablas/figuras/fuentes y evidencia de intervenciones en el único
   candidato. Verificación externa, regresión pertinente, Ruff, conciliación,
   preservación y ataques reales de bytes/celdas. No declarar rechazado por
   verificador un ataque que falló al fabricar la adulteración.
8. Sellar una sola entrega al superar los controles. Auditorías posteriores
   fuera del sello. Actualizar índice vigente y matriz según lo ejecutado;
   B6, redacción y alcance B2/B3 siguen separados. No generar Word/PDF.

## Interfaz y validadores que se deben conservar

Se inspeccionaron `data/replay.py`, `data/market_calendar.py`,
`data/prescribed.py`, `strategy.py`, `execution.py`, `models.py` y auxiliares
de riesgo/demoras. El adaptador se coloca entre fuentes autenticadas y eventos
consumidos, evitando copiar particiones completas. Publica barras/referencias
y volumen coherentes, además de un diario de transformaciones con valor/hash
original, nuevo valor, fórmula, unidad, escenario y disponibilidad.

La capa CF necesita una excepción de cobertura limitada a sus 306 claves;
la capa shock conserva actividad y calendario. La referencia de valoración
durante el cierre debe conservar edad/procedencia antiguas: se probará que el
reloj del factor no hace pasar frescura ni operatividad. No se autoriza
desactivar `coverage`, filtros del RuleBook o las condiciones de `MinuteBar`.
Si una interfaz común debe cambiar, la opción apagada debe conservar semántica,
config/digest y outputs. Una etiqueta sintética no disculpa huecos ajenos.

No usar el valor final de una vela para sizing anterior ni multiplicar un
precio que ya fue transformado. Conservar OHLC, quote/base, precio de señal
y referencia de equity consistentes; VWAP y slippage se aplican una vez.
El calendario no se consulta como señal futura. Tests con reapertura alterada
deben dejar idénticos todos los datos/decisiones anteriores a ella.

Probar también solapamientos BTC/ETH, nanosegundos, final de muestra, volumen
cero, parciales, tick/step, comisiones en base, reservas/deuda, funding previo
a fills y corto cerrado sin margen. Cualquier checkpoint debe restaurar
estado de la intervención y órdenes, y coincidir con ejecución continua.

## Presupuesto y conservación

Los controles B4 medidos tardaron 1.956,69 s condicional y 2.860,42 s permanente,
incluido posprocesamiento: unos 80,3 minutos por par; picos de proceso 3,06/3,01
GB. Sus outputs originales pesan unos 55,7/57,1 MB por cartera.
Seis carteras económicas requieren aproximadamente cuatro horas al ritmo BASE;
cuatro controles agregan 2,7 horas. Reservar 6–10 horas para replay/controles,
además de desarrollo y QA, con ejecución serial y seguimiento de memoria.
Las intervenciones pueden alterar la frecuencia de órdenes y esos tiempos.

Presupuesto de espacio de trabajo: 5 GB, holgado frente a aproximadamente
0,57 GB para diez outputs de tamaño BASE, más extractos, candidato y copias
aisladas necesarias para QA. No es una medición de escenarios todavía no
ejecutados. Al inicio había aproximadamente 240,5 GB libres en C: y 841,9 GB
en D:. No descargar trades ni duplicar bases de minutos/paquetes completos.

Las corridas originales permanecen inmutables. Las revisiones de texto se
registran con motivo/diff dentro del mismo candidato, sin duplicar carteras.
Los temporales van fuera del árbol versionado en carpetas exclusivas, sin
symlinks/junctions. La limpieza del inventario no forma parte de este plan
autorizable y requiere una decisión posterior por rutas.

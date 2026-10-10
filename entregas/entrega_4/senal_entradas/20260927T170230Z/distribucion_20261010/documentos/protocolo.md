# Bloque 2: señal y selección de entradas

Registro previo a resultados, 2026-09-27T17:02:30Z. Sensibilidad exploratoria de
historia ya observada; no selección de ganadores ni prueba fuera de muestra.
La especificación científica se conserva en este protocolo histórico y en
[el protocolo descriptivo de distribución](../protocolo_distribucion.md).

## Población y matriz cerrada

Dos estrategias independientes, conditional y permanent, BTCUSDT/ETHUSDT,
10.000 USDT cada una, intervalo UTC [2022-01-01,2026-09-01), sin reinicios.
BASE: run_ad71d751b20623006c195ff3 y run_dfea4b7ac1475668d5968c97.

| ID | Dimensión | Cambios únicos respecto de la configuración efectiva BASE |
|---|---|---|
| H072 | horizonte y tenencia | horizon_hours=72; holding_hours=72 |
| H336 | horizonte y tenencia | horizon_hours=336; holding_hours=336 |
| V012 | vida media | half_life_hours=12 |
| V048 | vida media | half_life_hours=48 |
| B025 | basis de entrada | basis_max=Decimal('0.0025') |
| B100 | basis de entrada | basis_max=Decimal('0.01') |

No se cruzan dimensiones. Se derivan configuraciones desde la efectiva BASE.
Diff exacto obligatorio; rutas e identidad se registran aparte. Window=336 h,
precarga=360 h, disponibilidad=60 s y costo de ciclo=34 pb permanecen iguales.
Umbral de renovación condicional >0. Renovación sin filtro de basis de entrada.
Riesgo prioritario, reglas, fills, parciales, ejecución y contabilidad originales.
No se cambia código de `src`, defaults, datos ni configuraciones anteriores.

## Métricas y contratos

Ocho períodos: full, 2022-2023, 2024+, 2022, 2023, 2024, 2025, 2026 (enero-agosto).
Saldos heredados; cada cierre/período concilia a 1E-8 USDT. Se conservan equity,
P&L y componentes, retorno, CAGR365, Sharpe RF=0 y ddof=1 con días inactivos,
volatilidad y drawdown diarios. ND y motivos no se sustituyen por cero.
Capital utilizado diario=spot valuado+garantía; se informa media/máximo diario
y utilización. No se divide CAGR por utilización. Polvo sigue en el patrimonio.
Exposición: método corregido sobre trayectoria completa, luego cortes; unión
BTC/ETH para cartera, sin contar polvo como actividad. Se distinguen ciclos,
intentos, aperturas, renovación, fills parciales, fallas y motivos de cierre.

H1: todas las señales elegibles, población común EWMA/no-change por escenario;
target en (señal,señal+H], calendario acreditado, final global exclusivo.
Conservar inválidos/motivos y tiempos reales. MAE por activo e igual peso 50/50,
rotulado pb/H h; habilidad 1-MAE_EWMA/MAE_no_change sólo con denominador positivo.
H072/H336 son cambio compuesto de señal y tenencia; MAE entre horizontes no
permite ordenar calidad predictiva. No se recorta trayectoria financiera.

H2: contrato corregido de scripts/rules_sensitivity_h2.py: CAGR condicional
definido, finito, >0 y Sharpe definido >permanente del mismo escenario/período.
Preservar ventanas, cobertura, no_favorable/no_concluyente y motivos.

H3: minutos independientes de caja/posiciones; forecast completo si supera
costo y filtros, cero sólo para fallo conocido, desconocido excluye día conjunto.
1440 minutos por activo/día y media BTC/ETH 50/50. Timestamps reales, interrupción
documentada y sumas/conteos auditables. Cortes 2022-2023 y 2024-agosto 2026.
Ambos oportunidad y CAGR caen=favorable; ambos suben=contraria; restantes
evaluables=mixta; faltante indispensable=no_concluyente. Unidad pb/H h.

Entradas: partición excluyente funding/basis, no evaluables, primer bloqueo y
acciones acreditadas; permanente omite funding, aunque falle descriptivamente.
Renovaciones separadas. Las invariancias de economía, decisiones, H1 y H3 se
comprueban por separado. No se imponen diferencias ni se reetiquetan run_id.

## Ejecución y evidencia

A: autenticar referencias/inputs y estado Git; pruebas pequeñas y ventana
técnica contra ruta original, medir tiempo/RAM. B: H072/H336. C: V012/V048.
D: B025/B100. Cada etapa exige conciliación antes de interpretación. Comenzar
con una corrida; ampliar sólo con memoria medida. Reanudación por corrida
completa autenticada: configuración, datos, código, período y artefactos iguales.
Una corrida interrumpida se reinicia desde 2022; no hay checkpoint parcial nuevo.

Estados finales: ejecutado, reutilizado_verificado, bloqueado, fallido; estado
económico separado (complete/insolvent). Referencias se reutilizan con sus IDs.
Fuentes masivas y nuevas corridas completas locales, dependencias por argumentos.
E: reporte MD/HTML, tablas/curvas, fuentes, snapshots, matriz de requisitos,
verificador offline portable, corrupción semántica con hashes renovados,
regresiones/Ruff, preservación y exportación Git con índice temporal aislado.

Preservar referencias selladas, índices/manifiestos, configuraciones, PDF y
código histórico. No hay SOFR nuevo, concentración, reconstrucción intradía,
PDF final, optimización, descarga, commit, push ni cambio del índice del usuario.
Una incompatibilidad que exija tocar motor/interfaz requiere decisión explícita;
se continúan dimensiones independientes. Este bloque no completa toda E4.

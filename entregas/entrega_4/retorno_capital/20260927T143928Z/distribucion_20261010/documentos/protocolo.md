# Protocolo previo: retorno, capital y diagnósticos

Fecha: 2026-09-27. Encargo: `encargo_usuario.md`. Ejecución local por etapas.

## Población y fuentes

Sólo BASE_E3: condicional `run_ad71d751b20623006c195ff3` y permanente
`run_dfea4b7ac1475668d5968c97`. BTCUSDT y ETHUSDT; 10.000 USDT iniciales
por cartera; intervalo UTC [2022-01-01, 2026-09-01). Se autentican manifiestos
y archivos antes del cálculo. No se ejecuta ni importa el motor económico.

Dependencias explícitas: padre `reglas_historicas/20260925T005436Z`, corrección
`correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z`, evidencia
compacta intradía `riesgo_intradia/20260926T214118Z/paquete_20260926T220400Z`
y `Paquete de evidencia`. Sus rutas se suministran por argumentos.

Períodos: muestra completa, 2022, 2023, 2024, 2025, enero-agosto 2026 y los
cortes H3 [2022-01-01,2024-01-01), [2024-01-01,2026-09-01). Los saldos se heredan.

## Atribución por activo, ciclo y fecha

Se recuperan los cycle_id de transiciones originales y se enlazan órdenes,
fills y movimientos del ledger. Renovar no crea otro ciclo. Se distinguen
intentos sin fill, aperturas incompletas, ciclos cerrados y abiertos al fin.
Los costos de todos los intentos se conservan.

El estado contable de cada activo se reconstruye exclusivamente con los
movimientos persistidos: compra spot neta de comisión en base, costo promedio
proporcional al vender, corto y promedio variables, realizado, funding, fees
y cargos. Cada estado se contrasta con ledger, posiciones y cierres originales.
Transferencias y garantía no son resultado. Slippage ya está en los precios.

Se evalúa el P&L acumulado por activo en cierres diarios y fronteras de ciclos:
realizado spot + cantidad spot × precio − costo spot; realizado futuros +
corto × (promedio − mark); funding − fees − cargos. Las diferencias entre
fronteras consecutivas pertenecen al ciclo que ocupó ese segmento o a una
categoría explícita fuera de ciclo. Los límites de entrada usan el precio
causal persistido en la evaluación; los cierres usan el precio contemporáneo
ya exportado en la evidencia compacta intradía. Se conserva fuente y clave.
No se reconstruye una serie nueva por minuto. Un precio indispensable ausente
bloquea esa atribución: no se inventa ni se absorbe en un residuo.

El polvo conserva unidades y costo. Su cambio durante un segmento sin ciclo
queda en `outside_dust`; al entrar, el P&L acumulado se toma como base,
por lo que su ganancia previa no se reconoce otra vez. Las variaciones de
realizado/no realizado se muestran separadas; su reclasificación no crea P&L.
El cierre del ciclo no simula vender el remanente. Los ciclos abiertos se
valúan en el cierre final original, sin venta ni fee terminal.

Cada diferencia se fecha en su extremo final, con cierres diarios como
fronteras obligatorias; así ningún segmento cruza un año o corte sin división.
Se entrega además vida completa, distinta de la contribución por período.

Concentración: G=sum(max(PnL,0)), L=sum(max(-PnL,0)); top 1/3/5 ciclos por
signo y top 1/5/10 días únicos de cartera, con cantidad efectiva e identificadores.
G/L se refieren a la población incluida. El cociente sobre neto se identifica
separadamente, sin recortar >100%; neto no positivo o inferior al 10% de G+L
lleva advertencia descriptiva prefijada. Ninguna resta es un contrafactual.

## Restricciones y acciones

Entrada: `signals.parquet`, decision_kind=entry. Renovación:
`renewal_diagnostics.parquet`, con umbral cero y orden propio. Claves:
run_id, symbol, decision_time, decision_kind, ancla y ordinal de origen;
se comprueban duplicados exactos y empates legítimos sin deduplicación silenciosa.

Vista A: cuatro celdas funding/basis evaluables y grupo externo no evaluable
con motivos; basis inclusivo [0,0.005], separando negativo y superior al techo.
Vista B: estados pass/fail/not_evaluable, motivos simultáneos con solapamiento
y primer bloqueo excluyente en el orden persistido. Funding de la permanente
es descriptivo y no aplicado. Sizing con posición previa es prospectivo.
Vista C: decisión registrada y enlaces acreditables con transiciones, órdenes,
fills e intentos fallidos. Toda acción sin enlace único queda explícita.
Emparejamiento entre estrategias sólo por activo, instante y clase, informando
faltantes y ambigüedades. Estas filas no son minutos elegibles ni oportunidades
independientes perdidas, y no sustituyen H3.

## Integración, benchmark y controles

Se reutilizan sin cambio las métricas corregidas, exposición sin polvo y H1/H2/H3.
Capital usado diario=spot valuado+garantía; tiempo activo=unión de intervalos.
No se divide CAGR por utilización. 2026 tiene ocho meses observados.

Se investigarán como máximo dos candidatos públicos para el capital completo;
la selección será por trazabilidad/cobertura, antes de calcular retornos.
Estado obligatorio `pendiente_aprobacion_benchmark`; sólo una ficha aprobada
expresamente habilitará su cálculo en una versión posterior.

Aceptación por fase: fixtures previos con resultados explícitos; conciliación
por activo/día/período/cartera a 1E-8 USDT; preservación de cantidades y
movimientos; particiones y denominadores exactos; pruebas de manipulación,
rechazo de sobrescritura y verificación desde otra ruta. El verificador
recalcula relaciones y fuentes además de hashes. No requiere HEAD ni índice.
Los resultados de auditoría quedan fuera del paquete sellado. No hay commit,
push, cambios al índice, motor, configuraciones ni paquetes anteriores.

## Precisión de frontera incorporada durante la revisión

Las dos BASE usan `next_minute_vwap` y no registran movimientos del activo en
el instante de entrada. El constructor ahora rechaza explícitamente un fill
o cualquier movimiento económico no nulo del mismo activo en esa frontera:
exigiría distinguir estado previo/posterior a la entrada para asignar su costo.
No se oculta esa ambigüedad en una conciliación global. Funding cero,
transferencias sin P&L y eventos del otro activo no se rechazan por simultaneidad.
Esta guardia no cambia ninguna cifra de las dos carteras verificadas.

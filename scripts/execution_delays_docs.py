"""Spanish block-4 report and static, source-linked scientific figures."""

from collections import Counter
from datetime import UTC, datetime

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

from crypto_carry.config import iso  # noqa: E402
from scripts.execution_delays import CHANGES, STAGES  # noqa: E402
from scripts.return_capital.common import write_json  # noqa: E402
from scripts.return_capital.report import render_html  # noqa: E402
from scripts.signal_sensitivity_docs import fmt, table  # noqa: E402


def figures(package,tables):
    folder=package/'figuras'
    folder.mkdir()
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,
                         'axes.grid':True,'grid.alpha':.18,'figure.facecolor':'white'})
    sources={}
    for family,names in STAGES.items():
        fig,axes=plt.subplots(2,2,figsize=(12,7),constrained_layout=True)
        for col,strategy in enumerate(('conditional','permanent')):
            for scenario in ('BASE_E3',*names):
                rows=[r for r in tables['diario'] if r['scenario']==scenario and r['strategy']==strategy]
                if not rows:
                    continue
                dates=[datetime.fromtimestamp(int(r['time_ns'])/1e9,UTC) for r in rows]
                equity=[float(r['equity_usdt']) for r in rows]
                high=10000.
                dd=[]
                for value in equity:
                    high=max(high,value)
                    dd.append(100*(value/high-1))
                axes[0,col].plot(dates,equity,label=scenario,lw=1.25)
                axes[1,col].plot(dates,dd,label=scenario,lw=1.1)
            axes[0,col].set_title('Condicional' if strategy=='conditional' else 'Permanente')
            axes[0,col].set_ylabel('Equity (USDT; inicial 10.000)')
            axes[1,col].set_ylabel('Drawdown diario (%)')
            axes[0,col].legend(frameon=False,fontsize=8)
        fig.suptitle('Ejecución y demoras · '+family+' · cierres diarios UTC')
        for ext in ('png','svg'):
            fig.savefig(folder/(family+'.'+ext),dpi=165)
        plt.close(fig)
        sources[family]=dict(table='../tablas/diario.csv',scenarios=['BASE_E3',*names],
            normalization='absolute USDT, same 10000 initial capital; drawdown uses daily equity and initial capital')
        fig,axes=plt.subplots(1,2,figsize=(12,4),constrained_layout=True)
        for ax,strategy in zip(axes,('conditional','permanent')):
            base={int(r['time_ns']):float(r['equity_usdt']) for r in tables['diario']
                  if r['scenario']=='BASE_E3' and r['strategy']==strategy}
            for scenario in names:
                rows=[r for r in tables['diario'] if r['scenario']==scenario and r['strategy']==strategy]
                if rows:
                    ax.plot([datetime.fromtimestamp(int(r['time_ns'])/1e9,UTC) for r in rows],
                            [float(r['equity_usdt'])-base[int(r['time_ns'])] for r in rows],
                            label=scenario,lw=1.25)
            ax.axhline(0,color='#555555',lw=.7)
            ax.set_title('Condicional' if strategy=='conditional' else 'Permanente')
            ax.set_ylabel('Diferencia de equity con BASE (USDT)')
            if ax.get_legend_handles_labels()[0]:
                ax.legend(frameon=False,fontsize=8)
        fig.suptitle('Diferencia diaria de patrimonio · '+family+' · misma estrategia y fecha')
        for ext in ('png','svg'):
            fig.savefig(folder/(family+'_diferencia.'+ext),dpi=165)
        plt.close(fig)
        sources[family+'_diferencia']=dict(table='../tablas/diario.csv',scenarios=list(names),
            formula='equity_scenario(t)-equity_BASE_E3(t), matching strategy and exact daily timestamp; no forward extension')
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),constrained_layout=True)
    names=['BASE_E3',*CHANGES]
    for ax,strategy in zip(axes,('conditional','permanent')):
        selected={r['scenario']:r for r in tables['cronologia_resumen'] if r['strategy']==strategy and
                  r['period']=='full' and r['purpose']=='ALL'}
        for suffix,marker,label in (('p50','o','Mediana'),('p95','s','P95'),('max','|','Máximo')):
            ax.plot([float(selected[s]['submission_to_fill_seconds_'+suffix])/60 if s in selected and
                    selected[s]['submission_to_fill_seconds_'+suffix] is not None else float('nan') for s in names],
                    range(len(names)),marker,label=label)
        ax.set_yticks(range(len(names)),names)
        ax.set_xlabel('Envío a fill (minutos)')
        ax.set_title('Condicional' if strategy=='conditional' else 'Permanente')
        ax.legend(frameon=False)
    fig.suptitle('Sólo órdenes con fill; canceladas, expiradas y pendientes se cuentan aparte')
    for ext in ('png','svg'):
        fig.savefig(folder/('cronologia.'+ext),dpi=165)
    plt.close(fig)
    sources['cronologia']=dict(table='../tablas/cronologia_resumen.csv',period='full',purpose='ALL',
        population='orders with fill only; one observation per order; seconds divided by 60')
    # A bounded illustration for every portfolio, always its prespecified longest case.
    for summary in tables['incidentes_resumen']:
        if summary.get('selection')!='top5_duration' or summary.get('rank')!=1:
            continue
        rows=[r for r in tables['incidentes_detalle'] if r['run_id']==summary['run_id'] and r['case_id']==summary['case_id']]
        fig,axes=plt.subplots(2,1,figsize=(9,5.5),sharex=True,constrained_layout=True)
        t=[(r['time_ns']-summary['start_ns'])/60e9 for r in rows]
        axes[0].plot(t,[r['pnl_from_start_usdt'] for r in rows],color='#174d67',lw=1.3)
        axes[0].set_ylabel('P&L cartera desde inicio (USDT)')
        axes[1].plot(t,[r['spot_quantity'] for r in rows],label='Spot',lw=1.3)
        axes[1].plot(t,[r['short_quantity'] for r in rows],label='Corto',lw=1.3)
        axes[1].set_ylabel(summary['symbol'].removesuffix('USDT'))
        axes[1].set_xlabel('Minutos desde el inicio del caso')
        axes[1].legend(frameon=False)
        fig.suptitle(f"{summary['scenario']} / {summary['strategy']} · caso de mayor duración\n"
                     'Muestra local: precios causales, con arrastres señalados en la tabla')
        name='incidente_'+summary['scenario']+'_'+summary['strategy']
        for ext in ('png','svg'):
            fig.savefig(folder/(name+'.'+ext),dpi=150)
        plt.close(fig)
        sources[name]=dict(table='../tablas/incidentes_detalle.csv',run_id=summary['run_id'],
                           case_id=summary['case_id'],scope='selected case, not global intraday risk')
    write_json(folder/'fuentes.json',sources)


def summary_lines(tables):
    full={(r['scenario'],r['strategy']):r for r in tables['metricas'] if r['period']=='full'}
    lines=[]
    for scenario in CHANGES:
        items=[]
        for strategy in ('conditional','permanent'):
            if (scenario,strategy) not in full:
                continue
            r,b=full[scenario,strategy],full['BASE_E3',strategy]
            change=r['net_pnl_usdt']-b['net_pnl_usdt'] if r['coverage_complete'] and b['coverage_complete'] else None
            items.append(f"{strategy}: P&L {fmt(r['net_pnl_usdt'],digits=2)} USDT, diferencia con BASE {fmt(change,digits=2)} USDT")
        if items:
            lines.append('**'+scenario+'** — '+'; '.join(items)+'.')
    h2={r['scenario']:r['verdict'] for r in tables['h2'] if r['period']=='full'}
    h3={r['scenario']:r['h3_descriptive'] for r in tables['h3_resumen'] if r['period']=='full'}
    lines.extend(['H2, muestra completa: '+', '.join(s+' '+v for s,v in h2.items())+'.',
                  'H3, contraste original: '+', '.join(s+' '+v for s,v in h3.items())+'.'])
    return lines


def report(tables,index,partial):
    full=[r for r in tables['metricas'] if r['period']=='full']
    text=['# Bloque 4: precio de ejecución y demoras\n',
        '**'+('Desarrollo parcial' if partial else 'Seis variantes separadas, doce carteras nuevas y dos BASE reutilizadas verificadas')+'.** '
        'BTCUSDT/ETHUSDT, UTC [01/01/2022,01/09/2026), 10.000 USDT por cartera. '
        'Cada trayectoria es continua y conserva saldos entre los ocho períodos. '
        'Las cifras y archivos son locales; no acreditan publicación en GitHub ni completan toda la Entrega 4.\n',
        '[Síntesis](sintesis.md) · [Protocolo](documentos/protocolo.md) · [Corridas y comandos](indice_corridas.json) · '
        '[Auditoría](auditoria_ejecucion.md) · [Casos](incidentes.md) · [Reproducción](README.md)\n',
        '## Resultados principales\n',*summary_lines(tables),
        '\nLas sensibilidades no son estimaciones probabilísticas ni seleccionan una política ganadora. '
        'Una demora cambia toda la trayectoria; no se exige deterioro monótono.\n',
        table(['Escenario','Cartera','Equity inicial','Equity final','P&L','Retorno','CAGR365','Sharpe RF=0','Vol. anual','DD diario'],[
            [r['scenario'],r['strategy'],fmt(r['starting_equity_usdt'],digits=2),fmt(r['final_equity_usdt'],digits=2),
             fmt(r['net_pnl_usdt'],digits=2),fmt(r['net_return'],True),fmt(r['cagr'],True),fmt(r['sharpe']),
             fmt(r['annual_volatility'],True),fmt(r['max_drawdown'],True)] for r in full]),
        '[Todos los períodos y motivos ND](tablas/metricas.csv) · [Componentes diarios](tablas/diario.csv) · '
        '[Diferencias con BASE](tablas/deltas.csv). 2026 comprende enero–agosto; los retornos anuales no se suman. '
        'El drawdown principal es diario. Slippage y redondeo ya integran los precios; no se deducen otra vez. '
        'Garantías y transferencias no son P&L. La conciliación conserva 1E-8 USDT.\n',
        '## Contrato económico y temporal\n',
        table(['Escenario','Referencia','Demora añadida','Propósitos afectados'],[
            ['BASE_E3','VWAP','0 s','referencia sellada'],['E_OHLC4','(O+H+L+C)/4','0 s','misma ruta de minuto'],
            ['L01','VWAP','60 s','todas las órdenes cliente'],['L05','VWAP','300 s','todas las órdenes cliente'],
            ['LC01','VWAP','60 s','close_perp y close_spot'],['LC05','VWAP','300 s','close_perp y close_spot'],
            ['LC15','VWAP','900 s','close_perp y close_spot']]),
        'LC es una regla global para todo cierre cliente, cualquiera sea su motivo; sustituye el alcance por episodios '
        'de la antigua propuesta. Liquidate tiene cero demora adicional. El cierre spot posterior conserva su demora cliente. '
        'Las seis variantes no se cruzan entre sí ni adoptan parámetros de otros bloques; se conserva el modo BASE `realized`, '
        'umbral de entrada 34 pb, horizonte/holding 168 h, sizing joint_quantity, costos, cupos y calendario.\n',
        'Generación significa creación de la orden y coincide con su envío; la decisión/señal es otro registro. '
        'Elegibilidad = envío + demora aplicable. Inicio de ventana = techo al minuto de la elegibilidad, '
        'fin = inicio + 60 s; fill y vencimiento del intento están en ese fin. El reloj conserva nanosegundos. '
        'No se usa el high/low/close de la ventana futura al decidir o dimensionar. OHLC4 reemplaza sólo la referencia '
        'de ejecución; el slippage y el tick adverso se aplican una vez.\n',
        'Durante la espera siguen funding, garantías, reservas, inventario, deuda y controles de riesgo. '
        'Funding precede al fill simultáneo. No se trasladan holding, cooldown ni correction_deadline. '
        'Una corrección cancelada por su plazo preventivo no es una expiración contra una ventana antigua. '
        'Cancelar antes o exactamente al inicio anula el intento; dentro de una ventana comprometida se conserva la '
        'política diferida original, sin nueva latencia de cancelación. Ningún fill se admite en o después del final exclusivo.\n',
        'La liquidación BASE sigue usando ventana y cupo de volumen: no es un motor independiente del exchange. '
        'Se aprobó reparar la prioridad de los reintentos ya escalados a liquidación; se congeló una identidad nueva '
        'y se ejecutaron controles BASE completos separados. '
        '[Aprobación y transcripción UTF-8](controles/aprobacion_reparacion_transcripcion_utf8.md) · '
        '[Comparación exacta de controles](documentos/control_compatibilidad_base_completa.json). '
        'Las referencias selladas se conservan.\n']
    for family in STAGES:
        text.append(f'![Curvas y drawdown diario: {family}](figuras/{family}.png)\n')
        text.append(f'![Diferencia diaria de patrimonio con BASE: {family}](figuras/{family}_diferencia.png)\n')
    text.extend(['## Actividad, capital y ejecución\n',
        table(['Escenario','Cartera','Activo sin polvo','Descubierto','Capital usado medio','Uso diario medio','Garantía media','Deuda máxima diaria'],[
            [r['scenario'],r['strategy'],fmt(r['invested_fraction'],True),fmt(r['unhedged_fraction'],True),
             fmt(r['capital_deployed_usdt_daily_mean'],digits=2),fmt(r['capital_utilization_daily_mean'],True),
             fmt(r['collateral_usdt_daily_mean'],digits=2),fmt(r['debt_usdt_daily_max'],digits=2)] for r in full]),
        'La actividad integra la unión BTC/ETH sobre toda la trayectoria antes de recortar períodos. '
        'El polvo sigue valorado, pero no cuenta como tiempo activo. El capital utilizado proviene de cada cartera, '
        'no de escalar la referencia. [Actividad, renovaciones y fallos](tablas/actividad.csv), '
        '[eventos y liquidaciones](tablas/eventos.csv), [motivos de cierre](tablas/motivos_cierre.csv), '
        '[ciclos](tablas/ciclos.csv), [demoras de apertura/cierre](tablas/demoras_ciclos.csv), '
        '[órdenes completas](tablas/ordenes.csv), [capacidad](tablas/capacidad.csv), [faltantes](tablas/causas_faltantes.csv) '
        'y [conciliación del ledger](tablas/conciliacion_ledger.csv).\n',
        table(['Escenario','Cartera','Órdenes','Completas','Parciales','Sin fill','Canceladas','Expiradas','Pendientes','Reintentos'],[
            [r['scenario'],r['strategy'],r['orders'],r['orders_complete'],r['orders_partial'],r['orders_no_fill'],
             r['terminal_cancelled'],r['terminal_expired'],r['terminal_pending'],r['retries']]
             for r in tables['ejecucion_resumen'] if r['period']=='full' and r['symbol']=='PORTFOLIO']),
        'Cada pata y cada nuevo intento tienen envío y demora propios. La capacidad usa el minuto realmente elegido, '
        'consumo bruto compartido y orden persistido. BTC/ETH y spot/futuros mantienen cupos separados. '
        'La columna reintentos identifica una nueva orden de igual propósito emitida en el vencimiento de la anterior; '
        'las escaladas a liquidate conservan su propósito distinto y sus eventos de riesgo. '
        'Se distinguen volumen, filtros, cancelación preventiva, plazo de corrección, fin de muestra y fondos/inventario/reservas '
        'cuando la evidencia no permite una causa más específica. No se atribuye falsamente cada parcial al cupo.\n',
        '![Distribución de latencia realizada](figuras/cronologia.png)\n',
        '[Cronología por propósito y período](tablas/cronologia_resumen.csv): percentiles sólo sobre órdenes con fill; '
        'una orden no ejecutada conserva latencia ND. La elegibilidad no equivale a ejecución ni a confirmación del exchange.\n',
        '[L frente a LC de igual demora](tablas/comparacion_L_LC.csv) presenta ambos valores y LC−L. '
        'Es una comparación descriptiva de políticas con trayectorias distintas, no un efecto aditivo aislado de la apertura.\n',
        '## Incidentes y límites de valoración\n',
        'El [catálogo completo](tablas/episodios_descubiertos.csv) acompaña la selección previa de los cinco episodios '
        'de mayor duración por cartera, con desempate por inicio y activo. Se agrega el 24/03/2023 cuando existe '
        'inventario en esa variante, incluso polvo con riesgo de precio; las clases se registran sin convertir polvo '
        'en tiempo activo. No se impone una duración de 121 minutos. [Detalle e interpretación](incidentes.md).\n',
        'Los casos usan minutos y cada estado del ledger original. El episodio comienza después del movimiento '
        'de su activo y termina antes del movimiento que lo cierra, conservando funding y movimientos simultáneos intermedios. '
        'Las fronteras sin cambio de cantidades y la ventana calendario tienen políticas explícitas en el resumen. '
        'La valoración usa precios disponibles causalmente y reglas BASE. La pérdida desde el inicio corresponde '
        'al patrimonio de la cartera; '
        'spot/corto y holgura se muestran por el activo del caso. No se infiere un máximo intradía global. '
        'Un spot arrastrado acredita valoración, no venta durante una suspensión. La estimación futures_scaled del mark '
        'se identifica por separado; no se trata como mark oficial. Al extinguirse el corto, margen de ese contrato es ND.\n',
        '## H1, H2 y H3\n',
        'H1 reutiliza una sola evaluación BASE autenticada, después de comparar forecast, historia, targets y disponibilidad '
        'por corrida. No multiplica el tamaño de muestra por las variantes. La oportunidad H3 mantiene forecast, basis, '
        'umbral y operatividad, independientemente de llegada de órdenes, fondos o posiciones. '
        '[Invariancias](tablas/invariancias.csv) · [H1 original](hipotesis_base/h1_resumen.csv).\n',
        'H2 compara ambas estrategias del mismo escenario y período: CAGR condicional finito, definido y positivo; '
        'Sharpe definido y superior al permanente. RF sigue en cero. H3 conserva los cortes 2022–2023 y enero 2024–agosto 2026: '
        'ambos indicadores bajan = favorable; ambos suben = contraria; otros casos evaluables = mixta; faltantes = no concluyente.\n',
        table(['Escenario','H2 completo','CAGR condicional','H3 contraste original'],[
            [r['scenario'],r['verdict'],fmt(r['conditional_cagr'],True),next(x['h3_descriptive'] for x in tables['h3_resumen']
               if x['scenario']==r['scenario'] and x['period']=='full')] for r in tables['h2'] if r['period']=='full']),
        '[H2: todos los períodos y razones](tablas/h2.csv) · [H3: cortes y desglose anual](tablas/h3_resumen.csv).\n',
        '## Evidencia y alcance\n',
        'CSV y Parquet preservan precisión textual; las tablas de decisiones voluminosas se incluyen sólo en Parquet. '
        'El verificador incluido recalcula resultados desde registros y extractos compactos; comparte funciones con el constructor. '
        'La opción con raíz de datos vuelve a extraer ventanas y casos desde fuentes masivas; el modo offline no afirma leer '
        'archivos ausentes. Los hashes, código, configuraciones, pruebas y logs enlazan las identidades. '
        'La incompatibilidad histórica de inventario/config permanece separada de los cambios nuevos autorizados.\n',
        'No se recalcularon SOFR, concentración completa ni la serie intradía sellada. Shocks y contrafactual sin interrupción '
        'no se ejecutaron: bloques 5 y 6 pendientes, igual que la revisión transversal/redacción. '
        '[Matriz de cumplimiento](matriz_cumplimiento.md) · [Fuentes de figuras](figuras/fuentes.json).\n'])
    return '\n'.join(text)


def write_docs(package,tables,index,partial=False):
    figures(package,tables)
    text=report(tables,index,partial)
    (package/'reporte.md').write_text(text,encoding='utf8')
    (package/'reporte.html').write_text(render_html(text),encoding='utf8')
    (package/'sintesis.md').write_text('# Síntesis integrable: bloque 4\n\n'+'\n\n'.join(summary_lines(tables))+
        '\n\nSe conservan seis sensibilidades exploratorias separadas. Las trayectorias continuas, la actividad sin polvo y los '
        'componentes contables se recalculan para cada cartera. No se selecciona un parámetro ni se atribuyen probabilidades. '
        'El drawdown comparativo es diario; los incidentes son ventanas locales con cobertura explícita.\n',encoding='utf8')
    cases=['# Incidentes seleccionados\n','Selección fijada antes del lote: top cinco por duración y 24/03/2023 cuando hay exposición. '
        'El catálogo completo conserva los episodios restantes. Ningún máximo de esta tabla representa toda la muestra intradía.\n',
        table(['Escenario','Cartera','Caso / activo','Inicio UTC','Fin UTC','Observaciones','Pérdida máxima desde inicio','Holgura mínima observada','Obs. spot arrastrado','Obs. mark arrastrado'],[
            [r['scenario'],r['strategy'],r['case_id']+' / '+r['symbol'],iso(r['start_ns']),iso(r['end_ns']),r['observations'],
             fmt(r['max_loss_from_start_usdt'],digits=4),fmt(r['minimum_observed_margin_headroom_usdt'],digits=4),
             r['spot_carried_observations'],r['mark_carried_observations']] for r in tables['incidentes_resumen']]),
        '[Selección](tablas/incidentes_seleccion.csv) · [Detalle temporal](tablas/incidentes_detalle.parquet) · '
        '[Resumen y cobertura](tablas/incidentes_resumen.csv) · [Eventos originales del caso y hora previa](tablas/incidentes_eventos.parquet).\n',
        'La holgura sólo es evaluable donde existe corto y mark válido. Un precio causal arrastrado conserva una valoración '
        'contable, no evidencia de ejecución. Los códigos de calidad distinguen falta de minuto, volumen cero y dato inválido. '
        'El flag de estimación del mark es independiente de su disponibilidad. Los índices del ledger y los IDs de '
        'movimiento fijan las fronteras de cada episodio: POST del movimiento inicial y estado inmediatamente anterior '
        'al movimiento final, conservando los movimientos simultáneos intermedios. Cuando sólo cambia el estado '
        'operativo sin movimiento de cantidades se usa POST de todo el timestamp inicial y PRE del timestamp final, '
        'con motivo explícito. El 24/03 es una ventana calendario: incluye PRE y todos los POST dentro del día UTC. '
        'Un episodio censurado por el final exclusivo sólo se observa hasta final−1 ns; conserva su duración '
        'y no consume precios disponibles en el límite excluido. '
        'La pérdida parte del equity de inicio, '
        'no del máximo anterior al incidente. Los helpers locales usan float64, como el bloque de riesgo original; '
        'la conciliación contable diaria/periódica conserva Decimal y tolerancia 1E-8 USDT. '
        'Los casos que comparten cartera/ventana pueden compartir pérdida patrimonial: no se suman entre activos.\n']
    for r in tables['incidentes_resumen']:
        if r.get('selection')=='top5_duration' and r.get('rank')==1:
            cases.append(f"![{r['scenario']} / {r['strategy']}: mayor duración](figuras/incidente_{r['scenario']}_{r['strategy']}.png)\n")
    (package/'incidentes.md').write_text('\n'.join(cases),encoding='utf8')
    audit=['# Auditoría de ejecución\n',table(['Escenario','Cartera','Estado técnico','Estado económico','Run ID','Replay s','RAM pico GiB'],[
        [r['scenario'],r['strategy'],r['status'],r['engine_status'],r['run_id'],fmt(r.get('replay_seconds'),digits=2),
         fmt(r['peak_process_bytes']/1024**3,digits=3) if r.get('peak_process_bytes') else 'reutilizada'] for r in index]),
        'Primero se midió un replay sin concurrencia. Se habilitaron como máximo dos procesos, con un escritor de resultados. '
        'Los controles BASE completos son adicionales a las doce variantes y no reemplazan sus referencias. '
        'Se comparan once artefactos completos a precisión original y en orden persistido, excluyendo únicamente run_id '
        'y unidades de presentación. La primera comprobación como multiconjunto se conserva como antecedente y fue '
        'sustituida por la verificación sensible al orden antes de interpretar las variantes.\n',
        '[Control completo](documentos/control_compatibilidad_base_completa.json) · [Compatibilidad técnica](documentos/control_compatibilidad.json) · '
        '[Identidades, comandos y tiempos](indice_corridas.json). Los logs de lanzamiento y puertas de cada etapa se guardan en `ejecucion/`.\n',
        'El auditor enlaza referencias originales OHLC/VWAP, demoras por propósito, ventana, disponibilidad, eventos terminales, '
        'secuencia de fills/ledger, precios adversos, fees y capacidad compartida. Las órdenes sin fill no reciben latencia cero. '
        'Los propósitos se contrastan con mercado/lado, cargos y transiciones causales. Las pruebas de corrupción renuevan hashes '
        'sobre copias descartables; no modifican el original. Constructor y verificador comparten lógica declarada.\n',
        'Las pruebas se conservan en `pruebas/`. Las suites solapadas no se suman y una omisión no cuenta como aprobación. '
        'Los controles posteriores al sello se registran fuera del paquete en la carpeta de trabajo, identificando el hash comprobado.\n']
    (package/'auditoria_ejecucion.md').write_text('\n'.join(audit),encoding='utf8')
    readme='''# Evidencia de ejecución y demoras

[Reporte](reporte.md) · [HTML](reporte.html) · [Síntesis](sintesis.md) · [Incidentes](incidentes.md)

Desde una copia limpia, offline y con Python y dependencias fijadas en
`herramientas/pyproject.toml` y `herramientas/uv.lock`:

```powershell
python -B -X utf8 herramientas/scripts/verify_execution_delays.py --package . --output ../auditoria_nueva.json
```

El destino es nuevo y externo. No necesita HEAD, índice Git ni la ruta del proyecto original.
Recalcula cierres/períodos, exposición, H2/H3, órdenes/fills/ledger, precios,
cronología, capacidad e incidentes desde los extractos incluidos. No hace replay.
H1 reutiliza una sola población BASE después de verificar proyecciones y targets.
Constructor y verificador comparten funciones; no constituyen motores independientes.

Para volver a autenticar y extraer las ventanas desde fuentes masivas locales,
agregar `--data-root D:/Backtesting`; ese control exige esos archivos.
El CSV forecast original está comprimido sin pérdida con tamaño y hash originales.
Las carteras completas permanecen en los destinos indicados por el índice.

Pruebas semánticas del paquete (copias descartables, hashes renovados):

```powershell
$env:EXECUTION_DELAYS_PACKAGE = (Resolve-Path .).Path
python -B -m pytest herramientas/tests/integration/test_execution_delays_package.py -q -p no:cacheprovider
```

Los registros posteriores al sello, incluida la exportación binaria mediante
índice temporal aislado y la comprobación desde otra ruta, permanecen fuera
del paquete. No hay commit, push ni modificación del índice del usuario.
'''
    (package/'README.md').write_text(readme,encoding='utf8')
    compliance=[('1–3: alcance y referencias','documentos/autenticacion_referencias.json; documentos/protocolo.md'),
        ('4: identidad y compatibilidad','documentos/control_compatibilidad_base_completa.json; controles/aprobacion_reparacion_transcripcion_utf8.md'),
        ('5–6: precio y tiempo','tablas/ordenes.csv; tablas/fills_conciliados.csv; fuentes/volumen/'),
        ('7: fixtures, regresión y adulteraciones','pruebas/; herramientas/tests/'),
        ('8: puertas por etapa','ejecucion/; indice_corridas.json'),
        ('9: finanzas, actividad e incidentes','tablas/metricas.csv; tablas/episodios_descubiertos.csv; incidentes.md'),
        ('10: hipótesis','tablas/invariancias.csv; tablas/h2.csv; tablas/h3_resumen.csv'),
        ('11: archivos y portabilidad','README.md; manifiesto_paquete.json; controles externos de la carpeta de trabajo'),
        ('12: exclusiones y avance','documentos/protocolo.md; matriz global e historial en el proyecto')]
    (package/'matriz_cumplimiento.md').write_text('# Matriz de cumplimiento\n\n'+
        table(['Requisitos del protocolo','Evidencia'],compliance)+
        '\nLa verificación posterior al sello se registra externamente para mantener sus bytes inmutables.\n',encoding='utf8')
    write_json(package/'documentos/resumen_estados.json',dict(
        technical=dict(Counter(r['status'] for r in index)),economic=dict(Counter(r['engine_status'] for r in index)),
        partial=partial,publication='local only; no commit or push'))

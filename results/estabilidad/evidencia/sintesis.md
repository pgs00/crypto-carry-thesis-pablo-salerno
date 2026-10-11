# Síntesis integrable: estabilidad, incertidumbre y bloques previos

Esta síntesis reutiliza cifras identificadas por paquete, ruta, SHA-256 y run_id. La autenticación es selectiva: se releen los resúmenes y registros utilizados; la integridad histórica integral y compatibilidad BASE se reutilizan del bloque 5. No se repiten los bloques 1–5 ni se simula dentro del bootstrap.

## H1: capacidad descriptiva del pronóstico

[Tabla por pregunta: H1](tablas/sintesis_h1.csv). Se conservan MAE por activo y el promedio BTC/ETH 50/50; el bootstrap pondera sumas/conteos originales, con exclusiones del borde final. Un delta MAE EWMA menos no-cambio negativo favorece descriptivamente EWMA. H072 y H336 tienen horizontes distintos: sus MAE sólo se comparan dentro de cada horizonte. B1 interpreta BASE; B3/B4 preservan el pronóstico y sus controles de invariancia. B5 no añade observaciones históricas al remuestreo.

## H2: retorno positivo y Sharpe superior al permanente

[Tabla por pregunta: H2](tablas/sintesis_h2.csv). BASE total: no_favorable; CAGR condicional 1.633% y diferencia Sharpe -1.5713. En 2022 el Sharpe condicional es ND por volatilidad nula: no se reemplaza por cero. Los días inactivos siguen incluidos.

Las excepciones favorables acreditadas son las siguientes; se conservan todos sus períodos, sin generalizar el resultado total a los años ni seleccionar un ganador.

| Bloque / escenario | Períodos favorables H2 | Fuente |
|---|---|---|
| B2 / H336 | 2023, 2024 | [tabla autenticada](fuentes/sintesis_referencias/B2/tablas/h2.csv) |
| B3 / A050 | 2024 | [tabla autenticada](fuentes/sintesis_referencias/B3/tablas/h2.csv) |
| B3 / A100 | 2022-2023, 2023, 2024, full | [tabla autenticada](fuentes/sintesis_referencias/B3/tablas/h2.csv) |
| B3 / C03 | 2022-2023, 2023, 2024 | [tabla autenticada](fuentes/sintesis_referencias/B3/tablas/h2.csv) |
| B3 / S02 | 2024 | [tabla autenticada](fuentes/sintesis_referencias/B3/tablas/h2.csv) |
| B4 / L01 | 2022-2023, 2023, full | [tabla autenticada](fuentes/sintesis_referencias/B4/tablas/h2.csv) |
| B4 / LC01 | 2022-2023, 2023 | [tabla autenticada](fuentes/sintesis_referencias/B4/tablas/h2.csv) |
| B4 / LC05 | 2022-2023, 2023 | [tabla autenticada](fuentes/sintesis_referencias/B4/tablas/h2.csv) |
| B5 / CF_SIN_INTERRUPCION | 2022-2023, 2023 | [tabla autenticada](fuentes/sintesis_referencias/B5/resultados/h2.csv) |

Los inicios B6 comparan las dos estrategias del mismo inicio y período. Sus cuentas nuevas desde 10.000 USDT se distinguen de los tramos BASE con saldos heredados. Los intervalos marginales de CAGR y diferencia Sharpe complementan el veredicto histórico; dos intervalos al 95% no constituyen un contraste conjunto al 95%.

## H3: contraste original de regímenes

[Tabla por pregunta: H3](tablas/sintesis_h3.csv). El contraste original conserva 2022–2023 frente a 2024–agosto de 2026, oportunidad media en pb/168 h y CAGR condicional. BASE y las sensibilidades examinadas mantienen la dirección contraria documentada; los años son un desglose descriptivo. I2023/I2024 no validan H3 original por faltar parte o todo el primer régimen. El bootstrap conserva regímenes, años y pesos históricos.

## Retorno, capital, costos y comparador remunerado

[Tabla por pregunta](tablas/sintesis_retorno_capital.csv). BASE, 1.704 días: conditional: retorno 7.858%, CAGR365 1.633%, capital medio utilizado 19.807%, actividad sin polvo 28.318%; permanent: retorno 16.801%, CAGR365 3.382%, capital medio utilizado 82.631%, actividad sin polvo 98.208%. Son retornos netos de los costos modelados; el P&L monetario de cuentas con denominadores distintos no es directamente comparable. Pocos ciclos, inactividad y concentración siguen limitando la extrapolación; B1 no elimina ciclos para fabricar un CAGR contrafáctico.

SOFR: retorno 20.595% y CAGR365 4.093% en la cuenta hipotética bruta USD aprobada, ACT/360 y paridad nominal 1 USDT = 1 USD. No equivale a una cuenta accesible ni a rentabilidad libre de riesgo realizada; no se remunera caja ni garantías del carry. Acceso, costos y riesgo no son equiparables.

[Escenarios previos con sus IDs](tablas/sintesis_escenarios_previos.csv): B2 cambia señal/entrada; B3 mantiene selección a 34 pb y distingue costos, participación y capital; B4 altera convención/demora; B5 usa trayectorias hipotéticas aprobadas, recuperación impuesta y anclas fijas. Sus diferencias no identifican causalidad histórica ni probabilidades.

## Riesgo, garantías y definiciones de drawdown

[Tabla por pregunta](tablas/sintesis_riesgo.csv). El drawdown diario de las sensibilidades usa cierres diarios. El intradía global previo reconstruye la trayectoria BASE/MARGEN_2X con cobertura y valoración identificadas; la suspensión de marzo de 2023 conserva el precio antiguo/proxy hipotético separado. Las ventanas locales B4/B5 no son máximos intradía globales ni sustituyen esa reconstrucción. Garantías, reservas y transferencias no se agregan como P&L.

## Diagnóstico dirigido del defecto de prioridad de liquidación en B2/B3

Resultado: 28/28 variantes con precondición excluida por evidencia; 0 afectadas o indeterminadas. [Corridas](tablas/diagnostico_b2_b3_corridas.csv), [cobertura](tablas/diagnostico_b2_b3_cobertura.csv), [secuencias](tablas/diagnostico_b2_b3_eventos.csv).

El código autenticado de cada corrida inicia liquidation_pending=False; su única activación ocurre en _close e inmediatamente registra close_requested con liquidation=True. _event persiste todos los eventos; se contrastan contadores nativos, manifiesto de corrida completa, log de finalización, órdenes y posiciones. Se busca escalada seguida por timeout, reintento ordinario o HOLDING con corto remanente, por activo y sin inferir el estado desde un fill ausente. La exclusión se refiere sólo a esa rama y esas corridas; no demuestra equivalencia universal entre motores ni certifica reglas históricas del exchange.

No quedan run_id indeterminados para esta rama dentro de las 28 variantes examinadas. El resultado permite cerrar este pendiente dirigido, manteniendo la revisión transversal separada.

## Incertidumbre, cobertura y estado

El remuestreo BASE utiliza bloques circulares emparejados dentro de año/segmento contiguo: 28 días principal y 14/56 como sensibilidad, 5.000 réplicas por longitud, raíz 20261001, PCG64/SeedSequence e intervalos percentiles marginales nominales 95%. Circularidad no es contigüidad real; estratificar corta dependencia entre años y supone estabilidad aproximada dentro del estrato. No garantiza cobertura exacta ni elimina no estacionariedad. Las frecuencias no son probabilidades de verdad de hipótesis o ganancia futura. Menos de 95% evaluables deja el intervalo principal ND; cuantiles finitos quedan condicionados a evaluabilidad. No se selecciona longitud por conveniencia.

| Efecto BASE, bloques 28 días | Punto | IC marginal nominal 95% | Evaluables |
|---|---:|---:|---:|
| H1: delta MAE BTC/ETH 50/50 (pb/168 h) | -2.4043 | [-2.7263, -2.0905] | 5000/5000 |
| H2: CAGR condicional | 1.633% | [0.961%, 2.386%] | 5000/5000 |
| H2: diferencia Sharpe RF=0 | -1.5713 | [-4.2294, -0.2309] | 5000/5000 |
| H3: diferencia oportunidad (pb/168 h) | 2.6793 | [-1.0766, 7.3166] | 5000/5000 |
| H3: diferencia CAGR (puntos porcentuales) | 0.968 pp | [-0.413 pp, 2.388 pp] | 5000/5000 |

Los inicios alternativos usan historia ya examinada y no son validación fuera de muestra. 2026 es parcial, no se crean ceros previos al inicio y cada corte muestra sus fechas reales.

Las tablas B6 de inicios e intervalos ya se incorporaron; su validación corresponde a los verificadores financiero y estadístico del paquete.

Se leyó la extracción autenticada de la consigna académica B5 y el feedback E3. El registro [lecturas](fuentes/sintesis_lecturas.json) identifica el encargo general si fue localizado, o explicita su ausencia en las ubicaciones consultadas. La revisión transversal y Word/PDF permanecen pendientes; no hay commit, push ni cambios del índice.

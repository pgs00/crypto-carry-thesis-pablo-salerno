# Registro de ejecución — plan: documentos/plan.md

2026-09-27: encargo leído; rama codex/crypto-carry, HEAD 120f94309e724a7a25e68e5ade67eed43a98f9e7,
árbol e índice limpios al inicio. Sin AGENTS.md en la raíz ni ancestros revisados.
Se preservó hash binario del índice y de src/configs en estado_inicial.json.
Regla: aplicar el encargo completo sin pedir revisión del plan; la aprobación
puntual del benchmark sigue pendiente. Protocolo escrito antes de tablas nuevas.

Etapa 1: completa. Verificadores archivados de padre/corrección, E3 e intradía
compacto finalizaron con código 0; comandos y salida en auditorias. Fuente real
de entradas: signals.parquet; renovaciones: renewal_diagnostics.parquet.

Etapa 2: completa. Diez ciclos condicionales y veinte permanentes; 3.408 cierres
de cartera conciliados; comprobación adicional por activo, componentes y ocho
períodos. Polvo fuera de ciclo identificado mediante fronteras, sin bolsa residual.

Etapa 3: completa. 21.009 evaluaciones clasificadas: 20.448 entradas y 561
renovaciones. Se verifica partición, orden original, funding de la permanente
no aplicado, umbral cero de renovación y órdenes iniciales únicas. Las acciones
sin evaluación exacta permanecen explícitas. Se corrigió la preservación del
ordinal de órdenes filtradas con fixture rojo y verde.

Etapa 4: completa. Finanzas/exposición corregidas integradas sin modificaciones.
Propuesta SOFR bruta y alternativa SGOV documentadas. 1.166 tasas públicas
descargadas exclusivamente para cobertura; ningún retorno remunerado calculado.
La aprobación puntual y controles del futuro benchmark permanecen pendientes.

Pruebas previas: fixtures contables y de filtros fallaron inicialmente por
módulos ausentes; luego pasaron. Una prueba sintética carecía de basis/forecast:
se completó su entrada, sin relajar el verificador. La suite de 26 pruebas,
incluida manipulación de cifras/intervalos/clasificaciones/denominadores, pasó
antes del armado del paquete. Ruff se limita a los archivos nuevos.

Etapa 5: en cierre. Revisión independiente de sólo lectura, pruebas finales,
sellado y verificación portable dejarán resultados externos con el hash exacto.

Cierre previo al sello: 173 pruebas pasaron en 39,10 s y Ruff pas?. Dos
observaciones del revisor se corrigieron con regresiones; ver revision.md.
La auditor?a del sello y de portabilidad se registra externamente despu?s
del armado, sin modificar este documento archivado.

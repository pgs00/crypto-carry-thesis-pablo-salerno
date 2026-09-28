# Registro de ejecución del bloque 3

2026-09-27: encargo leído íntegramente. Rama codex/crypto-carry, HEAD
af9fc227915a340665fce2f917d810dec6507d12. Árbol e índice iniciales limpios.
Huellas iniciales y snapshot de código previo guardados antes de modificar src.
Regla de trabajo: ejecutar directamente el alcance autorizado y conservar
todos los intentos, fallos y correcciones. No hay commits ni staging.

## Referencia y extensión

- Se autenticaron seis paquetes previos y ambas BASE originales. Se cotejaron
  los 1.731 identificadores de entrada con los archivos y el manifiesto local.
- La extensión económica está limitada a config, costs, diagnostics y la
  declaración de supuestos. Identidad congelada:
  `aff0e047e4638219c5fba35959e160291802dcfad2269ecfc69a8f0e08495308`.
- Compatibilidad: doce comparaciones deterministas de código previo/nuevo,
  modos anteriores y BASE con selección fija; proyecciones económicas iguales.
  Los cuatro campos diagnósticos nuevos se excluyen explícitamente de esa
  proyección, sin excluir resultados, fills, ledger o estados.
- Pruebas antes del histórico: 1.033 aprobadas, 13 omitidas por requerir un
  paquete de integración del bloque 2. Este conteo no se suma con los de suites
  focalizadas. Fallos de fixtures y sus correcciones quedan en `pruebas/`.
- Recursos medidos primero sin concurrencia. Se habilitaron como máximo dos
  replays y un único escritor de materialización.

## Revisión técnica y ejecución

- Una revisión independiente de la extensión no encontró cambios económicos
  ajenos al encargo. Señaló cuatro protecciones de recuperación: identidad de
  estrategia/escenario, exclusión mutua por par, H3 por intento y autenticación
  de raíz/datos reales. Se incorporaron como revisión técnica 2, conservando
  protocolo y runner originales. La identidad económica permanece igual.
- Costos/deslizamiento se ejecutan primero. C02 ambas estrategias y C03
  condicional terminaron y conciliaron; las restantes siguen en ejecución.
  Los estados individuales y logs son la fuente vigente de este registro.
- El candidato parcial 01 se construyó con cinco carteras verificadas. Su
  verificador detectó una diferencia de serialización de listas en CSV
  (`episodios_descubiertos.states`); no es un residual financiero ni exige
  repetir el motor. Se conserva el candidato y el fallo; la corrección se
  probará y el siguiente candidato tendrá un destino nuevo.

## Límites mantenidos

El auditor no adjudica a volumen los faltantes que no puede separar entre
fondos, inventario y reservas. H1 se reutiliza una sola vez con igualdad de
proyecciones; H3 se recalcula con nuevos CAGR y oportunidad BASE autenticada.
No hay nuevas series intradía, remuneración de caja, Word/PDF ni publicación.

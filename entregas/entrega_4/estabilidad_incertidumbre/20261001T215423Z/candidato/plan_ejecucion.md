# Plan de ejecución B6

Especificación vinculante: `C:/Users/pablo/Downloads/Prompt_Codex_Bloque_6_Estabilidad_Incertidumbre.md`, leída íntegramente. Encargo autorizado: cuatro carteras y protocolo estadístico fijo. No requiere nueva aprobación. Fecha del encargo: 2026-10-01.

Destino: `entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/candidato`.

Estado vigente: **B6 ejecutado y verificado**, cierre 2026-10-01 23:00:11 UTC. Paquete final válido: `entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/paquete_final_verificado`. Certificado: `controles_finales_corregidos/verificacion_offline.json` dentro de la misma entrega. Las anotaciones de avance inferiores conservan la secuencia histórica; el cierre al final de este documento las actualiza.

## Restricciones

- I2023/I2024 por conditional/permanent, sólo cambia start respecto de BASE; precarga 360 h; efectivo inicial 10.000 USDT; fin exclusivo 2026-09-01.
- Reutilizar motor corregido, reglas, auditorías y compatibilidad B5; no modificar src ni repetir BASE/B1-B5.
- Bootstrap BASE circular emparejado por año y segmento contiguo: 28 días principal, 14/56 sensibilidad; 5.000 réplicas cada uno; PCG64/SeedSequence raíz 20261001; percentiles 0,025/0,975 lineales; lotes 128-256.
- Coordinador único, procesos independientes, máximo cuatro carteras y seis trabajadores totales, crecimiento presupuestado a 4 GiB y reserva de 6 GiB. Hilos internos uno; sin llamadas al modelo durante la espera.
- Candidato editable y un paquete final; sin Word/PDF, limpieza, commit, push ni cambios del índice.

## Tareas e interfaces

- [x] 1. Contrato/runner y fixtures: `scripts/stability_uncertainty_contract.py`, `scripts/run_stability_uncertainty.py`, `tests/unit/test_stability_runner.py`. Entradas autenticadas una vez, code_hash vigente, tabla inmutable de archivos y metadatos; cuatro estados exclusivos en `ejecuciones/{scenario}__{strategy}.json` con `path`, `run_id`, `manifest_sha256`, `status`. Test de matriz cerrada, inicio real, precarga, disponibilidad de funding, fin exclusivo y protección de referencias.
- [x] 2. Bootstrap: `scripts/stability_uncertainty_bootstrap.py`, `tests/unit/test_stability_bootstrap.py`. CLI `--candidate PATH --data-root D:/Backtesting`, función `build(candidate, data_root)`; insumos compactos en `estadistica/`; tablas/réplicas autocontenidas. `verify(candidate)` recalcula desde insumos incluidos. Fixtures escalares/vectorizados, serial/paralelo, huecos/años, conteos H1, degeneración y compuestos.
- [x] 3. Métricas/reporte: `scripts/stability_uncertainty_report.py`, `tests/unit/test_stability_report.py`. `build(candidate, data_root)` espera cuatro estados; `verify(candidate)` recalcula métricas desde evidencia incluida. Cuenta nueva versus BASE heredada, anual/cortes con cobertura real, H2 corregido y H3 original limitado a BASE. Conciliación Decimal 1E-8 y auditoría vigente de ejecución.
- [x] 4. Síntesis/pendiente: `scripts/stability_uncertainty_synthesis.py`; `build(candidate, project, data_root)` produce síntesis y tablas de evidencia histórica, con diagnóstico dirigido B2/B3 sin replay y cobertura explícita. Fuentes y certificados copiados selectivamente.
- [x] 5. Coordinación/entrega: `scripts/coordinate_stability_uncertainty.py`, `scripts/verify_stability_uncertainty.py`, `scripts/package_stability_uncertainty.py`. Cola reanudable, bloqueos, recursos y tiempos; comando externo PowerShell preparado al comienzo. Posprocesamiento, regresión pertinente/Ruff, sello y una verificación integral offline desde copia limpia. Índices globales actualizados sólo según estado real.

## Revisión prioritaria

- Herencia de inventario/denominador frente a reinicio, sin filas previas ficticias.
- Insolvencia o muestra parcial: fechas reales y ND, nunca completar cash desconocido.
- Retorno diario y CAGR conservan convenciones financieras originales.
- Entrada modificada o trabajador huérfano: bloquear reutilización incompatible/duplicación.
- Verificador debe detectar adulteración de datos y tipos, no solamente hashes de tablas finales.

## Registro de decisiones y avance

- Reutilización del checkout limpio en rama `codex/crypto-carry`, HEAD `c25efa189cdf4c509d4f571756cb9bd8b6776a08`; trabajo separado en nuevos auxiliares y nuevo destino, fuentes económicas intactas. Índice inicial SHA256 `07e15cd95a546b1b1bb73239414e47a141cd7484b906529695afe2e194ed04cb`.
- Los requisitos de aprobación, commit, limpieza y suites completas de las skills se subordinan al encargo explícito: ejecución ya autorizada, sin commit/limpieza y regresión pertinente sin suites históricas solapadas.
- Tarea 1 completada: seis fixtures aprobados, Ruff limpio; protocolo congelado con código económico `ac1a148ac22eaa6498cdf9e35d6a825f6d81ad29a015fc6d892b57f71ce8a998`. Se autenticaron una vez 1.731 identidades de entrada y cuatro referencias originales/corregidas. No cambió `src/`.
- Tarea 2: cálculo BASE completado por proceso analítico único; 15.000 réplicas, 17 efectos, 51 intervalos, 1.704 días, cinco estratos anuales; revisión de verificador y pruebas en curso. No se ejecutó el motor en el remuestreo.
- Tarea 3: implementación y 14 fixtures específicos aprobados; regresión financiera pertinente anterior de 131 pruebas y smoke de BASE preservada con fuentes compactas B5. Los conteos no se suman: son controles de alcance distinto y parcialmente solapado. Pendiente aplicar a nuevas carteras al terminar.
- Coordinador local lanzado por PowerShell PID 15200; coordinador Python PID 12344. Comando: `& '.\scripts\Start-B6.ps1'` desde la raíz. Comenzó con dos carteras por presupuesto de memoria; cola cerrada de cuatro. Estado persistente en candidato/progreso_local.json. No hay llamadas al modelo desde el proceso local.
- Verificador de sello y protocolo: tres pruebas negativas aprobadas (adulteración real de CSV, archivo extra, tipo incorrecto y ruta insegura, parámetros estadísticos). Finalizador autónomo implementado; revisión fresca solicitada antes de habilitar `controles/desarrollo_listo.json`. Una única verificación integral offline se reserva para la copia del paquete final.
- Revisión fresca terminada: dos hallazgos importantes de reanudación corregidos. Pruebas negativas reprodujeron cinco posprocesos huérfanos no detectados, cierre bloqueado aceptado y certificado de otro sello aceptado; los siete fallaban antes. Después: 11/11 pruebas de entrega aprobadas, incluido cierre completo sin acceso a datos ni repetición offline. Se preservó el coordinador inicial exacto en `codigo_coordinador_inicial`; las correcciones de reanudación se aplican a futuros lanzamientos. El proceso activo conserva su versión inicial, que no cambia el cálculo ni el posprocesamiento en la trayectoria normal.
- Bootstrap terminado/verificado: 16 fixtures; identidad serial/paralela de índices y estadísticas, CSV adulterado y tipos rechazados; 10,88 s de construcción, 11,54 s de verificación compacta de desarrollo, máximo 588 MB. 15.000 réplicas, 75.000 flujos, 17 efectos y 51 intervalos, sin degeneración. Reutilización autenticada probada sin recalcular. Verificación integral final sigue reservada al cierre local.
- Síntesis/diagnóstico terminado: 12 fixtures y Ruff aprobados; 28/28 variantes B2/B3 excluyen la precondición de la rama `liquidation_pending` según código, contadores y registros íntegros. 31.180 eventos, 42.906 órdenes y 113.731 estados; no una equivalencia universal. El cierre actualizará la fila del alcance con esta limitación. Consigna y feedback consultados; encargo general no localizado en ubicaciones consultadas.
- Estado último comprobado para traspaso: una cartera finalizada, otras dos activas y una en cola; coordinador PID 12344. No se supervisan porcentajes. El cierre ejecutará reporte de nuevas carteras, síntesis actualizada, regresión pertinente/Ruff y una única copia offline final, condicionado a que todos los controles pasen. Word/PDF y revisión transversal siguen pendientes.

## Cierre verificado

- Cuatro carteras previstas completadas; cero repeticiones de BASE. Reporte y síntesis actualizados con los nuevos inicios.
- Regresión pertinente original: 148 pruebas aprobadas. Reparación del exportador: 14 pruebas de entrega aprobadas; los conteos se solapan y no se suman. Ruff aprobado.
- La primera exportación excluyó indebidamente `uv.lock`; la verificación se detuvo antes de recalcular resultados. Se corrigió el filtro de locks y se agregó autenticación completa del código antes de sellar. Se conserva el intento fallido intacto y no vigente, sin limpieza.
- Único paquete final válido: `paquete_final_verificado`, 662 archivos sellados; SHA-256 del manifiesto `8cca7f25e8d83f0e9b879574b1f06c77b8ca2a9aa6ae07fdd94baf80e73c829d`.
- Una verificación integral corregida pasó en 24,74 s desde copia aislada, con acceso prohibido al repositorio original y a D:/Backtesting. Recalculó métricas/conciliaciones de seis carteras únicas (cuatro nuevas y dos BASE conservadas), las 15.000 réplicas y 51 intervalos y las ocho tablas de síntesis desde evidencia compacta. Ninguna repetición del motor.
- Los 126 archivos analíticos y los 40 archivos de identidad económica se conservaron. Índice Git sin cambios; candidato editable y referencias anteriores intactas. Matriz e índice de versiones actualizados a `ejecutado`.
- Revisión transversal y Word/PDF pendientes como etapas posteriores. Esta actualización afecta sólo notas mutables de trabajo; el paquete sellado conserva el plan y el traspaso históricos, y su certificado externo fija el estado final.

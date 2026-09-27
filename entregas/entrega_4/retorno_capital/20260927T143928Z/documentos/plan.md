# Plan de implementación del bloque retorno y capital

Ejecución nativa con pruebas previas y verificación por etapa. El encargo del
usuario autoriza completar el trabajo; no requiere otra aprobación del plan.
La única aprobación pendiente corresponde a la ficha del benchmark.

Objetivo: dos análisis completos, integración anual y propuesta remunerada.
Arquitectura: posprocesadores pequeños en `scripts/return_capital/`, constructor
y verificador CLI; Python 3.14, Decimal, PyArrow, Matplotlib, pytest y Ruff.
Especificación y restricciones: `encargo_usuario.md` y `protocolo.md`.

- [x] 1. Autenticar entradas y documentar esquemas/linaje. Guardar auditoría,
  entorno, rama, HEAD e identidad del índice; no mutarlos.
- [x] 2. Escribir y observar fallar fixtures contables/concentración. Implementar
  `accounting.py` y `concentration.py`. Conciliar cierres y fronteras; sólo
  interpretar al pasar el control de 1E-8.
- [x] 3. Escribir y observar fallar fixtures de filtros/claves/acciones.
  Implementar `decisions.py`; comprobar particiones, orden, permanente,
  renovación y cobertura de enlaces.
- [x] 4. Integrar tablas corregidas sin modificar números. Investigar dos
  candidatos como máximo; archivar originales públicos y ficha pendiente.
- [x] 5. Construir reporte MD/HTML, CSV, figuras, manifiesto y herramientas
  portables. Verificar relaciones y manipulaciones; ejecutar pruebas y Ruff.
  Comprobar otra ruta y preservación final antes de entregar localmente.

Atención de revisión: empates con funding previo a fills; polvo heredado;
aperturas fallidas; ciclos entre años; desconocidos y funding no aplicado.
Cada uno tiene fixture específico. No se agregarán backtests ni escenarios.

# Implementación de la comparación SOFR aprobada

Ejecución nativa con superpowers:executing-plans y pruebas previas. La ficha
ya fue aprobada; no se requiere otra aprobación del diseño. No se hacen commits,
worktrees ni cambios al índice. El trabajo previo sin commit permanece intacto.

Objetivo: una cuenta hipotética separada de 10.000 USD, ACT/360, paridad nominal
USDT/USD, comparada con las BASE netas de costos modelados, sin remunerar carry.
Especificación: ficha original y aprobación textual en documentos de esta versión.
Arquitectura: módulos nuevos scripts/sofr_benchmark; reutilizar IO y protección
de paquetes de return_capital, sin invocar derive ni los diagnósticos anteriores.
Entorno: Python 3.14, Decimal, pytest, Ruff, Matplotlib y HTTP público para fuentes.

- [x] 1. Autenticar la versión previa y registrar estado de Git/motor/configs.
  Archivar SIFMA histórico/2026, excepciones NY Fed y SOFR Index, con URL/consulta/hash.
  Crear calendar.py y tests: cierre total, cierre temprano, excepción, duplicado,
  fecha hábil faltante, observación inesperada y 31/12/2021. Comparar todas las
  fechas contra el calendario independiente de la presencia de tasas.
- [x] 2. Crear accrual.py mediante fixtures: tasa porcentual/100, ACT/360,
  sábados/feriados simples, días hábiles consecutivos de igual tasa compuestos,
  bloque inicial 0,05% por dos días, bisiesto, fin excluyente, saldo heredado.
  Controlar SOFR Index únicamente entre fechas hábiles con límites derivados
  del redondeo publicado a ocho decimales, definidos antes de interpretar.
- [x] 3. Crear comparison.py: cartera diaria y bloques, ocho períodos originales,
  P&L/retorno/CAGR365 desde saldos heredados, diferencias descriptivas. Reutilizar
  cifras carry y H2 RF=0 exactamente, sin nuevas evaluaciones ni backtests.
- [x] 4. Crear report.py, package.py, verification.py y CLIs. Guardar originales,
  calendario por fecha, bloques, cartera, controles Index/inicial, comparación,
  figuras PNG/SVG con datos, MD/HTML y manifiesto. Rechazar sobrescrituras.
  Verificador recalcula calendario, composición, períodos y fuentes de figuras;
  validación compacta y con dependencia explícita del paquete previo.
- [ ] 5. Pruebas de manipulación, Ruff, revisión financiera independiente, copia
  portable, inspección de figuras, hashes de preservación y ZIP binario. Auditorías
  externas al sello. Documentar límites heredados y cualquier control histórico
  preexistente, sin modificar sus manifiestos.

Foco de revisión: SIFMA no equivale al calendario bancario/NYSE; excepciones
Good Friday 2023/2026 y duelo Carter 2025; no inventar Index de sábado; no
agrupar tasas iguales; no capitalizar un corte dentro de un bloque; ACT/360
no implica CAGR360; no ampliar tolerancias según resultados observados.

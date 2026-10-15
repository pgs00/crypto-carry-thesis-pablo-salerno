# Evidencia complementaria

Este paquete respalda los análisis exploratorios de la [tesina](../../Tesina_Pablo_Salerno.pdf) y del [Executive Briefing](../../Executive_Briefing_Pablo_Salerno.pdf).

- [Descargar evidencia completa, ZIP de 13,6 MB](Evidencia_complementaria_Pablo_Salerno.zip)
- [Parche técnico para revisión](reproducibility.patch)
- [Resultados de verificación y versiones por bloque](verification_summary.json)
- [SHA256 del archivo](SHA256SUMS.txt)

## Hallazgos principales

| Análisis | Resultado | Interpretación |
|---|---|---|
| H1, muestra completa emparejada | MAE del EWMA: 6,2990 pb; última tasa: 8,7033 pb; media de 7 días: 6,5764 pb. | La mejora es 27,63% frente a la última tasa y 4,22% frente a la media de 7 días. No implica una ventaja económica del filtro. |
| H3 por año | Oportunidad media por 168 horas: 0; 2,6808; 10,6972; 0; 0 pb en 2022–2026, respectivamente. | La concentración en 2024 queda oculta al agrupar subperíodos. Cero oportunidades nuevas no equivale a cero posiciones heredadas. |
| Caja a SOFR | Con 100% del saldo contable libre remunerado: CAGR 4,6853% condicional y 3,7529% incondicional. | El ranking se invierte bajo este supuesto; con 50%, sigue siendo inferior el CAGR condicional (3,2008% frente a 3,5683%). |

2026 abarca enero a agosto. La oportunidad de H3 es el indicador definido por
la regla, no el funding medio ni el rendimiento de la cartera. El análisis
anual complementa el test original sin sustituirlo.

## Contenido y alcance

El ZIP contiene los insumos congelados, scripts, tablas CSV, gráficos PNG/SVG y registros de las comprobaciones de:

- H1: comparadores de medias de siete y catorce días y tasa constante, conservando las 10.180 observaciones emparejadas.
- H3: oportunidad anual y mensual, sin reemplazar la comparación original entre subperíodos.
- Basis y funding: estadísticas por activo y período y anualización con duraciones efectivas.
- Caja: sensibilidad ex post a SOFR del 0%, 50%, 75% y 100% del saldo contable libre.
- Reproducción técnica: corrección del fixture y comparación numérica portable sobre evidencia sellada.

Los resultados originales se conservan como caso base. Los cálculos añadidos son complementarios y exploratorios. La sensibilidad SOFR no vuelve a simular las operaciones ni acredita acceso real a esa tasa; el saldo contable no descuenta reservas de órdenes pendientes.

La verificación documentada obtuvo cuatro pases de los verificadores originales y cinco de la capa externa. La suite preparada registró 1.411 pruebas aprobadas, 48 omitidas y ningún fallo; la extensión final de la política pasó 30 pruebas dirigidas. El resumen enlazado identifica las versiones exactas y el alcance de cada comprobación.

## Reproducción

Descargar y extraer el ZIP. Desde la raíz de la carpeta extraída, ejecutar:

```bash
python quant_h1/analyze_feedback.py
python cash_review/validate_cash_overlay.py
```

Ambos cálculos requieren únicamente la biblioteca estándar de Python. Para los gráficos:

```bash
python -m pip install -r requirements_figures.txt
python build_figures.py
```

Para las comprobaciones del repositorio, consultar `verification/README_VERIFICACION.md` dentro del ZIP y ejecutar sus instrucciones desde `verification/`. El parche corresponde al commit base `8b395342b7e3a9dd1fbb59f72bee6b5e6efebb49`; los verificadores compactos deben ejecutarse secuencialmente, con salidas fuera de los paquetes sellados.

## Publicación e integridad

El parche se conserva como evidencia; no está aplicado al motor ni a sus pruebas. Los datos, las fuentes y los paquetes sellados mantienen sus identidades.

El SHA256 externo y el [catálogo del producto](../../docs/procedencia/producto.json) autentican el ZIP. El archivo `SHA256SUMS.json` dentro del ZIP inventaría sus 128 archivos restantes. Las referencias a `8b39534` identifican la versión fuente examinada, y permiten reproducir la evidencia complementaria sobre esa base.

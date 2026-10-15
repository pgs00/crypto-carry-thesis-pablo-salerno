# Evidencia complementaria

Este paquete acompaña las versiones finales de la tesina y del Executive Briefing de Pablo Salerno.

- [Descargar evidencia completa, ZIP de 13,6 MB](Evidencia_complementaria_Pablo_Salerno.zip?raw=1)
- [Parche técnico para revisión](reproducibility.patch)
- [Resultados de verificación y versiones por bloque](verification_summary.json)
- [SHA256 del archivo](SHA256SUMS.txt)

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

El parche se incorpora como evidencia para revisión; esta publicación no lo aplica al motor, a sus pruebas ni a los paquetes sellados. Las fechas editoriales se omiten en esta presentación. Los datos, las fuentes y sus identidades permanecen sin cambios.

SHA256 del ZIP:

```text
03d0b1c8cdef9105a11a4fa5537f51a40d3a787374c14fb19653f579a34501be
```

El archivo `SHA256SUMS.json` dentro del ZIP inventaría sus 128 archivos restantes. Las referencias a `8b39534` identifican la versión fuente examinada, y permiten reproducir la evidencia complementaria sobre esa base.

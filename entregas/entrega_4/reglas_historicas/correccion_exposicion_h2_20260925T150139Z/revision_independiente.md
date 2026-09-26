# Revisión independiente y controles visuales

Revisión de código concluida el 26/09/2026, antes del paquete final. Alcance:
auxiliares H2/exposición, constructor, documentación, verificador y pruebas.
El revisor no modificó archivos ni Git, no revisó hipótesis económicas fuera de
alcance y no ejecutó carteras históricas.

Se identificaron y resolvieron tres observaciones:

1. La entrada genérica v2 podía crear un `.pyc` dentro de evidencia si se omitía
   `-B`. Se protegió el import y se agregó una regresión con copia temporal real
   e invocación sin `-B`: falla antes de la corrección y pasa después. Comandos,
   salidas y códigos en `controles/red_carga_verificador_sin_cache.*` y
   `controles/green_carga_verificador_sin_cache.*`.
2. La validación de los resúmenes debe verificar también escenario, estrategia
   y run_id. La reconstrucción independiente ahora conserva esas identidades y
   comprueba cada campo; hay pruebas que alteran las identidades.
3. La guía activa todavía documentaba `--package`/`--seal`. Se actualizaron sus
   comandos y definiciones v2; la copia histórica sellada quedó intacta.

El revisor no dejó hallazgos abiertos en el código revisado. Ejecutó 79 pruebas
de H2/exposición/constructor, 64 del verificador y la nueva regresión de caché.
Son controles de revisión; el conteo final de la suite se reporta por separado,
sin sumar ejecuciones repetidas. Confirmó 48 H2 reales: 43 no_favorable,
5 no_concluyente y cero cambios de veredicto frente al padre.

Se inspeccionaron visualmente las figuras PNG generadas en una carpeta temporal.
La primera vista comprimía las pocas horas de exposición activa junto a cientos
de días del bruto. La figura definitiva separa ambas magnitudes en paneles con
unidades explícitas (días brutos / horas activas), etiquetas numéricas y una
leyenda externa que no cubre barras. El panel de tiempo invertido conserva una
escala porcentual común. No se cambió ningún dato para ajustar la presentación.

La certificación del producto, la ejecución desde otra ruta y la preservación
global corresponden a los controles finales externos; esta revisión no los
sustituye.

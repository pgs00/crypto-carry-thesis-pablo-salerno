# B6 completado: ejecución local y cierre

Estado vigente al 2026-10-01 23:00:11 UTC: **completado y verificado**. Las cuatro carteras previstas terminaron; no hay otra corrida necesaria para cerrar B6. La verificación independiente pasó desde una copia aislada, sin ejecutar el motor ni acceder al repositorio o a D:/Backtesting.

Entrega vigente:

- [Reporte HTML](../paquete_final_verificado/reporte.html) y [síntesis](../paquete_final_verificado/sintesis.md).
- [Manifiesto sellado](../paquete_final_verificado/manifiesto_paquete.json).
- [Certificado independiente](../controles_finales_corregidos/verificacion_offline.json).
- [Estado de cierre](../cierre_actual.json) y [preservación](../controles_finales_corregidos/preservacion.json).

El error anterior era de exportación: se omitió `uv.lock` al filtrar los archivos `.lock`. Se corrigió el filtro, se agregaron controles y pasaron las 14 pruebas de entrega. Los 126 archivos analíticos conservan sus bytes y las carteras no se repitieron. `paquete_final` conserva el intento fallido, intacto y no vigente; el único paquete final válido es `paquete_final_verificado`. El candidato sigue editable. Las notas de continuación y el plan incluidos en el sello conservan el registro histórico del traspaso; este documento mutable y `cierre_actual.json` reflejan el cierre posterior.

Para consultar el estado, sin iniciar ningún proceso:

```powershell
Set-Location -LiteralPath 'C:\Users\pablo\Documentos\UCEMA\Tesina\Backtesting'
Get-Content -Encoding UTF8 -Raw -LiteralPath '.\entregas\entrega_4\estabilidad_incertidumbre\20261001T215423Z\cierre_actual.json'
```

Quedan pendientes la revisión transversal de la entrega y, después, Word/PDF. Son etapas posteriores al bloque analítico B6. No se hizo limpieza, commit, push ni cambios del índice.

## Comando original y registro histórico

Desde PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\pablo\Documentos\UCEMA\Tesina\Backtesting'
& '.\scripts\Start-B6.ps1'
```

El comando autentica/prepara si hace falta, ejecuta únicamente I2023/I2024 por condicional/permanente y encadena posprocesamiento, pruebas, sello y verificación offline. Un bloqueo del sistema operativo impide otro coordinador. Los estados terminados se verifican antes de reutilizarse; una tentativa incompleta sin checkpoint completo queda bloqueada para evitar repetirla sin explicación.

El proceso escribe `progreso_local.json` cada 30 segundos y logs exclusivos por cartera. No realiza llamadas al modelo/API. El cierre queda en `../cierre_actual.json`. Los errores detienen la etapa afectada; las carteras útiles ya iniciadas continúan y quedan registradas. No hay reintentos automáticos ilimitados.

La ejecución se inició después de aprobar las pruebas pequeñas y congelar el protocolo. El lanzador PowerShell tuvo PID 15200 y el coordinador Python PID 12344. En el traspaso inicial había una cartera completada, dos activas y una pendiente; ese estado histórico fue superado por el cierre verificado indicado arriba.

El proceso original usó la copia preservada en `codigo_coordinador_inicial`. La versión del comando de reanudación agrega detección de posprocesos huérfanos; las reglas económicas, presupuesto de memoria y ruta de cálculo no cambiaron. El cierre corregido permite autenticar y devolver el resultado terminado sin repetir la verificación integral.

El primer cierre usó `../paquete_final` y `../controles_finales`; quedó detenido antes del recálculo offline por la omisión del archivo de dependencias. Las rutas vigentes están enlazadas al comienzo de este documento. `../cierre_actual.json` tiene `status=completado`, `passed=true` y el hash del sello verificado.

Si la cola termina con error, `progreso_local.json` identifica la etapa, razón y log. Un relanzamiento valida las carteras terminadas; no vuelve a ejecutar BASE ni una cartera completa válida. Una tentativa económica incompleta sin checkpoint íntegro queda bloqueada y preservada. Un sello existente nunca se sobrescribe ni dispara otra verificación integral por rutina.

El reporte, la síntesis con los cuatro nuevos inicios conciliados, las tablas estadísticas y el diagnóstico B2/B3 están incluidos y verificados. El proceso local terminó; no requiere supervisión ni nuevas llamadas al modelo/API.

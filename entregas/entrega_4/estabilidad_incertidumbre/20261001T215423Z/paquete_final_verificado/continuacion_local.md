# Ejecución local automática B6

Desde PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\pablo\Documentos\UCEMA\Tesina\Backtesting'
& '.\scripts\Start-B6.ps1'
```

El comando autentica/prepara si hace falta, ejecuta únicamente I2023/I2024 por condicional/permanente y encadena posprocesamiento, pruebas, sello y verificación offline. Un bloqueo del sistema operativo impide otro coordinador. Los estados terminados se verifican antes de reutilizarse; una tentativa incompleta sin checkpoint completo queda bloqueada para evitar repetirla sin explicación.

El proceso escribe `progreso_local.json` cada 30 segundos y logs exclusivos por cartera. No realiza llamadas al modelo/API. El cierre queda en `../cierre_actual.json`. Los errores detienen la etapa afectada; las carteras útiles ya iniciadas continúan y quedan registradas. No hay reintentos automáticos ilimitados.

La ejecución fue iniciada después de aprobar las pruebas pequeñas y congelar el protocolo. Lanzador PowerShell PID 15200; coordinador Python PID 12344. Último control de traspaso: una cartera completada, dos activas y una pendiente. Esta observación no afirma que el paquete final esté terminado.

El proceso activo usa la copia preservada en `codigo_coordinador_inicial`. La versión del comando de reanudación agrega detección de posprocesos huérfanos; las reglas económicas, presupuesto de memoria y ruta de cálculo no cambiaron. No iniciar otro comando mientras el coordinador siga activo: el bloqueo rechazará la duplicación.

Al finalizar normalmente estarán:

- `../paquete_final/reporte.html` y `../paquete_final/sintesis.md`.
- `../paquete_final/manifiesto_paquete.json` y su sidecar SHA-256.
- `../controles_finales/verificacion_offline.json`, con el hash del sello verificado.
- `../cierre_actual.json` con `status=completado` y `passed=true` sólo si pasaron todos los controles.

Si la cola termina con error, `progreso_local.json` identifica la etapa, razón y log. Un relanzamiento valida las carteras terminadas; no vuelve a ejecutar BASE ni una cartera completa válida. Una tentativa económica incompleta sin checkpoint íntegro queda bloqueada y preservada. Un sello existente nunca se sobrescribe ni dispara otra verificación integral por rutina.

Ya disponibles: `tablas/bootstrap_intervalos.csv`, `estadistica/verificacion_desarrollo.json`, `sintesis.md` y `tablas/diagnostico_b2_b3_corridas.csv`. La síntesis será actualizada localmente con los nuevos inicios una vez conciliados. El cierre puede continuar sin conversación ni llamadas al modelo/API; no depende de una futura acción del asistente.

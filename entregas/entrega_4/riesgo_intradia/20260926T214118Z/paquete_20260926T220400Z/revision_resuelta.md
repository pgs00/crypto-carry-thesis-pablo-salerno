# Resolución de la revisión financiera

La revisión independiente, conservada en `documentos/revision_financiera.md`, encontró cuatro puntos de prioridad media. No encontró un problema crítico de contabilidad. Se aplicó una corrección y verificación de los puntos observados antes de sellar este producto.

| Hallazgo | Resolución y evidencia |
| --- | --- |
| El POST final contaminaba los extremos de exposición activa | `incident_exposure_mask` conserva el PRE terminal y movimientos de otros activos anteriores al cambio de cantidad del activo afectado. Excluye el estado ya cubierto o de polvo. El P&L final sigue incluyendo el POST de ejecución. Pruebas específicas cubren apertura, polvo terminal y empates. El catálogo fue regenerado: ETH002 BASE condicional tiene corto máximo 0 durante su exposición; ETH009 tiene exposición neta mínima 2.954,19662321 USDT. |
| Un cierre NaN podía acreditar anidación diaria | Se exige finitud en ambos lados de la conciliación de grillas. La prueba reproduce el error y ahora lo rechaza. Los cierres reales ya eran finitos y conciliaban a la tolerancia original. |
| La integración podía tratar deuda como caja redistribuible | Se descuenta deuda antes de reservas y necesidades conjuntas. La prueba de caja 100, deuda 90 y necesidad 20 exige faltante 10. La auditoría de los cuatro ledgers encontró deuda cero; la guarda no modifica las trayectorias reconstruidas de este encargo. |
| Faltaban ventanas alrededor de extremos | Se exportaron CSV y figuras del pico al valle/recuperación del peor DD y de días completos alrededor de la menor holgura por cartera. Los CSV de DD usan una envolvente diaria (primero, último, mínimo, máximo en orden temporal) para representar períodos largos; las cifras proceden de la serie completa. Los CSV de garantías conservan los puntos de minuto/evento de la ventana. |

Se conservan logs RED/GREEN de los problemas reproducidos, las pruebas finales y la versión exacta ejecutada de la reconstrucción. El verificador completo vuelve a calcular todos los bloques y contrasta sus valores con las particiones existentes; no ejecuta decisiones ni cambia la economía de las carteras.

La revisión también señaló que la función auxiliar que convierte argumentos ISO usa precisión de segundos. Los argumentos de período de esta entrega son medianoches enteras y los timestamps financieros se leen como enteros originales: no se detectó impacto en las series. La documentación limita esa interfaz y no extiende una afirmación de exactitud a futuras entradas fraccionarias.

La inspección visual incluyó las 13 figuras; también se comprobaron los enlaces locales del HTML y los hashes de sus entradas. No se registra un render de navegador que no se haya ejecutado.

# Bloque 3: plan de implementación y ejecución

**Objetivo:** ejecutar 16 carteras continuas y conservar dos BASE verificadas,
con umbral de selección 34 pb y fricciones/capacidad/capital del escenario.
**Especificación:** `encargo_usuario.md`, íntegro y autorizado por el usuario.
**Arquitectura:** extensión explícita en configuración/costo/diagnóstico;
runner cerrado que reutiliza `signal_sensitivity.simulate`; posprocesamiento
corregido de exposición/H2 y auditoría nueva de ejecución. Python 3.14,
Decimal, Nautilus, PyArrow, pandas y matplotlib del entorno existente.

Restricciones globales: sin cruces ni cambios del bloque 2, sin nuevos cálculos
SOFR/intradía, sin Word/PDF, sin commit/push ni escrituras al índice del usuario.
Se trabaja sobre la rama existente por instrucción del usuario, conservando
huellas y código previo. El diseño y las puertas ya están autorizados en el
encargo; no se pide nuevamente aprobación dentro de ese alcance.

- [x] A1. Autenticar paquetes, BASE y datos; guardar estado e índice iniciales.
- [x] A2. Pruebas RED del acoplamiento y modo nuevo; cambio mínimo en
  `config.py`, `costs.py`, `diagnostics.py`, `data/prescribed.py`.
- [x] A3. `cost_capacity.py`: ocho diffs exactos. Pruebas de precio, comisiones
  en base, selección/renovación, capacidad, límites, capital y liquidación.
- [x] A4. Comparar código previo/nuevo apagado y BASE con modo activado:
  fills, ledger, órdenes, posiciones, cierres y diagnósticos económicos.
  Medir ventana pequeña secuencial; congelar runner/código antes del lote.
- [x] B. C02/C03/S02/S05, dos estrategias. Conciliación 1E-8, tarifas y umbral.
- [ ] C. P050/P025, dos estrategias. Capacidad por clave, causas y conciliación.
- [ ] D. A050/A100, dos estrategias. Nueva trayectoria, reglas/tramos y conciliación.
- [ ] E1. Tablas de ocho períodos; H1/oportunidad H3 autenticados, nuevos H2/H3,
  auditoría por orden/minuto y extremos prefijados, curvas absolutas/normalizadas.
- [ ] E2. Reporte MD/HTML, código y evidencia portátil; verificador semántico,
  pruebas de corrupción con hashes renovados, copia offline y exportación binaria.
- [ ] E3. Revisión independiente final, regresión/Ruff, preservación y matriz global.

Focos de revisión: cargo de liquidación no multiplicado; tratamiento original
de forzosas comprobado sin inventar excepciones; causas sólo acreditadas; insolvencia
sin días ficticios; H1/H3 sin duplicar observaciones ni contaminar con AUM.

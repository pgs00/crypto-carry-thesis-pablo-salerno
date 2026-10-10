# Aprobación metodológica del comparador SOFR

Registro de la continuación del 27/09/2026. La hora de guardado del registro
no pretende ser la hora exacta del mensaje. La ficha original aprobada se
conserva como copia binaria y su hash se fija en el manifiesto de esta versión.

> Apruebo la cuenta hipotética bruta en USD ligada a SOFR realizada,
> con 10.000 USD iniciales, ACT/360 y paridad nominal 1 USDT = 1 USD,
> bajo los supuestos y límites de la ficha.

Los criterios metodológicos aprobados comprenden:

1. Validación de días sin observación contra calendario histórico y excepciones;
   un faltante inexplicado bloquea el cálculo, sin relleno automático.
2. Verificación directa de 01/01/2022–03/01/2022 y contraste de composición posterior
   con SOFR Index entre fechas hábiles, sin índice ficticio del sábado ni ampliación
   de tolerancias para forzar coincidencias.
3. Delimitación de bloques por fechas hábiles consecutivas, aunque la tasa sea igual.
4. ACT/360 para intereses; CAGR a 365 días para comparar en el estudio.
5. Carry neto de costos modelados frente a SOFR hipotética bruta, sin afirmar
   acceso real, equivalencia de riesgos ni rentabilidad garantizada.

La especificación contempla una cartera separada, comparación por períodos,
tablas, figuras y verificaciones con identidad propia y saldos heredados.
Excluye la remuneración de caja y garantías del carry, conserva H2/Sharpe RF=0
y reutiliza los diagnósticos previos y las carteras persistidas, sin nuevos
backtests ni cambios en la evidencia original.

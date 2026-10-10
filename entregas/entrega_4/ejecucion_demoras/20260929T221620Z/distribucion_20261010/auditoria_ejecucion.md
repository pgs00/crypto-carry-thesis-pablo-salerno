# Auditoría de ejecución

| Escenario | Cartera | Estado técnico | Estado económico | Run ID | Replay s | RAM pico GiB |
|---|---|---|---|---|---|---|
| BASE_E3 | conditional | reutilizado_verificado | complete | run_ad71d751b20623006c195ff3 | ND | reutilizada |
| BASE_E3 | permanent | reutilizado_verificado | complete | run_dfea4b7ac1475668d5968c97 | ND | reutilizada |
| E_OHLC4 | conditional | ejecutado | complete | run_877714c21697899d1a109f52 | 1198.54 | 2.849 |
| E_OHLC4 | permanent | ejecutado | complete | run_19ae8a8e67fb24f8a9d68298 | 1528.66 | 2.886 |
| L01 | conditional | ejecutado | complete | run_8db4ad88c779d7e7f81be824 | 621.99 | 2.808 |
| L01 | permanent | ejecutado | complete | run_f5dfd5bbc3e6c8ac366067c9 | 844.18 | 2.828 |
| L05 | conditional | ejecutado | complete | run_6aace4d2a522105d78ad6551 | 567.65 | 2.849 |
| L05 | permanent | ejecutado | complete | run_c89a516fe95ffc8c2b205f86 | 776.37 | 2.822 |
| LC01 | conditional | ejecutado | complete | run_0ce7dbd6aa97e1cb2edb23e6 | 528.04 | 2.846 |
| LC01 | permanent | ejecutado | complete | run_a776bbe88682a750aaa9ca64 | 770.71 | 2.834 |
| LC05 | conditional | ejecutado | complete | run_1aebb0ffdd49eb09f6c1784e | 496.64 | 2.814 |
| LC05 | permanent | ejecutado | complete | run_60bc48530980377859d86882 | 698.76 | 2.880 |
| LC15 | conditional | ejecutado | complete | run_3b854753f9373b92e1e7b20c | 489.61 | 2.805 |
| LC15 | permanent | ejecutado | complete | run_80c68eaa1473bcf72d058da6 | 660.31 | 2.823 |

Primero se midió un replay sin concurrencia. Se habilitaron como máximo dos procesos, con un escritor de resultados. Los controles BASE completos son adicionales a las doce variantes y no reemplazan sus referencias. Se comparan once artefactos completos a precisión original y en orden persistido, excluyendo únicamente run_id y unidades de presentación. La primera comprobación como multiconjunto se conserva como antecedente y fue sustituida por la verificación sensible al orden antes de interpretar las variantes.

[Control completo](documentos/control_compatibilidad_base_completa.json) · [Compatibilidad técnica](documentos/control_compatibilidad.json) · [Identidades, comandos y tiempos](indice_corridas.json). Los logs de lanzamiento y puertas de cada etapa se guardan en `ejecucion/`.

El auditor enlaza referencias originales OHLC/VWAP, demoras por propósito, ventana, disponibilidad, eventos terminales, secuencia de fills/ledger, precios adversos, fees y capacidad compartida. Las órdenes sin fill no reciben latencia cero. Los propósitos se contrastan con mercado/lado, cargos y transiciones causales. Las pruebas de corrupción renuevan hashes sobre copias descartables; no modifican el original. Constructor y verificador comparten lógica declarada.

Las pruebas se conservan en `pruebas/`. Las suites solapadas no se suman y una omisión no cuenta como aprobación. Los controles posteriores al sello se registran fuera del paquete en la carpeta de trabajo, identificando el hash comprobado.

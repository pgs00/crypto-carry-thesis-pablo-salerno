# Refuerzo de la compatibilidad completa

La primera comparación heredaba un digest que ordenaba las filas. Conservaba
valores exactos pero no probaba la secuencia persistida. Se archiva íntegra y
se repite la comparación, sin replay, con digest sensible al orden en los once
artefactos de ambas estrategias. La puerta vigente vuelve a escribirse sólo
con el resultado nuevo. No se altera ninguna corrida ni el motor congelado.

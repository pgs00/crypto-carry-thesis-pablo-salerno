# Procedencia y autenticación

Los PDF publicados son las versiones finales proporcionadas por el autor,
conservadas sin modificar su contenido:

- [Tesina, 37 páginas](../../Tesina_Pablo_Salerno.pdf).
- [Executive Briefing, 2 páginas](../../Executive_Briefing_Pablo_Salerno.pdf).

El [catálogo del producto](producto.json) registra sus tamaños y hashes, los
paquetes científicos y los documentos de lectura. Las versiones anteriores
permanecen en el historial de Git.

## Resultados y fuentes

Los resúmenes en `results/<tema>/README.md` enlazan los informes completos en
`evidencia/`. Estos paquetes conservan sus bytes, manifiestos, configuraciones
e identidades de corrida. La síntesis editorial no sustituye ni regenera las
tablas originales. Los nombres y fechas dentro de fuentes y snapshots
identifican su contexto científico e histórico.

El padre de [reglas históricas](../../data/evidence/reglas_historicas/) se
conserva completo porque la corrección BASE depende de él. Las
[ventanas independientes](../../data/evidence/ventanas_independientes/)
corresponden a otro experimento. La fuente comprimida de las carteras
continuas se conserva en [`data/evidence/`](../../data/evidence/).

La [vista continua](../../results/base/continuo/README.md) reúne 12 tablas y
6 figuras originales. Su adaptación editorial conserva el
[manifiesto anterior](../../results/base/continuo/procedencia/distribucion_20261010/manifest.json),
su sidecar y su README. `scripts.publish_thesis --verify` autentica los
19 miembros originales y la adaptación.

La [evidencia complementaria](../../results/complementaria/README.md) contiene
los cálculos exploratorios y el parche portable sobre su versión fuente.
El catálogo también autentica el ZIP, su SHA256 y los archivos externos.

## Comprobación

```bash
python -B -m scripts.verify_product
python -B -m scripts.verify_documentation
python -B -m scripts.publish_thesis --verify
```

El primer control comprueba las identidades, los miembros exactos de cada
paquete y los documentos actuales. Los verificadores científicos de la
[guía de reproducción](../reproduction.md) comprueban los cálculos de su
alcance específico. Verificar archivos no equivale a ejecutar nuevamente el
motor, y los certificados históricos no acreditan una ejecución nueva.

El [mapa de rutas](rutas.json) localiza las fuentes que conservan direcciones
anteriores. Resolver una dirección no reemplaza comprobar sus hashes.

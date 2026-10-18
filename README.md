# Contrataciones públicas del Perú. Proyecto Integrador de Minería de Datos Masivos

**Integrantes:** Ricardo Acuña, Juan Aquino y Camilo Soto.

**Fuente de datos:** Contrataciones Abiertas del Perú en estándar OCDS, publicadas por el OECE, antes OSCE, bajo licencia CC BY 4.0. [Registro de Datos de Open Contracting Partnership, publicación 135](https://data.open-contracting.org/es/publication/135).

El repositorio reúne los dos proyectos integradores del curso, sobre el mismo dataset y la misma base limpia.

Es la continuación del proyecto parcial.

| Carpeta                                             | Proyecto                                            | Técnicas                                                                                                                                                           |
| --------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Proyecto parte 1](<Proyecto%20parte%201/README.md>) | Minería de datos masivos y flujos de datos         | KDD y EDA en Spark, similitud con MinHash, LSH y SimHash, búsqueda aproximada de vecinos, minería de flujos, reglas de asociación, reporte interactivo           |
| [Proyecto parte 2](<Proyecto%20parte%202/README.md>) | Grafos, clustering y aprendizaje de representación | base relacional en Spark con resolución de entidades, clustering y anomalías, sistemas de recomendación; análisis de enlaces, comunidades y embeddings en curso |

Cada carpeta tiene su propio README con el entorno, la forma de levantar Spark y los pasos para reproducir. El proyecto 2 lee la base limpia y los CSV crudos del proyecto 1, de modo que el proyecto 1 se reproduce primero; el script correr_todo.sh del proyecto 2 lo hace solo si hace falta.

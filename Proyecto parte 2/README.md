# Proyecto Integrador 2. Grafos, clustering y aprendizaje de representación sobre contrataciones públicas del Perú

**Integrantes:** Ricardo Acuña, Juan Aquino y Camilo Soto.

**Curso:** Minería de Datos Masivos, 2026 2. Prof. Heider Sanchez.

**Fuente de datos:** Contrataciones Abiertas del Perú en estándar OCDS, publicadas por el OECE, antes OSCE, bajo licencia CC BY 4.0. Paquetes anuales 2023 a 2025 del [Registro de Datos de Open Contracting Partnership, publicación 135](https://data.open-contracting.org/es/publication/135).

## De qué trata

El primer proyecto describió el gasto proceso por proceso. Este segundo mira **relaciones**: quién le compra a quién, quién compite con quién y qué relaciones se salen de lo esperable. Parte de la base limpia del proyecto 1, que está en la carpeta hermana Proyecto parte 1, y no la duplica.

Las tres preguntas que guían el trabajo, todas pensadas para quien supervisa el gasto público y todas presentadas como señales descriptivas para priorizar una revisión, nunca como acusaciones:

1. **¿Qué tipos de proveedor existen y cuáles combinan dependencia de un solo cliente con poca competencia?** Parte II, clustering y anomalías.
2. **¿Es predecible con quién contrata una entidad, y qué relaciones se salen de lo esperable?** Parte III, sistemas de recomendación.
3. **¿Quiénes son los actores centrales y hay grupos de proveedores que compiten siempre entre sí?** Partes IV y V, pendientes.

## Estado

| Notebook                     | Parte                                                         | Spark                                                      | Qué produce                                                                 |
| ---------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------- |
| 1_base_relacional.ipynb      | I. Transformación, resolución de entidades, base relacional | obligatorio, todo el notebook                              | hechos, características, matrices de interacción y grafo en data/processed |
| 2_clustering_anomalias.ipynb | II. Clustering y detección de anomalías                     | preparación, PCA y KMeans de MLlib; el resto en local     | tipología de proveedores y cola de anomalías                               |
| 3_recomendacion.ipynb        | III. Sistemas de recomendación                               | ALS de MLlib; vecindario, contenido y evaluación en local | recomendador híbrido evaluado y alertas de relaciones inusuales             |

Las Partes IV a VII y el reporte web interactivo se construirán sobre las mismas tablas.

## Estructura

```
Proyecto parte 2/
├── notebooks/
│   ├── 1_base_relacional.ipynb
│   ├── 2_clustering_anomalias.ipynb
│   ├── 3_recomendacion.ipynb
│   └── scripts/
│       ├── helpers.py      Spark acotado, figuras con lectura obligatoria, hallazgos con acción
│       ├── ingesta.py      lectura de los CSV crudos, copia del proyecto 1
│       ├── relacional.py   aplanado, resolución de entidades, características, matrices y grafo
│       └── algoritmos.py   KMeans++, silueta, DBSCAN, jerárquico, vecindario, TF-IDF y métricas
├── data/processed/         la base relacional en Parquet, se regenera con el notebook 1
├── artifacts/              tablas pequeñas en CSV y JSON para el reporte web
├── figs/                   figuras en SVG, vectoriales, y PNG
├── _build/                 generadores de los notebooks y revisiones de estilo y ejecución
├── correr_todo.sh          reproduce las tres partes de principio a fin
└── requirements.txt
```

Los notebooks no se editan a mano: se generan desde _build/nb1.py, nb2.py y nb3.py, donde cada celda está escrita como texto. Así un cambio en una celda es un cambio legible en el historial de git y no una diferencia enorme en un JSON con salidas incrustadas.

## Cómo levantar el entorno

Verificado sobre el entorno conda spark310: Python 3.10, PySpark 4.2.0, OpenJDK 21, scikit-learn 1.7 y scipy 1.15.

```bash
conda create -n spark310 python=3.10
conda activate spark310
pip install -r requirements.txt
java -version        # Spark necesita una JVM 17 o 21 en el PATH
```

**Spark no se instala ni se levanta aparte.** Corre en modo local dentro del mismo proceso de Python que ejecuta el notebook: la primera celda que pide una sesión la crea y la última la cierra. No hay Docker ni clúster, y es deliberado: la base relacional son unos cientos de MB en Parquet y cabe en una máquina. Lo que sí se respeta es usar solo la API pública de Spark, de modo que el mismo código correría en un clúster cambiando únicamente el master.

La sesión se abre en notebooks/scripts/helpers.py:

```python
def abrir_spark(nombre, memoria="2g", particiones=8, hilos=3):
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    spark = (SparkSession.builder.master(f"local[{hilos}]").appName(nombre)
             .config("spark.driver.memory", memoria)
             .config("spark.sql.shuffle.partitions", particiones)
             .config("spark.sql.session.timeZone", "America/Lima")
             .config("spark.sql.adaptive.enabled", "true")
             .config("spark.ui.showConsoleProgress", "false")
             .config("spark.sql.execution.arrow.pyspark.enabled", "true")
             .getOrCreate())
    ...
```

Tres detalles que cuestan horas si se olvidan:

1. **Memoria e hilos acotados.** 2 GB y 3 hilos bastan y dejan la máquina usable para otros trabajos. Si la máquina está libre se pueden subir con los argumentos de abrir_spark.
2. **PYSPARK_PYTHON fijado al intérprete activo.** Si el sistema tiene otro Spark instalado, sus workers arrancan con otro Python y fallan con PYTHON_VERSION_MISMATCH.
3. **addPyFile de los módulos de scripts.** Los workers no heredan el sys.path del notebook; sin esto, cualquier función de relacional.py que viaje a un worker falla con ModuleNotFoundError.

Mientras una sesión está viva, su interfaz web está en el puerto 4040, o en el 4041 si el 4040 está ocupado.

## Cómo reproducir

**Requisito previo:** la tabla limpia del proyecto 1 en Proyecto parte 1/data/processed/tabla_analitica.parquet, y los CSV crudos en Proyecto parte 1/data/raw. Si no están, el script siguiente ejecuta primero el notebook 1 del proyecto 1, que descarga los tres paquetes anuales, unos 420 MB comprimidos.

**Todo de una vez:**

```bash
cd "Proyecto parte 2"
bash correr_todo.sh
```

**Notebook por notebook**, en este orden, porque el 1 escribe en data/processed la base que leen los otros dos:

```bash
conda activate spark310
cd "Proyecto parte 2"
for n in 1_base_relacional 2_clustering_anomalias 3_recomendacion; do
  jupyter nbconvert --to notebook --execute --inplace \
    --ExecutePreprocessor.timeout=7200 notebooks/$n.ipynb
done
```

O abriéndolos en Jupyter y ejecutando todas las celdas, también en ese orden. Con el entorno activado el kernel python3 es el del entorno; si se ejecuta sin activarlo, hay que poner el bin del entorno primero en el PATH, porque el kernel se lanza como python a secas.

**Tiempos de referencia** en una máquina de 8 núcleos compartida con otro trabajo: el notebook 1 tarda unos 25 minutos, de los que la lectura de 3 GB de CSV crudos es la mayor parte, y deja un Parquet intermedio en data/processed/intermedio que las corridas siguientes reutilizan; borrar esa carpeta fuerza la relectura. Los notebooks 2 y 3 tardan unos minutos cada uno.

**Revisiones antes de entregar:**

```bash
python _build/verificar.py        # todas las celdas ejecutadas, sin errores, cada figura con su lectura
python _build/auditar_estilo.py   # redacción sin guiones como puntuación, cursivas ni comillas invertidas
```

## Decisiones de diseño que conviene conocer

**Implementaciones propias contrastadas con bibliotecas.** KMeans++, silueta, DBSCAN, jerárquico aglomerativo, filtrado colaborativo, TF-IDF y las métricas de ranking están escritos a mano en algoritmos.py siguiendo las lectures, y se comparan contra KMeans y ALS de Spark MLlib, DBSCAN y HDBSCAN de scikit-learn y linkage de scipy. La resolución de entidades usa MinHash y LSH propios escritos en DataFrames de Spark, porque el MinHashLSH de MLlib, con bandas de una sola fila, no terminaba.

**Spark donde aporta, local donde no, y medido.** La Parte I corre entera en Spark, como exige el enunciado. En las Partes II y III cada notebook mide el camino de Spark contra el local y justifica la elección: a esta escala KMeans y el vecindario son más rápidos en numpy, y ALS se queda en Spark porque es lo que escalaría sin cambiar el código.

## Uso de herramientas de asistencia

El enunciado admite herramientas de IA y exige que cada integrante comprenda y sepa explicar lo que se entrega. Por eso el código está escrito para poder defenderse en una sustentación: funciones cortas, cada algoritmo verificado contra una biblioteca antes de usarse y cada decisión argumentada en el notebook.

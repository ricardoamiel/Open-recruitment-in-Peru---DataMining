# Proyecto Integrador. Minería de Datos Masivos y Flujos de Datos

Aplicación articulada de las seis técnicas del curso sobre las contrataciones públicas del Estado peruano.

**Integrantes:** Ricardo Amiel Acuña Villogas, Juan Leibniz Aquino Espinoza y Camilo Ernesto Soto Cristóbal.

**Reporte interactivo publicado:** [ricardoamiel.github.io/Open-recruitment-in-Peru---DataMining](https://ricardoamiel.github.io/Open-recruitment-in-Peru---DataMining/)

**Fuente de datos:** Contrataciones Abiertas del Perú en estándar OCDS, publicadas por el OECE, antes OSCE. Paquetes anuales 2023 a 2025 del [Registro de Datos de Open Contracting Partnership, publicación 135](https://data.open-contracting.org/es/publication/135).

## Qué hay aquí

Un notebook por parte. La rúbrica puntúa cada parte por separado, las partes III y IV no usan Spark, y un notebook único pasaría de trescientas celdas.

| Notebook | Parte | Spark | Qué produce |
| --- | --- | --- | --- |
| 1_kdd_eda.ipynb | I. KDD, EDA y procesamiento distribuido | obligatorio | Tabla analítica en Parquet |
| 2_similitud_lsh.ipynb | II. Jaccard, shingling, MinHash, LSH y SimHash | obligatorio | Pares similares y curvas de error |
| 3_ann_ivf_hnsw.ipynb | III. Búsqueda aproximada de vecinos | no se usa | Recall frente a latencia |
| 4_flujos.ipynb | IV. Muestreo, Bloom, Count-Min y DGIM | no se usa | Precisión, memoria y tiempo |
| 5_reglas_asociacion.ipynb | V. A-Priori y FP-Growth | obligatorio | Reglas con soporte, confianza y lift |
| 6_reporte_interactivo.ipynb | VI. Reporte técnico interactivo | no se usa | reporte/index.html |

En los notebooks va el resultado y una lectura corta de cada figura. El razonamiento completo, las alternativas descartadas y los límites de cada conclusión están en [docs/JUSTIFICACION.md](docs/JUSTIFICACION.md). Las treinta y ocho figuras, con lo que muestra cada una, cómo explicarla en voz alta y qué responder a la pregunta previsible, están en [docs/FIGURAS.md](docs/FIGURAS.md).

```
PROYECTO/
├── notebooks/
│   ├── 1_kdd_eda.ipynb  ...  6_reporte_interactivo.ipynb
│   └── scripts/
│       ├── helpers.py      Spark, figuras con lectura obligatoria, exportación
│       ├── ingesta.py      descarga y paso de los CSV crudos a la tabla limpia
│       └── algoritmos.py   MinHash, LSH, SimHash, Bloom, Count-Min, DGIM, A-Priori
├── docs/
│   ├── JUSTIFICACION.md    el porqué de cada decisión, parte por parte
│   ├── FIGURAS.md          guía de las 38 figuras y guion de sustentación
│   └── index.html          copia del reporte, es lo que publica GitHub Pages
├── informe/                informe en docx, seis páginas, propuesta y hallazgos del EDA
├── reporte/                plantilla e index.html del reporte interactivo
├── presentacion/           diapositivas en pptx y en LaTeX Beamer
├── correr_todo.sh          reproduce las seis partes y pasa las revisiones
├── artifacts/              agregados ligeros que alimentan el reporte
├── figs/                   las 37 figuras en SVG y PNG
└── data/                   raw sin versionar, processed en Parquet
```

## Tres decisiones de diseño que conviene conocer

**Ninguna figura puede quedar sin interpretar.** La función que guarda figuras exige una lectura de al menos cuarenta caracteres y falla si no la recibe. No es una convención que haya que recordar, es una restricción del código. Las lecturas se escriben con cadenas calculadas del propio dato, así que no pueden quedar desfasadas si cambia un número.

**Las implementaciones son propias y además se contrastan.** MinHash, LSH, SimHash, Bloom, Count-Min, DGIM, reservoir y A-Priori están escritos a mano en notebooks/scripts/algoritmos.py, y donde existe equivalente se comparan contra Spark MLlib o FAISS. La implementación propia demuestra que se entiende el mecanismo; el contraste demuestra que no se entendió mal. Todas se verifican contra su definición antes de usarse.

**Los ayudantes viven junto a los notebooks.** Están en notebooks/scripts y se importan por nombre, nunca con asterisco, para que al leer una celda se vea de dónde sale cada función.

## Entorno

Verificado sobre el entorno conda spark310: Python 3.10.20, PySpark 4.2.0, OpenJDK 21, FAISS 1.15.1 y scikit-learn 1.7.2.

```bash
conda activate spark310
pip install -r requirements.txt
```

## Cómo se levanta Spark

No hay Docker ni clúster. Spark corre en modo local dentro del mismo proceso de Python que ejecuta el notebook, de modo que no hay nada que arrancar antes: la primera celda que pide una sesión la crea, y el único requisito externo es una máquina virtual de Java en el PATH.

La decisión es deliberada y no una comodidad. El volumen del proyecto son 177 mil filas y 30 MB en Parquet, que entran de sobra en la memoria de una máquina, así que un clúster solo añadiría latencia de red y una capa que no se puede inspeccionar desde el notebook. Lo que sí hace falta demostrar es que el código es el mismo que correría distribuido, y eso se consigue usando únicamente la API pública de Spark, sin recoger la tabla al driver salvo para graficar.

El modo local reserva un hilo por núcleo con la expresión local con asterisco, y el número de particiones de barajado se declara explícitamente porque el valor por omisión de doscientas es absurdo a esta escala. La figura f15_shuffle mide cuánto importa ese parámetro.

```python
# notebooks/scripts/helpers.py
def abrir_spark(nombre, memoria="6g", particiones=16):
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    spark = (SparkSession.builder.master("local[*]").appName(nombre)
             .config("spark.driver.memory", memoria)
             .config("spark.sql.shuffle.partitions", particiones)
             .config("spark.sql.session.timeZone", "America/Lima")
             .config("spark.sql.adaptive.enabled", "true")
             .config("spark.ui.showConsoleProgress", "false")
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    for modulo in ("algoritmos.py", "ingesta.py"):
        ruta = Path(__file__).parent / modulo
        if ruta.exists():
            spark.sparkContext.addPyFile(str(ruta))
    return spark
```

Las dos líneas que no son evidentes son las que más tiempo costaron. Si el sistema tiene un SPARK_HOME propio, sus workers arrancan con otro intérprete y los RDD fallan con PYTHON_VERSION_MISMATCH; fijar PYSPARK_PYTHON al intérprete activo lo evita, y vaciar SPARK_HOME no sirve porque rompe el lanzamiento del gateway. Y los workers no heredan el sys.path del driver, así que deserializar en un worker un objeto definido en algoritmos.py falla con ModuleNotFoundError, que es exactamente lo que ocurre al difundir una instancia de MinHash; addPyFile envía los módulos y lo resuelve.

Para abrir la interfaz web de Spark durante una corrida, basta visitar el puerto 4040 mientras la sesión está viva. Cada notebook cierra su sesión al final, de modo que dos notebooks no compiten por la memoria.

Si en algún momento el proyecto tuviera que correr contra un clúster, lo único que cambia es el master de esa función. Nada del resto del código supone modo local.

## Reproducir desde cero

No hace falta descargar nada a mano. La primera celda de datos del notebook 1 descarga y extrae los tres paquetes anuales si no están, unos 420 MB comprimidos.

```bash
cd PROYECTO
bash correr_todo.sh
```

El script comprueba el entorno, imprime la versión de PySpark y de Java con la que corre, ejecuta los seis notebooks en orden y termina pasando las dos revisiones. Equivale a esto, que también sirve si se prefiere lanzarlo a mano:

```bash
for n in 1_kdd_eda 2_similitud_lsh 3_ann_ivf_hnsw 4_flujos 5_reglas_asociacion 6_reporte_interactivo; do
  jupyter nbconvert --to notebook --execute --inplace \
    --ExecutePreprocessor.timeout=3600 notebooks/$n.ipynb
done
```

El orden importa: el notebook 1 produce el Parquet del que dependen los demás, y el 6 necesita los agregados que exportan los cinco anteriores. La corrida completa toma unos veinte minutos en una máquina de ocho núcleos.

## El reporte interactivo

reporte/index.html se abre con un doble clic, sin servidor. Lleva los agregados incrustados y no consulta ningún servicio externo salvo las tipografías y la biblioteca D3. Cada hallazgo sigue la misma anatomía: pregunta de interés, arquitectura del pipeline, visualización, controles donde apliquen e interpretación escrita.

Seis módulos tienen parámetros ajustables en vivo: la curva S de LSH según bandas y filas, el error de MinHash según el número de funciones hash, la tasa de falsos positivos del filtro de Bloom, la cota de error del Count-Min Sketch, la memoria de DGIM según el tamaño de la ventana, y el filtrado de reglas por soporte, confianza y lift. Los cinco primeros se recalculan con la fórmula cerrada del algoritmo; el último filtra sobre las reglas ya calculadas.

La versión publicada está en [GitHub Pages](https://ricardoamiel.github.io/Open-recruitment-in-Peru---DataMining/). Pages solo admite como raíz del sitio la carpeta del repositorio o docs, de modo que el notebook 6 escribe el reporte en los dos sitios: reporte/index.html, que es donde vive con su plantilla, y docs/index.html, que es lo que Pages sirve.

## Sobre el uso de herramientas de asistencia

El enunciado admite el uso de herramientas de IA y exige que el equipo comprenda y sepa explicar todo lo que entrega. Por eso el código está escrito para poder defenderse en una sustentación oral: funciones cortas, sin capas de abstracción, cada algoritmo verificado contra su definición y cada decisión argumentada por escrito en [docs/JUSTIFICACION.md](docs/JUSTIFICACION.md).

Para la sustentación hay dos piezas más. [docs/FIGURAS.md](docs/FIGURAS.md) recorre las treinta y ocho figuras con el guion de lo que se dice de cada una y la respuesta a la pregunta previsible, incluidos los tres resultados que no salieron como esperábamos y el error de medición que tuvimos que corregir. La carpeta presentacion tiene las diapositivas en pptx y en LaTeX, generadas del mismo contenido declarado una sola vez para que las dos versiones no puedan divergir.

# Proyecto Integrador. Minería de Datos Masivos y Flujos de Datos

Aplicación articulada de las seis técnicas del curso sobre las contrataciones públicas del Estado peruano.

**Integrantes:** Ricardo Amiel Acuña Villogas, Juan Leibniz Aquino Espinoza y Camilo Ernesto Soto Cristóbal.

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

En los notebooks va el resultado y una lectura corta de cada figura. El razonamiento completo, las alternativas descartadas y los límites de cada conclusión están en [docs/JUSTIFICACION.md](docs/JUSTIFICACION.md).

```
PROYECTO/
├── notebooks/
│   ├── 1_kdd_eda.ipynb  ...  6_reporte_interactivo.ipynb
│   └── scripts/
│       ├── helpers.py      Spark, figuras con lectura obligatoria, exportación
│       ├── ingesta.py      descarga y paso de los CSV crudos a la tabla limpia
│       └── algoritmos.py   MinHash, LSH, SimHash, Bloom, Count-Min, DGIM, A-Priori
├── docs/JUSTIFICACION.md   el porqué de cada decisión, parte por parte
├── informe/                informe en docx, seis páginas, propuesta y hallazgos del EDA
├── reporte/                plantilla e index.html del reporte interactivo
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

Si el sistema tiene un SPARK_HOME propio, sus workers arrancarían con otro intérprete. La función abrir_spark fija PYSPARK_PYTHON al intérprete activo y envía los módulos a los workers con addPyFile, de modo que los RDD funcionan sin configuración manual.

## Reproducir desde cero

No hace falta descargar nada a mano. La primera celda de datos del notebook 1 descarga y extrae los tres paquetes anuales si no están, unos 420 MB comprimidos.

```bash
cd PROYECTO
for n in 1_kdd_eda 2_similitud_lsh 3_ann_ivf_hnsw 4_flujos 5_reglas_asociacion 6_reporte_interactivo; do
  jupyter nbconvert --to notebook --execute --inplace \
    --ExecutePreprocessor.timeout=3600 notebooks/$n.ipynb
done
```

El orden importa: el notebook 1 produce el Parquet del que dependen los demás, y el 6 necesita los agregados que exportan los cinco anteriores. La corrida completa toma unos veinte minutos en una máquina de ocho núcleos.

## El reporte interactivo

reporte/index.html se abre con un doble clic, sin servidor. Lleva los agregados incrustados y no consulta ningún servicio externo salvo las tipografías y la biblioteca D3. Cada hallazgo sigue la misma anatomía: pregunta de interés, arquitectura del pipeline, visualización, controles donde apliquen e interpretación escrita.

Cuatro módulos tienen parámetros ajustables en vivo: la curva S de LSH según bandas y filas, la tasa de falsos positivos del filtro de Bloom, la cota de error del Count-Min Sketch, y el filtrado de reglas por soporte, confianza y lift. Los tres primeros se recalculan con la fórmula cerrada del algoritmo; el cuarto filtra sobre las reglas ya calculadas.

## Sobre el uso de herramientas de asistencia

El enunciado admite el uso de herramientas de IA y exige que el equipo comprenda y sepa explicar todo lo que entrega. Por eso el código está escrito para poder defenderse en una sustentación oral: funciones cortas, sin capas de abstracción, cada algoritmo verificado contra su definición y cada decisión argumentada por escrito en docs/JUSTIFICACION.md.

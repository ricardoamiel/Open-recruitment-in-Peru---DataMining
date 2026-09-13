# Proyecto Integrador. Minería de Datos Masivos y Flujos de Datos

Grupo 1:
- Ricardo Amiel Acuña Villogas
- Camilo Ernesto Soto Cristóbal
- Juan Leibniz Aquino Espinoza

Aplicación articulada de las técnicas del curso sobre un conjunto de datos abiertos del Estado peruano. Este repositorio contiene, por ahora, la **Parte I completa**: KDD, análisis exploratorio y procesamiento distribuido con Apache Spark.

## Fuente de datos

Contrataciones Abiertas del Perú, publicadas por el Organismo Especializado para las Contrataciones Públicas Eficientes (OECE, antes OSCE) bajo el Open Contracting Data Standard.

1. Registro de descarga masiva: https://data.open-contracting.org/es/publication/135
2. Portal de consulta: https://contratacionesabiertas.osce.gob.pe/
3. Paquetes usados: 2023, 2024 y 2025 en formato CSV comprimido.

Se citan explícitamente estas fuentes en el notebook y en el informe, tal como exige el enunciado.

## Estructura

```
PROYECTO/
├── config/
│   └── ocds_peru.yaml          perfil del dataset: rutas, roles y políticas de limpieza
├── src/
│   ├── kdd/                    código genérico, independiente del dataset
│   │   ├── config.py           carga y valida el perfil
│   │   ├── sesion.py           SparkSession y cronómetro
│   │   ├── perfilado.py        nulos, duplicados, cardinalidad, cuantiles, canastas
│   │   ├── limpieza.py         motor que ejecuta las políticas declaradas
│   │   ├── viz.py              figuras con paleta validada para daltonismo
│   │   └── artefactos.py       exportación a CSV, JSON y Parquet con manifiesto
│   └── perfiles/
│       └── ocds_peru.py        único módulo que conoce la forma cruda de este dataset
├── notebooks/
│   └── P1_KDD_EDA.ipynb        Parte I completa, ejecutada
├── scripts/                    generadores del notebook y del informe, ver scripts/README_scripts.md
├── informe/                    informe de planificación en formato docx
├── data/raw/                   paquetes anuales descargados (no versionados)
├── data/processed/             tabla analítica en Parquet, particionada por año
├── artifacts/                  agregados ligeros para el reporte web
└── figs/                       figuras en SVG y PNG
```

## Por qué está separado así

La separación entre el perfil y el código genérico es deliberada. El enunciado permite cambiar de fuente de datos, y la Parte I es la que alimenta a todas las demás, así que conviene que rehacerla con otro dataset cueste poco.

Para cambiar de dataset hacen falta exactamente dos cosas:

1. Escribir un archivo config/otro_dataset.yaml con los mismos apartados: metadatos, rutas, roles de columna y políticas de limpieza.
2. Escribir un módulo src/perfiles/otro_dataset.py con una función construir_tabla_analitica(spark, cfg) que devuelva un DataFrame plano con las columnas que el YAML promete.

El notebook no cambia. El perfilado, el motor de limpieza, las figuras y la exportación de artefactos operan sobre los roles declarados, no sobre nombres de columna cableados.

## Entorno

Verificado sobre el entorno conda spark310: Python 3.10.20, PySpark 4.2.0 y OpenJDK 21.

```bash
conda activate spark310
pip install -r requirements.txt
```

La variable SPARK_HOME del sistema apunta a una instalación cuyos workers arrancarían con otro intérprete de Python. El módulo src/kdd/sesion.py fija PYSPARK_PYTHON al intérprete del entorno activo, de modo que los RDD funcionan sin configuración manual.

## Reproducir la Parte I

Primero, descargar los paquetes anuales dentro de data/raw:

```bash
cd PROYECTO/data/raw
for a in 2023 2024 2025; do
  curl -L "https://data.open-contracting.org/es/publication/135/download?name=$a.csv.tar.gz" -o $a.csv.tar.gz
  tar -xzf $a.csv.tar.gz
done
```

Después, ejecutar el notebook:

```bash
cd PROYECTO
jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.timeout=3000 notebooks/P1_KDD_EDA.ipynb
```

La ejecución completa toma unos pocos minutos en una máquina de 8 núcleos y 16 GB de memoria. Produce la tabla analítica en Parquet, las figuras en figs y los agregados en artifacts junto con su manifiesto.

## Qué deja lista la Parte I para las partes siguientes

La tabla analítica persiste tres representaciones que no hay que volver a construir:

1. El objeto contractual normalizado, texto libre del que salen los shingles de la Parte II y los vectores TF-IDF de la Parte III.
2. El conjunto de códigos CUBSO por proceso, entrada directa de Jaccard y MinHash en la Parte II y de A-Priori y FP-Growth en la Parte V.
3. La fecha de convocatoria con resolución de minuto, que ordena el flujo simulado de la Parte IV.

## Nota sobre el uso de herramientas de asistencia

El enunciado admite el uso de herramientas de IA y exige que el equipo comprenda y sepa explicar todo lo que entrega. Cada decisión metodológica de este repositorio está justificada por escrito en el punto donde se toma: las políticas de limpieza llevan su razón en el propio archivo de configuración, y cada figura declara por qué se genera y a qué pregunta responde.

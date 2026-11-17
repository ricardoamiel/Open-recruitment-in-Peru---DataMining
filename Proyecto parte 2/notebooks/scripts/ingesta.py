"""Lectura de los CSV crudos de OCDS que descarga el proyecto 1.

La descarga y la limpieza viven en Proyecto parte 1/notebooks/scripts/ingesta.py;
aqui solo se leen las tablas que la parte 2 necesita volver a mirar.

Fuente: Open Contracting Partnership, Data Registry, publicacion 135
(Peru, OECE). https://data.open-contracting.org/es/publication/135
"""

from pyspark.sql import functions as F

from helpers import CRUDO

PERIODOS = ["2023", "2024", "2025"]


def leer(spark, tabla, columnas):
    """Lee la misma tabla de los tres paquetes anuales y las une.

    Todo se lee como texto a proposito: si Spark infiriera el esquema, el
    codigo CUBSO de 16 digitos pasaria a coma flotante y volveria en notacion
    cientifica, perdiendo justo los digitos que identifican el item.
    """
    if not (CRUDO / PERIODOS[0]).exists():
        raise FileNotFoundError(f"Faltan los CSV crudos en {CRUDO}. Ejecutar antes el notebook "
                                "1_kdd_eda del proyecto 1, que los descarga.")
    partes = []
    for periodo in PERIODOS:
        df = (spark.read.option("header", True).option("inferSchema", False)
              .option("quote", '"').option("escape", '"')
              .csv(str(CRUDO / periodo / tabla)))
        partes.append(df.select(*[c for c in columnas if c in df.columns])
                        .withColumn("periodo_archivo", F.lit(periodo)))
    salida = partes[0]
    for p in partes[1:]:
        salida = salida.unionByName(p, allowMissingColumns=True)
    return salida

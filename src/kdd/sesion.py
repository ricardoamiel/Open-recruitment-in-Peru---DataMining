"""Construccion de la SparkSession y utilidades de medicion de tiempo.

Se centraliza aqui porque el entorno spark310 tiene una particularidad: la
variable SPARK_HOME apunta a una instalacion del sistema cuyos workers
arrancarian con otro interprete de Python. Fijar PYSPARK_PYTHON al Python del
entorno evita el error PYTHON_VERSION_MISMATCH al usar RDDs.
"""

from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager

from pyspark.sql import SparkSession


def crear_spark(cfg, nombre: str = "ProyectoIntegrador-P1", nucleos: str = "*") -> SparkSession:
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

    n_shuffle = cfg["particionado"]["n_particiones_shuffle"]

    spark = (
        SparkSession.builder.master(f"local[{nucleos}]")
        .appName(nombre)
        .config("spark.driver.memory", "6g")
        .config("spark.sql.shuffle.partitions", str(n_shuffle))
        .config("spark.sql.session.timeZone", "America/Lima")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


@contextmanager
def cronometro(etiqueta: str, registro: list | None = None):
    """Mide el tiempo de pared de un bloque y lo acumula en una lista.

    Se usa para la comparacion RDD frente a DataFrame que pide la Parte I.
    """
    t0 = time.perf_counter()
    yield
    dt = time.perf_counter() - t0
    print(f"{etiqueta}: {dt:.2f} s")
    if registro is not None:
        registro.append({"operacion": etiqueta, "segundos": round(dt, 3)})


def describir_entorno(spark: SparkSession) -> dict:
    sc = spark.sparkContext
    return {
        "spark": spark.version,
        "python": sys.version.split()[0],
        "master": sc.master,
        "nucleos_default": sc.defaultParallelism,
        "shuffle_partitions": spark.conf.get("spark.sql.shuffle.partitions"),
        "adaptive": spark.conf.get("spark.sql.adaptive.enabled"),
    }

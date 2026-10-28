"""Reproduce fuera de Jupyter la celda 8 del notebook 1, donde muere el kernel.

Separa los dos pasos de la celda (pivot de Spark y mapa de calor de matplotlib)
y activa faulthandler, que imprime el stack de Python aunque el proceso caiga
por un error nativo, cosa que Jupyter solo reporta como "Kernel died".

    cd notebooks
    C:/Users/LENOVO/anaconda3/envs/spark310/python.exe -X faulthandler scripts/reproducir_celda8.py
"""

import faulthandler, sys, time
from pathlib import Path

faulthandler.enable()
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import abrir_spark, mapa_calor
from ingesta import construir_tabla


def paso(msg):
    print(f"{time.strftime('%H:%M:%S')}  {msg}", flush=True)


spark = abrir_spark("reproducir-celda8")
paso("construir_tabla + cache + count")
cruda = construir_tabla(spark).cache()
paso(f"{cruda.count():,} filas")

paso("pivot periodo_archivo x anio -> toPandas")
cruce = (cruda.groupBy("periodo_archivo").pivot("anio").count()
         .orderBy("periodo_archivo").toPandas().set_index("periodo_archivo").fillna(0))
paso(f"pivot ok, forma {cruce.shape}, columnas {list(cruce.columns)[:6]}...")

paso("mapa_calor")
import matplotlib
matplotlib.use("Agg")
fig, _ = mapa_calor(cruce, "prueba", "procesos")
paso("mapa_calor ok")
spark.stop()

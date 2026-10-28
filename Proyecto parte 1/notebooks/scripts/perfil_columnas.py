"""Perfil de columnas para la Parte V: que se usa y que hay disponible.

Solo lee. Dos bloques: (1) la tabla analitica en parquet, con nulos, distintos
y distribucion de las columnas que alimentan las canastas; (2) las cabeceras
de las 21 tablas crudas, para ver que atributos quedan fuera de la tabla.

    cd notebooks
    C:/Users/LENOVO/anaconda3/envs/spark310/python.exe scripts/perfil_columnas.py

El reporte queda en notebooks/scripts/logs/perfil_columnas.log.
"""

import csv, sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import pandas as pd
from pyspark.sql import functions as F

from helpers import PARQUET, RAIZ, abrir_spark

LOG = AQUI / "logs" / "perfil_columnas.log"
LOG.parent.mkdir(exist_ok=True)
_lineas = []
pd.set_option("display.width", 200); pd.set_option("display.max_rows", 200)
pd.set_option("display.max_colwidth", 70)


def log(msg=""):
    print(msg)
    _lineas.append(str(msg))


def seccion(titulo):
    log(); log(f"== {titulo} " + "=" * (70 - len(titulo)))


spark = abrir_spark("perfil-columnas", memoria="4g")
datos = spark.read.parquet(str(PARQUET))
n = datos.count()

seccion(f"Tabla analitica: {n:,} procesos, {len(datos.columns)} columnas")
filas = []
for campo in datos.schema.fields:
    c = F.col(campo.name)
    es_arr = campo.dataType.typeName() == "array"
    nulos = F.sum((c.isNull() | (F.size(c) == 0 if es_arr else F.lit(False))).cast("int"))
    distintos = F.lit(None) if es_arr else F.approx_count_distinct(c)
    r = datos.select(nulos.alias("n"), distintos.alias("d")).collect()[0]
    filas.append({"columna": campo.name, "tipo": campo.dataType.simpleString(),
                  "pct_nulo_o_vacio": round(100 * r["n"] / n, 2), "distintos_aprox": r["d"]})
log(pd.DataFrame(filas).to_string(index=False))


def frecuencias(col, top=25):
    seccion(f"Valores de {col}")
    t = (datos.groupBy(col).count().orderBy(F.desc("count")).limit(top).toPandas())
    t["pct"] = (100 * t["count"] / n).round(2)
    log(t.to_string(index=False))


for col in ("metodo", "categoria", "nivel_gobierno", "moneda", "departamento",
            "adjudicado", "n_postores_imputado", "monto_outlier", "anio"):
    frecuencias(col)

seccion("n_postores: distribucion (todas las filas y solo las no imputadas)")
for etiqueta, df in (("todas", datos), ("no imputadas", datos.filter("NOT n_postores_imputado"))):
    t = (df.withColumn("k", F.when(F.col("n_postores") >= 6, F.lit("6+"))
                        .otherwise(F.col("n_postores").cast("int").cast("string")))
         .groupBy("k").count().orderBy("k").toPandas())
    t["pct"] = (100 * t["count"] / t["count"].sum()).round(2)
    log(f"-- {etiqueta}"); log(t.to_string(index=False))

seccion("Cruce postor unico x metodo (no imputadas)")
t = (datos.filter("NOT n_postores_imputado")
     .groupBy("metodo").agg(F.count("*").alias("procesos"),
                            F.round(100 * F.avg((F.col("n_postores") <= 1).cast("int")), 1)
                            .alias("pct_postor_unico"),
                            F.round(100 * F.avg((F.col("n_postores") == 0).cast("int")), 1)
                            .alias("pct_cero_postores"))
     .orderBy(F.desc("procesos")).toPandas())
log(t.to_string(index=False))

seccion("Cobertura de la canasta CUBSO")
t = datos.select(
    F.round(100 * F.avg((F.col("n_items") > 0).cast("int")), 2).alias("pct_con_items"),
    F.round(100 * F.avg((F.size("items") >= 2).cast("int")), 2).alias("pct_2_o_mas_codigos"),
    F.round(100 * F.avg(F.col("adjudicado").cast("int")), 2).alias("pct_adjudicado"),
    F.round(100 * F.avg(((F.col("n_items") > 0) & ~F.col("adjudicado")).cast("int")), 2)
        .alias("pct_items_sin_adjudicar"),
).toPandas()
log(t.to_string(index=False))
log("n_proveedores (proveedores adjudicados distintos por proceso):")
t = datos.groupBy("n_proveedores").count().orderBy("n_proveedores").limit(10).toPandas()
log(t.to_string(index=False))

seccion("monto_pen: cuantiles y tramos usados en la canasta enriquecida")
q = datos.stat.approxQuantile("monto_pen", [0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99], 0.001)
log(dict(zip(["p1", "p10", "p25", "p50", "p75", "p90", "p99"], [round(v) for v in q])))
tramo = F.expr("""CASE WHEN monto_pen < 50000 THEN '1 <50k' WHEN monto_pen < 500000 THEN '2 50k-500k'
                       WHEN monto_pen < 5000000 THEN '3 500k-5M' ELSE '4 >5M' END""")
t = datos.groupBy(tramo.alias("tramo")).count().orderBy("tramo").toPandas()
t["pct"] = (100 * t["count"] / n).round(2)
log(t.to_string(index=False))

seccion("Tablas crudas (2024): columnas disponibles")
crudo = RAIZ / "data" / "raw" / "2024"
for f in sorted(crudo.glob("*.csv")):
    with open(f, encoding="utf-8", errors="replace", newline="") as h:
        cab = next(csv.reader(h))
    log(f"-- {f.name} ({f.stat().st_size/1e6:.0f} MB, {len(cab)} columnas)")
    log("   " + ", ".join(cab))

spark.stop()
LOG.write_text("\n".join(_lineas) + "\n", encoding="utf-8")
print(f"\nlog: {LOG}")

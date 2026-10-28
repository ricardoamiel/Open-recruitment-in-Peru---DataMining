"""Verifica que significa n_postores y en que se diferencian tender_items y awards_items.

Solo lee los CSV crudos de un periodo (2024 por defecto). Tres preguntas:
  1. tender_procurementMethod (open/selective/limited/direct) frente al metodo detallado.
  2. tender_numberOfTenderers frente a los postores listados en tender_tenderers
     y a los proveedores adjudicados en awards_suppliers.
  3. Cobertura y coincidencia de codigos CUBSO entre tender_items y awards_items.

    cd notebooks
    C:/Users/LENOVO/anaconda3/envs/spark310/python.exe scripts/verificar_postores.py

El reporte queda en notebooks/scripts/logs/verificar_postores.log.
"""

import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import pandas as pd
from pyspark.sql import functions as F

from helpers import RAIZ, abrir_spark

PERIODO = sys.argv[1] if len(sys.argv) > 1 else "2024"
CRUDO = RAIZ / "data" / "raw" / PERIODO
LOG = AQUI / "logs" / "verificar_postores.log"
LOG.parent.mkdir(exist_ok=True)
_lineas = []
pd.set_option("display.width", 200); pd.set_option("display.max_rows", 200)
pd.set_option("display.max_colwidth", 60)


def log(msg=""):
    print(msg)
    _lineas.append(str(msg))


def seccion(titulo):
    log(); log(f"== {titulo} " + "=" * (70 - len(titulo)))


spark = abrir_spark("verificar-postores", memoria="4g")
leer = lambda t: (spark.read.option("header", True).option("inferSchema", False)
                  .option("quote", '"').option("escape", '"').csv(str(CRUDO / t)))

main = (leer("main.csv")
        .select("ocid", F.col("tender_procurementMethod").alias("tipo"),
                F.col("tender_procurementMethodDetails").alias("metodo"),
                F.col("tender_numberOfTenderers").cast("int").alias("n_postores"))
        .dropDuplicates(["ocid"]))
n = main.count()
log(f"periodo {PERIODO}: {n:,} procesos en main.csv")

seccion("1. tender_procurementMethod x metodo detallado (top 25)")
t = (main.groupBy("tipo", "metodo").count().orderBy(F.desc("count")).limit(25).toPandas())
log(t.to_string(index=False))

seccion("2. n_postores frente a tender_tenderers y awards_suppliers")
tenderers = (leer("tender_tenderers.csv").groupBy(F.col("main_ocid").alias("ocid"))
             .agg(F.countDistinct("id").alias("n_listados")))
suppliers = (leer("awards_suppliers.csv").groupBy(F.col("main_ocid").alias("ocid"))
             .agg(F.countDistinct("id").alias("n_adjudicados")))
cmp = (main.join(tenderers, "ocid", "left").join(suppliers, "ocid", "left")
       .fillna(0, ["n_listados", "n_adjudicados"]))
r = cmp.select(
    F.count("*").alias("procesos"),
    F.round(100 * F.avg((F.col("n_listados") > 0).cast("int")), 1).alias("pct_con_lista"),
    F.round(100 * F.avg((F.col("n_postores") == F.col("n_listados")).cast("int")), 1)
        .alias("pct_n_postores_igual_lista"),
    F.round(100 * F.avg((F.col("n_postores") > F.col("n_listados")).cast("int")), 1)
        .alias("pct_n_postores_mayor"),
    F.round(100 * F.avg((F.col("n_postores") < F.col("n_listados")).cast("int")), 1)
        .alias("pct_n_postores_menor"),
).toPandas()
log(r.to_string(index=False))
log("Por tipo de procedimiento (solo procesos con lista de postores):")
t = (cmp.filter("n_listados > 0").groupBy("tipo").agg(
        F.count("*").alias("procesos"),
        F.round(F.avg("n_postores"), 2).alias("media_n_postores"),
        F.round(F.avg("n_listados"), 2).alias("media_listados"),
        F.round(F.avg("n_adjudicados"), 2).alias("media_adjudicados"),
        F.round(100 * F.avg((F.col("n_postores") == F.col("n_listados")).cast("int")), 1)
            .alias("pct_iguales"))
     .orderBy(F.desc("procesos")).toPandas())
log(t.to_string(index=False))
log("Ejemplos de discrepancia (n_postores != listados):")
log(cmp.filter("n_listados > 0 AND n_postores != n_listados")
    .select("ocid", "metodo", "n_postores", "n_listados", "n_adjudicados")
    .limit(12).toPandas().to_string(index=False))
log("Postor unico segun cada fuente:")
log(cmp.select(
    F.sum((F.col("n_postores") == 1).cast("int")).alias("n_postores_eq_1"),
    F.sum((F.col("n_listados") == 1).cast("int")).alias("listados_eq_1"),
    F.sum(((F.col("n_postores") == 1) & (F.col("n_listados") == 1)).cast("int")).alias("ambos"),
).toPandas().to_string(index=False))

seccion("3. tender_items frente a awards_items (codigo CUBSO de 8 digitos)")
cod = lambda t: (leer(t).select(F.col("main_ocid").alias("ocid"),
                                F.substring("classification_id", 1, 8).alias("item"))
                 .filter(F.length("item") == 8).groupBy("ocid")
                 .agg(F.collect_set("item").alias("s")))
ti, ai = cod("tender_items.csv").withColumnRenamed("s", "t"), cod("awards_items.csv").withColumnRenamed("s", "a")
both = main.select("ocid").join(ti, "ocid", "left").join(ai, "ocid", "left")
r = both.select(
    F.round(100 * F.avg(F.col("t").isNotNull().cast("int")), 1).alias("pct_con_tender_items"),
    F.round(100 * F.avg(F.col("a").isNotNull().cast("int")), 1).alias("pct_con_award_items"),
    F.round(100 * F.avg((F.col("t").isNotNull() & F.col("a").isNull()).cast("int")), 1)
        .alias("pct_solo_tender"),
    F.round(100 * F.avg((F.col("t").isNull() & F.col("a").isNotNull()).cast("int")), 1)
        .alias("pct_solo_award"),
).toPandas()
log(r.to_string(index=False))
ambos = both.filter("t IS NOT NULL AND a IS NOT NULL")
log(ambos.select(
    F.count("*").alias("procesos_con_ambos"),
    F.round(100 * F.avg((F.size(F.array_except("t", "a")) + F.size(F.array_except("a", "t")) == 0)
                        .cast("int")), 1).alias("pct_mismo_conjunto"),
    F.round(100 * F.avg((F.size(F.array_except("a", "t")) == 0).cast("int")), 1)
        .alias("pct_award_subconjunto_tender"),
    F.round(F.avg(F.size("t")), 2).alias("tam_medio_tender"),
    F.round(F.avg(F.size("a")), 2).alias("tam_medio_award"),
).toPandas().to_string(index=False))
log("Ejemplos donde difieren:")
log(ambos.filter("size(array_except(t, a)) + size(array_except(a, t)) > 0")
    .limit(8).toPandas().to_string(index=False))

spark.stop()
LOG.write_text("\n".join(_lineas) + "\n", encoding="utf-8")
print(f"\nlog: {LOG}")

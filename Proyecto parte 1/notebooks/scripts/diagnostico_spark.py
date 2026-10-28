"""Diagnostico del entorno para los notebooks con Spark.

Solo lee y reporta; no instala ni modifica nada. Se ejecuta desde notebooks/
con el python del env spark310 para reproducir lo que ve el kernel:

    cd notebooks
    C:/Users/LENOVO/anaconda3/envs/spark310/python.exe scripts/diagnostico_spark.py

El reporte queda en notebooks/scripts/logs/diagnostico_spark.log.
"""

import importlib, os, shutil, subprocess, sys, traceback
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
LOG = AQUI / "logs" / "diagnostico_spark.log"
LOG.parent.mkdir(exist_ok=True)
_lineas = []


def log(msg=""):
    print(msg)
    _lineas.append(str(msg))


def seccion(titulo):
    log(); log(f"== {titulo} " + "=" * (60 - len(titulo)))


def ok(cond, msg):
    log(f"  [{'OK' if cond else 'FALLA'}] {msg}")
    return cond


seccion("Interprete")
log(f"  fecha: {datetime.now():%Y-%m-%d %H:%M:%S}")
log(f"  python: {sys.version.split()[0]}  {sys.executable}")
log(f"  cwd: {Path.cwd()}")
ok("spark310" in sys.executable, "el interprete es el del env spark310")

seccion("Librerias")
for nombre in ("pyspark", "py4j", "pandas", "numpy", "pyarrow", "matplotlib",
               "faiss", "sklearn", "scipy"):
    try:
        mod = importlib.import_module(nombre)
        ok(True, f"{nombre} {getattr(mod, '__version__', '?')}")
    except Exception as e:
        ok(False, f"{nombre}: {type(e).__name__}: {e}")

seccion("Java")
java_home = os.environ.get("JAVA_HOME")
ok(bool(java_home) and Path(java_home).exists(), f"JAVA_HOME = {java_home}")
java = shutil.which("java")
log(f"  java en PATH: {java}")
if java:
    r = subprocess.run([java, "-version"], capture_output=True, text=True)
    log("  " + r.stderr.strip().splitlines()[0])

seccion("Hadoop en Windows (winutils)")
try:
    import pyspark
    jars = Path(pyspark.__file__).parent / "jars"
    hadoop_jars = sorted(p.name for p in jars.glob("hadoop-client-api-*.jar"))
    log(f"  version de Hadoop que trae pyspark: {hadoop_jars}")
except Exception as e:
    log(f"  no se pudo leer jars de pyspark: {e}")
hadoop_home = os.environ.get("HADOOP_HOME")
ok(bool(hadoop_home), f"HADOOP_HOME = {hadoop_home}")
if hadoop_home:
    bin_ = Path(hadoop_home) / "bin"
    ok((bin_ / "winutils.exe").exists(), f"{bin_ / 'winutils.exe'} existe")
    ok((bin_ / "hadoop.dll").exists(), f"{bin_ / 'hadoop.dll'} existe")
    ok(str(bin_).lower() in os.environ.get("PATH", "").lower(), "HADOOP_HOME\\bin esta en PATH")
log(f"  winutils en PATH: {shutil.which('winutils')}")

seccion("Modulos del proyecto")
sys.path.insert(0, str(AQUI))
for nombre in ("helpers", "algoritmos", "ingesta"):
    try:
        importlib.import_module(nombre)
        ok(True, f"import {nombre}")
    except Exception as e:
        ok(False, f"import {nombre}: {type(e).__name__}: {e}")
try:
    import helpers
    log(f"  RAIZ    = {helpers.RAIZ}")
    ok(helpers.PARQUET.exists(), f"PARQUET existe: {helpers.PARQUET}")
    crudo = helpers.RAIZ / "data" / "raw"
    for periodo in ("2023", "2024", "2025"):
        f = crudo / periodo / "tender_items.csv"
        ok(f.exists(), f"{f.relative_to(helpers.RAIZ)} existe")
except Exception as e:
    log(f"  no se pudo revisar rutas: {e}")

seccion("Arranque de Spark")
spark = None
try:
    from pyspark.sql import SparkSession
    spark = (SparkSession.builder.master("local[2]").appName("diagnostico")
             .config("spark.ui.showConsoleProgress", "false").getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    ok(True, f"SparkSession {spark.version}")
    ok(spark.range(10).count() == 10, "consulta trivial (range.count)")
except Exception as e:
    ok(False, f"SparkSession: {type(e).__name__}: {str(e).splitlines()[0]}")
if spark is not None:
    # Es exactamente lo que hace abrir_spark y donde falla el notebook 5.
    try:
        spark.sparkContext.addPyFile(str(AQUI / "algoritmos.py"))
        ok(True, "addPyFile(algoritmos.py)")
    except Exception as e:
        msg = str(e)
        causa = next((l for l in msg.splitlines() if "Exception:" in l), msg.splitlines()[0])
        ok(False, f"addPyFile: {causa.strip()[:200]}")
    spark.stop()

LOG.write_text("\n".join(_lineas) + "\n", encoding="utf-8")
print(f"\nlog: {LOG}")

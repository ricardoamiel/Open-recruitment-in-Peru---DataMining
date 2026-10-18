"""De los CSV crudos de OCDS a una tabla analitica limpia.

Una fila por proceso de contratacion. Todo lo especifico del dataset vive
aqui; los notebooks consumen el parquet que produce este modulo.

Fuente: Open Contracting Partnership, Data Registry, publicacion 135
(Peru, OECE). https://data.open-contracting.org/es/publication/135
"""

import tarfile
import urllib.request

import pandas as pd
from pyspark.sql import Window
from pyspark.sql import functions as F

from helpers import RAIZ

# ============================================================================
# Descarga de los datos. Si ya estan, no hace nada. Esto es lo que permite que
# el notebook se ejecute de cero en otra maquina sin pasos manuales previos.
# ============================================================================
CRUDO = RAIZ / "data" / "raw"
PERIODOS = ["2023", "2024", "2025"]
URL = "https://data.open-contracting.org/es/publication/135/download?name={}.csv.tar.gz"


def asegurar_datos():
    """Descarga y extrae los paquetes anuales que falten."""
    CRUDO.mkdir(parents=True, exist_ok=True)
    for periodo in PERIODOS:
        if (CRUDO / periodo / "main.csv").exists():
            print(f"  {periodo}: ya presente")
            continue
        comprimido = CRUDO / f"{periodo}.csv.tar.gz"
        if not comprimido.exists():
            print(f"  {periodo}: descargando, son entre 70 y 200 MB")
            urllib.request.urlretrieve(URL.format(periodo), comprimido)
        print(f"  {periodo}: extrayendo")
        with tarfile.open(comprimido) as t:
            t.extractall(CRUDO)
    total = sum(f.stat().st_size for f in CRUDO.rglob("*.csv"))
    print(f"  CSV disponibles: {total/1e9:.2f} GB")


# ============================================================================
# De los CSV crudos a la tabla analitica. Una fila por proceso de contratacion.
# Todo lo especifico del dataset vive en estas funciones.
# ============================================================================
VENTANA = (2023, 2025)

# El SEACE grabo parte de los textos en CP850 y el registro los leyo como
# Latin-1, de modo que cada letra acentuada quedo convertida siempre en el
# mismo caracter equivocado. Las ocho primeras sustituciones deshacen esa
# conversion; las tres ultimas corrigen acentos graves escritos donde iba un
# acento agudo. Se deja sin tocar lo ambiguo, sobre todo el signo de
# interrogacion invertido, que unas veces sustituye una tilde y otras esta
# puesto a proposito: repararlo por conjetura mete mas ruido del que quita.
ARREGLOS = [("¥", "Ñ"), ("¤", "ñ"), ("¢", "ó"),
            ("à", "Ó"), ("Ö", "Í"), ("µ", "Á"),
            ("\u0090", "É"), (" ", "á"), ("Ò", "Ó"),
            ("Ì", "Í"), ("È", "É")]

NIVEL_GOBIERNO = """
CASE
  WHEN comprador_nombre RLIKE 'MUNICIPALIDAD|MUNICIPIO'  THEN 'Gobierno local'
  WHEN comprador_nombre RLIKE 'GOBIERNO REGIONAL|DIRECCION REGIONAL|GERENCIA REGIONAL|REGION '
                                                         THEN 'Gobierno regional'
  WHEN comprador_nombre RLIKE 'UNIVERSIDAD'              THEN 'Universidad publica'
  WHEN comprador_nombre RLIKE 'HOSPITAL|RED DE SALUD|RED ASISTENCIAL|DIRESA'
                                                         THEN 'Establecimiento de salud'
  WHEN comprador_nombre RLIKE 'UNIDAD DE GESTION EDUCATIVA|UGEL'
                                                         THEN 'Unidad educativa'
  WHEN comprador_nombre RLIKE 'EJERCITO|MARINA DE GUERRA|FUERZA AEREA|POLICIA|COMANDO CONJUNTO|MINISTERIO DE DEFENSA|MINISTERIO DEL INTERIOR'
                                                         THEN 'Fuerzas armadas y policiales'
  WHEN comprador_nombre RLIKE 'S\\\\.A\\\\.|EMPRESA|E\\\\.P\\\\.S|PETROLEOS|ELECTRO|SEDAPAL|BANCO DE LA NACION'
                                                         THEN 'Empresa del Estado'
  WHEN comprador_nombre RLIKE 'MINISTERIO|INSTITUTO|SUPERINTENDENCIA|ORGANISMO|PROGRAMA|PROYECTO ESPECIAL|FONDO|COMISION|AGENCIA|AUTORIDAD|SERVICIO NACIONAL|UNIDAD EJECUTORA|OFICINA|DIRECCION GENERAL|CONSEJO|TRIBUNAL|CONTRALORIA|REGISTRO NACIONAL|CONGRESO|PODER JUDICIAL|MINISTERIO PUBLICO|ESSALUD|PRESIDENCIA|INPE|CENTRO NACIONAL'
                                                         THEN 'Gobierno nacional'
  ELSE 'Otro'
END
"""


def texto(columna):
    """Repara la codificacion y normaliza: recorta, colapsa espacios, mayusculas."""
    e = F.col(columna)
    for malo, bueno in ARREGLOS:
        e = F.replace(e, F.lit(malo), F.lit(bueno))
    return F.upper(F.trim(F.regexp_replace(e, r"\s+", " ")))


def leer(spark, tabla, columnas):
    """Lee la misma tabla de los tres paquetes anuales y las une.

    Todo se lee como texto a proposito: si Spark infiriera el esquema, el
    codigo CUBSO de 16 digitos pasaria a coma flotante y volveria en notacion
    cientifica, perdiendo justo los digitos que identifican el item.
    """
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


def construir_tabla(spark):
    """Selecciona 5 de las 21 tablas crudas y las desnormaliza a un grano unico."""
    main = leer(spark, "main.csv", [
        "ocid", "publishedDate", "buyer_id", "buyer_name", "tender_description",
        "tender_mainProcurementCategory", "tender_procurementMethodDetails",
        "tender_datePublished", "tender_numberOfTenderers",
        "tender_value_amount_PEN", "tender_value_currency"])

    procesos = main.select(
        "ocid", "periodo_archivo",
        # Fecha del evento, no la del registro: el paquete anual republica
        # procesos convocados anios antes, y usar la fecha de publicacion
        # describiria la actividad del publicador, no la del Estado comprador.
        F.to_timestamp("tender_datePublished").alias("fecha"),
        F.to_timestamp("publishedDate").alias("fecha_registro"),
        texto("tender_description").alias("objeto"),
        F.col("tender_mainProcurementCategory").alias("categoria"),
        F.col("tender_procurementMethodDetails").alias("metodo"),
        F.col("buyer_id").alias("comprador_id"),
        texto("buyer_name").alias("comprador_nombre"),
        F.col("tender_value_amount_PEN").cast("double").alias("monto_pen"),
        F.col("tender_value_currency").alias("moneda"),
        F.col("tender_numberOfTenderers").cast("double").alias("n_postores"),
    ).withColumn("anio", F.year("fecha")) \
     .withColumn("mes", F.month("fecha")) \
     .withColumn("anio_mes", F.date_format("fecha", "yyyy-MM")) \
     .withColumn("nivel_gobierno", F.expr(NIVEL_GOBIERNO))

    premios = leer(spark, "awards.csv", ["main_ocid", "id", "value_amount"]).select(
        F.col("main_ocid").alias("ocid"), F.col("id").alias("awards_id"),
        F.col("value_amount").cast("double").alias("monto_adjudicado"))
    provs = leer(spark, "awards_suppliers.csv",
                 ["main_ocid", "awards_id", "id", "name"]).select(
        F.col("main_ocid").alias("ocid"), "awards_id",
        F.col("id").alias("proveedor_id"), texto("name").alias("proveedor_nombre"))
    adjudicaciones = provs.join(premios, ["ocid", "awards_id"], "left")

    # Un proceso puede tener varias adjudicaciones; se guarda el proveedor de la
    # mayor y aparte cuantos proveedores distintos hubo, que mide fraccionamiento.
    mayor = Window.partitionBy("ocid").orderBy(F.col("monto_adjudicado").desc_nulls_last())
    principal = (adjudicaciones.withColumn("_r", F.row_number().over(mayor))
                 .filter("_r = 1").select("ocid", "proveedor_id", "proveedor_nombre"))
    cuantos = adjudicaciones.groupBy("ocid").agg(
        F.countDistinct("proveedor_id").alias("n_proveedores"))

    # El codigo CUBSO tiene 16 digitos: los 8 primeros ubican el bien o servicio
    # en la jerarquia del catalogo y los 8 ultimos son el correlativo del item
    # concreto. Se usa el prefijo de 8 porque el codigo completo es casi unico
    # por item y daria un universo tan disperso que ningun conjunto alcanzaria
    # el soporte minimo en la Parte V.
    items = leer(spark, "awards_items.csv",
                 ["main_ocid", "classification_id", "classification_description"]).select(
        F.col("main_ocid").alias("ocid"),
        F.substring("classification_id", 1, 8).alias("item"),
        texto("classification_description").alias("item_nombre"),
    ).filter(F.length("item") == 8)
    canasta = items.groupBy("ocid").agg(F.collect_set("item").alias("items"),
                                        F.count("*").alias("n_items"))

    partes = leer(spark, "parties.csv", ["main_ocid", "id", "roles", "address_department"])
    compradores = (partes.filter(F.col("roles").contains("buyer"))
                   .select(F.col("main_ocid").alias("ocid"),
                           F.col("id").alias("comprador_id"),
                           texto("address_department").alias("departamento"))
                   .filter(F.col("departamento").isNotNull() & (F.col("departamento") != ""))
                   .dropDuplicates(["ocid", "comprador_id"]))

    return (procesos
            .join(principal, "ocid", "left").join(cuantos, "ocid", "left")
            .join(canasta, "ocid", "left").join(compradores, ["ocid", "comprador_id"], "left")
            .withColumn("items", F.coalesce("items", F.array()))
            .withColumn("n_items", F.coalesce("n_items", F.lit(0)))
            .withColumn("n_proveedores", F.coalesce("n_proveedores", F.lit(0)))
            # Uno de cada cinco procesos quedo desierto, anulado o en tramite.
            # No es un error del dato, asi que se marca en lugar de eliminarse.
            .withColumn("adjudicado", F.col("proveedor_id").isNotNull()))


def catalogo_items(spark):
    """Diccionario de codigo CUBSO a su descripcion mas frecuente.

    Sin el, las reglas de la Parte V serian listas de numeros de ocho digitos.
    """
    items = leer(spark, "awards_items.csv",
                 ["main_ocid", "classification_id", "classification_description"]).select(
        F.substring("classification_id", 1, 8).alias("item"),
        texto("classification_description").alias("nombre"),
    ).filter(F.length("item") == 8)
    orden = Window.partitionBy("item").orderBy(F.col("n").desc())
    return (items.groupBy("item", "nombre").agg(F.count("*").alias("n"))
            .withColumn("_r", F.row_number().over(orden)).filter("_r = 1")
            .select("item", "nombre", "n"))


def limpiar(df):
    """Aplica las seis decisiones de limpieza y devuelve la tabla con su bitacora.

    Cada paso registra cuantas filas toco. El porque de cada decision esta en
    la celda de texto anterior y, con mas detalle, en docs/JUSTIFICACION.md.
    """
    log = []

    def anotar(paso, detalle, antes, despues, tocadas=None):
        log.append({"paso": paso, "detalle": detalle,
                    "filas_afectadas": antes - despues if tocadas is None else tocadas,
                    "filas_restantes": despues})

    n = df.count()
    anotar("entrada", "tabla analitica cruda", n, n, 0)

    # 1. Una fila por ocid, conservando la version registrada mas tarde.
    reciente = Window.partitionBy("ocid").orderBy(F.col("fecha_registro").desc_nulls_last())
    df = df.withColumn("_r", F.row_number().over(reciente)).filter("_r = 1").drop("_r")
    m = df.count(); anotar("duplicados", "una fila por ocid, la mas reciente", n, m); n = m

    # 2. Monto no positivo. El cero es un campo no publicado, no un monto, y no
    #    admite imputacion: la mediana inventaria gasto publico que no existe.
    m = df.filter("monto_pen > 0").count()
    anotar("descarte", "monto_pen nulo o no positivo", n, m)
    df = df.filter("monto_pen > 0"); n = m

    # 3. Ventana temporal. El paquete anual arrastra convocatorias de anios
    #    previos; mezclarlas produce picos que son del publicador, no del Estado.
    cond = f"anio BETWEEN {VENTANA[0]} AND {VENTANA[1]}"
    m = df.filter(cond).count()
    anotar("descarte", f"fecha fuera de {VENTANA[0]} a {VENTANA[1]}", n, m)
    df = df.filter(cond); n = m

    # 4. Postores faltantes. La ausencia no es al azar, se concentra en ciertos
    #    metodos, asi que la mediana se calcula dentro del metodo y no global.
    faltan = df.filter(F.col("n_postores").isNull()).count()
    medianas = (df.filter(F.col("n_postores").isNotNull()).groupBy("metodo")
                .agg(F.percentile_approx("n_postores", 0.5).alias("_med")))
    global_ = df.select("n_postores").na.drop().stat.approxQuantile("n_postores", [0.5], 0.001)
    df = (df.join(F.broadcast(medianas), "metodo", "left")
            .withColumn("n_postores_imputado", F.col("n_postores").isNull())
            .withColumn("n_postores", F.coalesce("n_postores", "_med", F.lit(global_[0])))
            .drop("_med"))
    anotar("imputacion", "n_postores con la mediana de su metodo", n, n, faltan)

    # 5. Extremos de monto. Se marcan y se conservan: en contratacion publica el
    #    monto alto es el caso de mayor interes, eliminarlo borra el fenomeno.
    q1, q3 = df.select(F.log1p("monto_pen").alias("v")).stat.approxQuantile("v", [0.25, 0.75], 0.001)
    bajo, alto = q1 - 3 * (q3 - q1), q3 + 3 * (q3 - q1)
    df = df.withColumn("monto_outlier",
                       (F.log1p("monto_pen") < bajo) | (F.log1p("monto_pen") > alto))
    anotar("marca", f"monto fuera de [{bajo:.2f}, {alto:.2f}] en escala log, se conserva",
           n, n, df.filter("monto_outlier").count())

    # 6. Postores absurdos. Aqui el extremo no tiene lectura sustantiva, es un
    #    error de carga, pero la fila sigue aportando monto, objeto y canasta.
    tope = df.select("n_postores").stat.approxQuantile("n_postores", [0.999], 0.0005)[0]
    tocadas = df.filter(F.col("n_postores") > tope).count()
    df = df.withColumn("n_postores", F.least("n_postores", F.lit(tope)))
    anotar("recorte", f"n_postores winsorizado al percentil 99,9, tope {tope:.0f}", n, n, tocadas)

    return df, pd.DataFrame(log)

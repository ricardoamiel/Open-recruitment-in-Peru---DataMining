"""Perfil del dataset: Contrataciones Abiertas del Peru en estandar OCDS.

Este es el unico modulo que conoce la forma concreta de los datos crudos. Su
contrato con el resto del proyecto es una sola funcion que devuelve una tabla
analitica plana, con una fila por proceso de contratacion y las columnas que el
perfil YAML declara en la seccion de roles. Para trabajar con otro dataset basta
escribir otro modulo con la misma firma.

El paquete anual del registro de Open Contracting trae los datos normalizados en
varias tablas relacionadas. Aqui se hace la etapa de seleccion e integracion del
KDD: se eligen las tablas y columnas pertinentes y se desnormalizan a un grano
unico.

Fuente citada: Open Contracting Partnership, Data Registry, publicacion 135
(Peru, OECE), paquetes anuales en formato CSV.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

# ---------------------------------------------------------------------------
# Columnas que se retienen de cada tabla cruda. Leer solo estas es la primera
# optimizacion: main.csv trae 37 columnas y el analisis necesita 14.
# ---------------------------------------------------------------------------
COLS_MAIN = [
    "ocid", "date", "publishedDate", "buyer_id", "buyer_name",
    "tender_title", "tender_description", "tender_mainProcurementCategory",
    "tender_procurementMethod", "tender_procurementMethodDetails",
    "tender_datePublished", "tender_numberOfTenderers",
    "tender_value_amount", "tender_value_currency", "tender_value_amount_PEN",
    "tender_tenderPeriod_startDate", "tender_tenderPeriod_endDate",
]
COLS_AWARDS = ["main_ocid", "id", "value_amount"]
COLS_SUPPLIERS = ["main_ocid", "awards_id", "id", "name"]
COLS_ITEMS = ["main_ocid", "classification_id", "classification_description", "totalValue_amount"]
COLS_PARTIES = ["main_ocid", "id", "roles", "address_department"]

# El SEACE arrastra textos grabados en la pagina de codigos CP850 y leidos luego
# como Latin-1. El resultado es que cada letra acentuada aparece convertida en
# otro caracter, siempre el mismo, de forma reversible. Las ocho primeras
# sustituciones deshacen esa conversion; las tres ultimas corrigen acentos graves
# escritos donde correspondia un acento agudo, que es un error de digitacion y no
# de codificacion. Se repara aqui, en el perfil, porque es una peculiaridad de
# esta fuente y no una regla general de limpieza.
#
# Quedan sin tocar los caracteres cuya intencion es ambigua, en particular el
# signo de interrogacion invertido, que unas veces sustituye una tilde y otras
# esta puesto a proposito. Repararlos por conjetura introduciria mas ruido del
# que quita, y el notebook reporta cuantas filas los conservan.
_ARREGLOS_TEXTO = [
    ("\u00a5", "\u00d1"),  # Ñ
    ("\u00a4", "\u00f1"),  # ñ
    ("\u00a2", "\u00f3"),  # ó
    ("\u00e0", "\u00d3"),  # Ó
    ("\u00d6", "\u00cd"),  # Í
    ("\u00b5", "\u00c1"),  # Á
    ("\u0090", "\u00c9"),  # É
    ("\u00a0", "\u00e1"),  # á
    ("\u00d2", "\u00d3"),  # Ò escrita por Ó
    ("\u00cc", "\u00cd"),  # Ì escrita por Í
    ("\u00c8", "\u00c9"),  # È escrita por É
]

_NIVEL_GOBIERNO = """
CASE
  WHEN comprador_nombre RLIKE 'MUNICIPALIDAD|MUNICIPIO'                        THEN 'Gobierno local'
  WHEN comprador_nombre RLIKE 'GOBIERNO REGIONAL|DIRECCION REGIONAL|GERENCIA REGIONAL|REGION '
                                                                               THEN 'Gobierno regional'
  WHEN comprador_nombre RLIKE 'UNIVERSIDAD'                                    THEN 'Universidad publica'
  WHEN comprador_nombre RLIKE 'HOSPITAL|RED DE SALUD|RED ASISTENCIAL|INSTITUTO NACIONAL DE SALUD|DIRESA|DIRECCION DE SALUD'
                                                                               THEN 'Establecimiento de salud'
  WHEN comprador_nombre RLIKE 'UNIDAD DE GESTION EDUCATIVA|UGEL'               THEN 'Unidad educativa'
  WHEN comprador_nombre RLIKE 'EJERCITO|MARINA DE GUERRA|FUERZA AEREA|POLICIA|COMANDO CONJUNTO|FUERZAS ARMADAS|MINISTERIO DE DEFENSA|MINISTERIO DEL INTERIOR'
                                                                               THEN 'Fuerzas armadas y policiales'
  WHEN comprador_nombre RLIKE 'S\\.A\\.|S\\.A\\.C|EMPRESA|E\\.P\\.S|PETROLEOS|ELECTRO|SEDAPAL|BANCO DE LA NACION|CORPORACION'
                                                                               THEN 'Empresa del Estado'
  WHEN comprador_nombre RLIKE 'MINISTERIO|INSTITUTO|SUPERINTENDENCIA|ORGANISMO|PROGRAMA|PROYECTO ESPECIAL|FONDO|COMISION|AGENCIA|AUTORIDAD|SERVICIO NACIONAL|UNIDAD EJECUTORA|OFICINA|DIRECCION GENERAL|DIRECCION DE |CONSEJO|TRIBUNAL|JURADO NACIONAL|DEFENSORIA|CONTRALORIA|REGISTRO NACIONAL|CONGRESO|PODER JUDICIAL|MINISTERIO PUBLICO|SEGURO SOCIAL|ESSALUD|PRESIDENCIA|INPE|CENTRO NACIONAL|ACADEMIA|CENTRAL DE COMPRAS|SENATI|SENCICO|ARCHIVO GENERAL|BIBLIOTECA NACIONAL'
                                                                               THEN 'Gobierno nacional'
  ELSE 'Otro'
END
"""


def _leer(spark: SparkSession, ruta: str, columnas: list[str]) -> DataFrame:
    """Lectura de CSV con todo como texto.

    Se fuerza el tipo texto a proposito. Si se dejara inferir el esquema, Spark
    convertiria el codigo CUBSO de 16 digitos a numero y lo devolveria en
    notacion cientifica, perdiendo los digitos finales que identifican el item.
    Los tipos se asignan despues, de forma explicita y controlada.
    """
    df = (
        spark.read.option("header", True)
        .option("quote", '"')
        .option("escape", '"')
        .option("multiLine", False)
        .option("mode", "PERMISSIVE")
        .option("inferSchema", False)
        .csv(ruta)
    )
    presentes = [c for c in columnas if c in df.columns]
    return df.select(*presentes)


def _leer_periodos(spark, raiz, periodos, archivo, columnas) -> DataFrame:
    partes = []
    for p in periodos:
        d = _leer(spark, f"{raiz}/{p}/{archivo}", columnas).withColumn("periodo_archivo", F.lit(p))
        partes.append(d)
    out = partes[0]
    for d in partes[1:]:
        out = out.unionByName(d, allowMissingColumns=True)
    return out


def _texto_limpio(col):
    e = F.col(col)
    for malo, bueno in _ARREGLOS_TEXTO:
        e = F.replace(e, F.lit(malo), F.lit(bueno))
    return e


def construir_tabla_analitica(spark: SparkSession, cfg) -> DataFrame:
    raiz = str(cfg.ruta("raw"))
    periodos = cfg["ingesta"]["periodos"]

    # --- 1. Nucleo del proceso -------------------------------------------
    main = _leer_periodos(spark, raiz, periodos, "main.csv", COLS_MAIN)

    procesos = main.select(
        F.col("ocid"),
        F.col("periodo_archivo"),
        # Fecha del evento: cuando la entidad convoco el proceso en el SEACE.
        # No se usa "date" porque esa es la fecha en que el registro entro al
        # paquete OCDS, que para los procesos reprocesados es anios posterior.
        F.to_timestamp("tender_datePublished").alias("fecha"),
        F.to_timestamp("publishedDate").alias("fecha_publicacion"),
        F.col("tender_title").alias("codigo_proceso"),
        _texto_limpio("tender_description").alias("objeto"),
        F.col("tender_mainProcurementCategory").alias("categoria"),
        F.col("tender_procurementMethod").alias("metodo"),
        F.col("tender_procurementMethodDetails").alias("metodo_detalle"),
        F.col("buyer_id").alias("comprador_id"),
        _texto_limpio("buyer_name").alias("comprador_nombre"),
        F.col("tender_value_amount_PEN").cast("double").alias("monto_pen"),
        F.col("tender_value_amount").cast("double").alias("monto_original"),
        F.col("tender_value_currency").alias("moneda"),
        F.col("tender_numberOfTenderers").cast("double").alias("n_postores"),
        F.datediff(
            F.to_date("tender_tenderPeriod_endDate"), F.to_date("tender_tenderPeriod_startDate")
        ).cast("double").alias("duracion_convocatoria_dias"),
    )

    procesos = (
        procesos.withColumn("anio", F.year("fecha"))
        .withColumn("mes", F.month("fecha"))
        .withColumn("anio_mes", F.date_format("fecha", "yyyy-MM"))
        .withColumn("nivel_gobierno", F.expr(_NIVEL_GOBIERNO))
    )

    # --- 2. Proveedor adjudicado -----------------------------------------
    # Un proceso puede tener varias adjudicaciones. Se conserva el proveedor de
    # la adjudicacion de mayor monto como representante del proceso, y aparte el
    # numero de proveedores distintos, que es el dato que mide fraccionamiento.
    awards = _leer_periodos(spark, raiz, periodos, "awards.csv", COLS_AWARDS).select(
        F.col("main_ocid").alias("ocid"),
        F.col("id").alias("awards_id"),
        F.col("value_amount").cast("double").alias("monto_adjudicado"),
    )
    suppliers = _leer_periodos(spark, raiz, periodos, "awards_suppliers.csv", COLS_SUPPLIERS).select(
        F.col("main_ocid").alias("ocid"),
        F.col("awards_id"),
        F.col("id").alias("proveedor_id"),
        _texto_limpio("name").alias("proveedor_nombre"),
    )
    adj = suppliers.join(awards, ["ocid", "awards_id"], "left")

    orden = Window.partitionBy("ocid").orderBy(F.col("monto_adjudicado").desc_nulls_last())
    principal = (
        adj.withColumn("_rn", F.row_number().over(orden))
        .filter(F.col("_rn") == 1)
        .select(
            "ocid",
            F.col("proveedor_id").alias("proveedor_principal_id"),
            F.col("proveedor_nombre").alias("proveedor_principal_nombre"),
            F.col("monto_adjudicado").alias("monto_adjudicado_principal"),
        )
    )
    resumen_adj = adj.groupBy("ocid").agg(
        F.countDistinct("proveedor_id").alias("n_proveedores"),
        F.sum("monto_adjudicado").alias("monto_adjudicado_total"),
    )

    # --- 3. Canasta de items ---------------------------------------------
    # El codigo CUBSO tiene 16 digitos: los 8 primeros identifican el bien o
    # servicio en la jerarquia del catalogo y los 8 ultimos son el correlativo
    # del item concreto. Para la canasta de la Parte V se usa el prefijo de 8,
    # porque el codigo completo es casi unico por item y produciria un universo
    # tan disperso que ningun conjunto llegaria al soporte minimo.
    items = _leer_periodos(spark, raiz, periodos, "awards_items.csv", COLS_ITEMS).select(
        F.col("main_ocid").alias("ocid"),
        F.substring(F.col("classification_id"), 1, 8).alias("item_cubso"),
        F.substring(F.col("classification_id"), 1, 4).alias("familia_cubso"),
        _texto_limpio("classification_description").alias("item_descripcion"),
        F.col("totalValue_amount").cast("double").alias("item_monto"),
    ).filter(F.col("item_cubso").isNotNull() & (F.length("item_cubso") == 8))

    canasta = items.groupBy("ocid").agg(
        F.collect_set("item_cubso").alias("items_cubso"),
        F.collect_set("familia_cubso").alias("familias_cubso"),
        F.count("*").alias("n_items"),
        F.sum("item_monto").alias("monto_items"),
    )

    # --- 4. Departamento de la entidad compradora ------------------------
    parties = _leer_periodos(spark, raiz, periodos, "parties.csv", COLS_PARTIES)
    compradores = (
        parties.filter(F.col("roles").contains("buyer"))
        .select(
            F.col("main_ocid").alias("ocid"),
            F.col("id").alias("comprador_id"),
            F.upper(F.trim(_texto_limpio("address_department"))).alias("departamento"),
        )
        .filter(F.col("departamento").isNotNull() & (F.col("departamento") != ""))
        .dropDuplicates(["ocid", "comprador_id"])
    )

    # --- 5. Tabla analitica ----------------------------------------------
    tabla = (
        procesos.join(principal, "ocid", "left")
        .join(resumen_adj, "ocid", "left")
        .join(canasta, "ocid", "left")
        .join(compradores, ["ocid", "comprador_id"], "left")
        .withColumn("items_cubso", F.coalesce(F.col("items_cubso"), F.array()))
        .withColumn("familias_cubso", F.coalesce(F.col("familias_cubso"), F.array()))
        .withColumn("n_items", F.coalesce(F.col("n_items"), F.lit(0)))
        .withColumn("n_proveedores", F.coalesce(F.col("n_proveedores"), F.lit(0)))
        # Uno de cada cinco procesos no tiene adjudicacion registrada: quedaron
        # desiertos, fueron anulados o siguen en tramite. No son un error de
        # datos, asi que se marcan en lugar de eliminarse, y las partes que
        # comparan proveedores filtran por esta bandera.
        .withColumn("tiene_adjudicacion", F.col("proveedor_principal_id").isNotNull())
    )
    return tabla


def catalogo_items(spark: SparkSession, cfg) -> DataFrame:
    """Diccionario codigo CUBSO de 8 digitos a su descripcion mas frecuente.

    Sirve para interpretar en palabras las reglas de asociacion de la Parte V y
    los vecinos de la Parte III, que de otro modo serian listas de numeros.
    """
    raiz = str(cfg.ruta("raw"))
    items = _leer_periodos(
        spark, raiz, cfg["ingesta"]["periodos"], "awards_items.csv", COLS_ITEMS
    ).select(
        F.substring(F.col("classification_id"), 1, 8).alias("item_cubso"),
        _texto_limpio("classification_description").alias("descripcion"),
    ).filter(F.col("item_cubso").isNotNull() & (F.length("item_cubso") == 8))

    conteo = items.groupBy("item_cubso", "descripcion").agg(F.count("*").alias("n"))
    orden = Window.partitionBy("item_cubso").orderBy(F.col("n").desc())
    return (
        conteo.withColumn("_rn", F.row_number().over(orden))
        .filter(F.col("_rn") == 1)
        .select("item_cubso", F.col("descripcion").alias("etiqueta"), F.col("n").alias("apariciones"))
    )

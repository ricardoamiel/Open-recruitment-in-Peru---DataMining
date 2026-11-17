"""Construccion de la base relacional del Proyecto 2 sobre Spark.

Parte de la tabla limpia del Proyecto 1, una fila por proceso, y vuelve a los
CSV crudos solo para recuperar lo que esa tabla resumio: todos los
proveedores adjudicados de cada proceso, todos sus participantes y los items
de cada adjudicacion. De ahi salen los tres objetos que piden las demas
partes: vectores de caracteristicas, matriz de interaccion y grafo.

Todo lo especifico del dataset vive aqui; el notebook 1 solo orquesta.
"""

from pyspark.sql import Window
from pyspark.sql import functions as F

from ingesta import leer

# ============================================================================
# Normalizacion de identificadores y nombres de proveedores
# ============================================================================

# Formas juridicas que cambian entre registros de una misma empresa
# ("S.A.C.", "SAC", "SOCIEDAD ANONIMA CERRADA") y no la distinguen de otra.
FORMAS = (r"\b(SOCIEDAD ANONIMA CERRADA|SOCIEDAD ANONIMA ABIERTA|SOCIEDAD ANONIMA|"
          r"SOCIEDAD COMERCIAL DE RESPONSABILIDAD LIMITADA|"
          r"EMPRESA INDIVIDUAL DE RESPONSABILIDAD LIMITADA|"
          r"S ?A ?C|S ?A ?A|S ?R ?L|E ?I ?R ?L|S ?C ?R ?L|S ?A|LTDA|INC|LLC|L ?P|SPA|LIMITED|LTD|GMBH|CORP)\b")


def nombre_normalizado(columna):
    """Mayusculas, sin tildes, sin puntuacion y sin forma juridica."""
    e = F.upper(F.col(columna))
    e = F.translate(e, "ÁÉÍÓÚÜÑ", "AEIOUUN")
    e = F.regexp_replace(e, r"[^A-Z0-9 ]", " ")
    e = F.regexp_replace(e, FORMAS, " ")
    return F.trim(F.regexp_replace(e, r"\s+", " "))


def tipo_proveedor(columna):
    """Clasifica el identificador publicado.

    El RUC peruano tiene 11 digitos y su prefijo dice que es: 20 persona
    juridica, 10, 15 y 17 persona natural. Los consorcios no tienen RUC propio
    en el registro y reciben un codigo interno de 6 o 7 digitos, y los
    proveedores extranjeros un codigo que empieza con L o un falso RUC 99.
    """
    num = F.regexp_replace(F.col(columna), r"^PE-RUC-", "")
    return (F.when(num.rlike(r"^20\d{9}$"), "empresa")
             .when(num.rlike(r"^(10|15|17)\d{9}$"), "persona natural")
             .when(num.rlike(r"^\d{6,7}$"), "consorcio")
             .otherwise("extranjero"))


# ============================================================================
# Lectura de las tablas crudas, restringidas a los procesos limpios
# ============================================================================

def participaciones(spark, procesos):
    """Una fila por proceso y participante, con el nombre publicado."""
    t = leer(spark, "tender_tenderers.csv", ["main_ocid", "id", "name"])
    return (t.select(F.col("main_ocid").alias("ocid"), F.col("id").alias("proveedor_id"),
                     F.upper(F.trim("name")).alias("proveedor_nombre"))
             .join(procesos.select("ocid"), "ocid")
             .dropDuplicates(["ocid", "proveedor_id"]))


def adjudicaciones(spark, procesos):
    """Una fila por adjudicacion y proveedor, con monto, contrato e items.

    El enlace incompleto se resuelve a favor de la adjudicacion: es el acto
    que decide a quien se le compra. Un contrato sin adjudicacion no tiene
    proveedor confiable y se descarta; una adjudicacion sin contrato se
    conserva con la marca con_contrato en falso, porque la relacion entre la
    entidad y el proveedor ya existe aunque el contrato no se haya publicado.
    """
    prov = leer(spark, "awards_suppliers.csv", ["main_ocid", "awards_id", "id", "name"]).select(
        F.col("main_ocid").alias("ocid"), "awards_id", F.col("id").alias("proveedor_id"),
        F.upper(F.trim("name")).alias("proveedor_nombre"))
    premio = leer(spark, "awards.csv", ["main_ocid", "id", "value_amount", "value_currency"]).select(
        F.col("main_ocid").alias("ocid"), F.col("id").alias("awards_id"),
        F.col("value_amount").cast("double").alias("monto_adjudicado"),
        F.col("value_currency").alias("moneda_adjudicada"))
    contrato = (leer(spark, "contracts.csv", ["main_ocid", "awardID"])
                .select(F.col("main_ocid").alias("ocid"), F.col("awardID").alias("awards_id"))
                .dropDuplicates().withColumn("con_contrato", F.lit(True)))

    # El codigo CUBSO tiene 16 digitos. Los cuatro primeros son la familia
    # del catalogo, que es la granularidad del mercado: 368 familias en la
    # ventana, frente a 4.664 productos de ocho digitos.
    items = (leer(spark, "awards_items.csv",
                  ["main_ocid", "awards_id", "classification_id", "totalValue_amount"])
             .filter(F.length("classification_id") >= 8)
             .select(F.col("main_ocid").alias("ocid"), "awards_id",
                     F.substring("classification_id", 1, 4).alias("familia"),
                     F.coalesce(F.col("totalValue_amount").cast("double"), F.lit(0.0)).alias("v")))
    orden = Window.partitionBy("ocid", "awards_id").orderBy(F.col("v_fam").desc())
    familia = (items.groupBy("ocid", "awards_id", "familia").agg(F.sum("v").alias("v_fam"))
               .withColumn("_r", F.row_number().over(orden)).filter("_r = 1")
               .select("ocid", "awards_id", "familia"))

    cols = ["ocid", "comprador_id", "comprador_nombre", "departamento", "nivel_gobierno", "anio_mes",
            "fecha", "anio", "metodo", "categoria", "n_postores", "monto_pen"]
    return (prov.join(procesos.select(*cols), "ocid")
            .join(premio, ["ocid", "awards_id"], "left")
            .join(contrato, ["ocid", "awards_id"], "left")
            .join(familia, ["ocid", "awards_id"], "left")
            .withColumn("con_contrato", F.coalesce("con_contrato", F.lit(False)))
            .dropDuplicates(["ocid", "awards_id", "proveedor_id"]))


# ============================================================================
# Resolucion de entidades de proveedores
# ============================================================================

def claves_exactas(registros):
    """Primer paso: una clave por proveedor real, sin comparar nombres.

    registros trae proveedor_id, proveedor_nombre y departamento del comprador.
    El RUC es la verdad: identifica a la persona aunque cambie el nombre. Los
    extranjeros no tienen RUC y su codigo cambia de un proceso a otro, pero su
    nombre es distintivo, asi que la clave es el nombre normalizado. Los
    consorcios son el caso delicado: el nombre se repite en todo el pais
    (hay 166 consorcios distintos llamados Santa Rosa), de modo que el nombre
    solo no basta y la clave suma el departamento del comprador.
    """
    r = registros.withColumn("tipo", tipo_proveedor("proveedor_id")) \
                 .withColumn("nombre_norm", nombre_normalizado("proveedor_nombre"))
    # Departamento modal de cada codigo de consorcio: un codigo es una sola
    # inscripcion y casi siempre opera en un solo departamento.
    orden = Window.partitionBy("proveedor_id").orderBy(F.col("n").desc(), "departamento")
    depto = (r.groupBy("proveedor_id", "departamento").agg(F.count("*").alias("n"))
             .withColumn("_r", F.row_number().over(orden)).filter("_r = 1")
             .select("proveedor_id", F.coalesce("departamento", F.lit("SIN DEPARTAMENTO"))
                     .alias("depto_modal")))
    ruc = F.regexp_replace("proveedor_id", r"^PE-RUC-", "")
    return (r.select("proveedor_id", "tipo", "nombre_norm").dropDuplicates(["proveedor_id"])
            .join(depto, "proveedor_id", "left")
            .withColumn("clave", F.when(F.col("tipo").isin("empresa", "persona natural"),
                                        F.concat(F.lit("RUC-"), ruc))
                                  .when(F.col("tipo") == "extranjero",
                                        F.concat(F.lit("EXT-"), "nombre_norm"))
                                  .otherwise(F.concat(F.lit("CON-"), "nombre_norm",
                                                      F.lit("|"), "depto_modal"))))


# Romano de I a XXXIX; la anticipacion evita aceptar la cadena vacia.
ROMANO = r"^(?=[IVX])X{0,3}(IX|IV|V?I{0,3})$"


def pares_difusos(claves, bandas=10, filas=4, umbral=0.85, k=3):
    """Segundo paso: nombres casi iguales entre claves sin RUC, con MinHash y LSH.

    Reutiliza el metodo del Proyecto 1, escrito con DataFrames de Spark:
    tejas de k caracteres del nombre, una firma MinHash de bandas * filas
    funciones, y candidatos los pares que coinciden en todas las filas de al
    menos una banda. Despues se verifica cada candidato con su Jaccard exacto.

    No se usa MinHashLSH de MLlib porque sus bandas tienen una sola fila: dos
    nombres son candidatos si coinciden en un solo minimo, y como casi todos
    los consorcios comparten las tejas de la palabra CONSORCIO, casi todos
    los pares chocan. Con 4 filas por banda el umbral de la curva S sube a
    (1/10)^(1/4) = 0,56, y un par con Jaccard 0,8 sigue siendo candidato con
    probabilidad 1 - (1 - 0,8^4)^10 = 0,999.

    Solo se comparan claves del mismo bloque: mismo tipo, y en consorcios
    mismo departamento, por la misma razon que la clave exacta lo incluye.
    """
    # Las claves ID- son codigos que ya se probaron distintos porque compitieron
    # entre si; volver a compararlos por nombre los fusionaria de nuevo.
    base = (claves.filter(F.col("tipo").isin("consorcio", "extranjero"))
            .filter(~F.col("clave").startswith("ID-"))
            .select("clave", "tipo", "nombre_norm", "depto_modal").dropDuplicates(["clave"])
            # La palabra CONSORCIO ya esta en el tipo; dejarla en el nombre
            # haria parecidos a todos los consorcios entre si.
            .withColumn("nombre_cmp", F.trim(F.regexp_replace("nombre_norm", r"\bCONSORCIO\b", "")))
            # Las palabras se ordenan antes de formar tejas, porque el mismo
            # proveedor aparece como FRANCO SANTOS TANIA y TANIA FRANCO SANTOS.
            .withColumn("nombre_cmp", F.array_join(F.array_sort(F.split("nombre_cmp", " ")), " "))
            # Numeros y romanos distinguen consorcios hermanos: VIAL AN 104 y
            # VIAL AN 107, SAN CARLOS y SAN CARLOS XI, o CCARHUAYO y CCARHUAYO1,
            # son distintos. El numero pegado al final de una palabra tambien
            # cuenta; el romano pegado no, porque FENIX o MAX terminan en X.
            .withColumn("marca", F.array_join(F.array_sort(F.concat(
                F.filter(F.split("nombre_norm", " "), lambda t: t.rlike(f"^[0-9]+$|{ROMANO}")),
                F.transform(F.filter(F.split("nombre_norm", " "), lambda t: t.rlike(r"^[A-Z]+[0-9]+$")),
                            lambda t: F.regexp_extract(t, r"([0-9]+)$", 1)))), " "))
            .withColumn("bloque", F.when(F.col("tipo") == "extranjero", F.lit("EXT"))
                                   .otherwise(F.col("depto_modal")))
            .filter(F.length("nombre_cmp") >= k + 2))
    tejas = (base.select("clave", F.explode(F.expr(
                f"transform(sequence(1, length(nombre_cmp) - {k - 1}), i -> substr(nombre_cmp, i, {k}))"))
                .alias("teja")).dropDuplicates())
    conjuntos = tejas.groupBy("clave").agg(F.collect_set("teja").alias("tejas"))

    # Firma MinHash: para cada funcion h_s, el minimo hash de las tejas.
    semillas = tejas.sparkSession.range(bandas * filas).withColumnRenamed("id", "s")
    firma = (tejas.crossJoin(F.broadcast(semillas))
             .groupBy("clave", "s").agg(F.min(F.xxhash64("s", "teja")).alias("m")))
    # Una llave por banda: las filas de la banda, en orden, en un solo hash.
    llaves = (firma.withColumn("banda", (F.col("s") / filas).cast("int"))
              .groupBy("clave", "banda")
              .agg(F.xxhash64(F.array_sort(F.collect_list(F.struct("s", "m")))).alias("llave"))
              .join(base.select("clave", "bloque", "marca"), "clave"))
    a, b = llaves.alias("a"), llaves.alias("b")
    candidatos = (a.join(b, ["bloque", "banda", "llave", "marca"])
                  .select(F.col("a.clave").alias("a"), F.col("b.clave").alias("b"))
                  .filter("a < b").dropDuplicates())
    ca, cb = conjuntos.alias("ca"), conjuntos.alias("cb")
    return (candidatos
            .join(ca, F.col("a") == F.col("ca.clave")).join(cb, F.col("b") == F.col("cb.clave"))
            .withColumn("jaccard", F.size(F.array_intersect("ca.tejas", "cb.tejas"))
                        / F.size(F.array_union("ca.tejas", "cb.tejas")))
            .select("a", "b", "jaccard")
            .join(base.select(F.col("clave").alias("a"), F.col("nombre_norm").alias("nombre_a")), "a")
            .join(base.select(F.col("clave").alias("b"), F.col("nombre_norm").alias("nombre_b")), "b")
            .withColumn("fusiona", F.col("jaccard") >= umbral))


def conflictos(part, mapa_df):
    """Pares de codigos que una fusion uniria pero que compitieron entre si.

    Es la validacion que el propio dato ofrece: dos codigos que participan en
    el mismo proceso son, con certeza, dos proveedores distintos. mapa_df trae
    proveedor_id y la clave que se le quiere asignar; devuelve las claves que
    agrupan codigos rivales, que por eso no se fusionan.
    """
    m = part.select("ocid", "proveedor_id").join(mapa_df, "proveedor_id")
    return (m.groupBy("ocid", "clave").agg(F.countDistinct("proveedor_id").alias("n"))
            .filter("n > 1").select("clave").distinct())


def unir(pares):
    """Union-find sobre los pares fusionables. Devuelve clave -> representante.

    Corre en el driver porque los pares son pocos miles; un componente conexo
    distribuido seria la herramienta si fueran millones.
    """
    padre = {}

    def raiz(x):
        padre.setdefault(x, x)
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    for a, b in pares:
        ra, rb = raiz(a), raiz(b)
        if ra != rb:
            padre[max(ra, rb)] = min(ra, rb)
    return {x: raiz(x) for x in padre}


# ============================================================================
# Grafo de coparticipacion
# ============================================================================

def aristas_coparticipacion(part, max_participantes=50, min_procesos=2):
    """Proveedores unidos por haber competido en los mismos procesos.

    part trae ocid y nodo (entero). Dos criterios, los dos medidos en el
    notebook. Se excluyen los procesos con mas de max_participantes, porque
    en una convocatoria masiva coincidir no dice nada de la relacion y
    genera cliques que dominarian el grafo. Y el peso de cada coincidencia es
    1 / (n - 1), el de Newman para redes de colaboracion: competir en un
    proceso de 3 vale mas que competir en uno de 40. La arista se conserva si
    los dos coincidieron en al menos min_procesos procesos distintos.
    """
    n = part.groupBy("ocid").agg(F.count("*").alias("n"))
    p = part.join(n.filter(f"n BETWEEN 2 AND {max_participantes}"), "ocid")
    a, b = p.alias("a"), p.alias("b")
    pares = (a.join(b, (F.col("a.ocid") == F.col("b.ocid")) & (F.col("a.nodo") < F.col("b.nodo")))
             .select(F.col("a.nodo").alias("src"), F.col("b.nodo").alias("dst"),
                     (1.0 / (F.col("a.n") - 1)).alias("w")))
    return (pares.groupBy("src", "dst")
            .agg(F.count("*").alias("procesos"), F.sum("w").alias("peso"))
            .filter(f"procesos >= {min_procesos}"))


# ============================================================================
# Vectores de caracteristicas
# ============================================================================

# Metodos sin competencia abierta: el proveedor se elige sin concurso.
SIN_CONCURSO = ["Contratación Directa", "Regímen Especial", "Convenio",
                "Contratación Internacional", "Adjudicación Abreviada"]


def caracteristicas_proveedores(hechos, part):
    """Un vector por proveedor resuelto, con lo que describe su comportamiento.

    hechos trae una fila por adjudicacion con la clave del proveedor; part una
    por participacion con la misma clave. Cada caracteristica responde una
    pregunta distinta: cuanto vende, a cuantos, que tan dependiente es de un
    cliente, que tan amplio es su catalogo, con cuanta competencia gana.
    """
    por_cliente = hechos.groupBy("clave", "comprador_id").agg(F.sum("monto").alias("m"))
    cuota = (por_cliente.join(por_cliente.groupBy("clave").agg(F.sum("m").alias("mt")), "clave")
             .groupBy("clave").agg(F.max(F.col("m") / F.col("mt")).alias("cuota_cliente_top")))
    ventas = hechos.groupBy("clave").agg(
        F.countDistinct("ocid").alias("n_ganados"),
        F.sum("monto").alias("monto_total"),
        F.expr("percentile_approx(monto, 0.5)").alias("monto_mediano"),
        F.countDistinct("comprador_id").alias("n_entidades"),
        F.countDistinct("departamento").alias("n_departamentos"),
        F.countDistinct("familia").alias("n_familias"),
        F.countDistinct("anio_mes").alias("meses_activos"),
        F.avg((F.col("n_postores") <= 1).cast("double")).alias("pct_postor_unico"),
        F.avg(F.col("metodo").isin(SIN_CONCURSO).cast("double")).alias("pct_sin_concurso"),
        F.avg((F.col("categoria") == "works").cast("double")).alias("pct_obras"),
        F.avg((F.col("categoria") == "services").cast("double")).alias("pct_servicios"),
        F.avg((~F.col("con_contrato")).cast("double")).alias("pct_sin_contrato"))
    postula = part.groupBy("clave").agg(F.countDistinct("ocid").alias("n_participaciones"))
    return (ventas.join(cuota, "clave").join(postula, "clave", "left")
            .withColumn("n_participaciones", F.greatest("n_participaciones", "n_ganados"))
            .withColumn("tasa_victoria", F.col("n_ganados") / F.col("n_participaciones")))


def caracteristicas_entidades(hechos, procesos):
    """Un vector por entidad compradora: volumen, concentracion y competencia."""
    por_prov = hechos.groupBy("comprador_id", "clave").agg(F.sum("monto").alias("m"))
    hhi = (por_prov.join(por_prov.groupBy("comprador_id").agg(F.sum("m").alias("mt")), "comprador_id")
           .groupBy("comprador_id").agg(F.sum((F.col("m") / F.col("mt")) ** 2).alias("hhi_proveedores")))
    compras = procesos.groupBy("comprador_id").agg(
        F.first("comprador_nombre").alias("comprador_nombre"),
        F.first("nivel_gobierno").alias("nivel_gobierno"),
        F.first("departamento", ignorenulls=True).alias("departamento"),
        F.count("*").alias("n_procesos"),
        F.sum("monto_pen").alias("monto_total"),
        F.avg("n_postores").alias("postores_medio"),
        F.avg((F.col("n_postores") <= 1).cast("double")).alias("pct_postor_unico"),
        F.avg(F.col("metodo").isin(SIN_CONCURSO).cast("double")).alias("pct_sin_concurso"),
        F.avg(F.col("adjudicado").cast("double")).alias("pct_adjudicado"))
    variedad = hechos.groupBy("comprador_id").agg(
        F.countDistinct("clave").alias("n_proveedores"),
        F.countDistinct("familia").alias("n_familias"))
    return compras.join(variedad, "comprador_id", "left").join(hhi, "comprador_id", "left")


# ============================================================================
# Matriz de interaccion
# ============================================================================

def interaccion(hechos, fila, columna):
    """Matriz dispersa en formato largo: una fila por celda no vacia y anio.

    La senal implicita es el numero de adjudicaciones, y se guarda tambien el
    monto. Se conserva el anio para poder partir en entrenamiento y prueba
    por tiempo en la Parte III.
    """
    return (hechos.filter(F.col(columna).isNotNull())
            .groupBy(fila, columna, "anio")
            .agg(F.countDistinct("ocid").alias("n"), F.sum("monto").alias("monto")))

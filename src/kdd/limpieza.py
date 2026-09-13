"""Motor de limpieza dirigido por el perfil.

Cada politica declarada en el YAML se traduce a una transformacion de Spark y
deja una linea en la bitacora con cuantas filas toco y con que justificacion.
La bitacora es el entregable que sustenta el paso de preprocesamiento del KDD:
ninguna decision de borrado o imputacion queda escondida en el codigo.
"""

from __future__ import annotations

import pandas as pd
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F


def _texto(razon: str | None) -> str:
    return " ".join((razon or "").split())


def deduplicar(df: DataFrame, cfg) -> tuple[DataFrame, dict]:
    """Conserva una sola fila por clave, la mas reciente segun el criterio."""
    limp = cfg["limpieza"]
    clave = limp["clave_duplicados"]
    criterio = limp["criterio_duplicados"]

    antes = df.count()
    ventana = Window.partitionBy(*clave).orderBy(F.col(criterio).desc_nulls_last())
    df = df.withColumn("_rn", F.row_number().over(ventana)).filter(F.col("_rn") == 1).drop("_rn")
    despues = df.count()

    return df, {
        "paso": "deduplicacion",
        "columna": " + ".join(clave),
        "accion": "conservar_mas_reciente",
        "detalle": f"orden por {criterio} descendente",
        "filas_afectadas": antes - despues,
        "pct_filas": round(100.0 * (antes - despues) / antes, 3) if antes else 0.0,
        "filas_restantes": despues,
        "razon": _texto(limp.get("razon_duplicados")),
    }


def _aplicar_una(df: DataFrame, pol: dict, n_actual: int) -> tuple[DataFrame, dict]:
    col = pol["columna"]
    accion = pol["accion"]
    registro = {
        "paso": "limpieza",
        "columna": col,
        "accion": accion,
        "detalle": "",
        "filas_afectadas": 0,
        "pct_filas": 0.0,
        "filas_restantes": n_actual,
        "razon": _texto(pol.get("razon")),
    }

    if col not in df.columns:
        registro["detalle"] = "columna ausente, politica omitida"
        return df, registro

    if accion == "normalizar_texto":
        afectadas = df.filter(
            F.col(col).isNotNull() & (F.col(col) != F.upper(F.trim(F.regexp_replace(F.col(col), r"\s+", " "))))
        ).count()
        df = df.withColumn(col, F.upper(F.trim(F.regexp_replace(F.col(col), r"\s+", " "))))
        registro["detalle"] = "trim, mayusculas, espacios colapsados"
        registro["filas_afectadas"] = afectadas

    elif accion == "descartar_fila":
        cond = pol["condicion"]
        afectadas = df.filter(F.expr(cond)).count()
        df = df.filter(~F.coalesce(F.expr(cond), F.lit(False)))
        registro["detalle"] = f"condicion: {cond}"
        registro["filas_afectadas"] = afectadas
        registro["filas_restantes"] = n_actual - afectadas

    elif accion == "imputar_constante":
        valor = pol["valor"]
        afectadas = df.filter(F.col(col).isNull()).count()
        df = df.withColumn(f"{col}_imputado", F.col(col).isNull())
        df = df.withColumn(col, F.coalesce(F.col(col), F.lit(valor)))
        registro["detalle"] = f"nulos reemplazados por {valor!r}"
        registro["filas_afectadas"] = afectadas

    elif accion == "imputar_mediana":
        grupo = pol.get("grupo")
        afectadas = df.filter(F.col(col).isNull()).count()
        df = df.withColumn(f"{col}_imputado", F.col(col).isNull())
        global_med = df.select(col).na.drop().stat.approxQuantile(col, [0.5], 0.001)
        respaldo = F.lit(global_med[0] if global_med else 0.0)
        if grupo and grupo in df.columns:
            # La mediana por grupo se calcula con una agregacion explicita y se
            # reincorpora con un join, para que el plan sea legible y no dependa
            # de percentile_approx como funcion de ventana.
            medianas = (
                df.filter(F.col(col).isNotNull())
                .groupBy(grupo)
                .agg(F.percentile_approx(F.col(col), 0.5).alias("_mediana_grupo"))
            )
            df = df.join(F.broadcast(medianas), on=grupo, how="left")
            df = df.withColumn(col, F.coalesce(F.col(col), F.col("_mediana_grupo"), respaldo))
            df = df.drop("_mediana_grupo")
            detalle = f"mediana dentro de cada {grupo}, con respaldo en la mediana global"
        else:
            df = df.withColumn(col, F.coalesce(F.col(col), respaldo))
            detalle = "mediana global"
        registro["detalle"] = detalle
        registro["filas_afectadas"] = afectadas

    elif accion == "imputar_moda":
        afectadas = df.filter(F.col(col).isNull()).count()
        moda_fila = (
            df.filter(F.col(col).isNotNull())
            .groupBy(col)
            .count()
            .orderBy(F.desc("count"))
            .limit(1)
            .collect()
        )
        moda = moda_fila[0][0] if moda_fila else None
        df = df.withColumn(f"{col}_imputado", F.col(col).isNull())
        df = df.withColumn(col, F.coalesce(F.col(col), F.lit(moda)))
        registro["detalle"] = f"moda: {moda!r}"
        registro["filas_afectadas"] = afectadas

    elif accion == "marcar_outliers":
        metodo = pol.get("metodo", "iqr")
        factor = float(pol.get("factor", 1.5))
        base = F.log1p(F.col(col)) if metodo == "iqr_log" else F.col(col)
        aux = df.select(base.alias("_v")).na.drop()
        q1, q3 = aux.stat.approxQuantile("_v", [0.25, 0.75], 0.001)
        iqr = q3 - q1
        bajo, alto = q1 - factor * iqr, q3 + factor * iqr
        marca = f"{col}_outlier"
        df = df.withColumn(marca, ((base < F.lit(bajo)) | (base > F.lit(alto))) & F.col(col).isNotNull())
        afectadas = df.filter(F.col(marca)).count()
        registro["detalle"] = (
            f"{metodo}, factor {factor}, limites en escala de calculo [{bajo:.3f}, {alto:.3f}], "
            f"se marca sin eliminar"
        )
        registro["filas_afectadas"] = afectadas

    elif accion == "recortar":
        pi = float(pol.get("p_inferior", 0.0))
        ps = float(pol.get("p_superior", 1.0))
        cuantiles = df.select(col).na.drop().stat.approxQuantile(col, [max(pi, 1e-6), min(ps, 1 - 1e-6)], 0.0005)
        lo, hi = cuantiles[0], cuantiles[1]
        afectadas = df.filter((F.col(col) < F.lit(lo)) | (F.col(col) > F.lit(hi))).count()
        df = df.withColumn(col, F.least(F.greatest(F.col(col), F.lit(lo)), F.lit(hi)))
        registro["detalle"] = f"winsorizado a [{lo:.4g}, {hi:.4g}] (p{pi:.4g} a p{ps:.4g})"
        registro["filas_afectadas"] = afectadas

    else:
        raise ValueError(f"Accion de limpieza desconocida: {accion}")

    registro["pct_filas"] = round(100.0 * registro["filas_afectadas"] / n_actual, 3) if n_actual else 0.0
    return df, registro


def aplicar(df: DataFrame, cfg, deduplicar_primero: bool = True) -> tuple[DataFrame, pd.DataFrame]:
    """Aplica deduplicacion y politicas en el orden declarado en el perfil."""
    bitacora = []
    n = df.count()
    bitacora.append(
        {
            "paso": "entrada",
            "columna": "",
            "accion": "lectura",
            "detalle": "tabla analitica cruda",
            "filas_afectadas": 0,
            "pct_filas": 0.0,
            "filas_restantes": n,
            "razon": "Punto de partida para medir el efecto de cada politica.",
        }
    )

    if deduplicar_primero:
        df, reg = deduplicar(df, cfg)
        bitacora.append(reg)
        n = reg["filas_restantes"]
        df = df.cache()
        df.count()

    for pol in cfg["limpieza"]["politicas"]:
        df, reg = _aplicar_una(df, pol, n)
        n = reg["filas_restantes"]
        bitacora.append(reg)

    return df, pd.DataFrame(bitacora)

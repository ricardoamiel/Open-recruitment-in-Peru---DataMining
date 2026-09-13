"""Perfilado generico de una tabla analitica en Spark.

Todas las funciones reciben un DataFrame de Spark y devuelven un DataFrame de
pandas pequeno, apto para mostrarse en el notebook y exportarse como artefacto.
El calculo pesado ocurre en Spark; a pandas solo llega el resumen.
"""

from __future__ import annotations

import pandas as pd
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType


def resumen_columnas(df: DataFrame, aproximado: bool = True) -> pd.DataFrame:
    """Tipo, nulos y cardinalidad de cada columna en una sola pasada."""
    n = df.count()
    expr = []
    for c, t in df.dtypes:
        expr.append(F.sum(F.col(c).isNull().cast("long")).alias(f"nulos__{c}"))
        if t.startswith("array"):
            expr.append(F.lit(None).cast("long").alias(f"dist__{c}"))
        elif aproximado:
            expr.append(F.approx_count_distinct(F.col(c), 0.02).alias(f"dist__{c}"))
        else:
            expr.append(F.countDistinct(F.col(c)).alias(f"dist__{c}"))

    fila = df.agg(*expr).collect()[0].asDict()

    filas = []
    for c, t in df.dtypes:
        nulos = fila[f"nulos__{c}"] or 0
        filas.append(
            {
                "columna": c,
                "tipo": t,
                "nulos": int(nulos),
                "pct_nulos": round(100.0 * nulos / n, 2) if n else 0.0,
                "distintos_aprox": fila[f"dist__{c}"],
            }
        )
    return pd.DataFrame(filas).sort_values("pct_nulos", ascending=False).reset_index(drop=True)


def contar_duplicados(df: DataFrame, clave: list[str]) -> pd.DataFrame:
    """Cuantas filas sobran si la clave debiera ser unica."""
    total = df.count()
    unicos = df.select(*clave).distinct().count()
    return pd.DataFrame(
        [
            {
                "clave": " + ".join(clave),
                "filas": total,
                "claves_unicas": unicos,
                "filas_excedentes": total - unicos,
                "pct_excedente": round(100.0 * (total - unicos) / total, 3) if total else 0.0,
            }
        ]
    )


def resumen_numerico(df: DataFrame, columnas: list[str], error: float = 0.001) -> pd.DataFrame:
    """Estadisticos robustos por cuantiles aproximados, sin traer los datos."""
    cuantiles = [0.01, 0.25, 0.5, 0.75, 0.95, 0.99]
    filas = []
    for c in columnas:
        if c not in df.columns:
            continue
        q = df.select(c).na.drop().stat.approxQuantile(c, cuantiles, error)
        base = df.select(
            F.count(c).alias("n"),
            F.mean(c).alias("media"),
            F.stddev(c).alias("desv"),
            F.min(c).alias("min"),
            F.max(c).alias("max"),
        ).collect()[0]
        filas.append(
            {
                "columna": c,
                "n": base["n"],
                "media": base["media"],
                "desv": base["desv"],
                "min": base["min"],
                "p01": q[0] if q else None,
                "p25": q[1] if q else None,
                "mediana": q[2] if q else None,
                "p75": q[3] if q else None,
                "p95": q[4] if q else None,
                "p99": q[5] if q else None,
                "max": base["max"],
            }
        )
    return pd.DataFrame(filas)


def top_categorias(df: DataFrame, columna: str, n: int = 15) -> pd.DataFrame:
    """Frecuencia de las categorias mas comunes, con su peso relativo."""
    total = df.count()
    out = (
        df.groupBy(columna)
        .agg(F.count("*").alias("frecuencia"))
        .orderBy(F.desc("frecuencia"))
        .limit(n)
        .toPandas()
    )
    out["pct"] = (100.0 * out["frecuencia"] / total).round(2)
    return out


def resumen_canasta(df: DataFrame, columna_items: str) -> pd.DataFrame:
    """Tamano de las canastas y cardinalidad del universo de items."""
    if not isinstance(df.schema[columna_items].dataType, ArrayType):
        raise TypeError(f"{columna_items} no es una columna de tipo array")
    tam = df.select(F.size(F.col(columna_items)).alias("tam"))
    q = tam.stat.approxQuantile("tam", [0.5, 0.9, 0.99], 0.001)
    universo = df.select(F.explode(columna_items).alias("i")).select("i").distinct().count()
    base = tam.select(
        F.count("*").alias("canastas"),
        F.mean("tam").alias("tam_medio"),
        F.max("tam").alias("tam_max"),
        F.sum(F.when(F.col("tam") == 0, 1).otherwise(0)).alias("canastas_vacias"),
    ).collect()[0]
    return pd.DataFrame(
        [
            {
                "canastas": base["canastas"],
                "canastas_vacias": base["canastas_vacias"],
                "tam_medio": round(base["tam_medio"], 2),
                "tam_mediano": q[0],
                "tam_p90": q[1],
                "tam_p99": q[2],
                "tam_max": base["tam_max"],
                "universo_items": universo,
            }
        ]
    )


def cobertura_temporal(df: DataFrame, columna_tiempo: str) -> pd.DataFrame:
    r = df.select(
        F.min(columna_tiempo).alias("desde"),
        F.max(columna_tiempo).alias("hasta"),
        F.count(columna_tiempo).alias("con_fecha"),
    ).collect()[0]
    return pd.DataFrame([r.asDict()])

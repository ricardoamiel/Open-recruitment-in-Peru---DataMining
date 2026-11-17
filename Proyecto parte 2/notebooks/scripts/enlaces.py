"""Analisis de enlaces de la Parte IV: PageRank y HITS.

Tres implementaciones, todas escritas a partir de su definicion:

1. pagerank_spark: iteracion de potencia sobre DataFrames de Spark, la misma
   idea que el PageRank de GraphFrames (un mensaje por arista y una suma por
   destino en cada paso), sin depender de un paquete externo.
2. pagerank_local: la misma iteracion con una matriz dispersa de scipy. Sirve
   para verificar la de Spark y para barrer el factor de amortiguamiento, que
   exige decenas de corridas y en local cuesta milisegundos.
3. hits_local: hubs y authorities por iteracion de potencia sobre la matriz de
   adyacencia del bipartito entidad a proveedor.

Convencion de PageRank (lecture 11): r = beta M r + (1 - beta) / N. M reparte
el rango de cada nodo entre sus aristas salientes en proporcion al peso. Los
nodos sin aristas salientes (dead ends) filtrarian rango en cada paso; su masa
se reparte de manera uniforme, que equivale a la matriz M' de la lecture, donde
la columna de un dead end se llena con 1 / N.
"""

import time

import numpy as np
from scipy import sparse
from pyspark.sql import functions as F


def matriz_transicion(src, dst, peso, n):
    """M columna estocastica como matriz dispersa: M[j, i] = peso(i, j) / salida(i).

    Devuelve M y la mascara de dead ends (nodos sin peso saliente).
    """
    A = sparse.csr_matrix((peso, (src, dst)), shape=(n, n))
    salida = np.asarray(A.sum(1)).ravel()
    inv = np.divide(1.0, salida, out=np.zeros(n), where=salida > 0)
    M = (sparse.diags(inv) @ A).T.tocsr()
    return M, salida == 0


def pagerank_local(M, sin_salida, beta=0.85, tol=1e-10, max_iter=500, personal=None):
    """Iteracion de potencia con teletransporte.

    personal es el vector de reinicio; si es None el salto va uniforme a todos
    los nodos (PageRank clasico). Devuelve el rango y el numero de iteraciones.
    """
    n = M.shape[0]
    v = np.full(n, 1.0 / n) if personal is None else personal / personal.sum()
    r = v.copy()
    for it in range(1, max_iter + 1):
        fuga = r[sin_salida].sum()
        nuevo = beta * (M @ r) + (beta * fuga + 1 - beta) * v
        if np.abs(nuevo - r).sum() < tol:
            return nuevo, it
        r = nuevo
    return r, max_iter


def pagerank_spark(spark, aristas, nodos, beta=0.85, tol=1e-8, max_iter=100):
    """PageRank sobre DataFrames.

    aristas trae src, dst y peso; nodos trae la columna nodo con todos los
    vertices. En cada paso cada arista lleva rango(src) * peso / salida(src) a
    su destino, se suma por destino y se agrega el teletransporte y la masa de
    los dead ends. localCheckpoint corta el linaje en cada iteracion: sin eso el
    plan crece con cada paso y la iteracion 50 recalcula las 49 anteriores.
    """
    n = nodos.count()
    salida = aristas.groupBy("src").agg(F.sum("peso").alias("s"))
    m = (aristas.join(salida, "src")
         .select("src", "dst", (F.col("peso") / F.col("s")).alias("w"))
         .cache())
    m.count()
    con_salida = salida.select(F.col("src").alias("nodo"), F.lit(True).alias("tiene"))
    r = (nodos.select("nodo").join(con_salida, "nodo", "left")
         .select("nodo", F.coalesce("tiene", F.lit(False)).alias("tiene"),
                 F.lit(1.0 / n).alias("r"))
         .localCheckpoint())
    historial = []
    for it in range(1, max_iter + 1):
        t0 = time.perf_counter()
        fuga = r.filter(~F.col("tiene")).agg(F.sum("r")).first()[0] or 0.0
        base = (beta * fuga + 1 - beta) / n
        aporte = (m.join(r.select(F.col("nodo").alias("src"), "r"), "src")
                  .groupBy("dst").agg(F.sum(F.col("r") * F.col("w")).alias("a")))
        nuevo = (r.join(aporte.withColumnRenamed("dst", "nodo"), "nodo", "left")
                 .select("nodo", "tiene", "r",
                         (beta * F.coalesce("a", F.lit(0.0)) + base).alias("r2"))
                 .localCheckpoint())
        delta = nuevo.agg(F.sum(F.abs(F.col("r2") - F.col("r")))).first()[0]
        r = nuevo.select("nodo", "tiene", F.col("r2").alias("r"))
        historial.append({"iteracion": it, "delta_l1": delta,
                          "segundos": time.perf_counter() - t0})
        if delta < tol:
            break
    m.unpersist()
    return r.select("nodo", F.col("r").alias("pagerank")), historial


def hits_local(A, tol=1e-10, max_iter=1000):
    """Hubs y authorities de la matriz A (filas apuntan a columnas).

    a = A^T h y h = A a, normalizando cada paso por la norma 2. Converge al
    primer vector singular izquierdo (hubs) y derecho (authorities) de A.
    """
    h = np.ones(A.shape[0]) / np.sqrt(A.shape[0])
    a = None
    for it in range(1, max_iter + 1):
        a = A.T @ h
        a /= np.linalg.norm(a)
        h2 = A @ a
        h2 /= np.linalg.norm(h2)
        if np.abs(h2 - h).sum() < tol:
            return h2, a, it
        h = h2
    return h, a, max_iter


def solapamiento_top(x, y, k=100):
    """Fraccion de los k primeros de x que tambien estan entre los k primeros de y."""
    return len(set(np.argsort(-x)[:k]) & set(np.argsort(-y)[:k])) / k


def verificar():
    """Casos hechos a mano contra la definicion.

    1. Ciclo de tres nodos: por simetria el rango es 1/3 para cada uno.
    2. Dead end: dos nodos, 0 -> 1, beta = 0.8. Con M' la columna de 1 se
       llena con 1/2, asi que r0 = 0.8 r1 / 2 + 0.1 y, como r0 + r1 = 1,
       la solucion exacta es r = (5/14, 9/14).
    3. HITS en una estrella: el unico hub apunta a dos authorities iguales.
    """
    M, d = matriz_transicion([0, 1, 2], [1, 2, 0], [1.0, 1.0, 1.0], 3)
    r, _ = pagerank_local(M, d, beta=0.85)
    assert np.allclose(r, 1 / 3)
    M, d = matriz_transicion([0], [1], [1.0], 2)
    r, _ = pagerank_local(M, d, beta=0.8)
    assert np.allclose(r, [5 / 14, 9 / 14]), r
    A = sparse.csr_matrix(np.array([[0, 1, 1], [0, 0, 0], [0, 0, 0]], dtype=float))
    h, a, _ = hits_local(A)
    assert np.allclose(a, [0, 1 / np.sqrt(2), 1 / np.sqrt(2)]) and np.argmax(h) == 0
    return True

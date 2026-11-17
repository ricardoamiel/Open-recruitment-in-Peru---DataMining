"""Deteccion de comunidades de la Parte V.

Cinco piezas, escritas desde su definicion (lectures 12 y 13):

1. modularidad: Q = suma sobre comunidades de [m_c / m - (d_c / 2m)^2], con
   pesos. Es la medida con la que se comparan todos los metodos.
2. betweenness_aristas y girvan_newman: Brandes para la intermediacion de
   aristas (una BFS por nodo, acumulando dependencias hacia atras) y el corte
   iterativo de la arista de mayor intermediacion. Exacto y caro: O(n m) por
   corte, por eso solo corre sobre un subgrafo.
3. espectral: vectores propios del laplaciano normalizado simetrico y KMeans
   sobre sus filas normalizadas (Ng, Jordan y Weiss).
4. propagacion_etiquetas_spark: cada nodo adopta la etiqueta de mayor peso
   entre sus vecinos; es la variante escalable que trae GraphFrames, escrita
   sobre DataFrames.
5. ari y nmi: acuerdo entre dos particiones, a partir de la tabla de
   contingencia. Q mide una particion contra el azar; ARI y NMI miden si dos
   particiones dicen lo mismo, o si una particion coincide con etiquetas
   externas como el departamento o el rubro.
6. bigclam: comunidades solapadas. P(u, v) = 1 - exp(-F_u . F_v), F >= 0, y
   ascenso de gradiente proyectado sobre la verosimilitud.
"""

from collections import deque

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import eigsh
from pyspark.sql import functions as F
from pyspark.sql import Window


def modularidad(A, etiquetas):
    """A simetrica (dispersa), etiquetas por nodo; -1 cuenta como comunidad propia por nodo."""
    A = sparse.csr_matrix(A)
    etq = np.asarray(etiquetas).copy()
    sueltos = etq < 0
    etq[sueltos] = etq.max() + 1 + np.arange(sueltos.sum())
    grado = np.asarray(A.sum(1)).ravel()
    dos_m = grado.sum()
    _, c = np.unique(etq, return_inverse=True)
    S = sparse.csr_matrix((np.ones(len(c)), (np.arange(len(c)), c)))
    interno = (S.T @ A @ S).diagonal()            # 2 m_c (cada arista interna cuenta dos veces)
    d_c = S.T @ grado
    return float((interno / dos_m - (d_c / dos_m) ** 2).sum())


def contingencia(a, b):
    _, ia = np.unique(a, return_inverse=True)
    _, ib = np.unique(b, return_inverse=True)
    return sparse.csr_matrix((np.ones(len(ia)), (ia, ib))).toarray()


def ari(a, b):
    """Indice de Rand ajustado.

    Rand cuenta los pares de elementos en los que las dos particiones estan de
    acuerdo (juntos en ambas o separados en ambas). El ajuste resta lo que se
    esperaria por azar con los mismos tamanos de grupo: 0 es azar, 1 es
    identico, y puede ser negativo.
    """
    C = contingencia(a, b)
    comb = lambda x: x * (x - 1) / 2
    suma_ij = comb(C).sum()
    suma_a, suma_b = comb(C.sum(1)).sum(), comb(C.sum(0)).sum()
    esperado = suma_a * suma_b / comb(C.sum())
    maximo = (suma_a + suma_b) / 2
    return float((suma_ij - esperado) / (maximo - esperado)) if maximo != esperado else 1.0


def nmi(a, b):
    """Informacion mutua normalizada por la media aritmetica de las entropias.

    I(A;B) mide cuanto se reduce la incertidumbre sobre el grupo de un elemento
    en B al conocer su grupo en A. Se divide por (H(A) + H(B)) / 2 para que
    quede entre 0 (independientes) y 1 (identicas), la convencion de sklearn.
    """
    C = contingencia(a, b)
    n = C.sum()
    P = C / n
    pa, pb = P.sum(1), P.sum(0)
    nz = P > 0
    I = (P[nz] * np.log(P[nz] / np.outer(pa, pb)[nz])).sum()
    H = lambda p: -(p[p > 0] * np.log(p[p > 0])).sum()
    den = (H(pa) + H(pb)) / 2
    return float(I / den) if den > 0 else 1.0


def betweenness_aristas(vecinos):
    """Intermediacion de cada arista no dirigida (sin pesos), algoritmo de Brandes.

    vecinos es una lista de listas. Devuelve un dict {(u, v): valor} con u < v.
    """
    n = len(vecinos)
    eb = {}
    for s in range(n):
        pila, pred = [], [[] for _ in range(n)]
        sigma = np.zeros(n); sigma[s] = 1
        dist = np.full(n, -1); dist[s] = 0
        cola = deque([s])
        while cola:
            v = cola.popleft(); pila.append(v)
            for w in vecinos[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1; cola.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]; pred[w].append(v)
        delta = np.zeros(n)
        while pila:
            w = pila.pop()
            for v in pred[w]:
                c = sigma[v] / sigma[w] * (1 + delta[w])
                e = (v, w) if v < w else (w, v)
                eb[e] = eb.get(e, 0.0) + c
                delta[v] += c
    return {e: b / 2 for e, b in eb.items()}       # cada camino se conto desde sus dos extremos


def componentes(vecinos):
    n = len(vecinos)
    etq = np.full(n, -1); c = 0
    for s in range(n):
        if etq[s] >= 0:
            continue
        cola = deque([s]); etq[s] = c
        while cola:
            v = cola.popleft()
            for w in vecinos[v]:
                if etq[w] < 0:
                    etq[w] = c; cola.append(w)
        c += 1
    return etq


def girvan_newman(A, max_cortes=None):
    """Corta la arista de mayor intermediacion hasta vaciar el grafo.

    Registra la particion cada vez que aumenta el numero de componentes, con
    su modularidad medida sobre el grafo original. Devuelve la lista de
    particiones [{k, Q, etiquetas, cortes}].
    """
    A = sparse.csr_matrix(A)
    n = A.shape[0]
    vecinos = [set(A.indices[A.indptr[i]:A.indptr[i + 1]]) - {i} for i in range(n)]
    historia, k_previo, cortes = [], 0, 0
    total = sum(len(v) for v in vecinos) // 2
    while cortes < (max_cortes or total):
        etq = componentes([list(v) for v in vecinos])
        k = etq.max() + 1
        if k > k_previo:
            historia.append({"k": int(k), "Q": modularidad(A, etq), "etiquetas": etq.copy(), "cortes": cortes})
            k_previo = k
        eb = betweenness_aristas([list(v) for v in vecinos])
        if not eb:
            break
        u, v = max(eb, key=eb.get)
        vecinos[u].discard(v); vecinos[v].discard(u)
        cortes += 1
    return historia


def espectral(A, k, semilla=0):
    """Ng, Jordan y Weiss: k vectores propios mayores de D^-1/2 A D^-1/2, filas normalizadas, KMeans."""
    from sklearn.cluster import KMeans
    A = sparse.csr_matrix(A, dtype=float)
    d = np.asarray(A.sum(1)).ravel()
    Dm = sparse.diags(1 / np.sqrt(np.maximum(d, 1e-12)))
    N = Dm @ A @ Dm
    vals, vecs = eigsh(N, k=k, which="LA")
    X = vecs / np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-12)
    etq = KMeans(k, n_init=10, random_state=semilla).fit_predict(X)
    return etq, np.sort(vals)[::-1]


def propagacion_etiquetas_spark(aristas, nodos, max_iter=10):
    """Label propagation sincrona sobre DataFrames.

    aristas trae src, dst y peso (una sola direccion; se simetriza aqui).
    En cada paso cada nodo toma la etiqueta con mayor peso total entre sus
    vecinos; los empates se rompen por la etiqueta menor para que el
    resultado sea determinista. Devuelve el DataFrame nodo, etiqueta y el
    numero de nodos que cambiaron en cada iteracion.
    """
    sim = aristas.select("src", "dst", "peso").union(
        aristas.select(F.col("dst").alias("src"), F.col("src").alias("dst"), "peso")).cache()
    etq = nodos.select("nodo", F.col("nodo").alias("etiqueta")).localCheckpoint()
    cambios = []
    for _ in range(max_iter):
        votos = (sim.join(etq.withColumnRenamed("nodo", "src"), "src")
                 .groupBy(F.col("dst").alias("nodo"), "etiqueta").agg(F.sum("peso").alias("p")))
        w = Window.partitionBy("nodo").orderBy(F.desc("p"), F.asc("etiqueta"))
        nueva = (votos.withColumn("r", F.row_number().over(w)).filter("r = 1")
                 .select("nodo", F.col("etiqueta").alias("nueva")))
        junto = (etq.join(nueva, "nodo", "left")
                 .select("nodo", "etiqueta", F.coalesce("nueva", "etiqueta").alias("nueva")).localCheckpoint())
        n_cambios = junto.filter("etiqueta != nueva").count()
        cambios.append(n_cambios)
        etq = junto.select("nodo", F.col("nueva").alias("etiqueta"))
        if n_cambios == 0:
            break
    sim.unpersist()
    return etq, cambios


def bigclam(A, K, iters=300, paso=0.05, semilla=0, F0=None, tol=1e-5):
    """BigCLAM por ascenso de gradiente proyectado (F >= 0).

    log L = suma_{(u,v) en E} log(1 - exp(-F_u.F_v)) - suma_{(u,v) no en E} F_u.F_v.
    El segundo termino se calcula con la suma total de F, sin recorrer los
    pares no conectados: suma_{v != u, v no vecino} F_v = F_total - F_u - suma vecinos.
    El gradiente de cada fila se recorta en norma para que los nodos de grado
    alto no exploten en los primeros pasos.
    """
    A = sparse.csr_matrix(A, copy=True)          # copia: no tocar los pesos de quien llama
    A.data[:] = 1
    n = A.shape[0]
    rng = np.random.default_rng(semilla)
    Fm = rng.uniform(0, 0.5, (n, K)) if F0 is None else F0.copy()
    filas, cols = A.nonzero()
    historia = []
    previo = -np.inf
    for it in range(iters):
        prod = np.einsum("ij,ij->i", Fm[filas], Fm[cols])
        e = np.exp(-np.clip(prod, 1e-10, 50))
        coef = e / (1 - e)                                   # d/dx log(1 - exp(-x)) = e / (1 - e)
        grad_pos = sparse.csr_matrix((coef, (filas, cols)), shape=(n, n)) @ Fm
        suma_vec = A @ Fm
        total = Fm.sum(0)
        grad = grad_pos - (total[None, :] - Fm - suma_vec)
        norma = np.linalg.norm(grad, axis=1, keepdims=True)
        grad = grad / np.maximum(1, norma / 5.0)
        Fm = np.maximum(Fm + paso * grad, 0)
        if it % 10 == 0 or it == iters - 1:
            prod = np.einsum("ij,ij->i", Fm[filas], Fm[cols])
            # filas y cols traen cada arista en las dos direcciones, de ahi las mitades
            ll_pos = np.log(1 - np.exp(-np.clip(prod, 1e-10, 50))).sum() / 2
            todos_pares = (Fm.sum(0) @ Fm.sum(0) - (Fm * Fm).sum()) / 2
            ll = ll_pos - (todos_pares - prod.sum() / 2)
            historia.append({"iteracion": it, "log_verosimilitud": float(ll)})
            if abs(ll - previo) < tol * abs(previo):
                break
            previo = ll
    return Fm, historia


def membresias_bigclam(Fm, A):
    """Umbral de la lecture: delta = sqrt(-log(1 - epsilon)), epsilon = densidad del grafo."""
    n = A.shape[0]
    eps = A.nnz / (n * (n - 1))
    delta = np.sqrt(-np.log(1 - eps))
    return Fm >= delta, delta


# Club de karate de Zachary (34 nodos, 78 aristas), para las pruebas.
KARATE = [(0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6), (0, 7), (0, 8), (0, 10), (0, 11), (0, 12), (0, 13),
          (0, 17), (0, 19), (0, 21), (0, 31), (1, 2), (1, 3), (1, 7), (1, 13), (1, 17), (1, 19), (1, 21), (1, 30),
          (2, 3), (2, 7), (2, 8), (2, 9), (2, 13), (2, 27), (2, 28), (2, 32), (3, 7), (3, 12), (3, 13), (4, 6),
          (4, 10), (5, 6), (5, 10), (5, 16), (6, 16), (8, 30), (8, 32), (8, 33), (9, 33), (13, 33), (14, 32),
          (14, 33), (15, 32), (15, 33), (18, 32), (18, 33), (19, 33), (20, 32), (20, 33), (22, 32), (22, 33),
          (23, 25), (23, 27), (23, 29), (23, 32), (23, 33), (24, 25), (24, 27), (24, 31), (25, 31), (26, 29),
          (26, 33), (27, 33), (28, 31), (28, 33), (29, 32), (29, 33), (30, 32), (30, 33), (31, 32), (31, 33),
          (32, 33)]


def karate():
    u, v = zip(*KARATE)
    A = sparse.csr_matrix((np.ones(156), (u + v, v + u)), shape=(34, 34))
    return A


def verificar():
    """Valores publicados para el club de karate.

    1. Las dos facciones reales tienen Q = 0.3582 (valor de la documentacion de networkx).
    2. Girvan-Newman alcanza su maximo Q = 0.4013 con 5 comunidades.
    3. La arista de mayor intermediacion es (0, 31), con 71.39 (Brandes).
    """
    A = karate()
    mr_hi = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 16, 17, 19, 21]
    faccion = np.array([0 if i in mr_hi else 1 for i in range(34)])
    assert abs(modularidad(A, faccion) - 0.3582) < 1e-3, modularidad(A, faccion)
    vec = [list(A.indices[A.indptr[i]:A.indptr[i + 1]]) for i in range(34)]
    eb = betweenness_aristas(vec)
    top = max(eb, key=eb.get)
    assert top == (0, 31) and abs(eb[top] - 71.3929) < 1e-3, (top, eb[top])
    h = girvan_newman(A)
    mejor = max(h, key=lambda x: x["Q"])
    assert mejor["k"] == 5 and abs(mejor["Q"] - 0.4013) < 1e-3, (mejor["k"], mejor["Q"])
    rng = np.random.default_rng(0)
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
    for _ in range(5):
        a, b = rng.integers(0, 4, 200), rng.integers(0, 6, 200)
        b[:120] = a[:120]
        assert abs(ari(a, b) - adjusted_rand_score(a, b)) < 1e-10
        assert abs(nmi(a, b) - normalized_mutual_info_score(a, b)) < 1e-10
    assert ari(faccion, 1 - faccion) == 1.0 and nmi(faccion, faccion) == 1.0
    return True

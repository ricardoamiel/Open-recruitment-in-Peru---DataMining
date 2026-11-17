"""Implementaciones propias de los algoritmos del Proyecto 2, semanas 7 a 10.

Igual que en el Proyecto 1, son cortas a proposito: el objetivo es poder
explicar cada linea y contrastarlas despues contra Spark MLlib o
scikit-learn. Siguen la notacion de las lectures (MMDS, capitulos 7 y 9).
"""

import numpy as np
from scipy import sparse

# ============================================================================
# Clustering, semana 7
# ============================================================================


def kmeans_pp_inicio(X, k, semilla=0):
    """Inicializacion k-means++ tal como la lecture.

    El primer centroide es un punto al azar. Cada siguiente se elige con
    probabilidad proporcional a D(x)^2, la distancia al cuadrado al centroide
    ya elegido mas cercano: los puntos lejanos tienen mas chance, y por eso
    los centroides iniciales quedan bien separados.
    """
    rng = np.random.default_rng(semilla)
    centros = [X[rng.integers(len(X))]]
    d2 = ((X - centros[0]) ** 2).sum(1)
    for _ in range(1, k):
        p = d2 / d2.sum()
        # Seleccion por probabilidad acumulada: el primer punto cuya
        # acumulada supera un numero uniforme en [0, 1].
        nuevo = X[np.searchsorted(np.cumsum(p), rng.random())]
        centros.append(nuevo)
        d2 = np.minimum(d2, ((X - nuevo) ** 2).sum(1))
    return np.array(centros)


def asignar(X, C):
    """Indice del centroide mas cercano y su distancia al cuadrado."""
    # ||x - c||^2 = ||x||^2 - 2 x.c + ||c||^2, sin materializar n * k * d.
    d2 = (X ** 2).sum(1)[:, None] - 2 * X @ C.T + (C ** 2).sum(1)[None, :]
    d2 = np.maximum(d2, 0)
    j = d2.argmin(1)
    return j, d2[np.arange(len(X)), j]


def kmeans(X, k, semilla=0, max_iter=100, tol=1e-6):
    """Lloyd: asignar al centroide mas cercano y recalcular promedios.

    Se detiene cuando ningun punto cambia de cluster. Devuelve etiquetas,
    centroides, SSE e iteraciones usadas.
    """
    C = kmeans_pp_inicio(X, k, semilla)
    previo = None
    for it in range(1, max_iter + 1):
        j, d2 = asignar(X, C)
        if previo is not None and (j == previo).all():
            break
        previo = j
        for c in range(k):
            miembros = X[j == c]
            # Un cluster vacio se reinicia en el punto peor representado.
            C[c] = miembros.mean(0) if len(miembros) else X[d2.argmax()]
    return j, C, float(d2.sum()), it


def silueta(X, etiquetas, muestra=3000, semilla=0):
    """Silueta media sobre una muestra: (b - a) / max(a, b).

    a es la distancia media a los de su cluster y b la menor distancia media
    a otro cluster. Es O(n^2), por eso se estima sobre una muestra.
    """
    rng = np.random.default_rng(semilla)
    idx = rng.choice(len(X), min(muestra, len(X)), replace=False)
    Xm, em = X[idx], etiquetas[idx]
    D = np.sqrt(np.maximum((Xm ** 2).sum(1)[:, None] - 2 * Xm @ Xm.T + (Xm ** 2).sum(1)[None, :], 0))
    s = np.zeros(len(Xm))
    for i in range(len(Xm)):
        propio = em == em[i]
        if propio.sum() <= 1:
            continue
        a = D[i, propio].sum() / (propio.sum() - 1)
        b = min(D[i, em == c].mean() for c in np.unique(em) if c != em[i])
        s[i] = (b - a) / max(a, b)
    return float(s.mean())


def dbscan(X, eps, min_pts):
    """DBSCAN de la lecture: nucleos, expansion por alcanzabilidad y ruido.

    Un punto es nucleo si tiene al menos min_pts vecinos a distancia eps,
    contandose a si mismo. Los clusters crecen de nucleo en nucleo; los
    puntos que no son alcanzables desde ningun nucleo quedan como ruido (-1).
    La vecindad se consulta con un KD-tree para no calcular n^2 distancias.
    """
    from scipy.spatial import cKDTree
    vecinos = cKDTree(X).query_ball_point(X, eps)
    nucleo = np.array([len(v) >= min_pts for v in vecinos])
    etiqueta = np.full(len(X), -1)
    actual = 0
    for i in range(len(X)):
        if etiqueta[i] != -1 or not nucleo[i]:
            continue
        etiqueta[i] = actual
        pila = [i]
        while pila:
            p = pila.pop()
            if not nucleo[p]:
                continue          # un punto frontera se une pero no expande
            for q in vecinos[p]:
                if etiqueta[q] == -1:
                    etiqueta[q] = actual
                    pila.append(q)
        actual += 1
    return etiqueta, nucleo


def aglomerativo(X):
    """Jerarquico aglomerativo con enlace por centroide, como en la lecture.

    Cada punto empieza como su propio cluster y en cada paso se fusionan los
    dos cuyos centroides estan mas cerca. Es la version O(n^3) de la lecture,
    con la matriz de distancias completa; solo sirve para muestras pequenas y
    para verificar a scipy. Devuelve la matriz de fusiones en el formato de
    scipy: los dos clusters, la distancia y el tamano del nuevo.
    """
    centros = {i: X[i].astype(float) for i in range(len(X))}
    tam = {i: 1 for i in range(len(X))}
    fusiones, siguiente = [], len(X)
    while len(centros) > 1:
        ids = list(centros)
        C = np.array([centros[i] for i in ids])
        D = np.sqrt(((C[:, None, :] - C[None, :, :]) ** 2).sum(-1))
        np.fill_diagonal(D, np.inf)
        a, b = np.unravel_index(D.argmin(), D.shape)
        ia, ib = ids[a], ids[b]
        n = tam[ia] + tam[ib]
        centros[siguiente] = (tam[ia] * centros[ia] + tam[ib] * centros[ib]) / n
        tam[siguiente] = n
        fusiones.append([min(ia, ib), max(ia, ib), D[a, b], n])
        for i in (ia, ib):
            del centros[i], tam[i]
        siguiente += 1
    return np.array(fusiones)


# ============================================================================
# Recomendacion, semanas 9 y 10
# ============================================================================


def normalizar_filas(M):
    """Divide cada fila por su norma L2, para que el producto sea el coseno."""
    n = np.sqrt(np.asarray(M.multiply(M).sum(1)).ravel())
    n[n == 0] = 1
    return sparse.diags(1 / n) @ M


def tfidf(M):
    """TF-IDF de la lecture sobre una matriz de conteos fila x termino.

    TF es la frecuencia del termino normalizada por la maxima de la fila e
    IDF es log(N / n_i), con n_i el numero de filas que contienen el termino.
    """
    M = sparse.csr_matrix(M, dtype=np.float64)
    maximo = M.max(1).toarray().ravel(); maximo[maximo == 0] = 1
    tf = sparse.diags(1 / maximo) @ M
    df = np.bincount(M.indices, minlength=M.shape[1])
    idf = np.log(M.shape[0] / np.maximum(df, 1))
    return sparse.csr_matrix(tf @ sparse.diags(idf))


def vecinos_usuario(R, k=30):
    """Filtrado colaborativo usuario usuario: similitud coseno y k vecinos.

    R es la matriz de interaccion implicita usuario x item. Devuelve la
    matriz de similitud con solo los k vecinos mas similares por fila, que es
    la N(x) de la lecture.
    """
    Rn = normalizar_filas(R)
    S = (Rn @ Rn.T).toarray()
    np.fill_diagonal(S, 0)
    if k < S.shape[1]:
        corte = np.argpartition(-S, k, axis=1)[:, k:]
        np.put_along_axis(S, corte, 0, axis=1)
    return S


def puntaje_vecinos(S, R, filas):
    """Prediccion de la lecture: promedio ponderado por la similitud.

    r(x, i) = sum_y s_xy r_yi / sum_y |s_xy|, sobre los vecinos y de x.
    """
    Sx = S[filas]
    return np.asarray(Sx @ R) / (np.abs(Sx).sum(1, keepdims=True) + 1e-9)


def top_k(puntajes, k, excluir=None):
    """Indices de los k mayores puntajes por fila, ya ordenados.

    excluir es una matriz dispersa con los items conocidos que no deben
    recomendarse de nuevo.
    """
    P = np.array(puntajes, dtype=np.float64, copy=True)
    if excluir is not None:
        filas, cols = excluir.nonzero()
        P[filas, cols] = -np.inf
    idx = np.argpartition(-P, k, axis=1)[:, :k]
    orden = np.take_along_axis(P, idx, 1).argsort(1)[:, ::-1]
    return np.take_along_axis(idx, orden, 1)


def metricas_ranking(recomendados, relevantes, k):
    """Precision, recall y NDCG en k, promediados sobre usuarios con relevantes.

    relevantes es una lista de conjuntos. NDCG descuenta cada acierto por
    log2 de su posicion mas uno, y lo divide por el maximo alcanzable.
    """
    p = r = n = 0.0
    usuarios = 0
    descuento = 1 / np.log2(np.arange(2, k + 2))
    for rec, rel in zip(recomendados, relevantes):
        if not rel:
            continue
        usuarios += 1
        acierto = np.array([i in rel for i in rec[:k]], dtype=float)
        p += acierto.sum() / k
        r += acierto.sum() / len(rel)
        n += (acierto * descuento).sum() / descuento[:min(len(rel), k)].sum()
    return {"precision": p / usuarios, "recall": r / usuarios, "ndcg": n / usuarios,
            "usuarios": usuarios}

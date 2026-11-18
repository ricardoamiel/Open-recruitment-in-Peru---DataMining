"""Aprendizaje de representacion en grafos de la Parte VI.

Todo escrito desde su definicion (lectures 14 y 15), sin bibliotecas de grafos:

1. grafo_knn: k vecinos mas cercanos por coseno, simetrizado por union.
2. embedding_svd: SVD truncada de la adyacencia normalizada D^-1/2 A D^-1/2,
   escalada por la raiz de los valores singulares. Es la factorizacion de
   matrices de la lecture usada como embedder.
3. caminatas_node2vec: caminatas de segundo orden. Desde v, habiendo llegado
   de t, el paso a x pesa 1/p si x = t, 1 si x es vecino de t y 1/q si no lo es.
   Se muestrea por rechazo, como en la implementacion de referencia de PyG:
   se propone un vecino uniforme y se acepta con probabilidad peso / max(peso).
4. skipgram: skip-gram con muestreo negativo (word2vec), en numpy con SGD por
   lotes. Las caminatas son las frases y los nodos las palabras.
5. prediccion_enlaces: se reservan aristas, se entrena el embedding sin ellas
   y se mide el AUC de distinguir aristas reservadas de pares al azar.
"""

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import svds


def grafo_knn(X, k=10):
    """Adyacencia simetrica del grafo KNN por coseno (union de las dos direcciones)."""
    from sklearn.neighbors import NearestNeighbors
    Xn = X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)
    nn = NearestNeighbors(n_neighbors=k + 1, metric="cosine").fit(Xn)
    _, idx = nn.kneighbors(Xn)
    n = len(X)
    filas = np.repeat(np.arange(n), k)
    cols = idx[:, 1:].ravel()
    A = sparse.csr_matrix((np.ones(len(filas)), (filas, cols)), shape=(n, n))
    A = ((A + A.T) > 0).astype(float)
    return A.tocsr()


def embedding_svd(A, d=32):
    A = sparse.csr_matrix(A, dtype=float)
    g = np.asarray(A.sum(1)).ravel()
    Dm = sparse.diags(1 / np.sqrt(np.maximum(g, 1e-12)))
    U, s, _ = svds(Dm @ A @ Dm, k=d)
    orden = np.argsort(-s)
    return U[:, orden] * np.sqrt(s[orden]), s[orden]


def caminatas_node2vec(A, p=1.0, q=1.0, por_nodo=10, largo=40, semilla=0):
    """Matriz de caminatas (por_nodo * n filas, largo columnas) con el sesgo de p y q."""
    A = sparse.csr_matrix(A)
    n = A.shape[0]
    ptr, ind = A.indptr, A.indices
    grado = np.diff(ptr)
    rng = np.random.default_rng(semilla)
    inicio = np.tile(np.arange(n), por_nodo)
    inicio = inicio[grado[inicio] > 0]
    W = np.empty((len(inicio), largo), dtype=np.int64)
    W[:, 0] = inicio
    W[:, 1] = ind[ptr[inicio] + (rng.random(len(inicio)) * grado[inicio]).astype(int)]
    w_max = max(1 / p, 1.0, 1 / q)
    vecinos = [set(ind[ptr[i]:ptr[i + 1]]) for i in range(n)] if (p != 1 or q != 1) else None
    for paso in range(2, largo):
        t, v = W[:, paso - 2], W[:, paso - 1]
        x = ind[ptr[v] + (rng.random(len(v)) * grado[v]).astype(int)]
        if vecinos is None:                     # p = q = 1: caminata uniforme, es DeepWalk
            W[:, paso] = x
            continue
        pendientes = np.arange(len(v))
        elegido = np.empty(len(v), dtype=np.int64)
        while len(pendientes):
            tt, xx = t[pendientes], x[pendientes]
            peso = np.where(xx == tt, 1 / p,
                            np.fromiter((xi in vecinos[ti] for xi, ti in zip(xx, tt)), bool, len(xx)) * (1 - 1 / q) + 1 / q)
            acepta = rng.random(len(pendientes)) * w_max < peso
            elegido[pendientes[acepta]] = xx[acepta]
            pendientes = pendientes[~acepta]
            if len(pendientes):
                vv = v[pendientes]
                x[pendientes] = ind[ptr[vv] + (rng.random(len(vv)) * grado[vv]).astype(int)]
        W[:, paso] = elegido
    return W


def pares_contexto(W, ventana=5):
    """Pares (centro, contexto) de todas las caminatas con una ventana simetrica."""
    c, x = [], []
    for d in range(1, ventana + 1):
        c.append(W[:, :-d].ravel()); x.append(W[:, d:].ravel())
        c.append(W[:, d:].ravel()); x.append(W[:, :-d].ravel())
    return np.concatenate(c), np.concatenate(x)


def skipgram(W, n, d=32, ventana=5, negativos=5, epocas=2, lote=4096, tasa=0.025, semilla=0):
    """Skip-gram con muestreo negativo. Devuelve la matriz de embeddings de entrada (n x d).

    Para cada par (u, v) se maximiza log s(z_u . c_v) + suma de log s(-z_u . c_w)
    sobre negativos w muestreados con la distribucion unigrama elevada a 3/4.
    """
    rng = np.random.default_rng(semilla)
    Z = (rng.random((n, d)) - .5) / d
    Cx = np.zeros((n, d))
    frec = np.bincount(W.ravel(), minlength=n) ** 0.75
    frec /= frec.sum()
    acum = np.cumsum(frec)
    sig = lambda x: 1 / (1 + np.exp(-np.clip(x, -10, 10)))
    for ep in range(epocas):
        cen, ctx = pares_contexto(W, ventana)
        orden = rng.permutation(len(cen))
        total = len(orden)
        for a in range(0, total, lote):
            lr = tasa * max(1e-4, 1 - (ep * total + a) / (epocas * total))
            b = orden[a:a + lote]
            u, v = cen[b], ctx[b]
            neg = np.searchsorted(acum, rng.random((len(b), negativos)))
            zu = Z[u]
            g_pos = 1 - sig(np.einsum("ij,ij->i", zu, Cx[v]))
            g_neg = -sig(np.einsum("ij,ikj->ik", zu, Cx[neg]))
            grad_u = g_pos[:, None] * Cx[v] + np.einsum("ik,ikj->ij", g_neg, Cx[neg])
            np.add.at(Cx, v, lr * g_pos[:, None] * zu)
            np.add.at(Cx, neg.ravel(), lr * (g_neg[:, :, None] * zu[:, None, :]).reshape(-1, d))
            np.add.at(Z, u, lr * grad_u)
    return Z


def reservar_aristas(A, fraccion=0.1, semilla=0):
    """Saca una fraccion de aristas sin aislar nodos. Devuelve A sin ellas, positivos y negativos."""
    rng = np.random.default_rng(semilla)
    T = sparse.triu(A, 1).tocoo()
    grado = np.asarray((A > 0).sum(1)).ravel()
    orden = rng.permutation(T.nnz)
    reserva = []
    g = grado.copy()
    meta = int(fraccion * T.nnz)
    for e in orden:
        u, v = T.row[e], T.col[e]
        if g[u] > 1 and g[v] > 1:
            reserva.append(e); g[u] -= 1; g[v] -= 1
            if len(reserva) >= meta:
                break
    reserva = np.array(reserva)
    queda = np.setdiff1d(np.arange(T.nnz), reserva)
    n = A.shape[0]
    B = sparse.csr_matrix((np.ones(len(queda)), (T.row[queda], T.col[queda])), shape=(n, n))
    B = B + B.T
    pos = np.c_[T.row[reserva], T.col[reserva]]
    neg = rng.integers(0, n, size=(len(pos) * 3, 2))
    neg = neg[(neg[:, 0] != neg[:, 1]) & (np.asarray(A[neg[:, 0], neg[:, 1]]).ravel() == 0)][:len(pos)]
    return B.tocsr(), pos, neg


def auc_enlaces(Z, pos, neg):
    """AUC del producto punto normalizado (coseno) entre extremos."""
    from sklearn.metrics import roc_auc_score
    Zn = Z / np.maximum(np.linalg.norm(Z, axis=1, keepdims=True), 1e-12)
    s_pos = np.einsum("ij,ij->i", Zn[pos[:, 0]], Zn[pos[:, 1]])
    s_neg = np.einsum("ij,ij->i", Zn[neg[:, 0]], Zn[neg[:, 1]])
    y = np.r_[np.ones(len(s_pos)), np.zeros(len(s_neg))]
    return roc_auc_score(y, np.r_[s_pos, s_neg])


def verificar():
    """Pruebas sobre dos cliques unidos por una arista.

    1. Con p = q = 1 las caminatas solo usan aristas existentes.
    2. Con q muy chico (exploracion hacia afuera) la caminata cruza el puente
       mas seguido que con q muy grande (se queda cerca).
    3. Skip-gram separa los dos cliques: el coseno medio dentro de un clique
       supera al coseno medio entre cliques.
    """
    n = 20
    A = np.zeros((n, n))
    A[:10, :10] = 1; A[10:, 10:] = 1; np.fill_diagonal(A, 0); A[9, 10] = A[10, 9] = 1
    A = sparse.csr_matrix(A)
    W = caminatas_node2vec(A, 1, 1, por_nodo=5, largo=10)
    assert all(A[W[i, j], W[i, j + 1]] for i in range(len(W)) for j in range(9))
    cruces = lambda W: np.mean((W[:, :-1] < 10) != (W[:, 1:] < 10))
    lejos = cruces(caminatas_node2vec(A, 1, 0.1, por_nodo=20, largo=30, semilla=1))
    cerca = cruces(caminatas_node2vec(A, 1, 10, por_nodo=20, largo=30, semilla=1))
    assert lejos > cerca, (lejos, cerca)
    Z = skipgram(caminatas_node2vec(A, 1, 1, por_nodo=20, largo=20), n, d=8, epocas=3, lote=512)
    Zn = Z / np.linalg.norm(Z, axis=1, keepdims=True)
    S = Zn @ Zn.T
    dentro = (S[:10, :10].sum() - 10 + S[10:, 10:].sum() - 10) / 180
    entre = S[:10, 10:].mean()
    assert dentro > entre + 0.2, (dentro, entre)
    return True

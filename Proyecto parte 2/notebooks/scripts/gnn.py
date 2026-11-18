"""Redes neuronales sobre grafos de la Parte VI: GCN, GraphSAGE y GAT.

Escritas a mano en PyTorch, sin PyTorch Geometric, para que cada capa se lea
como su ecuacion (lecture 15):

1. GCN (Kipf y Welling): H' = A_hat H W, con A_hat = D^-1/2 (A + I) D^-1/2.
   Cada nodo promedia a sus vecinos y a si mismo, ponderados por grado.
2. GraphSAGE (Hamilton y otros), agregador de media:
   H' = [H W_1 || media de los vecinos de H W_2]. Separa al nodo de su
   vecindario, lo que ayuda cuando el nodo tiene pocos vecinos.
3. GAT (Velickovic y otros): H'_i = suma_j alfa_ij W h_j, con
   alfa_ij = softmax_j(LeakyReLU(a . [W h_i || W h_j])). Aprende cuanto
   pesa cada vecino en lugar de fijarlo por el grado.

Las tres se entrenan como autoencoder de enlaces: dos capas producen un vector
por nodo, el puntaje de un par es el producto punto y la perdida es entropia
cruzada binaria entre aristas del grafo y pares al azar (muestreo negativo).
"""

import time

import numpy as np
import torch
from torch import nn
from scipy import sparse

torch.set_num_threads(3)


def a_tensor(M):
    M = M.tocoo()
    return torch.sparse_coo_tensor(np.vstack([M.row, M.col]), M.data.astype(np.float32), M.shape, check_invariants=False).coalesce()


def normalizada_gcn(A):
    A = (sparse.csr_matrix(A) > 0).astype(float) + sparse.eye(A.shape[0])
    d = np.asarray(A.sum(1)).ravel()
    Dm = sparse.diags(1 / np.sqrt(d))
    return a_tensor(Dm @ A @ Dm)


def media_vecinos(A):
    A = (sparse.csr_matrix(A) > 0).astype(float)
    d = np.asarray(A.sum(1)).ravel()
    return a_tensor(sparse.diags(1 / np.maximum(d, 1)) @ A)


class CapaGCN(nn.Module):
    def __init__(self, entrada, salida):
        super().__init__(); self.W = nn.Linear(entrada, salida)
    def forward(self, H, ctx):
        return torch.sparse.mm(ctx["A_gcn"], self.W(H))


class CapaSAGE(nn.Module):
    def __init__(self, entrada, salida):
        super().__init__(); self.propio = nn.Linear(entrada, salida); self.vecinos = nn.Linear(entrada, salida, bias=False)
    def forward(self, H, ctx):
        return self.propio(H) + self.vecinos(torch.sparse.mm(ctx["A_media"], H))


class CapaGAT(nn.Module):
    def __init__(self, entrada, salida, cabezas=2):
        super().__init__()
        self.cabezas, self.d = cabezas, salida // cabezas
        self.W = nn.Linear(entrada, salida, bias=False)
        self.a_dst = nn.Parameter(torch.randn(cabezas, self.d) * .1)
        self.a_src = nn.Parameter(torch.randn(cabezas, self.d) * .1)
    def forward(self, H, ctx):
        src, dst = ctx["src"], ctx["dst"]                         # incluye lazos propios
        Wh = self.W(H).view(-1, self.cabezas, self.d)
        e = nn.functional.leaky_relu((Wh[dst] * self.a_dst).sum(-1) + (Wh[src] * self.a_src).sum(-1), 0.2)
        n = H.shape[0]
        maximo = torch.full((n, self.cabezas), -1e9).scatter_reduce(0, dst[:, None].expand_as(e), e, "amax")
        ex = torch.exp(e - maximo[dst])                           # softmax por nodo destino, estable
        suma = torch.zeros(n, self.cabezas).index_add_(0, dst, ex)
        alfa = ex / suma[dst].clamp_min(1e-12)
        salida = torch.zeros(n, self.cabezas, self.d).index_add_(0, dst, alfa[..., None] * Wh[src])
        return salida.reshape(n, -1)


CAPAS = {"GCN": CapaGCN, "GraphSAGE": CapaSAGE, "GAT": CapaGAT}


class Codificador(nn.Module):
    def __init__(self, tipo, entrada, oculta=64, salida=32):
        super().__init__()
        self.c1, self.c2 = CAPAS[tipo](entrada, oculta), CAPAS[tipo](oculta, salida)
    def forward(self, X, ctx):
        return self.c2(torch.relu(self.c1(X, ctx)), ctx)


def contexto(A):
    B = (sparse.csr_matrix(A) > 0).tocoo()
    n = A.shape[0]
    lazo = np.arange(n)
    return {"A_gcn": normalizada_gcn(A), "A_media": media_vecinos(A),
            "src": torch.as_tensor(np.r_[B.row, lazo], dtype=torch.long),
            "dst": torch.as_tensor(np.r_[B.col, lazo], dtype=torch.long)}


def entrenar(tipo, A, X, epocas=200, lote=40000, tasa=0.01, semilla=0):
    """Entrena el codificador sobre las aristas de A. Devuelve los embeddings (numpy) y la historia de pérdida."""
    torch.manual_seed(semilla); rng = np.random.default_rng(semilla)
    ctx = contexto(A)
    Xt = torch.as_tensor(X, dtype=torch.float32)
    T = sparse.triu((sparse.csr_matrix(A) > 0), 1).tocoo()
    aristas = np.c_[T.row, T.col]
    n = A.shape[0]
    modelo = Codificador(tipo, X.shape[1])
    opt = torch.optim.Adam(modelo.parameters(), lr=tasa)
    historia, t0 = [], time.perf_counter()
    for ep in range(epocas):
        modelo.train(); opt.zero_grad()
        Z = modelo(Xt, ctx)
        pos = torch.as_tensor(aristas[rng.integers(0, len(aristas), lote)])
        neg = torch.as_tensor(rng.integers(0, n, (lote, 2)))
        s_pos = (Z[pos[:, 0]] * Z[pos[:, 1]]).sum(1)
        s_neg = (Z[neg[:, 0]] * Z[neg[:, 1]]).sum(1)
        perdida = nn.functional.binary_cross_entropy_with_logits(
            torch.cat([s_pos, s_neg]), torch.cat([torch.ones(lote), torch.zeros(lote)]))
        perdida.backward(); opt.step()
        if ep % 20 == 0 or ep == epocas - 1:
            historia.append({"epoca": ep, "perdida": float(perdida.detach())})
    modelo.eval()
    with torch.no_grad():
        Z = modelo(Xt, ctx).numpy()
    return Z, historia, time.perf_counter() - t0


def auc_producto(Z, pos, neg):
    """AUC con el mismo puntaje con que se entrenó: producto punto."""
    from sklearn.metrics import roc_auc_score
    s = lambda P: np.einsum("ij,ij->i", Z[P[:, 0]], Z[P[:, 1]])
    return roc_auc_score(np.r_[np.ones(len(pos)), np.zeros(len(neg))], np.r_[s(pos), s(neg)])


def verificar():
    """Dos cliques unidos por un puente: cada capa debe aprender a separarlos.

    Se reserva una arista interna de cada clique y se compara su puntaje con el
    de pares entre cliques: el AUC tiene que ser alto para las tres capas. Y la
    atención de GAT tiene que sumar 1 sobre los vecinos de cada nodo.
    """
    n = 20
    M = np.zeros((n, n)); M[:10, :10] = 1; M[10:, 10:] = 1; np.fill_diagonal(M, 0); M[9, 10] = M[10, 9] = 1
    A = sparse.csr_matrix(M)
    X = np.c_[np.ones(n), np.random.default_rng(0).normal(size=(n, 3))]
    pos = np.array([[0, 1], [2, 3], [11, 12], [13, 14]]); neg = np.array([[0, 15], [2, 17], [4, 19], [6, 12]])
    for tipo in CAPAS:
        Z, _, _ = entrenar(tipo, A, X, epocas=150, lote=200)
        assert auc_producto(Z, pos, neg) >= 0.9, tipo
    capa = CapaGAT(4, 4)
    ctx = contexto(A)
    Wh = capa.W(torch.as_tensor(X, dtype=torch.float32)).view(-1, 2, 2)
    e = (Wh[ctx["dst"]] * capa.a_dst).sum(-1) + (Wh[ctx["src"]] * capa.a_src).sum(-1)
    m = torch.full((n, 2), -1e9).scatter_reduce(0, ctx["dst"][:, None].expand_as(e), e, "amax")
    ex = torch.exp(e - m[ctx["dst"]]); s = torch.zeros(n, 2).index_add_(0, ctx["dst"], ex)
    assert torch.allclose(torch.zeros(n, 2).index_add_(0, ctx["dst"], ex / s[ctx["dst"]]), torch.ones(n, 2))
    return True

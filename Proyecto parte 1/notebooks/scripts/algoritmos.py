"""Implementaciones propias de los algoritmos del curso, semanas 3 a 6.

Todas son cortas a proposito. El objetivo no es competir con una biblioteca
sino poder explicar linea por linea que hace cada una, y poder medirlas contra
la version exacta o contra la implementacion de Spark MLlib.

El porque de cada eleccion esta en docs/JUSTIFICACION.md.
"""

import hashlib
from collections import Counter
from itertools import combinations

import numpy as np
import pandas as pd

# ============================================================================
# Algoritmos de similitud, semanas 3 y 4. Implementados a mano para poder
# explicar cada linea; se contrastan despues contra Spark MLlib.
# ============================================================================

# Primo de Mersenne. Con 2^31 - 1 el producto a*x cabe en int64 sin desbordar,
# que es lo que permite vectorizar MinHash con numpy en vez de iterar en Python.
P = (1 << 31) - 1


def h(x, semilla=0):
    """Hash determinista entre procesos.

    No se usa hash() de Python porque viene aleatorizado por proceso y haria
    irreproducibles las firmas y los buckets entre ejecuciones.
    """
    d = hashlib.blake2b(str(x).encode(), digest_size=8,
                        salt=semilla.to_bytes(8, "little")).digest()
    return int.from_bytes(d, "little")


def shingles(texto, k=9):
    """Conjunto de k-shingles de caracteres sobre el texto ya normalizado."""
    t = " ".join(texto.split())
    return {t[i:i + k] for i in range(max(1, len(t) - k + 1))}


def jaccard(a, b):
    """Similitud de Jaccard exacta. Es la verdad de referencia del proyecto."""
    if not a and not b: return 1.0
    return len(a & b) / len(a | b)


class MinHash:
    """Firmas MinHash con n funciones hash lineales de la forma (a*x + b) mod P.

    La propiedad que lo sostiene: para una permutacion aleatoria, la
    probabilidad de que dos conjuntos compartan el minimo es exactamente su
    similitud de Jaccard. Con n funciones, la fraccion de coincidencias en la
    firma estima Jaccard con error del orden de 1 sobre la raiz de n.
    """

    def __init__(self, n=128, semilla=0):
        rng = np.random.default_rng(semilla)
        self.n = n
        self.a = rng.integers(1, P, n, dtype=np.int64)
        self.b = rng.integers(0, P, n, dtype=np.int64)

    def firma(self, conjunto):
        xs = np.array([h(e) % P for e in conjunto], dtype=np.int64)
        if xs.size == 0:
            return np.full(self.n, P, dtype=np.int64)
        # Una sola matriz n por tamano del conjunto, y un minimo por fila.
        return ((self.a[:, None] * xs[None, :] + self.b[:, None]) % P).min(axis=1)

    @staticmethod
    def similitud(f1, f2):
        """Jaccard estimada: fraccion de posiciones donde las firmas coinciden."""
        return float((f1 == f2).mean())


def bandas(firma, b, r):
    """Parte la firma en b bandas de r filas y devuelve un hash por banda.

    Dos documentos son candidatos si coinciden en al menos una banda. La
    semilla por banda evita que bandas distintas con el mismo contenido
    colisionen entre si.
    """
    if len(firma) != b * r:
        raise ValueError(f"firma de {len(firma)} no se parte en {b} por {r}")
    return [h(tuple(firma[i * r:(i + 1) * r]), i) for i in range(b)]


def prob_candidato(s, b, r):
    """Curva S: probabilidad de que un par con similitud s sea candidato."""
    return 1 - (1 - np.asarray(s, dtype=float) ** r) ** b


def umbral_lsh(b, r):
    """Aproximacion estandar del punto de inflexion de la curva S.

    Cuidado con una confusion frecuente: en este umbral la probabilidad de ser
    candidato no es un medio sino 1 menos (1 menos 1 sobre b) elevado a b, es
    decir alrededor de 0,63. El valor marca donde la curva cambia de
    concavidad, no donde vale la mitad.
    """
    return (1 / b) ** (1 / r)


def simhash(pesos, bits=64, semilla=0):
    """SimHash sobre un vector con pesos, por proyeccion en hiperplanos aleatorios.

    A diferencia de MinHash, que trata un conjunto sin pesos y estima Jaccard,
    SimHash respeta el peso de cada termino y estima similitud coseno. Por eso
    es el adecuado para TF-IDF y MinHash lo es para conjuntos de codigos.
    """
    v = np.zeros(bits)
    for token, peso in pesos.items():
        bh = h(token, semilla)
        v += peso * np.array([1 if (bh >> i) & 1 else -1 for i in range(bits)])
    return int(sum(1 << i for i in range(bits) if v[i] > 0))


def hamming(a, b):
    """Numero de bits distintos entre dos firmas SimHash."""
    return bin(a ^ b).count("1")

# ============================================================================
# Estructuras de resumen para flujos, semana 5. Ninguna sustituye a otra:
# responden preguntas distintas sobre el mismo flujo.
# ============================================================================
class BloomFilter:
    """Responde si un elemento pudo haber aparecido antes, con memoria fija.

    Nunca dice que no a algo que si estaba: los falsos negativos son imposibles
    por construccion. Si puede decir que si a algo que no estaba, con una
    probabilidad que se calcula de antemano.
    """

    def __init__(self, n_esperado, fpr_objetivo=0.01):
        self.m = int(np.ceil(-n_esperado * np.log(fpr_objetivo) / np.log(2) ** 2))
        self.k = max(1, round(self.m / n_esperado * np.log(2)))
        self.bits = bytearray((self.m + 7) // 8)
        self.insertados = 0

    def _posiciones(self, x):
        # Doble hash de Kirsch y Mitzenmacher: k posiciones a partir de dos
        # hashes, con el mismo comportamiento que k funciones independientes.
        h1, h2 = h(x, 0), h(x, 1) | 1
        return [(h1 + i * h2) % self.m for i in range(self.k)]

    def agregar(self, x):
        for p in self._posiciones(x):
            self.bits[p >> 3] |= 1 << (p & 7)
        self.insertados += 1

    def __contains__(self, x):
        return all(self.bits[p >> 3] >> (p & 7) & 1 for p in self._posiciones(x))

    @property
    def bytes_usados(self):
        return len(self.bits)

    def fpr_teorica(self, n=None):
        n = self.insertados if n is None else n
        return float((1 - np.exp(-self.k * n / self.m)) ** self.k)


class CountMinSketch:
    """Estima cuantas veces aparecio cada clave sin guardar un diccionario.

    Nunca subestima: cada celda acumula la clave mas sus colisiones, y el
    estimador toma el minimo de las d filas. El error queda acotado por epsilon
    por el total de eventos, con probabilidad 1 menos delta.
    """

    def __init__(self, epsilon=1e-3, delta=1e-3, w=None, d=None):
        # Se puede dimensionar por garantia de error o fijando ancho y
        # profundidad, que es lo que hace falta para compararlo con un Bloom.
        self.w = int(w) if w else int(np.ceil(np.e / epsilon))
        self.d = int(d) if d else int(np.ceil(np.log(1 / delta)))
        self.tabla = np.zeros((self.d, self.w), dtype=np.int64)
        self.total = 0

    def _columnas(self, x):
        return [h(x, i) % self.w for i in range(self.d)]

    def agregar(self, x, veces=1):
        for fila, col in enumerate(self._columnas(x)):
            self.tabla[fila, col] += veces
        self.total += veces

    def estimar(self, x):
        return int(min(self.tabla[f, c] for f, c in enumerate(self._columnas(x))))

    @property
    def bytes_usados(self):
        return self.tabla.nbytes

    def error_teorico(self):
        """Cota superior del error absoluto: epsilon por el total de eventos."""
        return np.e / self.w * self.total


class DGIM:
    """Cuenta unos en los ultimos N elementos de un flujo binario.

    Guarda cubos de tamano potencia de dos, a lo mas r de cada tamano, de modo
    que la memoria es del orden del logaritmo al cuadrado de N en lugar de N.
    El error relativo esta acotado por 1 sobre r.
    """

    def __init__(self, N, r=2):
        self.N, self.r, self.t = N, r, 0
        self.cubos = []   # cada cubo es [marca de tiempo, tamano], del mas viejo al mas nuevo

    def agregar(self, bit):
        self.t += 1
        # Se descarta el cubo mas viejo cuando sale por completo de la ventana.
        while self.cubos and self.cubos[0][0] <= self.t - self.N:
            self.cubos.pop(0)
        if not bit:
            return
        self.cubos.append([self.t, 1])
        self._fusionar()

    def _fusionar(self):
        tamano = 1
        while True:
            indices = [i for i, c in enumerate(self.cubos) if c[1] == tamano]
            if len(indices) <= self.r:
                return
            viejo, siguiente = indices[0], indices[1]
            # El cubo fusionado hereda la marca de tiempo del mas reciente.
            self.cubos[siguiente][1] = tamano * 2
            self.cubos.pop(viejo)
            tamano *= 2

    def estimar(self):
        """Suma todos los cubos y cuenta solo la mitad del mas antiguo."""
        vivos = [c for c in self.cubos if c[0] > self.t - self.N]
        if not vivos:
            return 0
        return sum(c[1] for c in vivos[1:]) + vivos[0][1] // 2

    @property
    def n_cubos(self):
        return len(self.cubos)


def reservoir(flujo, k, semilla=0):
    """Muestra uniforme de tamano fijo k sin conocer el largo del flujo.

    Invariante: tras ver i elementos, cada uno esta en la muestra con
    probabilidad k sobre i. El elemento i se acepta con esa probabilidad y
    desaloja a uno al azar.
    """
    rng = np.random.default_rng(semilla)
    muestra = []
    for i, x in enumerate(flujo):
        if i < k:
            muestra.append(x)
        else:
            j = int(rng.integers(0, i + 1))
            if j < k:
                muestra[j] = x
    return muestra


def muestreo_por_clave(flujo, clave, fraccion, semilla=7):
    """Conserva todos los eventos de una fraccion de las claves.

    Es lo contrario del muestreo por evento: si se muestrea un evento de cada
    diez, ninguna pregunta por entidad se puede responder sobre la muestra,
    porque cada entidad queda incompleta. Aqui la entidad entra entera o no entra.
    """
    corte = fraccion * (1 << 32)
    return [x for x in flujo if (h(clave(x), semilla) % (1 << 32)) < corte]

# ============================================================================
# Patrones frecuentes, semana 6. A-Priori propio, que luego se contrasta
# contra FP-Growth de Spark MLlib sobre las mismas transacciones.
# ============================================================================


def apriori(transacciones, soporte_min):
    """Conjuntos frecuentes por niveles.

    Se apoya en la antimonotonia: si un conjunto no es frecuente, ningun
    superconjunto suyo puede serlo. Eso poda el espacio, pero obliga a una
    pasada completa por las transacciones en cada nivel, y ese es su costo.
    """
    n = len(transacciones)
    conj = [frozenset(t) for t in transacciones]

    conteo = Counter(frozenset([i]) for t in conj for i in t)
    frecuentes = {c: v for c, v in conteo.items() if v / n >= soporte_min}
    todos = dict(frecuentes)

    k = 2
    while frecuentes:
        candidatos = _candidatos(list(frecuentes), k)
        if not candidatos:
            break
        conteo = Counter(c for t in conj for c in candidatos if c <= t)
        frecuentes = {c: v for c, v in conteo.items() if v / n >= soporte_min}
        todos.update(frecuentes)
        k += 1
    return {c: v / n for c, v in todos.items()}


def _candidatos(frecuentes, k):
    """Une pares de conjuntos frecuentes y poda los que tienen algun
    subconjunto no frecuente."""
    previos = set(frecuentes)
    salida = set()
    for a, b in combinations(frecuentes, 2):
        union = a | b
        if len(union) == k and all(frozenset(s) in previos
                                   for s in combinations(union, k - 1)):
            salida.add(union)
    return list(salida)


def reglas(soportes, confianza_min=0.5):
    """Reglas con soporte, confianza y lift.

    El lift es el que distingue una asociacion real de una coincidencia por
    frecuencia: una confianza alta sobre un item que de por si aparece en casi
    todas las transacciones no dice nada.
    """
    filas = []
    for conjunto, soporte in soportes.items():
        if len(conjunto) < 2:
            continue
        for tam in range(1, len(conjunto)):
            for antecedente in combinations(sorted(conjunto), tam):
                ant = frozenset(antecedente); cons = conjunto - ant
                if ant not in soportes or cons not in soportes:
                    continue
                confianza = soporte / soportes[ant]
                if confianza < confianza_min:
                    continue
                filas.append({"antecedente": " + ".join(sorted(ant)),
                              "consecuente": " + ".join(sorted(cons)),
                              "soporte": round(soporte, 5),
                              "confianza": round(confianza, 4),
                              "lift": round(confianza / soportes[cons], 3)})
    return pd.DataFrame(filas).sort_values("lift", ascending=False).reset_index(drop=True)

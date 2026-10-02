"""Utilidades compartidas por los notebooks del proyecto.

Vive en notebooks/scripts junto a los notebooks que lo usan. Tres
responsabilidades y nada mas: abrir Spark, dibujar figuras con su lectura
obligatoria, y exportar agregados para el reporte interactivo de la Parte VI.
"""

import json, os, sys, time
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

RAIZ = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
FIGS, ARTEFACTOS = RAIZ / "figs", RAIZ / "artifacts"
PARQUET = RAIZ / "data" / "processed" / "tabla_analitica.parquet"
FIGS.mkdir(parents=True, exist_ok=True); ARTEFACTOS.mkdir(parents=True, exist_ok=True)

pd.set_option("display.width", 190); pd.set_option("display.max_colwidth", 64)

# Paleta validada para vision con deficiencia de color. La del curso no separa
# el verde del naranja bajo deuteranopia, asi que se reescalonaron esos tonos.
AZUL, ROJO, VERDE, MORADO, TEAL = "#2E6DB4", "#B3441F", "#6FAE3C", "#8B5BB5", "#00A0A0"
PALETA = [AZUL, ROJO, VERDE, MORADO, TEAL]
TINTA, SUAVE, REJILLA = "#1C1C1C", "#5A5A5A", "#E3E3E1"

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": REJILLA, "axes.labelcolor": SUAVE, "axes.titlecolor": TINTA,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.labelsize": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": SUAVE, "ytick.color": SUAVE, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "grid.color": REJILLA, "legend.frameon": False, "legend.fontsize": 9,
    "font.family": "DejaVu Sans", "figure.dpi": 110, "savefig.bbox": "tight"})


def fmt(x, _pos=None):
    """Formato compacto que conserva precision en magnitudes pequenas."""
    a = abs(x)
    if a >= 1e9: return f"{x/1e9:,.1f} MM"
    if a >= 1e6: return f"{x/1e6:,.1f} M"
    if a >= 1e4: return f"{x/1e3:,.0f} k"
    if x == int(x): return f"{int(x):,}"
    if a >= 100: return f"{x:,.0f}"
    if a >= 10:  return f"{x:,.1f}"
    if a >= 1:   return f"{x:,.2f}"
    return f"{x:.3f}"


MILES = mticker.FuncFormatter(fmt)
FIGURAS = []


def figura(fig, nombre, lectura):
    """Guarda la figura e imprime su lectura debajo.

    La lectura es obligatoria a proposito: el enunciado exige que cada hallazgo
    venga con su interpretacion, y la funcion falla si no la recibe. Asi es
    imposible dejar un grafico sin interpretar por descuido.
    """
    lectura = " ".join(lectura.split())
    if len(lectura) < 40:
        raise ValueError(f"La figura {nombre} necesita una lectura, no un rotulo")
    fig.savefig(FIGS / f"{nombre}.svg"); fig.savefig(FIGS / f"{nombre}.png", dpi=150)
    FIGURAS.append({"figura": nombre, "lectura": lectura})
    print(f"\nLectura de {nombre}\n{lectura}\n")


def exportar(df, nombre, descripcion):
    """Guarda una tabla pequena en CSV y JSON para el reporte web de la Parte VI."""
    df.to_csv(ARTEFACTOS / f"{nombre}.csv", index=False)
    df.to_json(ARTEFACTOS / f"{nombre}.json", orient="records", force_ascii=False, indent=1)
    indice = ARTEFACTOS / "indice.json"
    datos = json.loads(indice.read_text()) if indice.exists() else {}
    datos[nombre] = {"descripcion": " ".join(descripcion.split()), "filas": len(df)}
    indice.write_text(json.dumps(datos, ensure_ascii=False, indent=1))
    return df


from contextlib import contextmanager


@contextmanager
def cronometro(etiqueta):
    """Mide el tiempo de pared de un bloque y lo imprime."""
    t0 = time.perf_counter()
    yield
    print(f"{etiqueta}: {time.perf_counter() - t0:.2f} s")


def medir(fn, repeticiones=3):
    """Mediana de varias corridas, descartando la primera por calentamiento.

    Una sola corrida no es una medicion: el primer paso paga la compilacion, el
    llenado de cache y la lectura en frio.
    """
    fn()
    tiempos = []
    for _ in range(repeticiones):
        t0 = time.perf_counter(); fn(); tiempos.append(time.perf_counter() - t0)
    return float(np.median(tiempos))

# ------------------------------------------------------------- Spark local
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F


def abrir_spark(nombre, memoria="6g", particiones=16):
    """SparkSession en modo local.

    Se fija PYSPARK_PYTHON porque si el sistema tiene un SPARK_HOME propio, sus
    workers arrancan con otro interprete y los RDD fallan con
    PYTHON_VERSION_MISMATCH. No conviene vaciar SPARK_HOME: eso rompe el
    lanzamiento del gateway.
    """
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    spark = (SparkSession.builder.master("local[*]").appName(nombre)
             .config("spark.driver.memory", memoria)
             .config("spark.sql.shuffle.partitions", particiones)
             .config("spark.sql.session.timeZone", "America/Lima")
             .config("spark.sql.adaptive.enabled", "true")
             .config("spark.ui.showConsoleProgress", "false")
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    # Los workers no heredan el sys.path del driver. Sin esto, deserializar en un
    # worker un objeto definido en algoritmos.py falla con ModuleNotFoundError,
    # que es justo lo que ocurre al difundir una instancia de MinHash.
    for modulo in ("algoritmos.py", "ingesta.py"):
        ruta = Path(__file__).parent / modulo
        if ruta.exists():
            spark.sparkContext.addPyFile(str(ruta))
    return spark

# --------------------------------------------------- figuras de uso frecuente
def barras_h(datos, categoria, valor, titulo, etiqueta_x="", color=AZUL, alto=0.36):
    """Magnitud comparada entre categorias, ordenada y con el valor rotulado.

    El rotulo directo es lo que permite leer la figura sin depender del color.
    """
    d = datos.sort_values(valor, ascending=True)
    fig, ax = plt.subplots(figsize=(8.4, max(2.4, alto * len(d) + 1.1)))
    ax.barh(d[categoria].astype(str), d[valor], color=color, height=0.68)
    ax.xaxis.set_major_formatter(MILES)
    ax.grid(axis="x", alpha=.9); ax.set_axisbelow(True)
    ax.set_xlabel(etiqueta_x or valor); ax.set_title(titulo, loc="left", pad=12)
    tope = d[valor].max()
    for y, v in enumerate(d[valor]):
        ax.text(v + tope * .012, y, fmt(v), va="center", fontsize=8.5, color=SUAVE)
    ax.set_xlim(0, tope * 1.15)
    ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
    return fig, ax


def lineas(datos, x, series, titulo, etiqueta_y=""):
    """Evolucion temporal. Una sola escala vertical, nunca dos ejes."""
    fig, ax = plt.subplots(figsize=(9.2, 3.9))
    for i, s in enumerate(series):
        ax.plot(datos[x], datos[s], color=PALETA[i % 5], lw=2, label=s)
    ax.yaxis.set_major_formatter(MILES)
    ax.grid(axis="y", alpha=.9); ax.set_axisbelow(True)
    ax.set_xlabel(x); ax.set_ylabel(etiqueta_y or series[0])
    ax.set_title(titulo, loc="left", pad=12)
    if len(series) > 1: ax.legend(loc="upper left", ncols=min(len(series), 4))
    fig.autofmt_xdate(rotation=45, ha="right")
    return fig, ax


def barras_agrupadas(datos, categoria, series, titulo, etiqueta_y=""):
    """Pocas series sobre las mismas categorias, con leyenda fuera del trazado.

    La leyenda va encima y no dentro porque dentro choca con la barra mas alta
    justo cuando esa barra es el hallazgo.
    """
    x = np.arange(len(datos)); ancho = .8 / len(series)
    fig, ax = plt.subplots(figsize=(9.2, 4))
    for i, s in enumerate(series):
        ax.bar(x + i * ancho - .4 + ancho / 2, datos[s], ancho * .88,
               color=PALETA[i % 5], label=s)
    ax.set_xticks(x, [str(v) for v in datos[categoria]], rotation=28, ha="right")
    ax.yaxis.set_major_formatter(MILES)
    ax.grid(axis="y", alpha=.9); ax.set_axisbelow(True)
    ax.set_ylabel(etiqueta_y); ax.set_title(titulo, loc="left", pad=28)
    if len(series) > 1:
        ax.legend(loc="lower left", bbox_to_anchor=(0, 1.01, 1, .1),
                  ncols=min(len(series), 4), borderaxespad=0)
    ax.set_ylim(top=float(np.nanmax(datos[series].values)) * 1.08)
    return fig, ax


def mapa_calor(tabla, titulo, etiqueta="", formato="{:.0f}"):
    """Magnitud sobre dos dimensiones discretas, con rampa de un solo tono.

    Un solo tono codifica magnitud sin sugerir polaridad, que es lo que haria
    una rampa de dos colores o un arcoiris.
    """
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list(
        "az", ["#DCE8F5", "#B6CFEA", "#87B0DC", "#5B92CD", AZUL, "#1D4A7C"])
    fig, ax = plt.subplots(figsize=(1 + .78 * tabla.shape[1], 1.2 + .4 * tabla.shape[0]))
    im = ax.imshow(tabla.values, cmap=cmap, aspect="auto")
    ax.set_xticks(range(tabla.shape[1]), [str(c) for c in tabla.columns])
    ax.set_yticks(range(tabla.shape[0]), [str(i) for i in tabla.index])
    vmax = np.nanmax(tabla.values)
    for i in range(tabla.shape[0]):
        for j in range(tabla.shape[1]):
            v = tabla.values[i, j]
            if np.isfinite(v):
                ax.text(j, i, formato.format(v), ha="center", va="center", fontsize=8,
                        color="white" if v > .62 * vmax else TINTA)
    cb = fig.colorbar(im, ax=ax, fraction=.035, pad=.02)
    cb.outline.set_visible(False); cb.set_label(etiqueta, color=SUAVE, fontsize=9)
    ax.set_title(titulo, loc="left", pad=12)
    for s in ax.spines.values(): s.set_visible(False)
    ax.tick_params(length=0)
    return fig, ax


def gini(valores):
    """Coeficiente de Gini sobre valores positivos."""
    v = np.sort(np.asarray(valores, dtype=float)); v = v[np.isfinite(v) & (v > 0)]
    acum = np.cumsum(v) / v.sum(); x = np.arange(1, len(v) + 1) / len(v)
    return float(1 - 2 * np.trapezoid(np.r_[0, acum], np.r_[0, x]))


def lorenz(valores, titulo, etiqueta="entidades"):
    """Curva de Lorenz. Convierte la concentracion en una medida comparable."""
    v = np.sort(np.asarray(valores, dtype=float)); v = v[v > 0]
    acum = np.r_[0, np.cumsum(v) / v.sum()]; x = np.r_[0, np.arange(1, len(v) + 1) / len(v)]
    g = 1 - 2 * np.trapezoid(acum, x)
    fig, ax = plt.subplots(figsize=(5.4, 5))
    ax.plot([0, 1], [0, 1], color=SUAVE, lw=1.4, ls=(0, (4, 3)), label="igualdad perfecta")
    ax.plot(x, acum, color=AZUL, lw=2.2, label="distribucion observada")
    ax.fill_between(x, acum, x, color=AZUL, alpha=.10)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1, decimals=0))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1, decimals=0))
    ax.set_xlabel(f"porcentaje acumulado de {etiqueta}")
    ax.set_ylabel("porcentaje acumulado del monto")
    ax.set_title(titulo, loc="left", pad=12)
    ax.grid(alpha=.9); ax.set_axisbelow(True); ax.legend(loc="upper left")
    ax.text(.97, .06, f"Gini = {g:.3f}", ha="right", fontsize=11, fontweight="bold",
            color=TINTA, transform=ax.transAxes)
    return fig, float(g)

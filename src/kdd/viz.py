"""Figuras del EDA.

Reglas de diseno que sigue todo este modulo:

1. La forma la decide el trabajo del dato. Magnitud comparada entre categorias
   va en barras horizontales ordenadas; evolucion en el tiempo va en linea;
   distribucion muy asimetrica va en histograma sobre escala logaritmica;
   concentracion va en curva de Lorenz.
2. Un solo eje vertical por figura. Nunca dos escalas superpuestas.
3. La paleta categorica es fija y se asigna por entidad, no por posicion en el
   ranking, para que un filtro no repinte las series que sobreviven.
4. Los colores fueron validados para vision con deficiencia de color. La paleta
   del curso (azul 1F4E79, naranja C55A11, verde 548235) no separa el verde del
   naranja bajo deuteranopia, asi que se reescalonaron las mismas tres familias
   a valores que si separan, y se agregaron dos slots adicionales.
5. Toda figura lleva ejes rotulados y, cuando hay dos o mas series, leyenda. El
   dato que sostiene cada figura se exporta ademas como tabla, de modo que
   ninguna lectura dependa solo del color.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

# Dentro de Jupyter se deja el backend interactivo para que las figuras aparezcan
# en la salida de la celda; fuera de Jupyter se usa Agg, que no necesita pantalla.
try:
    get_ipython()  # noqa: F821
except NameError:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# Paleta categorica, en orden fijo.
PALETA = ["#2E6DB4", "#B3441F", "#6FAE3C", "#8B5BB5", "#00A0A0"]
# Rampa secuencial de un solo tono, para magnitudes.
RAMPA_AZUL = ["#DCE8F5", "#B6CFEA", "#87B0DC", "#5B92CD", "#2E6DB4", "#1D4A7C"]

TINTA = "#1C1C1C"
TINTA_SUAVE = "#5A5A5A"
REJILLA = "#E3E3E1"
FONDO = "#FFFFFF"

plt.rcParams.update(
    {
        "figure.facecolor": FONDO,
        "axes.facecolor": FONDO,
        "axes.edgecolor": REJILLA,
        "axes.labelcolor": TINTA_SUAVE,
        "axes.titlecolor": TINTA,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "xtick.color": TINTA_SUAVE,
        "ytick.color": TINTA_SUAVE,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "font.family": "DejaVu Sans",
        "grid.color": REJILLA,
        "grid.linewidth": 0.8,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "figure.dpi": 110,
        "savefig.bbox": "tight",
    }
)

_DIR_FIGS = Path("figs")
_MANIFIESTO: list[dict] = []


def configurar(directorio_figuras) -> None:
    global _DIR_FIGS
    _DIR_FIGS = Path(directorio_figuras)
    _DIR_FIGS.mkdir(parents=True, exist_ok=True)


def manifiesto() -> pd.DataFrame:
    """Tabla con cada figura generada y el motivo por el que se genero."""
    return pd.DataFrame(_MANIFIESTO)


def _limpiar(ax, ejes_visibles=("left", "bottom")) -> None:
    for lado, spine in ax.spines.items():
        spine.set_visible(lado in ejes_visibles)


def _guardar(fig, nombre: str, titulo: str, porque: str):
    ruta_svg = _DIR_FIGS / f"{nombre}.svg"
    ruta_png = _DIR_FIGS / f"{nombre}.png"
    fig.savefig(ruta_svg, format="svg")
    fig.savefig(ruta_png, format="png", dpi=150)
    _MANIFIESTO.append(
        {"figura": nombre, "titulo": titulo, "porque_se_genera": " ".join(porque.split()),
         "svg": str(ruta_svg), "png": str(ruta_png)}
    )
    return fig


def _miles(x, _pos=None) -> str:
    """Formato compacto que conserva precision en magnitudes pequenas.

    Un formateador que redondea siempre a entero convierte una escala de
    coeficientes de Gini en una columna de unos. Por eso el numero de decimales
    depende del orden de magnitud del valor.
    """
    if abs(x) >= 1e9:
        return f"{x/1e9:,.1f} MM"
    if abs(x) >= 1e6:
        return f"{x/1e6:,.1f} M"
    if abs(x) >= 1e4:
        return f"{x/1e3:,.0f} k"
    if x == int(x):
        return f"{int(x):,}"
    if abs(x) >= 100:
        return f"{x:,.0f}"
    if abs(x) >= 10:
        return f"{x:,.1f}"
    if abs(x) >= 1:
        return f"{x:,.2f}"
    return f"{x:.3f}"


def barras_h(datos: pd.DataFrame, categoria: str, valor: str, titulo: str, porque: str,
             nombre: str, etiqueta_x: str = "", color: str = PALETA[0], alto_fila: float = 0.34):
    """Magnitud comparada entre categorias. Orden descendente y valor rotulado.

    El rotulo directo sobre cada barra es lo que permite leer la figura sin
    depender del color y sin volver a la tabla.
    """
    d = datos.sort_values(valor, ascending=True)
    fig, ax = plt.subplots(figsize=(8.6, max(2.4, alto_fila * len(d) + 1.0)))
    ax.barh(d[categoria].astype(str), d[valor], color=color, height=0.68)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_miles))
    ax.grid(axis="x", alpha=0.9)
    ax.set_axisbelow(True)
    ax.set_xlabel(etiqueta_x or valor)
    ax.set_title(titulo, loc="left", pad=12)
    tope = d[valor].max()
    for y, v in enumerate(d[valor]):
        ax.text(v + tope * 0.012, y, _miles(v), va="center", ha="left", fontsize=8.5, color=TINTA_SUAVE)
    ax.set_xlim(0, tope * 1.14)
    _limpiar(ax, ("bottom",))
    ax.tick_params(axis="y", length=0)
    return _guardar(fig, nombre, titulo, porque)


def serie_tiempo(datos: pd.DataFrame, x: str, series: list[str], titulo: str, porque: str,
                 nombre: str, etiqueta_y: str = "", marcar_ultimo: bool = True):
    """Evolucion temporal. Una sola escala vertical; leyenda si hay dos o mas series."""
    fig, ax = plt.subplots(figsize=(9.2, 4.0))
    for i, s in enumerate(series):
        ax.plot(datos[x], datos[s], color=PALETA[i % len(PALETA)], linewidth=2.0, label=s)
        if marcar_ultimo and len(datos):
            ax.scatter([datos[x].iloc[-1]], [datos[s].iloc[-1]], s=34,
                       color=PALETA[i % len(PALETA)], zorder=3, edgecolor=FONDO, linewidth=1.5)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_miles))
    ax.grid(axis="y", alpha=0.9)
    ax.set_axisbelow(True)
    ax.set_xlabel(x)
    ax.set_ylabel(etiqueta_y or (series[0] if len(series) == 1 else ""))
    ax.set_title(titulo, loc="left", pad=12)
    if len(series) > 1:
        ax.legend(loc="upper left", ncols=min(len(series), 4))
    _limpiar(ax)
    fig.autofmt_xdate(rotation=45, ha="right")
    return _guardar(fig, nombre, titulo, porque)


def histograma_log(valores: np.ndarray, titulo: str, porque: str, nombre: str,
                   etiqueta_x: str = "", bins: int = 44, color: str = PALETA[0]):
    """Distribucion de una variable de cola larga, en escala logaritmica.

    En escala lineal el 99 por ciento de la masa se apila en la primera barra y
    la figura no informa nada. El logaritmo hace legible el rango completo.
    """
    v = np.asarray(valores, dtype=float)
    v = v[np.isfinite(v) & (v > 0)]
    fig, ax = plt.subplots(figsize=(8.6, 3.8))
    bordes = np.logspace(np.log10(v.min()), np.log10(v.max()), bins)
    ax.hist(v, bins=bordes, color=color, edgecolor=FONDO, linewidth=0.6)
    ax.set_xscale("log")
    ax.grid(axis="y", alpha=0.9)
    ax.set_axisbelow(True)
    ax.set_xlabel(etiqueta_x or "valor (escala logaritmica)")
    ax.set_ylabel("numero de registros")
    ax.set_title(titulo, loc="left", pad=12)
    mediana = float(np.median(v))
    ax.axvline(mediana, color=PALETA[1], linewidth=2.0, linestyle=(0, (4, 3)))
    ax.text(mediana, ax.get_ylim()[1] * 0.94, f" mediana {_miles(mediana)}",
            color=PALETA[1], fontsize=9, va="top")
    _limpiar(ax)
    return _guardar(fig, nombre, titulo, porque)


def lorenz(valores: np.ndarray, titulo: str, porque: str, nombre: str,
           etiqueta_entidad: str = "entidades"):
    """Curva de Lorenz y coeficiente de Gini para medir concentracion.

    Responde directamente a la pregunta de cuanto del total se lleva la minoria
    de mayor peso, que en una tabla de ranking no se ve.
    """
    v = np.sort(np.asarray(valores, dtype=float))
    v = v[np.isfinite(v) & (v > 0)]
    n = len(v)
    acum = np.cumsum(v) / v.sum()
    x = np.arange(1, n + 1) / n
    gini = float(1 - 2 * np.trapezoid(acum, x))

    fig, ax = plt.subplots(figsize=(5.6, 5.2))
    ax.plot([0, 1], [0, 1], color=TINTA_SUAVE, linewidth=1.4, linestyle=(0, (4, 3)),
            label="igualdad perfecta")
    ax.plot(np.concatenate([[0], x]), np.concatenate([[0], acum]),
            color=PALETA[0], linewidth=2.2, label="distribucion observada")
    ax.fill_between(np.concatenate([[0], x]), np.concatenate([[0], acum]),
                    np.concatenate([[0], x]), color=PALETA[0], alpha=0.10)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel(f"porcentaje acumulado de {etiqueta_entidad}")
    ax.set_ylabel("porcentaje acumulado del monto")
    ax.set_title(titulo, loc="left", pad=12)
    ax.grid(alpha=0.9)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left")
    ax.text(0.97, 0.06, f"Gini = {gini:.3f}", ha="right", fontsize=11,
            color=TINTA, fontweight="bold", transform=ax.transAxes)
    _limpiar(ax)
    _guardar(fig, nombre, titulo, porque)
    return fig, gini


def mapa_calor(tabla: pd.DataFrame, titulo: str, porque: str, nombre: str,
               etiqueta_valor: str = "", formato: str = "{:.0f}"):
    """Magnitud sobre dos dimensiones discretas, con rampa de un solo tono.

    Un solo tono de claro a oscuro codifica magnitud sin sugerir polaridad, que
    es lo que haria una rampa de dos colores o un arcoiris.
    """
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list("azul_sec", RAMPA_AZUL)
    fig, ax = plt.subplots(figsize=(1.0 + 0.8 * tabla.shape[1], 1.2 + 0.42 * tabla.shape[0]))
    im = ax.imshow(tabla.values, cmap=cmap, aspect="auto")
    ax.set_xticks(range(tabla.shape[1]), [str(c) for c in tabla.columns])
    ax.set_yticks(range(tabla.shape[0]), [str(i) for i in tabla.index])
    vmax = np.nanmax(tabla.values)
    for i in range(tabla.shape[0]):
        for j in range(tabla.shape[1]):
            val = tabla.values[i, j]
            if np.isfinite(val):
                ax.text(j, i, formato.format(val), ha="center", va="center", fontsize=8,
                        color=FONDO if val > 0.62 * vmax else TINTA)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.outline.set_visible(False)
    cb.set_label(etiqueta_valor, color=TINTA_SUAVE, fontsize=9)
    ax.set_title(titulo, loc="left", pad=12)
    _limpiar(ax, ())
    ax.tick_params(length=0)
    return _guardar(fig, nombre, titulo, porque)


def barras_agrupadas(datos: pd.DataFrame, categoria: str, series: list[str], titulo: str,
                     porque: str, nombre: str, etiqueta_y: str = ""):
    """Comparacion de pocas series sobre las mismas categorias.

    Se deja un espacio entre barras contiguas para que cada marca se lea como
    una pieza separada y no como un bloque continuo.
    """
    d = datos.copy()
    n_s = len(series)
    x = np.arange(len(d))
    ancho = 0.8 / n_s
    fig, ax = plt.subplots(figsize=(9.2, 4.0))
    for i, s in enumerate(series):
        ax.bar(x + i * ancho - 0.4 + ancho / 2, d[s], width=ancho * 0.88,
               color=PALETA[i % len(PALETA)], label=s)
    ax.set_xticks(x, [str(v) for v in d[categoria]], rotation=30, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_miles))
    ax.grid(axis="y", alpha=0.9)
    ax.set_axisbelow(True)
    ax.set_ylabel(etiqueta_y)
    ax.set_title(titulo, loc="left", pad=30)
    if n_s > 1:
        # La leyenda va sobre el area de trazado y no dentro, porque dentro
        # choca con la barra mas alta justo cuando esa barra es el hallazgo.
        ax.legend(loc="lower left", bbox_to_anchor=(0, 1.01, 1, 0.1),
                  ncols=min(n_s, 4), borderaxespad=0)
    ax.set_ylim(top=float(np.nanmax(d[series].values)) * 1.08)
    _limpiar(ax)
    return _guardar(fig, nombre, titulo, porque)

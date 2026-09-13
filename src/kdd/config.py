"""Carga del perfil de dataset.

El perfil es un YAML que declara metadatos, rutas, roles de columna y politicas
de limpieza. Este modulo lo lee, resuelve las rutas relativas contra la raiz del
proyecto y verifica que lo minimo indispensable este presente.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]

_CLAVES_OBLIGATORIAS = ["dataset", "ingesta", "roles", "limpieza", "particionado"]
_ROLES_OBLIGATORIOS = ["clave", "tiempo", "categoricas", "numericas"]


class Config(dict):
    """Diccionario del perfil con accesos por punto para lo que mas se usa."""

    @property
    def roles(self) -> dict:
        return self["roles"]

    @property
    def rutas(self) -> dict:
        return self["_rutas"]

    def ruta(self, nombre: str) -> Path:
        return self["_rutas"][nombre]


def cargar(nombre_o_ruta: str = "ocds_peru") -> Config:
    """Devuelve el perfil ya validado y con rutas absolutas."""
    ruta = Path(nombre_o_ruta)
    if not ruta.suffix:
        ruta = RAIZ / "config" / f"{nombre_o_ruta}.yaml"
    if not ruta.is_absolute():
        ruta = RAIZ / ruta

    with open(ruta, "r", encoding="utf-8") as f:
        crudo = yaml.safe_load(f)

    faltantes = [k for k in _CLAVES_OBLIGATORIAS if k not in crudo]
    if faltantes:
        raise ValueError(f"El perfil {ruta.name} no declara: {faltantes}")

    faltantes = [k for k in _ROLES_OBLIGATORIOS if k not in crudo["roles"]]
    if faltantes:
        raise ValueError(f"El perfil {ruta.name} no declara los roles: {faltantes}")

    ing = crudo["ingesta"]
    crudo["_rutas"] = {
        "raiz": RAIZ,
        "perfil": ruta,
        "raw": RAIZ / ing["ruta_raw"],
        "procesada": RAIZ / ing["ruta_procesada"],
        "artefactos": RAIZ / ing["ruta_artefactos"],
        "figuras": RAIZ / ing["ruta_figuras"],
    }
    for nombre in ("artefactos", "figuras"):
        crudo["_rutas"][nombre].mkdir(parents=True, exist_ok=True)
    crudo["_rutas"]["procesada"].parent.mkdir(parents=True, exist_ok=True)

    return Config(crudo)


def cargar_perfil_modulo(cfg: Config):
    """Importa el modulo que sabe construir la tabla analitica de este dataset."""
    import sys

    src = str(RAIZ / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    return importlib.import_module(cfg["dataset"]["modulo_perfil"])


def columnas_declaradas(cfg: Config) -> list[str]:
    """Todas las columnas que el perfil promete que existiran."""
    r = cfg.roles
    cols = [r["clave"], r["tiempo"]]
    if r.get("particion"):
        cols.append(r["particion"])
    for grupo in ("entidades", "categoricas", "numericas", "texto"):
        cols += list(r.get(grupo) or [])
    if r.get("canasta"):
        cols.append(r["canasta"]["items"])
    return list(dict.fromkeys(cols))

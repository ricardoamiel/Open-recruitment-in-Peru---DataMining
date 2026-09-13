"""Exportacion de artefactos ligeros para el reporte web.

La arquitectura del proyecto es calcular una vez y explorar muchas: Spark
produce agregados pequenos y los deja en disco como CSV y JSON, y la pagina del
reporte los lee sin volver a invocar Spark. Cada exportacion queda anotada en
artifacts/manifiesto.json con su descripcion y la parte del proyecto que la
consume, para que el reporte final se arme sin adivinar de donde salio cada cosa.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

_DIR = Path("artifacts")
_MANIFIESTO: dict[str, dict] = {}


def configurar(directorio) -> None:
    global _DIR, _MANIFIESTO
    _DIR = Path(directorio)
    _DIR.mkdir(parents=True, exist_ok=True)
    ruta = _DIR / "manifiesto.json"
    if ruta.exists():
        _MANIFIESTO = json.loads(ruta.read_text(encoding="utf-8"))


def exportar(datos: pd.DataFrame, nombre: str, descripcion: str,
             parte: str = "I", formatos: tuple[str, ...] = ("csv", "json")) -> dict:
    """Guarda una tabla pequena y la registra en el manifiesto."""
    salidas = {}
    if "csv" in formatos:
        ruta = _DIR / f"{nombre}.csv"
        datos.to_csv(ruta, index=False, encoding="utf-8")
        salidas["csv"] = ruta.name
    if "json" in formatos:
        ruta = _DIR / f"{nombre}.json"
        datos.to_json(ruta, orient="records", force_ascii=False, indent=1, date_format="iso")
        salidas["json"] = ruta.name

    entrada = {
        "nombre": nombre,
        "descripcion": " ".join(descripcion.split()),
        "parte": parte,
        "filas": int(len(datos)),
        "columnas": list(datos.columns.astype(str)),
        "archivos": salidas,
        "generado": datetime.now().isoformat(timespec="seconds"),
    }
    _MANIFIESTO[nombre] = entrada
    _escribir_manifiesto()
    return entrada


def exportar_parquet(df, ruta, particion: str | None = None, modo: str = "overwrite") -> str:
    """Persiste la tabla analitica en parquet, particionada si corresponde."""
    escritor = df.write.mode(modo)
    if particion:
        escritor = escritor.partitionBy(particion)
    escritor.parquet(str(ruta))
    return str(ruta)


def _escribir_manifiesto() -> None:
    (_DIR / "manifiesto.json").write_text(
        json.dumps(_MANIFIESTO, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def manifiesto() -> pd.DataFrame:
    if not _MANIFIESTO:
        return pd.DataFrame(columns=["nombre", "parte", "filas", "descripcion"])
    d = pd.DataFrame(_MANIFIESTO.values())
    return d[["nombre", "parte", "filas", "descripcion"]]

"""Ejecuta un notebook celda por celda y registra en que celda falla.

nbconvert solo informa "Kernel died" sin decir donde. Este runner usa el mismo
motor (nbclient) pero anota cada celda con su tiempo antes de ejecutarla, asi
que si el kernel muere la ultima linea del log es la celda culpable. Solo
guarda el notebook si todas las celdas terminan bien.

    C:/Users/LENOVO/anaconda3/envs/spark310/python.exe notebooks/scripts/ejecutar_notebook.py notebooks/1_kdd_eda.ipynb

El log queda en notebooks/scripts/logs/ejecutar_<notebook>.log.
"""

import os, sys, time
from pathlib import Path

import nbformat
from jupyter_client.kernelspec import KernelSpecManager
from nbclient import NotebookClient

ruta = Path(sys.argv[1]).resolve()
kernel = sys.argv[2] if len(sys.argv) > 2 else "spark310"

# Lanzar el python de un env de conda sin activarlo deja fuera del PATH sus
# DLL nativas (Library\bin), y el kernel puede caer al dibujar o al cargar
# extensiones compiladas. Se antepone lo que haria `conda activate`.
entorno = Path(KernelSpecManager().get_kernel_spec(kernel).argv[0]).parent
os.environ["PATH"] = os.pathsep.join(
    [str(entorno / d) for d in ("", "Library/mingw-w64/bin", "Library/usr/bin",
                                "Library/bin", "Scripts", "bin")]
    + [os.environ.get("PATH", "")])
os.environ["CONDA_PREFIX"] = str(entorno)
LOG = Path(__file__).resolve().parent / "logs" / f"ejecutar_{ruta.stem}.log"
LOG.parent.mkdir(exist_ok=True)
log = open(LOG, "w", encoding="utf-8", buffering=1)


def anotar(msg):
    print(msg); log.write(msg + "\n")


nb = nbformat.read(ruta, as_version=4)
cliente = NotebookClient(nb, kernel_name=kernel, timeout=3600,
                         resources={"metadata": {"path": str(ruta.parent)}})
anotar(f"{ruta.name} con kernel {kernel}, {len(nb.cells)} celdas")
with cliente.setup_kernel():
    for i, celda in enumerate(nb.cells):
        if celda.cell_type != "code":
            continue
        primera = celda.source.strip().splitlines()[0][:70] if celda.source.strip() else ""
        anotar(f"[{i:>3}] inicio  {time.strftime('%H:%M:%S')}  {primera}")
        t0 = time.perf_counter()
        try:
            cliente.execute_cell(celda, i)
        except Exception as e:
            anotar(f"[{i:>3}] FALLA   {type(e).__name__}: {str(e)[-1500:]}")
            sys.exit(1)
        anotar(f"[{i:>3}] ok      {time.perf_counter() - t0:.1f} s")

nbformat.write(nb, ruta)
anotar(f"guardado {ruta.name}")

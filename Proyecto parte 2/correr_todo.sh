#!/usr/bin/env bash
# Reproduce las partes I a III del Proyecto Integrador 2 desde cero.
#
# Spark corre en modo local dentro del proceso del notebook, asi que no hay
# servicios que levantar: basta el entorno de conda y Java en el PATH. La
# sesion se abre con 2 GB y 3 hilos para poder convivir con otros trabajos.
#
# Uso:  bash correr_todo.sh
set -euo pipefail

ENTORNO="${ENTORNO:-spark310}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$RAIZ"

PY="$(conda run -n "$ENTORNO" which python 2>/dev/null || true)"
if [ -z "$PY" ]; then
  echo "No se encontro el entorno $ENTORNO. Crearlo con:"
  echo "  conda create -n $ENTORNO python=3.10 && conda activate $ENTORNO"
  echo "  pip install -r requirements.txt"
  exit 1
fi
# El kernel de Jupyter se lanza como "python" a secas, asi que el entorno
# tiene que ir primero en el PATH o el notebook arranca con otro interprete.
export PATH="$(dirname "$PY"):$PATH"
echo "interprete: $PY"
"$PY" -c "import pyspark, sys; print('pyspark', pyspark.__version__, 'sobre', sys.version.split()[0])"
java -version 2>&1 | head -1

# La base limpia del proyecto 1 es la entrada. Si no existe, se genera con su
# notebook 1, que ademas descarga los CSV crudos.
if [ ! -d "../Proyecto parte 1/data/processed/tabla_analitica.parquet" ]; then
  echo "=== falta la base del proyecto 1, se genera ==="
  (cd "../Proyecto parte 1" && jupyter nbconvert --to notebook --execute --inplace \
     --ExecutePreprocessor.timeout=3600 notebooks/1_kdd_eda.ipynb)
fi

# El orden importa: el notebook 1 escribe en data/processed la base
# relacional que leen el 2 y el 3.
for N in 1_base_relacional 2_clustering_anomalias 3_recomendacion; do
  echo "=== $N ==="
  jupyter nbconvert --to notebook --execute --inplace \
    --ExecutePreprocessor.timeout=7200 \
    --ExecutePreprocessor.kernel_name=python3 "notebooks/$N.ipynb"
done

"$PY" _build/verificar.py
"$PY" _build/auditar_estilo.py
echo "listo"

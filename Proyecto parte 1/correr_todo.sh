#!/usr/bin/env bash
# Reproduce el proyecto completo desde cero.
#
# No hace falta levantar ningun servicio: Spark corre en modo local dentro del
# mismo proceso de Python que ejecuta el notebook, asi que el unico requisito es
# el entorno de conda y una maquina virtual de Java en el PATH.
#
# Uso:  bash correr_todo.sh
set -euo pipefail

ENTORNO="${ENTORNO:-spark310}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$RAIZ"

# El interprete del entorno se usa de forma explicita en lugar de activar conda,
# porque conda activate no funciona en un script no interactivo sin inicializar
# el shell, y porque asi queda registrado cual fue el interprete de la corrida.
PY="$(conda run -n "$ENTORNO" which python 2>/dev/null || true)"
if [ -z "$PY" ]; then
  echo "No se encontro el entorno $ENTORNO. Crearlo con:"
  echo "  conda create -n $ENTORNO python=3.10 && conda activate $ENTORNO"
  echo "  pip install -r requirements.txt"
  exit 1
fi

echo "interprete: $PY"
"$PY" -c "import pyspark, sys; print('pyspark', pyspark.__version__, 'sobre', sys.version.split()[0])"
java -version 2>&1 | head -1

# El orden no es negociable: el notebook 1 produce el Parquet del que dependen
# los demas, y el 6 necesita los agregados que exportan los cinco anteriores.
for N in 1_kdd_eda 2_similitud_lsh 3_ann_ivf_hnsw 4_flujos 5_reglas_asociacion 6_reporte_interactivo; do
  echo "=== $N ==="
  "$PY" -m jupyter nbconvert --to notebook --execute --inplace \
    --ExecutePreprocessor.timeout=3600 \
    --ExecutePreprocessor.kernel_name=python3 "notebooks/$N.ipynb"
done

#echo "=== revisiones ==="
#"$PY" _build/verificar.py
#"$PY" _build/auditar_estilo.py
echo "listo. El reporte quedo en reporte/index.html y docs/index.html"

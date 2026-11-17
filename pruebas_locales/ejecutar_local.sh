#!/usr/bin/env bash
# Prueba TODO el procesamiento sin AWS, con datos sintéticos en los mismos formatos.
# Requisitos: Java 11+ y  pip install pyspark==3.5.3 pyarrow pandas matplotlib duckdb streamlit
set -euo pipefail
cd "$(dirname "$0")/.."
DL=pruebas_locales/datalake
export PYSPARK_PYTHON=python3
SPARK="spark-submit --master local[4] --conf spark.ui.enabled=false"

echo "1) RAW sintético";              python3 pruebas_locales/generar_datos_sinteticos.py --destino $DL/raw
echo "2) Punto 4: raw -> trusted";    $SPARK 04-preparacion/glue_raw_a_trusted.py --RAW $DL/raw --TRUSTED $DL/trusted 2>/dev/null | grep raw_a_trusted
echo "3) Punto 6: SparkSQL";          $SPARK 06-consultas-sql/sparksql_consultas.py --trusted $DL/trusted 2>/dev/null | head -40
echo "4) Punto 7: PySpark -> refined"; $SPARK 07-pyspark/analitica_pyspark.py --TRUSTED $DL/trusted --REFINED $DL/refined 2>/dev/null | tail -3
echo "5) Punto 8: gráficas";           python3 08-visualizacion/matplotlib/graficas.py --refined $DL/refined --salida pruebas_locales/salida
echo
echo "Para la app:  python3 pruebas_locales/api_local.py &"
echo "              API_URL=http://localhost:8000 streamlit run 08-visualizacion/streamlit/app.py"

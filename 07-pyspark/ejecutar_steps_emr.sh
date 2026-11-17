#!/usr/bin/env bash
# Envía al EMR, como STEPS (sin entrar por SSH), todo el trabajo de Hive y Spark:
#   1. Hive DDL (punto 5)          2. Consultas Hive (punto 6)
#   3. SparkSQL (punto 6)          4. Analítica PySpark -> refined (punto 7)
# Uso:  source config.env && export CLUSTER_ID=j-XXXX && bash 07-pyspark/ejecutar_steps_emr.sh
set -euo pipefail
: "${CLUSTER_ID:?export CLUSTER_ID=j-XXXXXXXX (lo imprimió 02_crear_emr.sh)}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"

aws s3 cp "$RAIZ/05-catalogacion/hive_ddl.sql"              "$SCRIPTS/"
aws s3 cp "$RAIZ/06-consultas-sql/hive_sparksql_consultas.sql" "$SCRIPTS/"
aws s3 cp "$RAIZ/06-consultas-sql/sparksql_consultas.py"    "$SCRIPTS/"
aws s3 cp "$RAIZ/07-pyspark/analitica_pyspark.py"           "$SCRIPTS/"

STEPS=$(aws emr add-steps --cluster-id "$CLUSTER_ID" --query 'StepIds' --output text --steps \
  "Type=HIVE,Name=P5-hive-ddl,ActionOnFailure=CONTINUE,Args=[-f,$SCRIPTS/hive_ddl.sql,-d,BUCKET=$BUCKET]" \
  "Type=HIVE,Name=P6-hive-consultas,ActionOnFailure=CONTINUE,Args=[-f,$SCRIPTS/hive_sparksql_consultas.sql]" \
  "Type=Spark,Name=P6-sparksql,ActionOnFailure=CONTINUE,Args=[--deploy-mode,client,$SCRIPTS/sparksql_consultas.py,--catalogo,--sql,$SCRIPTS/hive_sparksql_consultas.sql]" \
  "Type=Spark,Name=P7-analitica-pyspark,ActionOnFailure=CONTINUE,Args=[--deploy-mode,client,$SCRIPTS/analitica_pyspark.py,--TRUSTED,$TRUSTED,--REFINED,$REFINED]")
echo "Steps enviados: $STEPS"

for s in $STEPS; do
  aws emr wait step-complete --cluster-id "$CLUSTER_ID" --step-id "$s" 2>/dev/null || true
  aws emr describe-step --cluster-id "$CLUSTER_ID" --step-id "$s" \
    --query 'Step.[Name,Status.State]' --output text
done
echo "Salida de cada step (stdout): s3://$BUCKET/logs/emr/$CLUSTER_ID/steps/<step-id>/stdout.gz"
echo "Luego catalogue refined:  bash 05-catalogacion/01_crawlers_glue.sh --refined"

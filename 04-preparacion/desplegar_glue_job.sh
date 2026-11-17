#!/usr/bin/env bash
# Sube el script a S3, crea (o actualiza) el Glue Job y lo ejecuta una vez.
set -euo pipefail
: "${GLUE_JOB:?Haga primero: source config.env}"
DIR="$(cd "$(dirname "$0")" && pwd)"

aws s3 cp "$DIR/glue_raw_a_trusted.py" "$SCRIPTS/glue_raw_a_trusted.py"

JOB_DEF=$(cat <<EOF
{
  "Role": "$LAB_ROLE_ARN",
  "Command": {"Name": "glueetl", "ScriptLocation": "$SCRIPTS/glue_raw_a_trusted.py", "PythonVersion": "3"},
  "DefaultArguments": {
    "--RAW": "$RAW",
    "--TRUSTED": "$TRUSTED",
    "--job-language": "python",
    "--enable-continuous-cloudwatch-log": "true",
    "--enable-metrics": "true",
    "--TempDir": "s3://$BUCKET/tmp/glue/"
  },
  "GlueVersion": "4.0",
  "WorkerType": "G.1X",
  "NumberOfWorkers": 2,
  "Timeout": 30,
  "MaxRetries": 0
}
EOF
)

if aws glue get-job --job-name "$GLUE_JOB" >/dev/null 2>&1; then
  aws glue update-job --job-name "$GLUE_JOB" --job-update "$JOB_DEF" >/dev/null
  echo "Job $GLUE_JOB actualizado"
else
  aws glue create-job --name "$GLUE_JOB" --cli-input-json "$JOB_DEF" >/dev/null
  echo "Job $GLUE_JOB creado"
fi

RUN_ID=$(aws glue start-job-run --job-name "$GLUE_JOB" --query JobRunId --output text)
echo "Ejecutando $RUN_ID (2-4 min)..."
while true; do
  ESTADO=$(aws glue get-job-run --job-name "$GLUE_JOB" --run-id "$RUN_ID" --query JobRun.JobRunState --output text)
  echo "  $ESTADO"
  [[ "$ESTADO" =~ ^(SUCCEEDED|FAILED|STOPPED|TIMEOUT|ERROR)$ ]] && break
  sleep 20
done
aws s3 ls "$TRUSTED/" --recursive | head -20

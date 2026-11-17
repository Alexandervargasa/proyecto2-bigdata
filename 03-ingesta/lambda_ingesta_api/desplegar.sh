#!/usr/bin/env bash
# Despliega la Lambda ingesta_api_clima y la programa con EventBridge (diario).
# 10:30 UTC = 05:30 Colombia (después del snapshot de MariaDB de las 05:00).
set -euo pipefail
: "${BUCKET:?Haga primero: source config.env}"
FN="ingesta_api_clima"
DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$DIR" && rm -f /tmp/$FN.zip && zip -q /tmp/$FN.zip lambda_function.py
ENV="Variables={BUCKET=$BUCKET,OPENMETEO_URL=$OPENMETEO_URL,ONI_URL=$ONI_URL,VENTANA_DIAS=10,DIAS_RETRASO=6}"

if aws lambda get-function --function-name "$FN" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FN" --zip-file fileb:///tmp/$FN.zip >/dev/null
  aws lambda wait function-updated --function-name "$FN"
  aws lambda update-function-configuration --function-name "$FN" --environment "$ENV" --timeout 900 >/dev/null
else
  aws lambda create-function --function-name "$FN" --runtime python3.12 \
    --handler lambda_function.lambda_handler --role "$LAB_ROLE_ARN" \
    --zip-file fileb:///tmp/$FN.zip --timeout 900 --memory-size 256 \
    --environment "$ENV" >/dev/null
fi
aws lambda wait function-active --function-name "$FN"

# Regla programada de EventBridge
RULE="ingesta-api-clima-diaria"
RULE_ARN=$(aws events put-rule --name "$RULE" --schedule-expression "cron(30 10 * * ? *)" \
            --query RuleArn --output text)
FN_ARN=$(aws lambda get-function --function-name "$FN" --query Configuration.FunctionArn --output text)
aws lambda add-permission --function-name "$FN" --statement-id eventbridge-diario \
  --action lambda:InvokeFunction --principal events.amazonaws.com --source-arn "$RULE_ARN" \
  >/dev/null 2>&1 || true
aws events put-targets --rule "$RULE" --targets "Id=1,Arn=$FN_ARN" >/dev/null
echo "Lambda $FN desplegada y programada ($RULE)."

echo "Carga inicial (backfill $FECHA_INICIO_API -> hoy): tarda 1-5 minutos (máx. 15), no escriba nada..."
# --cli-read-timeout: sin esto la CLI deja de esperar a los 60 s y REINTENTA (invoca varias veces).
# --max-attempts 1: si algo falla, no reintentar la invocación.
AWS_MAX_ATTEMPTS=1 aws lambda invoke --function-name "$FN" --cli-binary-format raw-in-base64-out \
  --cli-read-timeout 920 --payload "{\"inicio\": \"$FECHA_INICIO_API\"}" /tmp/salida_$FN.json >/dev/null
cat /tmp/salida_$FN.json; echo

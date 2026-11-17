#!/usr/bin/env bash
# Despliega la Lambda api_clima y la expone con API Gateway (HTTP API).
# Requiere: tablas en clima_refined (punto 7 + crawler refined).
set -euo pipefail
: "${BUCKET:?Haga primero: source config.env}"
FN="api_clima"
API_NAME="clima-api"
DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$DIR" && rm -f /tmp/$FN.zip && zip -q /tmp/$FN.zip lambda_function.py
ENV="Variables={ATHENA_OUTPUT=$ATHENA_OUTPUT,DB_REFINED=$GLUE_DB_REFINED,DB_TRUSTED=$GLUE_DB_TRUSTED}"

if aws lambda get-function --function-name "$FN" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FN" --zip-file fileb:///tmp/$FN.zip >/dev/null
  aws lambda wait function-updated --function-name "$FN"
  aws lambda update-function-configuration --function-name "$FN" --environment "$ENV" >/dev/null
else
  aws lambda create-function --function-name "$FN" --runtime python3.12 \
    --handler lambda_function.lambda_handler --role "$LAB_ROLE_ARN" \
    --zip-file fileb:///tmp/$FN.zip --timeout 29 --memory-size 256 --environment "$ENV" >/dev/null
fi
aws lambda wait function-active --function-name "$FN"
FN_ARN=$(aws lambda get-function --function-name "$FN" --query Configuration.FunctionArn --output text)

# HTTP API "quick create": ruta $default -> Lambda, stage $default con auto-deploy
API_ID=$(aws apigatewayv2 get-apis --query "Items[?Name=='$API_NAME'].ApiId | [0]" --output text)
if [[ "$API_ID" == "None" || -z "$API_ID" ]]; then
  API_ID=$(aws apigatewayv2 create-api --name "$API_NAME" --protocol-type HTTP --target "$FN_ARN" \
            --cors-configuration AllowOrigins='*',AllowMethods=GET --query ApiId --output text)
fi
aws lambda add-permission --function-name "$FN" --statement-id apigw-invoke \
  --action lambda:InvokeFunction --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$AWS_REGION:$ACCOUNT_ID:$API_ID/*" >/dev/null 2>&1 || true

URL=$(aws apigatewayv2 get-api --api-id "$API_ID" --query ApiEndpoint --output text)
echo "API publicada: $URL"
echo "export API_URL=\"$URL\"   # agréguelo a config.env (lo usa Streamlit)"
echo
echo "Pruebas:"
echo "  curl $URL/preguntas"
echo "  curl $URL/preguntas/1"
echo "  curl \"$URL/clima-mensual?ciudad=05001&desde=2024-01&hasta=2025-12\""

#!/usr/bin/env bash
# Crea el bucket del datalake con sus zonas raw / trusted / refined.
set -euo pipefail
: "${BUCKET:?Haga primero: source config.env}"

if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  aws s3api create-bucket --bucket "$BUCKET" --region "$AWS_REGION"   # us-east-1 no lleva LocationConstraint
fi
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

for z in raw trusted refined scripts athena-results; do
  aws s3api put-object --bucket "$BUCKET" --key "$z/" >/dev/null
done
aws s3 ls "s3://$BUCKET/"

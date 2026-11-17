#!/usr/bin/env bash
# Ingesta automática Fuente 2 (archivos del EC2) -> S3 raw.
# 'aws s3 sync' sube solo archivos nuevos o modificados (incremental), y
# conserva la estructura anio=AAAA/ para que el crawler la vea como partición.
set -euo pipefail
: "${RAW:?Falta config.env}"
ORIGEN="${ORIGEN_ARCHIVOS:-/opt/datos/estaciones}"
DESTINO="$RAW/archivos_ec2/estaciones/"

echo "$(date '+%F %T') sync $ORIGEN -> $DESTINO"
aws s3 sync "$ORIGEN" "$DESTINO" --exclude "*" --include "*.csv" --only-show-errors
echo "$(date '+%F %T') archivos en S3: $(aws s3 ls "$DESTINO" --recursive | wc -l)"

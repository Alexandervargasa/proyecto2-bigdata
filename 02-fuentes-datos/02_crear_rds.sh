#!/usr/bin/env bash
# Crea el RDS MariaDB (db.t3.micro, 20 GB, sin acceso público).
# Tarda ~10 minutos. Al final imprime el endpoint: cópielo en DB_HOST de config.env
set -euo pipefail
: "${DB_INSTANCE_ID:?Haga primero: source config.env}"

SG_RDS=$(aws ec2 describe-security-groups --filters Name=group-name,Values="$SG_RDS_NAME" \
          --query 'SecurityGroups[0].GroupId' --output text)
[[ "$SG_RDS" == sg-* ]] || { echo "ERROR: no existe el security group $SG_RDS_NAME. Ejecute antes 01_crear_red.sh" >&2; exit 1; }

if ! aws rds describe-db-instances --db-instance-identifier "$DB_INSTANCE_ID" >/dev/null 2>&1; then
  aws rds create-db-instance \
    --db-instance-identifier "$DB_INSTANCE_ID" \
    --engine mariadb \
    --db-instance-class db.t3.micro \
    --allocated-storage 20 \
    --master-username "$DB_USER" \
    --master-user-password "$DB_PASSWORD" \
    --vpc-security-group-ids "$SG_RDS" \
    --no-publicly-accessible \
    --backup-retention-period 0 \
    --no-multi-az \
    --tags Key=proyecto,Value=clima-bigdata >/dev/null
  echo "Creando RDS $DB_INSTANCE_ID ... (espere ~10 min)"
fi

aws rds wait db-instance-available --db-instance-identifier "$DB_INSTANCE_ID"
ENDPOINT=$(aws rds describe-db-instances --db-instance-identifier "$DB_INSTANCE_ID" \
            --query 'DBInstances[0].Endpoint.Address' --output text)
echo "Endpoint RDS: $ENDPOINT"
echo ">>> Ponga en config.env:  export DB_HOST=\"$ENDPOINT\""

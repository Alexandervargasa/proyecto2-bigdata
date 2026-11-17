#!/usr/bin/env bash
# Crea los security groups en la VPC por defecto:
#   sg-clima-ec2 : SSH (22) y Streamlit (8501) desde Internet
#   sg-clima-rds : MariaDB (3306) SOLO desde sg-clima-ec2
# Uso: (desde la raíz del repo, en CloudShell o su PC con credenciales del Lab)
#   source config.env && bash 02-fuentes-datos/01_crear_red.sh
set -euo pipefail
: "${SG_EC2_NAME:?Haga primero: source config.env}"

VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true \
          --query 'Vpcs[0].VpcId' --output text)
echo "VPC por defecto: $VPC_ID"

crear_sg () {  # nombre descripción
  local id
  id=$(aws ec2 describe-security-groups \
        --filters Name=group-name,Values="$1" Name=vpc-id,Values="$VPC_ID" \
        --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)
  if [[ -z "$id" || "$id" == "None" ]]; then
    id=$(aws ec2 create-security-group --group-name "$1" --description "$2" \
          --vpc-id "$VPC_ID" --query GroupId --output text)
  fi
  echo "$id"
}

SG_EC2=$(crear_sg "$SG_EC2_NAME" "EC2 fuentes clima: SSH y Streamlit")
SG_RDS=$(crear_sg "$SG_RDS_NAME" "RDS MariaDB clima: 3306 desde EC2")

# '|| true' para que el script se pueda re-ejecutar sin fallar por reglas duplicadas
aws ec2 authorize-security-group-ingress --group-id "$SG_EC2" --protocol tcp --port 22   --cidr 0.0.0.0/0 2>/dev/null || true
aws ec2 authorize-security-group-ingress --group-id "$SG_EC2" --protocol tcp --port 8501 --cidr 0.0.0.0/0 2>/dev/null || true
aws ec2 authorize-security-group-ingress --group-id "$SG_RDS" --protocol tcp --port 3306 --source-group "$SG_EC2" 2>/dev/null || true

echo "SG EC2: $SG_EC2"
echo "SG RDS: $SG_RDS"

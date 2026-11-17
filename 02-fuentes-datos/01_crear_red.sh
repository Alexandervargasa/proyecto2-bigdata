#!/usr/bin/env bash
# Crea los security groups en la VPC por defecto:
#   clima-ec2-sg : SSH (22) y Streamlit (8501) desde Internet
#   clima-rds-sg : MariaDB (3306) SOLO desde clima-ec2-sg
# (AWS no permite nombres que empiecen por "sg-": ese prefijo es de los IDs)
# Uso: (desde la raíz del repo, en CloudShell)
#   source config.env && bash 02-fuentes-datos/01_crear_red.sh
# Se puede ejecutar varias veces: reutiliza lo que ya exista.
set -euo pipefail
: "${SG_EC2_NAME:?Haga primero: source config.env}"
if [[ "$SG_EC2_NAME" == sg-* || "$SG_RDS_NAME" == sg-* ]]; then
  echo "ERROR: los nombres de security group no pueden empezar por 'sg-'." >&2
  echo "       En config.env use SG_EC2_NAME=\"clima-ec2-sg\" y SG_RDS_NAME=\"clima-rds-sg\", y haga source config.env" >&2
  exit 1
fi

VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true \
          --query 'Vpcs[0].VpcId' --output text)
echo "VPC por defecto: $VPC_ID"

crear_sg () {  # nombre descripción  -> imprime el ID
  local id
  id=$(aws ec2 describe-security-groups \
        --filters Name=group-name,Values="$1" Name=vpc-id,Values="$VPC_ID" \
        --query 'SecurityGroups[0].GroupId' --output text)
  if [[ -z "$id" || "$id" == "None" ]]; then
    id=$(aws ec2 create-security-group --group-name "$1" --description "$2" \
          --vpc-id "$VPC_ID" --query GroupId --output text) || return 1
  fi
  echo "$id"
}

permitir () {  # group-id  argumentos de la regla...  (ignora solo "la regla ya existe")
  local salida
  if ! salida=$(aws ec2 authorize-security-group-ingress --group-id "$@" 2>&1); then
    if [[ "$salida" == *InvalidPermission.Duplicate* ]]; then
      echo "  regla ya existía: $*"
    else
      echo "$salida" >&2; return 1
    fi
  fi
}

SG_EC2=$(crear_sg "$SG_EC2_NAME" "EC2 fuentes clima: SSH y Streamlit")
SG_RDS=$(crear_sg "$SG_RDS_NAME" "RDS MariaDB clima: 3306 desde EC2")
[[ "$SG_EC2" == sg-* && "$SG_RDS" == sg-* ]] || { echo "ERROR: no se obtuvieron los IDs de los security groups" >&2; exit 1; }

permitir "$SG_EC2" --protocol tcp --port 22   --cidr 0.0.0.0/0
permitir "$SG_EC2" --protocol tcp --port 8501 --cidr 0.0.0.0/0
permitir "$SG_RDS" --protocol tcp --port 3306 --source-group "$SG_EC2"

echo "SG EC2 ($SG_EC2_NAME): $SG_EC2"
echo "SG RDS ($SG_RDS_NAME): $SG_RDS"
aws ec2 describe-security-groups --group-ids "$SG_EC2" "$SG_RDS" \
  --query 'SecurityGroups[].[GroupName,GroupId]' --output table

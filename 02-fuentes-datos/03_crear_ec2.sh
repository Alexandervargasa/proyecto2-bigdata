#!/usr/bin/env bash
# Crea el EC2 "clima-fuentes" (Amazon Linux 2023) con LabInstanceProfile.
# Este EC2 cumple 3 papeles:
#   1) servidor de ARCHIVOS (fuente 2): /opt/datos/estaciones
#   2) ejecuta la ingesta automática (cron) de MariaDB y archivos -> S3
#   3) aloja la app Streamlit del punto 8
set -euo pipefail
: "${EC2_NAME:?Haga primero: source config.env}"

AMI=$(aws ssm get-parameter \
       --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
       --query Parameter.Value --output text)
SG_EC2=$(aws ec2 describe-security-groups --filters Name=group-name,Values="$SG_EC2_NAME" \
          --query 'SecurityGroups[0].GroupId' --output text)

# user-data: se ejecuta una sola vez, como root, al primer arranque
USER_DATA=$(cat <<EOF
#!/bin/bash
dnf install -y git mariadb105 python3-pip cronie
systemctl enable --now crond
mkdir -p /opt/datos/estaciones && chown -R ec2-user:ec2-user /opt/datos
sudo -u ec2-user git clone ${REPO_URL} /home/ec2-user/proyecto2-bigdata-clima || true
sudo -u ec2-user pip3 install --user pymysql boto3 requests streamlit pandas pyarrow altair
EOF
)

INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI" --instance-type "$EC2_TYPE" \
  --key-name "$KEY_NAME" \
  --security-group-ids "$SG_EC2" \
  --iam-instance-profile Name="$LAB_INSTANCE_PROFILE" \
  --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=20,VolumeType=gp3}' \
  --user-data "$USER_DATA" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$EC2_NAME}]" \
  --query 'Instances[0].InstanceId' --output text)

aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
DNS=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
       --query 'Reservations[0].Instances[0].PublicDnsName' --output text)
echo "EC2: $INSTANCE_ID  ->  ssh -i labsuser.pem ec2-user@$DNS"
echo "(espere 2-3 minutos a que termine el user-data antes de entrar)"

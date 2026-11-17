#!/usr/bin/env bash
# Crea el clúster EMR con Hive, Spark, JupyterHub y Livy, usando el
# Glue Data Catalog como metastore de Hive y de Spark (un solo catálogo).
# Se auto-termina tras 1 hora sin trabajo para cuidar el crédito del Lab.
set -euo pipefail
: "${EMR_NAME:?Haga primero: source config.env}"

CONF='[
 {"Classification":"hive-site","Properties":{"hive.metastore.client.factory.class":"com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory"}},
 {"Classification":"spark-hive-site","Properties":{"hive.metastore.client.factory.class":"com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory"}}
]'

CLUSTER_ID=$(aws emr create-cluster \
  --name "$EMR_NAME" \
  --release-label "$EMR_RELEASE" \
  --applications Name=Hadoop Name=Hive Name=Spark Name=Hue Name=JupyterHub Name=Livy \
  --instance-groups "InstanceGroupType=MASTER,InstanceCount=1,InstanceType=$EMR_INSTANCE_TYPE" \
                    "InstanceGroupType=CORE,InstanceCount=2,InstanceType=$EMR_INSTANCE_TYPE" \
  --service-role EMR_DefaultRole \
  --ec2-attributes "InstanceProfile=EMR_EC2_DefaultRole,KeyName=$KEY_NAME" \
  --configurations "$CONF" \
  --log-uri "s3://$BUCKET/logs/emr/" \
  --auto-termination-policy IdleTimeout=3600 \
  --query ClusterId --output text)

echo "Clúster $CLUSTER_ID creándose (8-12 min)..."
aws emr wait cluster-running --cluster-id "$CLUSTER_ID"
DNS=$(aws emr describe-cluster --cluster-id "$CLUSTER_ID" --query Cluster.MasterPublicDnsName --output text)
echo "export CLUSTER_ID=$CLUSTER_ID   # agréguelo a config.env"
echo "Master: ssh -i labsuser.pem hadoop@$DNS"
echo "Si el SSH no conecta: EC2 > Security Groups > ElasticMapReduce-master > Inbound: agregar SSH 22."

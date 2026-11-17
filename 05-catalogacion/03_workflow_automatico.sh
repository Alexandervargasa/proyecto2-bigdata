#!/usr/bin/env bash
# Orquestación diaria con un Glue Workflow (puntos 3 -> 4 -> 5 sin intervención):
#   06:00 COT  crawlers raw  ->  (ambos OK)  job raw_a_trusted  ->  (OK)  crawler trusted
# Requiere: job del punto 4 y crawlers de 01_crawlers_glue.sh ya creados.
set -euo pipefail
: "${GLUE_JOB:?Haga primero: source config.env}"
WF="clima_workflow_diario"

aws glue create-workflow --name "$WF" --description "Ingesta raw -> trusted -> catálogo" 2>/dev/null || true

borrar () { aws glue delete-trigger --name "$1" >/dev/null 2>&1 || true; }
borrar t1_programado; borrar t2_job; borrar t3_crawler_trusted

aws glue create-trigger --workflow-name "$WF" --name t1_programado --type SCHEDULED \
  --schedule "cron(0 11 * * ? *)" --start-on-creation \
  --actions CrawlerName=crawler_clima_raw CrawlerName=crawler_clima_raw_archivos >/dev/null

aws glue create-trigger --workflow-name "$WF" --name t2_job --type CONDITIONAL --start-on-creation \
  --predicate '{"Logical":"AND","Conditions":[
     {"LogicalOperator":"EQUALS","CrawlerName":"crawler_clima_raw","CrawlState":"SUCCEEDED"},
     {"LogicalOperator":"EQUALS","CrawlerName":"crawler_clima_raw_archivos","CrawlState":"SUCCEEDED"}]}' \
  --actions JobName="$GLUE_JOB" >/dev/null

aws glue create-trigger --workflow-name "$WF" --name t3_crawler_trusted --type CONDITIONAL --start-on-creation \
  --predicate "{\"Conditions\":[{\"LogicalOperator\":\"EQUALS\",\"JobName\":\"$GLUE_JOB\",\"State\":\"SUCCEEDED\"}]}" \
  --actions CrawlerName=crawler_clima_trusted >/dev/null

echo "Workflow $WF listo. Para probarlo ya:  aws glue start-workflow-run --name $WF"
echo "Véalo en: Glue > Workflows (orchestration) > $WF > pestaña Graph"

#!/usr/bin/env bash
# Catálogo con AWS Glue: bases de datos, clasificador CSV ';' y crawlers.
#   clima_raw      <- crawler_clima_raw (MariaDB CSV + API JSON)
#                     crawler_clima_raw_archivos (CSV legado ';')
#   clima_trusted  <- crawler_clima_trusted (Parquet)
#   clima_refined  <- crawler_clima_refined (Parquet, se corre después del punto 7)
set -euo pipefail
: "${BUCKET:?Haga primero: source config.env}"

for db in "$GLUE_DB_RAW" "$GLUE_DB_TRUSTED" "$GLUE_DB_REFINED"; do
  aws glue create-database --database-input "Name=$db,Description=Datalake clima Colombia" 2>/dev/null \
    && echo "BD $db creada" || echo "BD $db ya existe"
done

# Clasificador para el CSV legado (separador ';' con encabezado)
aws glue create-classifier --csv-classifier \
  '{"Name":"csv_punto_y_coma","Delimiter":";","QuoteSymbol":"\"","ContainsHeader":"PRESENT"}' 2>/dev/null || true

crear_crawler () {  # nombre bd targets_json [clasificador] [configuracion]
  local args=(--name "$1" --role "$LAB_ROLE_ARN" --database-name "$2" --targets "$3"
              --schema-change-policy UpdateBehavior=UPDATE_IN_DATABASE,DeleteBehavior=LOG
              --recrawl-policy RecrawlBehavior=CRAWL_EVERYTHING)
  [[ -n "${4:-}" ]] && args+=(--classifiers "$4")
  [[ -n "${5:-}" ]] && args+=(--configuration "$5")
  if aws glue get-crawler --name "$1" >/dev/null 2>&1; then
    aws glue update-crawler "${args[@]}" >/dev/null; echo "crawler $1 actualizado"
  else
    aws glue create-crawler "${args[@]}" >/dev/null; echo "crawler $1 creado"
  fi
}

# Un target por carpeta-tabla: el nombre de la tabla será el de la carpeta
crear_crawler crawler_clima_raw "$GLUE_DB_RAW" "{\"S3Targets\":[
  {\"Path\":\"$RAW/mariadb/departamento/\"},
  {\"Path\":\"$RAW/mariadb/ciudad/\"},
  {\"Path\":\"$RAW/api_openmeteo/\"}]}"

crear_crawler crawler_clima_raw_archivos "$GLUE_DB_RAW" \
  "{\"S3Targets\":[{\"Path\":\"$RAW/archivos_ec2/estaciones/\"}]}" csv_punto_y_coma

crear_crawler crawler_clima_trusted "$GLUE_DB_TRUSTED" "{\"S3Targets\":[
  {\"Path\":\"$TRUSTED/dim_ciudad/\"},
  {\"Path\":\"$TRUSTED/clima_diario/\"},
  {\"Path\":\"$TRUSTED/oni_mensual/\"}]}"

# refined: una tabla por carpeta de primer nivel (s3://bucket=1 / refined=2 / tabla=3)
crear_crawler crawler_clima_refined "$GLUE_DB_REFINED" \
  "{\"S3Targets\":[{\"Path\":\"$REFINED/\",\"Exclusions\":[\"**_SUCCESS\",\"**.csv\"]}]}" "" \
  '{"Version":1.0,"Grouping":{"TableLevelConfiguration":3}}'

correr () {
  aws glue start-crawler --name "$1" 2>/dev/null || true
  echo -n "esperando $1 "
  until [[ "$(aws glue get-crawler --name "$1" --query Crawler.State --output text)" == "READY" ]]; do
    echo -n "."; sleep 15; done
  echo " $(aws glue get-crawler --name "$1" --query Crawler.LastCrawl.Status --output text)"
}

if [[ "${1:-}" == "--refined" ]]; then
  correr crawler_clima_refined
  aws glue get-tables --database-name "$GLUE_DB_REFINED" --query 'TableList[].Name' --output table
else
  correr crawler_clima_raw
  correr crawler_clima_raw_archivos
  correr crawler_clima_trusted
  for db in "$GLUE_DB_RAW" "$GLUE_DB_TRUSTED"; do
    aws glue get-tables --database-name "$db" --query 'TableList[].[DatabaseName,Name,StorageDescriptor.Location]' --output table
  done
fi

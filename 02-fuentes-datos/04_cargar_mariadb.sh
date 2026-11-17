#!/usr/bin/env bash
# Ejecutar DENTRO del EC2 (el RDS solo acepta conexiones desde clima-ec2-sg).
# Crea el esquema y carga los datos maestros.
set -euo pipefail
: "${DB_HOST:?Ponga DB_HOST en config.env y haga: source config.env}"
DIR="$(cd "$(dirname "$0")" && pwd)/mariadb"

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD" < "$DIR/schema.sql"
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD" < "$DIR/seed.sql"

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -e "
  SELECT COUNT(*) AS departamentos FROM departamento;
  SELECT COUNT(*) AS ciudades FROM ciudad;
  SELECT c.ciudad, d.departamento, c.altitud_m, c.region_natural
  FROM ciudad c JOIN departamento d USING (cod_depto) ORDER BY c.altitud_m DESC LIMIT 5;"

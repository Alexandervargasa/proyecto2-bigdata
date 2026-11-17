#!/usr/bin/env bash
# Ejecutar DENTRO del EC2 (el RDS solo acepta conexiones desde clima-ec2-sg).
# Crea el esquema y carga los datos maestros.
#
# RDS MariaDB exige conexiones cifradas (require_secure_transport=ON), así que
# nos conectamos con TLS verificando el certificado de AWS (bundle oficial de RDS).
set -euo pipefail
: "${DB_HOST:?Ponga DB_HOST en config.env y haga: source config.env}"
DIR="$(cd "$(dirname "$0")" && pwd)/mariadb"
CA="${DB_SSL_CA:-$HOME/rds-global-bundle.pem}"

if [[ ! -s "$CA" ]]; then
  echo "Descargando certificado de RDS en $CA"
  curl -sSf -o "$CA" https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
fi

sql () { mysql --default-character-set=utf8mb4 --ssl-ca="$CA" --ssl-verify-server-cert -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -p"$DB_PASSWORD" "$@"; }

sql < "$DIR/schema.sql"
sql < "$DIR/seed.sql"

sql "$DB_NAME" -e "
  SHOW SESSION STATUS LIKE 'Ssl_version';
  SELECT COUNT(*) AS departamentos FROM departamento;
  SELECT COUNT(*) AS ciudades FROM ciudad;
  SELECT c.ciudad, d.departamento, c.altitud_m, c.region_natural
  FROM ciudad c JOIN departamento d USING (cod_depto) ORDER BY c.altitud_m DESC LIMIT 5;"

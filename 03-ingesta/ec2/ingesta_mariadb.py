#!/usr/bin/env python3
"""
Ingesta automática Fuente 1 (RDS MariaDB) -> S3 raw.

Extrae completas las tablas maestras (son pequeñas: carga full snapshot) y las
deja tal cual, como CSV, en:
    s3://<bucket>/raw/mariadb/<tabla>/fecha_ingesta=AAAA-MM-DD/<tabla>.csv

Corre en el EC2 (misma VPC que el RDS, rol LabInstanceProfile -> sin llaves).
Programado con cron (ver instalar_cron.sh). Es idempotente: si corre dos veces
el mismo día, sobrescribe el snapshot de ese día.
"""
import csv
import datetime as dt
import io
import os
import sys

import boto3
import pymysql

TABLAS = ["departamento", "ciudad"]


def ca_rds():
    """Certificado de RDS: MariaDB en RDS exige TLS (require_secure_transport=ON)."""
    ca = os.path.expanduser(os.environ.get("DB_SSL_CA", "~/rds-global-bundle.pem"))
    if not os.path.isfile(ca):
        sys.exit(f"Falta el certificado {ca}. Descárguelo con:\n"
                 f"  curl -o {ca} https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem")
    return ca


def main():
    bucket = os.environ["BUCKET"]
    hoy = dt.date.today().isoformat()
    s3 = boto3.client("s3")
    con = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", "3306")), user=os.environ["DB_USER"],
                          password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                          charset="utf8mb4",
                          ssl={"ca": ca_rds()})
    with con:
        for tabla in TABLAS:
            with con.cursor() as cur:
                cur.execute(f"SELECT * FROM {tabla}")
                columnas = [c[0] for c in cur.description]
                filas = cur.fetchall()
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(columnas)
            w.writerows(filas)
            key = f"raw/mariadb/{tabla}/fecha_ingesta={hoy}/{tabla}.csv"
            s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue().encode("utf-8"),
                          ContentType="text/csv")
            print(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {tabla}: {len(filas)} filas -> s3://{bucket}/{key}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR ingesta_mariadb: {e}", file=sys.stderr)
        sys.exit(1)

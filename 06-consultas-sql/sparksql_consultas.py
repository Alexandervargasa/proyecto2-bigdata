"""
Punto 6 — Las mismas consultas de hive_sparksql_consultas.sql ejecutadas con SparkSQL.

  EMR (usa el Glue Data Catalog, base clima_hive):
      spark-submit sparksql_consultas.py --catalogo
  Directo sobre los Parquet de trusted (EMR o local):
      spark-submit sparksql_consultas.py --trusted s3://<bucket>/trusted
"""
import argparse
import os
import re

from pyspark.sql import SparkSession

p = argparse.ArgumentParser()
p.add_argument("--catalogo", action="store_true", help="usar tablas del Glue Data Catalog")
p.add_argument("--trusted", help="ruta de la zona trusted (crea vistas temporales)")
p.add_argument("--sql", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             "hive_sparksql_consultas.sql"))
a = p.parse_args()

b = SparkSession.builder.appName("clima_sparksql")
if a.catalogo:
    b = b.enableHiveSupport()
spark = b.getOrCreate()
spark.sparkContext.setLogLevel("WARN")

if a.trusted:
    t = a.trusted.rstrip("/")
    for tabla in ("dim_ciudad", "clima_diario", "oni_mensual"):
        spark.read.parquet(f"{t}/{tabla}").createOrReplaceTempView(tabla)

if a.sql.startswith("s3://"):
    texto = "\n".join(r for r in spark.sparkContext.textFile(a.sql).collect())
else:
    texto = open(a.sql, encoding="utf-8").read()

for sentencia in [s.strip() for s in texto.split(";") if s.strip()]:
    codigo = "\n".join(l for l in sentencia.splitlines() if not l.strip().startswith("--")).strip()
    if not codigo:
        continue
    if codigo.upper().startswith("USE "):
        if a.catalogo:
            spark.sql(codigo)
        continue
    titulo = re.search(r"--\s*(P\d+:.*)", sentencia)
    print("\n" + "=" * 90 + f"\n{titulo.group(1) if titulo else ''}\n" + "=" * 90)
    spark.sql(codigo).show(40, truncate=False)

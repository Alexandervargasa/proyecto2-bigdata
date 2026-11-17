#!/usr/bin/env python3
"""
Simula API Gateway + Athena en local para probar la Lambda api_clima y la app
Streamlit sin AWS. Ejecuta el handler REAL de la Lambda; solo reemplaza la
función consultar() por DuckDB leyendo los Parquet locales.

    pip install duckdb
    python3 pruebas_locales/api_local.py            # http://localhost:8000
    API_URL=http://localhost:8000 streamlit run 08-visualizacion/streamlit/app.py
"""
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import duckdb

AQUI = os.path.dirname(os.path.abspath(__file__))
DL = os.path.join(AQUI, "datalake")
sys.path.insert(0, os.path.join(AQUI, "..", "08-visualizacion", "api_lambda"))
os.environ.setdefault("ATHENA_OUTPUT", "s3://local/")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
import lambda_function as lf  # noqa: E402

con = duckdb.connect()
for esquema, zona in (("clima_refined", "refined"), ("clima_trusted", "trusted")):
    con.execute(f"CREATE SCHEMA {esquema}")
    for tabla in os.listdir(os.path.join(DL, zona)):
        ruta = os.path.join(DL, zona, tabla, "**", "*.parquet")
        con.execute(f"CREATE VIEW {esquema}.{tabla} AS SELECT * FROM read_parquet('{ruta}', hive_partitioning=true)")


def consultar_duckdb(sql, parametros=None):
    # Athena recibe los parámetros como literales SQL; aquí se sustituyen igual
    for p in parametros or []:
        sql = sql.replace("?", p, 1)
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, f)) for f in cur.fetchall()]


lf.consultar = consultar_duckdb


class Manejador(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        evento = {"rawPath": u.path, "queryStringParameters":
                  {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()} or None}
        r = lf.lambda_handler(evento, None)
        self.send_response(r["statusCode"])
        for k, v in r["headers"].items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(r["body"].encode("utf-8"))

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("API local en http://localhost:8000")
    HTTPServer(("0.0.0.0", 8000), Manejador).serve_forever()

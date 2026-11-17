#!/usr/bin/env python3
"""
Ejecuta en Athena todas las consultas de athena_consultas.sql e imprime los
resultados (evidencia rápida desde CloudShell). Las líneas comentadas se omiten.

    source config.env && python3 06-consultas-sql/ejecutar_athena.py
"""
import os
import re
import sys
import time

import boto3

ARCHIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "athena_consultas.sql")
athena = boto3.client("athena", region_name=os.environ.get("AWS_REGION", "us-east-1"))
salida = os.environ["ATHENA_OUTPUT"]


def ejecutar(sql):
    qid = athena.start_query_execution(QueryString=sql, ResultConfiguration={"OutputLocation": salida},
                                       WorkGroup="primary")["QueryExecutionId"]
    while True:
        e = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        estado = e["Status"]["State"]
        if estado in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if estado != "SUCCEEDED":
        raise RuntimeError(e["Status"].get("StateChangeReason", estado))
    filas = athena.get_query_results(QueryExecutionId=qid, MaxResults=50)["ResultSet"]["Rows"]
    datos = [[c.get("VarCharValue", "") for c in f["Data"]] for f in filas]
    escaneado = e["Statistics"]["DataScannedInBytes"] / 1024
    return datos, escaneado


texto = open(ARCHIVO, encoding="utf-8").read()
for bloque in [b.strip() for b in texto.split(";") if b.strip()]:
    titulo = re.search(r"--\s*(P\d+:.*)", bloque)
    sql = "\n".join(l for l in bloque.splitlines() if not l.strip().startswith("--")).strip()
    if not sql or not titulo:
        continue
    print("\n" + "=" * 80 + f"\n{titulo.group(1)}\n" + "=" * 80)
    try:
        datos, kb = ejecutar(sql)
        anchos = [max(len(str(f[i])) for f in datos) for i in range(len(datos[0]))]
        for f in datos:
            print("  ".join(str(v).ljust(a) for v, a in zip(f, anchos)))
        print(f"(datos escaneados: {kb:.1f} KB)")
    except Exception as ex:
        print(f"ERROR: {ex}", file=sys.stderr)

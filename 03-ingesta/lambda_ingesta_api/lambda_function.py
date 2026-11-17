"""
Lambda ingesta_api_clima: Fuente 3 (URLs en Internet) -> S3 raw.

1) Lee la lista de ciudades del último snapshot de MariaDB que ya está en
   raw/mariadb/ciudad/ (así la Lambda no necesita entrar a la VPC del RDS).
2) Pide a Open-Meteo el clima diario de cada ciudad para una ventana de fechas y
   guarda las respuestas SIN modificar en JSON Lines (una línea por ciudad):
       raw/api_openmeteo/fecha_ingesta=AAAA-MM-DD/clima_HHMMSS.jsonl
3) Descarga el índice ONI de NOAA tal cual:
       raw/api_noaa/oni/fecha_ingesta=AAAA-MM-DD/oni.ascii.txt

Ventana de fechas:
  - Ejecución programada (EventBridge, diaria): últimos VENTANA_DIAS días hasta
    hoy - DIAS_RETRASO (ERA5 publica con ~5 días de retraso). Repetir días es
    intencional: trusted se queda con la ingesta más reciente de cada día.
  - Carga inicial (backfill): invoque con {"inicio": "2025-01-01"} y opcional "fin".

Solo usa librería estándar + boto3 (incluido en el runtime): no necesita layers.
"""
import csv
import datetime as dt
import io
import json
import os
import time
import urllib.parse
import urllib.request

import boto3

s3 = boto3.client("s3")

BUCKET = os.environ["BUCKET"]
OPENMETEO_URL = os.environ.get("OPENMETEO_URL", "https://archive-api.open-meteo.com/v1/archive")
ONI_URL = os.environ.get("ONI_URL", "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt")
VENTANA_DIAS = int(os.environ.get("VENTANA_DIAS", "10"))
DIAS_RETRASO = int(os.environ.get("DIAS_RETRASO", "6"))
VARIABLES = "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,wind_speed_10m_max"


def http_get(url, intentos=4):
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "proyecto-bigdata-eafit/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:
            if i == intentos - 1:
                raise
            print(f"reintento {i + 1}: {e}")
            time.sleep(2 ** i * 3)


def ultimo_snapshot_ciudades():
    prefijo = "raw/mariadb/ciudad/"
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefijo, Delimiter="/")
    particiones = sorted(p["Prefix"] for p in resp.get("CommonPrefixes", []))
    if not particiones:
        raise RuntimeError("No hay snapshot de ciudades en raw/mariadb/ciudad/. "
                           "Ejecute primero ingesta_mariadb.py en el EC2.")
    key = particiones[-1] + "ciudad.csv"
    cuerpo = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode("utf-8")
    print(f"ciudades desde s3://{BUCKET}/{key}")
    return list(csv.DictReader(io.StringIO(cuerpo)))


def lambda_handler(event, context):
    event = event or {}
    ahora = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).replace(tzinfo=None)  # hora Colombia
    hoy = ahora.date()
    fin = dt.date.fromisoformat(event["fin"]) if event.get("fin") else hoy - dt.timedelta(days=DIAS_RETRASO)
    inicio = dt.date.fromisoformat(event["inicio"]) if event.get("inicio") else fin - dt.timedelta(days=VENTANA_DIAS - 1)

    # ---- Open-Meteo ----
    lineas, errores = [], []
    for c in ultimo_snapshot_ciudades():
        params = {"latitude": c["latitud"], "longitude": c["longitud"],
                  "start_date": inicio.isoformat(), "end_date": fin.isoformat(),
                  "daily": VARIABLES, "timezone": "America/Bogota"}
        url = f"{OPENMETEO_URL}?{urllib.parse.urlencode(params)}"
        try:
            respuesta = json.loads(http_get(url))
            lineas.append(json.dumps({
                "id_ciudad": c["id_ciudad"], "ciudad": c["ciudad"],
                "fecha_extraccion": ahora.isoformat(timespec="seconds"),
                "fecha_inicio": inicio.isoformat(), "fecha_fin": fin.isoformat(),
                "respuesta": respuesta}, ensure_ascii=False))
        except Exception as e:
            errores.append(f"{c['id_ciudad']}: {e}")
        time.sleep(0.3)

    key_clima = f"raw/api_openmeteo/fecha_ingesta={hoy}/clima_{ahora:%H%M%S}.jsonl"
    s3.put_object(Bucket=BUCKET, Key=key_clima, Body="\n".join(lineas).encode("utf-8"),
                  ContentType="application/x-ndjson")

    # ---- NOAA ONI ----
    key_oni = f"raw/api_noaa/oni/fecha_ingesta={hoy}/oni.ascii.txt"
    s3.put_object(Bucket=BUCKET, Key=key_oni, Body=http_get(ONI_URL), ContentType="text/plain")

    resultado = {"ventana": [inicio.isoformat(), fin.isoformat()], "ciudades_ok": len(lineas),
                 "errores": errores, "clima": f"s3://{BUCKET}/{key_clima}", "oni": f"s3://{BUCKET}/{key_oni}"}
    print(json.dumps(resultado, ensure_ascii=False))
    return resultado

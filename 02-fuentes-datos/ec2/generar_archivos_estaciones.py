#!/usr/bin/env python3
"""
Fuente 2 (archivos en EC2): genera el histórico diario 2022-2024 de cada ciudad
con el formato de un "sistema legado de estaciones":

    CODIGO_ESTACION;FECHA;TMAX;TMIN;TMED;PRECIP;VIENTO_MAX
    EST-05001;01/01/2022;27,4;16,1;20,9;3,2;11,5
    ...  (faltantes = -999)

Un archivo por ciudad y año:  /opt/datos/estaciones/anio=2022/EST_05001_2022.csv

Los valores vienen de Open-Meteo (reanálisis ERA5); lo "simulado" es el formato.
Las ciudades y coordenadas se leen de la fuente 1 (MariaDB). Con --csv se pueden
leer de un CSV (útil para pruebas sin base de datos).

Uso en el EC2:
    source <carpeta-del-repo>/config.env
    python3 generar_archivos_estaciones.py
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

VARIABLES = ["temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
             "precipitation_sum", "wind_speed_10m_max"]
FALTANTE = "-999"


def leer_ciudades_mariadb():
    import pymysql  # pip3 install --user pymysql
    con = pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"],
                          password=os.environ["DB_PASSWORD"],
                          database=os.environ.get("DB_NAME", "clima_maestros"),
                          cursorclass=pymysql.cursors.DictCursor, charset="utf8mb4")
    with con, con.cursor() as cur:
        cur.execute("SELECT id_ciudad, ciudad, latitud, longitud FROM ciudad ORDER BY id_ciudad")
        return cur.fetchall()


def leer_ciudades_csv(ruta):
    with open(ruta, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pedir_openmeteo(lat, lon, inicio, fin, url, intentos=5):
    params = {"latitude": lat, "longitude": lon, "start_date": inicio, "end_date": fin,
              "daily": ",".join(VARIABLES), "timezone": "America/Bogota"}
    full = f"{url}?{urllib.parse.urlencode(params)}"
    for i in range(intentos):
        try:
            with urllib.request.urlopen(full, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # 429 (límite de peticiones) o red: reintento con espera
            espera = 2 ** i * 5
            print(f"  reintento {i + 1}/{intentos} en {espera}s: {e}", file=sys.stderr)
            time.sleep(espera)
    raise RuntimeError(f"Open-Meteo no respondió para {lat},{lon}")


def formato_legado(valor):
    """Número con coma decimal; nulo -> -999."""
    if valor is None:
        return FALTANTE
    return f"{valor:.1f}".replace(".", ",")


def escribir_archivos(id_ciudad, daily, destino):
    por_anio = {}
    for i, fecha in enumerate(daily["time"]):          # fecha ISO aaaa-mm-dd
        a, m, d = fecha.split("-")
        fila = [f"EST-{id_ciudad}", f"{d}/{m}/{a}"] + \
               [formato_legado(daily[v][i]) for v in VARIABLES]
        por_anio.setdefault(a, []).append(fila)
    for anio, filas in por_anio.items():
        carpeta = os.path.join(destino, f"anio={anio}")
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, f"EST_{id_ciudad}_{anio}.csv")
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["CODIGO_ESTACION", "FECHA", "TMAX", "TMIN", "TMED", "PRECIP", "VIENTO_MAX"])
            w.writerows(filas)
        print(f"  {ruta}  ({len(filas)} filas)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--destino", default="/opt/datos/estaciones")
    p.add_argument("--inicio", default=os.environ.get("FECHA_INICIO_HISTORICO", "2022-01-01"))
    p.add_argument("--fin", default=os.environ.get("FECHA_FIN_HISTORICO", "2024-12-31"))
    p.add_argument("--csv", help="leer ciudades de un CSV en vez de MariaDB")
    p.add_argument("--url", default=os.environ.get("OPENMETEO_URL",
                                                   "https://archive-api.open-meteo.com/v1/archive"))
    a = p.parse_args()

    ciudades = leer_ciudades_csv(a.csv) if a.csv else leer_ciudades_mariadb()
    print(f"{len(ciudades)} ciudades, periodo {a.inicio} a {a.fin}")
    for c in ciudades:
        print(f"- {c['id_ciudad']} {c['ciudad']}")
        datos = pedir_openmeteo(c["latitud"], c["longitud"], a.inicio, a.fin, a.url)
        escribir_archivos(c["id_ciudad"], datos["daily"], a.destino)
        time.sleep(1)  # respetar el límite gratuito de Open-Meteo


if __name__ == "__main__":
    main()

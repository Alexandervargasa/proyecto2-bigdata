#!/usr/bin/env python3
"""
Genera una zona RAW local con EXACTAMENTE los mismos formatos que producen las
ingestas reales (CSV MariaDB, CSV legado EC2, JSONL Open-Meteo, TXT NOAA), pero
con valores sintéticos. Sirve para probar los scripts Spark sin AWS ni Internet.

    python3 pruebas_locales/generar_datos_sinteticos.py --destino pruebas_locales/datalake/raw

Los valores NO son reales: temperatura = f(altitud, latitud, mes) + ruido.
Incluye a propósito defectos para probar la preparación: -999, un valor fuera de
rango, una ciudad huérfana y días repetidos entre dos ingestas de la API.
"""
import argparse
import csv
import datetime as dt
import json
import math
import os
import random
import shutil

AQUI = os.path.dirname(os.path.abspath(__file__))
MAESTROS = os.path.join(AQUI, "..", "02-fuentes-datos", "mariadb")
random.seed(42)


def clima_sintetico(ciudad, fecha):
    alt = int(ciudad["altitud_m"])
    base = 28.5 - 0.0058 * alt + (1.5 if ciudad["region_natural"] == "Caribe" else 0)
    tmed = base + 0.8 * math.sin(2 * math.pi * (fecha.timetuple().tm_yday - 60) / 365) + random.gauss(0, 0.8)
    if fecha.year == 2024 and fecha.month <= 4:   # "El Niño"
        tmed += 1.0
    tmax = tmed + 5 + random.random() * 3
    tmin = tmed - 5 - random.random() * 2
    lluvia_mes = 1 + math.cos(2 * math.pi * (fecha.month - 4.5) / 6)  # bimodal abr/oct
    precip = max(0.0, random.expovariate(1 / (6 * lluvia_mes)) - 3)
    viento = 8 + random.random() * 15
    return [round(x, 1) for x in (tmax, tmin, tmed, precip, viento)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default=os.path.join(AQUI, "datalake", "raw"))
    raw = ap.parse_args().destino
    shutil.rmtree(raw, ignore_errors=True)

    ciudades = list(csv.DictReader(open(os.path.join(MAESTROS, "ciudades.csv"), encoding="utf-8")))
    deptos = list(csv.DictReader(open(os.path.join(MAESTROS, "departamentos.csv"), encoding="utf-8")))

    # --- MariaDB: dos snapshots (debe usarse el último) ---
    for fi, extra in (("2026-11-16", {}), ("2026-11-17", {})):
        for tabla, filas in (("departamento", deptos), ("ciudad", ciudades)):
            d = os.path.join(raw, "mariadb", tabla, f"fecha_ingesta={fi}")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, f"{tabla}.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(filas[0].keys()) + ["actualizado_en"])
                w.writeheader()
                for r in filas:
                    w.writerow({**r, "actualizado_en": f"{fi} 10:00:00"})

    # --- EC2: CSV legados 2022-2024 ---
    for c in ciudades + [{"id_ciudad": "99999", "altitud_m": "100", "region_natural": "Caribe"}]:  # 99999 = huérfana
        for anio in (2022, 2023, 2024):
            d = os.path.join(raw, "archivos_ec2", "estaciones", f"anio={anio}")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, f"EST_{c['id_ciudad']}_{anio}.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["CODIGO_ESTACION", "FECHA", "TMAX", "TMIN", "TMED", "PRECIP", "VIENTO_MAX"])
                dia = dt.date(anio, 1, 1)
                while dia.year == anio:
                    vals = clima_sintetico(c, dia)
                    txt = [f"{v:.1f}".replace(".", ",") for v in vals]
                    if random.random() < 0.01:
                        txt[random.randrange(5)] = "-999"
                    if c["id_ciudad"] == "05001" and dia == dt.date(2023, 3, 3):
                        txt[0] = "85,0"   # fuera de rango
                    w.writerow([f"EST-{c['id_ciudad']}", dia.strftime("%d/%m/%Y")] + txt)
                    dia += dt.timedelta(days=1)

    # --- API Open-Meteo: backfill + una ingesta diaria que repite días ---
    def jsonl(fi, hora, ini, fin):
        d = os.path.join(raw, "api_openmeteo", f"fecha_ingesta={fi}")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"clima_{hora}.jsonl"), "w", encoding="utf-8") as f:
            for c in ciudades:
                dias, dia = [], ini
                while dia <= fin:
                    dias.append(dia)
                    dia += dt.timedelta(days=1)
                vals = [clima_sintetico(c, x) for x in dias]
                daily = {"time": [x.isoformat() for x in dias]}
                for k, nom in enumerate(["temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
                                         "precipitation_sum", "wind_speed_10m_max"]):
                    daily[nom] = [v[k] for v in vals]
                daily["temperature_2m_mean"][-1] = None   # nulo -> se imputa
                resp = {"latitude": float(c["latitud"]), "longitude": float(c["longitud"]),
                        "elevation": float(c["altitud_m"]), "timezone": "America/Bogota",
                        "daily_units": {"temperature_2m_max": "°C"}, "daily": daily}
                f.write(json.dumps({"id_ciudad": c["id_ciudad"], "ciudad": c["ciudad"],
                                    "fecha_extraccion": f"{fi}T{hora[:2]}:{hora[2:4]}:{hora[4:]}",
                                    "fecha_inicio": ini.isoformat(), "fecha_fin": fin.isoformat(),
                                    "respuesta": resp}, ensure_ascii=False) + "\n")

    jsonl("2026-11-16", "053000", dt.date(2025, 1, 1), dt.date(2026, 11, 10))
    jsonl("2026-11-17", "053000", dt.date(2026, 11, 2), dt.date(2026, 11, 11))

    # --- NOAA ONI (mismo formato de ancho fijo) ---
    d = os.path.join(raw, "api_noaa", "oni", "fecha_ingesta=2026-11-17")
    os.makedirs(d, exist_ok=True)
    temporadas = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]
    with open(os.path.join(d, "oni.ascii.txt"), "w") as f:
        f.write("SEAS  YR   TOTAL   ANOM\n")
        for anio in range(2021, 2027):
            for i, s in enumerate(temporadas):
                if anio == 2026 and i > 8:
                    break
                anom = 1.6 * math.sin(2 * math.pi * ((anio - 2021) * 12 + i - 20) / 40)
                f.write(f"  {s} {anio}   {26.5 + anom:5.2f}   {anom:5.2f}\n")
    print(f"RAW sintético en {raw}")


if __name__ == "__main__":
    main()

"""
Punto 8b — API REST de resultados: API Gateway (HTTP API) -> Lambda -> Athena.

Rutas (método GET):
  /preguntas                          lista de preguntas de negocio
  /preguntas/{n}                      respuesta de la pregunta n (1..8) desde clima_refined
  /ciudades                           ciudades del maestro (clima_trusted.dim_ciudad)
  /clima-mensual?ciudad=05001&desde=2024-01&hasta=2025-12
                                      serie mensual de una ciudad (clima_refined.clima_mensual)

Seguridad: los parámetros del usuario se validan con expresiones regulares y se
pasan a Athena como *parámetros de ejecución* (?), nunca concatenados en el SQL.
Los resultados se guardan en memoria del contenedor 10 minutos (las tablas
refined cambian una vez al día).
"""
import json
import os
import re
import time

import boto3

athena = boto3.client("athena")
SALIDA = os.environ["ATHENA_OUTPUT"]
DB_REFINED = os.environ.get("DB_REFINED", "clima_refined")
DB_TRUSTED = os.environ.get("DB_TRUSTED", "clima_trusted")
CACHE, TTL = {}, 600

PREGUNTAS = {
    1: ("¿Cuál fue la ciudad más caliente en abril de 2025?", "p1_ciudad_mas_caliente_abr2025", "temp_max_promedio DESC"),
    2: ("Ranking de departamentos por temperatura media 2024", "p2_ranking_deptos_temp_2024", "puesto"),
    3: ("¿Qué región natural llueve más? (anual)", "p3_lluvia_anual_region", "anio, precip_anual_promedio_mm DESC"),
    4: ("Altitud vs temperatura media", "p4_detalle_ciudades", "altitud_m"),
    5: ("Lluvia mensual promedio por región", "p5_lluvia_mensual_region", "region_natural, mes"),
    6: ("Días de calor extremo 2024 vs 2025", "p6_dias_calor_extremo", "dias_2024 DESC"),
    7: ("Anomalía de lluvia según fase ENSO", "p7_lluvia_vs_enso", "region_natural, fase_enso"),
    8: ("Población expuesta a calor extremo 2024", "p8_poblacion_expuesta_calor", "persona_dias_expuestos DESC"),
}
CONVERTIR = {"integer": int, "bigint": int, "tinyint": int, "smallint": int,
             "double": float, "float": float, "decimal": float, "boolean": lambda v: v == "true"}


def consultar(sql, parametros=None):
    clave = (sql, tuple(parametros or []))
    if clave in CACHE and time.time() - CACHE[clave][0] < TTL:
        return CACHE[clave][1]
    kw = {"QueryString": sql, "ResultConfiguration": {"OutputLocation": SALIDA}}
    if parametros:
        kw["ExecutionParameters"] = parametros
    qid = athena.start_query_execution(**kw)["QueryExecutionId"]
    while True:
        st = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
        if st["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(0.4)
    if st["State"] != "SUCCEEDED":
        raise RuntimeError(st.get("StateChangeReason", st["State"]))

    filas, columnas, tipos, token = [], None, None, None
    while True:
        kw = {"QueryExecutionId": qid, "MaxResults": 1000}
        if token:
            kw["NextToken"] = token
        r = athena.get_query_results(**kw)
        if columnas is None:
            info = r["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]
            columnas, tipos = [c["Name"] for c in info], [c["Type"] for c in info]
            datos = r["ResultSet"]["Rows"][1:]          # la primera fila es el encabezado
        else:
            datos = r["ResultSet"]["Rows"]
        for f in datos:
            valores = [c.get("VarCharValue") for c in f["Data"]]
            filas.append({col: (CONVERTIR.get(t, str)(v) if v is not None else None)
                          for col, t, v in zip(columnas, tipos, valores)})
        token = r.get("NextToken")
        if not token:
            break
    CACHE[clave] = (time.time(), filas)
    return filas


def respuesta(codigo, cuerpo):
    return {"statusCode": codigo,
            "headers": {"Content-Type": "application/json; charset=utf-8",
                        "Access-Control-Allow-Origin": "*"},
            "body": json.dumps(cuerpo, ensure_ascii=False, default=str)}


def lambda_handler(event, context):
    ruta = event.get("rawPath", "/").rstrip("/") or "/"
    qs = event.get("queryStringParameters") or {}
    try:
        if ruta in ("/", "/preguntas"):
            return respuesta(200, [{"id": k, "pregunta": v[0], "tabla": v[1]} for k, v in PREGUNTAS.items()])

        m = re.fullmatch(r"/preguntas/(\d)", ruta)
        if m:
            n = int(m.group(1))
            if n not in PREGUNTAS:
                return respuesta(404, {"error": "pregunta inexistente (1..8)"})
            titulo, tabla, orden = PREGUNTAS[n]       # nombres fijos del diccionario: no vienen del usuario
            datos = consultar(f'SELECT * FROM "{DB_REFINED}"."{tabla}" ORDER BY {orden}')
            return respuesta(200, {"id": n, "pregunta": titulo, "filas": datos})

        if ruta == "/ciudades":
            datos = consultar(f'SELECT id_ciudad, ciudad, departamento, region_natural, altitud_m, '
                              f'latitud, longitud FROM "{DB_TRUSTED}"."dim_ciudad" ORDER BY ciudad')
            return respuesta(200, datos)

        if ruta == "/clima-mensual":
            ciudad = qs.get("ciudad", "")
            desde, hasta = qs.get("desde", "2022-01"), qs.get("hasta", "2099-12")
            if not re.fullmatch(r"\d{5}", ciudad) or not all(re.fullmatch(r"\d{4}-\d{2}", x) for x in (desde, hasta)):
                return respuesta(400, {"error": "use ciudad=05001&desde=AAAA-MM&hasta=AAAA-MM"})
            sql = (f'SELECT anio, mes, ciudad, temp_max_prom, temp_media_prom, temp_min_prom, '
                   f'precip_total_mm, dias_calor_extremo, fase_enso '
                   f'FROM "{DB_REFINED}"."clima_mensual" '
                   f'WHERE id_ciudad = ? AND anio * 100 + mes BETWEEN ? AND ? ORDER BY anio, mes')
            datos = consultar(sql, [f"'{ciudad}'", desde.replace("-", ""), hasta.replace("-", "")])
            return respuesta(200, datos)

        return respuesta(404, {"error": f"ruta no encontrada: {ruta}",
                               "rutas": ["/preguntas", "/preguntas/{n}", "/ciudades", "/clima-mensual"]})
    except Exception as e:
        print("ERROR", repr(e))
        return respuesta(500, {"error": str(e)})

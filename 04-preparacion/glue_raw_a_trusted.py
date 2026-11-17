"""
Punto 4 — Preparación de datos: RAW (bronze) -> TRUSTED (silver).

Corre como **AWS Glue Job** (Glue 4.0 / Spark 3.3) y también con `spark-submit`
en EMR o en local (mismo código; solo cambian los parámetros):

  Glue : --RAW s3://bucket/raw --TRUSTED s3://bucket/trusted   (Job parameters)
  EMR  : spark-submit glue_raw_a_trusted.py --RAW s3://... --TRUSTED s3://...
  Local: spark-submit glue_raw_a_trusted.py --RAW ./datalake/raw --TRUSTED ./datalake/trusted

Qué hace:
  1. dim_ciudad   : último snapshot de MariaDB (ciudad + departamento), tipado.
  2. clima_diario : une los CSV legados del EC2 y el JSON de la API en un solo
                    esquema; corrige formatos, aplica reglas de calidad,
                    elimina duplicados; Parquet particionado por anio/mes.
  3. oni_mensual  : parsea el .txt de NOAA y asigna la fase ENSO por mes.
"""
import sys

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql import types as T
from pyspark.sql.utils import AnalysisException


# --------------------------------------------------------------------------
# Arranque: Glue si está disponible, si no Spark normal
# --------------------------------------------------------------------------
def iniciar():
    try:
        from awsglue.context import GlueContext
        from awsglue.job import Job
        from awsglue.utils import getResolvedOptions
        from pyspark.context import SparkContext

        args = getResolvedOptions(sys.argv, ["JOB_NAME", "RAW", "TRUSTED"])
        glue_ctx = GlueContext(SparkContext.getOrCreate())
        job = Job(glue_ctx)
        job.init(args["JOB_NAME"], args)
        return glue_ctx.spark_session, args["RAW"], args["TRUSTED"], job
    except ImportError:
        import argparse
        p = argparse.ArgumentParser()
        p.add_argument("--RAW", required=True)
        p.add_argument("--TRUSTED", required=True)
        a, _ = p.parse_known_args()
        spark = SparkSession.builder.appName("clima_raw_a_trusted").getOrCreate()
        return spark, a.RAW, a.TRUSTED, None


spark, RAW, TRUSTED, job = iniciar()
RAW, TRUSTED = RAW.rstrip("/"), TRUSTED.rstrip("/")
spark.conf.set("spark.sql.session.timeZone", "America/Bogota")


def log(msg):
    print(f"[raw_a_trusted] {msg}", flush=True)


def ultimo_snapshot(df: DataFrame) -> DataFrame:
    """Se queda con la partición fecha_ingesta más reciente."""
    maxima = df.agg(F.max("fecha_ingesta")).first()[0]
    log(f"  snapshot usado: fecha_ingesta={maxima}")
    return df.filter(F.col("fecha_ingesta") == F.lit(maxima))


def leer_csv_texto(ruta, sep=","):
    # Todo como texto: inferSchema convertiría '05001' en 5001 y perderíamos el cero
    return (spark.read.option("header", True).option("sep", sep)
            .option("inferSchema", False).option("encoding", "UTF-8").csv(ruta))


# --------------------------------------------------------------------------
# 1. dim_ciudad  (fuente: RDS MariaDB)
# --------------------------------------------------------------------------
log("1/3 dim_ciudad")
depto = ultimo_snapshot(leer_csv_texto(f"{RAW}/mariadb/departamento/"))
ciudad = ultimo_snapshot(leer_csv_texto(f"{RAW}/mariadb/ciudad/"))

dim_ciudad = (
    ciudad.alias("c")
    .join(depto.alias("d"), F.col("c.cod_depto") == F.col("d.cod_depto"), "left")
    .select(
        F.lpad(F.trim("c.id_ciudad"), 5, "0").alias("id_ciudad"),
        F.trim("c.ciudad").alias("ciudad"),
        F.lpad(F.trim("c.cod_depto"), 2, "0").alias("cod_depto"),
        F.trim("d.departamento").alias("departamento"),
        F.trim("c.region_natural").alias("region_natural"),
        F.col("c.latitud").cast("double").alias("latitud"),
        F.col("c.longitud").cast("double").alias("longitud"),
        F.col("c.altitud_m").cast("int").alias("altitud_m"),
        (F.col("c.es_capital").cast("int") == 1).alias("es_capital"),
        F.col("d.poblacion_2024").cast("long").alias("poblacion_depto"),
        F.col("d.area_km2").cast("int").alias("area_depto_km2"),
    )
    .dropDuplicates(["id_ciudad"])
)
dim_ciudad.cache()
log(f"  ciudades: {dim_ciudad.count()}")
dim_ciudad.coalesce(1).write.mode("overwrite").parquet(f"{TRUSTED}/dim_ciudad")


# --------------------------------------------------------------------------
# 2. clima_diario  (fuentes: archivos EC2 + API Open-Meteo)
# --------------------------------------------------------------------------
log("2/3 clima_diario")
COLS = ["temp_max", "temp_min", "temp_media", "precipitacion_mm", "viento_max_kmh"]


def numero_legado(c):
    """'27,4' -> 27.4 ; '-999' o vacío -> null"""
    limpio = F.trim(F.col(c))
    return (F.when(limpio.isNull() | (limpio == "") | (limpio == "-999"), F.lit(None))
            .otherwise(F.regexp_replace(limpio, ",", ".").cast("double")))


# 2a. CSV legados del EC2
archivos = (
    leer_csv_texto(f"{RAW}/archivos_ec2/estaciones/", sep=";")
    .select(
        F.regexp_replace(F.trim("CODIGO_ESTACION"), "^EST-", "").alias("id_ciudad"),
        F.to_date(F.trim("FECHA"), "dd/MM/yyyy").alias("fecha"),
        numero_legado("TMAX").alias("temp_max"),
        numero_legado("TMIN").alias("temp_min"),
        numero_legado("TMED").alias("temp_media"),
        numero_legado("PRECIP").alias("precipitacion_mm"),
        numero_legado("VIENTO_MAX").alias("viento_max_kmh"),
        F.lit("archivos_ec2").alias("fuente"),
        F.current_timestamp().alias("marca_ingesta"),
        F.lit(2).alias("prioridad"),
    )
)
log(f"  filas archivos EC2: {archivos.count()}")

# 2b. JSON de la API (una línea por ciudad, arreglos paralelos por variable)
ARR = T.ArrayType(T.DoubleType())
esquema_api = T.StructType([
    T.StructField("id_ciudad", T.StringType()),
    T.StructField("ciudad", T.StringType()),
    T.StructField("fecha_extraccion", T.StringType()),
    T.StructField("respuesta", T.StructType([
        T.StructField("daily", T.StructType([
            T.StructField("time", T.ArrayType(T.StringType())),
            T.StructField("temperature_2m_max", ARR),
            T.StructField("temperature_2m_min", ARR),
            T.StructField("temperature_2m_mean", ARR),
            T.StructField("precipitation_sum", ARR),
            T.StructField("wind_speed_10m_max", ARR),
        ]))
    ])),
])
try:
    api_raw = spark.read.schema(esquema_api).json(f"{RAW}/api_openmeteo/")
    d = "respuesta.daily."
    api = (
        api_raw.select("id_ciudad", "fecha_extraccion", "respuesta",
                       F.posexplode(d + "time").alias("i", "dia"))
        .select(
            F.lpad("id_ciudad", 5, "0").alias("id_ciudad"),
            F.to_date("dia").alias("fecha"),
            F.col(d + "temperature_2m_max")[F.col("i")].alias("temp_max"),
            F.col(d + "temperature_2m_min")[F.col("i")].alias("temp_min"),
            F.col(d + "temperature_2m_mean")[F.col("i")].alias("temp_media"),
            F.col(d + "precipitation_sum")[F.col("i")].alias("precipitacion_mm"),
            F.col(d + "wind_speed_10m_max")[F.col("i")].alias("viento_max_kmh"),
            F.lit("api_openmeteo").alias("fuente"),
            F.to_timestamp("fecha_extraccion").alias("marca_ingesta"),
            F.lit(1).alias("prioridad"),
        )
    )
    log(f"  filas API (con repetidos entre ingestas): {api.count()}")
except AnalysisException as e:
    log(f"  sin datos de API todavía ({e.desc[:80]}...)")
    api = archivos.limit(0)

clima = archivos.unionByName(api)

# 2c. Reglas de calidad: fuera de rango -> null (no se elimina la fila)
reglas = {
    "temp_max": (-10, 50), "temp_min": (-10, 50), "temp_media": (-10, 50),
    "precipitacion_mm": (0, 500), "viento_max_kmh": (0, 200),
}
for c, (lo, hi) in reglas.items():
    clima = clima.withColumn(c, F.when(F.col(c).between(lo, hi), F.col(c)))
inconsistente = F.col("temp_max") < F.col("temp_min")
clima = (clima.withColumn("temp_max", F.when(inconsistente, None).otherwise(F.col("temp_max")))
              .withColumn("temp_min", F.when(inconsistente, None).otherwise(F.col("temp_min"))))
# temp_media faltante -> promedio de max y min (regla de negocio documentada)
clima = clima.withColumn("temp_media", F.coalesce("temp_media", (F.col("temp_max") + F.col("temp_min")) / 2))
clima = clima.withColumn("temp_media", F.round("temp_media", 1))

# 2d. Deduplicar: una fila por ciudad y día. Gana la API sobre los archivos y,
#     dentro de la misma fuente, la ingesta más reciente.
w = Window.partitionBy("id_ciudad", "fecha").orderBy(F.col("prioridad"), F.col("marca_ingesta").desc())
clima = (clima.filter(F.col("fecha").isNotNull() & F.col("id_ciudad").isNotNull())
              .withColumn("rn", F.row_number().over(w)).filter("rn = 1").drop("rn", "prioridad"))

# 2e. Integridad referencial: solo ciudades que existen en el maestro
huerfanas = clima.join(dim_ciudad.select("id_ciudad"), "id_ciudad", "left_anti").count()
clima = clima.join(dim_ciudad.select("id_ciudad"), "id_ciudad", "left_semi")

clima = (clima.withColumn("fecha_ingesta", F.to_date("marca_ingesta")).drop("marca_ingesta")
              .withColumn("anio", F.year("fecha")).withColumn("mes", F.month("fecha"))
              .select("id_ciudad", "fecha", *COLS, "fuente", "fecha_ingesta", "anio", "mes"))
clima.cache()

calidad = clima.agg(F.count("*").alias("filas"),
                    *[F.sum(F.col(c).isNull().cast("int")).alias(f"nulos_{c}") for c in COLS]).first()
log(f"  filas finales: {calidad['filas']} | huérfanas descartadas: {huerfanas}")
log("  nulos: " + ", ".join(f"{c}={calidad['nulos_' + c]}" for c in COLS))

(clima.repartition("anio", "mes").write.mode("overwrite")
      .partitionBy("anio", "mes").parquet(f"{TRUSTED}/clima_diario"))


# --------------------------------------------------------------------------
# 3. oni_mensual  (fuente: NOAA)
# --------------------------------------------------------------------------
log("3/3 oni_mensual")
# Cada temporada de 3 meses se asigna a su mes central (DJF -> enero, ..., NDJ -> diciembre)
MES_CENTRAL = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
               "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}
mapa = F.create_map(*[x for k, v in MES_CENTRAL.items() for x in (F.lit(k), F.lit(v))])
try:
    oni_txt = ultimo_snapshot(spark.read.text(f"{RAW}/api_noaa/oni/"))
    partes = F.split(F.trim("value"), r"\s+")
    oni = (
        oni_txt.filter(~F.trim("value").startswith("SEAS") & (F.trim("value") != ""))
        .select(partes[0].alias("temporada"), partes[1].cast("int").alias("anio"),
                partes[3].cast("double").alias("oni_anomalia"))
        .withColumn("mes", mapa[F.col("temporada")])
        .filter(F.col("mes").isNotNull() & F.col("oni_anomalia").isNotNull())
        .withColumn("fase_enso", F.when(F.col("oni_anomalia") >= 0.5, "El Niño")
                                  .when(F.col("oni_anomalia") <= -0.5, "La Niña")
                                  .otherwise("Neutral"))
        .select("anio", "mes", "temporada", "oni_anomalia", "fase_enso")
        .dropDuplicates(["anio", "mes"])
    )
    log(f"  meses ONI: {oni.count()}")
    oni.coalesce(1).write.mode("overwrite").parquet(f"{TRUSTED}/oni_mensual")
except AnalysisException as e:
    log(f"  sin ONI todavía: {e.desc[:80]}")

log("OK")
if job:
    job.commit()

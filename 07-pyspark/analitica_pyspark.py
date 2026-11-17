"""
Punto 7 — Analítica descriptiva con PySpark (API de DataFrames, sin SQL).

Responde las 8 preguntas de negocio y escribe cada respuesta en la zona
REFINED (gold) en Parquet, más dos tablas de apoyo para la visualización:

  refined/clima_mensual          ciudad x año x mes (para gráficas y la API)
  refined/estadisticas_ciudad    media, desviación y percentiles por ciudad
  refined/p1_ciudad_mas_caliente_abr2025 ... refined/p8_poblacion_expuesta_calor

  EMR  : spark-submit analitica_pyspark.py --TRUSTED s3://b/trusted --REFINED s3://b/refined
  Local: spark-submit analitica_pyspark.py --TRUSTED ./datalake/trusted --REFINED ./datalake/refined
"""
import argparse

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

p = argparse.ArgumentParser()
p.add_argument("--TRUSTED", required=True)
p.add_argument("--REFINED", required=True)
p.add_argument("--umbral_calor", type=float, default=35.0, help="°C para 'calor extremo'")
a = p.parse_args()
T, R, UMBRAL = a.TRUSTED.rstrip("/"), a.REFINED.rstrip("/"), a.umbral_calor

spark = SparkSession.builder.appName("clima_analitica_pyspark").getOrCreate()
spark.sparkContext.setLogLevel("WARN")

dim = spark.read.parquet(f"{T}/dim_ciudad")
clima = spark.read.parquet(f"{T}/clima_diario")
oni = spark.read.parquet(f"{T}/oni_mensual")

# Base enriquecida: cada día con los atributos de la ciudad (dim pequeña -> broadcast)
base = clima.join(F.broadcast(dim), "id_ciudad").cache()
es_calor = (F.col("temp_max") >= UMBRAL).cast("int")


def guardar(df, nombre, mostrar=20):
    print("\n" + "=" * 90 + f"\n{nombre}\n" + "=" * 90)
    df.show(mostrar, truncate=False)
    df.coalesce(1).write.mode("overwrite").parquet(f"{R}/{nombre}")


# ---------- Tablas de apoyo ----------
mensual = (base.groupBy("id_ciudad", "ciudad", "departamento", "region_natural", "altitud_m", "anio", "mes")
               .agg(F.round(F.avg("temp_max"), 2).alias("temp_max_prom"),
                    F.round(F.avg("temp_media"), 2).alias("temp_media_prom"),
                    F.round(F.avg("temp_min"), 2).alias("temp_min_prom"),
                    F.round(F.sum("precipitacion_mm"), 1).alias("precip_total_mm"),
                    F.sum(es_calor).alias("dias_calor_extremo"),
                    F.count("*").alias("dias_con_dato"))
               .join(oni.select("anio", "mes", "oni_anomalia", "fase_enso"), ["anio", "mes"], "left"))
mensual.cache()
guardar(mensual.orderBy("id_ciudad", "anio", "mes"), "clima_mensual", 5)

estad = (base.groupBy("ciudad", "region_natural", "altitud_m")
             .agg(F.round(F.avg("temp_media"), 2).alias("temp_media"),
                  F.round(F.stddev("temp_media"), 2).alias("temp_media_desv"),
                  F.expr("round(percentile_approx(temp_max, 0.9), 1)").alias("temp_max_p90"),
                  F.expr("round(percentile_approx(temp_min, 0.1), 1)").alias("temp_min_p10"),
                  F.round(F.avg("precipitacion_mm"), 2).alias("precip_diaria_media"),
                  F.round(F.avg((F.col("precipitacion_mm") >= 1).cast("int")) * 100, 1).alias("pct_dias_lluvia"),
                  F.min("fecha").alias("desde"), F.max("fecha").alias("hasta"))
             .orderBy(F.desc("temp_media")))
guardar(estad, "estadisticas_ciudad", 10)

# ---------- P1: ciudad más caliente en abril 2025 ----------
p1 = (base.filter((F.col("anio") == 2025) & (F.col("mes") == 4))
          .groupBy("ciudad", "departamento")
          .agg(F.round(F.avg("temp_max"), 2).alias("temp_max_promedio"),
               F.max("temp_max").alias("temp_max_absoluta"), F.count("*").alias("dias"))
          .orderBy(F.desc("temp_max_promedio")).limit(5))
guardar(p1, "p1_ciudad_mas_caliente_abr2025")

# ---------- P2: ranking de departamentos por temperatura media 2024 ----------
p2 = (base.filter(F.col("anio") == 2024).groupBy("departamento")
          .agg(F.round(F.avg("temp_media"), 2).alias("temp_media_2024"))
          .withColumn("puesto", F.rank().over(Window.orderBy(F.desc("temp_media_2024"))))
          .select("puesto", "departamento", "temp_media_2024").orderBy("puesto"))
guardar(p2, "p2_ranking_deptos_temp_2024", 40)

# ---------- P3: lluvia anual por región ----------
p3 = (mensual.filter(F.col("anio").between(2022, 2025))
             .groupBy("region_natural", "id_ciudad", "anio").agg(F.sum("precip_total_mm").alias("anual"))
             .groupBy("region_natural", "anio")
             .agg(F.round(F.avg("anual"), 1).alias("precip_anual_promedio_mm"),
                  F.countDistinct("id_ciudad").alias("ciudades"))
             .orderBy("anio", F.desc("precip_anual_promedio_mm")))
guardar(p3, "p3_lluvia_anual_region", 30)

# ---------- P4: altitud vs temperatura ----------
por_ciudad = base.groupBy("ciudad", "altitud_m").agg(F.avg("temp_media").alias("temp_media"))
corr = por_ciudad.stat.corr("altitud_m", "temp_media")
# pendiente por mínimos cuadrados: cov(x,y)/var(x)
m = por_ciudad.agg(F.covar_samp("altitud_m", "temp_media").alias("cov"),
                   F.var_samp("altitud_m").alias("var"),
                   F.avg("altitud_m").alias("x"), F.avg("temp_media").alias("y")).first()
pend = m["cov"] / m["var"]
p4 = spark.createDataFrame([(round(corr, 3), round(pend * 1000, 2), round(m["y"] - pend * m["x"], 2),
                             por_ciudad.count())],
                           "correlacion double, grados_por_1000m double, temp_estimada_nivel_mar double, ciudades long")
guardar(p4, "p4_altitud_vs_temperatura")
guardar(por_ciudad.select("ciudad", "altitud_m", F.round("temp_media", 2).alias("temp_media"))
                  .orderBy("altitud_m"), "p4_detalle_ciudades", 40)

# ---------- P5: meses más lluviosos por región ----------
region_mes = (mensual.filter(F.col("anio").between(2022, 2025))
                     .groupBy("region_natural", "mes")
                     .agg(F.round(F.avg("precip_total_mm"), 1).alias("precip_mensual_promedio_mm")))
w5 = Window.partitionBy("region_natural").orderBy(F.desc("precip_mensual_promedio_mm"))
p5 = region_mes.withColumn("puesto", F.rank().over(w5)).orderBy("region_natural", "mes")
guardar(p5, "p5_lluvia_mensual_region", 72)   # se guardan los 12 meses (para graficar)

# ---------- P6: días de calor extremo 2024 vs 2025 ----------
p6 = (base.filter(F.col("anio").isin(2024, 2025))
          .groupBy("ciudad", "region_natural")
          .pivot("anio", [2024, 2025]).agg(F.sum(es_calor))
          .withColumnRenamed("2024", "dias_2024").withColumnRenamed("2025", "dias_2025")
          .withColumn("diferencia", F.col("dias_2025") - F.col("dias_2024"))
          .filter((F.col("dias_2024") + F.col("dias_2025")) > 0)
          .orderBy(F.desc("dias_2024"), F.desc("dias_2025")))
guardar(p6, "p6_dias_calor_extremo", 40)

# ---------- P7: anomalía de lluvia según fase ENSO ----------
completos = mensual.filter(F.col("dias_con_dato") >= 28)
normal = completos.groupBy("id_ciudad", "mes").agg(F.avg("precip_total_mm").alias("precip_normal"))
p7 = (completos.filter(F.col("fase_enso").isNotNull()).join(normal, ["id_ciudad", "mes"])
               .withColumn("anomalia", F.col("precip_total_mm") - F.col("precip_normal"))
               .groupBy("region_natural", "fase_enso")
               .agg(F.round(F.avg("anomalia"), 1).alias("anomalia_mm"),
                    F.round(F.avg("anomalia") / F.avg("precip_normal") * 100, 1).alias("anomalia_pct"),
                    F.count("*").alias("meses_ciudad"))
               .orderBy("region_natural", "fase_enso"))
guardar(p7, "p7_lluvia_vs_enso", 30)

# ---------- P8: población expuesta a calor extremo 2024 ----------
p8 = (base.filter(F.col("anio") == 2024)
          .groupBy("departamento", "poblacion_depto").agg(F.sum(es_calor).alias("dias_calor"))
          .filter(F.col("dias_calor") > 0)
          .withColumn("persona_dias_expuestos", F.col("dias_calor").cast("long") * F.col("poblacion_depto"))
          .orderBy(F.desc("persona_dias_expuestos")).limit(10))
guardar(p8, "p8_poblacion_expuesta_calor")

print("\nOK: tablas escritas en", R)

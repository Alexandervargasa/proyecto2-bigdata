# Punto 7 — Analítica descriptiva con Spark en Python (PySpark)

`analitica_pyspark.py` responde las 8 preguntas con la **API de DataFrames**
(`groupBy`, `agg`, `Window`, `pivot`, `broadcast`, `stat.corr`, `percentile_approx`),
sin escribir SQL, y deja cada respuesta en **refined (gold)** en Parquet.

| Tabla refined | Contenido |
|---------------|-----------|
| `clima_mensual` | Ciudad × año × mes: promedios, lluvia total, días de calor y fase ENSO. Alimenta las gráficas y la API |
| `estadisticas_ciudad` | Media, desviación, P90 de Tmax, P10 de Tmin, % de días con lluvia |
| `p1_…` a `p8_…` | Una tabla por pregunta (`p4_detalle_ciudades` trae los puntos de la regresión) |

Como control de calidad, los resultados de PySpark deben coincidir con los de
SparkSQL/Hive/Athena del punto 6: son dos implementaciones independientes de la
misma lógica. (En la prueba local con datos sintéticos coinciden en P1, P4, P6 y P7.)

## Ejecutar en EMR como steps (recomendado)
```bash
source config.env
export CLUSTER_ID=j-XXXXXXXX
bash 07-pyspark/ejecutar_steps_emr.sh            # también corre los pasos Hive/SparkSQL
bash 05-catalogacion/01_crawlers_glue.sh --refined
```
Consola: EMR → clúster → *Steps* (pantallazo con los 4 en *Completed*) → *View logs* → `stdout`.

## Ejecutar por SSH o JupyterHub
```bash
spark-submit s3://<bucket>/scripts/analitica_pyspark.py --TRUSTED s3://<bucket>/trusted --REFINED s3://<bucket>/refined
```
En JupyterHub (`https://<master-dns>:9443`, usuario `jovyan` / clave `jupyter`)
puede pegar el script por bloques en un notebook PySpark para tener las tablas
como evidencia visual.

Parámetro opcional `--umbral_calor 33` para refinar P6/P8.

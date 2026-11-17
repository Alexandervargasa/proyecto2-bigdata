# Proyecto 2 — Big Data: Clima de las capitales de Colombia en AWS

**Curso:** SI3007 — Big Data · Universidad EAFIT
**Integrantes:** `David Alejandro Ballesteros Jaimes, daballestj@eafit.edu.co` · `Alexander Vargas Atehortúa, avargasa2@eafit.edu.co`

Datalake en **S3** (raw → trusted → refined) alimentado automáticamente desde
**RDS MariaDB**, **archivos en EC2** y **URLs de Internet** (Open-Meteo y NOAA);
preparación con **Glue/Spark**; catálogo en **Glue Data Catalog** y **Hive (EMR)**;
analítica con **Athena, Hive, SparkSQL y PySpark**; visualización con
**matplotlib** y una app **Streamlit** que consume una API publicada en
**API Gateway**.

Diagrama de arquitectura y decisiones de diseño: [`docs/arquitectura.md`](docs/arquitectura.md).

## Estructura del repositorio (un directorio por punto del enunciado)

| Carpeta | Punto | Contenido |
|---------|-------|-----------|
| [`01-caso-estudio`](01-caso-estudio/) | 1 | Contexto, fuentes, **8 preguntas de negocio**, diccionario de datos |
| [`02-fuentes-datos`](02-fuentes-datos/) | 2 | Red, RDS MariaDB (esquema + datos), EC2 y generador de archivos, URLs |
| [`03-ingesta`](03-ingesta/) | 3 | Bucket, cron en EC2 (MariaDB y archivos), Lambda + EventBridge (API) |
| [`04-preparacion`](04-preparacion/) | 4 | Glue Job PySpark raw → trusted |
| [`05-catalogacion`](05-catalogacion/) | 5 | Crawlers, EMR con Glue Catalog, DDL Hive, Glue Workflow diario |
| [`06-consultas-sql`](06-consultas-sql/) | 6 | Consultas en Athena, Hive y SparkSQL |
| [`07-pyspark`](07-pyspark/) | 7 | Analítica PySpark → refined, steps de EMR |
| [`08-visualizacion`](08-visualizacion/) | 8 | matplotlib, API Gateway + Lambda + Athena, Streamlit |
| [`pruebas_locales`](pruebas_locales/) | — | Prueba de todo el procesamiento sin AWS con datos sintéticos |
| [`docs`](docs/) | — | Arquitectura y decisiones |

## Cómo reproducir todo (orden exacto)

Requisitos: AWS Academy **Learner Lab** iniciado (círculo verde), región
`us-east-1`, AWS CloudShell, y `labsuser.pem` descargado de *AWS Details*.

| # | Dónde | Comando | Tiempo |
|---|-------|---------|--------|
| 0 | CloudShell | `git clone <este-repo> && cd proyecto2-bigdata-clima && cp config.env.example config.env && nano config.env && source config.env` | 2 min |
| 1 | CloudShell | `bash 03-ingesta/00_crear_datalake.sh` | 1 min |
| 2 | CloudShell | `bash 02-fuentes-datos/01_crear_red.sh` | 1 min |
| 3 | CloudShell | `bash 02-fuentes-datos/02_crear_rds.sh` → poner `DB_HOST` en `config.env` | 10 min |
| 4 | CloudShell | `bash 02-fuentes-datos/03_crear_ec2.sh` | 3 min |
| 5 | EC2 (SSH) | crear `config.env` igual, `source config.env`, `bash 02-fuentes-datos/04_cargar_mariadb.sh` | 1 min |
| 6 | EC2 | `python3 02-fuentes-datos/ec2/generar_archivos_estaciones.py` | 2 min |
| 7 | EC2 | `python3 03-ingesta/ec2/ingesta_mariadb.py && bash 03-ingesta/ec2/ingesta_archivos.sh && bash 03-ingesta/ec2/instalar_cron.sh` | 1 min |
| 8 | CloudShell | `bash 03-ingesta/lambda_ingesta_api/desplegar.sh` (incluye carga inicial 2025→hoy) | 2 min |
| 9 | CloudShell | `bash 04-preparacion/desplegar_glue_job.sh` | 4 min |
| 10 | CloudShell | `bash 05-catalogacion/01_crawlers_glue.sh` | 4 min |
| 11 | CloudShell | `bash 05-catalogacion/03_workflow_automatico.sh` | 1 min |
| 12 | CloudShell | `python3 06-consultas-sql/ejecutar_athena.py` | 1 min |
| 13 | CloudShell | `bash 05-catalogacion/02_crear_emr.sh` → `export CLUSTER_ID=...` | 12 min |
| 14 | CloudShell | `bash 07-pyspark/ejecutar_steps_emr.sh` (Hive DDL, Hive, SparkSQL, PySpark) | 8 min |
| 15 | CloudShell | `bash 05-catalogacion/01_crawlers_glue.sh --refined` | 2 min |
| 16 | CloudShell | `bash 08-visualizacion/api_lambda/desplegar_api.sh` → `API_URL` a `config.env` | 1 min |
| 17 | CloudShell | `python3 08-visualizacion/matplotlib/graficas.py --refined $REFINED --salida graficas` | 1 min |
| 18 | EC2 | `bash 08-visualizacion/streamlit/instalar_servicio.sh` → `http://<ip>:8501` | 2 min |

Cada carpeta tiene su `README.md` con el detalle, la alternativa por consola y
las **evidencias** (pantallazos) que conviene pegar en el documento.

## Al terminar cada sesión del Learner Lab
- Termine el EMR (`aws emr terminate-clusters --cluster-ids $CLUSTER_ID`); igual se
  auto-termina tras 1 h sin trabajo.
- El Lab detiene EC2 y RDS al cerrar la sesión; al volver, la IP pública del EC2
  cambia (el RDS conserva su endpoint).
- Las Lambdas, reglas, crawlers, S3 y el catálogo se conservan entre sesiones.

## Probar sin AWS
```bash
pip install pyspark==3.5.3 pyarrow pandas matplotlib duckdb streamlit   # requiere Java 11+
bash pruebas_locales/ejecutar_local.sh
```
Los datos de esa prueba son **sintéticos** (solo validan la lógica); los
resultados reales salen de la ejecución en AWS.

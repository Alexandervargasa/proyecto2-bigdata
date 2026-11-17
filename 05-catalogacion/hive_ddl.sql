-- =====================================================================
-- Punto 5 — Catalogación con EMR / Hive (DDL manual)
-- En el nodo master del EMR:
--   hive --hivevar BUCKET=clima-colombia-datalake-XXXX -f hive_ddl.sql
-- Como el EMR usa el Glue Data Catalog como metastore, estas tablas también
-- aparecen en Glue y se pueden consultar desde Athena.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS clima_hive
COMMENT 'Tablas creadas con DDL de Hive sobre el datalake de clima'
LOCATION 's3://${hivevar:BUCKET}/hive/clima_hive.db/';

USE clima_hive;

-- ---------- Zona RAW: el CSV legado se puede leer directo con Hive ----------
DROP TABLE IF EXISTS raw_estaciones;
CREATE EXTERNAL TABLE raw_estaciones (
  codigo_estacion STRING,
  fecha           STRING,
  tmax            STRING,
  tmin            STRING,
  tmed            STRING,
  precip          STRING,
  viento_max      STRING
)
PARTITIONED BY (anio INT)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ';'
STORED AS TEXTFILE
LOCATION 's3://${hivevar:BUCKET}/raw/archivos_ec2/estaciones/'
TBLPROPERTIES ('skip.header.line.count'='1');
MSCK REPAIR TABLE raw_estaciones;

-- ---------- Zona TRUSTED (Parquet escrito por el Glue job) ----------
DROP TABLE IF EXISTS dim_ciudad;
CREATE EXTERNAL TABLE dim_ciudad (
  id_ciudad       STRING,
  ciudad          STRING,
  cod_depto       STRING,
  departamento    STRING,
  region_natural  STRING,
  latitud         DOUBLE,
  longitud        DOUBLE,
  altitud_m       INT,
  es_capital      BOOLEAN,
  poblacion_depto BIGINT,
  area_depto_km2  INT
)
STORED AS PARQUET
LOCATION 's3://${hivevar:BUCKET}/trusted/dim_ciudad/';

DROP TABLE IF EXISTS clima_diario;
CREATE EXTERNAL TABLE clima_diario (
  id_ciudad        STRING,
  fecha            DATE,
  temp_max         DOUBLE,
  temp_min         DOUBLE,
  temp_media       DOUBLE,
  precipitacion_mm DOUBLE,
  viento_max_kmh   DOUBLE,
  fuente           STRING,
  fecha_ingesta    DATE
)
PARTITIONED BY (anio INT, mes INT)
STORED AS PARQUET
LOCATION 's3://${hivevar:BUCKET}/trusted/clima_diario/';
MSCK REPAIR TABLE clima_diario;   -- registra las particiones anio=/mes=

DROP TABLE IF EXISTS oni_mensual;
CREATE EXTERNAL TABLE oni_mensual (
  anio         INT,
  mes          INT,
  temporada    STRING,
  oni_anomalia DOUBLE,
  fase_enso    STRING
)
STORED AS PARQUET
LOCATION 's3://${hivevar:BUCKET}/trusted/oni_mensual/';

SHOW TABLES;
SHOW PARTITIONS clima_diario;
SELECT COUNT(*) AS filas FROM clima_diario;

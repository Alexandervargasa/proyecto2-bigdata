-- =====================================================================
-- Punto 6 — Consultas descriptivas en HiveQL / SparkSQL (mismo dialecto)
--   Hive  (master EMR):  hive -f hive_sparksql_consultas.sql
--   Spark (master EMR):  spark-submit sparksql_consultas.py --catalogo
--   Spark (local)     :  spark-submit sparksql_consultas.py --trusted ./datalake/trusted
-- Tablas: clima_hive.dim_ciudad, clima_hive.clima_diario, clima_hive.oni_mensual
-- (en clima_hive las particiones anio/mes son INT, ver 05-catalogacion/hive_ddl.sql)
-- =====================================================================
USE clima_hive;

-- P1: Ciudad más caliente en abril de 2025 (temperatura máxima promedio), top 5
SELECT c.ciudad, c.departamento,
       ROUND(AVG(d.temp_max), 2) AS temp_max_promedio,
       ROUND(MAX(d.temp_max), 1) AS temp_max_absoluta,
       COUNT(*)                  AS dias
FROM clima_diario d
JOIN dim_ciudad c ON d.id_ciudad = c.id_ciudad
WHERE d.anio = 2025 AND d.mes = 4
GROUP BY c.ciudad, c.departamento
ORDER BY temp_max_promedio DESC
LIMIT 5;

-- P2: Ranking de departamentos por temperatura media en 2024
SELECT RANK() OVER (ORDER BY AVG(d.temp_media) DESC) AS puesto,
       c.departamento,
       ROUND(AVG(d.temp_media), 2) AS temp_media_2024,
       ROUND(MIN(d.temp_min), 1)   AS temp_min_absoluta,
       ROUND(MAX(d.temp_max), 1)   AS temp_max_absoluta
FROM clima_diario d
JOIN dim_ciudad c ON d.id_ciudad = c.id_ciudad
WHERE d.anio = 2024
GROUP BY c.departamento
ORDER BY puesto;

-- P3: Precipitación anual promedio por ciudad, según región natural y año
WITH anual AS (
  SELECT id_ciudad, anio, SUM(precipitacion_mm) AS precip_anual
  FROM clima_diario
  WHERE anio BETWEEN 2022 AND 2025
  GROUP BY id_ciudad, anio
)
SELECT c.region_natural, a.anio,
       ROUND(AVG(a.precip_anual), 1) AS precip_anual_promedio_mm,
       COUNT(DISTINCT a.id_ciudad)   AS ciudades
FROM anual a
JOIN dim_ciudad c ON a.id_ciudad = c.id_ciudad
GROUP BY c.region_natural, a.anio
ORDER BY a.anio, precip_anual_promedio_mm DESC;

-- P4: Relación altitud - temperatura media (correlación y gradiente por 1.000 m)
WITH prom AS (
  SELECT c.ciudad, CAST(c.altitud_m AS DOUBLE) AS altitud, AVG(d.temp_media) AS temp_media
  FROM clima_diario d
  JOIN dim_ciudad c ON d.id_ciudad = c.id_ciudad
  GROUP BY c.ciudad, c.altitud_m
)
SELECT ROUND(CORR(altitud, temp_media), 3)                AS correlacion,
       ROUND(REGR_SLOPE(temp_media, altitud) * 1000, 2)   AS grados_por_1000m,
       ROUND(REGR_INTERCEPT(temp_media, altitud), 2)      AS temp_estimada_nivel_mar,
       COUNT(*)                                           AS ciudades
FROM prom;

-- P5: Los 3 meses más lluviosos de cada región (lluvia mensual promedio por ciudad)
WITH mensual AS (
  SELECT id_ciudad, anio, mes, SUM(precipitacion_mm) AS precip_mes
  FROM clima_diario
  WHERE anio BETWEEN 2022 AND 2025
  GROUP BY id_ciudad, anio, mes
), region_mes AS (
  SELECT c.region_natural, m.mes, AVG(m.precip_mes) AS precip_mensual_promedio
  FROM mensual m
  JOIN dim_ciudad c ON m.id_ciudad = c.id_ciudad
  GROUP BY c.region_natural, m.mes
), ranking AS (
  SELECT region_natural, mes, precip_mensual_promedio,
         RANK() OVER (PARTITION BY region_natural ORDER BY precip_mensual_promedio DESC) AS puesto
  FROM region_mes
)
SELECT region_natural, puesto, mes, ROUND(precip_mensual_promedio, 1) AS precip_mensual_promedio_mm
FROM ranking
WHERE puesto <= 3
ORDER BY region_natural, puesto;

-- P6: Días de calor extremo (Tmax >= 35 °C) por ciudad: 2024 vs 2025
SELECT c.ciudad, c.region_natural,
       SUM(CASE WHEN d.anio = 2024 AND d.temp_max >= 35 THEN 1 ELSE 0 END) AS dias_2024,
       SUM(CASE WHEN d.anio = 2025 AND d.temp_max >= 35 THEN 1 ELSE 0 END) AS dias_2025,
       SUM(CASE WHEN d.anio = 2025 AND d.temp_max >= 35 THEN 1 ELSE 0 END)
     - SUM(CASE WHEN d.anio = 2024 AND d.temp_max >= 35 THEN 1 ELSE 0 END) AS diferencia
FROM clima_diario d
JOIN dim_ciudad c ON d.id_ciudad = c.id_ciudad
WHERE d.anio IN (2024, 2025)
GROUP BY c.ciudad, c.region_natural
HAVING SUM(CASE WHEN d.temp_max >= 35 THEN 1 ELSE 0 END) > 0
ORDER BY dias_2024 DESC, dias_2025 DESC;

-- P7: Anomalía de lluvia mensual según la fase ENSO (vs. el promedio de ese mes en esa ciudad)
WITH mensual AS (
  SELECT id_ciudad, anio, mes, SUM(precipitacion_mm) AS precip_mes
  FROM clima_diario
  GROUP BY id_ciudad, anio, mes
  HAVING COUNT(*) >= 28                       -- solo meses completos
), normal AS (
  SELECT id_ciudad, mes, AVG(precip_mes) AS precip_normal
  FROM mensual
  GROUP BY id_ciudad, mes
)
SELECT c.region_natural, o.fase_enso,
       ROUND(AVG(m.precip_mes - n.precip_normal), 1)                          AS anomalia_mm,
       ROUND(100 * AVG(m.precip_mes - n.precip_normal) / AVG(n.precip_normal), 1) AS anomalia_pct,
       COUNT(*)                                                               AS meses_ciudad
FROM mensual m
JOIN normal n      ON m.id_ciudad = n.id_ciudad AND m.mes = n.mes
JOIN oni_mensual o ON m.anio = o.anio AND m.mes = o.mes
JOIN dim_ciudad c  ON m.id_ciudad = c.id_ciudad
GROUP BY c.region_natural, o.fase_enso
ORDER BY c.region_natural, o.fase_enso;

-- P8: Población departamental expuesta a calor extremo en 2024 (persona-días)
WITH calor AS (
  SELECT c.departamento, c.poblacion_depto,
         SUM(CASE WHEN d.temp_max >= 35 THEN 1 ELSE 0 END) AS dias_calor
  FROM clima_diario d
  JOIN dim_ciudad c ON d.id_ciudad = c.id_ciudad
  WHERE d.anio = 2024
  GROUP BY c.departamento, c.poblacion_depto
)
SELECT departamento, dias_calor, poblacion_depto,
       CAST(dias_calor AS BIGINT) * poblacion_depto AS persona_dias_expuestos
FROM calor
WHERE dias_calor > 0
ORDER BY persona_dias_expuestos DESC
LIMIT 10;

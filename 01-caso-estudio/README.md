# Punto 1 — Caso de estudio: Clima de las capitales de Colombia

## Contexto de negocio

Una aseguradora agrícola (o una entidad de gestión del riesgo) quiere entender el
comportamiento del clima en las 33 ciudades principales de Colombia (las capitales
de departamento, Bogotá D.C. y Girardot como ciudad de referencia de Cundinamarca)
para priorizar zonas de riesgo por **calor extremo** y **lluvias intensas**, y
relacionar ese comportamiento con el fenómeno **El Niño / La Niña**.

## Fuentes de datos (requisito: BD + archivos + URL)

| # | Tipo | Dónde vive (simulado) | Qué contiene | Formato |
|---|------|------------------------|--------------|---------|
| 1 | **Base de datos** | RDS **MariaDB** `clima_maestros` | Datos maestros: `departamento` (código DANE, nombre, población, área) y `ciudad` (código DANE, coordenadas, altitud, región natural, si es capital) | Tablas SQL |
| 2 | **Archivos** | Servidor **EC2** `/opt/datos/estaciones/` | Histórico diario **2022–2024** por ciudad, simulando exportes de un sistema legado de estaciones: separador `;`, coma decimal, fecha `dd/mm/aaaa`, faltantes como `-999` | CSV, un archivo por ciudad y año |
| 3a | **URL** | API **Open-Meteo Historical Weather** | Clima diario reciente **2025 → hoy-6 días** (reanálisis ERA5) | JSON |
| 3b | **URL** | **NOAA CPC** `oni.ascii.txt` | Índice Oceánico El Niño (ONI) trimestral móvil desde 1950 | Texto ancho fijo |

> **Nota de honestidad de los datos:** los archivos del EC2 se *generan* desde
> Open-Meteo con un formato "legado" para simular un servidor de archivos, tal como
> pide el enunciado ("simular datos ... archivos en una instancia EC2"). Los valores
> son reales (reanálisis), el formato es el simulado. Las poblaciones del RDS son
> proyecciones DANE aproximadas; si quiere precisión, actualícelas con el archivo
> oficial de proyecciones de población del DANE.

Variables diarias: temperatura máxima, mínima y media a 2 m (°C), precipitación
acumulada (mm) y velocidad máxima del viento a 10 m (km/h).

Volumen aproximado: 33 ciudades × ~1.400 días ≈ 46.000 filas diarias, más el ONI
(~900 filas) y los maestros. Es pequeño a propósito, para que todo corra dentro de
los límites del Learner Lab; el mismo flujo escala cambiando `daily` por `hourly`
en la ingesta (≈ 1,1 millones de filas).

## Preguntas de negocio

| # | Pregunta | Fuentes que cruza | Respuesta en |
|---|----------|-------------------|--------------|
| **P1** | ¿Cuál fue la ciudad más caliente de Colombia en **abril de 2025** (mayor temperatura máxima promedio)? Top 5. | API + RDS | Athena, Hive, SparkSQL, PySpark |
| **P2** | Ordene los **departamentos** por temperatura media durante **2024**. | Archivos + RDS | Athena, Hive, SparkSQL, PySpark |
| **P3** | ¿Qué **región natural** (Andina, Caribe, Pacífica, Orinoquía, Amazonía, Insular) llueve más? Precipitación anual promedio por ciudad, por región y año. | Archivos + API + RDS | Athena, Hive, SparkSQL, PySpark |
| **P4** | ¿Qué tanto baja la temperatura con la **altitud**? Correlación y pendiente (°C por cada 1.000 m). | Todas las de clima + RDS | Athena, Hive, SparkSQL, PySpark |
| **P5** | ¿Cuáles son los **meses más lluviosos** de cada región? (régimen bimodal andino vs monomodal) | Archivos + API + RDS | Athena, Hive, SparkSQL, PySpark |
| **P6** | ¿Cuántos **días de calor extremo** (Tmax ≥ 35 °C) tuvo cada ciudad por año? ¿2024 (El Niño) tuvo más que 2025? | Archivos + API | Athena, Hive, SparkSQL, PySpark |
| **P7** | ¿Cómo cambia la **lluvia mensual** según la fase **El Niño / La Niña / Neutral** del ONI? | Archivos + API + NOAA + RDS | Athena, Hive, SparkSQL, PySpark |
| **P8** | ¿Qué departamentos tienen más **población expuesta** a calor extremo en 2024 (población × días ≥ 35 °C)? | Archivos + RDS | Athena, Hive, SparkSQL, PySpark |

Las preguntas se pueden refinar a medida que avance el proyecto (el enunciado lo
permite): por ejemplo cambiar el umbral de calor, el año o el mes.

## Diccionario de datos (zona trusted)

**`dim_ciudad`**: `id_ciudad` (código DANE municipio, 5 dígitos), `ciudad`,
`cod_depto`, `departamento`, `region_natural`, `latitud`, `longitud`,
`altitud_m`, `es_capital`, `poblacion_depto`, `area_depto_km2`.

**`clima_diario`** (particionada por `anio`, `mes`): `id_ciudad`, `fecha`,
`temp_max`, `temp_min`, `temp_media`, `precipitacion_mm`, `viento_max_kmh`,
`fuente` (`archivos_ec2` | `api_openmeteo`), `fecha_ingesta` (para la API, el día
en que se extrajo; para los archivos, el día en que se procesó), `anio`, `mes`.

**`oni_mensual`**: `anio`, `mes`, `temporada` (ej. `DJF`), `oni_anomalia`,
`fase_enso` (`El Niño` si ≥ 0,5; `La Niña` si ≤ −0,5; si no `Neutral`).

## Arquitectura

Ver el diagrama y las decisiones en [`../docs/arquitectura.md`](../docs/arquitectura.md).

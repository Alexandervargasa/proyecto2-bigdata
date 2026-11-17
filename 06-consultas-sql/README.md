# Punto 6 — Consultas analíticas descriptivas con SQL: Athena, EMR/Hive y SparkSQL

Las 8 preguntas del punto 1 se responden con **tres motores sobre los mismos datos**
(zona trusted) y el **mismo catálogo** (Glue Data Catalog).

| Archivo | Motor | Base de datos |
|---------|-------|---------------|
| `athena_consultas.sql` | Athena (Trino) | `clima_trusted` (crawler) |
| `hive_sparksql_consultas.sql` | Hive en EMR | `clima_hive` (DDL del punto 5) |
| `sparksql_consultas.py` | SparkSQL en EMR | ejecuta el mismo `.sql` de Hive |

¿Por qué dos dialectos? Athena consulta las tablas del crawler, cuyas particiones
`anio`/`mes` son `string`, así que filtra con `'2025'`. En Hive las tablas se
definieron con particiones `INT`. HiveQL y SparkSQL son prácticamente el mismo
dialecto, así que comparten archivo.

## 1. Athena
Consola: Athena → *Query editor* → Settings → *Query result location*
`s3://<bucket>/athena-results/` → Database `clima_trusted` → pegue cada consulta.

Desde CloudShell, todas de una vez:
```bash
source config.env
python3 06-consultas-sql/ejecutar_athena.py
```
El script también imprime los **KB escaneados**: compare P1 (lee solo la
partición `anio=2025/mes=4`) contra P4 (lee todo). Esa es la evidencia de por qué
se particionó en el punto 4.

## 2. Hive (master del EMR)
```bash
aws s3 cp s3://<bucket>/scripts/hive_sparksql_consultas.sql .
hive -f hive_sparksql_consultas.sql
```
(o en Hue → Editor → Hive).

## 3. SparkSQL (master del EMR)
```bash
aws s3 cp s3://<bucket>/scripts/sparksql_consultas.py .
spark-submit sparksql_consultas.py --catalogo --sql s3://<bucket>/scripts/hive_sparksql_consultas.sql
# o directo sobre los Parquet, sin catálogo:
spark-submit sparksql_consultas.py --trusted s3://<bucket>/trusted --sql s3://<bucket>/scripts/hive_sparksql_consultas.sql
```
Suba antes los scripts: `aws s3 cp 06-consultas-sql/ $SCRIPTS/ --recursive`.

## Notas para interpretar
- **P4** es una regresión lineal simple: la pendiente esperada en Colombia es
  cercana a −6 °C por cada 1.000 m (gradiente térmico vertical).
- **P6/P8** usan Tmax ≥ 35 °C. El reanálisis ERA5 suaviza los extremos frente a
  una estación real; si con datos reales salen muy pocas ciudades, baje el umbral
  a 33 °C y explíquelo en el documento (refinar preguntas está permitido).
- **P7** compara cada mes contra el promedio de ese mismo mes en esa ciudad
  (anomalía), para no confundir el efecto ENSO con la estacionalidad. Con solo
  ~4 años la "normal" es corta: dígalo como limitación.
- **P8** usa la capital como proxy del clima de todo el departamento.

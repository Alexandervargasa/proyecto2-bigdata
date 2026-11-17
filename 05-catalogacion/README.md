# Punto 5 — Catalogación de tablas: AWS Glue y EMR/Hive

Hay **un solo catálogo**: el **Glue Data Catalog**. Los crawlers lo llenan
automáticamente, y el EMR está configurado para usarlo como metastore de Hive y
Spark, así que las tablas creadas con DDL de Hive también quedan en Glue y se ven
desde Athena.

| Base de datos | Cómo se llena | Tablas |
|---------------|---------------|--------|
| `clima_raw` | crawlers `crawler_clima_raw` y `crawler_clima_raw_archivos` (clasificador `;`) | `departamento`, `ciudad`, `api_openmeteo`, `estaciones` |
| `clima_trusted` | crawler `crawler_clima_trusted` | `dim_ciudad`, `clima_diario` (particiones `anio`,`mes`), `oni_mensual` |
| `clima_refined` | crawler `crawler_clima_refined` (después del punto 7) | `clima_mensual`, `p1_…` … `p8_…` |
| `clima_hive` | **DDL de Hive** en EMR (`hive_ddl.sql`) | `raw_estaciones`, `dim_ciudad`, `clima_diario`, `oni_mensual` |

> Note que en `clima_raw.ciudad` el crawler infiere `id_ciudad` como `bigint` y
> pierde el cero de `05001`. Por eso el job del punto 4 lee raw como texto: es un
> buen ejemplo de por qué raw no se consulta directamente para el negocio.

## Pasos

### 1. Crawlers de Glue (CloudShell)
```bash
source config.env
bash 05-catalogacion/01_crawlers_glue.sh            # raw + trusted
```
Consola: Glue → Data Catalog → Crawlers (pantallazo de estado *Succeeded*) y
Databases → Tables (pantallazo del esquema de `clima_diario` con sus particiones).

### 2. EMR + Hive
```bash
bash 05-catalogacion/02_crear_emr.sh                # 8-12 min
aws s3 cp 05-catalogacion/hive_ddl.sql $SCRIPTS/
ssh -i labsuser.pem hadoop@<master-dns>
```
En el master:
```bash
aws s3 cp s3://<bucket>/scripts/hive_ddl.sql .
hive --hivevar BUCKET=<bucket> -f hive_ddl.sql
```
También puede usar **Hue** (`http://<master-dns>:8888`) con un túnel SSH o
abriendo el puerto en el security group del master.

### 3. Orquestación automática diaria
```bash
bash 05-catalogacion/03_workflow_automatico.sh
aws glue start-workflow-run --name clima_workflow_diario   # prueba inmediata
```
Pantallazo: Glue → Workflows → `clima_workflow_diario` → *Graph* con todo en verde.

### 4. Catálogo de refined (después del punto 7)
```bash
bash 05-catalogacion/01_crawlers_glue.sh --refined
```

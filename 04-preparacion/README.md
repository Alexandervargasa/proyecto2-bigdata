# Punto 4 — Preparación de datos: raw (bronze) → trusted (silver)

Herramientas: **AWS Glue** (job tipo Spark, Glue 4.0) con **Apache Spark (PySpark)**.
El mismo script corre también con `spark-submit` en EMR o en local.

## Transformaciones que hace `glue_raw_a_trusted.py`

| Problema en raw | Solución en trusted |
|-----------------|---------------------|
| Códigos DANE con cero a la izquierda (`05001`) | Se lee todo como texto y se usa `lpad`; nunca `inferSchema` |
| Snapshots diarios repetidos de MariaDB | Se toma la última `fecha_ingesta` |
| CSV legado con `;`, coma decimal y fecha `dd/mm/aaaa` | `sep=';'`, `regexp_replace(',', '.')`, `to_date(..., 'dd/MM/yyyy')` |
| Faltantes codificados como `-999` | Se convierten a `null` |
| JSON con arreglos paralelos (`time[]`, `temperature_2m_max[]`, …) | `posexplode` → una fila por ciudad y día |
| Días repetidos entre ingestas de la API (ventana de 10 días) | `row_number()` por (`id_ciudad`, `fecha`): gana API sobre archivo y la ingesta más reciente |
| Valores físicamente imposibles | Rango −10..50 °C, 0..500 mm, 0..200 km/h; `temp_max < temp_min` → `null` |
| `temp_media` faltante | (`temp_max` + `temp_min`) / 2 |
| Ciudades que no están en el maestro | Se descartan (`left_semi`) y se cuentan en el log |
| ONI en texto de ancho fijo y por trimestre (`DJF`, `JFM`…) | `split` por espacios; temporada → mes central; fase El Niño / La Niña / Neutral |
| Formatos CSV/JSON/TXT | Todo queda en **Parquet**; `clima_diario` particionado por `anio`/`mes` |

Salida:
```
trusted/dim_ciudad/            (33 filas)
trusted/clima_diario/anio=*/mes=*/
trusted/oni_mensual/
```

## Ejecutar (CloudShell)
```bash
source config.env
bash 04-preparacion/desplegar_glue_job.sh
```
La ejecución automática diaria la programa el **Glue Workflow** del punto 5
(`05-catalogacion/03_workflow_automatico.sh`): job → crawler de trusted.

### Por consola (para pantallazos)
Glue → ETL jobs → *Script editor* → Spark → *Upload* `glue_raw_a_trusted.py` →
Job details: IAM role `LabRole`, Glue 4.0, G.1X, 2 workers → Advanced →
Job parameters: `--RAW s3://<bucket>/raw`, `--TRUSTED s3://<bucket>/trusted` → Run.

## Ver el log de calidad
Glue → Job runs → *Output logs*. Busque las líneas `[raw_a_trusted]`: muestran
filas leídas por fuente, filas finales, huérfanas y nulos por columna. Eso sirve
como evidencia de la preparación.

## Alternativa en EMR
```bash
spark-submit s3://<bucket>/scripts/glue_raw_a_trusted.py --RAW s3://<bucket>/raw --TRUSTED s3://<bucket>/trusted
```

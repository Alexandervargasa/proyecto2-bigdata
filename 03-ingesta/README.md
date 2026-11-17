# Punto 3 — Ingesta automática hacia el datalake (S3)

| Fuente | Mecanismo automático | Frecuencia | Destino (zona raw / bronze) |
|--------|----------------------|------------|-----------------------------|
| RDS MariaDB | `cron` en EC2 → `ingesta_mariadb.py` (pymysql + boto3) | diario 05:00 COT | `raw/mariadb/<tabla>/fecha_ingesta=AAAA-MM-DD/` |
| Archivos EC2 | `cron` en EC2 → `ingesta_archivos.sh` (`aws s3 sync`) | cada hora | `raw/archivos_ec2/estaciones/anio=AAAA/` |
| Open-Meteo + NOAA | **Lambda** `ingesta_api_clima` + regla **EventBridge** | diario 05:30 COT | `raw/api_openmeteo/fecha_ingesta=.../`, `raw/api_noaa/oni/fecha_ingesta=.../` |

Raw guarda los datos **sin transformar** (CSV con `;` y coma decimal, JSON tal
cual responde la API, el .txt de NOAA). La limpieza es trabajo del punto 4.

## Pasos

### 1. Crear el bucket (CloudShell)
```bash
source config.env
bash 03-ingesta/00_crear_datalake.sh
```

### 2. Ingesta desde el EC2 (por SSH en el EC2)
```bash
cd ~/proyecto2-bigdata-clima && source config.env
# prueba manual (evidencia)
python3 03-ingesta/ec2/ingesta_mariadb.py
bash    03-ingesta/ec2/ingesta_archivos.sh
# programación automática
bash 03-ingesta/ec2/instalar_cron.sh
```

### 3. Lambda para las URLs (CloudShell)
Requiere que ya exista el snapshot `raw/mariadb/ciudad/` (paso 2).
```bash
bash 03-ingesta/lambda_ingesta_api/desplegar.sh
```
El script crea la función con `LabRole`, crea la regla `ingesta-api-clima-diaria`
y hace la **carga inicial** desde `2025-01-01`. Las ejecuciones diarias siguientes
traen solo los últimos 10 días.

### 4. Verificar
```bash
aws s3 ls s3://$BUCKET/raw/ --recursive | head -20
aws s3 cp s3://$BUCKET/raw/api_noaa/oni/ - --recursive | head -5
```

## Evidencias sugeridas
1. `crontab -l` en el EC2 y `tail ~/logs/*.log`.
2. Consola Lambda → `ingesta_api_clima` → pestaña *Monitor* / CloudWatch logs.
3. EventBridge → Rules → `ingesta-api-clima-diaria` (cron).
4. Consola S3 mostrando las carpetas `raw/mariadb`, `raw/archivos_ec2`, `raw/api_openmeteo`, `raw/api_noaa`.

## Alternativas que se consideraron
- **AWS DMS / Glue JDBC** para MariaDB: más "empresariales", pero en Learner Lab
  piden conexiones VPC, endpoints S3 y permisos que suelen fallar. Puede
  mencionarse como mejora.
- **Kinesis Firehose** para la API: sobra para un lote diario.

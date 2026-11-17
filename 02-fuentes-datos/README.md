# Punto 2 — Fuentes de datos: RDS MariaDB, archivos en EC2 y URLs

Todo se ejecuta con las credenciales del **AWS Academy Learner Lab**, en
**us-east-1**. Lo más cómodo es **AWS CloudShell** (ya trae AWS CLI y credenciales):
en la consola, ícono `>_` arriba a la derecha.

## 0. Preparar la configuración (una vez)

```bash
git clone https://github.com/SU_USUARIO/proyecto2-bigdata-clima.git
cd proyecto2-bigdata-clima
cp config.env.example config.env
nano config.env        # cambie DB_PASSWORD y REPO_URL
source config.env
```

## 1. Red: security groups

```bash
bash 02-fuentes-datos/01_crear_red.sh
```
El RDS **no** es público: solo acepta el puerto 3306 desde el security group del EC2.

## 2. Fuente 1 — RDS MariaDB

```bash
bash 02-fuentes-datos/02_crear_rds.sh      # ~10 min
# copie el endpoint impreso en config.env -> DB_HOST
```
Por consola (equivalente, útil para pantallazos): RDS → Create database → Standard
create → MariaDB → Free tier / `db.t3.micro` → identificador `clima-mariadb` →
usuario `admin` → Public access **No** → VPC security group `sg-clima-rds`.

## 3. Fuente 2 — EC2 servidor de archivos

```bash
bash 02-fuentes-datos/03_crear_ec2.sh
```
Descargue `labsuser.pem` desde *AWS Details* del Learner Lab y entre:
```bash
chmod 400 labsuser.pem
ssh -i labsuser.pem ec2-user@<DNS-publico>
```
Dentro del EC2:
```bash
cd ~/proyecto2-bigdata-clima
cp config.env.example config.env && nano config.env   # mismo contenido, con DB_HOST
source config.env

# 3.1 cargar la base de datos (esquema + 33 departamentos + 33 ciudades)
bash 02-fuentes-datos/04_cargar_mariadb.sh

# 3.2 generar los archivos históricos 2022-2024 (33 ciudades x 3 años = 99 CSV)
python3 02-fuentes-datos/ec2/generar_archivos_estaciones.py
ls -R /opt/datos/estaciones | head
head -3 /opt/datos/estaciones/anio=2024/EST_05001_2024.csv
```

## 4. Fuente 3 — URLs en Internet

No hay que crear nada: son servicios públicos que la ingesta (punto 3) consulta.

| URL | Ejemplo |
|-----|---------|
| Open-Meteo Historical Weather API | `https://archive-api.open-meteo.com/v1/archive?latitude=6.2442&longitude=-75.5812&start_date=2025-04-01&end_date=2025-04-03&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,wind_speed_10m_max&timezone=America/Bogota` |
| NOAA CPC Índice ONI | `https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt` |

Abra ambas en el navegador para el pantallazo de evidencia.

## Evidencias sugeridas para el documento
1. RDS `clima-mariadb` en estado *Available* (consola RDS).
2. Salida de `04_cargar_mariadb.sh` con los conteos y el top 5 por altitud.
3. EC2 `clima-fuentes` *Running* con el rol `LabInstanceProfile`.
4. `ls -R /opt/datos/estaciones` y `head` de un CSV mostrando el formato legado.
5. Las dos URLs abiertas en el navegador.

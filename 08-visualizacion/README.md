# Punto 8 — Visualización (matplotlib) y aplicación Streamlit expuesta con API Gateway

```
Streamlit (EC2 :8501) ──HTTP──▶ API Gateway (HTTP API) ──▶ Lambda api_clima ──▶ Athena ──▶ S3 refined
```

## 8a. matplotlib — 9 gráficas PNG
```bash
pip3 install --user pandas pyarrow matplotlib
python3 08-visualizacion/matplotlib/graficas.py --refined s3://$BUCKET/refined --salida graficas
```
Genera `p1_…png` a `p8_…png` y `serie_mensual_ciudades.png`. Péguelas en el documento.

## 8b. API REST con API Gateway + Lambda + Athena (CloudShell)
```bash
source config.env
bash 08-visualizacion/api_lambda/desplegar_api.sh
# copie la línea export API_URL=... a config.env (en CloudShell y en el EC2)
curl $API_URL/preguntas/1
```

| Ruta | Respuesta |
|------|-----------|
| `GET /preguntas` | Lista de las 8 preguntas |
| `GET /preguntas/{n}` | Filas de la tabla refined de la pregunta *n* |
| `GET /ciudades` | Maestro de ciudades |
| `GET /clima-mensual?ciudad=05001&desde=2024-01&hasta=2025-12` | Serie mensual de una ciudad |

Decisiones:
- **HTTP API** (no REST API): más barato y simple; la ruta `$default` envía todo a
  la Lambda y la Lambda enruta por `rawPath`.
- **Sin inyección SQL**: los parámetros se validan con regex y viajan a Athena como
  `ExecutionParameters` (`?`), nunca pegados al texto del SQL.
- **Caché de 10 min** en la Lambda: refined cambia una vez al día y Athena tarda
  1-3 s por consulta.
- Límite de 29 s del timeout de API Gateway: por eso la API lee tablas **refined**
  (ya agregadas, pocas filas) y no `clima_diario` completa.

## 8c. Streamlit (en el EC2)
```bash
cd ~/proyecto2-bigdata-clima && git pull && source config.env
bash 08-visualizacion/streamlit/instalar_servicio.sh
# abra http://<IP-publica-EC2>:8501
```
Tres pestañas: las 8 preguntas con su gráfica y tabla, un explorador por ciudad
(serie mensual de temperatura y lluvia) y la documentación de la API.

### ¿Por qué Streamlit no va "detrás" de API Gateway?
Streamlit mantiene una conexión **WebSocket** (`/_stcore/stream`). Un HTTP API
de API Gateway con integración HTTP proxy hacia el EC2 entrega el HTML, pero no
hace el *upgrade* a WebSocket, así que la app se queda en "Please wait…". Por eso
la arquitectura es *Streamlit consume una API expuesta por API Gateway*. Si el
profesor exige que la URL de la app también pase por API Gateway, se puede
agregar una ruta `ANY /app/{proxy+}` con integración `HTTP_PROXY` a
`http://<ec2>:8501/{proxy}`: sirve como evidencia de enrutamiento, pero presente
esa limitación en el documento. Para producción se usaría un Application Load
Balancer o CloudFront delante del EC2.

## Evidencias sugeridas
1. Las PNG de matplotlib.
2. Consola API Gateway → `clima-api` → *Routes* / *Integrations* y la URL en el navegador mostrando JSON.
3. CloudWatch logs de `api_clima`.
4. Pantallazos de la app Streamlit (pregunta + explorador por ciudad).

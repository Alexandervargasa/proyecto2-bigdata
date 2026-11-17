# Pruebas locales (sin AWS)

Valida la lógica de los puntos 4, 6, 7 y 8 en su computador, con datos
**sintéticos** que tienen exactamente los formatos de raw (CSV de MariaDB, CSV
legado con `;`, JSONL de Open-Meteo, TXT de NOAA). Incluye defectos a propósito
(`-999`, un valor fuera de rango, una ciudad huérfana, días repetidos entre
ingestas) para comprobar la preparación.

```bash
pip install pyspark==3.5.3 pyarrow pandas matplotlib duckdb streamlit   # y Java 11+
bash pruebas_locales/ejecutar_local.sh

# app Streamlit contra una API local que ejecuta el handler real de la Lambda
python3 pruebas_locales/api_local.py &
API_URL=http://localhost:8000 streamlit run 08-visualizacion/streamlit/app.py
```

Los números que salen aquí **no son reales**; no los use en el informe.

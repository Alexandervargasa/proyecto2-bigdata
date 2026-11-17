"""
Punto 8c — App Streamlit que consume la API publicada en API Gateway.

    export API_URL=https://xxxx.execute-api.us-east-1.amazonaws.com
    streamlit run app.py --server.port 8501 --server.address 0.0.0.0
"""
import inspect
import os

import altair as alt
import pandas as pd
import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "").rstrip("/")

# Compatibilidad: Streamlit reciente usa width="stretch"; las versiones que se instalan
# con Python 3.9 (Amazon Linux 2023 en el EC2) solo conocen use_container_width=True.
if "width" in inspect.signature(st.altair_chart).parameters:
    ANCHO = {"width": "stretch"}
else:
    ANCHO = {"use_container_width": True}
NARANJA, AZUL, AQUA = "#eb6834", "#2a78d6", "#1baf7a"
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

st.set_page_config(page_title="Clima Colombia · Big Data", page_icon="🌦️", layout="wide")


@st.cache_data(ttl=600, show_spinner="Consultando la API…")
def api(ruta, **params):
    r = requests.get(f"{API_URL}{ruta}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


st.title("Clima de las capitales de Colombia")
st.caption("Datalake en S3 · Glue · EMR · Athena — datos servidos por API Gateway + Lambda")
if not API_URL:
    st.error("Defina la variable de entorno API_URL con la URL de API Gateway.")
    st.stop()

tab_preg, tab_ciudad, tab_api = st.tabs(["Preguntas de negocio", "Explorar una ciudad", "Sobre la API"])

# ------------------------------------------------------------------ preguntas
with tab_preg:
    preguntas = api("/preguntas")
    opciones = {f"P{p['id']} · {p['pregunta']}": p["id"] for p in preguntas}
    elegida = st.selectbox("Pregunta", list(opciones))
    n = opciones[elegida]
    df = pd.DataFrame(api(f"/preguntas/{n}")["filas"])

    if df.empty:
        st.info("La consulta no devolvió filas.")
    elif n == 1:
        c1, c2 = st.columns([1, 2])
        top = df.iloc[0]
        c1.metric("Ciudad más caliente (abril 2025)", top["ciudad"], f"{top['temp_max_promedio']:.1f} °C de máxima promedio")
        c2.altair_chart(alt.Chart(df).mark_bar(color=NARANJA, cornerRadiusEnd=4).encode(
            x=alt.X("temp_max_promedio:Q", title="°C"),
            y=alt.Y("ciudad:N", sort="-x", title=None),
            tooltip=list(df.columns)), **ANCHO)
    elif n == 2:
        st.altair_chart(alt.Chart(df).mark_bar(color=AZUL, cornerRadiusEnd=4).encode(
            x=alt.X("temp_media_2024:Q", title="Temperatura media 2024 (°C)"),
            y=alt.Y("departamento:N", sort="-x", title=None), tooltip=list(df.columns)
        ).properties(height=700), **ANCHO)
    elif n == 3:
        st.altair_chart(alt.Chart(df).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X("region_natural:N", title=None), xOffset="anio:N",
            y=alt.Y("precip_anual_promedio_mm:Q", title="mm / año"),
            color=alt.Color("anio:O", scale=alt.Scale(scheme="blues"), title="Año"),
            tooltip=list(df.columns)), **ANCHO)
    elif n == 4:
        puntos = alt.Chart(df).mark_circle(size=80, color=AZUL).encode(
            x=alt.X("altitud_m:Q", title="Altitud (m)"), y=alt.Y("temp_media:Q", title="Temperatura media (°C)"),
            tooltip=list(df.columns))
        st.altair_chart(puntos + puntos.transform_regression("altitud_m", "temp_media")
                        .mark_line(color="#52514e", strokeDash=[6, 4]), **ANCHO)
    elif n == 5:
        df["mes_txt"] = df["mes"].map(lambda m: MESES[m - 1])
        st.altair_chart(alt.Chart(df).mark_rect().encode(
            x=alt.X("mes_txt:N", sort=MESES, title=None), y=alt.Y("region_natural:N", title=None),
            color=alt.Color("precip_mensual_promedio_mm:Q", scale=alt.Scale(scheme="blues"), title="mm/mes"),
            tooltip=["region_natural", "mes", "precip_mensual_promedio_mm", "puesto"]
        ).properties(height=320), **ANCHO)
    elif n == 6:
        largo = df.melt(id_vars=["ciudad"], value_vars=["dias_2024", "dias_2025"], var_name="anio", value_name="dias")
        st.altair_chart(alt.Chart(largo).mark_bar(cornerRadiusEnd=4).encode(
            y=alt.Y("ciudad:N", sort=list(df["ciudad"]), title=None), yOffset="anio:N",
            x=alt.X("dias:Q", title="Días con Tmax ≥ 35 °C"),
            color=alt.Color("anio:N", scale=alt.Scale(domain=["dias_2024", "dias_2025"], range=[NARANJA, AZUL]),
                            title="Año"), tooltip=["ciudad", "anio", "dias"]
        ).properties(height=650), **ANCHO)
    elif n == 7:
        st.altair_chart(alt.Chart(df).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X("region_natural:N", title=None), xOffset="fase_enso:N",
            y=alt.Y("anomalia_pct:Q", title="% vs. promedio del mes"),
            color=alt.Color("fase_enso:N", scale=alt.Scale(domain=["El Niño", "Neutral", "La Niña"],
                                                            range=[NARANJA, AQUA, AZUL]), title="Fase"),
            tooltip=list(df.columns)), **ANCHO)
    elif n == 8:
        df["millones_persona_dias"] = df["persona_dias_expuestos"] / 1e6
        st.altair_chart(alt.Chart(df).mark_bar(color=NARANJA, cornerRadiusEnd=4).encode(
            x=alt.X("millones_persona_dias:Q", title="Millones de persona-días"),
            y=alt.Y("departamento:N", sort="-x", title=None), tooltip=list(df.columns)),
            **ANCHO)

    with st.expander("Ver tabla"):
        st.dataframe(df, hide_index=True, **ANCHO)

# ------------------------------------------------------------------ ciudad
with tab_ciudad:
    ciudades = pd.DataFrame(api("/ciudades"))
    c1, c2, c3 = st.columns([2, 1, 1])
    nombre = c1.selectbox("Ciudad", ciudades["ciudad"], index=int((ciudades["ciudad"] == "Medellín").idxmax()))
    desde = c2.text_input("Desde (AAAA-MM)", "2022-01")
    hasta = c3.text_input("Hasta (AAAA-MM)", "2026-12")
    fila = ciudades[ciudades["ciudad"] == nombre].iloc[0]
    serie = pd.DataFrame(api("/clima-mensual", ciudad=fila["id_ciudad"], desde=desde, hasta=hasta))
    if serie.empty:
        st.info("Sin datos para ese periodo.")
    else:
        serie["periodo"] = pd.to_datetime(serie["anio"].astype(str) + "-" + serie["mes"].astype(str) + "-01")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Altitud", f"{fila['altitud_m']:,} m")
        k2.metric("Temp. media del periodo", f"{serie['temp_media_prom'].mean():.1f} °C")
        k3.metric("Lluvia total", f"{serie['precip_total_mm'].sum():,.0f} mm")
        k4.metric("Días ≥ 35 °C", int(serie["dias_calor_extremo"].sum()))
        temp = (serie.rename(columns={"temp_max_prom": "Máxima", "temp_media_prom": "Media", "temp_min_prom": "Mínima"})
                     .melt(id_vars=["periodo"], value_vars=["Máxima", "Media", "Mínima"], var_name="serie", value_name="°C"))
        st.altair_chart(alt.Chart(temp).mark_line(strokeWidth=2).encode(
            x=alt.X("periodo:T", title=None), y=alt.Y("°C:Q", scale=alt.Scale(zero=False)),
            color=alt.Color("serie:N", scale=alt.Scale(domain=["Máxima", "Media", "Mínima"],
                                                       range=[NARANJA, AQUA, AZUL]), title=None),
            tooltip=["periodo:T", "serie", "°C"]).properties(title=f"Temperatura mensual · {nombre}"),
            **ANCHO)
        st.altair_chart(alt.Chart(serie).mark_bar(color=AZUL, cornerRadiusEnd=3).encode(
            x=alt.X("periodo:T", title=None), y=alt.Y("precip_total_mm:Q", title="mm"),
            tooltip=["periodo:T", "precip_total_mm", "fase_enso"]).properties(title="Lluvia mensual"),
            **ANCHO)

# ------------------------------------------------------------------ api
with tab_api:
    st.markdown(f"""
**URL base:** `{API_URL}`

| Ruta | Qué devuelve |
|------|--------------|
| `GET /preguntas` | Lista de preguntas |
| `GET /preguntas/{{n}}` | Respuesta de la pregunta *n* (tabla refined vía Athena) |
| `GET /ciudades` | Maestro de ciudades |
| `GET /clima-mensual?ciudad=05001&desde=2024-01&hasta=2025-12` | Serie mensual de una ciudad |

Flujo: **Streamlit (EC2) → API Gateway → Lambda `api_clima` → Athena → S3 refined**.
""")
    st.code(f"curl {API_URL}/preguntas/1", language="bash")

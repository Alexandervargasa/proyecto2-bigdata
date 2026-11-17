#!/usr/bin/env python3
"""
Punto 8a — Visualización con matplotlib a partir de la zona REFINED.

    # desde S3 (CloudShell o EC2 con LabInstanceProfile)
    python3 graficas.py --refined s3://<bucket>/refined --salida ./graficas
    # local
    python3 graficas.py --refined ../../pruebas_locales/datalake/refined --salida ./graficas

Requiere: pip install pandas pyarrow matplotlib
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

# Paleta categórica validada (orden fijo) + tinta de texto
AZUL, NARANJA, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
TINTA, TINTA_2, REJILLA = "#0b0b0b", "#52514e", "#e4e3df"
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

plt.rcParams.update({
    "figure.dpi": 120, "savefig.dpi": 150, "font.size": 10,
    "axes.edgecolor": REJILLA, "axes.labelcolor": TINTA_2, "axes.titleweight": "bold",
    "axes.titlecolor": TINTA, "xtick.color": TINTA_2, "ytick.color": TINTA_2,
    "axes.grid": True, "grid.color": REJILLA, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "axes.axisbelow": True,
})


def leer(refined, tabla):
    ruta = f"{refined.rstrip('/')}/{tabla}"
    if ruta.startswith("s3://"):
        from pyarrow import fs
        s3 = fs.S3FileSystem(region=os.environ.get("AWS_REGION", "us-east-1"))
        return pq.read_table(ruta[5:], filesystem=s3).to_pandas()
    return pq.read_table(ruta).to_pandas()


def guardar(fig, salida, nombre):
    fig.tight_layout()
    ruta = os.path.join(salida, nombre)
    fig.savefig(ruta, bbox_inches="tight")
    plt.close(fig)
    print("  ", ruta)


def barras_h(ax, etiquetas, valores, color, fmt="{:.1f}"):
    ax.barh(etiquetas, valores, color=color, height=0.7)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    for y, v in enumerate(valores):
        ax.text(v, y, " " + fmt.format(v), va="center", fontsize=8, color=TINTA_2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refined", required=True)
    ap.add_argument("--salida", default="graficas")
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    R = a.refined

    # P1
    d = leer(R, "p1_ciudad_mas_caliente_abr2025")
    fig, ax = plt.subplots(figsize=(7, 3.2))
    barras_h(ax, d["ciudad"], d["temp_max_promedio"], NARANJA)
    ax.set(title="P1 · Ciudades más calientes, abril 2025", xlabel="Temperatura máxima promedio (°C)")
    ax.set_xlim(d["temp_max_promedio"].min() - 2, d["temp_max_promedio"].max() + 1)
    guardar(fig, a.salida, "p1_ciudad_mas_caliente.png")

    # P2
    d = leer(R, "p2_ranking_deptos_temp_2024").sort_values("puesto")
    fig, ax = plt.subplots(figsize=(7, 8))
    barras_h(ax, d["departamento"], d["temp_media_2024"], AZUL)
    ax.set(title="P2 · Departamentos por temperatura media, 2024", xlabel="°C")
    guardar(fig, a.salida, "p2_ranking_departamentos.png")

    # P3
    d = leer(R, "p3_lluvia_anual_region")
    piv = d.pivot(index="region_natural", columns="anio", values="precip_anual_promedio_mm")
    piv = piv.loc[piv.mean(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(8, 4))
    anchos = 0.8 / len(piv.columns)
    tonos = ["#9ec5f4", "#5b9ae8", "#2a78d6", "#1a4f91"][-len(piv.columns):]   # secuencial de un tono
    for i, anio in enumerate(piv.columns):
        ax.bar([x + i * anchos for x in range(len(piv))], piv[anio], width=anchos * 0.92,
               color=tonos[i], label=str(anio))
    ax.set_xticks([x + anchos * (len(piv.columns) - 1) / 2 for x in range(len(piv))], piv.index)
    ax.grid(axis="x", visible=False)
    ax.set(title="P3 · Lluvia anual promedio por ciudad, según región", ylabel="mm / año")
    ax.legend(title="Año", frameon=False, ncol=len(piv.columns))
    guardar(fig, a.salida, "p3_lluvia_region.png")

    # P4
    pts = leer(R, "p4_detalle_ciudades")
    reg = leer(R, "p4_altitud_vs_temperatura").iloc[0]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.scatter(pts["altitud_m"], pts["temp_media"], s=36, color=AZUL, edgecolor="white", linewidth=1.5, zorder=3)
    xs = [0, pts["altitud_m"].max()]
    ax.plot(xs, [reg["temp_estimada_nivel_mar"] + reg["grados_por_1000m"] * x / 1000 for x in xs],
            color=TINTA_2, linewidth=1.5, linestyle="--")
    for _, f in pts[pts["ciudad"].isin(["Bogotá", "Tunja", "Medellín", "Cali", "Santa Marta", "Pasto"])].iterrows():
        ax.annotate(f["ciudad"], (f["altitud_m"], f["temp_media"]), xytext=(5, 4),
                    textcoords="offset points", fontsize=8, color=TINTA_2)
    ax.set(title=f"P4 · Altitud vs temperatura  (r = {reg['correlacion']}, "
                 f"{reg['grados_por_1000m']} °C por 1.000 m)",
           xlabel="Altitud (m s. n. m.)", ylabel="Temperatura media (°C)")
    guardar(fig, a.salida, "p4_altitud_temperatura.png")

    # P5 (mapa de calor secuencial de un tono)
    d = leer(R, "p5_lluvia_mensual_region")
    piv = d.pivot(index="region_natural", columns="mes", values="precip_mensual_promedio_mm")
    fig, ax = plt.subplots(figsize=(9, 3.6))
    im = ax.imshow(piv.values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(12), MESES)
    ax.set_yticks(range(len(piv)), piv.index)
    ax.grid(False)
    for (i, j), v in pd.DataFrame(piv.values).stack().items():
        ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7,
                color="white" if v > piv.values.mean() else TINTA)
    fig.colorbar(im, ax=ax, label="mm / mes")
    ax.set_title("P5 · Lluvia mensual promedio por región (régimen de lluvias)")
    guardar(fig, a.salida, "p5_meses_lluviosos.png")

    # P6
    d = leer(R, "p6_dias_calor_extremo").head(15)
    fig, ax = plt.subplots(figsize=(8, 5.5))
    y = range(len(d))
    ax.barh([i - 0.2 for i in y], d["dias_2024"], height=0.38, color=NARANJA, label="2024")
    ax.barh([i + 0.2 for i in y], d["dias_2025"], height=0.38, color=AZUL, label="2025")
    ax.set_yticks(list(y), d["ciudad"])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False)
    ax.set(title="P6 · Días con temperatura máxima ≥ 35 °C", xlabel="días en el año")
    guardar(fig, a.salida, "p6_dias_calor.png")

    # P7
    d = leer(R, "p7_lluvia_vs_enso")
    piv = d.pivot(index="region_natural", columns="fase_enso", values="anomalia_pct")
    colores = {"El Niño": NARANJA, "La Niña": AZUL, "Neutral": AQUA}
    fig, ax = plt.subplots(figsize=(8, 4))
    fases = [f for f in ["El Niño", "Neutral", "La Niña"] if f in piv.columns]
    w = 0.8 / len(fases)
    for i, f in enumerate(fases):
        ax.bar([x + i * w for x in range(len(piv))], piv[f], width=w * 0.92, color=colores[f], label=f)
    ax.axhline(0, color=TINTA_2, linewidth=0.8)
    ax.set_xticks([x + w * (len(fases) - 1) / 2 for x in range(len(piv))], piv.index)
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, ncol=3)
    ax.set(title="P7 · Anomalía de lluvia mensual según fase ENSO", ylabel="% vs. promedio del mes")
    guardar(fig, a.salida, "p7_lluvia_enso.png")

    # P8
    d = leer(R, "p8_poblacion_expuesta_calor")
    fig, ax = plt.subplots(figsize=(7, 4))
    barras_h(ax, d["departamento"], d["persona_dias_expuestos"] / 1e6, NARANJA, fmt="{:,.0f} M")
    ax.set(title="P8 · Población expuesta a calor extremo, 2024", xlabel="millones de persona-días")
    guardar(fig, a.salida, "p8_poblacion_expuesta.png")

    # Serie mensual de 3 ciudades (clima_mensual)
    d = leer(R, "clima_mensual")
    d["periodo"] = pd.to_datetime(dict(year=d["anio"], month=d["mes"], day=1))
    fig, ax = plt.subplots(figsize=(9, 3.8))
    for ciudad, color in (("Barranquilla", NARANJA), ("Medellín", AQUA), ("Bogotá", AZUL)):
        s = d[d["ciudad"] == ciudad].sort_values("periodo")
        ax.plot(s["periodo"], s["temp_media_prom"], color=color, linewidth=2, label=ciudad)
        ax.annotate(ciudad, (s["periodo"].iloc[-1], s["temp_media_prom"].iloc[-1]), xytext=(4, 0),
                    textcoords="offset points", fontsize=8, color=TINTA_2, va="center")
    ax.legend(frameon=False, ncol=3, loc="upper left")
    ax.set(title="Temperatura media mensual: costa, valle y altiplano", ylabel="°C")
    guardar(fig, a.salida, "serie_mensual_ciudades.png")


if __name__ == "__main__":
    main()

"""
Dashboard de Rotación de Inventario — Chile · México · Perú
============================================================
App Streamlit que replica la lógica de análisis de rotación trabajada
para los 3 países: cruce ventas vs stock, rotación, clasificación,
recomendaciones y resumen ejecutivo.

Uso:
    pip install streamlit pandas plotly openpyxl
    streamlit run app.py
"""

import io
from datetime import date, datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import matriz_logic as ml

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Rotación de Inventario · CL · MX · PE",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Paleta tipo semáforo ──
COL = {
    "estrella": "#1B9E5A", "buena": "#7FC241", "media": "#F2C037",
    "baja": "#F08A24", "nula": "#E04D4D", "sin_stock": "#9AA5B1",
    "ink": "#1A2B4A", "mid": "#2E4A7A", "bg": "#F0F4F9",
}
CLASS_COLOR = {
    "ESTRELLA": COL["estrella"], "BUENA ROTACION": COL["buena"],
    "ROTACION MEDIA": COL["media"], "BAJA ROTACION": COL["baja"],
    "NULA ROTACION": COL["nula"], "SIN STOCK": COL["sin_stock"],
}
CLASS_EMOJI = {
    "ESTRELLA": "⭐", "BUENA ROTACION": "🟢", "ROTACION MEDIA": "🟡",
    "BAJA ROTACION": "🟠", "NULA ROTACION": "🔴", "SIN STOCK": "⚪",
}
REC_PRIORITY = {
    "LIQUIDAR": 1, "BAJAR PRECIO DE VENTA": 2, "NO COMPRAR MÁS": 3,
    "BAJAR PRECIO DE RETOMA": 4, "REPONER INVENTARIO": 2, "REVISAR STOCK": 4,
    "MANTENER": 5, "PRIORIZAR COMPRA": 6, "SIN STOCK": 7,
}
PRI_LABEL = {1: "🔴 URGENTE", 2: "🟠 ALTA", 3: "🟠 ALTA", 4: "🟡 MEDIA",
             5: "🟢 BAJA", 6: "🟢 BAJA", 7: "—"}

CSS = """
<style>
    .main > div { padding-top: 1.2rem; }
    .stMetric { background:#fff; border:1px solid #E2E8F0; border-radius:12px;
                padding:14px 16px; box-shadow:0 1px 3px rgba(0,0,0,.05); }
    h1,h2,h3 { color:#1A2B4A; }
    div[data-testid="stMetricValue"] { font-size:1.4rem; }
    .country-pill { display:inline-block; padding:4px 14px; border-radius:20px;
                    color:#fff; font-weight:700; font-size:.85rem; margin-right:6px;}
    .stDataFrame { border-radius:10px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

COUNTRY_META = {
    "Chile":  {"code": "CL", "flag": "🇨🇱", "cur": "CLP", "fmt": "{:,.0f}"},
    "México": {"code": "MX", "flag": "🇲🇽", "cur": "MXN", "fmt": "{:,.2f}"},
    "Perú":   {"code": "PE", "flag": "🇵🇪", "cur": "PEN", "fmt": "{:,.2f}"},
}


# ──────────────────────────────────────────────────────────────────────────────
# CARGA Y NORMALIZACIÓN DE ARCHIVOS
# ──────────────────────────────────────────────────────────────────────────────
def _read_excel_smart(file, kind):
    """Lee un excel detectando la fila de encabezado (0 o 5)."""
    raw = file.read()
    for header in (0, 5):
        try:
            df = pd.read_excel(io.BytesIO(raw), header=header)
        except Exception:
            continue
        cols = [str(c).strip() for c in df.columns]
        if kind == "stock" and "Producto" in cols and "Stock" in cols:
            df.columns = cols
            return df
        if kind == "ventas" and "Tipo Movimiento" in cols and "Producto / Servicio" in cols:
            df.columns = cols
            return df
    # fallback header=0
    df = pd.read_excel(io.BytesIO(raw), header=0)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _pick_cost_col(v):
    for c in ["Costo neto unitario", "Costo Neto Unitario", "Costo Neto unitario"]:
        if c in v.columns:
            return c
    return None


def process_country(ventas_file, stock_file, days):
    """Replica la lógica de rotación trabajada en el análisis."""
    ventas = _read_excel_smart(ventas_file, "ventas")
    stock = _read_excel_smart(stock_file, "stock")

    cost_col = _pick_cost_col(ventas)

    v = ventas[(ventas["Tipo Movimiento"] == "venta") &
               (~ventas["Tipo de Producto / Servicio"].isin(["Sin Tipo"]))].copy()
    # Nombre fusionado: junta variantes de color en un solo modelo (ej. "IPHONE 13 128GB")
    v["pn"] = v["Producto / Servicio"].apply(ml.fusionar_variante)
    v["vn"] = ""

    s = stock[stock["Producto"].notna()].copy()
    s["pn"] = s["Producto"].apply(ml.fusionar_variante)
    s["vn"] = ""
    s["Tipo de Producto"] = s["Tipo de Producto"].fillna("SIN TIPO")

    agg_v = {
        "Unidades_vendidas": ("Cantidad", "sum"),
        "Venta_costo_total": ("Costo Total Neto", "sum"),
        "Venta_neta_total": ("Venta Total Neta", "sum"),
        "Precio_prom_venta": ("Precio Neto Unitario", "mean"),
        "Margen_total": ("Margen", "sum"),
    }
    if cost_col:
        agg_v["Costo_prom_venta"] = (cost_col, lambda x: x[x > 0].mean() if (x > 0).any() else 0)
    va = v.groupby(["pn", "vn", "Tipo de Producto / Servicio"]).agg(**agg_v).reset_index()

    sa = s.groupby(["pn", "vn", "Tipo de Producto"]).agg(
        Stock_total=("Stock", "sum"),
        Stock_disponible=("Cantidad Disponible", "sum"),
        Costo_inventario_total=("Costo Neto Prom. Total", "sum"),
        Costo_unitario_prom=("Costo Neto Prom. Unitario", "mean"),
        Precio_lista=("Precio Venta Bruto", "mean"),
        Ultimo_costo=("Último costo", "mean"),
    ).reset_index()

    df = sa.merge(va, on=["pn", "vn"], how="left")
    for c in ["Unidades_vendidas", "Venta_costo_total", "Venta_neta_total",
              "Margen_total", "Precio_prom_venta"]:
        df[c] = df.get(c, 0)
        df[c] = df[c].fillna(0)
    if "Costo_prom_venta" not in df:
        df["Costo_prom_venta"] = 0
    df["Costo_prom_venta"] = df["Costo_prom_venta"].fillna(0)

    df["Categoria"] = df["Tipo de Producto"].fillna("SIN TIPO")
    df["Producto"] = df["pn"]
    df["Variante"] = df["vn"]
    # línea de modelo y marca (para pestaña de teléfonos)
    df[["Linea", "Marca"]] = df["Producto"].apply(lambda x: pd.Series(ml.extraer_linea_modelo(x)))

    factor = 30.44 / days
    df["Rotacion"] = np.where(df["Costo_inventario_total"] > 0,
                              df["Venta_costo_total"] / df["Costo_inventario_total"], np.nan)
    df["Rotacion_mensual_proy"] = df["Rotacion"] * factor
    df["Dias_inventario"] = np.where(
        df["Unidades_vendidas"] > 0,
        df["Stock_disponible"] / (df["Unidades_vendidas"] / days),
        np.where(df["Stock_disponible"] > 0, 9999, 0),
    )
    df["Margen_pct"] = np.where(df["Venta_neta_total"] > 0,
                                df["Margen_total"] / df["Venta_neta_total"], np.nan)
    df["Score"] = df["Rotacion"].fillna(0) * 0.6 + df["Margen_pct"].fillna(0) * 0.4

    def classify(r):
        rotm = (r["Rotacion"] if not pd.isna(r["Rotacion"]) else 0) * factor
        if r["Stock_disponible"] == 0:
            return "SIN STOCK"
        if r["Unidades_vendidas"] == 0:
            return "NULA ROTACION"
        if rotm >= 2.0 and (not pd.isna(r["Margen_pct"])) and r["Margen_pct"] >= 0.20:
            return "ESTRELLA"
        if rotm >= 1.0:
            return "BUENA ROTACION"
        if rotm >= 0.3:
            return "ROTACION MEDIA"
        if rotm > 0:
            return "BAJA ROTACION"
        return "NULA ROTACION"

    df["Clasificacion"] = df.apply(classify, axis=1)

    def alerts(r):
        out = []
        rotm = (r["Rotacion"] if not pd.isna(r["Rotacion"]) else 0) * factor
        di = r["Dias_inventario"]
        st_ = r["Stock_disponible"]
        if r["Unidades_vendidas"] == 0 and st_ > 0:
            out.append("PRODUCTO ESTANCADO")
        if di < 7 and rotm >= 1.0:
            out.append("RIESGO DE QUIEBRE")
        if di > 180 and st_ > 5 and di < 9999:
            out.append("SOBRESTOCK")
        if r["Clasificacion"] in ("NULA ROTACION", "BAJA ROTACION") and r["Costo_inventario_total"] > 0:
            out.append("CAPITAL EN RIESGO")
        return ", ".join(out) if out else "—"

    df["Alertas"] = df.apply(alerts, axis=1)

    def recomendar(r):
        cls = r["Clasificacion"]
        st_ = r["Stock_disponible"]
        di = r["Dias_inventario"]
        mp = r["Margen_pct"] if not pd.isna(r["Margen_pct"]) else 0
        if cls == "SIN STOCK":
            return "SIN STOCK"
        if cls == "ESTRELLA":
            return "PRIORIZAR COMPRA"
        if cls == "BUENA ROTACION":
            if di < 7:
                return "REPONER INVENTARIO"
            return "PRIORIZAR COMPRA" if mp >= 0.15 else "BAJAR PRECIO DE RETOMA"
        if cls == "ROTACION MEDIA":
            return "BAJAR PRECIO DE RETOMA" if mp < 0.05 else "MANTENER"
        if cls in ("BAJA ROTACION", "NULA ROTACION"):
            if di > 180 or mp < 0:
                return "LIQUIDAR"
            if st_ > 2:
                return "BAJAR PRECIO DE VENTA"
            return "NO COMPRAR MÁS"
        return "REVISAR STOCK"

    df["Recomendacion"] = df.apply(recomendar, axis=1)

    def motivo(r):
        cls = r["Clasificacion"]
        di = r["Dias_inventario"]
        rotm = r["Rotacion_mensual_proy"]
        rotm_s = "0" if pd.isna(rotm) else f"{rotm:.1f}x"
        if cls == "ESTRELLA":
            return f"Alta rotación ({rotm_s}/mes) y buen margen — priorizar abastecimiento"
        if cls == "BUENA ROTACION" and di < 7:
            return f"Rotación buena con solo {di:.0f} días de stock — riesgo de quiebre"
        if cls == "BUENA ROTACION":
            return f"Rotación saludable ({rotm_s}/mes) — mantener disponibilidad"
        if cls == "ROTACION MEDIA":
            return "Rotación moderada — ajustar retoma si el margen es bajo"
        if cls == "BAJA ROTACION":
            return f"Baja salida con {di:.0f} días de inventario — bajar precio o frenar compra"
        if cls == "NULA ROTACION":
            return "Sin ventas en el período con stock disponible — capital inmovilizado"
        return "Sin stock disponible"

    df["Motivo"] = df.apply(motivo, axis=1)
    df["Ranking"] = df["Score"].rank(ascending=False, method="min").astype("Int64")

    keep = ["Categoria", "Producto", "Variante", "Linea", "Marca",
            "Stock_total", "Stock_disponible",
            "Unidades_vendidas", "Venta_neta_total", "Venta_costo_total",
            "Costo_inventario_total", "Margen_total", "Margen_pct",
            "Rotacion", "Rotacion_mensual_proy", "Dias_inventario",
            "Clasificacion", "Alertas", "Score", "Ranking",
            "Recomendacion", "Motivo"]
    return df[keep]


def country_kpis(df, days):
    ws = df[df["Stock_disponible"] > 0]
    vd = df[df["Unidades_vendidas"] > 0]
    tc = df["Costo_inventario_total"].sum()
    tvc = df["Venta_costo_total"].sum()
    rot = tvc / tc if tc else 0
    cap_riesgo = df[df["Clasificacion"].isin(["NULA ROTACION", "BAJA ROTACION"])]["Costo_inventario_total"].sum()
    return {
        "Stock total": df["Stock_total"].sum(),
        "Stock disponible": df["Stock_disponible"].sum(),
        "Capital en inventario": tc,
        "Venta neta": df["Venta_neta_total"].sum(),
        "Venta a costo": tvc,
        "Margen total": df["Margen_total"].sum(),
        "% Margen": (df["Margen_total"].sum() / df["Venta_neta_total"].sum()
                     if df["Venta_neta_total"].sum() else 0),
        "Rotación semanal": rot,
        "Rotación mensual proy.": rot * (30.44 / days),
        "Días inventario prom.": vd["Dias_inventario"].replace(9999, np.nan).mean(),
        "Capital en riesgo": cap_riesgo,
        "% Capital en riesgo": cap_riesgo / tc if tc else 0,
        "Productos en stock": len(ws),
        "Productos con venta": len(vd),
        "Productos estancados": int(df["Alertas"].astype(str).str.contains("ESTANCADO").sum()),
    }


# ──────────────────────────────────────────────────────────────────────────────
# EXPORTAR A EXCEL
# ──────────────────────────────────────────────────────────────────────────────
def build_excel(all_df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        cons = pd.concat([d.assign(País=p) for p, d in all_df.items()], ignore_index=True)
        cons.to_excel(xw, sheet_name="Base Consolidada", index=False)

        rot_pais = cons.groupby("País").apply(
            lambda g: pd.Series({
                "Capital inventario": g["Costo_inventario_total"].sum(),
                "Venta a costo": g["Venta_costo_total"].sum(),
                "Rotación": (g["Venta_costo_total"].sum() / g["Costo_inventario_total"].sum()
                             if g["Costo_inventario_total"].sum() else 0),
                "Margen total": g["Margen_total"].sum(),
            }), include_groups=False).reset_index()
        rot_pais.to_excel(xw, sheet_name="Rotación por País", index=False)

        rot_cat = cons.groupby(["País", "Categoria"]).agg(
            Stock=("Stock_disponible", "sum"),
            Unidades_vendidas=("Unidades_vendidas", "sum"),
            Capital=("Costo_inventario_total", "sum"),
            Venta_costo=("Venta_costo_total", "sum"),
        ).reset_index()
        rot_cat["Rotación"] = np.where(rot_cat["Capital"] > 0,
                                       rot_cat["Venta_costo"] / rot_cat["Capital"], 0)
        rot_cat.to_excel(xw, sheet_name="Rotación por Categoría", index=False)

        cons[["País", "Categoria", "Producto", "Variante", "Clasificacion",
              "Rotacion_mensual_proy", "Margen_pct", "Score", "Ranking"]]\
            .to_excel(xw, sheet_name="Clasificación Producto", index=False)

        recs = cons[cons["Stock_disponible"] > 0][[
            "País", "Categoria", "Producto", "Variante", "Clasificacion",
            "Recomendacion", "Rotacion_mensual_proy", "Margen_pct",
            "Stock_disponible", "Dias_inventario", "Costo_inventario_total", "Motivo"]]
        recs.to_excel(xw, sheet_name="Recomendaciones", index=False)

        resumen = pd.DataFrame({p: country_kpis(d, st.session_state["days"])
                                for p, d in all_df.items()}).T
        resumen.to_excel(xw, sheet_name="Resumen Ejecutivo")
    buf.seek(0)
    return buf


# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR — CARGA
# ──────────────────────────────────────────────────────────────────────────────
st.sidebar.title("📥 Carga de archivos")
st.sidebar.caption("Sube stock + ventas por país. Formatos .xlsx")

c1, c2 = st.sidebar.columns(2)
fi = c1.date_input("Inicio período", value=date(2026, 5, 25))
ff = c2.date_input("Fin período", value=date(2026, 6, 1))
days = max((ff - fi).days, 1)
st.session_state["days"] = days
st.sidebar.caption(f"Período: **{days} días**  ·  factor mensual ×{30.44/days:.2f}")

uploads = {}
ga4_uploads = {}
for pais, meta in COUNTRY_META.items():
    with st.sidebar.expander(f"{meta['flag']} {pais}", expanded=(pais == "Chile")):
        sf = st.file_uploader(f"Stock {pais}", type=["xlsx"], key=f"s_{meta['code']}")
        vf = st.file_uploader(f"Ventas {pais}", type=["xlsx"], key=f"v_{meta['code']}")
        gf = st.file_uploader(f"GA4 Visitas/CR {pais} (opcional)", type=["xlsx", "csv"],
                              key=f"g_{meta['code']}",
                              help="Archivo de GA4 con visitas y conversiones por producto. "
                                   "Necesario solo para la Matriz de Decisiones.")
        uploads[pais] = (vf, sf)
        ga4_uploads[pais] = gf

st.sidebar.divider()
st.sidebar.caption("**Matriz de Decisiones**")
marcas_matriz = st.sidebar.multiselect("Marcas a analizar", ["iPhone", "Samsung"],
                                       default=["iPhone", "Samsung"])
min_ventas = st.sidebar.number_input("Mín. ventas/30d para calificar", 1, 100, 10)

# ──────────────────────────────────────────────────────────────────────────────
# PROCESAMIENTO
# ──────────────────────────────────────────────────────────────────────────────
all_df = {}
for pais, (vf, sf) in uploads.items():
    if vf is not None and sf is not None:
        try:
            all_df[pais] = process_country(vf, sf, days)
        except Exception as e:
            st.sidebar.error(f"{pais}: error procesando — {e}")

st.title("📊 Dashboard de Rotación de Inventario")
st.markdown("**Chile · México · Perú** — rotación por modelo, clasificación, recomendaciones "
            "y **Matriz de Decisiones de marketing** (CR × Visitas × Stock)")

if not all_df:
    st.info("👈 Sube al menos un par de archivos (stock + ventas) de un país para comenzar. "
            "Puedes cargar los tres países o solo uno.")
    st.stop()

cons = pd.concat([d.assign(País=p) for p, d in all_df.items()], ignore_index=True)

# ── Exportar (arriba a la derecha) ──
exp = build_excel(all_df)
st.download_button("⬇️ Descargar Excel consolidado", exp,
                   file_name=f"Rotacion_{fi:%d%b}-{ff:%d%b}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ──────────────────────────────────────────────────────────────────────────────
# FILTROS GLOBALES
# ──────────────────────────────────────────────────────────────────────────────
with st.expander("🔎 Filtros", expanded=False):
    fc = st.columns(5)
    f_pais = fc[0].multiselect("País", sorted(cons["País"].unique()), default=list(cons["País"].unique()))
    f_cat = fc[1].multiselect("Categoría", sorted(cons["Categoria"].unique()))
    f_cls = fc[2].multiselect("Clasificación", list(CLASS_COLOR.keys()))
    f_rec = fc[3].multiselect("Recomendación", sorted(cons["Recomendacion"].unique()))
    f_prod = fc[4].text_input("Buscar producto")

fcons = cons[cons["País"].isin(f_pais)] if f_pais else cons
if f_cat:
    fcons = fcons[fcons["Categoria"].isin(f_cat)]
if f_cls:
    fcons = fcons[fcons["Clasificacion"].isin(f_cls)]
if f_rec:
    fcons = fcons[fcons["Recomendacion"].isin(f_rec)]
if f_prod:
    fcons = fcons[fcons["Producto"].str.contains(f_prod.upper(), na=False)]

# ──────────────────────────────────────────────────────────────────────────────
# SECCIONES (TABS)
# ──────────────────────────────────────────────────────────────────────────────
tabs = st.tabs(["🏠 Resumen Ejecutivo", "🌎 Comparativo", "🗂️ Por Categoría",
                "📦 Por Producto", "📱 Rotación Teléfonos", "🎯 Matriz Decisiones",
                "🚦 Alertas", "💡 Recomendaciones"])

cur_fmt = lambda p, x: COUNTRY_META[p]["fmt"].format(x) if pd.notna(x) else "—"

# ── TAB 1 · RESUMEN EJECUTIVO ───────────────────────────────────────────────────
with tabs[0]:
    for pais, d in all_df.items():
        if f_pais and pais not in f_pais:
            continue
        meta = COUNTRY_META[pais]
        k = country_kpis(d, days)
        st.markdown(f"<span class='country-pill' style='background:{COL['ink']}'>"
                    f"{meta['flag']} {pais} · {meta['cur']}</span>", unsafe_allow_html=True)
        r1 = st.columns(4)
        r1[0].metric("Stock disponible", f"{k['Stock disponible']:,.0f}")
        r1[1].metric("Capital inventario", cur_fmt(pais, k["Capital en inventario"]))
        r1[2].metric("Venta neta", cur_fmt(pais, k["Venta neta"]))
        r1[3].metric("Margen total", cur_fmt(pais, k["Margen total"]))
        r2 = st.columns(4)
        r2[0].metric("% Margen", f"{k['% Margen']*100:.1f}%")
        r2[1].metric("Rotación semanal", f"{k['Rotación semanal']:.2f}")
        r2[2].metric("Rotación mensual proy.", f"{k['Rotación mensual proy.']:.2f}")
        r2[3].metric("Días inv. prom.", f"{k['Días inventario prom.']:.0f}" if pd.notna(k['Días inventario prom.']) else "—")
        r3 = st.columns(4)
        r3[0].metric("Capital en riesgo", cur_fmt(pais, k["Capital en riesgo"]))
        r3[1].metric("% Capital en riesgo", f"{k['% Capital en riesgo']*100:.1f}%",
                     delta_color="inverse")
        r3[2].metric("Productos con venta", f"{k['Productos con venta']:,}")
        r3[3].metric("Productos estancados", f"{k['Productos estancados']:,}", delta_color="inverse")
        st.divider()

# ── TAB 2 · COMPARATIVO ─────────────────────────────────────────────────────────
with tabs[1]:
    comp = pd.DataFrame({p: country_kpis(d, days) for p, d in all_df.items()}).T.reset_index(names="País")
    if len(comp) >= 1:
        cc = st.columns(2)
        metrics_bar = [
            ("Capital en inventario", "Capital en inventario"),
            ("Venta neta", "Venta neta"),
            ("Rotación mensual proy.", "Rotación mensual proyectada"),
            ("% Margen", "% Margen"),
            ("Capital en riesgo", "Capital en riesgo"),
            ("Productos estancados", "Productos estancados"),
        ]
        for i, (col, title) in enumerate(metrics_bar):
            fig = px.bar(comp, x="País", y=col, color="País", text_auto=".2s",
                         title=title, color_discrete_sequence=[COL["mid"], COL["buena"], COL["media"]])
            fig.update_layout(showlegend=False, height=300, margin=dict(t=40, b=10))
            cc[i % 2].plotly_chart(fig, use_container_width=True)

    st.subheader("Categorías con mejor y peor desempeño por país")
    for pais, d in all_df.items():
        cat = d.groupby("Categoria").agg(
            Cap=("Costo_inventario_total", "sum"),
            VC=("Venta_costo_total", "sum")).reset_index()
        cat["Rotación"] = np.where(cat["Cap"] > 0, cat["VC"] / cat["Cap"], 0)
        cat = cat[cat["Cap"] > 0].sort_values("Rotación", ascending=False)
        if len(cat) == 0:
            continue
        best = cat.head(3)[["Categoria", "Rotación"]]
        worst = cat.tail(3)[["Categoria", "Rotación"]]
        cols = st.columns([1, 3, 3])
        cols[0].markdown(f"**{COUNTRY_META[pais]['flag']} {pais}**")
        cols[1].caption("🟢 Mejor rotación")
        cols[1].dataframe(best, hide_index=True, use_container_width=True)
        cols[2].caption("🔴 Peor rotación")
        cols[2].dataframe(worst, hide_index=True, use_container_width=True)

# ── TAB 3 · POR CATEGORÍA ───────────────────────────────────────────────────────
with tabs[2]:
    cat = fcons.groupby(["País", "Categoria"]).agg(
        Stock=("Stock_disponible", "sum"),
        Unidades_vendidas=("Unidades_vendidas", "sum"),
        Capital=("Costo_inventario_total", "sum"),
        Venta_costo=("Venta_costo_total", "sum"),
        Margen=("Margen_total", "sum"),
    ).reset_index()
    cat["Rotación semanal"] = np.where(cat["Capital"] > 0, cat["Venta_costo"] / cat["Capital"], 0)
    cat["Rotación mensual proy."] = cat["Rotación semanal"] * (30.44 / days)
    cat["Días inventario"] = np.where(
        cat["Unidades_vendidas"] > 0,
        cat["Stock"] / (cat["Unidades_vendidas"] / days), np.nan)
    cat = cat.sort_values("Rotación mensual proy.", ascending=False)

    st.subheader("Rotación por categoría")
    fig = px.bar(cat, x="Rotación mensual proy.", y="Categoria", color="País",
                 orientation="h", height=max(350, len(cat) * 22),
                 color_discrete_sequence=[COL["mid"], COL["buena"], COL["media"]])
    fig.update_layout(margin=dict(t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        cat.style.format({
            "Stock": "{:,.0f}", "Unidades_vendidas": "{:,.0f}", "Capital": "{:,.0f}",
            "Venta_costo": "{:,.0f}", "Margen": "{:,.0f}",
            "Rotación semanal": "{:.2f}", "Rotación mensual proy.": "{:.2f}",
            "Días inventario": "{:,.0f}"}),
        hide_index=True, use_container_width=True)

# ── TAB 4 · POR PRODUCTO ────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader(f"Análisis por producto · {len(fcons):,} filas")
    show = fcons.copy()
    show["Clasif."] = show["Clasificacion"].map(lambda c: f"{CLASS_EMOJI.get(c,'')} {c}")
    view = show[["País", "Categoria", "Producto", "Stock_disponible",
                 "Unidades_vendidas", "Venta_neta_total", "Venta_costo_total",
                 "Margen_pct", "Rotacion", "Rotacion_mensual_proy", "Dias_inventario",
                 "Clasif.", "Score", "Ranking", "Costo_inventario_total", "Recomendacion"]]\
        .sort_values("Score", ascending=False)
    st.dataframe(
        view.style.format({
            "Stock_disponible": "{:,.0f}", "Unidades_vendidas": "{:,.0f}",
            "Venta_neta_total": "{:,.0f}", "Venta_costo_total": "{:,.0f}",
            "Margen_pct": "{:.1%}", "Rotacion": "{:.2f}", "Rotacion_mensual_proy": "{:.2f}",
            "Dias_inventario": "{:,.0f}", "Score": "{:.3f}",
            "Costo_inventario_total": "{:,.0f}"}),
        hide_index=True, use_container_width=True, height=560)

# ── TAB 5 · ROTACIÓN TELÉFONOS (iPhone / Samsung) ───────────────────────────────
with tabs[4]:
    st.subheader("📱 Rotación de teléfonos por línea de modelo")
    st.caption("Solo iPhone y Samsung, agrupados por modelo (colores y capacidades sumados).")
    fones = fcons[fcons["Marca"].isin(["iPhone", "Samsung"])].copy()
    if len(fones) == 0:
        st.info("No se detectaron teléfonos iPhone/Samsung en los datos cargados.")
    else:
        mc = st.columns(3)
        marca_pick = mc[0].multiselect("Marca", ["iPhone", "Samsung"], default=["iPhone", "Samsung"])
        pais_pick = mc[1].multiselect("País", sorted(fones["País"].unique()),
                                      default=sorted(fones["País"].unique()))
        fones = fones[fones["Marca"].isin(marca_pick) & fones["País"].isin(pais_pick)]

        # Agrupar por línea de modelo (suma capacidades distintas de un mismo modelo)
        ph = fones.groupby(["País", "Marca", "Linea"]).agg(
            Stock_disponible=("Stock_disponible", "sum"),
            Unidades_vendidas=("Unidades_vendidas", "sum"),
            Venta_neta_total=("Venta_neta_total", "sum"),
            Venta_costo_total=("Venta_costo_total", "sum"),
            Costo_inventario_total=("Costo_inventario_total", "sum"),
            Margen_total=("Margen_total", "sum"),
            Variantes=("Producto", "nunique"),
        ).reset_index()
        ph["Rotacion"] = np.where(ph["Costo_inventario_total"] > 0,
                                  ph["Venta_costo_total"] / ph["Costo_inventario_total"], 0)
        ph["Rotacion_mensual_proy"] = ph["Rotacion"] * (30.44 / days)
        ph["Dias_inventario"] = np.where(
            ph["Unidades_vendidas"] > 0,
            ph["Stock_disponible"] / (ph["Unidades_vendidas"] / days), np.nan)
        ph["Margen_pct"] = np.where(ph["Venta_neta_total"] > 0,
                                    ph["Margen_total"] / ph["Venta_neta_total"], np.nan)
        ph = ph.sort_values("Rotacion_mensual_proy", ascending=False)

        k = st.columns(4)
        k[0].metric("Líneas de modelo", f"{len(ph):,}")
        k[1].metric("Stock total", f"{ph['Stock_disponible'].sum():,.0f}")
        k[2].metric("Unidades vendidas", f"{ph['Unidades_vendidas'].sum():,.0f}")
        k[3].metric("Rotación mensual prom.", f"{ph['Rotacion_mensual_proy'].mean():.2f}")

        fig = px.bar(ph.head(25), x="Rotacion_mensual_proy", y="Linea", color="Marca",
                     orientation="h", height=max(400, len(ph.head(25)) * 24),
                     color_discrete_map={"iPhone": "#2E4A7A", "Samsung": "#1B9E5A"},
                     labels={"Rotacion_mensual_proy": "Rotación mensual proyectada", "Linea": ""},
                     title="Top 25 líneas por rotación")
        fig.update_layout(margin=dict(t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            ph[["País", "Marca", "Linea", "Variantes", "Stock_disponible", "Unidades_vendidas",
                "Venta_neta_total", "Margen_pct", "Rotacion", "Rotacion_mensual_proy",
                "Dias_inventario", "Costo_inventario_total"]]
            .style.format({
                "Stock_disponible": "{:,.0f}", "Unidades_vendidas": "{:,.0f}",
                "Venta_neta_total": "{:,.0f}", "Margen_pct": "{:.1%}",
                "Rotacion": "{:.2f}", "Rotacion_mensual_proy": "{:.2f}",
                "Dias_inventario": "{:,.0f}", "Costo_inventario_total": "{:,.0f}"}),
            hide_index=True, use_container_width=True, height=480)

# ── TAB 6 · MATRIZ DE DECISIONES ────────────────────────────────────────────────
with tabs[5]:
    st.subheader("🎯 Matriz de Decisiones · CR × Visitas × Stock")
    st.caption("Cruza GA4 (visitas/conversión) con stock y ventas por línea de modelo. "
               "Requiere cargar el archivo GA4 del país en la barra lateral.")

    pais_mat = st.selectbox("País a analizar", list(COUNTRY_META.keys()),
                            index=0, key="mat_pais")
    gf = ga4_uploads.get(pais_mat)
    vf, sf = uploads.get(pais_mat, (None, None))

    if gf is None or pais_mat not in all_df:
        st.info(f"👈 Para ver la matriz de {pais_mat}, carga su archivo GA4 (y stock + ventas) "
                "en la barra lateral.")
    else:
        try:
            # GA4
            raw = gf.read()
            if gf.name.endswith(".csv"):
                ga = pd.read_csv(io.BytesIO(raw))
            else:
                ga = pd.read_excel(io.BytesIO(raw))
            ga.columns = [str(c).strip() for c in ga.columns]

            # mapeo de columnas GA4
            with st.expander("⚙️ Mapeo de columnas GA4", expanded=False):
                cols = list(ga.columns)
                def _guess(opts, default=0):
                    return default
                gc = st.columns(3)
                col_prod = gc[0].selectbox("Producto/Nombre", cols,
                    index=next((i for i, c in enumerate(cols) if "rod" in c.lower()), 0))
                col_vis = gc[1].selectbox("Visitas", cols,
                    index=next((i for i, c in enumerate(cols) if "isit" in c.lower() or "view" in c.lower()), 0))
                col_comp = gc[2].selectbox("Compras/Transacciones", cols,
                    index=next((i for i, c in enumerate(cols) if "ompra" in c.lower() or "rans" in c.lower()), 0))

            ga = ga.rename(columns={col_prod: "Producto", col_vis: "Visitas", col_comp: "Compras"})
            ga["Visitas"] = pd.to_numeric(ga["Visitas"], errors="coerce").fillna(0)
            ga["Compras"] = pd.to_numeric(ga["Compras"], errors="coerce").fillna(0)
            ga[["linea", "marca"]] = ga["Producto"].apply(lambda x: pd.Series(ml.extraer_linea_modelo(x, tuple(marcas_matriz))))
            ga = ga[ga["linea"].notna() & ~ga["linea"].astype(str).str.contains("otro")]
            ga_g = ga.groupby("linea").agg(Visitas=("Visitas", "sum"),
                                           Compras_ga4=("Compras", "sum"),
                                           marca=("marca", "first")).reset_index()

            # Bsale (stock + ventas) desde lo ya procesado, agrupado por línea
            d = all_df[pais_mat]
            ph = d[d["Marca"].isin(marcas_matriz)].copy()
            stock_g = ph.groupby("Linea").agg(
                Stock=("Stock_disponible", "sum"),
                Ventas_7d=("Unidades_vendidas", "sum"),
                Variantes=("Producto", "nunique"),
                marca=("Marca", "first")).reset_index().rename(columns={"Linea": "linea"})
            stock_g["Ventas_30d"] = stock_g["Ventas_7d"] * (30.44 / days)

            cal, casi, soldout, cortes = ml.construir_matriz(
                ga_g, stock_g, ventas_window_days=30)
            cal["Marca_pri"] = cal["marca"]

            if len(cal) == 0:
                st.warning("Ningún modelo califica con los filtros actuales "
                           f"(≥{min_ventas} ventas/30d). Revisa los datos o baja el umbral.")
            else:
                # KPI strip por cuadrante
                kc = st.columns(4)
                quad_color = {"Escalar tráfico": "#10b981", "Invertir en CR": "#f59e0b",
                              "Activar tráfico": "#2E4A7A", "Revisar / Liquidar": "#dc2626"}
                for i, q in enumerate(["Escalar tráfico", "Invertir en CR",
                                       "Activar tráfico", "Revisar / Liquidar"]):
                    n = (cal["Cuadrante"] == q).sum()
                    kc[i].markdown(
                        f"<div style='background:{quad_color[q]};border-radius:10px;padding:14px;"
                        f"text-align:center;color:#fff'><div style='font-size:1.6rem;font-weight:800'>{n}</div>"
                        f"<div style='font-size:.72rem'>{q}</div></div>", unsafe_allow_html=True)

                # Bubble chart
                plot = cal.copy()
                plot["CR_plot"] = plot["CR"].clip(upper=cortes["cr_max"])
                fig = px.scatter(
                    plot, x="CR_plot", y="Visitas", size="Stock", color="Cuadrante",
                    text="linea", size_max=55,
                    color_discrete_map=quad_color,
                    hover_data={"CR": ":.2f", "Visitas": True, "Ventas_30d": ":.0f",
                                "Stock": True, "DOI": ":.0f", "Variantes": True,
                                "CR_plot": False},
                    labels={"CR_plot": "CR % (compra/visita)", "Visitas": "Visitas (GA4)"},
                    height=560)
                fig.add_vline(x=cortes["cr_cut"], line_dash="dash", line_color="#888",
                              annotation_text=f"CR {cortes['cr_cut']}%")
                fig.add_hline(y=cortes["vis_cut"], line_dash="dash", line_color="#888",
                              annotation_text=f"Mediana visitas {cortes['vis_cut']:.0f}")
                fig.update_traces(textposition="top center", textfont_size=9)
                fig.update_layout(margin=dict(t=20, b=10), xaxis_range=[0, cortes["cr_max"] * 1.05])
                st.plotly_chart(fig, use_container_width=True)

                # Tabla de decisiones con semáforo DOI
                tab = cal.sort_values(["Prioridad", "Stock"],
                                      key=lambda s: s.map({"Crítica": 0, "Alta": 1, "Media": 2, "Baja": 3})
                                      if s.name == "Prioridad" else s,
                                      ascending=[True, False]).copy()
                tab_disp = tab[["linea", "marca", "Variantes", "Stock", "DOI", "Visitas",
                                "Ventas_7d", "CR", "Ventas_30d", "Cuadrante", "Nivel_stock",
                                "Prioridad", "Decision", "Accion_precio"]].rename(columns={
                    "linea": "Modelo", "marca": "Marca", "DOI": "Días Inv.",
                    "Ventas_7d": "Ventas 7d", "CR": "CR%", "Ventas_30d": "Ventas 30d",
                    "Nivel_stock": "Nivel Stock", "Accion_precio": "Acción Precio"})

                def _doi_style(val):
                    bg, fg = ml.doi_color(val)
                    return f"background-color:{bg};color:{fg}"

                def _doi_fmt(v):
                    return "∞" if v >= 9999 else f"{v:.0f}"

                styler = tab_disp.style.format({
                    "Stock": "{:,.0f}", "Días Inv.": _doi_fmt, "Visitas": "{:,.0f}",
                    "Ventas 7d": "{:,.0f}", "CR%": "{:.2f}", "Ventas 30d": "{:,.0f}"})
                styler = styler.map(_doi_style, subset=["Días Inv."])
                st.dataframe(styler, hide_index=True, use_container_width=True, height=420)

                # Descarga Excel de la matriz
                mbuf = io.BytesIO()
                with pd.ExcelWriter(mbuf, engine="openpyxl") as xw:
                    tab_disp.to_excel(xw, sheet_name="Matriz Decisiones", index=False)
                    if len(soldout):
                        soldout[["linea", "Stock", "Ventas_30d", "Visitas"]]\
                            .to_excel(xw, sheet_name="Sold-out winners", index=False)
                    if len(casi):
                        casi[["linea", "Ventas_30d", "Stock", "Visitas"]]\
                            .to_excel(xw, sheet_name="Casi califican", index=False)
                mbuf.seek(0)
                st.download_button("⬇️ Descargar matriz (Excel)", mbuf,
                                   file_name=f"Matriz_Decisiones_{pais_mat}_{ff:%d%b}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                # Notas al pie
                if len(soldout):
                    st.markdown("**🔥 Sold-out winners** (vendían bien pero quedaron sin stock):")
                    for _, r in soldout.iterrows():
                        st.caption(f"• {r['linea']} · {r['Ventas_30d']:.0f} ventas/mes, agotado — reponer urgente")
                if len(casi):
                    st.markdown("**📍 Casi califican** (5–9 ventas/30d):")
                    st.caption(", ".join(casi["linea"].tolist()))

                st.caption(f"Cortes: CR mediana {cortes['cr_cut']}% (empírico Reuse, electrónica reacondicionada) · "
                           f"visitas mediana {cortes['vis_cut']:.0f} · DOI = Stock × 30 ÷ Ventas 30d · "
                           "Ventas 30d proyectadas desde la ventana cargada.")
        except Exception as e:
            st.error(f"Error procesando la matriz: {e}")
            import traceback
            st.code(traceback.format_exc())

# ── TAB 7 · ALERTAS ─────────────────────────────────────────────────────────────
with tabs[6]:
    st.subheader("Semáforo de clasificación")
    counts = fcons["Clasificacion"].value_counts()
    cols = st.columns(len(CLASS_COLOR))
    for i, (cls, color) in enumerate(CLASS_COLOR.items()):
        cols[i].markdown(
            f"<div style='background:{color};border-radius:10px;padding:14px;text-align:center;color:#fff'>"
            f"<div style='font-size:1.6rem;font-weight:800'>{int(counts.get(cls,0))}</div>"
            f"<div style='font-size:.72rem'>{CLASS_EMOJI[cls]} {cls}</div></div>",
            unsafe_allow_html=True)

    st.subheader("Alertas operativas")
    alert_types = ["PRODUCTO ESTANCADO", "RIESGO DE QUIEBRE", "SOBRESTOCK", "CAPITAL EN RIESGO"]
    ac = st.columns(4)
    for i, a in enumerate(alert_types):
        n = fcons["Alertas"].str.contains(a).sum()
        ac[i].metric(a.title(), f"{n:,}")

    sel = st.selectbox("Ver detalle de alerta", ["Todas"] + alert_types)
    base = fcons if sel == "Todas" else fcons[fcons["Alertas"].str.contains(sel)]
    base = base[base["Alertas"] != "—"] if sel == "Todas" else base
    st.dataframe(
        base[["País", "Categoria", "Producto", "Variante", "Clasificacion",
              "Alertas", "Stock_disponible", "Dias_inventario", "Costo_inventario_total"]]
        .sort_values("Costo_inventario_total", ascending=False)
        .style.format({"Stock_disponible": "{:,.0f}", "Dias_inventario": "{:,.0f}",
                       "Costo_inventario_total": "{:,.0f}"}),
        hide_index=True, use_container_width=True, height=420)

# ── TAB 8 · RECOMENDACIONES ─────────────────────────────────────────────────────
with tabs[7]:
    st.subheader("Recomendaciones comerciales priorizadas")
    rec = fcons[fcons["Stock_disponible"] > 0].copy()
    rec["_pri"] = rec["Recomendacion"].map(REC_PRIORITY).fillna(8)
    rec["Prioridad"] = rec["_pri"].map(PRI_LABEL)
    rec = rec.sort_values(["_pri", "Costo_inventario_total"], ascending=[True, False])
    st.dataframe(
        rec[["Prioridad", "Recomendacion", "País", "Categoria", "Producto", "Variante",
             "Clasificacion", "Rotacion_mensual_proy", "Margen_pct", "Stock_disponible",
             "Dias_inventario", "Costo_inventario_total", "Motivo"]]
        .style.format({"Rotacion_mensual_proy": "{:.2f}", "Margen_pct": "{:.1%}",
                       "Stock_disponible": "{:,.0f}", "Dias_inventario": "{:,.0f}",
                       "Costo_inventario_total": "{:,.0f}"}),
        hide_index=True, use_container_width=True, height=420)

    st.divider()
    cc = st.columns(3)
    cc[0].markdown("**🔴 Productos estancados**")
    est = fcons[fcons["Alertas"].str.contains("ESTANCADO")]\
        .nlargest(15, "Costo_inventario_total")[["País", "Producto", "Costo_inventario_total"]]
    cc[0].dataframe(est.style.format({"Costo_inventario_total": "{:,.0f}"}),
                    hide_index=True, use_container_width=True)
    cc[1].markdown("**🟢 Alta rotación**")
    alta = fcons[fcons["Clasificacion"].isin(["ESTRELLA", "BUENA ROTACION"])]\
        .nlargest(15, "Rotacion_mensual_proy")[["País", "Producto", "Rotacion_mensual_proy"]]
    cc[1].dataframe(alta.style.format({"Rotacion_mensual_proy": "{:.2f}"}),
                    hide_index=True, use_container_width=True)
    cc[2].markdown("**💰 Mayor capital inmovilizado**")
    cap = fcons[fcons["Clasificacion"].isin(["NULA ROTACION", "BAJA ROTACION"])]\
        .nlargest(15, "Costo_inventario_total")[["País", "Producto", "Costo_inventario_total"]]
    cc[2].dataframe(cap.style.format({"Costo_inventario_total": "{:,.0f}"}),
                    hide_index=True, use_container_width=True)

st.caption("Rotación = Venta a costo ÷ Costo de inventario · Rotación mensual proyectada = rotación del período × (30.44 ÷ días) · "
           "Clasificación y alertas calculadas sobre la rotación mensual proyectada.")

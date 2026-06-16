"""
matriz_logic.py — Lógica de extracción de línea de modelo, fusión de variantes
y construcción de la Matriz de Decisiones (CR × Visitas × Stock) de Reuse.

Se importa desde app.py. Mantiene la lógica canónica de la skill original.
"""
import re
import numpy as np
import pandas as pd


# ──────────────────────────────────────────────────────────────────────────────
# 1. FUSIÓN DE VARIANTES — quita color y deja "modelo + capacidad"
# ──────────────────────────────────────────────────────────────────────────────
# Colores a remover del nombre (ES + algunos EN)
_COLORES = [
    "NEGRO", "BLANCO", "AZUL", "ROJO", "VERDE", "MORADO", "ROSA", "ROSADO",
    "DORADO", "PLATA", "PLATEADO", "GRIS", "GRAFITO", "AMARILLO", "NARANJA",
    "CORAL", "TITANIO NATURAL", "TITANIO AZUL", "TITANIO BLANCO", "TITANIO NEGRO",
    "TITANIO DESIERTO", "TITANIO", "MEDIANOCHE", "BLANCO ESTELAR", "ESTELAR",
    "PURPURA", "PÚRPURA", "LILA", "CELESTE", "TURQUESA", "MENTA", "CREMA",
    "BEIGE", "OLIVA", "LAVANDA", "GRAPHITE", "MIDNIGHT", "STARLIGHT", "SIERRA",
    "ALPINE", "PACIFIC", "DESERT", "NATURAL", "SPACE GRAY", "SPACE BLACK",
    "PRODUCT RED", "(PRODUCT)RED", "PINK", "BLUE", "BLACK", "WHITE", "GREEN",
    "PURPLE", "GOLD", "SILVER", "YELLOW", "GRAY", "GREY", "ULTRAMARINE",
    "TEAL", "FANTASMA", "PHANTOM", "LAVENDER", "CREAM", "MINT", "BORA",
]
_REACOND = ["REACONDICIONADO", "REACONDICIONADA", "REACONDICIONADO POR DISTRIBUIDOR OFICIAL",
            "REACONDICIONADA POR DISTRIBUIDOR OFICIAL", "OPENBOX", "OPEN BOX",
            "POR DISTRIBUIDOR OFICIAL", "SEMINUEVO", "SEMI NUEVO", "USADO"]


def fusionar_variante(nombre: str) -> str:
    """
    Convierte 'APPLE IPHONE 13 128GB NEGRO REACONDICIONADO' → 'IPHONE 13 128GB'.
    Quita marca redundante (APPLE/SAMSUNG), color y términos de reacondicionado.
    Mantiene capacidad (128GB) porque diferencia precio/rotación.
    """
    if not isinstance(nombre, str):
        return ""
    s = " " + nombre.upper().strip() + " "
    # normaliza espacios
    s = re.sub(r"\s+", " ", s)
    # quita reacondicionado (frases largas primero)
    for r in sorted(_REACOND, key=len, reverse=True):
        s = s.replace(" " + r + " ", " ")
    # quita colores (palabras completas, frases largas primero)
    for c in sorted(_COLORES, key=len, reverse=True):
        s = re.sub(r"\b" + re.escape(c) + r"\b", " ", s)
    # quita marca redundante al inicio
    s = re.sub(r"\bAPPLE\b", " ", s)
    s = re.sub(r"\bSAMSUNG\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ──────────────────────────────────────────────────────────────────────────────
# 2. EXTRACCIÓN DE LÍNEA DE MODELO (agrupa colores Y capacidades)
# ──────────────────────────────────────────────────────────────────────────────
_IPHONE_EXCL = ["CARCASA", "FUNDA", "CABLE", "CARGADOR", "PROTECTOR", "LÁMINA", "LAMINA",
                "ADAPTADOR", "VIDRIO", "MICA"]
_SAMSUNG_EXCL = ["TAB", "WATCH", "MONITOR", "LAVADORA", "REFRIGERADOR", "COCINA",
                 "MICROONDAS", "HORNO", "ASPIRADORA", " TV ", "SOUNDBAR", "PARLANTE",
                 "AUDÍFONO", "AUDIFONO", "CARGADOR", "CARCASA", "FUNDA", "PANTALLA",
                 "BOOK", "BUDS", "GALAXY FIT", "GALAXY WATCH", "SECADORA", "FREEZER",
                 "BOTTOM MOUNT", "REFRIGERATOR", "DRYER", "WASHER", "LAVASECA"]


def _is_excluded(nombre_upper, excl_list):
    return any(x.strip() in nombre_upper for x in excl_list)


def linea_iphone(n: str):
    """Devuelve la línea de modelo iPhone o None."""
    s = n.upper()
    if "IPHONE" not in s:
        return None
    if _is_excluded(s, _IPHONE_EXCL):
        return None
    # orden importa
    if re.search(r"IPHONE\s+AIR", s):
        return "iPhone Air"
    m = re.search(r"IPHONE\s+SE\s*(3|2)?", s)
    if m:
        g = m.group(1)
        return f"iPhone SE {g}" if g else "iPhone SE"
    if re.search(r"IPHONE\s+XR", s):
        return "iPhone XR"
    if re.search(r"IPHONE\s+XS\s+MAX", s):
        return "iPhone XS Max"
    if re.search(r"IPHONE\s+XS", s):
        return "iPhone XS"
    if re.search(r"IPHONE\s+X\b", s):
        return "iPhone X"
    if re.search(r"IPHONE\s+8\s+PLUS", s):
        return "iPhone 8 Plus"
    if re.search(r"IPHONE\s+8\b", s):
        return "iPhone 8"
    if re.search(r"IPHONE\s+7\b", s):
        return "iPhone 7"
    if re.search(r"IPHONE\s+6S\s+PLUS", s):
        return "iPhone 6s Plus"
    # iPhone N (e)? (Pro Max|Pro|Plus|mini)?
    m = re.search(r"IPHONE\s+(\d{1,2})\s*(E)?\s*(PRO\s+MAX|PRO|PLUS|MINI)?", s)
    if m:
        num = m.group(1)
        e = "e" if m.group(2) else ""
        suf = m.group(3)
        suf_map = {"PRO MAX": " Pro Max", "PRO": " Pro", "PLUS": " Plus", "MINI": " mini"}
        suf_txt = suf_map.get(suf.strip(), "") if suf else ""
        return f"iPhone {num}{e}{suf_txt}"
    return "iPhone (otro)"


def linea_samsung(n: str):
    """Devuelve la línea de modelo Samsung/Galaxy o None."""
    s = n.upper()
    if "SAMSUNG" not in s and "GALAXY" not in s:
        return None
    if _is_excluded(s, _SAMSUNG_EXCL):
        return None
    if re.search(r"Z\s+FOLD\s*(\d)", s):
        g = re.search(r"Z\s+FOLD\s*(\d)", s).group(1)
        return f"Galaxy Z Fold {g}"
    if re.search(r"Z\s+FLIP\s*(\d)", s):
        g = re.search(r"Z\s+FLIP\s*(\d)", s).group(1)
        return f"Galaxy Z Flip {g}"
    m = re.search(r"NOTE\s+(\d{1,2})\s*(ULTRA|PLUS|\+)?", s)
    if m:
        suf = m.group(2)
        suf_txt = {"ULTRA": " Ultra", "PLUS": " Plus", "+": " Plus"}.get(suf, "") if suf else ""
        return f"Galaxy Note {m.group(1)}{suf_txt}"
    m = re.search(r"\bS(\d{1,2})(E)?\s*(ULTRA|PLUS|FE|\+)?", s)
    if m:
        num = m.group(1)
        e = "e" if m.group(2) else ""
        suf = m.group(3)
        suf_txt = {"ULTRA": " Ultra", "PLUS": " Plus", "FE": " FE", "+": " Plus"}.get(suf, "") if suf else ""
        return f"Galaxy S{num}{e}{suf_txt}"
    m = re.search(r"\bA(\d{2,3})S?\b", s)
    if m:
        return f"Galaxy A{m.group(1)}"
    return "Galaxy (otro)"


def extraer_linea_modelo(nombre: str, marcas=("iPhone", "Samsung")):
    """Intenta iPhone y Samsung. Devuelve (linea, marca) o (None, None)."""
    if not isinstance(nombre, str):
        return None, None
    if "iPhone" in marcas:
        li = linea_iphone(nombre)
        if li:
            return li, "iPhone"
    if "Samsung" in marcas:
        ls = linea_samsung(nombre)
        if ls:
            return ls, "Samsung"
    return None, None


# ──────────────────────────────────────────────────────────────────────────────
# 3. MATRIZ DE DECISIONES
# ──────────────────────────────────────────────────────────────────────────────
CR_CUT = 0.85          # corte de mediana CR % (empírico Reuse)
CR_MAX = 2.0           # clamp eje X
MIN_VENTAS_30D = 10    # filtro A
QUASI_LOW, QUASI_HIGH = 5, 9   # "casi califican"


def _to_num(series):
    return pd.to_numeric(
        series.astype(str).str.replace(",", "").str.replace("%", "").str.strip(),
        errors="coerce").fillna(0)


def construir_matriz(ga4, bsale_modelo, ventas_window_days=30):
    """
    ga4: DataFrame con columnas internas [linea, marca, Visitas, Compras_ga4]
    bsale_modelo: DataFrame agregado por linea con [linea, marca, Stock, Ventas_30d, Ventas_7d, Variantes]
    Devuelve (matriz_df, casi_df, soldout_df, cortes).
    """
    df = bsale_modelo.merge(
        ga4[["linea", "Visitas", "Compras_ga4"]], on="linea", how="outer")
    df["Visitas"] = df["Visitas"].fillna(0)
    df["Stock"] = df["Stock"].fillna(0)
    df["Ventas_30d"] = df["Ventas_30d"].fillna(0)
    df["Ventas_7d"] = df["Ventas_7d"].fillna(0)
    df["Variantes"] = df["Variantes"].fillna(0).astype(int)
    df["marca"] = df["marca"].fillna(df["marca_y"] if "marca_y" in df else "—")
    if "marca_x" in df:
        df["marca"] = df["marca_x"].fillna(df.get("marca_y"))

    # CR a nivel modelo: SIEMPRE compras GA4 / visitas GA4 (misma ventana temporal).
    # No usar ventas Bsale escaladas: distinta ventana → CR inflado.
    df["Compras_ga4"] = df["Compras_ga4"].fillna(0)
    df["CR"] = np.where(df["Visitas"] > 0, df["Compras_ga4"] / df["Visitas"] * 100, 0)

    # DOI usa ventas Bsale a 30d (ritmo de inventario)
    df["DOI"] = np.where(df["Ventas_30d"] > 0, df["Stock"] * 30 / df["Ventas_30d"],
                         np.where(df["Stock"] > 3, 9999, 0))

    # filtros
    cal = df[df["Ventas_30d"] >= MIN_VENTAS_30D].copy()
    # Filtro B: excluir stock<=3 Y visitas<100
    filtro_b = (cal["Stock"] <= 3) & (cal["Visitas"] < 100)
    soldout = cal[filtro_b & (cal["Ventas_30d"] >= MIN_VENTAS_30D)].copy()
    cal = cal[~filtro_b].copy()

    casi = df[(df["Ventas_30d"] >= QUASI_LOW) & (df["Ventas_30d"] <= QUASI_HIGH)].copy()

    # cortes
    vis_cut = cal["Visitas"].median() if len(cal) else 0

    def cuadrante(r):
        cr_hi = r["CR"] >= CR_CUT
        vi_hi = r["Visitas"] >= vis_cut
        if cr_hi and vi_hi:
            return "Escalar tráfico"
        if not cr_hi and vi_hi:
            return "Invertir en CR"
        if cr_hi and not vi_hi:
            return "Activar tráfico"
        return "Revisar / Liquidar"

    def nivel_stock(s):
        if s < 10:
            return "bajo"
        if s <= 50:
            return "medio"
        return "alto"

    cal["Cuadrante"] = cal.apply(cuadrante, axis=1)
    cal["Nivel_stock"] = cal["Stock"].apply(nivel_stock)

    DEC = {
        ("Escalar tráfico", "alto"): ("Máximo push de ads. Stock respalda escalar.", "Mantener precio", "Media"),
        ("Escalar tráfico", "medio"): ("Escalar con cuidado, monitorear stock.", "Mantener / subir leve", "Media"),
        ("Escalar tráfico", "bajo"): ("No escalar. Subir precio para maximizar margen.", "Subir precio", "Alta"),
        ("Invertir en CR", "alto"): ("URGENTE: stock acumulado con baja CR. Bajar precio agresivo.", "Bajar precio YA", "Crítica"),
        ("Invertir en CR", "medio"): ("Revisar precio vs competencia, mejorar ficha.", "Bajar precio", "Alta"),
        ("Invertir en CR", "bajo"): ("Mejorar ficha, no enviar más tráfico.", "Bajar leve", "Baja"),
        ("Activar tráfico", "alto"): ("Buena CR + mucho stock + pocas visitas. Push agresivo de tráfico pagado.", "Mantener precio", "Crítica"),
        ("Activar tráfico", "medio"): ("Enviar tráfico para acelerar rotación.", "Mantener precio", "Alta"),
        ("Activar tráfico", "bajo"): ("Buena CR y poco stock. Monitorear.", "Mantener / subir", "Baja"),
        ("Revisar / Liquidar", "alto"): ("CRÍTICO: stock alto sin tracción. Liquidar agresivo.", "Liquidar", "Crítica"),
        ("Revisar / Liquidar", "medio"): ("Sin tracción. Bajar precio o liquidar por lote.", "Bajar precio fuerte", "Alta"),
        ("Revisar / Liquidar", "bajo"): ("Poco stock y sin tracción. Baja prioridad.", "Mantener", "Baja"),
    }
    cal["Decision"] = cal.apply(lambda r: DEC[(r["Cuadrante"], r["Nivel_stock"])][0], axis=1)
    cal["Accion_precio"] = cal.apply(lambda r: DEC[(r["Cuadrante"], r["Nivel_stock"])][1], axis=1)
    cal["Prioridad"] = cal.apply(lambda r: DEC[(r["Cuadrante"], r["Nivel_stock"])][2], axis=1)

    cortes = {"cr_cut": CR_CUT, "vis_cut": vis_cut, "cr_max": CR_MAX}
    return cal, casi, soldout, cortes


def doi_color(doi):
    """Devuelve hex de fondo y texto para el semáforo DOI."""
    if doi >= 9999:
        return "#dc2626", "#ffffff"   # stock muerto
    if doi == 0:
        return "#dc2626", "#ffffff"   # agotado
    if doi < 10:
        return "#dc2626", "#ffffff"
    if doi <= 30:
        return "#f59e0b", "#000000"
    return "#10b981", "#ffffff"

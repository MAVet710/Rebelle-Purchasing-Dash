import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# ------------------------------------------------------------
# OPTIONAL / SAFE IMPORT FOR PLOTLY
# ------------------------------------------------------------
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# =========================
# CONFIG & BRANDING
# =========================
CLIENT_NAME = "Rebelle Cannabis"
APP_TITLE = f"{CLIENT_NAME} Purchasing Dashboard"
APP_TAGLINE = "Streamlined purchasing visibility powered by Dutchie data."
LICENSE_FOOTER = f"Licensed exclusively to {CLIENT_NAME} • Powered by MAVet710 Analytics"

# Tab icon (favicon)
page_icon_url = (
    "https://raw.githubusercontent.com/MAVet710/Rebelle-Purchasing-Dash/"
    "ef50d34e20caf45231642e957137d6141082dbb9/rebelle.jpg"
)

st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    page_icon=page_icon_url,
)

# Background image
background_url = (
    "https://raw.githubusercontent.com/MAVet710/Rebelle-Purchasing-Dash/"
    "ef50d34e20caf45231642e957137d6141082dbb9/rebelle%20main.png"
)

# =========================
# GLOBAL STYLING
# =========================
st.markdown(
    f"""
    <style>
    .stApp {{
        background-image: url('{background_url}');
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        color: white;
    }}
    .block-container {{
        background-color: rgba(0, 0, 0, 0.80);
        padding: 2rem;
        border-radius: 12px;
    }}
    .dataframe td {{
        color: white !important;
    }}
    .neon-red {{
        color: #FF3131;
        font-weight: bold;
    }}
    .stButton>button {{
        background-color: rgba(255, 255, 255, 0.08);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.8);
        border-radius: 6px;
        padding: 0.4rem 0.8rem;
    }}
    .stButton>button:hover {{
        background-color: rgba(255, 255, 255, 0.25);
    }}
    .metric-label {{
        font-size: 0.8rem;
        opacity: 0.8;
    }}
    .footer {{
        text-align: center;
        font-size: 0.75rem;
        opacity: 0.7;
        margin-top: 2rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# HEADER
# =========================
st.title(f"🌿 {APP_TITLE}")
st.markdown(f"**Client:** {CLIENT_NAME}")
st.markdown(APP_TAGLINE)
st.markdown("---")

if not PLOTLY_AVAILABLE:
    st.warning(
        "⚠️ Plotly is not installed in this environment. Charts will be disabled.\n\n"
        "If using Streamlit Cloud, add `plotly` to your `requirements.txt` file."
    )

# =========================
# PAGE SWITCH
# =========================
section = st.sidebar.radio(
    "App Section",
    ["📊 Inventory Dashboard", "🧾 PO Builder"],
    index=0,
)

# ============================================================
# PAGE 1 – INVENTORY DASHBOARD
# ============================================================
if section == "📊 Inventory Dashboard":

    # -------------------------
    # SIDEBAR: FILES & CONTROLS
    # -------------------------
    st.sidebar.header("📂 Upload Core Reports")

    st.sidebar.markdown(
        "Upload **Dutchie-derived** reports for automated inventory and velocity analysis."
    )

    inv_file = st.sidebar.file_uploader("Inventory CSV", type="csv")
    sales_file = st.sidebar.file_uploader(
        "Detailed Sales Breakdown (optional)", type="xlsx"
    )
    product_sales_file = st.sidebar.file_uploader(
        "Product Sales Report (required)", type="xlsx"
    )
    aging_file = st.sidebar.file_uploader(
        "Inventory Aging Report (optional)", type="xlsx"
    )

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Forecast Settings")

    doh_threshold = st.sidebar.number_input(
        "Target Days on Hand",
        min_value=1,
        max_value=60,
        value=21,
        help="Minimum days of coverage you want per category/package size group.",
    )

    velocity_adjustment = st.sidebar.number_input(
        "Velocity Adjustment",
        min_value=0.01,
        max_value=5.0,
        value=0.50,
        step=0.01,
        help="Multiply avg units/day by this factor (e.g., 0.5 for slower store).",
    )

    st.sidebar.markdown("---")
    st.sidebar.header("📅 Sales Period")
    st.sidebar.write("Select the number of days represented in your sales report:")
    date_diff = st.sidebar.slider("Days in Sales Period", 7, 90, 60)

    # Metric filter state
    filter_state = st.session_state.setdefault("metric_filter", "None")

    # -------------------------
    # CORE PROCESSING
    # -------------------------
    if inv_file and product_sales_file:
        try:
            # ----------------------------
            # Inventory load & normalize
            # ----------------------------
            inv_df = pd.read_csv(inv_file)
            inv_df.columns = inv_df.columns.str.strip().str.lower()

            inv_df = inv_df.rename(
                columns={
                    "product": "itemname",
                    "category": "subcategory",
                    "available": "onhandunits",
                }
            )

            inv_df["onhandunits"] = pd.to_numeric(
                inv_df.get("onhandunits", 0), errors="coerce"
            ).fillna(0)
            inv_df["subcategory"] = (
                inv_df["subcategory"].astype(str).str.strip().str.lower()
            )

            # --- STRAIN TYPE FROM NAME & CONTEXT ---
            # (HYBRID / SATIVA / INDICA / CBD / DISPOSABLE / INFUSED)
            def extract_strain_type(name: str, subcat: str) -> str:
                s = str(name).lower()
                c = str(subcat).lower()

                # Context flags
                is_vape_context = any(
                    kw in s or kw in c
                    for kw in ["vape", "vap", "cart", "cartridge", "pen", "pod"]
                )
                is_preroll_context = any(
                    kw in s or kw in c
                    for kw in ["pre roll", "preroll", "pre-roll", "joint", "cone"]
                )

                # Base strain type
                base_type = "unspecified"
                if "indica" in s:
                    base_type = "indica"
                elif "sativa" in s:
                    base_type = "sativa"
                elif "hybrid" in s:
                    base_type = "hybrid"
                elif "cbd" in s:
                    base_type = "cbd"

                # Disposables in vapes
                if ("disposable" in s or "dispos" in s) and is_vape_context:
                    return (
                        f"{base_type} disposable"
                        if base_type != "unspecified"
                        else "disposable"
                    )

                # Infused pre-rolls
                if "infused" in s and is_preroll_context:
                    return (
                        f"{base_type} infused"
                        if base_type != "unspecified"
                        else "infused"
                    )

                return base_type

            # --- PACKAGE SIZE PARSER (mg, g, PLUS .5 / 0.5 VAPE LOGIC) ---
            def extract_size(text, context=None):
                s = str(text).lower()
                c = str(context).lower() if context is not None else s

                # mg patterns (e.g. 10mg, 5.5 mg)
                mg = re.search(r"(\d+(\.\d+)?\s?mg)", s)
                if mg:
                    return mg.group(1).replace(" ", "")

                # gram patterns: 1g, 0.5g, .5g, 1.0 g, etc.
                g = re.search(r"((?:\d+\.?\d*|\.\d+)\s?g)", s)
                if g:
                    return g.group(1).replace(" ", "")

                # vape context: bare 0.5 or .5 → treat as 0.5g
                is_vape_context = any(
                    kw in s or kw in c
                    for kw in [
                        "vape",
                        "vap",
                        "cart",
                        "cartridge",
                        "pen",
                        "pod",
                        "disposable",
                    ]
                )
                if is_vape_context:
                    half = re.search(r"\b0\.5\b|\b\.5\b", s)
                    if half:
                        return "0.5g"

                return "unspecified"

            # Inventory fields
            inv_df["strain_type"] = inv_df.apply(
                lambda row: extract_strain_type(row["itemname"], row["subcategory"]),
                axis=1,
            )
            inv_df["packagesize"] = inv_df.apply(
                lambda row: extract_size(row["itemname"], row["subcategory"]), axis=1
            )
            inv_df["subcat_group"] = (
                inv_df["subcategory"] + " – " + inv_df["packagesize"]
            )

            inv_df = inv_df[
                [
                    "itemname",
                    "strain_type",
                    "packagesize",
                    "subcategory",
                    "subcat_group",
                    "onhandunits",
                ]
            ]

            # ----------------------------
            # Sales load & normalize
            # ----------------------------
            sales_raw = pd.read_excel(product_sales_file)

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

st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    page_icon="🌿"
)

# Background image (swap to Rebelle-branded art if desired)
background_url = "https://raw.githubusercontent.com/MAVet710/buyer-dashboard/main/IMG_7158.PNG"

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
        "To enable visuals, install Plotly with:\n"
        "`pip install plotly`"
    )

# =========================
# SIDEBAR: FILE UPLOADS & CONTROLS
# =========================
st.sidebar.header("📂 Upload Core Reports")

st.sidebar.markdown(
    "Upload **Dutchie-derived** reports for automated inventory and velocity analysis. "
    "Ensure column names and formats match your standard export templates."
)

inv_file = st.sidebar.file_uploader("Inventory CSV", type="csv")
sales_file = st.sidebar.file_uploader("Detailed Sales Breakdown by Product (optional)", type="xlsx")
product_sales_file = st.sidebar.file_uploader("Product Sales Report (required)", type="xlsx")
aging_file = st.sidebar.file_uploader("Inventory Aging Report (optional)", type="xlsx")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Forecast Settings")

doh_threshold = st.sidebar.number_input(
    "Target Days on Hand",
    min_value=1,
    max_value=60,
    value=21,
    help="Minimum days of coverage you want per category/package size group."
)

velocity_adjustment = st.sidebar.number_input(
    "Velocity Adjustment",
    min_value=0.01,
    max_value=5.0,
    value=0.50,
    step=0.01,
    help="Multiply average units/day by this factor to tune for store traffic (e.g., 0.5 for slower store)."
)

st.sidebar.markdown("---")
st.sidebar.header("📅 Sales Period")
st.sidebar.write("Select the number of days represented in your sales report:")
date_diff = st.sidebar.slider("Days in Sales Period", min_value=7, max_value=90, value=60)

# Metric filter state
filter_state = st.session_state.setdefault("metric_filter", "None")

# =========================
# CORE PROCESSING
# =========================
if inv_file and product_sales_file:
    try:
        # --- Inventory ingest & normalization ---
        inv_df = pd.read_csv(inv_file)
        inv_df.columns = inv_df.columns.str.strip().str.lower()

        # Normalize expected column names
        inv_df = inv_df.rename(
            columns={
                "product": "itemname",
                "category": "subcategory",
                "available": "onhandunits"
            }
        )

        # Numeric and text cleanup
        inv_df["onhandunits"] = pd.to_numeric(inv_df.get("onhandunits", 0), errors="coerce").fillna(0)
        inv_df["subcategory"] = inv_df["subcategory"].astype(str).str.strip().str.lower()

        # Extract package sizes from product names (mg, g, oz)
        def extract_size(name):
            name = str(name).lower()
            mg_match = re.search(r"(\d+\s?mg)", name)
            g_match = re.search(r"(\d+\.?\d*\s?(g|oz))", name)
            if mg_match:
                return mg_match.group(1)
            if g_match:
                return g_match.group(1)
            return "unspecified"

        inv_df["packagesize"] = inv_df["itemname"].apply(extract_size)
        inv_df["subcat_group"] = inv_df["subcategory"] + " – " + inv_df["packagesize"]
        inv_df = inv_df[["itemname", "packagesize", "subcategory", "subcat_group", "onhandunits"]]

        # --- Sales ingest & normalization ---
        sales_raw = pd.rea_

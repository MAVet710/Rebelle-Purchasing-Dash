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

# 🟢 UPDATED PAGE ICON (FAVICON)
page_icon_url = "https://raw.githubusercontent.com/MAVet710/Rebelle-Purchasing-Dash/ef50d34e20caf45231642e957137d6141082dbb9/rebelle.jpg"

st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    page_icon=page_icon_url
)

# 🟢 UPDATED BACKGROUND IMAGE
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
        "If using Streamlit Cloud, add `plotly` to your requirements.txt file."
    )

# =========================
# SIDEBAR: FILE UPLOADS & CONTROLS
# =========================
st.sidebar.header("📂 Upload Core Reports")

st.sidebar.markdown(
    "Upload **Dutchie-derived** reports for automated inventory and velocity analysis."
)

inv_file = st.sidebar.file_uploader("Inventory CSV", type="csv")
sales_file = st.sidebar.file_uploader("Detailed Sales Breakdown (optional)", type="xlsx")
product_sales_file = st.sidebar.file_uploader("Product Sales Report (required)", type="xlsx")
aging_file = st.sidebar.file_uploader("Inventory Aging Report (optional)", type="xlsx")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Forecast Settings")

doh_threshold = st.sidebar.number_input("Target Days on Hand", 1, 60, 21)
velocity_adjustment = st.sidebar.number_input("Velocity Adjustment", 0.01, 5.0, 0.50, 0.01)

st.sidebar.markdown("---")
st.sidebar.header("📅 Sales Period")
date_diff = st.sidebar.slider("Days in Sales Period", 7, 90, 60)

filter_state = st.session_state.setdefault("metric_filter", "None")

# =========================
# CORE PROCESSING
# =========================
if inv_file and product_sales_file:
    try:
        # ----------------------------
        # Inventory load
        # ----------------------------
        inv_df = pd.read_csv(inv_file)
        inv_df.columns = inv_df.columns.str.strip().str.lower()

        inv_df = inv_df.rename(columns={
            "product": "itemname",
            "category": "subcategory",
            "available": "onhandunits"
        })

        inv_df["onhandunits"] = pd.to_numeric(inv_df.get("onhandunits", 0), errors="coerce").fillna(0)
        inv_df["subcategory"] = inv_df["subcategory"].astype(str).strip().str.lower()

        def extract_size(name):
            name = str(name).lower()
            mg = re.search(r"(\d+\s?mg)", name)
            g = re.search(r"(\d+\.?\d*\s?(g|oz))", name)
            return mg.group(1) if mg else g.group(1) if g else "unspecified"

        inv_df["packagesize"] = inv_df["itemname"].apply(extract_size)
        inv_df["subcat_group"] = inv_df["subcategory"] + " – " + inv_df["packagesize"]

        inv_df = inv_df[["itemname", "packagesize", "subcategory", "subcat_group", "onhandunits"]]

        # ----------------------------
        # Sales load
        # ----------------------------
        sales_raw = pd.read_excel(product_sales_file)
        sales_raw.columns = sales_raw.columns.astype(str).str.strip().str.lower()

        if "mastercategory" not in sales_raw.columns and "category" in sales_raw.columns:
            sales_raw = sales_raw.rename(columns={"category": "mastercategory"})

        sales_raw = sales_raw.rename(columns={
            "product": "product",
            "quantity sold": "unitssold",
            "weight": "packagesize"
        })

        sales_df = sales_raw[sales_raw["mastercategory"].notna()].copy()
        sales_df["mastercategory"] = sales_df["mastercategory"].astype(str).strip().str.lower()
        sales_df = sales_df[~sales_df["mastercategory"].str.contains("accessor")]
        sales_df = sales_df[sales_df["mastercategory"] != "all"]

        # ----------------------------
        # Aggregate + velocity
        # ----------------------------
        inventory_summary = inv_df.groupby(["subcategory", "packagesize"])["onhandunits"].sum().reset_index()

        agg = sales_df.groupby("mastercategory").agg({"unitssold": "sum"}).reset_index()
        agg["avgunitsperday"] = agg["unitssold"] / date_diff * velocity_adjustment

        detail = pd.merge(
            inventory_summary,
            agg,
            left_on="subcategory",
            right_on="mastercategory",
            how="left"
        ).fillna(0)

        detail["daysonhand"] = np.where(
            detail["avgunitsperday"] > 0,
            detail["onhandunits"] / detail["avgunitsperday"],
            0
        ).astype(int)

        detail["reorderqty"] = np.where(
            detail["daysonhand"] < doh_threshold,
            np.ceil((doh_threshold - detail["daysonhand"]) * detail["avgunitsperday"]).astype(int),
            0
        )

        def reorder_tag(row):
            if row["daysonhand"] <= 7: return "1 – Reorder ASAP"
            if row["daysonhand"] <= 21: return "2 – Watch Closely"
            if row["avgunitsperday"] == 0: return "4 – Dead Item"
            return "3 – Comfortable Cover"

        detail["reorderpriority"] = detail.apply(reorder_tag, axis=1)

        # =========================
        # METRICS
        # =========================
        total_units = int(sales_df["unitssold"].sum())
        active_categories = detail["subcategory"].nunique()
        reorder_asap = (detail["reorderpriority"] == "1 – Reorder ASAP").sum()
        watchlist_items = (detail["reorderpriority"] == "2 – Watch Closely").sum()

        st.markdown("### 📊 Portfolio Snapshot")

        c1, c2, c3, c4 = st.columns(4)
        if c1.button(f"Total Units Sold: {total_units:,}"): st.session_state.metric_filter = "None"
        if c2.button(f"Active Subcategories: {active_categories}"): st.session_state.metric_filter = "None"
        if c3.button(f"Watchlist Items: {watchlist_items}"): st.session_state.metric_filter = "Watchlist"
        if c4.button(f"Reorder ASAP: {reorder_asap}"): st.session_state.metric_filter = "Reorder ASAP"

        # =========================
        # TABLES
        # =========================
        st.markdown("### 🧮 Inventory Forecast by Subcategory")

        detail_view = detail.copy()

        if st.session_state.metric_filter == "Watchlist":
            detail_view = detail_view[detail_view["reorderpriority"] == "2 – Watch Closely"]
        elif st.session_state.metric_filter == "Reorder ASAP":
            detail_view = detail_view[detail_view["reorderpriority"] == "1 – Reorder ASAP"]

        for cat, group in detail_view.groupby("subcategory"):
            avg_doh = int(group["daysonhand"].mean())
            with st.expander(f"{cat.title()} – Avg DOH: {avg_doh}"):
                st.dataframe(group, use_container_width=True)

        # =========================
        # EXPORT
        # =========================
        csv = detail.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV", csv, "rebelle_forecast.csv", "text/csv")

        # =========================
        # CHART
        # =========================
        st.markdown("### 📈 Coverage by Priority")

        priority_summary = (
            detail.groupby("reorderpriority")["subcategory"]
            .count()
            .reset_index()
            .rename(columns={"subcategory": "itemcount"})
        )

        if PLOTLY_AVAILABLE:
            fig = px.bar(priority_summary, x="reorderpriority", y="itemcount",
                         title="Item Count by Reorder Priority")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Plotly not installed. Add `plotly` to requirements.txt to enable charts.")

    except Exception as e:
        st.error(f"Error processing files: {e}")

else:
    st.info("Please upload both an Inventory CSV and Product Sales Report.")

# =========================
# FOOTER
# =========================
st.markdown("---")
year = datetime.now().year
st.markdown(
    f'<div class="footer">{LICENSE_FOOTER} • © {year}</div>',
    unsafe_allow_html=True,
)

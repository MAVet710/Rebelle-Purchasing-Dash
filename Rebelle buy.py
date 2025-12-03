import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import re
from datetime import datetime

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

# Background image (hosted asset – swap if Rebelle wants custom art)
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
        sales_raw = pd.read_excel(product_sales_file)
        sales_raw.columns = sales_raw.columns.astype(str).str.strip().str.lower()

        if "mastercategory" not in sales_raw.columns and "category" in sales_raw.columns:
            sales_raw = sales_raw.rename(columns={"category": "mastercategory"})

        sales_raw = sales_raw.rename(
            columns={
                "product": "product",
                "quantity sold": "unitssold",
                "weight": "packagesize",
            }
        )

        # Filter to real product categories (exclude accessories, "all", etc.)
        sales_df = sales_raw[sales_raw["mastercategory"].notna()].copy()
        sales_df["mastercategory"] = sales_df["mastercategory"].astype(str).str.strip().str.lower()
        sales_df = sales_df[~sales_df["mastercategory"].str.contains("accessor")]
        sales_df = sales_df[sales_df["mastercategory"] != "all"]

        # --- Aggregate inventory by subcategory & package size ---
        inventory_summary = (
            inv_df.groupby(["subcategory", "packagesize"])["onhandunits"]
            .sum()
            .reset_index()
        )

        # --- Velocity (units per day) ---
        agg = sales_df.groupby("mastercategory").agg({"unitssold": "sum"}).reset_index()
        agg["avgunitsperday"] = agg["unitssold"].astype(float) / date_diff * velocity_adjustment

        # --- Merge inventory with velocity ---
        detail = pd.merge(
            inventory_summary,
            agg,
            left_on="subcategory",
            right_on="mastercategory",
            how="left",
        ).fillna(0)

        # --- Days on Hand & reorder quantity ---
        detail["daysonhand"] = np.where(
            detail["avgunitsperday"] > 0,
            detail["onhandunits"] / detail["avgunitsperday"],
            np.nan,
        )
        detail["daysonhand"] = (
            detail["daysonhand"]
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0)
            .astype(int)
        )

        detail["reorderqty"] = np.where(
            detail["daysonhand"] < doh_threshold,
            np.ceil((doh_threshold - detail["daysonhand"]) * detail["avgunitsperday"]).astype(int),
            0,
        )

        # --- Priority tagging ---
        def reorder_tag(row):
            if row["daysonhand"] <= 7:
                return "1 – Reorder ASAP"
            if row["daysonhand"] <= 21:
                return "2 – Watch Closely"
            if row["avgunitsperday"] == 0:
                return "4 – Dead Item"
            return "3 – Comfortable Cover"

        detail["reorderpriority"] = detail.apply(reorder_tag, axis=1)
        detail = detail.sort_values(
            ["reorderpriority", "avgunitsperday"], ascending=[True, False]
        )

        # =========================
        # TOPLINE METRICS
        # =========================
        total_units = sales_df["unitssold"].astype(float).sum()
        active_categories = detail["subcategory"].nunique()
        reorder_asap = detail[detail["reorderpriority"] == "1 – Reorder ASAP"].shape[0]
        watchlist_items = detail[detail["reorderpriority"] == "2 – Watch Closely"].shape[0]

        st.markdown("### 📊 Portfolio Snapshot")

        c1, c2, c3, c4 = st.columns(4)

        if c1.button(f"Total Units Sold: {int(total_units):,}"):
            st.session_state.metric_filter = "None"
        c1.markdown('<span class="metric-label">Across selected period</span>', unsafe_allow_html=True)

        if c2.button(f"Active Subcategories: {active_categories}"):
            st.session_state.metric_filter = "None"
        c2.markdown('<span class="metric-label">Unique subcategory groups</span>', unsafe_allow_html=True)

        if c3.button(f"Watchlist Items: {watchlist_items}"):
            st.session_state.metric_filter = "Watchlist"
        c3.markdown('<span class="metric-label">Days on hand nearing threshold</span>', unsafe_allow_html=True)

        if c4.button(f"Reorder ASAP: {reorder_asap}"):
            st.session_state.metric_filter = "Reorder ASAP"
        c4.markdown('<span class="metric-label">Critically low coverage</span>', unsafe_allow_html=True)

        st.markdown("---")

        # =========================
        # FILTER LOGIC
        # =========================
        def highlight_low_days(val):
            try:
                val = int(val)
                return "color: #FF3131; font-weight: bold;" if val < doh_threshold else ""
            except Exception:
                return ""

        if st.session_state.metric_filter == "Watchlist":
            detail_view = detail[detail["reorderpriority"] == "2 – Watch Closely"]
        elif st.session_state.metric_filter == "Reorder ASAP":
            detail_view = detail[detail["reorderpriority"] == "1 – Reorder ASAP"]
        else:
            detail_view = detail.copy()

        # =========================
        # CATEGORY-LEVEL TABLES
        # =========================
        st.markdown("### 🧮 Inventory Forecast by Subcategory & Package Size")

        master_groups = detail_view.groupby("subcategory")
        for cat, group in master_groups:
            avg_doh = int(np.floor(group["daysonhand"].mean()))
            header = f"{cat.title()} – Avg Days On Hand: {avg_doh}"
            with st.expander(header, expanded=False):
                display_cols = [
                    "packagesize",
                    "onhandunits",
                    "unitssold",
                    "avgunitsperday",
                    "daysonhand",
                    "reorderqty",
                    "reorderpriority",
                ]
                display_cols = [c for c in display_cols if c in group.columns]
                styled_cat_df = group[display_cols].style.applymap(
                    highlight_low_days, subset=["daysonhand"]
                )
                st.dataframe(styled_cat_df, use_container_width=True)

        # =========================
        # EXPORT
        # =========================
        csv = detail.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download Full Forecast as CSV",
            csv,
            f"{CLIENT_NAME.lower().replace(' ', '_')}_buyer_forecast.csv",
            "text/csv",
        )

        # =========================
        # OPTIONAL SIMPLE CHART
        # =========================
        st.markdown("### 📈 Coverage by Priority")
        priority_summary = (
            detail.groupby("reorderpriority")["subcategory"]
            .count()
            .reset_index()
            .rename(columns={"subcategory": "itemcount"})
        )
        fig = px.bar(
            priority_summary,
            x="reorderpriority",
            y="itemcount",
            title="Item Count by Reorder Priority",
        )
        fig.update_layout(
            xaxis_title="Reorder Priority",
            yaxis_title="Number of Subcat/Package Combinations",
        )
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error processing files: {e}")

else:
    st.info("Please upload both an **Inventory CSV** and a **Product Sales Report** to begin analysis.")

# =========================
# FOOTER
# =========================
st.markdown("---")
year = datetime.now().year
st.markdown(
    f'<div class="footer">{LICENSE_FOOTER} • © {year}</div>',
    unsafe_allow_html=True,
)

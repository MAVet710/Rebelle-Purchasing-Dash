import streamlit as st
import pandas as pd
import numpy as np
import io
import math
import re
from datetime import datetime

# Optional Plotly import
try:
    import plotly.express as px
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

# Optional Google Sheets imports
try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSHEETS = True
except Exception:
    HAS_GSHEETS = False

# ============================================================================
# PAGE SETUP
# ============================================================================
st.set_page_config(
    page_title="Rebelle Cannabis Purchasing Dashboard",
    page_icon="🍃",
    layout="wide",
)

REB_BACKGROUND = (
    "https://raw.githubusercontent.com/MAVet710/Rebelle-Purchasing-Dash/"
    "ef50d34e20caf45231642e957137d6141082dbb9/rebelle%20main.png"
)

BASE_CSS = f"""
<style>
.stApp {{
    background-image: url('{REB_BACKGROUND}');
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}}

.block-container {{
    background-color: rgba(0,0,0,0.80);
    padding: 2rem 2.5rem;
    border-radius: 18px;
    color: #f5f5f5;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}

[data-testid="stSidebar"] {{
    background-color: #0f172a;
    color: #e5e7eb;
}}

.small-muted {{
    font-size: 0.8rem;
    color: #9ca3af;
}}

.metric-chip {{
    padding: 0.6rem 0.9rem;
    border-radius: 999px;
    border: 1px solid rgba(148,163,184,0.4);
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    cursor: pointer;
    margin-right: 0.4rem;
    margin-bottom: 0.4rem;
}}

.metric-chip span.label {{
    font-size: 0.80rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #9ca3af;
}}

.metric-chip span.value {{
    font-weight: 600;
}}

.metric-chip.danger {{
    border-color: rgba(239,68,68,0.6);
    background: rgba(239,68,68,0.06);
}}

.metric-chip.warning {{
    border-color: rgba(234,179,8,0.6);
    background: rgba(234,179,8,0.05);
}}

.metric-chip.neutral {{
    border-color: rgba(59,130,246,0.5);
    background: rgba(37,99,235,0.05);
}}

.metric-chip .dot {{
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: #f97316;
}}

.table-header {{
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-size: 0.75rem;
    color: #9ca3af;
}}

.red-cell {{
    color: #f97373 !important;
    font-weight: 600 !important;
}}

.po-box-label {{
    font-size: 0.8rem;
    font-weight: 600;
    color: #e5e7eb;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}}

.po-box-input > div > div > input {{
    background-color: rgba(15,23,42,0.85);
    color: #f9fafb;
}}

.vendor-table .row_heading, .vendor-table .col_heading, .vendor-table td {{
    color: #f9fafb !important;
}}
</style>
"""
st.markdown(BASE_CSS, unsafe_allow_html=True)

# ============================================================================
# GOOGLE SHEETS / VENDOR AUTOSAVE SETUP
# ============================================================================

VENDOR_SHEET_ID = None
GOOGLE_SHEETS_ENABLED = False
sheets_status = "Vendor autosave: in-memory only."

try:
    if "gcp_service_account" in st.secrets:
        sa_block = st.secrets["gcp_service_account"]
        if isinstance(sa_block, dict):
            if "VENDOR_SHEET_ID" in sa_block:
                VENDOR_SHEET_ID = sa_block["VENDOR_SHEET_ID"]
            elif "VENDOR_SHEET_ID" in st.secrets:
                VENDOR_SHEET_ID = st.secrets["VENDOR_SHEET_ID"]

            if VENDOR_SHEET_ID and HAS_GSHEETS:
                creds = Credentials.from_service_account_info(
                    sa_block,
                    scopes=[
                        "https://www.googleapis.com/auth/spreadsheets",
                        "https://www.googleapis.com/auth/drive",
                    ],
                )
                gc = gspread.authorize(creds)
                GOOGLE_SHEETS_ENABLED = True
                sheets_status = "Google Sheets connected. Vendor autosave is ON."
            elif not HAS_GSHEETS:
                sheets_status = "Google Sheets client library not installed; autosave is in-memory only."
            else:
                sheets_status = "VENDOR_SHEET_ID missing in secrets; autosave is in-memory only."
        else:
            sheets_status = "gcp_service_account in secrets is not a dict; autosave is in-memory only."
    else:
        sheets_status = "gcp_service_account not defined in secrets; autosave is in-memory only."
except Exception as e:
    GOOGLE_SHEETS_ENABLED = False
    sheets_status = f"Error initializing Google Sheets: {e}"

# ============================================================================
# SESSION STATE SETUP
# ============================================================================

if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "trial"
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "trial_key_valid" not in st.session_state:
    st.session_state.trial_key_valid = False
if "app_section" not in st.session_state:
    st.session_state.app_section = "Inventory Dashboard"
if "vendor_df" not in st.session_state:
    st.session_state.vendor_df = pd.DataFrame(
        columns=[
            "Vendor",
            "Brands",
            "Spotlight Products",
            "Contact Name",
            "Email",
            "Phone",
            "Net Terms",
            "Notes",
        ]
    )
if "metric_filter" not in st.session_state:
    st.session_state.metric_filter = "None"

# ============================================================================
# SIDEBAR – THEME, AUTH, NAV
# ============================================================================

with st.sidebar:
    st.markdown("### 🌌 Theme")
    theme = st.radio("Mode", ["Dark", "Light"], index=0, label_visibility="collapsed")
    if theme == "Light":
        st.markdown(
            """
            <style>
            .block-container {background-color: rgba(255,255,255,0.92); color:#111827;}
            [data-testid="stSidebar"] {background-color:#f3f4f6; color:#111827;}
            .po-box-label {color:#111827;}
            .metric-chip {border-color:rgba(148,163,184,0.8);}
            </style>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### 👑 Admin Login")
    if st.session_state.is_admin:
        st.success("Admin mode: unlimited access.")
        if st.button("Logout Admin"):
            st.session_state.is_admin = False
            st.session_state.auth_mode = "trial"
    else:
        admin_user = st.text_input("Username", value="", placeholder="Admin username")
        admin_pass = st.text_input(
            "Password", value="", type="password", placeholder="Password"
        )
        if st.button("Login as Admin"):
            if admin_user == "God" and admin_pass == "Major420":
                st.session_state.is_admin = True
                st.session_state.auth_mode = "admin"
                st.success("Admin mode enabled.")
            else:
                st.error("Invalid admin credentials.")

    if not st.session_state.is_admin:
        st.markdown("---")
        st.markdown("### ⏱️ Trial Access")
        trial_input = st.text_input("Enter trial key", value="", type="password")
        if st.button("Activate Trial"):
            if trial_input.strip() == "rebelle24":
                st.session_state.trial_key_valid = True
                st.success("Trial key accepted – access granted.")
            else:
                st.error("Invalid trial key.")

    st.markdown("---")
    st.markdown("### ℹ️ Vendor Autosave")
    st.info(sheets_status)

    # Admin-only debug (hidden from clients)
    if st.session_state.is_admin:
        with st.expander("Developer debug (hidden from clients)", expanded=False):
            st.caption("Loaded secrets (keys only):")
            try:
                sec_view = {}
                for k, v in st.secrets.items():
                    if isinstance(v, dict):
                        sec_view[k] = list(v.keys())
                    else:
                        sec_view[k] = "***"
                st.json(sec_view)
            except Exception as e:
                st.write(f"Debug error: {e}")

    st.markdown("---")
    st.markdown("### App Section")

    sections = ["Inventory Dashboard", "PO Builder", "Vendor Tracker"]
    current_section = st.session_state.get("app_section", "Inventory Dashboard")
    if current_section not in sections:
        current_section = "Inventory Dashboard"

    section = st.radio(
        "",
        sections,
        index=sections.index(current_section),
        label_visibility="collapsed",
    )
    st.session_state.app_section = section

# Lock app if no access
if not st.session_state.is_admin and not st.session_state.trial_key_valid:
    st.title("🍃 Rebelle Cannabis Purchasing Dashboard")
    st.write("Client: **Rebelle Cannabis**")
    st.warning("Trial key or admin login required to use the dashboard.")
    st.stop()

# ============================================================================
# HEADER
# ============================================================================

st.title("🍃 Rebelle Cannabis Purchasing Dashboard")
st.write("**Client:** Rebelle Cannabis")
st.caption("Streamlined purchasing visibility powered by Dutchie / BLAZE / other POS exports.")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_days_on_hand(onhand_units, avg_units_per_day):
    if avg_units_per_day <= 0:
        return 0
    return int(onhand_units / avg_units_per_day)


def calculate_reorder_qty(doh, threshold, avg_units_per_day):
    if avg_units_per_day <= 0:
        return 0
    gap = threshold - doh
    if gap <= 0:
        return 0
    return int(math.ceil(gap * avg_units_per_day))


def normalize_name(s: str) -> str:
    return s.lower().replace(" ", "").replace("_", "").replace("-", "")


def find_column(possible_cols, df_columns):
    """
    Flexible matching for different column name variants.
    - Ignores case
    - Ignores spaces, underscores, and hyphens
    Returns the first match from df_columns or None.
    """
    cleaned_cols = {normalize_name(c): c for c in df_columns}
    for target in possible_cols:
        key = normalize_name(target)
        if key in cleaned_cols:
            return cleaned_cols[key]
    return None


def parse_sales_report(product_sales_file):
    """
    Handles Blaze-style and other Excel exports where headers may not be on row 0.
    Looks across all rows in all sheets for a row that contains BOTH:
      - a quantity-sold column header variant
      - a category/mastercategory header variant
    Then promotes that row to the header and returns a clean DataFrame plus
    the resolved quantity + category column names.
    """
    xls = pd.ExcelFile(product_sales_file)

    # Quantity variants: Blaze/Dutchie/other POS
    qty_variants = [
        "quantitysold",
        "quantity sold",
        "qtysold",
        "qty sold",
        "qty",
        "qty.",
        "sold",
        "units",
        "units sold",
        "units_sold",
        "salesunits",
        "sales units",
        "total units",
        "totalunits",
        "total quantity",
        "total quantity sold",
        "sum quantity",
        "sum of quantity",
        "sold units",
        "units sold (qty)",
    ]

    # Category/master variants
    cat_variants = [
        "mastercategory",
        "master category",
        "category",
        "productcategory",
        "product category",
        "product type",
        "producttype",
        "item category",
        "itemcategory",
        "subcategory",
        "sub category",
        "department",
        "dept",
        "prod category",
        "product group",
        "productgroup",
    ]

    qty_norms = {normalize_name(v) for v in qty_variants}
    cat_norms = {normalize_name(v) for v in cat_variants}

    last_sheet_info = []

    for sheet in xls.sheet_names:
        df_raw = xls.parse(sheet, header=None)
        header_row_idx = None

        # search row-by-row for header
        for i in range(len(df_raw)):
            row_vals = [str(x).strip() for x in df_raw.iloc[i].tolist()]
            row_norms = {normalize_name(x) for x in row_vals}

            if (row_norms & qty_norms) and (row_norms & cat_norms):
                header_row_idx = i
                break

        # record info for error messages (first few rows)
        last_sheet_info.append(
            (sheet, df_raw.head().values.tolist())
        )

        if header_row_idx is not None:
            header_vals = df_raw.iloc[header_row_idx].astype(str).tolist()
            df = df_raw.iloc[header_row_idx + 1 :].copy()
            df.columns = header_vals
            df = df.dropna(how="all")
            df.columns = df.columns.astype(str).str.strip().str.lower()

            qty_col = find_column(qty_variants, df.columns)
            cat_col = find_column(cat_variants, df.columns)

            return df, sheet, qty_col, cat_col

    # if we get here, nothing matched
    raise ValueError(
        "Could not find a header row with both a quantity-sold column and "
        "a category/mastercategory column.\n\n"
        "Sample of what was scanned (first few rows of each sheet):\n"
        + "\n".join(
            f"- Sheet '{s}': first rows {rows}" for s, rows in last_sheet_info[:3]
        )
    )

# ============================================================================
# INVENTORY DASHBOARD
# ============================================================================

if st.session_state.app_section == "Inventory Dashboard":
    st.markdown("## 📦 Inventory Dashboard")

    st.markdown("##### Data Source (for your reference)")
    data_source = st.radio(
        "POS / Reporting Backend",
        ["Dutchie", "BLAZE", "Other"],
        horizontal=True,
        label_visibility="collapsed",
    )

    col_up1, col_up2 = st.columns(2)
    with col_up1:
        inv_file = st.file_uploader("Inventory CSV", type=["csv"])
    with col_up2:
        product_sales_file = st.file_uploader(
            "Product Sales Report (XLSX)", type=["xlsx"]
        )

    doh_threshold = st.slider("Days on Hand Threshold", min_value=7, max_value=45, value=21)
    date_diff = st.slider("Days in Sales Period", min_value=7, max_value=90, value=60)
    velocity_adjustment = st.number_input(
        "Velocity Adjustment (e.g. 0.5 for slower stores)",
        min_value=0.1,
        max_value=5.0,
        value=1.0,
        step=0.1,
    )

    if inv_file is None or product_sales_file is None:
        st.info("Upload **Inventory CSV** and **Product Sales** to generate forecasts.")
    else:
        try:
            # ----------------- INVENTORY FILE -----------------
            inv_df = pd.read_csv(inv_file)
            inv_df.columns = inv_df.columns.astype(str).str.strip().str.lower()

            # Product name / SKU / description variants
            inv_name_variants = [
                "product",
                "product name",
                "productname",
                "item",
                "item name",
                "itemname",
                "sku",
                "sku name",
                "sku description",
                "product description",
                "description",
                "strain",
                "producttitle",
                "item description",
            ]

            # On-hand / available quantity variants
            inv_qty_variants = [
                "available",
                "availableqty",
                "available quantity",
                "available_qty",
                "on hand",
                "onhand",
                "on_hand",
                "on hand qty",
                "onhandqty",
                "onhandunits",
                "ending inventory",
                "ending qty",
                "current inventory",
                "current qty",
                "inventory on hand",
                "stock on hand",
                "qoh",
                "qty on hand",
                "quantity on hand",
                "quantity",
                "qty",
                "qty.",
            ]

            # Category / product type variants
            inv_cat_variants = [
                "category",
                "subcategory",
                "mastercategory",
                "productcategory",
                "product category",
                "product type",
                "producttype",
                "item category",
                "itemcategory",
                "department",
                "dept",
                "prod category",
                "product group",
                "productgroup",
                "menu category",
                "menucategory",
            ]

            name_col = find_column(inv_name_variants, inv_df.columns)
            qty_col = find_column(inv_qty_variants, inv_df.columns)
            cat_col = find_column(inv_cat_variants, inv_df.columns)

            if name_col is None or qty_col is None or cat_col is None:
                st.error(
                    "Inventory file missing required columns.\n\n"
                    "I tried to find something like:\n"
                    "- Product: "
                    + ", ".join(inv_name_variants)
                    + "\n- Quantity On Hand: "
                    + ", ".join(inv_qty_variants)
                    + "\n- Category: "
                    + ", ".join(inv_cat_variants)
                    + "\n\n"
                    "Columns in your inventory file:\n"
                    + ", ".join(inv_df.columns)
                )
                st.stop()

            inv_df = inv_df.rename(
                columns={
                    name_col: "itemname",
                    cat_col: "subcategory",
                    qty_col: "onhandunits",
                }
            )
            inv_df["onhandunits"] = pd.to_numeric(
                inv_df["onhandunits"], errors="coerce"
            ).fillna(0)
            inv_df["subcategory"] = (
                inv_df["subcategory"].astype(str).str.strip().str.lower()
            )

            def extract_size(name: str) -> str:
                name = str(name).lower()
                mg_match = re.search(r"(\d+\.?\d*\s?mg)", name)
                g_match = re.search(r"(\d+\.?\d*\s?(g|gram|grams|oz|ounce|ounces))", name)
                if mg_match:
                    return mg_match.group(1)
                if g_match:
                    return g_match.group(1)
                frac = re.search(r"(\d+\/\d+\s?oz)", name)
                if frac:
                    return frac.group(1)
                return "unspecified"

            def detect_type(name: str) -> str:
                n = str(name).lower()
                if "disposable" in n and ("vape" in n or "pen" in n):
                    return "Disposable Vape"
                if "infused" in n and ("pre-roll" in n or "pre roll" in n or "joint" in n):
                    return "Infused Pre-Roll"
                if "pre-roll" in n or "pre roll" in n or "joint" in n:
                    return "Pre-Roll"
                if "sativa" in n:
                    return "Sativa"
                if "indica" in n:
                    return "Indica"
                if "hybrid" in n:
                    return "Hybrid"
                if "cbd" in n:
                    return "CBD"
                return "Unspecified"

            inv_df["packagesize"] = inv_df["itemname"].apply(extract_size)
            inv_df["cannabis_type"] = inv_df["itemname"].apply(detect_type)

            inv_summary = (
                inv_df.groupby(["subcategory", "packagesize", "cannabis_type"])["onhandunits"]
                .sum()
                .reset_index()
            )

            # ----------------- PRODUCT SALES FILE (SMART HEADER PARSE) -----------------
            sales_raw, used_sheet, qty_sold_col, cat_sales_col = parse_sales_report(
                product_sales_file
            )
            st.caption(f"Using Product Sales sheet: **{used_sheet}**")

            if qty_sold_col is None or cat_sales_col is None:
                st.error(
                    "Unexpected issue reading Product Sales sheet.\n\n"
                    "**Columns in selected sheet:** "
                    + ", ".join(list(sales_raw.columns))
                )
                st.stop()

            sales_df = sales_raw.rename(
                columns={
                    qty_sold_col: "unitssold",
                    cat_sales_col: "mastercategory",
                }
            )

            sales_df["mastercategory"] = (
                sales_df["mastercategory"].astype(str).str.strip().str.lower()
            )

            # aggregate per mastercategory
            agg_sales = (
                sales_df.groupby("mastercategory")["unitssold"]
                .sum()
                .reset_index()
            )
            agg_sales["avgunitsperday"] = (
                agg_sales["unitssold"].astype(float) / float(date_diff) * velocity_adjustment
            )

            # join inventory rollup to sales summary
            detail = inv_summary.merge(
                agg_sales,
                left_on="subcategory",
                right_on="mastercategory",
                how="left",
            ).fillna({"unitssold": 0, "avgunitsperday": 0})

            # DOH & reorder math
            detail["daysonhand"] = detail.apply(
                lambda r: calculate_days_on_hand(r["onhandunits"], r["avgunitsperday"]),
                axis=1,
            )
            detail["reorderqty"] = detail.apply(
                lambda r: calculate_reorder_qty(
                    r["daysonhand"], doh_threshold, r["avgunitsperday"]
                ),
                axis=1,
            )

            def reorder_tag(row):
                if row["avgunitsperday"] == 0 and row["onhandunits"] > 0:
                    return "4 – Dead Item"
                if row["daysonhand"] <= 7:
                    return "1 – Reorder ASAP"
                if row["daysonhand"] <= 21:
                    return "2 – Watch Closely"
                return "3 – Comfortable Cover"

            detail["reorderpriority"] = detail.apply(reorder_tag, axis=1)

            # metrics
            total_units = sales_df["unitssold"].astype(float).sum()
            active_categories = detail["subcategory"].nunique()
            reorder_asap = detail[detail["reorderpriority"] == "1 – Reorder ASAP"].shape[0]
            watchlist_items = detail[detail["reorderpriority"] == "2 – Watch Closely"].shape[0]

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button(f"🔢 Total Units Sold: {int(total_units)}"):
                    st.session_state.metric_filter = "None"
            with c2:
                if st.button(f"📂 Active Categories: {active_categories}"):
                    st.session_state.metric_filter = "None"
            with c3:
                if st.button(f"👀 Watchlist: {watchlist_items}"):
                    st.session_state.metric_filter = "Watchlist"
            with c4:
                if st.button(f"⏱️ Reorder ASAP: {reorder_asap}"):
                    st.session_state.metric_filter = "Reorder ASAP"

            mf = st.session_state.get("metric_filter", "None")
            if mf == "Watchlist":
                detail_view = detail[detail["reorderpriority"] == "2 – Watch Closely"]
            elif mf == "Reorder ASAP":
                detail_view = detail[detail["reorderpriority"] == "1 – Reorder ASAP"]
            else:
                detail_view = detail.copy()

            st.markdown("### Inventory Forecast Table")

            grouped = (
                detail_view.sort_values(
                    ["reorderpriority", "avgunitsperday"], ascending=[True, False]
                ).groupby("subcategory")
            )

            for cat, group in grouped:
                avg_doh = int(
                    np.floor(group["daysonhand"].replace([np.inf, -np.inf], 0).mean())
                )
                with st.expander(f"{cat.title()} – Avg Days On Hand: {avg_doh}"):
                    show_df = group[
                        [
                            "packagesize",
                            "cannabis_type",
                            "onhandunits",
                            "unitssold",
                            "avgunitsperday",
                            "daysonhand",
                            "reorderqty",
                            "reorderpriority",
                        ]
                    ].rename(
                        columns={
                            "packagesize": "Pack Size",
                            "cannabis_type": "Type",
                            "onhandunits": "On Hand Units",
                            "unitssold": "Units Sold (Period)",
                            "avgunitsperday": "Avg Units / Day",
                            "daysonhand": "Days On Hand",
                            "reorderqty": "Reorder Qty",
                            "reorderpriority": "Priority",
                        }
                    )

                    styled = show_df.style.applymap(
                        lambda x: "color:#f97373; font-weight:600;"
                        if isinstance(x, (int, float)) and x < doh_threshold
                        else "",
                        subset=["Days On Hand"],
                    )
                    st.dataframe(styled, use_container_width=True)

            csv = detail.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download Forecast CSV",
                csv,
                file_name="rebelle_buyer_forecast.csv",
                mime="text/csv",
            )

        except Exception as e:
            st.error(f"Error processing files: {e}")

# ============================================================================
# PO BUILDER
# ============================================================================

elif st.session_state.app_section == "PO Builder":
    st.markdown("## 🧾 Purchase Order Builder")

    c_po1, c_po2, c_po3 = st.columns(3)
    with c_po1:
        po_number = st.text_input("PO Number")
    with c_po2:
        po_date = st.date_input("PO Date", value=datetime.today())
    with c_po3:
        vendor_name = st.text_input("Vendor Name")

    c_po4, c_po5 = st.columns(2)
    with c_po4:
        buyer_name = st.text_input("Buyer Name")
    with c_po5:
        terms = st.text_input("Payment Terms", value="Net 30")

    st.markdown("#### Line Items")

    if "po_lines" not in st.session_state:
        st.session_state.po_lines = pd.DataFrame(
            columns=["SKU", "Description", "Units", "Unit Cost", "Line Total"]
        )

    if st.button("➕ Add Line"):
        st.session_state.po_lines = pd.concat(
            [
                st.session_state.po_lines,
                pd.DataFrame(
                    [["", "", 0, 0.0, 0.0]],
                    columns=st.session_state.po_lines.columns,
                ),
            ],
            ignore_index=True,
        )

    edited = st.data_editor(
        st.session_state.po_lines,
        num_rows="dynamic",
        use_container_width=True,
        key="po_editor",
    )

    edited["Units"] = pd.to_numeric(edited["Units"], errors="coerce").fillna(0)
    edited["Unit Cost"] = pd.to_numeric(edited["Unit Cost"], errors="coerce").fillna(0.0)
    edited["Line Total"] = edited["Units"] * edited["Unit Cost"]
    st.session_state.po_lines = edited

    subtotal = edited["Line Total"].sum()
    st.markdown(f"**Subtotal:** ${subtotal:,.2f}")

    if st.button("Download PO (TXT)"):
        buffer = io.StringIO()
        buffer.write("Rebelle Cannabis – Purchase Order\n")
        buffer.write("=" * 60 + "\n\n")
        buffer.write(f"PO Number: {po_number}\n")
        buffer.write(f"PO Date:   {po_date}\n")
        buffer.write(f"Vendor:    {vendor_name}\n")
        buffer.write(f"Buyer:     {buyer_name}\n")
        buffer.write(f"Terms:     {terms}\n\n")
        buffer.write("Line Items:\n")
        buffer.write("-" * 60 + "\n")
        for _, row in edited.iterrows():
            buffer.write(
                f"{row['SKU']} | {row['Description']} | "
                f"{row['Units']} @ ${row['Unit Cost']:.2f} "
                f"= ${row['Line Total']:.2f}\n"
            )
        buffer.write("\n")
        buffer.write(f"Subtotal: ${subtotal:,.2f}\n")
        txt_bytes = buffer.getvalue().encode("utf-8")
        st.download_button(
            "Save PO File",
            data=txt_bytes,
            file_name=f"PO_{po_number or 'rebelle'}.txt",
            mime="text/plain",
        )

# ============================================================================
# VENDOR TRACKER
# ============================================================================

elif st.session_state.app_section == "Vendor Tracker":
    st.markdown("## 🤝 Vendor Tracking")
    st.caption(
        "Acts as a live vendor CRM: track brands, spotlight SKUs, contacts, terms, and buyer notes."
    )

    st.markdown("##### Vendor Table")

    vendor_df = st.session_state.vendor_df.copy()

    edited_vendor_df = st.data_editor(
        vendor_df,
        num_rows="dynamic",
        use_container_width=True,
        key="vendor_editor",
        hide_index=True,
    )

    st.session_state.vendor_df = edited_vendor_df

    if GOOGLE_SHEETS_ENABLED and VENDOR_SHEET_ID:
        try:
            sh = gc.open_by_key(VENDOR_SHEET_ID)
            try:
                ws = sh.worksheet("Vendors")
            except gspread.WorksheetNotFound:
                ws = sh.add_worksheet(title="Vendors", rows=1000, cols=10)

            ws.clear()
            if not edited_vendor_df.empty:
                ws.update(
                    "A1",
                    [list(edited_vendor_df.columns)]
                    + edited_vendor_df.astype(str).values.tolist(),
                )
            st.success("Vendor table autosaved to Google Sheets.", icon="✅")
        except Exception as e:
            st.warning(f"Autosave failed – check Sheets permissions: {e}")
    else:
        st.info(
            "Autosave is in-memory only. Configure Google Sheets credentials to persist across sessions."
        )

    csv_vendor = edited_vendor_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Vendor Table (CSV)",
        csv_vendor,
        file_name="rebelle_vendor_tracker.csv",
        mime="text/csv",
    )

# ============================================================================
# FOOTER
# ============================================================================

st.markdown(
    "<div style='text-align:center; margin-top:2rem; font-size:0.8rem; opacity:0.75;'>"
    "Licensed exclusively to Rebelle Cannabis • Powered by MAVet710 Analytics © 2025"
    "</div>",
    unsafe_allow_html=True,
)

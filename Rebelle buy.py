import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
from io import BytesIO

# PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

# Optional Plotly
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
APP_TAGLINE = "Streamlined purchasing visibility powered by Dutchie / BLAZE data."
LICENSE_FOOTER = f"Licensed exclusively to {CLIENT_NAME} • Powered by MAVet710 Analytics"

# Trial + Admin
TRIAL_KEY = "rebelle24"
TRIAL_DURATION_HOURS = 24
ADMIN_USERNAME = "God"
ADMIN_PASSWORD = "Major420"

REB_CATEGORIES = [
    "flower",
    "pre rolls",
    "vapes",
    "edibles",
    "beverages",
    "concentrates",
    "tinctures",
    "topicals",
]

page_icon_url = (
    "https://raw.githubusercontent.com/MAVet710/Rebelle-Purchasing-Dash/"
    "ef50d34e20caf45231642e957137d6141082dbb9/rebelle.jpg"
)

st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    page_icon=page_icon_url,
)

background_url = (
    "https://raw.githubusercontent.com/MAVet710/Rebelle-Purchasing-Dash/"
    "ef50d34e20caf45231642e957137d6141082dbb9/rebelle%20main.png"
)

# =========================
# THEME TOGGLE (LIGHT / DARK)
# =========================
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "Dark"

with st.sidebar:
    st.markdown("### 🎨 Theme")
    theme_choice = st.radio("Mode", ["Dark", "Light"], index=0 if st.session_state.theme_mode == "Dark" else 1)
    st.session_state.theme_mode = theme_choice

if st.session_state.theme_mode == "Dark":
    main_overlay = "rgba(0, 0, 0, 0.85)"
    main_text_color = "#ffffff"
    table_text_color = "#ffffff"
    sidebar_bg = "#111417"
    sidebar_text = "#f5f5f5"
    sidebar_input_bg = "#1f2430"
    sidebar_input_border = "#444444"
else:
    main_overlay = "rgba(255, 255, 255, 0.94)"
    main_text_color = "#111111"
    table_text_color = "#111111"
    sidebar_bg = "#f5f5f5"
    sidebar_text = "#111111"
    sidebar_input_bg = "#ffffff"
    sidebar_input_border = "#888888"

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
    }}

    .block-container {{
        background-color: {main_overlay};
        padding: 2rem;
        border-radius: 12px;
        color: {main_text_color} !important;
    }}

    .block-container *:not(input):not(textarea):not(select) {{
        color: {main_text_color} !important;
    }}

    .dataframe td {{
        color: {table_text_color} !important;
    }}

    .stButton>button {{
        background-color: rgba(255, 255, 255, 0.08);
        color: {main_text_color};
        border: 1px solid rgba(255, 255, 255, 0.8);
        border-radius: 6px;
    }}
    .stButton>button:hover {{
        background-color: rgba(255, 255, 255, 0.25);
    }}

    .footer {{
        text-align: center;
        font-size: 0.75rem;
        opacity: 0.7;
        margin-top: 2rem;
        color: {main_text_color} !important;
    }}

    /* Sidebar styling */
    [data-testid="stSidebar"] {{
        background-color: {sidebar_bg} !important;
    }}
    [data-testid="stSidebar"] * {{
        color: {sidebar_text} !important;
    }}
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] select,
    [data-testid="stSidebar"] .stTextInput input,
    [data-testid="stSidebar"] .stNumberInput input {{
        background-color: {sidebar_input_bg} !important;
        color: {sidebar_text} !important;
        border-color: {sidebar_input_border} !important;
    }}
    [data-testid="stSidebar"] .stRadio > label,
    [data-testid="stSidebar"] label {{
        color: {sidebar_text} !important;
        font-weight: 500;
    }}

    /* PO-only labels in main content */
    .po-label {{
        color: {main_text_color} !important;
        font-weight: 600;
        font-size: 0.9rem;
        margin-bottom: 0.1rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# SESSION DEFAULTS
# =========================
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "trial_start" not in st.session_state:
    st.session_state.trial_start = None
if "metric_filter" not in st.session_state:
    st.session_state.metric_filter = "All"
if "inv_raw_df" not in st.session_state:
    st.session_state.inv_raw_df = None
if "sales_raw_df" not in st.session_state:
    st.session_state.sales_raw_df = None

# =========================
# HELPERS
# =========================
def normalize_col(col: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(col).lower())

def detect_column(columns, aliases):
    norm_map = {normalize_col(c): c for c in columns}
    for alias in aliases:
        if alias in norm_map:
            return norm_map[alias]
    return None

def normalize_rebelle_category(raw):
    s = str(raw).lower().strip()
    if any(k in s for k in ["flower", "bud", "buds", "cannabis flower"]):
        return "flower"
    if any(k in s for k in ["pre roll", "preroll", "pre-roll", "joint", "joints"]):
        return "pre rolls"
    if any(k in s for k in ["vape", "cart", "cartridge", "pen", "pod"]):
        return "vapes"
    if any(k in s for k in ["edible", "gummy", "chocolate", "chew", "cookies"]):
        return "edibles"
    if any(k in s for k in ["beverage", "drink", "shot", "drinkable"]):
        return "beverages"
    if any(k in s for k in ["concentrate", "wax", "shatter", "crumble", "resin", "rosin", "dab"]):
        return "concentrates"
    if any(k in s for k in ["tincture", "drops", "sublingual", "dropper"]):
        return "tinctures"
    if any(k in s for k in ["topical", "lotion", "cream", "salve", "balm"]):
        return "topicals"
    return s

def extract_strain_type(name, subcat):
    s = str(name).lower()
    base = "unspecified"
    if "indica" in s:
        base = "indica"
    elif "sativa" in s:
        base = "sativa"
    elif "hybrid" in s:
        base = "hybrid"
    elif "cbd" in s:
        base = "cbd"

    vape = any(k in s for k in ["vape", "cart", "cartridge", "pen", "pod"])
    preroll = any(k in s for k in ["pre roll", "preroll", "pre-roll", "joint"])

    if ("disposable" in s or "dispos" in s) and vape:
        return base + " disposable" if base != "unspecified" else "disposable"
    if "infused" in s and preroll:
        return base + " infused" if base != "unspecified" else "infused"
    return base

def extract_size(text, context=None):
    s = str(text).lower()

    mg = re.search(r"(\d+(\.\d+)?\s?mg)", s)
    if mg:
        return mg.group(1).replace(" ", "")

    g = re.search(r"((?:\d+\.?\d*|\.\d+)\s?(g|oz))", s)
    if g:
        val = g.group(1).replace(" ", "")
        val_lower = val.lower()
        if val_lower in ["1oz", "1.0oz", "28g", "28.0g"]:
            return "28g"
        return val_lower

    if any(k in s for k in ["vape", "cart", "cartridge", "pen", "pod"]):
        half = re.search(r"\b0\.5\b|\b\.5\b", s)
        if half:
            return "0.5g"

    return "unspecified"

# ---- Smarter sales Excel header detection ----
def read_sales_excel_with_header_detection(uploaded_file):
    """
    Handle Dutchie / BLAZE Excel exports that sometimes have
    3–5 non-data rows above the real header.
    """
    raw = pd.read_excel(uploaded_file, header=None)

    header_row_idx = None

    qty_keywords = [
        "quantity", "qty", "units", "items", "items sold", "item sold",
        "qty sold", "quantity sold", "unit sold", "units sold"
    ]
    cat_keywords = [
        "category", "category name", "product category",
        "productcategory", "master category", "mastercategory",
        "product type", "type"
    ]
    prod_keywords = [
        "product", "product name", "product sku", "sku",
        "item", "item name", "producttitle", "product id"
    ]
    sales_keywords = ["sales", "total sales", "gross sales", "net sales"]

    max_scan = min(15, len(raw))

    for i in range(max_scan):
        row_vals = [str(v).lower() for v in raw.iloc[i].tolist()]
        has_prod = any(any(k in v for k in prod_keywords) for v in row_vals)
        has_cat = any(any(k in v for k in cat_keywords) for v in row_vals)
        has_qty = any(any(k in v for k in qty_keywords) for v in row_vals)
        has_sales = any(any(k in v for k in sales_keywords) for v in row_vals)

        # Accept if row clearly looks like a product-level header
        if has_prod and (has_cat or has_qty or has_sales):
            header_row_idx = i
            break

    if header_row_idx is None:
        header_row_idx = 0

    header = raw.iloc[header_row_idx].astype(str).str.strip()
    df = raw.iloc[header_row_idx + 1 :].copy()
    df.columns = header
    df = df.reset_index(drop=True)
    return df

# =========================
# PDF GENERATION FOR PO
# =========================
def generate_po_pdf(
    store_name,
    store_number,
    store_address,
    store_phone,
    store_contact,
    vendor_name,
    vendor_license,
    vendor_address,
    vendor_contact,
    po_number,
    po_date,
    terms,
    notes,
    po_df,
    subtotal,
    discount,
    tax_amount,
    shipping,
    total,
):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    left_margin = 0.7 * inch
    right_margin = width - 0.7 * inch
    top_margin = height - 0.75 * inch

    y = top_margin
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left_margin, y, f"{CLIENT_NAME} - Purchase Order")
    y -= 0.25 * inch

    c.setFont("Helvetica", 10)
    c.drawString(left_margin, y, f"PO Number: {po_number}")
    c.drawRightString(right_margin, y, f"Date: {po_date.strftime('%m/%d/%Y')}")
    y -= 0.35 * inch

    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_margin, y, "Ship To:")
    c.setFont("Helvetica", 10)
    y -= 0.18 * inch
    c.drawString(left_margin, y, store_name or "")
    y -= 0.16 * inch
    if store_number:
        c.drawString(left_margin, y, f"Store #: {store_number}")
        y -= 0.16 * inch
    if store_address:
        c.drawString(left_margin, y, store_address)
        y -= 0.16 * inch
    if store_phone:
        c.drawString(left_margin, y, f"Phone: {store_phone}")
        y -= 0.16 * inch
    if store_contact:
        c.drawString(left_margin, y, f"Buyer: {store_contact}")
        y -= 0.2 * inch

    vend_y = top_margin - 0.35 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(width / 2, vend_y, "Vendor:")
    vend_y -= 0.18 * inch
    c.setFont("Helvetica", 10)
    if vendor_name:
        c.drawString(width / 2, vend_y, vendor_name)
        vend_y -= 0.16 * inch
    if vendor_license:
        c.drawString(width / 2, vend_y, f"License #: {vendor_license}")
        vend_y -= 0.16 * inch
    if vendor_address:
        c.drawString(width / 2, vend_y, vendor_address)
        vend_y -= 0.16 * inch
    if vendor_contact:
        c.drawString(width / 2, vend_y, f"Contact: {vendor_contact}")
        vend_y -= 0.2 * inch

    y = min(y, vend_y) - 0.15 * inch
    if terms:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(left_margin, y, "Payment Terms:")
        c.setFont("Helvetica", 10)
        c.drawString(left_margin + 90, y, terms)
        y -= 0.25 * inch

    if notes:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(left_margin, y, "Notes:")
        y -= 0.16 * inch
        c.setFont("Helvetica", 9)
        text_obj = c.beginText()
        text_obj.setTextOrigin(left_margin, y)
        text_obj.setLeading(12)
        for line in notes.splitlines():
            text_obj.textLine(line)
        c.drawText(text_obj)
        y = text_obj.getY() - 0.25 * inch

    c.setFont("Helvetica-Bold", 10)
    header_y = y
    if header_y < 2.5 * inch:
        c.showPage()
        width, height = letter
        left_margin = 0.7 * inch
        right_margin = width - 0.7 * inch
        header_y = height - 1 * inch
        c.setFont("Helvetica-Bold", 16)
        c.drawString(left_margin, header_y, f"{CLIENT_NAME} - Purchase Order")
        header_y -= 0.4 * inch
        c.setFont("Helvetica-Bold", 10)

    y = header_y
    col_x = {
        "line": left_margin,
        "sku": left_margin + 0.4 * inch,
        "desc": left_margin + 1.4 * inch,
        "strain": left_margin + 3.8 * inch,
        "size": left_margin + 4.6 * inch,
        "qty": left_margin + 5.2 * inch,
        "unit": left_margin + 6.0 * inch,
        "total": left_margin + 7.0 * inch,
    }

    c.drawString(col_x["line"], y, "Ln")
    c.drawString(col_x["sku"], y, "SKU")
    c.drawString(col_x["desc"], y, "Description")
    c.drawString(col_x["strain"], y, "Strain")
    c.drawString(col_x["size"], y, "Size")
    c.drawRightString(col_x["qty"] + 0.3 * inch, y, "Qty")
    c.drawRightString(col_x["unit"] + 0.7 * inch, y, "Unit Price")
    c.drawRightString(col_x["total"] + 0.8 * inch, y, "Line Total")
    y -= 0.2 * inch

    c.setLineWidth(0.5)
    c.line(left_margin, y, right_margin, y)
    y -= 0.18 * inch
    c.setFont("Helvetica", 9)

    for idx, row in po_df.reset_index(drop=True).iterrows():
        if y < 1.2 * inch:
            c.showPage()
            width, height = letter
            left_margin = 0.7 * inch
            right_margin = width - 0.7 * inch
            y = height - 1 * inch
            c.setFont("Helvetica-Bold", 10)
            c.drawString(left_margin, y, "SKU Line Items (cont.)")
            y -= 0.25 * inch
            c.drawString(col_x["line"], y, "Ln")
            c.drawString(col_x["sku"], y, "SKU")
            c.drawString(col_x["desc"], y, "Description")
            c.drawString(col_x["strain"], y, "Strain")
            c.drawString(col_x["size"], y, "Size")
            c.drawRightString(col_x["qty"] + 0.3 * inch, y, "Qty")
            c.drawRightString(col_x["unit"] + 0.7 * inch, y, "Unit Price")
            c.drawRightString(col_x["total"] + 0.8 * inch, y, "Line Total")
            y -= 0.2 * inch
            c.line(left_margin, y, right_margin, y)
            y -= 0.18 * inch
            c.setFont("Helvetica", 9)

        line_no = idx + 1
        c.drawString(col_x["line"], y, str(line_no))
        c.drawString(col_x["sku"], y, str(row.get("SKU", ""))[:10])
        c.drawString(col_x["desc"], y, str(row.get("Description", ""))[:30])
        c.drawString(col_x["strain"], y, str(row.get("Strain", ""))[:10])
        c.drawString(col_x["size"], y, str(row.get("Size", ""))[:8])
        c.drawRightString(col_x["qty"] + 0.3 * inch, y, f"{int(row.get('Qty', 0))}")
        c.drawRightString(col_x["unit"] + 0.7 * inch, y, f"${row.get('Unit Price', 0):,.2f}")
        c.drawRightString(col_x["total"] + 0.8 * inch, y, f"${row.get('Line Total', 0):,.2f}")
        y -= 0.18 * inch

    if y < 1.8 * inch:
        c.showPage()
        width, height = letter
        left_margin = 0.7 * inch
        right_margin = width - 0.7 * inch
        y = height - 1.5 * inch

    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(col_x["total"] + 0.8 * inch, y, f"Subtotal: ${subtotal:,.2f}")
    y -= 0.2 * inch
    if discount > 0:
        c.drawRightString(col_x["total"] + 0.8 * inch, y, f"Discount: -${discount:,.2f}")
        y -= 0.2 * inch
    if tax_amount > 0:
        c.drawRightString(col_x["total"] + 0.8 * inch, y, f"Tax: ${tax_amount:,.2f}")
        y -= 0.2 * inch
    if shipping > 0:
        c.drawRightString(col_x["total"] + 0.8 * inch, y, f"Shipping / Fees: ${shipping:,.2f}")
        y -= 0.2 * inch

    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(col_x["total"] + 0.8 * inch, y, f"TOTAL: ${total:,.2f}")

    c.showPage()
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# =========================
# ADMIN + TRIAL GATE
# =========================
st.sidebar.markdown("### 👑 Admin Login")

if not st.session_state.is_admin:
    admin_user = st.sidebar.text_input("Username", key="admin_user")
    admin_pass = st.sidebar.text_input("Password", type="password", key="admin_pass")
    if st.sidebar.button("Login as Admin"):
        if admin_user == ADMIN_USERNAME and admin_pass == ADMIN_PASSWORD:
            st.session_state.is_admin = True
            st.sidebar.success("✅ Admin mode enabled.")
        else:
            st.sidebar.error("❌ Invalid admin credentials.")
else:
    st.sidebar.success("👑 Admin mode: unlimited access")
    if st.sidebar.button("Logout Admin"):
        st.session_state.is_admin = False
        st.experimental_rerun()

trial_now = datetime.now()

if not st.session_state.is_admin:
    st.sidebar.markdown("### 🔐 Trial Access")
    if st.session_state.trial_start is None:
        trial_key_input = st.sidebar.text_input(
            "Enter trial key", type="password", key="trial_key_input"
        )
        if st.sidebar.button("Activate Trial", key="activate_trial"):
            if trial_key_input.strip() == TRIAL_KEY:
                st.session_state.trial_start = trial_now.isoformat()
                st.sidebar.success("✅ Trial activated. You have 24 hours of access.")
            else:
                st.sidebar.error("❌ Invalid trial key.")
        st.warning("This is a trial build. Enter a valid key to unlock the app.")
        st.stop()
    else:
        try:
            started_at = datetime.fromisoformat(st.session_state.trial_start)
        except Exception:
            st.session_state.trial_start = None
            st.experimental_rerun()

        elapsed = trial_now - started_at
        remaining = timedelta(hours=TRIAL_DURATION_HOURS) - elapsed

        if remaining.total_seconds() <= 0:
            st.sidebar.error("⛔ Trial expired. Please contact the vendor for full access.")
            st.error("The 24-hour trial has expired. Contact the vendor to purchase a full license.")
            st.stop()
        else:
            hours_left = int(remaining.total_seconds() // 3600)
            mins_left = int((remaining.total_seconds() % 3600) // 60)
            st.sidebar.info(f"⏰ Trial time remaining: {hours_left}h {mins_left}m")

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
        "If using Streamlit Cloud, add `plotly` and `reportlab` to your `requirements.txt` file."
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

    st.sidebar.markdown("### 🧩 Data Source")
    data_source = st.sidebar.selectbox(
        "Select POS / Data Source",
        ["Dutchie", "BLAZE"],
        index=0,
        help="Changes how column names are interpreted. Files are still CSV/XLSX exports.",
    )

    st.sidebar.header("📂 Upload Core Reports")
    inv_file = st.sidebar.file_uploader("Inventory CSV", type=["csv"])

    product_sales_file = st.sidebar.file_uploader(
        "Product Sales Report (POS export)",
        type=["xlsx", "csv"],
        help="Dutchie 'Product Sales' or Blaze sales export.",
    )

    sales_by_product_file = st.sidebar.file_uploader(
        "Sales by Product / Total Sales by Product (optional)",
        type=["xlsx", "csv"],
        help="Dutchie 'Total Sales by Product' or Blaze 'Sales by Product'. Improves accuracy when present.",
    )

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Forecast Settings")
    doh_threshold = st.sidebar.number_input("Target Days on Hand", 1, 60, 21)
    velocity_adjustment = st.sidebar.number_input("Velocity Adjustment", 0.01, 5.0, 0.5)
    date_diff = st.sidebar.slider("Days in Sales Period", 7, 90, 60)

    # Cache inventory
    if inv_file is not None:
        inv_df_raw = pd.read_csv(inv_file)
        st.session_state.inv_raw_df = inv_df_raw

    # Decide which sales file to use (optional one overrides)
    sales_source_file = None
    if sales_by_product_file is not None:
        sales_source_file = sales_by_product_file
    elif product_sales_file is not None:
        sales_source_file = product_sales_file

    if sales_source_file is not None:
        fname = sales_source_file.name.lower()
        if fname.endswith(".csv"):
            sales_raw_raw = pd.read_csv(sales_source_file)
        else:
            sales_raw_raw = read_sales_excel_with_header_detection(sales_source_file)
        st.session_state.sales_raw_df = sales_raw_raw

    if st.session_state.inv_raw_df is not None and st.session_state.sales_raw_df is not None:
        try:
            inv_df = st.session_state.inv_raw_df.copy()
            sales_raw = st.session_state.sales_raw_df.copy()

            # ---------------- INVENTORY ----------------
            inv_df.columns = inv_df.columns.str.strip().str.lower()

            if data_source == "BLAZE":
                inv_name_aliases = [
                    "product", "productname", "item", "itemname", "name",
                    "sku", "skuname", "product sku"
                ]
                inv_cat_aliases = [
                    "category", "productcategory", "product category",
                    "subcategory", "department"
                ]
                inv_qty_aliases = [
                    "currentquantity", "current quantity", "onhand", "onhandunits",
                    "quantity", "qty", "quantityonhand", "instock"
                ]
            else:  # Dutchie
                inv_name_aliases = [
                    "product", "productname", "name", "itemname", "sku name", "sku"
                ]
                inv_cat_aliases = [
                    "category", "productcategory", "mastercategory", "subcategory"
                ]
                inv_qty_aliases = [
                    "available", "onhand", "onhandunits", "inventory", "quantity",
                    "qty", "instock"
                ]

            name_col = detect_column(inv_df.columns, [normalize_col(a) for a in inv_name_aliases])
            cat_col = detect_column(inv_df.columns, [normalize_col(a) for a in inv_cat_aliases])
            qty_col = detect_column(inv_df.columns, [normalize_col(a) for a in inv_qty_aliases])

            if not (name_col and cat_col and qty_col):
                st.error(
                    "Could not auto-detect inventory columns (product / category / on-hand).\n\n"
                    "Check your Inventory export headers."
                )
                st.stop()

            inv_df = inv_df.rename(
                columns={
                    name_col: "itemname",
                    cat_col: "subcategory",
                    qty_col: "onhandunits",
                }
            )

            inv_df["onhandunits"] = pd.to_numeric(inv_df["onhandunits"], errors="coerce").fillna(0)
            inv_df["subcategory"] = inv_df["subcategory"].apply(normalize_rebelle_category)

            inv_df["strain_type"] = inv_df.apply(
                lambda x: extract_strain_type(x["itemname"], x["subcategory"]), axis=1
            )
            inv_df["packagesize"] = inv_df.apply(
                lambda x: extract_size(x["itemname"], x["subcategory"]), axis=1
            )

            inv_summary = (
                inv_df.groupby(["subcategory", "strain_type", "packagesize"])["onhandunits"]
                .sum()
                .reset_index()
            )

            # ---------------- SALES ----------------
            sales_raw.columns = sales_raw.columns.astype(str).str.lower()

            sales_name_aliases = [
                "product", "productname", "product name", "item", "itemname",
                "sku", "skuname", "sku name", "product sku", "description"
            ]
            name_col_sales = detect_column(
                sales_raw.columns, [normalize_col(a) for a in sales_name_aliases]
            )

            qty_aliases = [
                "quantitysold", "qtysold", "unitssold", "unitsold",
                "units", "totalunits", "quantity", "quantity sold",
                "itemssold", "items sold", "items_sold", "item_sold",
                # last resort: revenue-style columns if no true qty present
                "sales", "totalsales", "grosssales", "netsales"
            ]
            qty_col_sales = detect_column(
                sales_raw.columns, [normalize_col(a) for a in qty_aliases]
            )

            mc_aliases = [
                "mastercategory", "category", "master category",
                "productcategory", "product category", "category name"
            ]
            mc_col = detect_column(sales_raw.columns, [normalize_col(a) for a in mc_aliases])

            if not (name_col_sales and qty_col_sales and mc_col):
                st.error(
                    "Product Sales file detected but could not find required columns.\n\n"
                    "Looked for some variant of: product / product name, quantity or items sold, "
                    "and category or product category.\n\n"
                    "Tip: Use Dutchie 'Total Sales by Product' or Blaze 'Sales by Product' "
                    "exports without manually editing the headers."
                )
                st.stop()

            sales_raw = sales_raw.rename(
                columns={
                    name_col_sales: "product_name",
                    qty_col_sales: "unitssold",
                    mc_col: "mastercategory",
                }
            )

            sales_raw["unitssold"] = pd.to_numeric(
                sales_raw["unitssold"], errors="coerce"
            ).fillna(0)

            sales_raw["mastercategory"] = sales_raw["mastercategory"].apply(normalize_rebelle_category)

            sales_df = sales_raw[
                ~sales_raw["mastercategory"].astype(str).str.contains("accessor")
                & (sales_raw["mastercategory"] != "all")
            ].copy()

            sales_df["packagesize"] = sales_df.apply(
                lambda row: extract_size(row["product_name"], row["mastercategory"]),
                axis=1,
            )

            sales_summary = (
                sales_df.groupby(["mastercategory", "packagesize"])["unitssold"]
                .sum()
                .reset_index()
            )
            sales_summary["avgunitsperday"] = (
                sales_summary["unitssold"] / date_diff
            ) * velocity_adjustment

            detail = pd.merge(
                inv_summary,
                sales_summary,
                how="left",
                left_on=["subcategory", "packagesize"],
                right_on=["mastercategory", "packagesize"],
            ).fillna(0)

            # Ensure 28g flower rows exist
            flower_mask = detail["subcategory"].str.contains("flower", na=False)
            flower_cats = detail.loc[flower_mask, "subcategory"].unique()
            missing_rows = []
            for cat in flower_cats:
                if not ((detail["subcategory"] == cat) & (detail["packagesize"] == "28g")).any():
                    missing_rows.append(
                        {
                            "subcategory": cat,
                            "strain_type": "unspecified",
                            "packagesize": "28g",
                            "onhandunits": 0,
                            "mastercategory": cat,
                            "unitssold": 0,
                            "avgunitsperday": 0,
                        }
                    )
            if missing_rows:
                detail = pd.concat([detail, pd.DataFrame(missing_rows)], ignore_index=True)

            detail["daysonhand"] = np.where(
                detail["avgunitsperday"] > 0,
                detail["onhandunits"] / detail["avgunitsperday"],
                0,
            )
            detail["daysonhand"] = (
                detail["daysonhand"]
                .replace([np.inf, -np.inf], 0)
                .fillna(0)
                .astype(int)
            )

            detail["reorderqty"] = np.where(
                detail["daysonhand"] < doh_threshold,
                np.ceil((doh_threshold - detail["daysonhand"]) * detail["avgunitsperday"]),
                0,
            ).astype(int)

            def tag(row):
                if row["daysonhand"] <= 7:
                    return "1 – Reorder ASAP"
                if row["daysonhand"] <= 21:
                    return "2 – Watch Closely"
                if row["avgunitsperday"] == 0:
                    return "4 – Dead Item"
                return "3 – Comfortable Cover"

            detail["reorderpriority"] = detail.apply(tag, axis=1)

            # SUMMARY + CLICK FILTERS
            st.markdown("### Inventory Summary")

            total_units = int(detail["unitssold"].sum())
            reorder_asap = (detail["reorderpriority"] == "1 – Reorder ASAP").sum()

            col1, col2 = st.columns(2)
            with col1:
                if st.button(
                    f"Units Sold (Granular Size-Level): {total_units}",
                    key="btn_total_units",
                ):
                    st.session_state.metric_filter = "All"
            with col2:
                if st.button(
                    f"Reorder ASAP (Lines): {reorder_asap}",
                    key="btn_reorder_asap",
                ):
                    st.session_state.metric_filter = "Reorder ASAP"

            if st.session_state.metric_filter == "Reorder ASAP":
                detail_view = detail[detail["reorderpriority"] == "1 – Reorder ASAP"].copy()
            else:
                detail_view = detail.copy()

            st.markdown(f"*Current filter:* **{st.session_state.metric_filter}**")

            st.markdown("### Forecast Table")

            def red_low(val):
                try:
                    v = int(val)
                    return "color:#FF3131" if v < doh_threshold else ""
                except Exception:
                    return ""

            all_cats = sorted(detail_view["subcategory"].unique())

            def cat_sort_key(c):
                c_low = str(c).lower()
                if c_low in REB_CATEGORIES:
                    return (REB_CATEGORIES.index(c_low), c_low)
                return (len(REB_CATEGORIES), c_low)

            all_cats_sorted = sorted(all_cats, key=cat_sort_key)

            selected_cats = st.sidebar.multiselect(
                "Visible Categories",
                all_cats_sorted,
                default=all_cats_sorted,
            )
            detail_view = detail_view[detail_view["subcategory"].isin(selected_cats)]

            display_cols = [
                "mastercategory",
                "subcategory",
                "strain_type",
                "packagesize",
                "onhandunits",
                "unitssold",
                "avgunitsperday",
                "daysonhand",
                "reorderqty",
                "reorderpriority",
            ]
            display_cols = [c for c in display_cols if c in detail_view.columns]

            for cat in sorted(detail_view["subcategory"].unique(), key=cat_sort_key):
                group = detail_view[detail_view["subcategory"] == cat]
                with st.expander(cat.title()):
                    g = group[display_cols].copy()
                    st.dataframe(
                        g.style.applymap(red_low, subset=["daysonhand"]),
                        use_container_width=True,
                    )

        except Exception as e:
            st.error(f"Error: {e}")

    else:
        st.info("Upload inventory + at least one sales file to continue.")

# ============================================================
# PAGE 2 – PO BUILDER
# ============================================================
else:
    st.subheader("🧾 Purchase Order Builder")
    st.markdown("The labels above each PO field are white on the dark background for clarity.")

    st.markdown("### PO Header")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="po-label">Store / Ship-To Name</div>', unsafe_allow_html=True)
        store_name = st.text_input("", value="Rebelle Cannabis", key="store_name")

        st.markdown('<div class="po-label">Store #</div>', unsafe_allow_html=True)
        store_number = st.text_input("", key="store_number")

        st.markdown('<div class="po-label">Store Address</div>', unsafe_allow_html=True)
        store_address = st.text_input("", key="store_address")

        st.markdown('<div class="po-label">Store Phone</div>', unsafe_allow_html=True)
        store_phone = st.text_input("", key="store_phone")

        st.markdown('<div class="po-label">Buyer / Contact Name</div>', unsafe_allow_html=True)
        store_contact = st.text_input("", key="store_contact")

    with col2:
        st.markdown('<div class="po-label">Vendor Name</div>', unsafe_allow_html=True)
        vendor_name = st.text_input("", key="vendor_name")

        st.markdown('<div class="po-label">Vendor License Number</div>', unsafe_allow_html=True)
        vendor_license = st.text_input("", key="vendor_license")

        st.markdown('<div class="po-label">Vendor Address</div>', unsafe_allow_html=True)
        vendor_address = st.text_input("", key="vendor_address")

        st.markdown('<div class="po-label">Vendor Contact / Email</div>', unsafe_allow_html=True)
        vendor_contact = st.text_input("", key="vendor_contact")

        st.markdown('<div class="po-label">PO Number</div>', unsafe_allow_html=True)
        po_number = st.text_input("", key="po_number")

        st.markdown('<div class="po-label">PO Date</div>', unsafe_allow_html=True)
        po_date = st.date_input("", datetime.today(), key="po_date")

        st.markdown('<div class="po-label">Payment Terms</div>', unsafe_allow_html=True)
        terms = st.text_input("", value="Net 30", key="terms")

    st.markdown('<div class="po-label">PO Notes / Special Instructions</div>', unsafe_allow_html=True)
    notes = st.text_area("", "", height=70, key="notes")

    st.markdown("---")
    st.markdown("### Line Items")

    num_lines = st.number_input("Number of Line Items", 1, 50, 5)
    items = []

    for i in range(int(num_lines)):
        with st.expander(f"Line {i + 1}", expanded=(i < 3)):
            c1, c2, c3, c4, c5, c6 = st.columns([1.2, 2.5, 1.4, 1.2, 1.2, 1.3])

            with c1:
                st.markdown('<div class="po-label">SKU ID</div>', unsafe_allow_html=True)
                sku = st.text_input("", key=f"sku_{i}")

            with c2:
                st.markdown('<div class="po-label">SKU Name / Description</div>', unsafe_allow_html=True)
                desc = st.text_input("", key=f"desc_{i}")

            with c3:
                st.markdown('<div class="po-label">Strain / Type</div>', unsafe_allow_html=True)
                strain = st.text_input("", key=f"strain_{i}")

            with c4:
                st.markdown('<div class="po-label">Size (e.g. 3.5g)</div>', unsafe_allow_html=True)
                size = st.text_input("", key=f"size_{i}")

            with c5:
                st.markdown('<div class="po-label">Qty</div>', unsafe_allow_html=True)
                qty = st.number_input("", min_value=0, step=1, key=f"qty_{i}")

            with c6:
                st.markdown('<div class="po-label">Unit Price ($)</div>', unsafe_allow_html=True)
                price = st.number_input("", min_value=0.0, step=0.01, key=f"price_{i}")

            line_total = qty * price
            st.markdown(f"**Line Total:** ${line_total:,.2f}")

            items.append(
                {
                    "SKU": sku,
                    "Description": desc,
                    "Strain": strain,
                    "Size": size,
                    "Qty": qty,
                    "Unit Price": price,
                    "Line Total": line_total,
                }
            )

    po_df = pd.DataFrame(items)
    po_df = po_df[
        (po_df["SKU"].astype(str).str.strip() != "")
        | (po_df["Description"].astype(str).str.strip() != "")
        | (po_df["Qty"] > 0)
    ]

    st.markdown("---")

    if not po_df.empty:
        subtotal = float(po_df["Line Total"].sum())

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown('<div class="po-label">Tax Rate (%)</div>', unsafe_allow_html=True)
            tax_rate = st.number_input("", 0.0, 30.0, 0.0, key="tax_rate")
        with c2:
            st.markdown('<div class="po-label">Discount ($)</div>', unsafe_allow_html=True)
            discount = st.number_input("", 0.0, step=0.01, key="discount")
        with c3:
            st.markdown('<div class="po-label">Shipping / Fees ($)</div>', unsafe_allow_html=True)
            shipping = st.number_input("", 0.0, step=0.01, key="shipping")

        tax_amount = subtotal * (tax_rate / 100.0)
        total = subtotal + tax_amount + shipping - discount

        st.markdown("### Totals")
        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("SUBTOTAL", f"${subtotal:,.2f}")
        s2.metric("DISCOUNT", f"-${discount:,.2f}")
        s3.metric("TAX", f"${tax_amount:,.2f}")
        s4.metric("SHIPPING", f"${shipping:,.2f}")
        s5.metric("TOTAL", f"${total:,.2f}")

        st.markdown("### PO Review")
        st.dataframe(po_df, use_container_width=True)

        pdf_bytes = generate_po_pdf(
            store_name,
            store_number,
            store_address,
            store_phone,
            store_contact,
            vendor_name,
            vendor_license,
            vendor_address,
            vendor_contact,
            po_number,
            po_date,
            terms,
            notes,
            po_df,
            subtotal,
            discount,
            tax_amount,
            shipping,
            total,
        )

        st.markdown("### Download")
        st.download_button(
            "📥 Download PO (PDF)",
            data=pdf_bytes,
            file_name=f"PO_{po_number or 'rebelle'}.pdf",
            mime="application/pdf",
        )
    else:
        st.info("Add at least one line item to generate totals and PDF.")

# =========================
# FOOTER
# =========================
st.markdown("---")
year = datetime.now().year
st.markdown(
    f'<div class="footer">{LICENSE_FOOTER} • © {year}</div>',
    unsafe_allow_html=True,
)

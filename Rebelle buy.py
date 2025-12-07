import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
from io import BytesIO

# For PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

# ------------------------------------------------------------
# OPTIONAL / SAFE IMPORT FOR PLOTLY
# ------------------------------------------------------------
try:
    import plotly.express as px  # noqa: F401
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

# 🔐 TRIAL SETTINGS
TRIAL_KEY = "rebelle24"        # Rebelle 24-hour trial key
TRIAL_DURATION_HOURS = 24

# 👑 ADMIN CREDS
ADMIN_USERNAME = "God"
ADMIN_PASSWORD = "Major420"

# ✅ Canonical Rebelle category names (values, not column names)
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
# SESSION STATE DEFAULTS
# =========================
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "trial_start" not in st.session_state:
    st.session_state.trial_start = None
if "metric_filter" not in st.session_state:
    st.session_state.metric_filter = "All"   # All / Reorder ASAP
if "inv_raw_df" not in st.session_state:
    st.session_state.inv_raw_df = None
if "sales_raw_df" not in st.session_state:
    st.session_state.sales_raw_df = None
if "extra_sales_df" not in st.session_state:
    st.session_state.extra_sales_df = None
if "theme" not in st.session_state:
    st.session_state.theme = "Dark"  # Dark by default

theme = st.session_state.theme

# =========================
# GLOBAL STYLING (theme-aware)
# =========================
main_bg = "rgba(0, 0, 0, 0.85)" if theme == "Dark" else "rgba(255, 255, 255, 0.94)"
main_text = "#ffffff" if theme == "Dark" else "#111111"

st.markdown(
    f"""
    <style>
    .stApp {{
        background-image: url('{background_url}');
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}

    /* Main content area (center) */
    .block-container {{
        background-color: {main_bg};
        padding: 2rem;
        border-radius: 12px;
        color: {main_text} !important;
    }}

    /* Force almost all text in main area to theme text, but keep input text default */
    .block-container *:not(input):not(textarea):not(select) {{
        color: {main_text} !important;
    }}

    /* Keep tables readable on dark background */
    .dataframe td {{
        color: {main_text} !important;
    }}

    .stButton>button {{
        background-color: rgba(255, 255, 255, 0.08);
        color: {main_text};
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
        color: {main_text} !important;
    }}

    /* Sidebar: light, high-contrast for typing */
    [data-testid="stSidebar"] {{
        background-color: #f3f4f6 !important;
    }}
    [data-testid="stSidebar"] * {{
        color: #111111 !important;
        font-size: 0.9rem;
    }}
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] select {{
        background-color: #ffffff !important;
        color: #111111 !important;
        border-radius: 4px;
    }}

    /* PO-only labels in main content */
    .po-label {{
        color: {main_text} !important;
        font-weight: 600;
        font-size: 0.9rem;
        margin-bottom: 0.1rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# HELPER FUNCTIONS
# =========================

def normalize_col(col: str) -> str:
    """Lower + strip non-alphanumerics for matching (no spaces, etc.)."""
    return re.sub(r"[^a-z0-9]", "", str(col).lower())


def detect_column(columns, aliases):
    """
    Auto-detect a column by comparing normalized names
    against a list of alias keys (already normalized).
    """
    norm_map = {normalize_col(c): c for c in columns}
    for alias in aliases:
        if alias in norm_map:
            return norm_map[alias]
    return None


def normalize_rebelle_category(raw):
    """Map similar names to canonical Rebelle categories."""
    s = str(raw).lower().strip()

    # Flower
    if any(k in s for k in ["flower", "bud", "buds", "cannabis flower"]):
        return "flower"

    # Pre Rolls
    if any(k in s for k in ["pre roll", "preroll", "pre-roll", "joint", "joints"]):
        return "pre rolls"

    # Vapes
    if any(k in s for k in ["vape", "cart", "cartridge", "pen", "pod"]):
        return "vapes"

    # Edibles
    if any(k in s for k in ["edible", "gummy", "chocolate", "chew", "cookies"]):
        return "edibles"

    # Beverages
    if any(k in s for k in ["beverage", "drink", "drinkable", "shot", "beverages"]):
        return "beverages"

    # Concentrates
    if any(k in s for k in ["concentrate", "wax", "shatter", "crumble", "resin", "rosin", "dab"]):
        return "concentrates"

    # Tinctures
    if any(k in s for k in ["tincture", "tinctures", "drops", "sublingual", "dropper"]):
        return "tinctures"

    # Topicals
    if any(k in s for k in ["topical", "lotion", "cream", "salve", "balm"]):
        return "topicals"

    return s  # unchanged if not matched


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

    # Recognize vapes / pens
    vape = any(k in s for k in ["vape", "cart", "cartridge", "pen", "pod"])
    preroll = any(k in s for k in ["pre roll", "preroll", "pre-roll", "joint"])

    # Disposables (vapes)
    if ("disposable" in s or "dispos" in s) and vape:
        return base + " disposable" if base != "unspecified" else "disposable"

    # Infused pre-rolls
    if "infused" in s and preroll:
        return base + " infused" if base != "unspecified" else "infused"

    return base


def extract_size(text, context=None):
    s = str(text).lower()

    # mg doses
    mg = re.search(r"(\d+(\.\d+)?\s?mg)", s)
    if mg:
        return mg.group(1).replace(" ", "")

    # grams / ounces: normalize 1oz/1 oz/28g to "28g"
    g = re.search(r"((?:\d+\.?\d*|\.\d+)\s?(g|oz))", s)
    if g:
        val = g.group(1).replace(" ", "")
        val_lower = val.lower()
        if val_lower in ["1oz", "1.0oz", "28g", "28.0g"]:
            return "28g"
        return val_lower

    # 0.5g style vapes (if "vape", "cart", "pen", "pod" appears)
    if any(k in s for k in ["vape", "cart", "cartridge", "pen", "pod"]):
        half = re.search(r"\b0\.5\b|\b\.5\b", s)
        if half:
            return "0.5g"

    return "unspecified"


def read_inventory_file(uploaded_file):
    """
    Read inventory CSV while being robust to 3–5 line headers
    (e.g., Dutchie/BLAZE 'Export Date / From Date / To Date' at the top).
    """
    uploaded_file.seek(0)
    tmp = pd.read_csv(uploaded_file, header=None)
    header_row = 0
    max_scan = min(10, len(tmp))
    for i in range(max_scan):
        row_text = " ".join(str(v) for v in tmp.iloc[i].tolist()).lower()
        if any(tok in row_text for tok in ["product", "item", "sku", "name"]):
            header_row = i
            break
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, header=header_row)
    return df


def read_sales_file(uploaded_file):
    """
    Read Excel sales report with smart header detection.
    Looks for a row that contains something like 'category' and 'product'
    (Dutchie 'Total Sales by Product' style) and uses that as the header.
    """
    uploaded_file.seek(0)
    tmp = pd.read_excel(uploaded_file, header=None)
    header_row = 0
    max_scan = min(15, len(tmp))
    for i in range(max_scan):
        row_text = " ".join(str(v) for v in tmp.iloc[i].tolist()).lower()
        if "category" in row_text and ("product" in row_text or "name" in row_text):
            header_row = i
            break
    uploaded_file.seek(0)
    df = pd.read_excel(uploaded_file, header=header_row)
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

    # Header Title
    y = top_margin
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left_margin, y, f"{CLIENT_NAME} - Purchase Order")
    y -= 0.25 * inch

    # PO Number and Date
    c.setFont("Helvetica", 10)
    c.drawString(left_margin, y, f"PO Number: {po_number}")
    c.drawRightString(right_margin, y, f"Date: {po_date.strftime('%m/%d/%Y')}")
    y -= 0.35 * inch

    # Store (Ship-To) block
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

    # Vendor block
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

    # Terms
    y = min(y, vend_y) - 0.15 * inch
    if terms:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(left_margin, y, "Payment Terms:")
        c.setFont("Helvetica", 10)
        c.drawString(left_margin + 90, y, terms)
        y -= 0.25 * inch

    # Notes
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

    # Table header
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

    # Table rows
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
            c.setFont("Helvetica-Bold", 10)
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

    # Totals
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
# 🔐 THEME TOGGLE + ADMIN + TRIAL GATE
# =========================

# Theme toggle in sidebar
st.sidebar.markdown("### 🎨 Theme")
theme_choice = st.sidebar.radio(
    "Mode",
    ["Dark", "Light"],
    index=0 if st.session_state.theme == "Dark" else 1,
)
if theme_choice != st.session_state.theme:
    st.session_state.theme = theme_choice
    st.experimental_rerun()

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

    # Data source selector (for future hooks)
    st.sidebar.markdown("### 🧩 Data Source")
    data_source = st.sidebar.selectbox(
        "Select POS / Data Source",
        ["BLAZE", "Dutchie"],
        index=0,
        help="Changes how column names are interpreted. Files are still just CSV/XLSX exports.",
    )

    st.sidebar.header("📂 Upload Core Reports")

    inv_file = st.sidebar.file_uploader("Inventory CSV", type=["csv"])
    product_sales_file = st.sidebar.file_uploader(
        "Product Sales Report (qty-based)", type=["xlsx"]
    )
    extra_sales_file = st.sidebar.file_uploader(
        "Optional Extra Sales Detail (revenue)",
        type=["xlsx"],
        help="Optional: Dutchie 'Total Sales by Product' or similar. "
             "Currently **ignored for velocity** until revenue views are added.",
    )

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Forecast Settings")
    doh_threshold = st.sidebar.number_input("Target Days on Hand", 1, 60, 21)
    velocity_adjustment = st.sidebar.number_input("Velocity Adjustment", 0.01, 5.0, 0.5)
    date_diff = st.sidebar.slider("Days in Sales Period", 7, 90, 60)

    # Cache raw dataframes when new files are uploaded
    if inv_file is not None:
        try:
            inv_df_raw = read_inventory_file(inv_file)
            st.session_state.inv_raw_df = inv_df_raw
        except Exception as e:
            st.error(f"Error reading inventory file: {e}")
            st.stop()

    if product_sales_file is not None:
        try:
            sales_raw_raw = read_sales_file(product_sales_file)
            st.session_state.sales_raw_df = sales_raw_raw
        except Exception as e:
            st.error(f"Error reading Product Sales report: {e}")
            st.stop()

    if extra_sales_file is not None:
        try:
            extra_sales_raw = read_sales_file(extra_sales_file)
            st.session_state.extra_sales_df = extra_sales_raw
        except Exception:
            # Not critical – we can ignore failures here
            st.session_state.extra_sales_df = None

    if st.session_state.inv_raw_df is not None and st.session_state.sales_raw_df is not None:
        try:
            inv_df = st.session_state.inv_raw_df.copy()
            sales_raw = st.session_state.sales_raw_df.copy()

            # -------- INVENTORY --------
            inv_df.columns = inv_df.columns.str.strip().str.lower()

            # Auto-detect core inventory columns (supports BLAZE & Dutchie)
            inv_name_aliases = [
                "product", "productname", "item", "itemname", "name", "skuname", "skuid"
            ]
            inv_cat_aliases = [
                "category", "subcategory", "productcategory", "department", "mastercategory"
            ]
            inv_qty_aliases = [
                "available", "onhand", "onhandunits", "quantity", "qty",
                "quantityonhand", "instock", "currentquantity", "current quantity"
            ]

            name_col = detect_column(inv_df.columns, [normalize_col(a) for a in inv_name_aliases])
            cat_col = detect_column(inv_df.columns, [normalize_col(a) for a in inv_cat_aliases])
            qty_col = detect_column(inv_df.columns, [normalize_col(a) for a in inv_qty_aliases])

            if not (name_col and cat_col and qty_col):
                st.error(
                    "Could not auto-detect inventory columns (product / category / on-hand). "
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
            # normalize to Rebelle canonical categories
            inv_df["subcategory"] = inv_df["subcategory"].apply(normalize_rebelle_category)

            # Strain Type + Package Size
            inv_df["strain_type"] = inv_df.apply(
                lambda x: extract_strain_type(x["itemname"], x["subcategory"]), axis=1
            )
            inv_df["packagesize"] = inv_df.apply(
                lambda x: extract_size(x["itemname"], x["subcategory"]), axis=1
            )

            # Group inventory by subcategory + strain + size
            inv_summary = (
                inv_df.groupby(["subcategory", "strain_type", "packagesize"])["onhandunits"]
                .sum()
                .reset_index()
            )

            # -------- SALES (qty-based ONLY) --------
            sales_raw.columns = sales_raw.columns.astype(str).str.lower()

            # Auto-detect product name column
            sales_name_aliases = [
                "product", "productname", "product title", "producttitle",
                "productid", "name", "item", "itemname", "skuname",
                "sku", "description"
            ]
            name_col_sales = detect_column(
                sales_raw.columns, [normalize_col(a) for a in sales_name_aliases]
            )

            # Auto-detect quantity/units sold column – STRICTLY counts, not $$
            qty_aliases = [
                "quantitysold", "quantity sold",
                "qtysold", "qty sold",
                "itemsold", "item sold", "items sold",
                "unitssold", "units sold", "unit sold", "unitsold", "units",
                "totalunits", "total units",
                "quantity", "qty",
            ]
            qty_col_sales = detect_column(
                sales_raw.columns, [normalize_col(a) for a in qty_aliases]
            )

            # Extra safety: if the matched column is clearly a revenue column, reject it
            if qty_col_sales is not None:
                norm_qty_name = normalize_col(qty_col_sales)
                revenue_like = {
                    "sales", "netsales", "totalsales", "retailvalue",
                    "grosssales", "saleamount"
                }
                if norm_qty_name in revenue_like:
                    qty_col_sales = None

            # Auto-detect category/mastercategory column
            mc_aliases = [
                "mastercategory", "category", "master_category",
                "productcategory", "product category",
                "department", "dept", "subcategory"
            ]
            mc_col = detect_column(sales_raw.columns, [normalize_col(a) for a in mc_aliases])

            if not (name_col_sales and qty_col_sales and mc_col):
                st.error(
                    "Product Sales file detected but could not find required columns.\n\n"
                    "Looked for some variant of: product / product name, quantity or items sold, "
                    "and category or product category.\n\n"
                    "Tip: Use Dutchie 'Product Sales' or Blaze 'Sales by Product' exports "
                    "without manually editing the headers."
                )
           


::contentReference[oaicite:0]{index=0}

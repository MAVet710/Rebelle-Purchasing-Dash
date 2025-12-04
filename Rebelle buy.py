import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime
from io import BytesIO

# For PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

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
# GLOBAL STYLING WITH PO LABEL FIX
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
        color: white !important;
    }}

    .dataframe td {{
        color: white !important;
    }}

    .stButton>button {{
        background-color: rgba(255, 255, 255, 0.08);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.8);
        border-radius: 6px;
    }}

    .stButton>button:hover {{
        background-color: rgba(255, 255, 255, 0.25);
    }}

    .metric-label {{
        font-size: 0.8rem;
        opacity: 0.8;
    }}

    /* Make all labels readable on dark background */
    .stTextInput label,
    .stNumberInput label,
    .stDateInput label,
    .stTextArea label,
    .stSelectbox label,
    .stRadio label,
    label {{
        color: white !important;
        font-weight: 600 !important;
    }}

    .stTextInput input,
    .stNumberInput input,
    .stDateInput input,
    .stTextArea textarea {{
        color: white !important;
    }}

    ::placeholder {{
        color: rgba(200,200,200,0.65) !important;
    }}

    .footer {{
        text-align: center;
        font-size: 0.75rem;
        opacity: 0.7;
        margin-top: 2rem;
        color: white !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

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

    # Margins
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
        c.drawString(left_margin, y, f"Payment Terms: ")
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
            # New page for more lines
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

    # Totals section
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

    st.sidebar.header("📂 Upload Core Reports")

    inv_file = st.sidebar.file_uploader("Inventory CSV", type="csv")
    product_sales_file = st.sidebar.file_uploader("Product Sales Report", type="xlsx")

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Forecast Settings")
    doh_threshold = st.sidebar.number_input("Target Days on Hand", 1, 60, 21)
    velocity_adjustment = st.sidebar.number_input("Velocity Adjustment", 0.01, 5.0, 0.5)

    date_diff = st.sidebar.slider("Days in Sales Period", 7, 90, 60)

    if inv_file and product_sales_file:
        try:
            inv_df = pd.read_csv(inv_file)
            inv_df.columns = inv_df.columns.str.strip().str.lower()

            inv_df = inv_df.rename(
                columns={"product": "itemname", "category": "subcategory", "available": "onhandunits"}
            )
            inv_df["onhandunits"] = pd.to_numeric(inv_df["onhandunits"], errors="coerce").fillna(0)
            inv_df["subcategory"] = inv_df["subcategory"].astype(str).str.lower()

            def extract_strain_type(name, subcat):
                s = str(name).lower()
                base = "unspecified"
                if "indica" in s: base = "indica"
                elif "sativa" in s: base = "sativa"
                elif "hybrid" in s: base = "hybrid"
                elif "cbd" in s: base = "cbd"

                vape = any(k in s for k in ["vape", "cart", "cartridge", "pen", "pod"])
                preroll = any(k in s for k in ["pre roll", "preroll", "joint"])

                if ("disposable" in s or "dispos" in s) and vape:
                    return base + " disposable" if base != "unspecified" else "disposable"
                if "infused" in s and preroll:
                    return base + " infused" if base != "unspecified" else "infused"
                return base

            def extract_size(text, context=None):
                s = str(text).lower()
                mg = re.search(r"(\d+(\.\d+)?\s?mg)", s)
                if mg: return mg.group(1).replace(" ", "")
                g = re.search(r"((?:\d+\.?\d*|\.\d+)\s?g)", s)
                if g: return g.group(1).replace(" ", "")
                if any(k in s for k in ["vape", "cart", "pen", "pod"]):
                    half = re.search(r"\b0\.5\b|\b\.5\b", s)
                    if half: return "0.5g"
                return "unspecified"

            inv_df["strain_type"] = inv_df.apply(lambda x: extract_strain_type(x["itemname"], x["subcategory"]), axis=1)
            inv_df["packagesize"] = inv_df.apply(lambda x: extract_size(x["itemname"], x["subcategory"]), axis=1)

            sales_raw = pd.read_excel(product_sales_file)
            sales_raw.columns = sales_raw.columns.astype(str).str.lower()

            for try_col in ["product", "product name", "name", "item"]:
                if try_col in sales_raw.columns:
                    name_col = try_col
                    break
            else:
                st.error("No product name column found in Product Sales report.")
                st.stop()

            for try_col in ["quantity sold", "qty sold", "units sold", "units"]:
                if try_col in sales_raw.columns:
                    qty_col = try_col
                    break
            else:
                qty_col = None

            sales_raw["product_name"] = sales_raw[name_col].astype(str)
            sales_raw["unitssold"] = pd.to_numeric(sales_raw.get(qty_col, 0), errors="coerce").fillna(0)

            if "mastercategory" not in sales_raw.columns:
                if "category" in sales_raw.columns:
                    sales_raw = sales_raw.rename(columns={"category": "mastercategory"})
                else:
                    st.error("Master category missing.")
                    st.stop()

            sales_raw["mastercategory"] = sales_raw["mastercategory"].astype(str).str.lower()

            sales_df = sales_raw[
                ~sales_raw["mastercategory"].str.contains("accessor") &
                (sales_raw["mastercategory"] != "all")
            ].copy()

            sales_df["packagesize"] = sales_df.apply(
                lambda row: extract_size(row["product_name"], row["mastercategory"]),
                axis=1,
            )

            inv_summary = inv_df.groupby(["subcategory", "strain_type", "packagesize"])["onhandunits"].sum().reset_index()
            sales_summary = sales_df.groupby(["mastercategory", "packagesize"])["unitssold"].sum().reset_index()
            sales_summary["avgunitsperday"] = (sales_summary["unitssold"] / date_diff) * velocity_adjustment

            detail = pd.merge(
                inv_summary,
                sales_summary,
                how="left",
                left_on=["subcategory", "packagesize"],
                right_on=["mastercategory", "packagesize"],
            ).fillna(0)

            detail["daysonhand"] = np.where(
                detail["avgunitsperday"] > 0,
                detail["onhandunits"] / detail["avgunitsperday"],
                0,
            ).astype(int)

            detail["reorderqty"] = np.where(
                detail["daysonhand"] < doh_threshold,
                np.ceil((doh_threshold - detail["daysonhand"]) * detail["avgunitsperday"]),
                0,
            ).astype(int)

            def tag(row):
                if row["daysonhand"] <= 7: return "1 – Reorder ASAP"
                if row["daysonhand"] <= 21: return "2 – Watch Closely"
                if row["avgunitsperday"] == 0: return "4 – Dead Item"
                return "3 – Comfortable Cover"

            detail["reorderpriority"] = detail.apply(tag, axis=1)

            all_cats = sorted(detail["subcategory"].unique())
            selected_cats = st.sidebar.multiselect("Visible Categories", all_cats, default=all_cats)
            detail = detail[detail["subcategory"].isin(selected_cats)]

            st.markdown("### Inventory Summary")

            total_units = int(detail["unitssold"].sum())
            reorder_asap = (detail["reorderpriority"] == "1 – Reorder ASAP").sum()

            col1, col2 = st.columns(2)
            col1.metric("Units Sold", total_units)
            col2.metric("Reorder ASAP", reorder_asap)

            st.markdown("### Forecast Table")

            def red_low(val):
                return "color:#FF3131" if val < doh_threshold else ""

            for cat, group in detail.groupby("subcategory"):
                with st.expander(cat.title()):
                    st.dataframe(group.style.applymap(red_low, subset=["daysonhand"]), use_container_width=True)

        except Exception as e:
            st.error(f"Error: {e}")

    else:
        st.info("Upload inventory + product sales files to continue.")

# ============================================================
# PAGE 2 – PO BUILDER (WITH PDF EXPORT)
# ============================================================
else:
    st.subheader("🧾 Purchase Order Builder")

    st.markdown(
        "Build a professional PO and export it as a **PDF** formatted like a vendor order."
    )

    # -------------------------
    # HEADER INFO
    # -------------------------
    st.markdown("### PO Header")

    col1, col2 = st.columns(2)

    with col1:
        store_name = st.text_input("Store / Ship-To Name", value="Rebelle Cannabis")
        store_number = st.text_input("Store #", "")
        store_address = st.text_input("Store Address", "")
        store_phone = st.text_input("Store Phone", "")
        store_contact = st.text_input("Buyer / Contact Name", "")

    with col2:
        vendor_name = st.text_input("Vendor Name", "")
        vendor_license = st.text_input("Vendor License Number", "")
        vendor_address = st.text_input("Vendor Address", "")
        vendor_contact = st.text_input("Vendor Contact / Email", "")
        po_number = st.text_input("PO Number", "")
        po_date = st.date_input("PO Date", datetime.today())
        terms = st.text_input("Payment Terms", "Net 30")

    notes = st.text_area("PO Notes / Special Instructions", "", height=70)

    st.markdown("---")

    # -------------------------
    # LINE ITEMS
    # -------------------------
    st.markdown("### Line Items")

    num_lines = st.number_input("Number of Line Items", 1, 50, 5)

    items = []
    for i in range(int(num_lines)):
        with st.expander(f"Line {i + 1}", expanded=(i < 3)):
            c1, c2, c3, c4, c5, c6 = st.columns([1.2, 2.5, 1.4, 1.2, 1.2, 1.3])

            sku = c1.text_input("SKU ID", key=f"sku_{i}")
            desc = c2.text_input("SKU Name / Description", key=f"desc_{i}")
            strain = c3.text_input("Strain / Type", key=f"strain_{i}")
            size = c4.text_input("Size (e.g. 3.5g)", key=f"size_{i}")
            qty = c5.number_input("Qty", min_value=0, step=1, key=f"qty_{i}")
            price = c6.number_input("Unit Price ($)", min_value=0.0, step=0.01, key=f"price_{i}")

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
        (po_df["SKU"].astype(str).str.strip() != "") |
        (po_df["Description"].astype(str).str.strip() != "") |
        (po_df["Qty"] > 0)
    ]

    st.markdown("---")

    # -------------------------
    # TOTALS + PDF EXPORT
    # -------------------------
    if not po_df.empty:

        subtotal = float(po_df["Line Total"].sum())

        c1, c2, c3 = st.columns(3)
        tax_rate = c1.number_input("Tax Rate (%)", 0.0, 30.0, 0.0)
        discount = c2.number_input("Discount ($)", 0.0, step=0.01)
        shipping = c3.number_input("Shipping / Fees ($)", 0.0, step=0.01)

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

        # Generate PDF
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

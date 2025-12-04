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
            sales_raw.columns = (
                sales_raw.columns.astype(str).str.strip().str.lower()
            )

            # Ensure we have a mastercategory
            if "mastercategory" not in sales_raw.columns:
                if "category" in sales_raw.columns:
                    sales_raw = sales_raw.rename(
                        columns={"category": "mastercategory"}
                    )
                else:
                    st.error(
                        "Product Sales Report is missing a 'mastercategory' or 'category' column."
                    )
                    st.stop()

            # Detect product name column
            product_col_candidates = [
                "product",
                "product name",
                "productname",
                "item",
                "item name",
                "itemname",
                "name",
            ]
            name_col = None
            for c in product_col_candidates:
                if c in sales_raw.columns:
                    name_col = c
                    break

            if name_col is None:
                st.error(
                    "Could not find a product name column in the Product Sales Report. "
                    "Expected one of: product, product name, item, item name, name."
                )
                st.stop()

            sales_raw["product_name"] = sales_raw[name_col].astype(str)

            # Detect / create unitssold
            if "unitssold" not in sales_raw.columns:
                qty_candidates = [
                    "quantity sold",
                    "qty sold",
                    "units sold",
                    "units",
                ]
                qty_col = None
                for c in qty_candidates:
                    if c in sales_raw.columns:
                        qty_col = c
                        break

                if qty_col is not None:
                    sales_raw["unitssold"] = sales_raw[qty_col]
                else:
                    st.warning(
                        "No 'quantity sold' style column found; setting unitssold to 0 for all rows."
                    )
                    sales_raw["unitssold"] = 0

            sales_df = sales_raw[sales_raw["mastercategory"].notna()].copy()
            sales_df["mastercategory"] = (
                sales_df["mastercategory"].astype(str).str.strip().str.lower()
            )

            # Normalize size on sales using product_name text, just like inventory
            sales_df["packagesize"] = sales_df.apply(
                lambda row: extract_size(row["product_name"], row["mastercategory"]),
                axis=1,
            )

            # Force unitssold numeric
            sales_df["unitssold"] = pd.to_numeric(
                sales_df.get("unitssold", 0), errors="coerce"
            ).fillna(0)

            # Drop accessories and "all" aggregate rows
            sales_df = sales_df[
                ~sales_df["mastercategory"].str.contains("accessor")
            ]
            sales_df = sales_df[sales_df["mastercategory"] != "all"]

            # ----------------------------
            # Aggregate + velocity
            # ----------------------------
            inventory_summary = (
                inv_df.groupby(
                    ["subcategory", "strain_type", "packagesize"]
                )["onhandunits"]
                .sum()
                .reset_index()
            )

            agg = (
                sales_df.groupby(["mastercategory", "packagesize"])
                .agg({"unitssold": "sum"})
                .reset_index()
            )
            agg["avgunitsperday"] = (
                agg["unitssold"].astype(float) / date_diff * velocity_adjustment
            )

            detail = pd.merge(
                inventory_summary,
                agg,
                left_on=["subcategory", "packagesize"],
                right_on=["mastercategory", "packagesize"],
                how="left",
            )

            # Fill numeric nulls *after* merge
            detail["unitssold"] = pd.to_numeric(
                detail.get("unitssold", 0), errors="coerce"
            ).fillna(0)
            detail["avgunitsperday"] = pd.to_numeric(
                detail.get("avgunitsperday", 0), errors="coerce"
            ).fillna(0)

            detail["daysonhand"] = np.where(
                detail["avgunitsperday"] > 0,
                detail["onhandunits"] / detail["avgunitsperday"],
                np.nan,
            )
            detail["daysonhand"] = (
                detail["daysonhand"]
                .replace([np.inf, -np.inf], np.nan)
                .fillna(0)
            )
            detail["daysonhand"] = detail["daysonhand"].astype(int)

            detail["reorderqty"] = np.where(
                detail["daysonhand"] < doh_threshold,
                np.ceil(
                    (doh_threshold - detail["daysonhand"])
                    * detail["avgunitsperday"]
                ).astype(int),
                0,
            )

            def reorder_tag(row):
                if row["daysonhand"] <= 7:
                    return "1 – Reorder ASAP"
                if row["daysonhand"] <= 21:
                    return "2 – Watch Closely"
                if row["avgunitsperday"] == 0:
                    return "4 – Dead Item"
                return "3 – Comfortable Cover"

            detail["reorderpriority"] = detail.apply(reorder_tag, axis=1)

            # =========================
            # CATEGORY FILTER
            # =========================
            all_cats = sorted(detail["subcategory"].unique())
            default_cats = [c for c in all_cats if "accessor" not in c]
            if not default_cats:
                default_cats = all_cats

            st.sidebar.markdown("---")
            st.sidebar.header("🔎 Category Filter")
            selected_cats = st.sidebar.multiselect(
                "Visible Product Categories",
                options=all_cats,
                default=default_cats,
                help="Toggle which categories appear in the metrics, tables, and chart.",
            )

            if selected_cats:
                detail = detail[detail["subcategory"].isin(selected_cats)]
                sales_for_metrics = sales_df[
                    sales_df["mastercategory"].isin(selected_cats)
                ]
            else:
                sales_for_metrics = sales_df.copy()

            # =========================
            # METRICS
            # =========================
            total_units = int(sales_for_metrics["unitssold"].sum())
            active_categories = detail["subcategory"].nunique()
            reorder_asap = (
                detail["reorderpriority"] == "1 – Reorder ASAP"
            ).sum()
            watchlist_items = (
                detail["reorderpriority"] == "2 – Watch Closely"
            ).sum()

            st.markdown("### 📊 Portfolio Snapshot")

            c1, c2, c3, c4 = st.columns(4)
            if c1.button(f"Total Units Sold: {total_units:,}"):
                st.session_state.metric_filter = "None"
            c1.markdown(
                '<span class="metric-label">Across selected period (filtered categories)</span>',
                unsafe_allow_html=True,
            )

            if c2.button(f"Active Subcategories: {active_categories}"):
                st.session_state.metric_filter = "None"
            c2.markdown(
                '<span class="metric-label">Visible subcategory groups</span>',
                unsafe_allow_html=True,
            )

            if c3.button(f"Watchlist Items: {watchlist_items}"):
                st.session_state.metric_filter = "Watchlist"
            c3.markdown(
                '<span class="metric-label">Approaching DOH threshold</span>',
                unsafe_allow_html=True,
            )

            if c4.button(f"Reorder ASAP: {reorder_asap}"):
                st.session_state.metric_filter = "Reorder ASAP"
            c4.markdown(
                '<span class="metric-label">Critically low coverage</span>',
                unsafe_allow_html=True,
            )

            st.markdown("---")

            # =========================
            # FILTERED VIEW FOR PRIORITY BUTTONS
            # =========================
            detail_view = detail.copy()
            if st.session_state.metric_filter == "Watchlist":
                detail_view = detail_view[
                    detail_view["reorderpriority"] == "2 – Watch Closely"
                ]
            elif st.session_state.metric_filter == "Reorder ASAP":
                detail_view = detail_view[
                    detail_view["reorderpriority"] == "1 – Reorder ASAP"
                ]

            # =========================
            # STYLE FUNCTION (RED IF DOH < THRESHOLD)
            # =========================
            def highlight_low_days(val):
                try:
                    v = int(val)
                    if v < doh_threshold:
                        return "color: #FF3131; font-weight: bold;"
                except Exception:
                    pass
                return ""

            # =========================
            # TABLES (MASTER CATEGORY FIRST, WITH STYLING)
            # =========================
            st.markdown("### 🧮 Inventory Forecast by Subcategory")

            for cat, group in detail_view.groupby("subcategory"):
                avg_doh = int(group["daysonhand"].mean()) if len(group) > 0 else 0
                with st.expander(f"{cat.title()} – Avg DOH: {avg_doh}"):
                    preferred_cols = [
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
                    display_cols = [
                        c for c in preferred_cols if c in group.columns
                    ]
                    styled = group[display_cols].style.applymap(
                        highlight_low_days, subset=["daysonhand"]
                    )
                    st.dataframe(styled, use_container_width=True)

            # =========================
            # EXPORT
            # =========================
            csv = detail.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download CSV",
                csv,
                "rebelle_forecast.csv",
                "text/csv",
            )

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
                fig = px.bar(
                    priority_summary,
                    x="reorderpriority",
                    y="itemcount",
                    title="Item Count by Reorder Priority (Filtered Categories)",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(
                    "Plotly not installed. Add `plotly` to requirements.txt to enable charts."
                )
                st.dataframe(priority_summary, use_container_width=True)

        except Exception as e:
            st.error(f"Error processing files: {e}")

    else:
        st.info("Please upload both an Inventory CSV and Product Sales Report.")

# ============================================================
# PAGE 2 – PO BUILDER
# ============================================================
else:
    st.subheader("🧾 Purchase Order Builder")

    st.markdown(
        "Build a **vendor PO** with auto-calculated line totals and a downloadable CSV "
        "(structured like the invoice layout you shared)."
    )

    # -------------------------
    # HEADER INFO
    # -------------------------
    st.markdown("### PO Header Details")

    col_store, col_vendor = st.columns(2)

    # Store / Ship-to block
    with col_store:
        store_name = st.text_input(
            "Store / Ship-To Name",
            value="Rebelle Cannabis",
            placeholder="e.g. Rebelle Cannabis – Great Barrington",
        )
        store_number = st.text_input(
            "Store #",
            placeholder="e.g. MA001",
        )
        store_address = st.text_input(
            "Store Address",
            placeholder="e.g. 1 West Street, Great Barrington, MA 01230",
        )
        store_phone = st.text_input(
            "Store Phone",
            placeholder="e.g. (413) 555-1234",
        )
        store_contact = st.text_input(
            "Buyer / Contact Name",
            placeholder="e.g. Nelson DaSilva",
        )

    # Vendor block
    with col_vendor:
        vendor_name = st.text_input(
            "Vendor Name",
            placeholder="e.g. Cresco Labs",
        )
        vendor_license = st.text_input(
            "Vendor License Number",
            placeholder="e.g. MCT1425",
        )
        vendor_address = st.text_input(
            "Vendor Address",
            placeholder="e.g. 20 Example Ave, Worcester, MA 01605",
        )
        vendor_contact = st.text_input(
            "Vendor Contact / Email",
            placeholder="e.g. orders@vendor.com",
        )

    col_po1, col_po2 = st.columns(2)
    with col_po1:
        po_number = st.text_input(
            "Order / PO #",
            placeholder="e.g. 31144426",
        )
        vendor_order = st.text_input(
            "Vendor Sales Order #",
            placeholder="Optional – from vendor confirmation",
        )
    with col_po2:
        po_date = st.date_input("Order Date", datetime.today())
        terms = st.text_input(
            "Payment Terms",
            value="Net 30",
            placeholder="e.g. Net 30, COD, Prepaid",
        )

    notes = st.text_area(
        "PO Notes / Special Instructions",
        height=80,
        placeholder="Delivery windows, packaging requests, promo notes, etc.",
    )

    st.markdown("---")

    # -------------------------
    # LINE ITEMS
    # -------------------------
    st.markdown("### Line Items")

    num_lines = st.number_input(
        "Number of Line Items",
        min_value=1,
        max_value=50,
        value=5,
        step=1,
        help="Set how many SKU rows you want to build into this PO.",
    )

    line_items = []

    for i in range(int(num_lines)):
        with st.expander(f"Line {i + 1}", expanded=(i < 3)):
            c1, c2, c3, c4, c5, c6 = st.columns([1.2, 2.5, 1.4, 1.2, 1.2, 1.3])

            with c1:
                sku = st.text_input(
                    "SKU ID",
                    key=f"sku_{i}",
                    placeholder="e.g. 267570",
                )
            with c2:
                desc = st.text_input(
                    "SKU Name / Description",
                    key=f"desc_{i}",
                    placeholder="e.g. Eleven Flower 3.5g – Marshmallow OG",
                )
            with c3:
                strain = st.text_input(
                    "Strain / Type",
                    key=f"strain_{i}",
                    placeholder="e.g. Hybrid, Indica, CBD",
                )
            with c4:
                size = st.text_input(
                    "Size",
                    key=f"size_{i}",
                    placeholder="e.g. 3.5g, 7g, 1g pre-roll",
                )
            with c5:
                units = st.number_input(
                    "Qty",
                    min_value=0,
                    value=0,
                    step=1,
                    key=f"units_{i}",
                    help="Number of units ordered for this SKU.",
                )
            with c6:
                cost = st.number_input(
                    "Unit Price ($)",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    key=f"cost_{i}",
                    help="Cost per unit before discounts.",
                )

            line_total = units * cost

            st.markdown(
                f"**Line Total:** ${line_total:,.2f}"
                if line_total > 0
                else "**Line Total:** $0.00"
            )

            line_items.append(
                {
                    "line": i + 1,
                    "sku": sku,
                    "description": desc,
                    "strain_type": strain,
                    "size": size,
                    "units": units,
                    "unit_cost": cost,
                    "line_total": line_total,
                }
            )

    # Filter out completely empty lines
    po_df = pd.DataFrame(line_items)
    if not po_df.empty:
        po_df = po_df[
            (po_df["sku"].astype(str).str.strip() != "")
            | (po_df["description"].astype(str).str.strip() != "")
            | (po_df["units"] > 0)
        ]

    st.markdown("---")

    # -------------------------
    # TOTALS
    # -------------------------
    if not po_df.empty:
        subtotal = float(po_df["line_total"].sum())

        col_tot1, col_tot2, col_tot3, col_tot4, col_tot5 = st.columns(5)
        with col_tot1:
            tax_rate = st.number_input(
                "Tax Rate (%)",
                min_value=0.0,
                max_value=30.0,
                value=0.0,
                step=0.25,
            )
        with col_tot2:
            discount = st.number_input(
                "Manual Cost Discount ($)",
                min_value=0.0,
                value=0.0,
                step=0.01,
                help="Total discount applied to this PO (shown as negative).",
            )
        with col_tot3:
            shipping = st.number_input(
                "Shipping / Fees ($)",
                min_value=0.0,
                value=0.0,
                step=0.01,
            )
        with col_tot4:
            _ = st.empty()  # spacer
        with col_tot5:
            _ = st.empty()

        tax_amount = subtotal * (tax_rate / 100.0)
        total = subtotal + tax_amount + shipping - discount

        st.markdown("### PO Summary")

        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("SUBTOTAL", f"${subtotal:,.2f}")
        s2.metric(
            "Manual Cost Discount",
            f"-${discount:,.2f}" if discount > 0 else "$0.00",
        )
        s3.metric("Tax", f"${tax_amount:,.2f}")
        s4.metric("Shipping / Fees", f"${shipping:,.2f}")
        s5.metric("TOTAL", f"${total:,.2f}")

        st.markdown("### PO Line Item Table")

        display_df = po_df.rename(
            columns={
                "line": "Line",
                "sku": "SKU ID",
                "description": "SKU Name",
                "strain_type": "Strain / Type",
                "size": "Size",
                "units": "Qty",
                "unit_cost": "Unit Price ($)",
                "line_total": "Line Total ($)",
            }
        )

        st.dataframe(display_df, use_container_width=True)

        # -------------------------
        # DOWNLOAD
        # -------------------------
        st.markdown("#### Download")

        csv_po = display_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download PO Line Items (CSV)",
            csv_po,
            f"PO_{po_number or 'rebelle'}.csv",
            "text/csv",
        )

        # Optional: a simple text header summary you can paste into email / PDF
        st.markdown("#### PO Header Snapshot")
        st.code(
            f"Store: {store_name} (Store #{store_number})\n"
            f"Address: {store_address}\n"
            f"Phone: {store_phone}\n"
            f"Buyer: {store_contact}\n\n"
            f"Vendor: {vendor_name}\n"
            f"Vendor License: {vendor_license}\n"
            f"Vendor Address: {vendor_address}\n"
            f"Vendor Contact: {vendor_contact}\n\n"
            f"Order / PO #: {po_number}\n"
            f"Vendor Sales Order #: {vendor_order}\n"
            f"Order Date: {po_date}\n"
            f"Terms: {terms}\n"
            f"Notes: {notes}\n\n"
            f"PO Total: ${total:,.2f}",
            language="text",
        )

    else:
        st.info(
            "Add at least one line item (SKU ID, SKU Name, or Qty) to see totals and export options."
        )

# =========================
# FOOTER
# =========================
st.markdown("---")
year = datetime.now().year
st.markdown(
    f'<div class="footer">{LICENSE_FOOTER} • © {year}</div>',
    unsafe_allow_html=True,
)

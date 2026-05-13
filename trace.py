import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import math
import qrcode
from fpdf import FPDF
import tempfile
import os

# ==========================================
# 1. PAGE CONFIGURATION & SETUP
# ==========================================
st.set_page_config(page_title="Trace Inventory", page_icon="📦", layout="wide")

# ==========================================
# 2. GOOGLE SHEETS AUTHENTICATION
# ==========================================
@st.cache_resource
def init_connection():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client

try:
    client = init_connection()
    spreadsheet = client.open("Trace")
except Exception as e:
    st.error(f"Failed to connect to Google Sheets. Check your secrets.toml. Error: {e}")
    st.stop()

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
@st.cache_data(ttl=60)
def load_main_inventory():
    try:
        sheet = spreadsheet.sheet1
        return sheet.get_all_records()
    except Exception as e:
        return None

def generate_label_pdf(item_type, description, location, quantity):
    # A4 Layout Configuration
    LABELS_PER_ROW, ROWS_PER_PAGE = 3, 7
    LABELS_PER_PAGE = LABELS_PER_ROW * ROWS_PER_PAGE
    A4_WIDTH, A4_HEIGHT = 210, 297
    MARGIN_X, MARGIN_Y = 10, 10
    LABEL_W = (A4_WIDTH - (2 * MARGIN_X)) / LABELS_PER_ROW
    LABEL_H = (A4_HEIGHT - (2 * MARGIN_Y)) / ROWS_PER_PAGE

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_font("helvetica", size=8)

    with tempfile.TemporaryDirectory() as temp_dir:
        for i in range(quantity):
            current_label_on_page = i % LABELS_PER_PAGE
            if i > 0 and current_label_on_page == 0:
                pdf.add_page()

            col = current_label_on_page % LABELS_PER_ROW
            row = current_label_on_page // LABELS_PER_ROW
            x = MARGIN_X + (col * LABEL_W)
            y = MARGIN_Y + (row * LABEL_H)

            unique_id = f"{item_type[:3].upper()}-{i+1:03d}"
            qr_data = f"ID: {unique_id}\nType: {item_type}\nDesc: {description}\nLoc: {location}"
            
            qr = qrcode.make(qr_data)
            qr_path = os.path.join(temp_dir, f"qr_{i}.png")
            qr.save(qr_path)

            pdf.rect(x, y, LABEL_W, LABEL_H)
            qr_size = LABEL_H - 15 
            pdf.image(qr_path, x=x + 2, y=y + 2, w=qr_size, h=qr_size)

            text_x, text_y = x + qr_size + 4, y + 8
            pdf.text(x=text_x, y=text_y, text=f"ID: {unique_id}")
            pdf.text(x=text_x, y=text_y + 4, text=f"{item_type[:15]}")
            short_desc = description[:18] + "..." if len(description) > 18 else description
            pdf.text(x=text_x, y=text_y + 8, text=f"{short_desc}")
            pdf.text(x=text_x, y=text_y + 12, text=f"Loc: {location[:15]}")

    # FIX: Convert the bytearray returned by fpdf2 into standard bytes for Streamlit
    return bytes(pdf.output())

# ==========================================
# 4. APP LAYOUT & UI
# ==========================================
st.title("📦 trace.py")
st.markdown("### Physical Asset & Equipment Manager")

# Create the tabs (CSV Importer removed)
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📷 Scanner", "🖨️ Label Generator"])

# --- TAB 1: DASHBOARD ---
with tab1:
    st.subheader("Current Inventory Overview")
    data = load_main_inventory()
    
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
        
        # Simple metrics
        st.markdown("### Quick Stats")
        col1, col2 = st.columns(2)
        col1.metric("Total Items Tracked", len(df))
        if 'Category' in df.columns:
            col2.metric("Categories", df['Category'].nunique())
    else:
        st.info("The main 'Trace' sheet is empty or headers are missing. Add data to Row 1 of your Google Sheet!")

# --- TAB 2: SCANNER ---
with tab2:
    st.subheader("Mobile QR Scanner")
    st.info("This module uses your device camera to check items in and out.")
    st.warning("To enable live scanning, ensure the app is accessed via HTTPS.")

# --- TAB 3: LABEL GENERATOR ---
with tab3:
    st.subheader("Generate A4 QR Asset Labels")
    
    with st.form("batch_label_form"):
        col1, col2 = st.columns(2)
        with col1:
            item_type = st.text_input("Item Type", placeholder="e.g., Wireless Audio")
            description = st.text_input("Description", placeholder="e.g., DJI Mic Mini TX unit")
        with col2:
            location = st.selectbox("Storage Location", [
                "Studio Gear Box 1", 
                "School Office - Cabinet A", 
                "Computer Lab", 
                "Everyday Carry"
            ])
            quantity = st.number_input("Quantity to Generate", min_value=1, value=21, step=1)
        
        generate_btn = st.form_submit_button("Preview & Generate PDF")

    if generate_btn and item_type and description:
        LABELS_PER_PAGE = 21 # 3x7 grid
        pages_needed = math.ceil(quantity / LABELS_PER_PAGE)
        slots_filled = quantity % LABELS_PER_PAGE
        if slots_filled == 0: slots_filled = LABELS_PER_PAGE
        
        st.markdown("### Print Job Summary")
        m1, m2, m3 = st.columns(3)
        m1.metric("A4 Pages Required", pages_needed)
        m2.metric("Total Labels", quantity)
        if slots_filled == LABELS_PER_PAGE:
            m3.success("✅ Pages perfectly full!")
        else:
            m3.warning(f"⚠️ Last page has {LABELS_PER_PAGE - slots_filled} blank slots.")

        with st.spinner("Generating PDF with QR codes..."):
            pdf_bytes = generate_label_pdf(item_type, description, location, quantity)
            
        st.download_button(
            label="📄 Download A4 Print Sheet (PDF)",
            data=pdf_bytes,
            file_name=f"Trace_Labels_{item_type.replace(' ', '_')}.pdf",
            mime="application/pdf",
            type="primary"
        )
    elif generate_btn:
        st.error("Please fill in the Item Type and Description.")

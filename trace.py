import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import math
import qrcode
from fpdf import FPDF
import tempfile
import os
from datetime import datetime

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
    st.error(f"Failed to connect to Google Sheets. Error: {e}")
    st.stop()

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
TABS = ["Files", "Devices", "Things", "Other"]
PREFIXES = {"Files": "FIL", "Devices": "DEV", "Things": "THI", "Other": "OTH"}

@st.cache_data(ttl=30)
def get_all_locations():
    """Scans all tabs to find existing unique locations to populate the dropdown."""
    locations = set()
    for tab_name in TABS:
        try:
            records = spreadsheet.worksheet(tab_name).get_all_records()
            for r in records:
                if 'Location' in r and str(r['Location']).strip():
                    locations.add(str(r['Location']).strip())
        except Exception:
            pass
    if not locations:
        locations.add("GF001") # Default starting point
    return sorted(list(locations))

def generate_label_pdf(category, description, location, quantity, start_num, include_qr):
    LABELS_PER_ROW, ROWS_PER_PAGE = 3, 7
    LABELS_PER_PAGE = LABELS_PER_ROW * ROWS_PER_PAGE
    A4_WIDTH, A4_HEIGHT = 210, 297
    MARGIN_X, MARGIN_Y = 10, 10
    LABEL_W = (A4_WIDTH - (2 * MARGIN_X)) / LABELS_PER_ROW
    LABEL_H = (A4_HEIGHT - (2 * MARGIN_Y)) / ROWS_PER_PAGE

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    prefix = PREFIXES[category]

    with tempfile.TemporaryDirectory() as temp_dir:
        for i in range(quantity):
            current_label_on_page = i % LABELS_PER_PAGE
            if i > 0 and current_label_on_page == 0:
                pdf.add_page()

            col = current_label_on_page % LABELS_PER_ROW
            row = current_label_on_page // LABELS_PER_ROW
            x = MARGIN_X + (col * LABEL_W)
            y = MARGIN_Y + (row * LABEL_H)

            unique_id = f"{prefix}-{start_num + i:03d}"
            
            # Draw label boundary
            pdf.rect(x, y, LABEL_W, LABEL_H)
            
            short_desc = description[:22] + "..." if len(description) > 22 else description
            
            if include_qr:
                # With QR Code Layout
                qr_data = f"ID: {unique_id}\nType: {category}\nDesc: {description}\nLoc: {location}"
                qr = qrcode.make(qr_data)
                qr_path = os.path.join(temp_dir, f"qr_{i}.png")
                qr.save(qr_path)

                qr_size = LABEL_H - 15 
                pdf.image(qr_path, x=x + 2, y=y + 2, w=qr_size, h=qr_size)

                pdf.set_font("helvetica", size=8)
                text_x, text_y = x + qr_size + 4, y + 8
                pdf.text(x=text_x, y=text_y, text=f"ID: {unique_id}")
                pdf.text(x=text_x, y=text_y + 4, text=f"{category}")
                pdf.text(x=text_x, y=text_y + 8, text=f"{short_desc}")
                pdf.text(x=text_x, y=text_y + 12, text=f"Loc: {location[:15]}")
            else:
                # No QR Code Layout (Text only, centered and larger)
                pdf.set_font("helvetica", "B", 12)
                pdf.text(x=x + 5, y=y + 10, text=f"ID: {unique_id}")
                pdf.set_font("helvetica", "", 10)
                pdf.text(x=x + 5, y=y + 18, text=f"Category: {category}")
                pdf.text(x=x + 5, y=y + 26, text=f"Desc: {short_desc}")
                pdf.text(x=x + 5, y=y + 34, text=f"Loc: {location}")

    return bytes(pdf.output())

# ==========================================
# 4. APP LAYOUT & UI
# ==========================================
st.title("📦 trace.py")
st.markdown("### Physical Asset & Equipment Manager")

tab1, tab2, tab3 = st.tabs(["📝 Add Data & Print Labels", "📊 Dashboard", "📷 Scanner"])

# --- TAB 1: ADD DATA & LABEL GENERATOR ---
with tab1:
    st.subheader("Register New Asset & Generate Labels")
    
    # Form input
    with st.form("data_entry_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            category = st.selectbox("Category (Select Tab)", TABS)
            description = st.text_input("Contain / Description", placeholder="e.g., Python Course Files")
            
            existing_locations = get_all_locations()
            loc_choice = st.selectbox("Location", existing_locations + ["+ Add New Location (Type Below)"])
            new_location = st.text_input("New Location Name (if '+ Add New...' selected)", placeholder="e.g., GF002")
            
        with col2:
            qr_yes_no = st.selectbox("Include QR Code on Label?", ["Yes", "No"])
            quantity = st.number_input("Quantity to Generate/Register", min_value=1, value=1, step=1)
            
        submit_btn = st.form_submit_button("Save to Database & Generate PDF")

    if submit_btn:
        # 1. Input Validation
        final_location = new_location if loc_choice == "+ Add New Location (Type Below)" else loc_choice
        if not description or not final_location:
            st.error("Please fill in both Description and Location.")
        else:
            with st.spinner("Connecting to Google Sheets..."):
                try:
                    # 2. Get the correct worksheet and calculate next ID
                    worksheet = spreadsheet.worksheet(category)
                    records = worksheet.get_all_records()
                    next_id_num = len(records) + 1
                    
                    # 3. Prepare data rows
                    rows_to_append = []
                    dt_now = datetime.now()
                    date_str = dt_now.strftime("%d-%b-%Y")
                    time_str = dt_now.strftime("%H:%M")
                    
                    for i in range(quantity):
                        code = f"{PREFIXES[category]}-{next_id_num + i:03d}"
                        # Columns: Date, Time, Contain/Description, Location, Code, QR Code
                        rows_to_append.append([date_str, time_str, description, final_location, code, qr_yes_no])
                    
                    # 4. Update Google Sheets
                    worksheet.append_rows(rows_to_append)
                    st.success(f"✅ Successfully added {quantity} item(s) to the '{category}' tab!")

                    # 5. Generate PDF
                    include_qr_bool = True if qr_yes_no == "Yes" else False
                    pdf_bytes = generate_label_pdf(category, description, final_location, quantity, next_id_num, include_qr_bool)
                    
                    # Save to session state so download button persists
                    st.session_state['pdf_ready'] = pdf_bytes
                    st.session_state['pdf_name'] = f"Trace_{category}_{next_id_num}.pdf"

                    # Clear cache so locations refresh
                    get_all_locations.clear()

                except Exception as e:
                    st.error(f"Error updating database: {e}")

    # Show download button if PDF is ready in session state
    if 'pdf_ready' in st.session_state:
        st.download_button(
            label="📄 Download Ready: Print Labels (PDF)",
            data=st.session_state['pdf_ready'],
            file_name=st.session_state['pdf_name'],
            mime="application/pdf",
            type="primary"
        )

# --- TAB 2: DASHBOARD ---
with tab2:
    st.subheader("Current Inventory Overview")
    selected_view_tab = st.selectbox("Select Tab to View", TABS, key="dash_view")
    
    try:
        data = spreadsheet.worksheet(selected_view_tab).get_all_records()
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
            st.metric(f"Total {selected_view_tab}", len(df))
        else:
            st.info(f"The '{selected_view_tab}' tab is empty.")
    except Exception as e:
        st.error(f"Could not load tab. Ensure the tab '{selected_view_tab}' exists and has row 1 headers. Error: {e}")

# --- TAB 3: SCANNER ---
with tab3:
    st.subheader("Mobile QR Scanner")
    st.info("Check items in and out via mobile camera.")

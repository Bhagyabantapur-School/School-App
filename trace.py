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

@st.cache_data(ttl=10) # Short cache so it refreshes quickly after adding data
def get_category_data(category):
    try:
        return spreadsheet.worksheet(category).get_all_records()
    except Exception:
        return []

@st.cache_data(ttl=30)
def get_all_locations():
    locations = set()
    for tab_name in TABS:
        records = get_category_data(tab_name)
        for r in records:
            if 'Location' in r and str(r['Location']).strip():
                locations.add(str(r['Location']).strip())
    if not locations:
        locations.add("GF001")
    return sorted(list(locations))

def generate_label_pdf_from_data(items, category):
    LABELS_PER_ROW, ROWS_PER_PAGE = 3, 7
    LABELS_PER_PAGE = LABELS_PER_ROW * ROWS_PER_PAGE
    A4_WIDTH, A4_HEIGHT = 210, 297
    MARGIN_X, MARGIN_Y = 10, 10
    LABEL_W = (A4_WIDTH - (2 * MARGIN_X)) / LABELS_PER_ROW
    LABEL_H = (A4_HEIGHT - (2 * MARGIN_Y)) / ROWS_PER_PAGE

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    with tempfile.TemporaryDirectory() as temp_dir:
        for i, item in enumerate(items):
            current_label_on_page = i % LABELS_PER_PAGE
            if i > 0 and current_label_on_page == 0:
                pdf.add_page()

            col = current_label_on_page % LABELS_PER_ROW
            row = current_label_on_page // LABELS_PER_ROW
            x = MARGIN_X + (col * LABEL_W)
            y = MARGIN_Y + (row * LABEL_H)

            unique_id = item.get('Code', '')
            description = str(item.get('Contain/Description', ''))
            location = str(item.get('Location', ''))
            include_qr = str(item.get('QR Code', 'No')).strip().lower() == 'yes'

            # Draw label boundary
            pdf.rect(x, y, LABEL_W, LABEL_H)
            
            short_desc = description[:22] + "..." if len(description) > 22 else description
            
            if include_qr:
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
                pdf.set_font("helvetica", "B", 12)
                pdf.text(x=x + 5, y=y + 10, text=f"ID: {unique_id}")
                pdf.set_font("helvetica", "", 10)
                pdf.text(x=x + 5, y=y + 18, text=f"Cat: {category}")
                pdf.text(x=x + 5, y=y + 26, text=f"Desc: {short_desc}")
                pdf.text(x=x + 5, y=y + 34, text=f"Loc: {location}")

    return bytes(pdf.output())

# ==========================================
# 4. APP LAYOUT & UI
# ==========================================
st.title("📦 trace.py")
st.markdown("### Physical Asset & Equipment Manager")

tab1, tab2, tab3, tab4 = st.tabs(["📝 Add Data", "🖨️ Print & Preview", "📊 Dashboard", "📷 Scanner"])

# --- TAB 1: ADD DATA ---
with tab1:
    st.subheader("Register New Asset")
    
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
            quantity = st.number_input("Quantity to Register", min_value=1, value=1, step=1)
            
        # Replaced the dual-purpose button with a database-only button
        submit_btn = st.form_submit_button("Save to Database")

    if submit_btn:
        final_location = new_location if loc_choice == "+ Add New Location (Type Below)" else loc_choice
        if not description or not final_location:
            st.error("Please fill in both Description and Location.")
        else:
            with st.spinner("Saving to Google Sheets..."):
                try:
                    worksheet = spreadsheet.worksheet(category)
                    records = worksheet.get_all_records()
                    next_id_num = len(records) + 1
                    
                    rows_to_append = []
                    dt_now = datetime.now()
                    date_str = dt_now.strftime("%d-%b-%Y")
                    time_str = dt_now.strftime("%H:%M")
                    
                    for i in range(quantity):
                        code = f"{PREFIXES[category]}-{next_id_num + i:03d}"
                        rows_to_append.append([date_str, time_str, description, final_location, code, qr_yes_no])
                    
                    worksheet.append_rows(rows_to_append)
                    st.success(f"✅ Successfully saved {quantity} item(s) to the '{category}' tab! Switch to the **Print & Preview** tab to generate your labels.")
                    
                    # Clear caches so the print tab immediately sees the new data
                    get_category_data.clear()
                    get_all_locations.clear()

                except Exception as e:
                    st.error(f"Error updating database: {e}")

# --- TAB 2: PRINT & PREVIEW (NEW) ---
with tab2:
    st.subheader("Print Labels")
    
    print_category = st.selectbox("Select Category to Print", TABS, key="print_cat")
    data = get_category_data(print_category)
    
    if data:
        st.markdown("**Select ID Range to Print:**")
        codes = [str(d.get('Code', '')) for d in data]
        
        # Select range of items to print
        col_start, col_end = st.columns(2)
        start_idx = col_start.selectbox("From ID:", range(len(codes)), format_func=lambda x: codes[x], index=max(0, len(codes)-1))
        end_idx = col_end.selectbox("To ID:", range(len(codes)), format_func=lambda x: codes[x], index=len(codes)-1)
        
        if start_idx <= end_idx:
            selected_items = data[start_idx : end_idx + 1]
            total_labels = len(selected_items)
            pages_needed = math.ceil(total_labels / 21)
            
            # Print Metrics
            st.markdown("---")
            m1, m2 = st.columns(2)
            m1.metric("Labels to Print", total_labels)
            m2.metric("A4 Pages Required", pages_needed)
            
            # PDF Generation Button
            if st.button("Generate PDF from Selection", type="primary"):
                with st.spinner("Building PDF..."):
                    pdf_bytes = generate_label_pdf_from_data(selected_items, print_category)
                    st.session_state['ready_pdf'] = pdf_bytes
                    st.session_state['ready_pdf_name'] = f"Labels_{print_category}_{codes[start_idx]}_to_{codes[end_idx]}.pdf"
            
            if 'ready_pdf' in st.session_state:
                st.download_button(
                    label="📄 Download Ready PDF",
                    data=st.session_state['ready_pdf'],
                    file_name=st.session_state['ready_pdf_name'],
                    mime="application/pdf"
                )

            st.markdown("---")
            st.markdown("### Visual Layout Preview")
            
            # Label Preview Engine (Draws 3x7 grids separated by page breaks)
            for page in range(pages_needed):
                st.markdown(f"**📄 Page {page + 1}**")
                page_items = selected_items[page * 21 : (page + 1) * 21]
                
                # Render 3 columns per row
                for i in range(0, len(page_items), 3):
                    cols = st.columns(3)
                    for j in range(3):
                        if i + j < len(page_items):
                            item = page_items[i + j]
                            with cols[j]:
                                # CSS style to make it look like a physical label card
                                st.info(
                                    f"**{item.get('Code', '')}** \n"
                                    f"*{item.get('Contain/Description', '')[:25]}*...  \n"
                                    f"📍 {item.get('Location', '')} | QR: {item.get('QR Code', 'No')}"
                                )
                st.divider() # Visual separation between A4 pages
        else:
            st.error("Start ID cannot be greater than End ID.")
    else:
        st.info(f"No data found in the '{print_category}' tab yet.")

# --- TAB 3: DASHBOARD ---
with tab3:
    st.subheader("Current Inventory Overview")
    selected_view_tab = st.selectbox("Select Tab to View", TABS, key="dash_view")
    
    dash_data = get_category_data(selected_view_tab)
    if dash_data:
        df = pd.DataFrame(dash_data)
        st.dataframe(df, use_container_width=True)
        st.metric(f"Total {selected_view_tab}", len(df))
    else:
        st.info(f"The '{selected_view_tab}' tab is empty.")

# --- TAB 4: SCANNER ---
with tab4:
    st.subheader("Mobile QR Scanner")
    st.info("Check items in and out via mobile camera.")

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
from PIL import Image

# ==========================================
# 1. PAGE CONFIGURATION & SETUP
# ==========================================
st.set_page_config(page_title="Trace Inventory", page_icon="📦", layout="wide")
# --- BACK BUTTON (STRICTLY REQUIRED) ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py")
st.write("---") 
# ---------------------------------------
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

# Increased TTL to 120 seconds to protect Google API quota
@st.cache_data(ttl=120)
def get_category_data(category):
    try:
        return spreadsheet.worksheet(category).get_all_records()
    except Exception:
        return []

@st.cache_data(ttl=120)
def get_all_inventory_data():
    all_data = []
    for tab in TABS:
        records = get_category_data(tab)
        for r in records:
            row_data = r.copy() 
            row_data['Category'] = tab 
            all_data.append(row_data)
    return list(reversed(all_data))

@st.cache_data(ttl=120)
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

def hex_to_rgb(hex_code):
    hex_code = str(hex_code).lstrip('#')
    if len(hex_code) != 6:
        return (255, 255, 255)
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))

def generate_label_pdf_from_mixed_data(items):
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
            category = item.get('Category', 'Unknown')
            description = str(item.get('Contain/Description', ''))
            location = str(item.get('Location', ''))
            include_qr = str(item.get('QR Code', 'No')).strip().lower() == 'yes'
            item_color = str(item.get('Color', '#FFFFFF'))

            # Draw outer label boundary
            pdf.rect(x, y, LABEL_W, LABEL_H)
            
            # --- COLOR CODING STRIP ---
            r, g, b = hex_to_rgb(item_color)
            pdf.set_fill_color(r, g, b)
            pdf.rect(x, y, 4, LABEL_H, style="F") 
            
            short_desc = description[:22] + "..." if len(description) > 22 else description
            
            if include_qr:
                qr_data = f"ID: {unique_id}\nType: {category}\nDesc: {description}\nLoc: {location}"
                qr = qrcode.make(qr_data)
                qr_path = os.path.join(temp_dir, f"qr_{i}.png")
                qr.save(qr_path)

                qr_size = LABEL_H - 15 
                pdf.image(qr_path, x=x + 6, y=y + 2, w=qr_size, h=qr_size)

                pdf.set_font("helvetica", size=8)
                text_x, text_y = x + qr_size + 8, y + 8
                pdf.text(x=text_x, y=text_y, text=f"ID: {unique_id}")
                pdf.text(x=text_x, y=text_y + 4, text=f"{category}")
                pdf.text(x=text_x, y=text_y + 8, text=f"{short_desc}")
                pdf.text(x=text_x, y=text_y + 12, text=f"Loc: {location[:15]}")
            else:
                pdf.set_font("helvetica", "B", 12)
                pdf.text(x=x + 8, y=y + 10, text=f"ID: {unique_id}")
                pdf.set_font("helvetica", "", 10)
                pdf.text(x=x + 8, y=y + 18, text=f"Cat: {category}")
                pdf.text(x=x + 8, y=y + 26, text=f"Desc: {short_desc}")
                pdf.text(x=x + 8, y=y + 34, text=f"Loc: {location}")

    return bytes(pdf.output())

# ==========================================
# 4. APP LAYOUT & UI
# ==========================================
st.title("📦 trace.py")
st.markdown("### Physical Asset & Equipment Manager")

tab1, tab2, tab3, tab4 = st.tabs(["📝 Add Data", "🖨️ Universal Print Studio", "📊 Dashboard", "📷 Scanner"])

# --- TAB 1: ADD DATA ---
with tab1:
    st.subheader("Register New Asset")
    
    # Camera Color Capture Engine
    detected_color_hex = "#FFFFFF" 
    
    with st.expander("🎨 Color Coding (Camera)"):
        st.write("Take a picture of the item. The app will automatically extract its average color for your label.")
        enable_camera = st.checkbox("Turn on Camera")
        
        if enable_camera:
            cam_pic = st.camera_input("Capture Color")
            if cam_pic is not None:
                img = Image.open(cam_pic).convert('RGB')
                img_1x1 = img.resize((1, 1))
                r, g, b = img_1x1.getpixel((0, 0))
                detected_color_hex = f"#{r:02x}{g:02x}{b:02x}"
                st.success(f"Color Detected: {detected_color_hex}")
    
    with st.form("data_entry_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            category = st.selectbox("Category (Select Tab)", TABS)
            description = st.text_input("Contain / Description", placeholder="e.g., DJI Mic Mini TX unit")
            
            existing_locations = get_all_locations()
            loc_choice = st.selectbox("Location", existing_locations + ["+ Add New Location (Type Below)"])
            new_location = st.text_input("New Location Name (if '+ Add New...' selected)", placeholder="e.g., School Office - Cabinet A")
            
        with col2:
            qr_yes_no = st.selectbox("Include QR Code on Label?", ["Yes", "No"])
            final_color = st.color_picker("Item Color (Adjust if needed)", value=detected_color_hex)
            quantity = st.number_input("Quantity to Register", min_value=1, value=1, step=1)
            
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
                        rows_to_append.append([date_str, time_str, description, final_location, code, qr_yes_no, final_color])
                    
                    worksheet.append_rows(rows_to_append)
                    st.success(f"✅ Successfully saved {quantity} item(s) to the '{category}' tab!")
                    
                    # Clear caches instantly so the print queue updates
                    get_category_data.clear()
                    get_all_inventory_data.clear()
                    get_all_locations.clear()

                except Exception as e:
                    st.error(f"Error updating database: {e}")

# --- TAB 2: UNIVERSAL PRINT STUDIO ---
with tab2:
    st.subheader("Universal Print Queue")
    all_items = get_all_inventory_data()
    
    if all_items:
        df_print = pd.DataFrame(all_items)
        df_print.insert(0, "🖨️ Print?", False)
        
        edited_df = st.data_editor(
            df_print,
            hide_index=True,
            use_container_width=True,
            disabled=df_print.columns.drop("🖨️ Print?").tolist(),
            height=400,
            column_config={
                "Color": st.column_config.TextColumn("Color")
            }
        )
        
        selected_df = edited_df[edited_df["🖨️ Print?"] == True]
        selected_items = selected_df.to_dict('records')
        total_labels = len(selected_items)
        
        if total_labels > 0:
            pages_needed = math.ceil(total_labels / 21)
            
            st.markdown("---")
            m1, m2 = st.columns(2)
            m1.metric("Labels Selected for Print", total_labels)
            m2.metric("A4 Pages Required", pages_needed)
            
            if st.button("Generate Mixed PDF", type="primary"):
                with st.spinner("Building your custom PDF..."):
                    pdf_bytes = generate_label_pdf_from_mixed_data(selected_items)
                    st.session_state['mixed_pdf'] = pdf_bytes
            
            if 'mixed_pdf' in st.session_state:
                st.download_button(
                    label="📄 Download Ready PDF",
                    data=st.session_state['mixed_pdf'],
                    file_name="Trace_Mixed_Batch_Labels.pdf",
                    mime="application/pdf"
                )

            st.markdown("---")
            st.markdown("### Visual Layout Preview")
            
            for page in range(pages_needed):
                st.markdown(f"**📄 Page {page + 1}**")
                page_items = selected_items[page * 21 : (page + 1) * 21]
                
                for i in range(0, len(page_items), 3):
                    cols = st.columns(3)
                    for j in range(3):
                        if i + j < len(page_items):
                            item = page_items[i + j]
                            col_hex = item.get('Color', '#FFFFFF')
                            with cols[j]:
                                st.markdown(
                                    f"""
                                    <div style="border: 1px solid #ddd; padding: 10px; border-radius: 5px; display: flex;">
                                        <div style="background-color: {col_hex}; width: 10px; height: 80px; margin-right: 10px; border-radius: 2px;"></div>
                                        <div>
                                            <strong>{item.get('Code', '')}</strong> ({item.get('Category', '')})<br>
                                            <em>{str(item.get('Contain/Description', ''))[:25]}...</em><br>
                                            📍 {item.get('Location', '')} | QR: {item.get('QR Code', 'No')}
                                        </div>
                                    </div>
                                    """, 
                                    unsafe_allow_html=True
                                )
                st.write("") 
    else:
        st.info("Your inventory is currently empty across all categories.")

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

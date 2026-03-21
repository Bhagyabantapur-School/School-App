import streamlit as st
import pandas as pd
import qrcode
import os
import math
from fpdf import FPDF
import tempfile
from datetime import datetime

# --- IMPORTS FOR GOOGLE SHEETS & DRIVE API ---
import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound
from google.auth.transport.requests import AuthorizedSession

# --- IMPORT THE SCANNER ---
try:
    from streamlit_qrcode_scanner import qrcode_scanner
except ImportError:
    st.error("Please add 'streamlit-qrcode-scanner' to your requirements.txt")
    st.stop()

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="BPS Digital - ID Generator", page_icon="🏫", layout="wide")

if 'attendance_log' not in st.session_state:
    st.session_state['attendance_log'] = pd.DataFrame(columns=['Time', 'Name', 'Roll', 'Class', 'Status', 'MDM'])

# --- 2. GOOGLE CREDENTIALS & DRIVE FETCHING ---
@st.cache_resource
def get_google_credentials():
    skey = dict(st.secrets["gcp_service_account"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
    return Credentials.from_service_account_info(skey, scopes=scopes)

@st.cache_resource
def init_gsheets():
    try:
        creds = get_google_credentials()
        gc = gspread.authorize(creds)
        return gc.open("BPS_Database")
    except Exception as e:
        st.error("⚠️ Google Sheets Connection Failed!")
        st.stop()

sh = init_gsheets()

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_secure_image_bytes(file_id):
    try:
        creds = get_google_credentials()
        authed_session = AuthorizedSession(creds)
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        response = authed_session.get(url)
        return response.content if response.status_code == 200 else None
    except:
        return None

def extract_drive_id(url):
    if pd.isna(url) or not isinstance(url, str): return None
    if "drive.google.com/file/d/" in url:
        return url.split("/d/")[1].split("/")[0]
    return None

# --- 3. DATA FETCHING ---
@st.cache_data(ttl=300) 
def fetch_sheet_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        return pd.DataFrame(ws.get_all_records())
    except:
        return pd.DataFrame()

def append_sheet_df(sheet_name, df):
    if df.empty: return
    try: 
        ws = sh.worksheet(sheet_name)
        ws.append_rows(df.fillna("").astype(str).values.tolist())
    except:
        pass

@st.cache_data(ttl=300)
def get_students():
    df = fetch_sheet_data("students_master")
    if df.empty: return pd.DataFrame()
    for col in ['Section', 'Photo_URL', 'Mobile', 'Roll']:
        if col not in df.columns: df[col] = 'N/A'
    df['Roll'] = df['Roll'].astype(str)
    return df

# --- 4. PDF GENERATOR ---
def generate_pdf(students_list, photo_dict):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    x_start, y_start, card_w, card_h, gap = 10, 10, 86, 54, 8
    col, row = 0, 0
    
    for student in students_list:
        x, y = x_start + (col * (card_w + gap)), y_start + (row * (card_h + gap))
        pdf.set_draw_color(0); pdf.rect(x, y, card_w, card_h)
        pdf.set_fill_color(0, 51, 153); pdf.rect(x, y, card_w, 11, 'F')
        
        pdf.set_font("Arial", 'B', 8); pdf.set_text_color(255)
        pdf.set_xy(x, y+3); pdf.cell(card_w, 5, "BHAGYABANTAPUR PRIMARY SCHOOL", 0, 1, 'C')
        
        pdf.set_text_color(0); pdf.set_font("Arial", 'B', 9)
        pdf.set_xy(x+25, y+15); pdf.cell(40, 5, str(student.get('Name', '')).upper())
        
        col += 1
        if col >= 2: col, row = 0, row + 1
        if row >= 5: pdf.add_page(); col, row = 0, 0
            
    return pdf.output(dest='S').encode('latin-1') if isinstance(pdf.output(dest='S'), str) else bytes(pdf.output(dest='S'))

# --- 5. APP LAYOUT ---
tabs = st.tabs(["🖨️ Generator", "📸 Scanner", "📂 Database Explorer"])

# ==========================================
# TAB 1: GENERATOR (Header Optimized)
# ==========================================
with tabs[0]:
    # Compact Header: Logo and Title side-by-side
    h_col1, h_col2 = st.columns([1, 5])
    with h_col1:
        if os.path.exists('logo.png'): st.image('logo.png', width=70)
    with h_col2:
        st.markdown("<h2 style='margin-top:10px;'>BPS Student ID Card Generator</h2>", unsafe_allow_html=True)
    
    st.divider()

    df_master = get_students()
    df_log = fetch_sheet_data("form_distribution_log")
    
    if not df_master.empty and not df_log.empty:
        # Clearance Logic
        df_log['Roll'] = df_log['Roll'].astype(str)
        merged = pd.merge(df_master, df_log, on=['Class', 'Section', 'Roll'], how='inner')
        
        def check_clearance(row):
            is_returned = str(row.get('Return Status', '')).strip() == 'Complete'
            has_old = any([str(row.get(f'Old {f}', '')).strip() not in ['','nan','None'] for f in ['Student Name', 'Father Name', 'Mobile Number']])
            is_corrected = str(row.get('Data Corrected', '')).strip() == 'Yes'
            return is_returned and (is_corrected if has_old else True)

        merged['Cleared'] = merged.apply(check_clearance, axis=1)
        ready_df = merged[merged['Cleared'] == True].copy()

        if not ready_df.empty:
            ready_df.insert(0, "Select", False)
            selected_df = st.data_editor(
                ready_df[['Select', 'Roll', 'Name', 'Class', 'Section']],
                hide_index=True, use_container_width=True
            )
            
            if st.button("Generate ID Cards", type="primary"):
                # PDF Generation logic here...
                st.info("Generating PDF for selected students...")
        else:
            st.warning("No students meet the clearance criteria (Form Complete + Data Corrected).")

# ==========================================
# TAB 2: SCANNER
# ==========================================
with tabs[1]:
    st.subheader("📸 MDM & Attendance Scanner")
    qr = qrcode_scanner(key='scanner')
    if qr: st.success(f"Scanned: {qr}")

# ==========================================
# TAB 3: DATABASE EXPLORER (New Request)
# ==========================================
with tabs[2]:
    st.subheader("📊 School Data & Verification Status")
    
    # 1. Prepare visual dataframe
    df_m = get_students()
    df_l = fetch_sheet_data("form_distribution_log")
    df_l['Roll'] = df_l['Roll'].astype(str)
    
    full_db = pd.merge(df_m, df_l, on=['Class', 'Section', 'Roll'], how='left')
    
    # Create Boolean-style status columns
    full_db['Photo Taken'] = full_db['Photo_URL'].apply(lambda x: "✅" if pd.notna(x) and "drive" in str(x) else "❌")
    full_db['Form Returned'] = full_db['Return Status'].apply(lambda x: "✅" if str(x) == "Complete" else "❌")
    full_db['Verified'] = full_db['Data Corrected'].apply(lambda x: "✅" if str(x) == "Yes" else "❌")
    
    # 2. Dropdown Filter
    filter_option = st.selectbox(
        "Filter Students By Status:",
        ["All Students", "Missing Photo", "Pending Form Return", "Ready for ID Card"]
    )
    
    display_df = full_db.copy()
    if filter_option == "Missing Photo":
        display_df = display_df[display_df['Photo Taken'] == "❌"]
    elif filter_option == "Pending Form Return":
        display_df = display_df[display_df['Form Returned'] == "❌"]
    elif filter_option == "Ready for ID Card":
        # Check clearance using the same logic as Tab 1
        def filter_ready(row):
            is_returned = str(row.get('Return Status', '')).strip() == 'Complete'
            is_corrected = str(row.get('Data Corrected', '')).strip() == 'Yes'
            return is_returned and is_corrected
        display_df = display_df[display_df.apply(filter_ready, axis=1)]

    # 3. Show Table
    st.dataframe(
        display_df[['Class', 'Roll', 'Name', 'Photo Taken', 'Form Returned', 'Verified']],
        use_container_width=True,
        hide_index=True
    )
    st.caption(f"Showing {len(display_df)} records.")

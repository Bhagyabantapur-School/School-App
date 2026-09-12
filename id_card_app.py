import streamlit as st
import streamlit.components.v1 as components

# --- BACK BUTTON ---
if st.button("⬅️ Back to BPS Home", type="secondary"):
    st.switch_page("bps_dashboard.py")
st.write("---") 
# -------------------
import pandas as pd
import qrcode
import os
import math
from fpdf import FPDF
import tempfile
from datetime import datetime, timedelta, timezone
import base64
import concurrent.futures
import time
import re

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

# Initialize Session States
if 'distribution_log' not in st.session_state:
    st.session_state['distribution_log'] = pd.DataFrame(columns=['Name', 'Roll', 'Class', 'BPS Code'])
if 'received_log' not in st.session_state:
    st.session_state['received_log'] = pd.DataFrame(columns=['Name', 'Roll', 'Class', 'BPS Code'])
if 'generated_pdf_data' not in st.session_state:
    st.session_state['generated_pdf_data'] = None
if 'pending_pdf_data' not in st.session_state:
    st.session_state['pending_pdf_data'] = None
if 'last_scanned_dist' not in st.session_state:
    st.session_state['last_scanned_dist'] = None
if 'last_scanned_recv' not in st.session_state:
    st.session_state['last_scanned_recv'] = None

# --- 2. GOOGLE CREDENTIALS & DRIVE CONNECTIONS ---
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
        st.error("⚠️ Google Sheets Connection Failed! Please check your Streamlit Secrets.")
        st.stop()

sh = init_gsheets()

# --- 3. HELPER FUNCTIONS ---

def get_ist_now():
    utc_now = datetime.now(timezone.utc)
    return utc_now + timedelta(hours=5, minutes=30)

def get_unified_key(df, name_col='Name'):
    if 'Class' not in df.columns: df['Class'] = ''
    if 'Roll' not in df.columns: df['Roll'] = ''
    if name_col not in df.columns: df[name_col] = ''
    
    c = df['Class'].astype(str).str.strip().str.upper()
    r = df['Roll'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    n = df[name_col].astype(str).str.strip().str.upper()
    return c + "_" + r + "_" + n

def get_photo_key(df):
    if 'Class' not in df.columns: df['Class'] = ''
    if 'Roll' not in df.columns: df['Roll'] = ''
    
    c = df['Class'].astype(str).str.strip().str.upper()
    r = df['Roll'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    return c + "_" + r

def play_beep():
    beep_html = """
    <script>
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) {
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gainNode = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        gainNode.gain.setValueAtTime(0.1, ctx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.1);
        osc.connect(gainNode);
        gainNode.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.1);
    }
    </script>
    """
    components.html(beep_html, height=0, width=0)

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
    if pd.isna(url) or not isinstance(url, str) or "drive.google.com" not in url: return None
    if "/d/" in url:
        return url.split("/d/")[1].split("/")[0]
    return None

def get_secure_photo_b64(url):
    if pd.isna(url) or not isinstance(url, str) or url.strip() == "": 
        return None
    did = extract_drive_id(url)
    if did:
        b = fetch_secure_image_bytes(did)
        if b: 
            return f"data:image/jpeg;base64,{base64.b64encode(b).decode()}"
    return None

@st.cache_data(ttl=60) 
def fetch_sheet_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        df.replace({'TRUE': True, 'FALSE': False, 'True': True, 'False': False}, inplace=True)
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def fetch_class_photo_status():
    sh_local = init_gsheets()
    taken_keys = set()
    try:
        for ws in sh_local.worksheets():
            title = ws.title.upper()
            if "- PHOTO" in title:
                title_clean = title.split("- PHOTO")[0].strip()
                parts = title_clean.split()
                if len(parts) >= 2 and parts[0] == "CLASS":
                    class_name = f"CLASS {parts[1].strip()}"
                else:
                    continue
                
                values = ws.get_all_values()
                for row in values:
                    if not row or len(row) < 2: continue
                    roll = str(row[0]).strip().replace('.0', '')
                    if not roll.isdigit(): continue 
                    
                    is_taken = False
                    for cell in row[1:]:
                        val_up = str(cell).strip().upper()
                        if val_up in ['TRUE', 'YES', 'TAKEN', 'Y'] or 'DRIVE.GOOGLE' in val_up:
                            is_taken = True
                            break
                        
                    if is_taken:
                        taken_keys.add(f"{class_name.upper()}_{roll}")
    except:
        pass
    return list(taken_keys)

def clear_sheet_cache():
    fetch_sheet_data.clear()
    fetch_class_photo_status.clear()

def clear_grid_states():
    for k in list(st.session_state.keys()):
        if k == "gen_editor" or k == "db_explorer_grid" or k.startswith("shop_grid_") or k.startswith("lot_grid_") or k == "distributed_grid":
            del st.session_state[k]

def append_sheet_df(sheet_name, df):
    if df.empty: return
    try: 
        ws = sh.worksheet(sheet_name)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
        ws.append_row(list(df.columns))
    
    df = df.fillna("").astype(str)
    try:
        ws.append_rows(df.values.tolist(), table_range="A1")
        clear_sheet_cache()
    except Exception as e:
        st.error(f"⚠️ Cloud sync error: {e}")

def batch_log_action(sheet_name, df, action):
    if df.empty: return
    try:
        log_ws = sh.worksheet(sheet_name)
    except WorksheetNotFound:
        log_ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=5)
        log_ws.append_row(["Date", "Class", "Roll", "Name", "Action"])
    
    rows = []
    now_str = get_ist_now().strftime("%d-%m-%Y %H:%M:%S")
    for _, r in df.iterrows():
        name_val = str(r.get('Name', r.get('Name_x', 'Unknown')))
        rows.append([now_str, str(r.get('Class', '')), str(r.get('Roll', '')), name_val, action])
    
    if rows:
        log_ws.append_rows(rows, table_range="A1")
        clear_sheet_cache()

def reset_generated_status():
    """Removes all 'Generated' logs from the id_card_log Google Sheet"""
    try:
        ws = sh.worksheet("id_card_log")
        data = ws.get_all_values()
        if len(data) > 1:
            headers = data[0]
            df = pd.DataFrame(data[1:], columns=headers)
            df_kept = df[df['Action'].astype(str).str.strip() != 'Generated']
            
            ws.clear()
            ws.append_row(headers)
            if not df_kept.empty:
                ws.append_rows(df_kept.astype(str).values.tolist(), table_range="A1")
        clear_sheet_cache()
    except WorksheetNotFound:
        pass
    except Exception as e:
        st.error(f"Error resetting database: {e}")

# --- 4. PDF GENERATORS ---

def generate_pdf(students_list, photo_dict, progress_bar=None):
    """Generates the Landscape Student ID Cards"""
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    
    x_start, y_start, card_w, card_h, gap = 10, 10, 86, 54, 8
    col, row = 0, 0
    total_cards = len(students_list)
    
    bg_img = None
    for ext in ['background.jpg', 'background.jpeg', 'background.png']:
        if os.path.exists(ext):
            bg_img = ext
            break
            
    for idx, student in enumerate(students_list):
        if progress_bar:
            progress_bar.progress(0.5 + (idx / total_cards) * 0.5, text=f"Drawing Card {idx + 1} of {total_cards}...")

        x = x_start + (col * (card_w + gap))
        y = y_start + (row * (card_h + gap))
        
        if bg_img:
            try: pdf.image(bg_img, x=x, y=y, w=card_w, h=card_h)
            except: pass 

        pdf.set_draw_color(0, 0, 0); pdf.set_line_width(0.3); pdf.rect(x, y, card_w, card_h)
        pdf.set_fill_color(0, 51, 153); pdf.rect(x, y, card_w, 11, 'F')
        
        if os.path.exists('logo.png'): 
            pdf.image('logo.png', x=x+68.5, y=y+1, w=16, h=16)
            
        pdf.set_font("Arial", '', 6)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x+2, y+2) 
        pdf.cell(66, 3, "Mob: 7908390822  |  ID CARD - SESSION 2026", 0, 1, 'C')
        
        pdf.set_font("Arial", 'B', 8.5)
        pdf.set_xy(x+2, y+6) 
        pdf.cell(66, 5, "BHAGYABANTAPUR PRIMARY SCHOOL", 0, 1, 'C')
        
        photo_x, photo_y, photo_w, photo_h = x+3, y+14, 18, 22
        student_id = str(student.get('Sl', 0)) + "_" + str(student.get('Roll', '0'))
        
        if student_id in photo_dict and photo_dict[student_id] is not None:
            temp_path = tempfile.mktemp(suffix=".jpg")
            with open(temp_path, "wb") as f: f.write(photo_dict[student_id])
            try:
                pdf.image(temp_path, x=photo_x, y=photo_y, w=photo_w, h=photo_h)
                pdf.set_draw_color(0, 0, 0); pdf.rect(photo_x, photo_y, photo_w, photo_h)
            except: pass
        else:
            pdf.set_draw_color(200); pdf.rect(photo_x, photo_y, photo_w, photo_h) 
            pdf.set_text_color(150); pdf.set_font("Arial", '', 5)
            pdf.set_xy(photo_x, y+20); pdf.cell(photo_w, 5, "NO PHOTO", 0, 0, 'C')
        
        pdf.set_text_color(0); detail_x, curr_y, line_h = x+24, y+14, 4
        pdf.set_font("Arial", 'B', 9); pdf.set_xy(detail_x, curr_y)
        pdf.cell(44, line_h, f"{student.get('Name', '')}".upper()[:25], 0, 1); curr_y += 4.5
        pdf.set_font("Arial", '', 7)
        
        raw_dob = str(student.get('DOB', '')).strip().split(" ")[0] 
        fmt_dob = raw_dob
        if raw_dob and raw_dob.lower() not in ['nan', 'none', 'nat']:
            try:
                if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$", raw_dob):
                    parts = re.split(r"[-/]", raw_dob)
                    fmt_dob = f"{int(parts[2]):02d}.{int(parts[1]):02d}.{parts[0]}"
                else:
                    dt = pd.to_datetime(raw_dob, dayfirst=True)
                    fmt_dob = dt.strftime('%d.%m.%Y')
            except:
                fmt_dob = raw_dob.replace('-', '.').replace('/', '.')

        for label, val in [
            ("Father", str(student.get('Father', ''))[:22]), 
            ("Mother", str(student.get('Mother', ''))[:22]), 
            ("Class", f"{student.get('Class', '')} | Sec: {student.get('Section', 'A')}"), 
            ("DOB", fmt_dob) 
        ]:
            pdf.set_xy(detail_x, curr_y); pdf.cell(44, line_h, f"{label}: {val}", 0, 1); curr_y += line_h
            
        pdf.set_xy(detail_x, curr_y); pdf.set_font("Arial", 'B', 7)
        pdf.cell(44, line_h, f"Mob: {student.get('Mobile', '')}", 0, 1)

        qr_data = str(student.get('BPS Code', '')).strip()
        qr = qrcode.make(qr_data); qr_path = tempfile.mktemp(suffix=".png"); qr.save(qr_path)
        pdf.image(qr_path, x=x+4.5, y=y+37, w=15, h=15)
        
        if os.path.exists('image_2.png'):
            try: pdf.image('image_2.png', x=x, y=y+44, w=card_w, h=10)
            except: pass

        wm_x, wm_y = x + 55, y + 42
        pdf.set_draw_color(220, 240, 255); pdf.set_line_width(0.4)
        pdf.line(wm_x, wm_y, wm_x, wm_y + 6); pdf.line(wm_x, wm_y, wm_x + 2, wm_y); pdf.line(wm_x, wm_y + 6, wm_x + 2, wm_y + 6)
        pdf.line(wm_x + 27, wm_y, wm_x + 27, wm_y + 6); pdf.line(wm_x + 25, wm_y, wm_x + 27, wm_y); pdf.line(wm_x + 25, wm_y + 6, wm_x + 27, wm_y + 6)
        pdf.set_text_color(210, 235, 255); pdf.set_font("Arial", 'B', 6); pdf.set_xy(wm_x, wm_y + 1); pdf.cell(27, 4, "BPS DIGITAL", 0, 0, 'C')

        if os.path.exists('signature.png'): 
            try: pdf.image('signature.png', x=x+58, y=y+40, w=22, h=8)
            except: pass
        
        pdf.set_text_color(0); pdf.set_font("Arial", 'I', 6); pdf.set_xy(x, y+49); pdf.cell(card_w-5, 3, "Sukhamay Kisku", 0, 1, 'R')
        pdf.set_font("Arial", '', 5); pdf.set_xy(x, y+51); pdf.cell(card_w-5, 2, "Head Teacher", 0, 0, 'R')
        
        col += 1
        if col >= 2: col, row = 0, row + 1
        if row >= 5: pdf.add_page(); col, row = 0, 0
            
    if progress_bar: progress_bar.progress(1.0, text="✅ PDF Rendering Complete!")
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        return pdf_output.encode('latin-1')
    return bytes(pdf_output)

def generate_pending_photos_pdf(df_pending):
    """Generates an A4 list of students who are present today but need photos."""
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Bhagyabantapur Primary School", ln=True, align='C')
    
    pdf.set_font("Arial", 'B', 12)
    current_date = get_ist_now().strftime("%d-%m-%Y")
    pdf.cell(0, 8, f"Pending Photos for Present Students - {current_date}", ln=True, align='C')
    
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, "Message to Teachers: Please send the following students for photo taking today.", ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_text_color(0, 0, 0)
    
    if df_pending.empty:
        pdf.set_font("Arial", '', 12)
        pdf.cell(0, 10, "No pending photos for present students today. Great job!", ln=True, align='C')
    else:
        grouped = df_pending.groupby(['Class', 'Section'])
        for (cls_name, sec_name), group in grouped:
            pdf.set_font("Arial", 'B', 11)
            pdf.set_fill_color(230, 230, 230)
            pdf.cell(0, 8, f" {cls_name} - Section {sec_name} ", border=1, ln=True, fill=True)
            
            pdf.set_font("Arial", '', 10)
            for _, row in group.iterrows():
                roll_text = f"Roll: {row.get('Roll', 'N/A')}"
                name_text = f"{row.get('Name', 'Unknown')}"
                pdf.cell(30, 7, roll_text, border='B')
                pdf.cell(0, 7, name_text, border='B', ln=True)
            pdf.ln(5)
            
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        return pdf_output.encode('latin-1')
    return bytes(pdf_output)

# --- 5. MAIN APP LAYOUT ---

col_title, col_refresh = st.columns([5, 1])
with col_title:
    st.markdown("<h2 style='margin-top:0px;'>🏫 BPS Digital System</h2>", unsafe_allow_html=True)
with col_refresh:
    st.write("") 
    if st.button("🔄 Refresh Cloud Data", use_container_width=True):
        clear_sheet_cache()
        st.rerun()

st.divider()

tabs = st.tabs(["🖨️ ID Generator", "📸 Scanner", "📂 Database Explorer", "📋 Pending Photos Today", "✂️ Shop Tracking", "✅ Distributed Cards"])

# ==========================================
# TAB 1: ID GENERATOR
# ==========================================
with tabs[0]:
    h_col1, h_col2 = st.columns([1, 5])
    with h_col1:
        if os.path.exists('logo.png'): st.image('logo.png', width=70)
    with h_col2:
        st.markdown("<h3 style='margin-top:10px;'>BPS Student ID Card Generator</h3>", unsafe_allow_html=True)
        
    if st.session_state['generated_pdf_data'] is not None:
        st.success("✅ Your PDF is ready! Click below to save it.")
        st.download_button(
            label="📥 Download ID Cards (PDF)", 
            data=st.session_state['generated_pdf_data'], 
            file_name=f"BPS_ID_Cards_{get_ist_now().strftime('%Y%m%d')}.pdf", 
            mime="application/pdf"
        )
        st.divider()

    df_master = fetch_sheet_data("students_master")
    df_log = fetch_sheet_data("form_distribution_log")
    df_id_log_raw = fetch_sheet_data("id_card_log")
    
    if not df_master.empty and not df_log.empty:
        merged = pd.merge(df_master, df_log, on=['Class', 'Section', 'Roll'], how='left', indicator=True, suffixes=('', '_log'))
        merged['Key'] = get_unified_key(merged, name_col='Name_x' if 'Name_x' in merged.columns else 'Name')
        
        if not df_id_log_raw.empty:
            df_id_log = df_id_log_raw.copy()
            df_id_log['Action'] = df_id_log['Action'].astype(str).str.strip()
            df_id_log['Key'] = get_unified_key(df_id_log)
            df_id_log['Parsed_Time'] = pd.to_datetime(df_id_log['Date'], format="%d-%m-%Y %H:%M:%S", errors='coerce')
            df_id_log['Parsed_Time'] = df_id_log['Parsed_Time'].fillna(pd.to_datetime(df_id_log['Date'], dayfirst=True, errors='coerce'))
            df_id_log = df_id_log.sort_values(by='Parsed_Time', ascending=True).reset_index(drop=True)
            
            gen_keys = df_id_log[df_id_log['Action'] == 'Generated']['Key'].unique().tolist()
        else:
            df_id_log = pd.DataFrame()
            gen_keys = []
            
        merged['Generated'] = merged['Key'].isin(gen_keys)

        def format_grid_dob(raw_dob):
            raw_dob = str(raw_dob).strip().split(" ")[0]
            fmt_dob = raw_dob
            if raw_dob and raw_dob.lower() not in ['nan', 'none', 'nat', '']:
                try:
                    if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$", raw_dob):
                        parts = re.split(r"[-/]", raw_dob)
                        fmt_dob = f"{int(parts[2]):02d}.{int(parts[1]):02d}.{parts[0]}"
                    else:
                        dt = pd.to_datetime(raw_dob, dayfirst=True)
                        fmt_dob = dt.strftime('%d.%m.%Y')
                except:
                    fmt_dob = raw_dob.replace('-', '.').replace('/', '.')
            return fmt_dob

        # ✨ NEW: Lot Reprint Section
        if not df_id_log.empty:
            gen_log_only = df_id_log[df_id_log['Action'] == 'Generated'].copy()
            if not gen_log_only.empty:
                gen_log_only['Date_Only'] = gen_log_only['Date'].apply(lambda x: str(x).split(' ')[0] if pd.notna(x) and str(x).strip() != 'nan' else '')
                latest_gen_reprint = gen_log_only.drop_duplicates(subset=['Key'], keep='last').copy()
                
                unique_gen_dates_reprint = sorted(latest_gen_reprint['Date_Only'].unique(), key=lambda d: pd.to_datetime(d, dayfirst=True))
                lot_mapping_reprint = {d: f"Lot {i+1}" for i, d in enumerate(unique_gen_dates_reprint)}
                
                lot_options = []
                lot_to_keys = {}
                for d in unique_gen_dates_reprint:
                    lot_name = lot_mapping_reprint[d]
                    keys_in_lot = latest_gen_reprint[latest_gen_reprint['Date_Only'] == d]['Key'].tolist()
                    lot_label = f"📦 {lot_name} (Generated: {d}) - {len(keys_in_lot)} Cards"
                    lot_options.append(lot_label)
                    lot_to_keys[lot_label] = keys_in_lot
                
                st.markdown("##### 📦 Reprint an Existing Lot")
                col_l1, col_l2 = st.columns([3, 1])
                with col_l1:
                    selected_lot_to_reprint = st.selectbox("Select a previously generated Lot to re-download:", ["-- Select Lot --"] + list(reversed(lot_options)))
                with col_l2:
                    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
                    reprint_btn = st.button("🖨️ Generate PDF for Lot", use_container_width=True)
                    
                if reprint_btn and selected_lot_to_reprint != "-- Select Lot --":
                    target_keys = lot_to_keys[selected_lot_to_reprint]
                    selected_students = merged[merged['Key'].isin(target_keys)].copy()
                    
                    if not selected_students.empty:
                        if 'Section' not in selected_students.columns: selected_students['Section'] = 'A'
                        selected_students['Section'] = selected_students['Section'].fillna('A').astype(str)
                        selected_students['DOB'] = selected_students['DOB'].apply(format_grid_dob)
                        
                        st.session_state['generated_pdf_data'] = None 
                        photo_dict = {}
                        my_bar = st.progress(0, text="Starting secure fetch for Lot Reprint...")
                        
                        num_students = len(selected_students)
                        for idx, (index, student) in enumerate(selected_students.iterrows()):
                            sid = str(student.get('Sl', index)) + "_" + str(student.get('Roll', '0'))
                            photo_url = str(student.get('Photo_URL', ''))
                            drive_id = extract_drive_id(photo_url)
                            if drive_id:
                                img_bytes = fetch_secure_image_bytes(drive_id)
                                if img_bytes: photo_dict[sid] = img_bytes
                            my_bar.progress((idx + 1) / num_students * 0.5, text=f"Fetching photo {idx + 1} of {num_students}...")
                        
                        pdf_bytes = generate_pdf(selected_students.to_dict('records'), photo_dict, progress_bar=my_bar)
                        # We intentionally DO NOT batch_log_action here so it doesn't change the Lot's historical date
                        st.session_state['generated_pdf_data'] = pdf_bytes
                        clear_grid_states()
                        st.balloons()
                        st.rerun()
                st.divider()

        st.markdown("##### 🎛️ Generate NEW Cards (Filters)")
        col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns([1.3, 1.3, 1.3, 1.3, 1.2])
        with col_f1: hide_generated = st.checkbox("Hide Already Generated", value=True)
        with col_f2: require_photo = st.checkbox("Require Uploaded Photo", value=True)
        with col_f3: require_form = st.checkbox("Require 'Complete' Form", value=True)
        with col_f4: missing_form_only = st.checkbox("Missing Form Log Only", value=False)
        with col_f5:
            if st.button("⚠️ Reset All Generated", use_container_width=True, help="Moves all students back to the starting queue."):
                with st.spinner("Resetting database..."):
                    reset_generated_status()
                clear_grid_states()
                st.success("Success! List reset.")
                st.rerun()

        def is_ready_to_print(row):
            has_photo = pd.notna(row.get('Photo_URL')) and str(row.get('Photo_URL')).strip() != ""
            is_returned = str(row.get('Return Status', '')).strip() == 'Complete'
            has_corr = any([str(row.get(f'Old {f}', '')).strip() not in ['','nan','None'] for f in ['Student Name', 'Father Name', 'Mobile Number']])
            is_verified = str(row.get('Data Corrected', '')).strip() == 'Yes'
            form_ok = is_returned and (is_verified if has_corr else True)
            is_missing = (row['_merge'] == 'left_only')
            
            if missing_form_only:
                if not is_missing: return False
                if require_photo and not has_photo: return False
                return True

            if require_photo and not has_photo: return False
            if require_form and not form_ok: return False
            return True

        merged['Ready'] = merged.apply(is_ready_to_print, axis=1)
        
        if hide_generated: print_ready = merged[(merged['Ready'] == True) & (merged['Generated'] == False)].copy()
        else: print_ready = merged[merged['Ready'] == True].copy()

        if not print_ready.empty:
            print_ready = print_ready.reset_index(drop=True)
            print_ready.insert(0, "Select", False)
            
            if 'Section' not in print_ready.columns: print_ready['Section'] = 'A'
            print_ready['Section'] = print_ready['Section'].fillna('A').astype(str)
            
            for c in ['Father', 'Mother', 'DOB', 'Mobile']:
                if c not in print_ready.columns: print_ready[c] = ""
            
            print_ready['DOB'] = print_ready['DOB'].apply(format_grid_dob)

            def get_valid_photo(row):
                thumb = str(row.get('Thumb_URL', '')).strip()
                photo = str(row.get('Photo_URL', '')).strip()
                if thumb and thumb.lower() not in ['nan', 'none']: return thumb
                if photo and photo.lower() not in ['nan', 'none']: return photo
                return ""

            print_ready['Image_Target'] = print_ready.apply(get_valid_photo, axis=1)

            with st.spinner("Loading stamp size photos for visual verification..."):
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as exe:
                    print_ready['Photo'] = list(exe.map(get_secure_photo_b64, print_ready['Image_Target'].tolist()))

            st.write(f"Showing **{len(print_ready)}** students ready for new printing.")
            
            unique_groups = (print_ready['Class'].astype(str) + "_" + print_ready['Section'].astype(str)).unique().tolist()
            color_map = {grp: '#f4f6f9' if i % 2 == 0 else '#ffffff' for i, grp in enumerate(unique_groups)}

            def gen_row_style(row):
                grp = str(row['Class']) + "_" + str(row['Section'])
                bg = color_map.get(grp, '#ffffff')
                return [f'background-color: {bg}' for _ in row]

            show_cols_gen = ['Select', 'Photo', 'Name', 'Father', 'Mother', 'Class', 'Section', 'DOB', 'Mobile', 'Generated']
            styled_gen_df = print_ready[show_cols_gen].style.apply(gen_row_style, axis=1)
            
            edited_df = st.data_editor(
                styled_gen_df,
                hide_index=True, use_container_width=True, key="gen_editor",
                disabled=['Photo', 'Name', 'Father', 'Mother', 'Class', 'Section', 'DOB', 'Mobile', 'Generated'],
                column_config={
                    "Select": st.column_config.CheckboxColumn("Select", default=False),
                    "Photo": st.column_config.ImageColumn("Stamp Size Photo", width="medium")
                }
            )
            
            selected_students = print_ready.loc[edited_df[edited_df["Select"] == True].index].copy()

            if not selected_students.empty:
                num_students = len(selected_students)
                pages_needed = math.ceil(num_students / 10)
                st.divider()
                st.info(f"🖨️ **Print Summary:** You selected **{num_students}** students. Requires **{pages_needed}** A4 page(s).")
                
                if st.button("Generate Secure PDF", type="primary"):
                    st.session_state['generated_pdf_data'] = None 
                    photo_dict = {}
                    my_bar = st.progress(0, text="Starting secure fetch...")
                    for idx, (index, student) in enumerate(selected_students.iterrows()):
                        sid = str(student.get('Sl', index)) + "_" + str(student.get('Roll', '0'))
                        photo_url = str(student.get('Photo_URL', ''))
                        drive_id = extract_drive_id(photo_url)
                        if drive_id:
                            img_bytes = fetch_secure_image_bytes(drive_id)
                            if img_bytes: photo_dict[sid] = img_bytes
                        my_bar.progress((idx + 1) / num_students * 0.5, text=f"Fetching photo {idx + 1} of {num_students}...")
                    
                    pdf_bytes = generate_pdf(selected_students.to_dict('records'), photo_dict, progress_bar=my_bar)
                    batch_log_action("id_card_log", selected_students, "Generated")
                    st.session_state['generated_pdf_data'] = pdf_bytes
                    clear_grid_states()
                    st.balloons()
                    st.rerun()
        else:
            st.success("No students found in this stage. Check the filters above or scan new forms!")
    else:
        st.info("No students found in the main database.")

# ==========================================
# TAB 2: SCANNER (DISTRIBUTION ONLY)
# ==========================================
with tabs[1]:
    st.markdown('<h3 style="text-align:center; color:#28a745;">📸 Scan ID Card for Distribution</h3>', unsafe_allow_html=True)
    st.write("Scan ID cards as you hand them to students to officially mark them as Distributed!")
    
    qr_code = qrcode_scanner(key='distribution_scanner')
    
    if qr_code and qr_code != st.session_state.get('last_scanned_dist'):
        scanned_code = str(qr_code).strip().upper()
        m_df = fetch_sheet_data("students_master")
        
        s_match = m_df[m_df['BPS Code'].astype(str).str.strip().str.upper() == scanned_code]
        
        if not s_match.empty:
            student_name = str(s_match.iloc[0]['Name']).strip()
            student_class = str(s_match.iloc[0]['Class']).strip()
            student_roll = str(s_match.iloc[0]['Roll']).strip()

            existing = st.session_state['distribution_log'][
                (st.session_state['distribution_log']['Name'] == student_name) & 
                (st.session_state['distribution_log']['Class'] == student_class) &
                (st.session_state['distribution_log']['Roll'] == student_roll)
            ]
            
            if not existing.empty:
                st.warning(f"⚠️ {student_name} is already in your distribution scan list!")
                st.session_state['last_scanned_dist'] = qr_code
            else:
                new_entry = pd.DataFrame([{
                    'Name': student_name, 'Roll': student_roll, 
                    'Class': student_class, 'BPS Code': scanned_code
                }])
                st.session_state['distribution_log'] = pd.concat([st.session_state['distribution_log'], new_entry], ignore_index=True)
                st.session_state['last_scanned_dist'] = qr_code
                play_beep() 
                st.success(f"✅ **{student_name}** successfully scanned for distribution!")
        else:
            st.error("Invalid QR Code or BPS Code not found in database. Please scan a valid BPS ID Card.")
            st.session_state['last_scanned_dist'] = qr_code

    st.divider()
    
    st.markdown("### 🎁 Scanned Cards for Distribution")
    if not st.session_state['distribution_log'].empty:
        st.dataframe(st.session_state['distribution_log'], use_container_width=True)
        
        if st.button("🎁 Mark Scanned Cards as 'Distributed'", type="primary", use_container_width=True):
            batch_log_action("id_card_log", st.session_state['distribution_log'], "Distributed")
            st.success(f"✅ Successfully marked {len(st.session_state['distribution_log'])} cards as Distributed in the database!")
            st.session_state['distribution_log'] = pd.DataFrame(columns=['Name', 'Roll', 'Class', 'BPS Code'])
            clear_grid_states()
            time.sleep(1.5)
            st.rerun()
            
        if st.button("🗑️ Clear Scan List"):
            st.session_state['distribution_log'] = pd.DataFrame(columns=['Name', 'Roll', 'Class', 'BPS Code'])
            st.rerun()
    else:
        st.info("Scan ID cards above to add them to your distribution list.")

# ==========================================
# TAB 3: DATABASE EXPLORER & SUMMARIES
# ==========================================
with tabs[2]:
    st.subheader("📂 ID Lifecycle & Media Tracker")
    
    df_m = fetch_sheet_data("students_master")
    df_l = fetch_sheet_data("form_distribution_log")
    df_photo = fetch_sheet_data("photo_log")
    df_id_log_raw = fetch_sheet_data("id_card_log")
    
    if not df_id_log_raw.empty:
        df_id_log = df_id_log_raw.copy()
        df_id_log['Action'] = df_id_log['Action'].astype(str).str.strip()
        df_id_log['Key'] = get_unified_key(df_id_log)
        
        df_id_log['Parsed_Time'] = pd.to_datetime(df_id_log['Date'], format="%d-%m-%Y %H:%M:%S", errors='coerce')
        df_id_log['Parsed_Time'] = df_id_log['Parsed_Time'].fillna(pd.to_datetime(df_id_log['Date'], dayfirst=True, errors='coerce'))
        df_id_log = df_id_log.sort_values(by='Parsed_Time', ascending=True).reset_index(drop=True)
    else:
        df_id_log = pd.DataFrame()

    if not df_m.empty and not df_l.empty:
        explorer_db = pd.merge(df_m, df_l, on=['Class', 'Section', 'Roll'], how='left', suffixes=('', '_log'))
        explorer_db['Key'] = get_unified_key(explorer_db, name_col='Name_x' if 'Name_x' in explorer_db.columns else 'Name')
        explorer_db['Photo_Key'] = get_photo_key(explorer_db)
        
        for c in ['Father', 'Mother', 'DOB', 'Mobile']:
            if c not in explorer_db.columns: explorer_db[c] = ""
            
        photo_keys, gen_keys, dist_keys = [], [], []
        
        if not df_photo.empty:
            df_photo['Photo_Key'] = get_photo_key(df_photo)
            latest_photo = df_photo.drop_duplicates(subset=['Photo_Key'], keep='last')
            photo_keys = latest_photo[latest_photo['Action'] == 'Taken']['Photo_Key'].tolist()
            
        if not df_id_log.empty:
            gen_keys = df_id_log[df_id_log['Action'] == 'Generated']['Key'].unique().tolist()
            dist_df = df_id_log[df_id_log['Action'].isin(['Distributed', 'Undistributed'])]
            if not dist_df.empty:
                latest_dist = dist_df.drop_duplicates(subset=['Key'], keep='last')
                dist_keys = latest_dist[latest_dist['Action'] == 'Distributed']['Key'].tolist()

        class_photo_keys = fetch_class_photo_status()
        photo_keys = list(set(photo_keys + class_photo_keys))

        explorer_db['Photo_URL_Raw'] = explorer_db['Photo_URL']
        if 'Thumb_URL' in explorer_db.columns:
            explorer_db['Thumb_URL_Raw'] = explorer_db['Thumb_URL']
        else:
            explorer_db['Thumb_URL_Raw'] = ""

        explorer_db['Photo_URL'] = explorer_db['Photo_URL'].apply(lambda x: True if pd.notna(x) and str(x).strip() != "" else False)
        explorer_db['Thumb_URL'] = explorer_db['Thumb_URL'].apply(lambda x: True if pd.notna(x) and str(x).strip() != "" else False) if 'Thumb_URL' in explorer_db.columns else False

        explorer_db['Form_OK'] = explorer_db['Return Status'].apply(lambda x: True if str(x) == "Complete" else False)
        explorer_db['Verified'] = explorer_db['Data Corrected'].apply(lambda x: True if str(x) == "Yes" else False)
        
        explorer_db['Photo Taken'] = explorer_db['Photo_Key'].isin(photo_keys)
        explorer_db['Generated'] = explorer_db['Key'].isin(gen_keys)
        explorer_db['Distributed'] = explorer_db['Key'].isin(dist_keys)
        
        explorer_db['Already_Photo'] = explorer_db['Photo Taken']
        explorer_db['Already_Dist'] = explorer_db['Distributed']

        cat_filter = st.selectbox("Filter Tracking View:", [
            "All Students", 
            "Missing Photo Link", 
            "Form/Data Pending", 
            "Ready to Print", 
            "Printed (Needs Distribution)"
        ])
        
        filtered_view = explorer_db.copy()
        if cat_filter == "Missing Photo Link":
            filtered_view = filtered_view[filtered_view['Photo_URL'] == False]
        elif cat_filter == "Form/Data Pending":
            filtered_view = filtered_view[(filtered_view['Form_OK'] == False) | (filtered_view['Verified'] == False)]
        elif cat_filter == "Ready to Print":
            filtered_view = filtered_view[(filtered_view['Photo_URL'] == True) & (filtered_view['Form_OK'] == True) & (filtered_view['Verified'] == True) & (filtered_view['Generated'] == False)]
        elif cat_filter == "Printed (Needs Distribution)":
            filtered_view = filtered_view[(filtered_view['Generated'] == True) & (filtered_view['Distributed'] == False)]

        st.write("---")
        metrics_container = st.container()

        filtered_view = filtered_view.reset_index(drop=True)
        if 'Section' not in filtered_view.columns: filtered_view['Section'] = 'A'
        filtered_view['Section'] = filtered_view['Section'].fillna('A').astype(str)

        unique_groups_db = (filtered_view['Class'].astype(str) + "_" + filtered_view['Section'].astype(str)).unique().tolist()
        color_map_db = {grp: '#f4f6f9' if i % 2 == 0 else '#ffffff' for i, grp in enumerate(unique_groups_db)}

        def db_row_style(row):
            grp = str(row['Class']) + "_" + str(row['Section'])
            bg = color_map_db.get(grp, '#ffffff')
            return [f'background-color: {bg}' for _ in row]

        cols_to_show = ['Photo Taken', 'Photo_URL', 'Thumb_URL', 'Name', 'Class', 'Section', 'Roll', 'Form_OK', 'Verified', 'Generated', 'Distributed']
        styled_df = filtered_view[cols_to_show + ['Already_Photo', 'Already_Dist']].style.apply(db_row_style, axis=1)

        final_ed = st.data_editor(
            styled_df,
            column_order=cols_to_show, 
            column_config={
                "Photo Taken": st.column_config.CheckboxColumn("Photo Taken"),
                "Photo_URL": st.column_config.CheckboxColumn("Photo Link", disabled=True),
                "Thumb_URL": st.column_config.CheckboxColumn("Thumb Link", disabled=True),
                "Form_OK": st.column_config.CheckboxColumn("Form OK?", disabled=True),
                "Verified": st.column_config.CheckboxColumn("Verified?", disabled=True),
                "Generated": st.column_config.CheckboxColumn("Generated?", disabled=True),
                "Distributed": st.column_config.CheckboxColumn("Distributed?"),
            },
            disabled=['Photo_URL', 'Thumb_URL', 'Name', 'Class', 'Section', 'Roll', 'Form_OK', 'Verified', 'Generated'],
            hide_index=True, use_container_width=True, key="db_explorer_grid"
        )

        with metrics_container:
            st.markdown("##### 📊 Live Column Counts")
            ready_mask = (final_ed['Photo_URL'] == True) & (final_ed['Form_OK'] == True) & (final_ed['Verified'] == True) & (final_ed['Generated'] == False)
            c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
            c1.metric("📸 Photo Taken", int(final_ed['Photo Taken'].sum()))
            c2.metric("🔗 Photo Link", int(final_ed['Photo_URL'].sum()))
            c3.metric("🖼️ Thumb Link", int(final_ed['Thumb_URL'].sum()))
            c4.metric("📝 Form OK", int(final_ed['Form_OK'].sum()))
            c5.metric("✅ Verified", int(final_ed['Verified'].sum()))
            c6.metric("🚀 Ready to Gen", int(ready_mask.sum()))
            c7.metric("🖨️ Generated", int(final_ed['Generated'].sum()))
            c8.metric("🎁 Distributed", int(final_ed['Distributed'].sum()))
            st.write("") 

        # 📅 Date-wise Action Summary
        st.write("---")
        st.markdown("##### 📅 Date-wise Action Summary")
        if not df_id_log.empty:
            summary_log_action = df_id_log.copy()
            summary_log_action['Date_Only'] = summary_log_action['Date'].apply(lambda x: str(x).split(' ')[0] if pd.notna(x) and str(x).strip() != 'nan' else '')
            
            target_actions = ['Generated', 'Sent to Shop', 'Received from Shop', 'Distributed']
            summary_log_action = summary_log_action[summary_log_action['Action'].isin(target_actions)]
            
            if not summary_log_action.empty:
                pivot_df = pd.pivot_table(summary_log_action, index='Date_Only', columns='Action', aggfunc='size', fill_value=0).reset_index()
                for act in target_actions:
                    if act not in pivot_df.columns: pivot_df[act] = 0
                pivot_df = pivot_df[['Date_Only'] + target_actions]
                pivot_df['Parsed'] = pd.to_datetime(pivot_df['Date_Only'], dayfirst=True, errors='coerce')
                pivot_df = pivot_df.sort_values('Parsed', ascending=False).drop(columns=['Parsed']).reset_index(drop=True)
                pivot_df.rename(columns={'Date_Only': 'Date'}, inplace=True)
                
                color_map_sum = {d: '#f4f6f9' if i % 2 == 0 else '#ffffff' for i, d in enumerate(pivot_df['Date'])}
                def sum_row_style(row):
                    bg = color_map_sum.get(row['Date'], '#ffffff')
                    return [f'background-color: {bg}' for _ in row]
                    
                st.dataframe(pivot_df.style.apply(sum_row_style, axis=1), hide_index=True, use_container_width=True)
            else:
                st.info("No action logs found to summarize yet.")
        else:
            st.info("ID card log is empty.")

        # 📦 Lot-wise Distribution Summary
        st.write("---")
        st.markdown("##### 📦 Lot-wise Action Summary (Based on 'Generated' Date)")
        if not df_id_log.empty:
            gen_log = df_id_log[df_id_log['Action'] == 'Generated'].copy()
            if not gen_log.empty:
                gen_log['Date_Only'] = gen_log['Date'].apply(lambda x: str(x).split(' ')[0] if pd.notna(x) and str(x).strip() != 'nan' else '')
                
                latest_gen = gen_log.drop_duplicates(subset=['Key'], keep='last').copy()
                unique_gen_dates = sorted(latest_gen['Date_Only'].unique(), key=lambda d: pd.to_datetime(d, dayfirst=True))
                lot_mapping = {d: f"Lot {i+1}" for i, d in enumerate(unique_gen_dates)}
                latest_gen['Lot'] = latest_gen['Date_Only'].map(lot_mapping)
                
                def get_stage_agg(keys, action):
                    stage_log = df_id_log[(df_id_log['Key'].isin(keys)) & (df_id_log['Action'] == action)].copy()
                    if stage_log.empty: return ""
                    latest_stage = stage_log.drop_duplicates(subset=['Key'], keep='last').copy()
                    latest_stage['Date_Only'] = latest_stage['Date'].apply(lambda x: str(x).split(' ')[0])
                    counts = latest_stage['Date_Only'].value_counts()
                    sorted_dates = sorted(counts.index, key=lambda d: pd.to_datetime(d, dayfirst=True))
                    return " , ".join([f"{d} ({counts[d]})" for d in sorted_dates])
                
                summary_data = []
                for d in unique_gen_dates:
                    lot_name = lot_mapping[d]
                    keys_in_lot = latest_gen[latest_gen['Date_Only'] == d]['Key'].tolist()
                    qty = len(keys_in_lot)
                    
                    gen_str = f"{d} ({qty})"
                    sent_str = get_stage_agg(keys_in_lot, "Sent to Shop")
                    recv_str = get_stage_agg(keys_in_lot, "Received from Shop")
                    
                    dist_qty = sum([1 for k in keys_in_lot if k in dist_keys])
                    
                    dist_str = ""
                    if dist_qty > 0:
                        dist_logs = df_id_log[(df_id_log['Key'].isin(keys_in_lot)) & (df_id_log['Action'] == 'Distributed')].copy()
                        dist_logs = dist_logs[dist_logs['Key'].isin(dist_keys)].drop_duplicates(subset=['Key'], keep='last')
                        if not dist_logs.empty:
                            dist_logs['Date_Only'] = dist_logs['Date'].apply(lambda x: str(x).split(' ')[0])
                            counts = dist_logs['Date_Only'].value_counts()
                            sorted_d_dates = sorted(counts.index, key=lambda dt: pd.to_datetime(dt, dayfirst=True))
                            dist_str = " , ".join([f"{dt} ({counts[dt]})" for dt in sorted_d_dates])
                    
                    remain = qty - dist_qty
                    
                    summary_data.append({
                        "Lot Number": lot_name,
                        "Quantity": qty,
                        "Generated": gen_str,
                        "Sent to Shop": sent_str,
                        "Received from Shop": recv_str,
                        "Distributed": dist_str,
                        "Remain": remain
                    })
                
                lot_summary_df = pd.DataFrame(summary_data)
                
                lot_summary_df['SortVal'] = lot_summary_df['Lot Number'].apply(lambda x: int(x.replace('Lot ', '')))
                lot_summary_df = lot_summary_df.sort_values('SortVal', ascending=False).drop(columns=['SortVal']).reset_index(drop=True)
                
                color_map_lot = {l: '#f4f6f9' if i % 2 == 0 else '#ffffff' for i, l in enumerate(lot_summary_df['Lot Number'])}
                def lot_row_style(row):
                    bg = color_map_lot.get(row['Lot Number'], '#ffffff')
                    return [f'background-color: {bg}' for _ in row]
                    
                st.dataframe(lot_summary_df.style.apply(lot_row_style, axis=1), hide_index=True, use_container_width=True)
                
                st.markdown("##### 👥 Students Grouped by Lot")
                
                latest_overall = df_id_log.drop_duplicates(subset=['Key'], keep='last')
                status_dict = dict(zip(latest_overall['Key'], latest_overall['Action']))

                def get_valid_photo_tab3(row):
                    thumb = str(row.get('Thumb_URL_Raw', '')).strip()
                    photo = str(row.get('Photo_URL_Raw', '')).strip()
                    if thumb and thumb.lower() not in ['nan', 'none', 'false']: return thumb
                    if photo and photo.lower() not in ['nan', 'none', 'false']: return photo
                    return ""
                
                def format_lot_dob(raw_dob):
                    raw_dob = str(raw_dob).strip().split(" ")[0]
                    fmt_dob = raw_dob
                    if raw_dob and raw_dob.lower() not in ['nan', 'none', 'nat', '']:
                        try:
                            if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$", raw_dob):
                                parts = re.split(r"[-/]", raw_dob)
                                fmt_dob = f"{int(parts[2]):02d}.{int(parts[1]):02d}.{parts[0]}"
                            else:
                                dt = pd.to_datetime(raw_dob, dayfirst=True)
                                fmt_dob = dt.strftime('%d.%m.%Y')
                        except:
                            fmt_dob = raw_dob.replace('-', '.').replace('/', '.')
                    return fmt_dob

                for idx, row in lot_summary_df.iterrows():
                    lot_name = row['Lot Number']
                    gen_date = row['Generated'].split(' ')[0]
                    qty = row['Quantity']
                    remain = row['Remain']
                    
                    with st.expander(f"📦 {lot_name} (Generated: {gen_date}) | Total: {qty} | Remaining: {remain}"):
                        keys_in_lot = latest_gen[latest_gen['Lot'] == lot_name]['Key'].tolist()
                        lot_students = explorer_db[explorer_db['Key'].isin(keys_in_lot)].copy()
                        
                        if not lot_students.empty:
                            lot_students['Current Status'] = lot_students['Key'].map(status_dict).fillna('Generated')
                            lot_students['Image_Target'] = lot_students.apply(get_valid_photo_tab3, axis=1)
                            lot_students['DOB'] = lot_students['DOB'].apply(format_lot_dob)
                            
                            if 'Name_x' in lot_students.columns and 'Name' not in lot_students.columns:
                                lot_students['Name'] = lot_students['Name_x']

                            with st.spinner(f"Loading photos for {lot_name}..."):
                                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as exe:
                                    lot_students['Photo'] = list(exe.map(get_secure_photo_b64, lot_students['Image_Target'].tolist()))

                            show_cols = ['Photo', 'Name', 'Father', 'Mother', 'Class', 'Section', 'DOB', 'Mobile', 'Current Status']
                            st.data_editor(
                                lot_students[show_cols],
                                hide_index=True,
                                use_container_width=True,
                                column_config={
                                    "Photo": st.column_config.ImageColumn("Stamp Photo", width="medium")
                                },
                                disabled=True,
                                key=f"lot_grid_exp_{lot_name}"
                            )

            else:
                st.info("No cards have been Generated yet to create a Lot summary.")
        else:
            st.info("ID card log is empty.")

        st.write("---")

        if st.button("💾 Sync Manual Updates to Cloud"):
            new_photos = final_ed[(final_ed['Photo Taken'] == True) & (final_ed['Already_Photo'] == False)]
            new_dist = final_ed[(final_ed['Distributed'] == True) & (final_ed['Already_Dist'] == False)]
            removed_photos = final_ed[(final_ed['Photo Taken'] == False) & (final_ed['Already_Photo'] == True)]
            removed_dist = final_ed[(final_ed['Distributed'] == False) & (final_ed['Already_Dist'] == True)]
            
            updated = False
            with st.spinner("Writing updates to BPS_Database..."):
                if not new_photos.empty:
                    batch_log_action("photo_log", new_photos, "Taken")
                    updated = True
                if not removed_photos.empty:
                    batch_log_action("photo_log", removed_photos, "Untaken")
                    updated = True
                if not new_dist.empty:
                    batch_log_action("id_card_log", new_dist, "Distributed")
                    updated = True
                if not removed_dist.empty:
                    batch_log_action("id_card_log", removed_dist, "Undistributed")
                    updated = True
                    
            if updated:
                st.success("✅ Successfully synced updates to Cloud!")
                if not removed_photos.empty:
                    st.warning("⚠️ **Note:** If a 'Photo Taken' checkmark instantly reappears, it means that student is still marked directly inside their specific Class Google Sheet (e.g., 'CLASS 1 - PHOTOS'). You must delete the checkmark directly in that sheet to remove it permanently.")
                clear_grid_states()
                st.rerun()
            else:
                st.info("No changes were detected to sync.")

# ==========================================
# TAB 4: PENDING PHOTOS TODAY
# ==========================================
with tabs[3]:
    st.subheader("📋 Students Present Today Missing Photos")
    st.write("Generates a PDF list of students who are in school today but haven't had their photos taken yet.")
    
    today_str = get_ist_now().strftime("%d-%m-%Y")
    df_mdm = fetch_sheet_data("mdm_log")
    
    if not df_mdm.empty:
        df_mdm['Date'] = df_mdm['Date'].astype(str)
        today_present = df_mdm[df_mdm['Date'] == today_str].copy()
        
        if not today_present.empty:
            today_present['Key'] = get_photo_key(today_present)
            
            df_photo_local = fetch_sheet_data("photo_log")
            photo_keys_local = []
            if not df_photo_local.empty:
                df_photo_local['Key'] = get_photo_key(df_photo_local)
                latest_photo_local = df_photo_local.drop_duplicates(subset=['Key'], keep='last')
                photo_keys_local = latest_photo_local[latest_photo_local['Action'] == 'Taken']['Key'].tolist()
            
            auto_keys_local = fetch_class_photo_status()
            all_taken_keys = list(set(photo_keys_local + auto_keys_local))
            
            pending_students = today_present[~today_present['Key'].isin(all_taken_keys)].copy()
            
            if not pending_students.empty:
                df_m_tab4 = fetch_sheet_data("students_master")
                if not df_m_tab4.empty:
                    pending_students['Join_Key'] = get_unified_key(pending_students, name_col='Name_x' if 'Name_x' in pending_students.columns else 'Name')
                    df_m_tab4['Join_Key'] = get_unified_key(df_m_tab4, name_col='Name_x' if 'Name_x' in df_m_tab4.columns else 'Name')

                    cols_to_pull = ['Join_Key', 'Father', 'Mother', 'DOB', 'Mobile']
                    if 'Section' not in pending_students.columns and 'Section' in df_m_tab4.columns:
                        cols_to_pull.append('Section')
                    pending_students = pd.merge(pending_students, df_m_tab4[cols_to_pull], on='Join_Key', how='left')

                if 'Name' not in pending_students.columns and 'Name_x' in pending_students.columns:
                    pending_students['Name'] = pending_students['Name_x']

                if 'Section' not in pending_students.columns: pending_students['Section'] = 'A'
                pending_students['Section'] = pending_students['Section'].fillna('A').astype(str)

                for c in ['Father', 'Mother', 'DOB', 'Mobile', 'Name']:
                    if c not in pending_students.columns: pending_students[c] = ""

                def format_tab4_dob(raw_dob):
                    raw_dob = str(raw_dob).strip().split(" ")[0]
                    fmt_dob = raw_dob
                    if raw_dob and raw_dob.lower() not in ['nan', 'none', 'nat', '']:
                        try:
                            if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$", raw_dob):
                                parts = re.split(r"[-/]", raw_dob)
                                fmt_dob = f"{int(parts[2]):02d}.{int(parts[1]):02d}.{parts[0]}"
                            else:
                                dt = pd.to_datetime(raw_dob, dayfirst=True)
                                fmt_dob = dt.strftime('%d.%m.%Y')
                        except:
                            fmt_dob = raw_dob.replace('-', '.').replace('/', '.')
                    return fmt_dob

                pending_students['DOB'] = pending_students['DOB'].apply(format_tab4_dob)

                display_cols = ['Name', 'Father', 'Mother', 'Class', 'Section', 'DOB', 'Mobile']
                unique_groups_tab4 = (pending_students['Class'].astype(str) + "_" + pending_students['Section'].astype(str)).unique().tolist()
                color_map_tab4 = {grp: '#f4f6f9' if i % 2 == 0 else '#ffffff' for i, grp in enumerate(unique_groups_tab4)}

                def tab4_row_style(row):
                    grp = str(row['Class']) + "_" + str(row['Section'])
                    bg = color_map_tab4.get(grp, '#ffffff')
                    return [f'background-color: {bg}' for _ in row]

                styled_pending_df = pending_students[display_cols].style.apply(tab4_row_style, axis=1)
                st.dataframe(styled_pending_df, hide_index=True, use_container_width=True)

                st.write("---")
                if st.button("🖨️ Generate PDF for Teachers", type="primary"):
                    pdf_bytes = generate_pending_photos_pdf(pending_students)
                    st.session_state['pending_pdf_data'] = pdf_bytes
                    st.success("✅ Pending List PDF ready!")
                
                if st.session_state['pending_pdf_data'] is not None:
                    st.download_button(
                        label="📥 Download Pending List (PDF)", 
                        data=st.session_state['pending_pdf_data'], 
                        file_name=f"BPS_Pending_Photos_{get_ist_now().strftime('%Y%m%d')}.pdf", 
                        mime="application/pdf"
                    )
            else:
                st.success("🎉 All present students today have had their photos taken!")
        else:
            st.info(f"No MDM/Attendance logs found for today ({today_str}).")
    else:
        st.warning("No MDM data found in the database. Scan students first.")

# ==========================================
# TAB 5: SHOP & LAMINATION TRACKING
# ==========================================
with tabs[4]:
    st.subheader("✂️ Shop & Lamination Tracking")
    st.write("Track the physical ID cards as they are sent to the shop for lamination and ribbons.")
    
    df_m_shop = fetch_sheet_data("students_master")
    df_id_log_shop_raw = fetch_sheet_data("id_card_log")
    
    if not df_m_shop.empty and not df_id_log_shop_raw.empty:
        df_id_log_shop = df_id_log_shop_raw.copy()
        df_id_log_shop['Action'] = df_id_log_shop['Action'].astype(str).str.strip()
        df_id_log_shop['Key'] = get_unified_key(df_id_log_shop)
        df_id_log_shop['Parsed_Time'] = pd.to_datetime(df_id_log_shop['Date'], format="%d-%m-%Y %H:%M:%S", errors='coerce')
        df_id_log_shop['Parsed_Time'] = df_id_log_shop['Parsed_Time'].fillna(pd.to_datetime(df_id_log_shop['Date'], dayfirst=True, errors='coerce'))
        df_id_log_shop = df_id_log_shop.sort_values(by='Parsed_Time', ascending=True).reset_index(drop=True)

        df_m_shop['Key'] = get_unified_key(df_m_shop, name_col='Name_x' if 'Name_x' in df_m_shop.columns else 'Name')
        
        latest_log = df_id_log_shop.drop_duplicates(subset=['Key'], keep='last')
        track_df = pd.merge(df_m_shop, latest_log[['Key', 'Action']], on='Key', how='left')
        track_df['Action'] = track_df['Action'].fillna('None')
        
        def get_valid_photo(row):
            thumb = str(row.get('Thumb_URL', '')).strip()
            photo = str(row.get('Photo_URL', '')).strip()
            if thumb and thumb.lower() not in ['nan', 'none']: return thumb
            if photo and photo.lower() not in ['nan', 'none']: return photo
            return ""
            
        track_df['Image_Target'] = track_df.apply(get_valid_photo, axis=1)
        track_df = track_df[track_df['Image_Target'] != ""]
        
        view_filter = st.selectbox("Select Pipeline Stage:", [
            "1. Ready to Send to Shop (Cards Generated)",
            "2. Currently At Shop (Pending Return)",
            "3. Received from Shop (Ready to Distribute)"
        ])
        
        if "1." in view_filter:
            filtered_df = track_df[track_df['Action'] == 'Generated'].copy()
            target_action = "Sent to Shop"
            btn_text = "📤 Mark Selected as 'Sent to Shop'"
            undo_action = None
            
        elif "2." in view_filter:
            st.markdown("<h4 style='color:#0056b3;'>📷 Scan QR to Receive Cards from Shop</h4>", unsafe_allow_html=True)
            st.write("Scan the ID cards to instantly log them as received back from the lamination shop.")
            
            qr_code_recv = qrcode_scanner(key='receive_scanner')
            
            if qr_code_recv and qr_code_recv != st.session_state.get('last_scanned_recv'):
                scanned_code = str(qr_code_recv).strip().upper()
                s_match = df_m_shop[df_m_shop['BPS Code'].astype(str).str.strip().str.upper() == scanned_code]
                
                if not s_match.empty:
                    student_name = str(s_match.iloc[0]['Name']).strip()
                    student_class = str(s_match.iloc[0]['Class']).strip()
                    student_roll = str(s_match.iloc[0]['Roll']).strip()

                    card_status_df = track_df[track_df['BPS Code'].astype(str).str.strip().str.upper() == scanned_code]
                    current_status = card_status_df.iloc[0]['Action'] if not card_status_df.empty else 'None'
                    
                    if current_status != 'Sent to Shop':
                        st.warning(f"⚠️ Cannot receive **{student_name}**. Current status is '{current_status}', not 'Sent to Shop'.")
                        st.session_state['last_scanned_recv'] = qr_code_recv
                    else:
                        existing = st.session_state['received_log'][st.session_state['received_log']['BPS Code'] == scanned_code]
                        if not existing.empty:
                            st.warning(f"⚠️ {student_name} is already in your received scan list!")
                            st.session_state['last_scanned_recv'] = qr_code_recv
                        else:
                            new_entry = pd.DataFrame([{'Name': student_name, 'Roll': student_roll, 'Class': student_class, 'BPS Code': scanned_code}])
                            st.session_state['received_log'] = pd.concat([st.session_state['received_log'], new_entry], ignore_index=True)
                            st.session_state['last_scanned_recv'] = qr_code_recv
                            play_beep() 
                            st.success(f"✅ **{student_name}** successfully scanned!")
                else:
                    st.error("Invalid QR Code or BPS Code not found in database.")
                    st.session_state['last_scanned_recv'] = qr_code_recv

            if not st.session_state['received_log'].empty:
                st.markdown("##### 📥 Scanned Cards Ready to be Marked as Received")
                st.dataframe(st.session_state['received_log'], use_container_width=True)
                
                if st.button("📥 Submit Scanned Cards as 'Received from Shop'", type="primary", use_container_width=True):
                    batch_log_action("id_card_log", st.session_state['received_log'], "Received from Shop")
                    st.success(f"✅ Successfully marked {len(st.session_state['received_log'])} cards as Received!")
                    st.session_state['received_log'] = pd.DataFrame(columns=['Name', 'Roll', 'Class', 'BPS Code'])
                    clear_grid_states()
                    time.sleep(1.5)
                    st.rerun()
                    
                if st.button("🗑️ Clear Receive Scan List"):
                    st.session_state['received_log'] = pd.DataFrame(columns=['Name', 'Roll', 'Class', 'BPS Code'])
                    st.rerun()

            st.divider()
            st.markdown("#### 📋 Or Manual Grid Selection")
            
            filtered_df = track_df[track_df['Action'] == 'Sent to Shop'].copy()
            target_action = "Received from Shop"
            btn_text = "📥 Mark Manual Selection as 'Received from Shop'"
            undo_action = "Generated"
            undo_text = "⏪ Undo: Send back to 'Ready to Shop'"
            
        else:
            filtered_df = track_df[track_df['Action'] == 'Received from Shop'].copy()
            target_action = None
            btn_text = None
            undo_action = "Sent to Shop"
            undo_text = "⏪ Undo: Send back to 'At Shop'"
            st.info("💡 **To mark these cards as Distributed, please flip to the '📸 Scanner' tab and scan them as you hand them out.**")
            
        if not filtered_df.empty:
            st.write(f"Showing **{len(filtered_df)}** valid students in this list.")
                
            filtered_df = filtered_df.reset_index(drop=True)
                
            with st.spinner("Loading stamp size photos..."):
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as exe:
                    filtered_df['Photo'] = list(exe.map(get_secure_photo_b64, filtered_df['Image_Target'].tolist()))
            
            filtered_df.insert(0, "Select", False)
            show_cols = ['Select', 'Photo', 'Name', 'Class', 'Roll', 'BPS Code']
            for c in show_cols:
                if c not in filtered_df.columns: filtered_df[c] = ""
                    
            ed_df = st.data_editor(
                filtered_df[show_cols],
                hide_index=True, use_container_width=True,
                column_config={
                    "Select": st.column_config.CheckboxColumn("Select", default=False),
                    "Photo": st.column_config.ImageColumn("Stamp Size Photo", width="medium")
                },
                disabled=['Photo', 'Name', 'Class', 'Roll', 'BPS Code'],
                key=f"shop_grid_{view_filter[:2]}" 
            )
            
            selected_indices = ed_df[ed_df['Select'] == True].index
            selected = filtered_df.loc[selected_indices]
            
            if not selected.empty:
                st.info(f"🎯 **You have selected {len(selected)} student(s).**") 
                
                if target_action and undo_action:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button(btn_text, type="primary", use_container_width=True):
                            batch_log_action("id_card_log", selected, target_action)
                            st.success(f"✅ Successfully logged {len(selected)} students as '{target_action}'!")
                            clear_grid_states()
                            st.rerun()
                    with c2:
                        if st.button(undo_text, type="secondary", use_container_width=True):
                            batch_log_action("id_card_log", selected, undo_action)
                            st.warning(f"⏪ Successfully reverted {len(selected)} students back to '{undo_action}'.")
                            clear_grid_states()
                            st.rerun()
                elif target_action:
                    if st.button(btn_text, type="primary"):
                        batch_log_action("id_card_log", selected, target_action)
                        st.success(f"✅ Successfully logged {len(selected)} students as '{target_action}'!")
                        clear_grid_states()
                        st.rerun()
                elif undo_action:
                    if st.button(undo_text, type="secondary"):
                        batch_log_action("id_card_log", selected, undo_action)
                        st.warning(f"⏪ Successfully reverted {len(selected)} students back to '{undo_action}'.")
                        clear_grid_states()
                        st.rerun()
        else:
            st.success("No students found in this stage. Check the other dropdown options.")
    else:
        st.info("No ID card log data available. Generate IDs first.")

# ==========================================
# TAB 6: DISTRIBUTED CARDS
# ==========================================
with tabs[5]:
    st.subheader("✅ Distributed ID Cards")
    st.write("View the complete profile of all students whose ID cards have been successfully distributed.")

    df_m_dist = fetch_sheet_data("students_master")
    df_id_log_dist_raw = fetch_sheet_data("id_card_log")

    if not df_m_dist.empty and not df_id_log_dist_raw.empty:
        
        df_id_log_dist = df_id_log_dist_raw.copy()
        df_id_log_dist['Action'] = df_id_log_dist['Action'].astype(str).str.strip()
        df_id_log_dist['Key'] = get_unified_key(df_id_log_dist)
        
        df_id_log_dist['Parsed_Time'] = pd.to_datetime(df_id_log_dist['Date'], format="%d-%m-%Y %H:%M:%S", errors='coerce')
        df_id_log_dist['Parsed_Time'] = df_id_log_dist['Parsed_Time'].fillna(pd.to_datetime(df_id_log_dist['Date'], dayfirst=True, errors='coerce'))
        df_id_log_dist = df_id_log_dist.sort_values(by='Parsed_Time', ascending=True).reset_index(drop=True)

        df_m_dist['Key'] = get_unified_key(df_m_dist, name_col='Name_x' if 'Name_x' in df_m_dist.columns else 'Name')

        dist_events_only = df_id_log_dist[df_id_log_dist['Action'].isin(['Distributed', 'Undistributed'])].copy()

        if not dist_events_only.empty:
            latest_log_dist = dist_events_only.drop_duplicates(subset=['Key'], keep='last')
            currently_distributed = latest_log_dist[latest_log_dist['Action'] == 'Distributed']
            
            filtered_dist_df = pd.merge(df_m_dist, currently_distributed[['Key', 'Date']], on='Key', how='inner')

            if not filtered_dist_df.empty:
                filtered_dist_df['Parsed_Date'] = pd.to_datetime(filtered_dist_df['Date'], dayfirst=True, errors='coerce')
                filtered_dist_df = filtered_dist_df.sort_values(by='Parsed_Date', ascending=False).reset_index(drop=True)
                filtered_dist_df['Distributed Date'] = filtered_dist_df['Date'].apply(lambda x: str(x).split(' ')[0] if pd.notna(x) and str(x) != 'nan' else '')

                st.write(f"Showing **{len(filtered_dist_df)}** distributed ID cards.")

                if 'Section' not in filtered_dist_df.columns: filtered_dist_df['Section'] = 'A'
                filtered_dist_df['Section'] = filtered_dist_df['Section'].fillna('A').astype(str)

                for c in ['Father', 'Mother', 'DOB', 'Mobile', 'BPS Code']:
                    if c not in filtered_dist_df.columns: filtered_dist_df[c] = ""

                def format_dist_dob(raw_dob):
                    raw_dob = str(raw_dob).strip().split(" ")[0]
                    fmt_dob = raw_dob
                    if raw_dob and raw_dob.lower() not in ['nan', 'none', 'nat', '']:
                        try:
                            if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$", raw_dob):
                                parts = re.split(r"[-/]", raw_dob)
                                fmt_dob = f"{int(parts[2]):02d}.{int(parts[1]):02d}.{parts[0]}"
                            else:
                                dt = pd.to_datetime(raw_dob, dayfirst=True)
                                fmt_dob = dt.strftime('%d.%m.%Y')
                        except:
                            fmt_dob = raw_dob.replace('-', '.').replace('/', '.')
                    return fmt_dob

                filtered_dist_df['DOB'] = filtered_dist_df['DOB'].apply(format_dist_dob)

                def get_valid_photo(row):
                    thumb = str(row.get('Thumb_URL', '')).strip()
                    photo = str(row.get('Photo_URL', '')).strip()
                    if thumb and thumb.lower() not in ['nan', 'none']: return thumb
                    if photo and photo.lower() not in ['nan', 'none']: return photo
                    return ""

                filtered_dist_df['Image_Target'] = filtered_dist_df.apply(get_valid_photo, axis=1)

                with st.spinner("Loading student photos..."):
                    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as exe:
                        filtered_dist_df['Photo'] = list(exe.map(get_secure_photo_b64, filtered_dist_df['Image_Target'].tolist()))

                unique_dates_dist = filtered_dist_df['Distributed Date'].unique().tolist()
                color_map_dist = {d: '#f4f6f9' if i % 2 == 0 else '#ffffff' for i, d in enumerate(unique_dates_dist)}

                def dist_row_style(row):
                    bg = color_map_dist.get(row['Distributed Date'], '#ffffff')
                    return [f'background-color: {bg}' for _ in row]

                show_cols_dist = ['Photo', 'Name', 'Father', 'Mother', 'Class', 'Section', 'DOB', 'Mobile', 'BPS Code', 'Distributed Date']
                styled_dist_df = filtered_dist_df[show_cols_dist].style.apply(dist_row_style, axis=1)

                st.data_editor(
                    styled_dist_df,
                    hide_index=True, use_container_width=True,
                    column_config={
                        "Photo": st.column_config.ImageColumn("Stamp Size Photo", width="medium")
                    },
                    disabled=True, key="distributed_grid"
                )
            else:
                st.success("No cards have been distributed yet. Scan them in the Scanner tab!")
        else:
            st.success("No cards have been distributed yet. Scan them in the Scanner tab!")
    else:
        st.info("No ID card log data available.")

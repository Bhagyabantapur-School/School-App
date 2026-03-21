import streamlit as st
import pandas as pd
import qrcode
import os
from fpdf import FPDF
import tempfile
from datetime import datetime

# --- NEW IMPORTS FOR GOOGLE SHEETS & DRIVE API ---
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
st.set_page_config(page_title="BPS Digital - ID Generator", page_icon="🏫", layout="centered")

if 'attendance_log' not in st.session_state:
    st.session_state['attendance_log'] = pd.DataFrame(columns=['Time', 'Name', 'Roll', 'Class', 'Status', 'MDM'])

# --- 2. GOOGLE CREDENTIALS & DRIVE FETCHING ---
@st.cache_resource
def get_google_credentials():
    skey = dict(st.secrets["gcp_service_account"])
    # Combined scopes for both Google Sheets and Google Drive access
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

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_secure_image_bytes(file_id):
    """Securely downloads the image using the authorized service account."""
    try:
        creds = get_google_credentials()
        authed_session = AuthorizedSession(creds)
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        response = authed_session.get(url)
        
        if response.status_code == 200:
            return response.content
        return None
    except Exception as e:
        return None

def extract_drive_id(url):
    """Safely extracts the Google Drive file ID from a sharing link."""
    if pd.isna(url) or not isinstance(url, str) or url.strip() == "":
        return None
    if "drive.google.com/file/d/" in url:
        try:
            return url.split("/d/")[1].split("/")[0]
        except IndexError:
            pass
    return None

# --- 3. FETCH & CLEAN DATA ---
@st.cache_data(ttl=300) 
def fetch_sheet_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        df.replace({'TRUE': True, 'FALSE': False, 'True': True, 'False': False}, inplace=True)
        return df
    except Exception as e:
        return pd.DataFrame()

def clear_sheet_cache():
    fetch_sheet_data.clear()

def append_sheet_df(sheet_name, df):
    if df.empty: return
    try: 
        ws = sh.worksheet(sheet_name)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
        ws.append_row(list(df.columns))
    
    df = df.fillna("").astype(str)
    try:
        ws.append_rows(df.values.tolist())
        clear_sheet_cache()
    except Exception as e:
        st.error("⚠️ Google Sheets API error while saving data.")

@st.cache_data(ttl=300)
def get_students():
    df = fetch_sheet_data("students_master")
    if df.empty:
        return pd.DataFrame()
        
    if 'Class' in df.columns:
        df['Class'] = df['Class'].replace('CALSS IV', 'CLASS IV')
    
    # Ensure all necessary columns exist, including Photo_URL
    for col in ['Section', 'BloodGroup', 'Father', 'Mother', 'Gender', 'DOB', 'Mobile', 'Photo_URL']:
        if col not in df.columns:
            df[col] = 'N/A'
            
    # Fix Mobile Number trailing .0
    df['Mobile'] = df['Mobile'].astype(str)
    df['Mobile'] = df['Mobile'].apply(lambda x: x[:-2] if x.endswith('.0') else x)
    df['Mobile'] = df['Mobile'].replace(['nan', 'None', ''], 'N/A')
    
    # Format DOB to DD-MM-YYYY
    df['DOB'] = pd.to_datetime(df['DOB'], errors='coerce', dayfirst=True).dt.strftime('%d-%m-%Y').fillna(df['DOB'])

    return df

def parse_qr_data(qr_string):
    try:
        data = {}
        parts = qr_string.split('|')
        for part in parts:
            key, value = part.split(':')
            data[key.strip()] = value.strip()
        return data
    except:
        return None

# --- 4. PDF GENERATOR ---
def generate_pdf(students_list, photo_dict):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    x_start, y_start, card_w, card_h, gap = 10, 10, 86, 54, 8
    col, row = 0, 0
    
    bg_img = None
    for ext in ['background.jpg', 'background.jpeg', 'background.png']:
        if os.path.exists(ext):
            bg_img = ext
            break
            
    for student in students_list:
        x = x_start + (col * (card_w + gap))
        y = y_start + (row * (card_h + gap))
        
        if bg_img:
            try: pdf.image(bg_img, x=x, y=y, w=card_w, h=card_h)
            except: pass 

        pdf.set_draw_color(0, 0, 0); pdf.set_line_width(0.3); pdf.rect(x, y, card_w, card_h)
        pdf.set_fill_color(0, 51, 153); pdf.rect(x, y, card_w, 11, 'F')
        
        if os.path.exists('logo.png'): 
            pdf.image('logo.png', x=x+68.5, y=y+1, w=16, h=16)
            
        pdf.set_font("Arial", 'B', 8.5); pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x+2, y+1.5); pdf.cell(66, 5, "BHAGYABANTAPUR PRIMARY SCHOOL", 0, 1, 'C')
        pdf.set_font("Arial", '', 6)
        pdf.set_xy(x+2, y+6.5); pdf.cell(66, 3, "Mob: 7908390822  |  ID CARD - SESSION 2026", 0, 1, 'C')
        
        photo_x, photo_y, photo_w, photo_h = x+3, y+14, 18, 22
        student_id = str(student.get('Sl', 0)) + "_" + str(student.get('Roll', '0'))
        
        # Inject the securely fetched photo
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
        
        for label, val in [
            ("Father", str(student.get('Father', ''))[:22]), 
            ("Mother", str(student.get('Mother', ''))[:22]), 
            ("Class", f"{student.get('Class', '')} | Sec: {student.get('Section', 'A')}"), 
            ("DOB", student.get('DOB', ''))
        ]:
            pdf.set_xy(detail_x, curr_y); pdf.cell(44, line_h, f"{label}: {val}", 0, 1); curr_y += line_h
            
        pdf.set_xy(detail_x, curr_y); pdf.set_font("Arial", 'B', 7)
        pdf.cell(44, line_h, f"Mob: {student.get('Mobile', '')}", 0, 1)

        qr_data = f"Name:{student.get('Name', '')}|Roll:{student.get('Roll', '')}|Mob:{student.get('Mobile', '')}"
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
            
    # --- STREAMLIT CLOUD FPDF FIX ---
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        return pdf_output.encode('latin-1')
    else:
        return bytes(pdf_output)


# --- 5. TABS LAYOUT ---
tab1, tab2 = st.tabs(["🖨️ ID Card Generator", "📸 MDM & Attendance Scanner"])

# ==========================================
# TAB 1: ID CARD GENERATOR (Fully Automated)
# ==========================================
with tab1:
    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        if os.path.exists('logo.png'): st.image('logo.png', use_container_width=True)
    st.markdown('<h3 style="text-align:center; color:#007bff;">BPS Student ID Card Generator</h3>', unsafe_allow_html=True)
    st.divider()

    df = get_students()
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1: selected_class = st.selectbox("Class", ["All"] + sorted(df['Class'].dropna().unique().tolist()))
        with c2: selected_section = st.selectbox("Section", ["All"] + sorted(df['Section'].dropna().unique().tolist()))

        filtered_df = df.copy()
        if selected_class != "All": filtered_df = filtered_df[filtered_df['Class'] == selected_class]
        if selected_section != "All": filtered_df = filtered_df[filtered_df['Section'] == selected_section]
        
        filtered_df.insert(0, "Select", False)
        # Displaying the dataframe so you can select students to print
        edited_df = st.data_editor(
            filtered_df[['Select', 'Roll', 'Name', 'Class', 'Photo_URL']], 
            hide_index=True, 
            column_config={"Select": st.column_config.CheckboxColumn(required=True)}, 
            disabled=['Roll', 'Name', 'Class', 'Photo_URL'], 
            use_container_width=True
        )
        
        # Get full row data for the selected students
        selected_indices = edited_df[edited_df["Select"] == True].index
        selected_students = filtered_df.loc[selected_indices].copy()
        
        if not selected_students.empty:
            st.divider()
            st.success(f"Selected {len(selected_students)} student(s). Photos will be fetched securely from BPS Google Drive.")
            
            if st.button("Generate Secure PDF", type="primary"):
                photo_dict = {}
                
                # Show a progress bar while downloading images securely
                progress_text = "Fetching Secure Photos from Google Drive..."
                my_bar = st.progress(0, text=progress_text)
                
                total_students = len(selected_students)
                for idx, (index, student) in enumerate(selected_students.iterrows()):
                    sid = str(student.get('Sl', index)) + "_" + str(student.get('Roll', '0'))
                    photo_url = str(student.get('Photo_URL', ''))
                    
                    drive_id = extract_drive_id(photo_url)
                    if drive_id:
                        img_bytes = fetch_secure_image_bytes(drive_id)
                        if img_bytes:
                            photo_dict[sid] = img_bytes
                            
                    my_bar.progress((idx + 1) / total_students, text=f"Fetched photo {idx + 1} of {total_students}")
                
                my_bar.empty()
                
                with st.spinner("Compiling PDF Document..."):
                    pdf_bytes = generate_pdf(selected_students.to_dict('records'), photo_dict)
                    
                st.balloons()
                st.download_button("📥 Download ID Cards (PDF)", pdf_bytes, f"BPS_ID_Cards_{datetime.now().strftime('%Y%m%d')}.pdf", "application/pdf")
    else:
        st.warning("Could not load student data. Please check your Google Sheet Secrets.")

# ==========================================
# TAB 2: MDM SCANNER 
# ==========================================
with tab2:
    st.markdown('<h3 style="text-align:center; color:#28a745;">📸 Scan ID Card</h3>', unsafe_allow_html=True)
    st.write("Scanned data will sync directly to the main BPS Cloud Database!")
    
    qr_code = qrcode_scanner(key='mdm_scanner')
    
    if qr_code:
        data = parse_qr_data(qr_code)
        if data:
            student_name = data.get('Name', 'Unknown')
            student_roll = data.get('Roll', 'Unknown')
            
            df = get_students()
            student_match = df[(df['Name'] == student_name) & (df['Roll'].astype(str) == str(student_roll))]
            
            if not student_match.empty:
                s_class = student_match.iloc[0]['Class']
                s_sec = student_match.iloc[0]['Section']
                
                existing = st.session_state['attendance_log'][
                    (st.session_state['attendance_log']['Name'] == student_name) & 
                    (st.session_state['attendance_log']['Roll'] == student_roll)
                ]
                
                if not existing.empty:
                    st.warning(f"⚠️ {student_name} is already marked present today!")
                else:
                    curr_date_str = datetime.now().strftime("%d-%m-%Y")
                    curr_time_str = datetime.now().strftime("%H:%M")
                    
                    new_entry = pd.DataFrame([{
                        'Time': curr_time_str, 'Name': student_name, 'Roll': student_roll, 
                        'Class': f"{s_class} {s_sec}", 'Status': 'Present', 'MDM': 'Yes'
                    }])
                    st.session_state['attendance_log'] = pd.concat([st.session_state['attendance_log'], new_entry], ignore_index=True)
                    
                    mdm_data = pd.DataFrame([{
                        'Date': curr_date_str, 'Teacher': 'Scanned via ID App', 
                        'Class': s_class, 'Section': s_sec, 'Roll': student_roll, 
                        'Name': student_name, 'Time': curr_time_str
                    }])
                    append_sheet_df('mdm_log', mdm_data)

                    att_data = pd.DataFrame([{
                        'Date': curr_date_str, 'Class': s_class, 'Section': s_sec, 
                        'Roll': student_roll, 'Name': student_name, 'Status': True
                    }])
                    append_sheet_df('student_attendance_master', att_data)

                    st.success(f"✅ **{student_name}** logged & synced to Cloud!")
            else:
                st.error(f"Student '{student_name}' not found in the Master Database.")
        else:
            st.error("Invalid QR Code Format. Please scan a valid BPS ID Card.")

    st.divider()
    
    st.markdown("### 📋 Today's Local Scans")
    if not st.session_state['attendance_log'].empty:
        st.dataframe(st.session_state['attendance_log'], use_container_width=True)
    else:
        st.info("No students scanned yet today. Use the camera above to start.")

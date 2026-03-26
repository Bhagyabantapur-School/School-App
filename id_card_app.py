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

# Initialize Session States
if 'attendance_log' not in st.session_state:
    st.session_state['attendance_log'] = pd.DataFrame(columns=['Time', 'Name', 'Roll', 'Class', 'Status', 'MDM'])
if 'generated_pdf_data' not in st.session_state:
    st.session_state['generated_pdf_data'] = None
if 'pending_pdf_data' not in st.session_state:
    st.session_state['pending_pdf_data'] = None

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
                    class_name = f"CLASS {parts[1]}"
                else:
                    continue
                
                values = ws.get_all_values()
                for row in values:
                    if not row or len(row) < 2: continue
                    roll = str(row[0]).strip()
                    if not roll.isdigit(): continue 
                    
                    is_taken = False
                    for cell in row[1:]:
                        val_up = str(cell).strip().upper()
                        if val_up in ['TRUE', 'YES', 'TAKEN', 'Y'] or 'DRIVE.GOOGLE' in val_up:
                            is_taken = True
                            break
                        
                    if is_taken:
                        taken_keys.add(f"{class_name}_{roll}")
    except:
        pass
    return list(taken_keys)

def clear_sheet_cache():
    fetch_sheet_data.clear()
    fetch_class_photo_status.clear()

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
        st.error(f"⚠️ Cloud sync error: {e}")

def batch_log_action(sheet_name, df, action):
    if df.empty: return
    try:
        log_ws = sh.worksheet(sheet_name)
    except WorksheetNotFound:
        log_ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=5)
        log_ws.append_row(["Date", "Class", "Roll", "Name", "Action"])
    
    rows = []
    now_str = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    for _, r in df.iterrows():
        name_val = str(r.get('Name', r.get('Name_x', 'Unknown')))
        rows.append([now_str, str(r.get('Class', '')), str(r.get('Roll', '')), name_val, action])
    
    if rows:
        log_ws.append_rows(rows)
        clear_sheet_cache()

def parse_qr_data(qr_string):
    try:
        data = {}
        parts = qr_string.split('|')
        for part in parts:
            if ':' in part:
                key, value = part.split(':', 1)
                data[key.strip()] = value.strip()
        return data
    except:
        return None

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
        
        # Background
        if bg_img:
            try: pdf.image(bg_img, x=x, y=y, w=card_w, h=card_h)
            except: pass 

        # Border & Blue Header
        pdf.set_draw_color(0, 0, 0); pdf.set_line_width(0.3); pdf.rect(x, y, card_w, card_h)
        pdf.set_fill_color(0, 51, 153); pdf.rect(x, y, card_w, 11, 'F')
        
        # Logo
        if os.path.exists('logo.png'): 
            pdf.image('logo.png', x=x+68.5, y=y+1, w=16, h=16)
            
        pdf.set_font("Arial", 'B', 8.5); pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x+2, y+1.5); pdf.cell(66, 5, "BHAGYABANTAPUR PRIMARY SCHOOL", 0, 1, 'C')
        pdf.set_font("Arial", '', 6)
        pdf.set_xy(x+2, y+6.5); pdf.cell(66, 3, "Mob: 7908390822  |  ID CARD - SESSION 2026", 0, 1, 'C')
        
        # Photo
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
        
        # Details
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

        # QR Code
        qr_data = f"Name:{student.get('Name', '')}|Roll:{student.get('Roll', '')}|Mob:{student.get('Mobile', '')}"
        qr = qrcode.make(qr_data); qr_path = tempfile.mktemp(suffix=".png"); qr.save(qr_path)
        pdf.image(qr_path, x=x+4.5, y=y+37, w=15, h=15)
        
        # Footer Image
        if os.path.exists('image_2.png'):
            try: pdf.image('image_2.png', x=x, y=y+44, w=card_w, h=10)
            except: pass

        # Watermark
        wm_x, wm_y = x + 55, y + 42
        pdf.set_draw_color(220, 240, 255); pdf.set_line_width(0.4)
        pdf.line(wm_x, wm_y, wm_x, wm_y + 6); pdf.line(wm_x, wm_y, wm_x + 2, wm_y); pdf.line(wm_x, wm_y + 6, wm_x + 2, wm_y + 6)
        pdf.line(wm_x + 27, wm_y, wm_x + 27, wm_y + 6); pdf.line(wm_x + 25, wm_y, wm_x + 27, wm_y); pdf.line(wm_x + 25, wm_y + 6, wm_x + 27, wm_y + 6)
        pdf.set_text_color(210, 235, 255); pdf.set_font("Arial", 'B', 6); pdf.set_xy(wm_x, wm_y + 1); pdf.cell(27, 4, "BPS DIGITAL", 0, 0, 'C')

        # Signature
        if os.path.exists('signature.png'): 
            try: pdf.image('signature.png', x=x+58, y=y+40, w=22, h=8)
            except: pass
        
        pdf.set_text_color(0); pdf.set_font("Arial", 'I', 6); pdf.set_xy(x, y+49); pdf.cell(card_w-5, 3, "Sukhamay Kisku", 0, 1, 'R')
        pdf.set_font("Arial", '', 5); pdf.set_xy(x, y+51); pdf.cell(card_w-5, 2, "Head Teacher", 0, 0, 'R')
        
        # 10 Cards Per Page Logic
        col += 1
        if col >= 2: col, row = 0, row + 1
        if row >= 5: pdf.add_page(); col, row = 0, 0
            
    # Final Output Fix
    if progress_bar: progress_bar.progress(1.0, text="✅ PDF Rendering Complete!")
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        return pdf_output.encode('latin-1')
    return bytes(pdf_output)

def generate_pending_photos_pdf(df_pending):
    """Generates an A4 list of students who are present today but need photos."""
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Bhagyabantapur Primary School", ln=True, align='C')
    
    pdf.set_font("Arial", 'B', 12)
    current_date = datetime.now().strftime("%d-%m-%Y")
    pdf.cell(0, 8, f"Pending Photos for Present Students - {current_date}", ln=True, align='C')
    
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, "Message to Teachers: Please send the following students for photo taking today.", ln=True, align='C')
    pdf.ln(5)
    
    # Body grouped by class and section
    pdf.set_text_color(0, 0, 0)
    
    if df_pending.empty:
        pdf.set_font("Arial", '', 12)
        pdf.cell(0, 10, "No pending photos for present students today. Great job!", ln=True, align='C')
    else:
        # Group data
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
tabs = st.tabs(["🖨️ ID Generator", "📸 Scanner", "📂 Database Explorer", "📋 Pending Photos Today"])

# ==========================================
# TAB 1: ID GENERATOR
# ==========================================
with tabs[0]:
    h_col1, h_col2 = st.columns([1, 5])
    with h_col1:
        if os.path.exists('logo.png'): st.image('logo.png', width=70)
    with h_col2:
        st.markdown("<h2 style='margin-top:10px;'>BPS Student ID Card Generator</h2>", unsafe_allow_html=True)
    
    st.divider()

    df_master = fetch_sheet_data("students_master")
    df_log = fetch_sheet_data("form_distribution_log")
    df_id_log = fetch_sheet_data("id_card_log")
    
    if not df_master.empty and not df_log.empty:
        df_master['Roll'] = df_master['Roll'].astype(str)
        df_log['Roll'] = df_log['Roll'].astype(str)
        merged = pd.merge(df_master, df_log, on=['Class', 'Section', 'Roll'], how='inner', suffixes=('', '_log'))
        
        gen_keys = []
        if not df_id_log.empty:
            df_id_log['Key'] = df_id_log['Class'].astype(str) + "_" + df_id_log['Roll'].astype(str)
            gen_keys = df_id_log[df_id_log['Action'] == 'Generated']['Key'].unique().tolist()
            
        merged['Key'] = merged['Class'].astype(str) + "_" + merged['Roll'].astype(str)
        merged['Generated'] = merged['Key'].isin(gen_keys)
        
        def is_ready_to_print(row):
            has_photo = pd.notna(row.get('Photo_URL')) and str(row.get('Photo_URL')).strip() != ""
            is_returned = str(row.get('Return Status', '')).strip() == 'Complete'
            has_corr = any([str(row.get(f'Old {f}', '')).strip() not in ['','nan','None'] for f in ['Student Name', 'Father Name', 'Mobile Number']])
            is_verified = str(row.get('Data Corrected', '')).strip() == 'Yes'
            return has_photo and is_returned and (is_verified if has_corr else True)

        merged['Ready'] = merged.apply(is_ready_to_print, axis=1)
        print_ready = merged[merged['Ready'] == True].copy()

        if not print_ready.empty:
            print_ready.insert(0, "Select", False)
            
            edited_df = st.data_editor(
                print_ready[['Select', 'Roll', 'Name', 'Class', 'Generated']],
                hide_index=True, use_container_width=True, key="gen_editor",
                disabled=['Roll', 'Name', 'Class', 'Generated']
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
                            if img_bytes:
                                photo_dict[sid] = img_bytes
                                
                        my_bar.progress((idx + 1) / num_students * 0.5, text=f"Fetching photo {idx + 1} of {num_students}...")
                    
                    pdf_bytes = generate_pdf(selected_students.to_dict('records'), photo_dict, progress_bar=my_bar)
                    batch_log_action("id_card_log", selected_students, "Generated")
                        
                    st.session_state['generated_pdf_data'] = pdf_bytes
                    st.balloons()
                
                if st.session_state['generated_pdf_data'] is not None:
                    st.success("✅ Your PDF is ready! Click below to save it.")
                    st.download_button(
                        label="📥 Download ID Cards (PDF)", 
                        data=st.session_state['generated_pdf_data'], 
                        file_name=f"BPS_ID_Cards_{datetime.now().strftime('%Y%m%d')}.pdf", 
                        mime="application/pdf"
                    )
        else:
            st.info("No students found with a linked Photo URL and a cleared form.")

# ==========================================
# TAB 2: MDM SCANNER
# ==========================================
with tabs[1]:
    st.markdown('<h3 style="text-align:center; color:#28a745;">📸 Scan ID Card</h3>', unsafe_allow_html=True)
    st.write("Scanned data will sync directly to the main BPS Cloud Database!")
    
    qr_code = qrcode_scanner(key='mdm_scanner')
    
    if qr_code:
        data = parse_qr_data(qr_code)
        if data:
            student_name = data.get('Name', 'Unknown')
            student_roll = data.get('Roll', 'Unknown')
            
            m_df = fetch_sheet_data("students_master")
            s_match = m_df[(m_df['Name'] == student_name) & (m_df['Roll'].astype(str) == str(student_roll))]
            student_class = s_match.iloc[0]['Class'] if not s_match.empty else "Unknown"

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
                    'Class': student_class, 'Status': 'Present', 'MDM': 'Yes'
                }])
                st.session_state['attendance_log'] = pd.concat([st.session_state['attendance_log'], new_entry], ignore_index=True)
                
                mdm_data = pd.DataFrame([{
                    'Date': curr_date_str, 'Teacher': 'Scanned via ID App', 
                    'Class': student_class, 'Section': 'A', 'Roll': student_roll, 
                    'Name': student_name, 'Time': curr_time_str
                }])
                append_sheet_df('mdm_log', mdm_data)

                att_data = pd.DataFrame([{
                    'Date': curr_date_str, 'Class': student_class, 'Section': 'A', 
                    'Roll': student_roll, 'Name': student_name, 'Status': True
                }])
                append_sheet_df('student_attendance_master', att_data)

                st.success(f"✅ **{student_name}** logged & synced to Cloud!")
        else:
            st.error("Invalid QR Code Format. Please scan a valid BPS ID Card.")

    st.divider()
    st.markdown("### 📋 Today's Local Scans")
    if not st.session_state['attendance_log'].empty:
        st.dataframe(st.session_state['attendance_log'], use_container_width=True)
    else:
        st.info("No students scanned yet today.")

# ==========================================
# TAB 3: DATABASE EXPLORER
# ==========================================
with tabs[2]:
    st.subheader("📂 ID Lifecycle & Media Tracker")
    
    df_m = fetch_sheet_data("students_master")
    df_l = fetch_sheet_data("form_distribution_log")
    df_photo = fetch_sheet_data("photo_log")
    df_id_log = fetch_sheet_data("id_card_log")
    
    if not df_m.empty and not df_l.empty:
        df_m['Roll'] = df_m['Roll'].astype(str)
        df_l['Roll'] = df_l['Roll'].astype(str)
        
        explorer_db = pd.merge(df_m, df_l, on=['Class', 'Section', 'Roll'], how='left', suffixes=('', '_log'))
        explorer_db['Key'] = explorer_db['Class'].astype(str) + "_" + explorer_db['Roll'].astype(str)
        
        photo_keys, gen_keys, dist_keys = [], [], []
        
        if not df_photo.empty:
            df_photo['Key'] = df_photo['Class'].astype(str) + "_" + df_photo['Roll'].astype(str)
            photo_keys = df_photo[df_photo['Action'] == 'Taken']['Key'].unique().tolist()
            
        if not df_id_log.empty:
            df_id_log['Key'] = df_id_log['Class'].astype(str) + "_" + df_id_log['Roll'].astype(str)
            gen_keys = df_id_log[df_id_log['Action'] == 'Generated']['Key'].unique().tolist()
            dist_keys = df_id_log[df_id_log['Action'] == 'Distributed']['Key'].unique().tolist()

        class_photo_keys = fetch_class_photo_status()
        photo_keys = list(set(photo_keys + class_photo_keys))

        # Boolean Checkboxes for URLs
        explorer_db['Photo_URL'] = explorer_db['Photo_URL'].apply(lambda x: True if pd.notna(x) and str(x).strip() != "" else False)
        if 'Thumb_URL' in explorer_db.columns:
            explorer_db['Thumb_URL'] = explorer_db['Thumb_URL'].apply(lambda x: True if pd.notna(x) and str(x).strip() != "" else False)
        else:
            explorer_db['Thumb_URL'] = False

        explorer_db['Form_OK'] = explorer_db['Return Status'].apply(lambda x: True if str(x) == "Complete" else False)
        explorer_db['Verified'] = explorer_db['Data Corrected'].apply(lambda x: True if str(x) == "Yes" else False)
        
        explorer_db['Photo Taken'] = explorer_db['Key'].isin(photo_keys)
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
        
        # 1. Counts Placeholder
        metrics_container = st.container()

        # 2. Style rows based on class for alternation
        def row_style(row):
            classes = filtered_view['Class'].unique()
            color_map = {c: '#f4f6f9' if i % 2 == 0 else '#ffffff' for i, c in enumerate(classes)}
            bg = color_map.get(row['Class'], '#ffffff')
            return [f'background-color: {bg}' for _ in row]

        cols_to_show = ['Photo Taken', 'Photo_URL', 'Thumb_URL', 'Name', 'Class', 'Roll', 'Form_OK', 'Verified', 'Generated', 'Distributed']
        styled_df = filtered_view[cols_to_show + ['Already_Photo', 'Already_Dist']].style.apply(row_style, axis=1)

        # Draw Editor
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
            disabled=['Photo_URL', 'Thumb_URL', 'Name', 'Class', 'Roll', 'Form_OK', 'Verified', 'Generated'],
            hide_index=True,
            use_container_width=True,
            key="db_explorer_grid"
        )

        # 3. Populate live counts
        with metrics_container:
            st.markdown("##### 📊 Live Column Counts")
            c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
            c1.metric("📸 Photo Taken", int(final_ed['Photo Taken'].sum()))
            c2.metric("🔗 Photo Link", int(final_ed['Photo_URL'].sum()))
            c3.metric("🖼️ Thumb Link", int(final_ed['Thumb_URL'].sum()))
            c4.metric("📝 Form OK", int(final_ed['Form_OK'].sum()))
            c5.metric("✅ Verified", int(final_ed['Verified'].sum()))
            c6.metric("🖨️ Generated", int(final_ed['Generated'].sum()))
            c7.metric("🎁 Distributed", int(final_ed['Distributed'].sum()))
            st.write("") 

        if st.button("💾 Sync Manual Updates to Cloud"):
            new_photos = final_ed[(final_ed['Photo Taken'] == True) & (final_ed['Already_Photo'] == False)]
            new_dist = final_ed[(final_ed['Distributed'] == True) & (final_ed['Already_Dist'] == False)]
            
            updated = False
            with st.spinner("Writing updates to BPS_Database..."):
                if not new_photos.empty:
                    batch_log_action("photo_log", new_photos, "Taken")
                    updated = True
                if not new_dist.empty:
                    batch_log_action("id_card_log", new_dist, "Distributed")
                    updated = True
                    
            if updated:
                st.success("✅ Successfully synced updates to Cloud!")
                st.rerun()
            else:
                st.info("No new boxes were checked to sync.")

# ==========================================
# TAB 4: PENDING PHOTOS TODAY
# ==========================================
with tabs[3]:
    st.subheader("📋 Students Present Today Missing Photos")
    st.write("Generates a PDF list of students who are in school today but haven't had their photos taken yet.")
    
    today_str = datetime.now().strftime("%d-%m-%Y")
    df_mdm = fetch_sheet_data("mdm_log")
    
    if not df_mdm.empty:
        # Filter MDM Log for today
        df_mdm['Date'] = df_mdm['Date'].astype(str)
        today_present = df_mdm[df_mdm['Date'] == today_str].copy()
        
        if not today_present.empty:
            today_present['Key'] = today_present['Class'].astype(str) + "_" + today_present['Roll'].astype(str)
            
            # Fetch all taken photos keys (from DB Explorer logic)
            df_photo_local = fetch_sheet_data("photo_log")
            photo_keys_local = []
            if not df_photo_local.empty:
                df_photo_local['Key'] = df_photo_local['Class'].astype(str) + "_" + df_photo_local['Roll'].astype(str)
                photo_keys_local = df_photo_local[df_photo_local['Action'] == 'Taken']['Key'].unique().tolist()
            
            auto_keys_local = fetch_class_photo_status()
            all_taken_keys = list(set(photo_keys_local + auto_keys_local))
            
            # Filter out students whose photos are already taken
            pending_students = today_present[~today_present['Key'].isin(all_taken_keys)].copy()
            
            if not pending_students.empty:
                # Clean up display columns
                display_cols = ['Class', 'Section', 'Roll', 'Name', 'Time']
                st.dataframe(pending_students[display_cols], hide_index=True, use_container_width=True)
                
                st.write("---")
                if st.button("🖨️ Generate PDF for Teachers", type="primary"):
                    pdf_bytes = generate_pending_photos_pdf(pending_students)
                    st.session_state['pending_pdf_data'] = pdf_bytes
                    st.success("✅ Pending List PDF ready!")
                
                if st.session_state['pending_pdf_data'] is not None:
                    st.download_button(
                        label="📥 Download Pending List (PDF)", 
                        data=st.session_state['pending_pdf_data'], 
                        file_name=f"BPS_Pending_Photos_{datetime.now().strftime('%Y%m%d')}.pdf", 
                        mime="application/pdf"
                    )
            else:
                st.success("🎉 All present students today have had their photos taken!")
        else:
            st.info(f"No MDM/Attendance logs found for today ({today_str}).")
    else:
        st.warning("No MDM data found in the database. Scan students first.")

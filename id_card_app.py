import streamlit as st
import pandas as pd
import qrcode
import os
from fpdf import FPDF
import tempfile
from datetime import datetime

# --- IMPORT THE SCANNER ---
try:
    from streamlit_qrcode_scanner import qrcode_scanner
except ImportError:
    st.error("Please add 'streamlit-qrcode-scanner' to your requirements.txt")
    st.stop()

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="BPS Smart School", page_icon="🏫", layout="centered")

# --- 2. SESSION STATE (To remember scans) ---
if 'attendance_log' not in st.session_state:
    st.session_state['attendance_log'] = pd.DataFrame(columns=['Time', 'Name', 'Roll', 'Mobile', 'Status', 'MDM'])

# --- 3. HELPER FUNCTIONS ---
@st.cache_data
def get_students():
    if os.path.exists('students.csv'):
        try:
            df = pd.read_csv('students.csv')
            if 'Class' in df.columns:
                df['Class'] = df['Class'].replace('CALSS IV', 'CLASS IV')
            for col in ['Section', 'BloodGroup', 'Father', 'Gender', 'DOB', 'Mobile']:
                if col not in df.columns:
                    df[col] = 'N/A'
            return df
        except Exception as e:
            st.error(f"Error loading CSV: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

def parse_qr_data(qr_string):
    """Parses the QR string: 'Name:Suborno|Roll:12|Mob:987...'"""
    try:
        data = {}
        parts = qr_string.split('|')
        for part in parts:
            key, value = part.split(':')
            data[key.strip()] = value.strip()
        return data
    except:
        return None

def generate_pdf(students_list, photo_dict):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    x_start, y_start, card_w, card_h, gap = 10, 10, 86, 54, 8
    col, row = 0, 0
    
    for student in students_list:
        x = x_start + (col * (card_w + gap))
        y = y_start + (row * (card_h + gap))
        
        # Draw Card Background & Header
        pdf.set_draw_color(0, 0, 0); pdf.set_line_width(0.3); pdf.rect(x, y, card_w, card_h)
        pdf.set_fill_color(0, 123, 255); pdf.rect(x, y, card_w, 11, 'F')
        
        # --- 16mm LOGO LOGIC ---
        if os.path.exists('logo.png'): 
            # Set to 16x16mm
            pdf.image('logo.png', x=x+1.5, y=y+1, w=16, h=16)
            
        pdf.set_font("Arial", 'B', 8.5); pdf.set_text_color(255, 255, 255)
        # Shifted text right (x+18) to leave room for the 16mm logo
        pdf.set_xy(x+18, y+1.5); pdf.cell(card_w-19, 5, "BHAGYABANTAPUR PRIMARY SCHOOL", 0, 1, 'C')
        pdf.set_font("Arial", '', 6)
        pdf.set_xy(x+18, y+6.5); pdf.cell(card_w-19, 3, "ID CARD - SESSION 2026", 0, 1, 'C')
        
        # Photo (Will automatically layer over the bottom edge of the oversized logo)
        photo_x, photo_y, photo_w, photo_h = x+3, y+14, 18, 22
        student_id = str(student.get('Sl', 0)) + "_" + str(student.get('Roll', '0'))
        
        if student_id in photo_dict:
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
        pdf.cell(50, line_h, f"{student.get('Name', '')}".upper()[:25], 0, 1); curr_y += 4.5
        pdf.set_font("Arial", '', 7)
        for label, val in [("Father", student.get('Father', '')), ("Class", f"{student.get('Class', '')} | Sec: {student.get('Section', 'A')}"), ("Roll", f"{student.get('Roll', '')} | Sex: {student.get('Gender', '')}"), ("DOB", f"{student.get('DOB', '')} | Blood: {student.get('BloodGroup', '')}")]:
            pdf.set_xy(detail_x, curr_y); pdf.cell(50, line_h, f"{label}: {val}", 0, 1); curr_y += line_h
        pdf.set_xy(detail_x, curr_y); pdf.set_font("Arial", 'B', 7); pdf.cell(50, line_h, f"Mob: {student.get('Mobile', '')}", 0, 1)

        # QR & Sig
        qr_data = f"Name:{student.get('Name', '')}|Roll:{student.get('Roll', '')}|Mob:{student.get('Mobile', '')}"
        qr = qrcode.make(qr_data); qr_path = tempfile.mktemp(suffix=".png"); qr.save(qr_path)
        pdf.image(qr_path, x=x+4.5, y=y+37, w=15, h=15)
        if os.path.exists('signature.png'): pdf.image('signature.png', x=x+58, y=y+41, w=22, h=8)
        
        pdf.set_font("Arial", 'I', 6); pdf.set_xy(x, y+49); pdf.cell(card_w-5, 3, "Sukhamay Kisku", 0, 1, 'R')
        pdf.set_font("Arial", '', 5); pdf.set_xy(x, y+51); pdf.cell(card_w-5, 2, "Head Teacher", 0, 0, 'R')
        
        col += 1
        if col >= 2: col, row = 0, row + 1
        if row >= 5: pdf.add_page(); col, row = 0, 0
            
    return pdf.output(dest='S').encode('latin-1')


# --- 4. TABS LAYOUT ---
tab1, tab2 = st.tabs(["🖨️ ID Card Generator", "📸 MDM & Attendance Scanner"])

# ==========================================
# TAB 1: ID CARD GENERATOR
# ==========================================
with tab1:
    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        if os.path.exists('logo.png'): st.image('logo.png', use_container_width=True)
    st.markdown('<h3 style="text-align:center; color:#007bff;">BPS Student ID Card Generator</h3>', unsafe_allow_html=True)

    df = get_students()
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1: selected_class = st.selectbox("Class", ["All"] + sorted(df['Class'].dropna().unique().tolist()))
        with c2: selected_section = st.selectbox("Section", ["All"] + sorted(df['Section'].dropna().unique().tolist()))

        filtered_df = df.copy()
        if selected_class != "All": filtered_df = filtered_df[filtered_df['Class'] == selected_class]
        if selected_section != "All": filtered_df = filtered_df[filtered_df['Section'] == selected_section]
        
        filtered_df.insert(0, "Select", False)
        edited_df = st.data_editor(filtered_df, hide_index=True, column_config={"Select": st.column_config.CheckboxColumn(required=True)}, disabled=filtered_df.columns.drop("Select"), use_container_width=True)
        selected_students = edited_df[edited_df["Select"] == True].copy()
        
        uploaded_photos = {}
        if not selected_students.empty:
            st.divider()
            st.info(f"Selected {len(selected_students)} students. Upload photos below.")
            for index, student in selected_students.iterrows():
                sid = str(student.get('Sl', index)) + "_" + str(student.get('Roll', '0'))
                with st.expander(f"{student.get('Name')} (Roll: {student.get('Roll')})"):
                    photo = st.file_uploader("Image", type=['jpg','png'], key=f"p_{sid}")
                    if photo: uploaded_photos[sid] = photo.getvalue()
            
            if st.button("Generate PDF"):
                pdf_bytes = generate_pdf(selected_students.to_dict('records'), uploaded_photos)
                st.download_button("📥 Download PDF", pdf_bytes, "bps_cards.pdf", "application/pdf")
    else:
        st.error("students.csv not found")

# ==========================================
# TAB 2: MDM SCANNER
# ==========================================
with tab2:
    st.markdown('<h3 style="text-align:center; color:#28a745;">📸 MDM & Attendance</h3>', unsafe_allow_html=True)
    st.write("Scan a student ID card to mark them **Present** and record **MDM Taken**.")
    
    # 1. The Scanner Component
    qr_code = qrcode_scanner(key='mdm_scanner')
    
    # 2. Process the Scan
    if qr_code:
        data = parse_qr_data(qr_code)
        if data:
            student_name = data.get('Name', 'Unknown')
            student_roll = data.get('Roll', 'Unknown')
            
            # Check if already scanned today to prevent double entry
            existing = st.session_state['attendance_log'][
                (st.session_state['attendance_log']['Name'] == student_name) & 
                (st.session_state['attendance_log']['Roll'] == student_roll)
            ]
            
            if not existing.empty:
                st.warning(f"⚠️ {student_name} is already marked present today!")
            else:
                # Add to session state
                new_entry = pd.DataFrame([{
                    'Time': datetime.now().strftime("%H:%M:%S"),
                    'Name': student_name,
                    'Roll': student_roll,
                    'Mobile': data.get('Mob', 'N/A'),
                    'Status': 'Present',
                    'MDM': 'Yes'
                }])
                st.session_state['attendance_log'] = pd.concat([st.session_state['attendance_log'], new_entry], ignore_index=True)
                st.success(f"✅ **{student_name}** marked PRESENT & MDM TAKEN!")
        else:
            st.error("Invalid QR Code Format. Please scan a valid BPS ID Card.")

    st.divider()
    
    # 3. Show Today's Log
    st.markdown("### 📋 Today's Log")
    if not st.session_state['attendance_log'].empty:
        st.dataframe(st.session_state['attendance_log'], use_container_width=True)
        
        # 4. Download Report
        csv = st.session_state['attendance_log'].to_csv(index=False).encode('utf-8')
        date_str = datetime.now().strftime("%Y-%m-%d")
        st.download_button(
            label="📥 Download Daily MDM Report (CSV)",
            data=csv,
            file_name=f"BPS_MDM_Report_{date_str}.csv",
            mime='text/csv',
        )
    else:
        st.info("No students scanned yet today. Use the camera above to start.")

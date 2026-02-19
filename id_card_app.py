import streamlit as st
import pandas as pd
import qrcode
import os
from fpdf import FPDF
import tempfile

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="BPS ID Card Generator", page_icon="🪪", layout="centered")

# --- 2. STYLING ---
st.markdown("""
    <style>
        .main-header { font-size: 30px; font-weight: bold; color: #007bff; text-align: center; }
        .sub-header { font-size: 18px; color: #555; text-align: center; margin-bottom: 20px; }
        .stButton>button { width: 100%; background-color: #28a745; color: white; }
    </style>
""", unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---
@st.cache_data
def get_students():
    if os.path.exists('students.csv'):
        try:
            df = pd.read_csv('students.csv')
            
            # Fix any known typos in Class names
            if 'Class' in df.columns:
                df['Class'] = df['Class'].replace('CALSS IV', 'CLASS IV')
            
            # Ensure necessary columns exist to prevent errors
            for col in ['Section', 'BloodGroup', 'Father', 'Gender', 'DOB', 'Mobile']:
                if col not in df.columns:
                    df[col] = 'N/A'
            
            return df
        except Exception as e:
            st.error(f"Error loading CSV: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

def generate_pdf(students_list):
    # A4 Size: 210mm x 297mm
    # ID Card Size: 86mm x 54mm (Standard CR80)
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    
    # Grid settings
    x_start = 10
    y_start = 10
    card_w = 86
    card_h = 54
    gap = 8
    
    col = 0
    row = 0
    
    for student in students_list:
        # Calculate position
        x = x_start + (col * (card_w + gap))
        y = y_start + (row * (card_h + gap))
        
        # 1. Card Border
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.3)
        pdf.rect(x, y, card_w, card_h)
        
        # 2. Header (School Name & Logo)
        pdf.set_fill_color(0, 123, 255) # Blue Header
        pdf.rect(x, y, card_w, 11, 'F')
        
        if os.path.exists('logo.png'):
            pdf.image('logo.png', x=x + 2, y=y + 1.5, w=8, h=8)
            
        pdf.set_font("Arial", 'B', 8.5)
        pdf.set_text_color(255, 255, 255)
        
        # Shift text right to avoid overlapping the logo
        pdf.set_xy(x + 10, y + 1.5)
        pdf.cell(card_w - 10, 5, "BHAGYABANTAPUR PRIMARY SCHOOL", 0, 1, 'C')
        pdf.set_font("Arial", '', 6)
        pdf.set_xy(x + 10, y + 6.5)
        pdf.cell(card_w - 10, 3, "ID CARD - SESSION 2026", 0, 1, 'C')
        
        # Reset colors for body
        pdf.set_text_color(0, 0, 0)
        
        # 3. Photo & Placeholder
        photo_x, photo_y, photo_w, photo_h = x + 3, y + 14, 18, 22
        if student.get('PhotoPath') and os.path.exists(student['PhotoPath']):
            pdf.image(student['PhotoPath'], x=photo_x, y=photo_y, w=photo_w, h=photo_h)
            pdf.set_draw_color(0, 0, 0)
            pdf.rect(photo_x, photo_y, photo_w, photo_h)
        else:
            pdf.set_draw_color(200, 200, 200)
            pdf.rect(photo_x, photo_y, photo_w, photo_h) 
            pdf.set_text_color(150, 150, 150)
            pdf.set_font("Arial", '', 5)
            pdf.set_xy(photo_x, photo_y + 8)
            pdf.cell(photo_w, 5, "NO", 0, 1, 'C')
            pdf.set_xy(photo_x, photo_y + 11)
            pdf.cell(photo_w, 5, "PHOTO", 0, 0, 'C')
        
        # 4. Student Details
        pdf.set_text_color(0, 0, 0)
        detail_x = x + 24
        curr_y = y + 14
        line_h = 4
        
        pdf.set_font("Arial", 'B', 9)
        pdf.set_xy(detail_x, curr_y)
        pdf.cell(50, line_h, f"{student.get('Name', '')}".upper()[:25], 0, 1)
        curr_y += 4.5

        pdf.set_font("Arial", '', 7)
        
        pdf.set_xy(detail_x, curr_y)
        pdf.cell(50, line_h, f"Father: {student.get('Father', 'N/A')}", 0, 1)
        curr_y += line_h
        
        pdf.set_xy(detail_x, curr_y)
        pdf.cell(50, line_h, f"Class: {student.get('Class', '')} | Sec: {student.get('Section', 'A')}", 0, 1)
        curr_y += line_h
        
        pdf.set_xy(detail_x, curr_y)
        pdf.cell(50, line_h, f"Roll: {student.get('Roll', '')} | Sex: {student.get('Gender', 'N/A')}", 0, 1)
        curr_y += line_h
        
        pdf.set_xy(detail_x, curr_y)
        pdf.cell(50, line_h, f"DOB: {student.get('DOB', 'N/A')} | Blood: {student.get('BloodGroup', 'N/A')}", 0, 1)
        curr_y += line_h
        
        pdf.set_xy(detail_x, curr_y)
        pdf.set_font("Arial", 'B', 7)
        pdf.cell(50, line_h, f"Mob: {student.get('Mobile', 'N/A')}", 0, 1)
        
        # 5. QR Code
        qr_data = f"Name:{student.get('Name', '')}|Roll:{student.get('Roll', '')}|Mob:{student.get('Mobile', '')}"
        qr = qrcode.make(qr_data)
        qr_path = tempfile.mktemp(suffix=".png")
        qr.save(qr_path)
        pdf.image(qr_path, x=x + 68, y=y + 35, w=15, h=15)
        
        # 6. Signature Area
        if os.path.exists('signature.png'):
            pdf.image('signature.png', x=x + 58, y=y + 42, w=22, h=8)
            
        pdf.set_font("Arial", 'I', 6)
        pdf.set_xy(x, y + 49)
        pdf.cell(card_w - 5, 3, "Sukhamay Kisku", 0, 1, 'R')
        pdf.set_font("Arial", '', 5)
        pdf.set_xy(x, y + 51)
        pdf.cell(card_w - 5, 2, "Head Teacher", 0, 0, 'R')
        
        # Grid Logic (2 columns, 5 rows per page)
        col += 1
        if col >= 2:
            col = 0
            row += 1
        
        if row >= 5:
            pdf.add_page()
            row = 0
            col = 0
            
    return pdf.output(dest='S').encode('latin-1')

# --- 4. APP LAYOUT ---
st.markdown('<p class="main-header">🪪 BPS Student ID Card Generator</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Select students, update details, and attach photos</p>', unsafe_allow_html=True)

df = get_students()

if not df.empty:
    col1, col2 = st.columns(2)
    
    with col1:
        classes = ["All"] + sorted(df['Class'].dropna().unique().tolist())
        selected_class = st.selectbox("Filter by Class", classes)
    
    with col2:
        sections = ["All"] + sorted(df['Section'].dropna().unique().tolist())
        selected_section = st.selectbox("Filter by Section", sections)

    # Apply Filters
    filtered_df = df.copy()
    if selected_class != "All":
        filtered_df = filtered_df[filtered_df['Class'] == selected_class]
    if selected_section != "All":
        filtered_df = filtered_df[filtered_df['Section'] == selected_section]
        
    st.divider()
    
    # Selection and Editing Table
    st.write(f"Found **{len(filtered_df)}** students. Select students and update Blood Groups if needed.")
    filtered_df.insert(0, "Select", False)
    
    # Make 'Select' and 'BloodGroup' the only editable columns
    disabled_cols = filtered_df.columns.drop(["Select", "BloodGroup"])
    
    edited_df = st.data_editor(
        filtered_df,
        hide_index=True,
        column_config={
            "Select": st.column_config.CheckboxColumn(required=True),
            "BloodGroup": st.column_config.SelectboxColumn(
                "Blood Group",
                help="Update missing blood groups here",
                options=["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-", "N/A"],
            )
        },
        disabled=disabled_cols,
        use_container_width=True
    )
    
    # Get selected students
    selected_students = edited_df[edited_df["Select"] == True].copy()
    
    st.divider()
    
    # --- PHOTO UPLOAD SECTION ---
    if not selected_students.empty:
        st.markdown

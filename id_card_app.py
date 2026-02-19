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

# --- 3. DATA HELPER FUNCTIONS ---
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

def generate_pdf(students_list, photo_dict):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    
    x_start, y_start = 10, 10
    card_w, card_h = 86, 54
    gap = 8
    col, row = 0, 0
    
    for student in students_list:
        x = x_start + (col * (card_w + gap))
        y = y_start + (row * (card_h + gap))
        
        # 1. Card Border
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.3)
        pdf.rect(x, y, card_w, card_h)
        
        # 2. Header
        pdf.set_fill_color(0, 123, 255)
        pdf.rect(x, y, card_w, 11, 'F')
        
        if os.path.exists('logo.png'):
            pdf.image('logo.png', x=x + 2, y=y + 1.5, w=8, h=8)
            
        pdf.set_font("Arial", 'B', 8.5)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x + 10, y + 1.5)
        pdf.cell(card_w - 10, 5, "BHAGYABANTAPUR PRIMARY SCHOOL", 0, 1, 'C')
        pdf.set_font("Arial", '', 6)
        pdf.set_xy(x + 10, y + 6.5)
        pdf.cell(card_w - 10, 3, "ID CARD - SESSION 2026", 0, 1, 'C')
        
        pdf.set_text_color(0, 0, 0)
        
        # 3. Photo Logic (Local Only)
        photo_x, photo_y, photo_w, photo_h = x + 3, y + 14, 18, 22
        student_id = str(student.get('Sl', 0)) + "_" + str(student.get('Roll', '0'))
        
        if student_id in photo_dict:
            # Temporarily save the uploaded bytes to place on PDF
            temp_path = tempfile.mktemp(suffix=".jpg")
            with open(temp_path, "wb") as f:
                f.write(photo_dict[student_id])
            try:
                pdf.image(temp_path, x=photo_x, y=photo_y, w=photo_w, h=photo_h)
                pdf.set_draw_color(0, 0, 0)
                pdf.rect(photo_x, photo_y, photo_w, photo_h)
            except:
                pass
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
        pdf.image(qr_path, x=x + 4.5, y=y + 37, w=15, h=15)
        
        # 6. Signature Area
        if os.path.exists('signature.png'):
            pdf.image('signature.png', x=x + 58, y=y + 41, w=22, h=8)
            
        pdf.set_font("Arial", 'I', 6)
        pdf.set_xy(x, y + 49)
        pdf.cell(card_w - 5, 3, "Sukhamay Kisku", 0, 1, 'R')
        pdf.set_font("Arial", '', 5)
        pdf.set_xy(x, y + 51)
        pdf.cell(card_w - 5, 2, "Head Teacher", 0, 0, 'R')
        
        col += 1
        if col >= 2:
            col, row = 0, row + 1
        if row >= 5:
            pdf.add_page()
            col, row = 0, 0
            
    return pdf.output(dest='S').encode('latin-1')

# --- 4. APP LAYOUT ---
col_a, col_b, col_c = st.columns([1, 2, 1])
with col_b:
    if os.path.exists('logo.png'):
        st.image('logo.png', use_container_width=True)

st.markdown('<p class="main-header">🪪 BPS Student ID Card Generator</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Fast Batch Printing Mode</p>', unsafe_allow_html=True)

df = get_students()

if not df.empty:
    col1, col2 = st.columns(2)
    with col1:
        classes = ["All"] + sorted(df['Class'].dropna().unique().tolist())
        selected_class = st.selectbox("Filter by Class", classes)
    with col2:
        sections = ["All"] + sorted(df['Section'].dropna().unique().tolist())
        selected_section = st.selectbox("Filter by Section", sections)

    filtered_df = df.copy()
    if selected_class != "All": filtered_df = filtered_df[filtered_df['Class'] == selected_class]
    if selected_section != "All": filtered_df = filtered_df[filtered_df['Section'] == selected_section]
        
    st.divider()
    
    st.write(f"Found **{len(filtered_df)}** students. Select students to print.")
    filtered_df.insert(0, "Select", False)
    disabled_cols = filtered_df.columns.drop(["Select", "BloodGroup"])
    
    edited_df = st.data_editor(
        filtered_df,
        hide_index=True,
        column_config={
            "Select": st.column_config.CheckboxColumn(required=True),
            "BloodGroup": st.column_config.SelectboxColumn("Blood Group", options=["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-", "N/A"])
        },
        disabled=disabled_cols,
        use_container_width=True
    )
    
    selected_students = edited_df[edited_df["Select"] == True].copy()
    
    st.divider()
    
    # --- BATCH PHOTO UPLOAD SECTION ---
    uploaded_photos = {}
    
    if not selected_students.empty:
        st.markdown('### 📷 Add Photos for Selected Students')
        st.info("Upload photos here. They will be placed on the ID cards immediately when you click Generate.")
        
        for index, student in selected_students.iterrows():
            student_id = str(student.get('Sl', index)) + "_" + str(student.get('Roll', '0'))
            
            with st.expander(f"Photo: {student.get('Name', 'Unknown')} (Class: {student.get('Class', '')}, Roll: {student.get('Roll', '0')})"):
                photo = st.file_uploader("Choose Image", type=['jpg', 'jpeg', 'png'], key=f"photo_{student_id}")
                if photo is not None:
                    uploaded_photos[student_id] = photo.getvalue()
                    st.image(photo, width=150)

        st.divider()
        
        # --- GENERATION BUTTON ---
        c1, c2 = st.columns([1, 2])
        with c1:
            if st.button("Select All in Filtered List"):
                st.info("Tip: Click the checkbox at the very top of the 'Select' column in the table to select all.")

        with c2:
            if st.button(f"🖨️ Generate PDF for {len(selected_students)} Students"):
                with st.spinner("Building PDF..."):
                    student_data = selected_students.to_dict('records')
                    pdf_bytes = generate_pdf(student_data, uploaded_photos)
                    
                    st.download_button(
                        label="📥 Download Ready! Click to Save PDF",
                        data=pdf_bytes,
                        file_name="bps_id_cards_batch.pdf",
                        mime="application/pdf"
                    )
    else:
        st.warning("Please select at least one student from the table above.")

else:
    st.error("❌ 'students.csv' file not found.")

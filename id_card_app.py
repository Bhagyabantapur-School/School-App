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
def get_students():
    if os.path.exists('students.csv'):
        try:
            df = pd.read_csv('students.csv')
            # Standardize column names if needed
            if 'Section' not in df.columns: df['Section'] = 'A'
            return df
        except: return pd.DataFrame()
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
    gap = 10
    
    col = 0
    row = 0
    
    for student in students_list:
        # Calculate position
        x = x_start + (col * (card_w + gap))
        y = y_start + (row * (card_h + gap))
        
        # Draw Card Border
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.3)
        pdf.rect(x, y, card_w, card_h)
        
        # Header (School Name)
        pdf.set_fill_color(0, 123, 255) # Blue Header
        pdf.rect(x, y, card_w, 12, 'F')
        pdf.set_font("Arial", 'B', 10)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x, y + 2)
        pdf.cell(card_w, 5, "Bhagyabantapur Primary School", 0, 1, 'C')
        pdf.set_font("Arial", '', 7)
        pdf.set_xy(x, y + 7)
        pdf.cell(card_w, 3, "Est: 19XX | ID CARD 2026", 0, 1, 'C')
        
        # Reset colors for body
        pdf.set_text_color(0, 0, 0)
        
        # Student Photo Placeholder
        pdf.rect(x + 5, y + 16, 20, 25) # Box for photo
        pdf.set_font("Arial", '', 6)
        pdf.set_xy(x + 5, y + 25)
        pdf.cell(20, 5, "PHOTO", 0, 0, 'C')
        
        # Student Details
        detail_x = x + 30
        detail_y = y + 16
        line_height = 5
        
        pdf.set_font("Arial", 'B', 12)
        pdf.set_xy(detail_x, detail_y)
        pdf.cell(50, line_height, student['Name'][:20], 0, 1) # Truncate long names
        
        pdf.set_font("Arial", '', 9)
        pdf.set_xy(detail_x, detail_y + 6)
        pdf.cell(50, line_height, f"Class: {student['Class']} ({student.get('Section', 'A')})", 0, 1)
        
        pdf.set_xy(detail_x, detail_y + 11)
        pdf.cell(50, line_height, f"Roll No: {student['Roll']}", 0, 1)
        
        # Generate QR Code
        qr_data = f"{student['Name']}|{student['Class']}|{student['Roll']}"
        qr = qrcode.make(qr_data)
        qr_path = tempfile.mktemp(suffix=".png")
        qr.save(qr_path)
        
        # Place QR Code
        pdf.image(qr_path, x=x + 65, y=y + 35, w=18, h=18)
        
        # Footer
        pdf.set_font("Arial", 'I', 6)
        pdf.set_xy(x, y + 48)
        pdf.cell(card_w, 4, "Head Teacher Signature", 0, 0, 'R')
        
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
st.markdown('<p class="sub-header">Select students to generate printable ID cards</p>', unsafe_allow_html=True)

df = get_students()

if not df.empty:
    col1, col2 = st.columns(2)
    
    with col1:
        # Filter by Class
        classes = ["All"] + sorted(df['Class'].unique().tolist())
        selected_class = st.selectbox("Filter by Class", classes)
    
    with col2:
        # Filter by Section
        sections = ["All"] + sorted(df['Section'].unique().tolist()) if 'Section' in df.columns else ["A"]
        selected_section = st.selectbox("Filter by Section", sections)

    # Apply Filters
    filtered_df = df.copy()
    if selected_class != "All":
        filtered_df = filtered_df[filtered_df['Class'] == selected_class]
    if selected_section != "All":
        filtered_df = filtered_df[filtered_df['Section'] == selected_section]
        
    st.divider()
    
    # Selection Table
    st.write(f"Found **{len(filtered_df)}** students.")
    
    # Add a "Select" checkbox to the dataframe
    # We use st.data_editor to allow selection
    filtered_df.insert(0, "Select", False)
    
    edited_df = st.data_editor(
        filtered_df,
        hide_index=True,
        column_config={"Select": st.column_config.CheckboxColumn(required=True)},
        disabled=filtered_df.columns.drop("Select"),
        use_container_width=True
    )
    
    # Get selected students
    selected_students = edited_df[edited_df["Select"] == True]
    
    st.divider()
    
    # Buttons
    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("Select All in List"):
            # This is a UI trick, Streamlit data_editor doesn't support programmatic select all easily
            # So we just pass the whole filtered_df to the generator
            selected_students = filtered_df
            st.success(f"Selected all {len(filtered_df)} students!")

    with c2:
        if not selected_students.empty:
            if st.button(f"🖨️ Generate PDF for {len(selected_students)} Students"):
                # Convert to list of dicts for the PDF function
                student_data = selected_students.to_dict('records')
                pdf_bytes = generate_pdf(student_data)
                
                st.download_button(
                    label="📥 Download ID Cards (PDF)",
                    data=pdf_bytes,
                    file_name="bps_id_cards.pdf",
                    mime="application/pdf"
                )
        else:
            st.warning("Please select at least one student.")

else:
    st.error("❌ 'students.csv' file not found. Please upload student data in the main app first.")
import streamlit as st
import pandas as pd
from fpdf import FPDF # Requires fpdf2 (pip install fpdf2)

# --- 1. Load Data ---
@st.cache_data
def load_data():
    try:
        return pd.read_csv("students.csv")
    except FileNotFoundError:
        return pd.DataFrame() # Return empty if not found

df = load_data()

# --- 2. PDF Generation Class ---
class BPS_Survey(FPDF):
    def __init__(self):
        # A5 Format (Portrait orientation: 148mm x 210mm)
        super().__init__(orientation='P', unit='mm', format='A5')
        self.add_font('Bengali', '', 'Bengali.ttf')
        self.set_text_shaping(True) # HarfBuzz engine for correct conjuncts

    def draw_digit_boxes(self, x, y):
        """Draws 10 consecutive 8x8mm boxes for 10-digit phone numbers"""
        box_size = 8 # INCREASED BOX SIZE
        for i in range(10):
            self.rect(x + (i * box_size), y, box_size, box_size)

    def draw_single_form(self, x, y, row):
        """Draws exactly one survey form at the given x, y coordinates"""
        self.set_xy(x, y)
        
        # --- School Logo ---
        try:
            self.image('logo.png', x, y, 16) 
        except:
            self.rect(x, y, 16, 16)
            self.set_font('Helvetica', 'B', 6)
            self.text(x + 3, y + 8, "LOGO")

        # --- Header ---
        self.set_font('Helvetica', 'B', 12)
        self.set_xy(x + 18, y)
        self.cell(100, 7, "Bhagyabantapur Primary School (BPS)", ln=True)
        
        # INCREASED BENGALI FONT SIZE
        self.set_font('Bengali', '', 12) 
        self.set_x(x + 18)
        self.cell(100, 7, u"অভিভাবক তথ্য যাচাই ফর্ম", ln=True)
        
        # --- Student Info Table ---
        curr_y = y + 18
        self.rect(x, curr_y, 138, 20) # Wider table to fit A5 width
        
        mobile_val = str(row['Mobile']).split('.')[0] if pd.notna(row['Mobile']) and str(row['Mobile']).strip() != "" else "N/A"
        
        self.set_font('Helvetica', '', 10)
        # Left Column Data
        self.text(x + 3, curr_y + 6, f"Student: {row['Name']}")
        self.text(x + 3, curr_y + 12, f"Father: {row['Father']}")
        self.text(x + 3, curr_y + 18, f"Mother: {row['Mother']}")
        
        # Right Column Data
        self.text(x + 75, curr_y + 6, f"Class: {row['Class']}")
        self.text(x + 75, curr_y + 12, f"Section: {row['Section']}")
        self.text(x + 75, curr_y + 18, f"Mobile: {mobile_val}")
        
        # --- Questions Section ---
        curr_y += 24
        self.set_xy(x, curr_y)
        
        # INCREASED BENGALI FONT SIZE (Size 11 for questions)
        self.set_font('Bengali', '', 11)
        self.cell(28, 6, u"সঠিক ঘরে টিক (")
        self.set_font('ZapfDingbats', '', 10) 
        self.cell(4, 6, "4") # Checkmark
        self.set_font('Bengali', '', 11)
        self.cell(15, 6, u") দিন:")
        self.ln(7)
        
        # --- MOBILE QUESTION ---
        curr_y = self.get_y()
        self.set_xy(x, curr_y)
        self.cell(50, 6, u"এই মোবাইল নম্বরটি কি সঠিক?")
        
        # Draw "Yes" and Box
        self.set_x(x + 55)
        self.cell(10, 6, u"হ্যাঁ")
        self.rect(x + 63, curr_y + 1.5, 4, 4) 
        
        # Draw "No" and Box
        self.set_x(x + 75)
        self.cell(10, 6, u"না")
        self.rect(x + 83, curr_y + 1.5, 4, 4) 
        
        self.set_xy(x, curr_y + 7)
        self.cell(0, 6, u"সঠিক না হলে, সঠিক নম্বরটি দিন:", ln=True)
        self.draw_digit_boxes(x + 2, self.get_y() + 1)
        
        # --- WHATSAPP QUESTION ---
        curr_y = self.get_y() + 11
        self.set_xy(x, curr_y)
        self.cell(55, 6, u"এটি কি আপনার হোয়াটসঅ্যাপ নম্বর?")
        
        # Draw "Yes" and Box
        self.set_x(x + 60)
        self.cell(10, 6, u"হ্যাঁ")
        self.rect(x + 68, curr_y + 1.5, 4, 4) 
        
        # Draw "No" and Box
        self.set_x(x + 80)
        self.cell(10, 6, u"না")
        self.rect(x + 88, curr_y + 1.5, 4, 4) 
        
        self.set_xy(x, curr_y + 7)
        self.cell(0, 6, u"হোয়াটসঅ্যাপ নম্বর না হলে সেটি দিন:", ln=True)
        self.draw_digit_boxes(x + 2, self.get_y() + 1)
        
        # --- Signature Line ---
        curr_y = self.get_y() + 15
        self.set_font('Helvetica', '', 8)
        self.text(x, curr_y, "__________________________")
        self.text(x + 90, curr_y, "__________________________")
        
        self.set_font('Bengali', '', 10) # Larger signature labels
        self.set_xy(x, curr_y + 1)
        self.cell(40, 6, u"অভিভাবকের স্বাক্ষর")
        self.set_xy(x + 90, curr_y + 1)
        self.cell(30, 6, u"তারিখ")

# --- 3. Streamlit UI ---
st.set_page_config(page_title="BPS Survey Generator", layout="wide") 
st.title("📋 BPS Guardian Update Form (2-per-A5)")

if df.empty:
    st.error("⚠️ 'students.csv' not found or is empty.")
    st.stop()

# Ensure missing sections don't break the dropdown
if 'Section' not in df.columns:
    df['Section'] = "A" 
df['Section'] = df['Section'].fillna("N/A").astype(str)

# --- Class & Section Selection Logic ---
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    available_classes = sorted(df['Class'].dropna().unique())
    selected_class = st.selectbox("1. Select Class:", available_classes)

class_df = df[df['Class'] == selected_class]

with col2:
    available_sections = sorted(class_df['Section'].unique())
    selected_section = st.selectbox("2. Select Section:", available_sections)

final_df = class_df[class_df['Section'] == selected_section]

with col3:
    st.write(f"**3. Students in {selected_class} - {selected_section}:**")
    select_all = st.checkbox(f"Select All {len(final_df)} Students", value=True)
    
    if select_all:
        selected_indices = final_df.index.tolist()
    else:
        selected_indices = st.multiselect(
            "Choose specific students:", 
            final_df.index, 
            format_func=lambda i: f"{final_df.loc[i]['Name']} (Roll: {final_df.loc[i].get('Roll', 'N/A')})"
        )

# --- Generation Button ---
if st.button("Generate PDF Forms (A5)", type="primary"):
    if not selected_indices:
        st.warning("Please select at least one student.")
    else:
        with st.spinner(f"Generating PDF for {selected_class} - {selected_section}..."):
            pdf = BPS_Survey()
            
            # Loop processes 2 forms per A5 page
            for i in range(0, len(selected_indices), 2):
                pdf.add_page()
                
                # Top form and Bottom form coordinates (X, Y)
                y_coords = [6, 110] 
                
                for j in range(2):
                    if i + j < len(selected_indices):
                        student_data = df.loc[selected_indices[i + j]]
                        pdf.draw_single_form(x=5, y=y_coords[j], row=student_data)
            
            pdf_bytes = bytes(pdf.output())
            
        st.success(f"Successfully generated {len(selected_indices)} forms on {pdf.page_no()} pages!")
        
        st.download_button(
            label="⬇️ Download Survey Forms (PDF)", 
            data=pdf_bytes, 
            file_name=f"BPS_Surveys_Class_{selected_class}_Sec_{selected_section}.pdf",
            mime="application/pdf"
        )
